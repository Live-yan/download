#!/bin/sh
set -eu
ACTION=${1:-}
[ "$#" -eq 1 ] || { echo "用法: $0 start|stop|restart" >&2; exit 2; }
case "$ACTION" in start|stop|restart) ;; *) echo "仅支持 start、stop、restart" >&2; exit 2;; esac
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$HERE"
[ -f .env ] || { echo "请先复制并填写 .env.example 为 .env" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "缺少 docker" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "缺少 Docker Compose V2 插件" >&2; exit 1; }
case "$ACTION" in
 start) docker compose up -d --no-build --pull never samba-webmin ;;
 stop) docker compose stop samba-webmin ;;
 restart) docker compose restart samba-webmin ;;
esac
