import configparser
import logging
import shlex
from pathlib import Path

import paramiko

from .pathutil import resolve_pattern


def _get_logger(root: Path) -> logging.Logger:
    log_dir = root / 'logs'
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger('sync')
    if not logger.handlers:
        handler = logging.FileHandler(log_dir / 'sync.log', encoding='utf-8')
        handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _load_servers(ini_path: Path, names: list[str]) -> list[dict]:
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ini_path, encoding='utf-8')
    servers = []
    for name in names:
        if name not in cp:
            raise KeyError(f'服务器 [{name}] 不存在于 {ini_path}')
        sec = cp[name]
        servers.append({
            'name': name,
            'host': sec['server'],
            'user': sec['name'],
            'psw': sec['psw'],
            'copyto': sec['copyto'],
        })
    return servers


def _exec(client: paramiko.SSHClient, cmd: str, srv: dict,
          log: logging.Logger) -> str:
    log.info('  [%s] 执行: %s', srv['name'], cmd)
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    rc = stdout.channel.recv_exit_status()
    if rc != 0:
        raise RuntimeError(
            f'[{srv["name"]}] 命令失败 (rc={rc}): {cmd}\n{out}{err}'
        )
    return out


def _sync_one(files: list[Path], srv: dict, log: logging.Logger) -> None:
    log.info('同步到 %s (%s@%s)', srv['name'], srv['user'], srv['host'])
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            srv['host'], username=srv['user'], password=srv['psw'],
            timeout=30,
        )
        sftp = client.open_sftp()
        try:
            for f in files:
                remote = srv['copyto'].rstrip('/') + '/' + f.name
                sftp.put(str(f), remote)
                log.info('  已上传 %s -> %s', f, remote)
        finally:
            sftp.close()

        # 参考 sync-to-server.md：先 nginx -t 校验，再 sudo reload。
        # 非交互 SSH 的 PATH 常无 /usr/sbin，nginx 一律经 sudo 调用
        psw = shlex.quote(srv['psw'])
        _exec(client, f'echo {psw} | sudo -S nginx -t', srv, log)
        _exec(client, f'echo {psw} | sudo -S nginx -s reload', srv, log)
        log.info('  [%s] nginx 已重载', srv['name'])
    finally:
        client.close()


def run_sync(cfg: dict, root: Path) -> None:
    """执行同步操作；失败时写入 ./logs/sync.log 并以非零码退出。"""
    log = _get_logger(root)
    try:
        files = [p for p in resolve_pattern(cfg['from'], root) if p.is_file()]
        if not files:
            raise FileNotFoundError(f"sync.from 没有匹配到文件: {cfg['from']}")

        names = [n.strip() for n in str(cfg['servers']).split(',') if n.strip()]
        servers = _load_servers(root / 'servers-ssh.ini', names)

        for srv in servers:
            _sync_one(files, srv, log)

        log.info('同步成功: %d 个文件 -> %d 台服务器', len(files), len(servers))
        print(f'[sync] 成功: {len(files)} 个文件 -> {len(servers)} 台服务器')
    except Exception as e:
        log.error('同步失败: %s', e)
        print(f'[sync] 失败: {e}', flush=True)
        raise SystemExit(1)
