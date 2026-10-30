#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "用法: $0 start|stop|restart" >&2; exit 2; }
case "$1" in start|stop|restart) ;; *) exit 2;; esac
if [ "$1" != stop ] && ! systemctl is-active --quiet webmin-offline.service; then
 command -v ss >/dev/null
 if ss -H -ltn 'sport = :10000' | grep -q .; then
  echo '10000 端口已被其他服务占用，请人工处理；没有停止旧服务。' >&2
  exit 1
 fi
fi
exec systemctl "$1" webmin-offline.service
