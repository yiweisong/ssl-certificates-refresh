#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import yaml

from src.convert import run_convert
from src.sync import run_sync


def main() -> int:
    parser = argparse.ArgumentParser(description='根据规则更新 SSL 证书')
    parser.add_argument(
        '-r', '--rule', required=True,
        help='规则名称（rules 目录下的文件名，不含扩展名）',
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent

    rule_file = None
    for ext in ('.yml', '.yaml'):
        candidate = root / 'rules' / f'{args.rule}{ext}'
        if candidate.is_file():
            rule_file = candidate
            break
    if rule_file is None:
        print(f'规则文件不存在: rules/{args.rule}.yml', file=sys.stderr)
        return 2

    with open(rule_file, encoding='utf-8') as f:
        rule = yaml.safe_load(f) or {}

    if rule.get('convert'):
        run_convert(rule['convert'], args.rule, root)
    if rule.get('sync'):
        run_sync(rule['sync'], root)
    if not rule.get('convert') and not rule.get('sync'):
        print(f'规则文件为空或缺少 convert/sync 配置: {rule_file}',
              file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
