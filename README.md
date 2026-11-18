# SSL 证书更新工具

根据规则文件将 PFX 证书转换为 PEM/RSA/CRT 格式，并同步到各服务器及重载 Nginx。

## 使用方法

```bash
./update-certificates.sh -r <规则名称>
```

`<规则名称>` 对应 `rules/` 目录下的规则文件名（不含扩展名），例如：

```bash
./update-certificates.sh -r wild.example.com
```

脚本会自动完成：

1. **转换（convert）**：从 PFX 提取证书，生成 `example.pem` / `example.rsa` / `example.crt`
2. **同步（sync）**：将 `example.rsa`、`example.crt` 上传到规则中列出的服务器，执行 `nginx -t` 校验后 `sudo nginx -s reload` 重载

任一步骤失败会写入对应日志并以非零码终止（后续步骤不再执行）。

## 目录结构

```
update-certificates.sh   # 入口脚本（自动创建 .venv 并按 requirements.txt 安装依赖）
main.py                  # 解析 -r 参数、加载规则、依次执行 convert → sync
src/
  convert.py             # 证书转换（openssl）
  sync.py                # 证书同步 + nginx 重载（paramiko SFTP/SSH）
  pathutil.py            # 规则路径表达式解析（glob / :last-modified / :latest-modified）
rules/                   # 规则文件（YAML）
servers-ssh.ini          # 服务器连接配置（INI，按 [服务器名称] 分节）
certificates/            # 源 PFX 证书
output/                  # 转换输出（按 <证书名>/<时间戳>/ 组织）
logs/                    # convert.log / sync.log（运行时生成）
```

## 规则文件格式

位于 `rules/<规则名称>.yml`，包含 `convert` 和 `sync` 两部分：

```yaml
convert:
  from: ./certificates/wild.example.com/*.pfx(:last-modified)
  output: ./output
sync:
  from: ./output/wild.example.com/:latest-modified/example.{rsa,crt}
  servers: example-server1,example-server2,example-server3
```

### 字段说明

| 字段 | 说明 |
|---|---|
| `convert.from` | 源 PFX 路径（支持通配符，见下方路径语法） |
| `convert.output` | 转换输出根目录；实际输出为 `<output>/<证书名>/<YYYYMMDD-HHMMSS>/` |
| `sync.from` | 待同步文件路径（通常指向最新一次转换输出） |
| `sync.servers` | 逗号分隔的服务器名称列表，对应 `servers-ssh.ini` 中的节名 |

### 路径语法

- **通配符**：`*`、`?`、`[...]`，以及花括号选择 `example.{rsa,crt}`
- **`(:last-modified)`**（结尾选择器）：在所有匹配结果中取修改时间最新的一个，如 `*.pfx(:last-modified)`
- **`:latest-modified`**（路径组件）：在该层级取修改时间最新的子目录，如 `./output/wild.example.com/:latest-modified/...`

相对路径均相对于项目根目录解析。

## 服务器配置

`servers-ssh.ini`，每个服务器一节：

```ini
[example-server1]
server=ip-address    # IP / 主机名
name=name          # SSH 用户名
psw=******               # SSH 密码（sudo 密码默认同此密码）
copyto=path-to-folder   # 证书上传目标目录
```

同步流程：SFTP 上传 `sync.from` 匹配的文件 → `sudo nginx -t` 校验 → `sudo nginx -s reload` 重载。`nginx -t` 失败则不会重载。

## 环境要求

- macOS / Linux，`python3`（≥3.9）、`openssl`
- 首次运行自动创建 `.venv` 并按 `requirements.txt` 安装依赖（当前为 `pyyaml`、`paramiko`，pip 源为清华镜像）
- **依赖安装强制 `--only-binary=:all:`**：本机装有 IT 文件加密工具，`.py` 落盘为密文，源码编译类进程读到密文会产出损坏的 wheel，因此只允许使用预编译 wheel

## 日志与排错

- `logs/convert.log` — 转换失败原因
- `logs/sync.log` — 每台服务器的上传 / nginx 命令记录及失败原因

常见问题：

| 现象 | 处理 |
|---|---|
| `规则文件不存在` | 确认 `rules/<名称>.yml` 存在（仅支持 `.yml`/`.yaml`） |
| `nginx: command not found` | 已通过 `sudo` 调用规避；若仍出现，检查该用户 sudo 权限 |
| `[Errno 13] Permission denied`（上传） | 检查 `copyto` 目录是否可写、目标文件属主 |
| pip 安装报 `source code string cannot contain null bytes` | IT 加密工具干扰源码编译，删除 `.venv` 后重跑（脚本会用 `--only-binary` 重建） |
