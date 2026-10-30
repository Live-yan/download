#!/bin/sh
set -eu
case "${1:-serve}" in
 initialize)
  [ ! -e /etc/.samba-webmin-initialized ] || { echo '已经初始化，不要重复执行。' >&2; exit 1; }
  [ -t 0 ] || { echo '请用交互终端运行 docker compose run --rm initialize' >&2; exit 1; }
  echo '设置容器 root / Webmin 管理密码：'
  passwd root
  echo '设置 fileshare 的共享密码：'
  smbpasswd -c /etc/samba/smb.conf -a fileshare
  umask 077
  : > /etc/.samba-webmin-initialized
  exit 0 ;;
 serve) ;;
 *) echo '仅支持 initialize 或 serve' >&2; exit 2 ;;
esac
[ -f /etc/.samba-webmin-initialized ] || { echo '请先运行 docker compose run --rm initialize' >&2; exit 1; }
for p in /etc/passwd /etc/shadow /etc/group /etc/gshadow /etc/webmin/config /etc/webmin/miniserv.conf /etc/webmin/miniserv.users /etc/webmin/samba/config /etc/samba/smb.conf; do
 [ -s "$p" ] || { echo "配置不完整：$p" >&2; exit 1; }
done
root_hash=$(getent shadow root | cut -d: -f2)
case "$root_hash" in ''|'!'*|'*'*) echo '尚未设置管理密码' >&2; exit 1;; esac
id fileshare >/dev/null
pdbedit -s /etc/samba/smb.conf -L fileshare >/dev/null
python3 - <<'PY'
import os,re
from pathlib import Path
host=os.environ.get("WEBMIN_HOST","")
scheme=os.environ.get("WEBMIN_PUBLIC_SCHEME","https")
port=os.environ.get("WEBMIN_PUBLIC_PORT","443")
if len(host)>253 or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",host): raise SystemExit("WEBMIN_HOST must be a hostname, without scheme/path/port")
if scheme not in ("http","https") or not port.isdecimal() or not 1<=int(port)<=65535: raise SystemExit("Invalid public scheme/port")
def update(path,values):
 p=Path(path)
 lines=[l for l in p.read_text().splitlines() if l.split("=",1)[0] not in values]
 p.write_text("\n".join(lines+[f"{k}={v}" for k,v in values.items()])+"\n")
update("/etc/webmin/config",dict(referers=host))
update("/etc/webmin/miniserv.conf",dict(redirect_host=host,redirect_port=port,redirect_ssl=str(int(scheme=="https")),ssl="0",trust_real_ip="0",logtrust="0"))
PY
mkdir -p /run/samba /var/log/samba /var/lib/samba/private /var/webmin
testparm -s /etc/samba/smb.conf >/dev/null
/usr/sbin/smbd -s /etc/samba/smb.conf --foreground --no-process-group &
SMBD_PID=$!
perl /usr/share/webmin/miniserv.pl --nofork /etc/webmin/miniserv.conf &
WEBMIN_PID=$!
terminate() {
 kill "$SMBD_PID" "$WEBMIN_PID" 2>/dev/null || true
 wait "$SMBD_PID" 2>/dev/null || true
 wait "$WEBMIN_PID" 2>/dev/null || true
}
trap 'terminate; exit 0' INT TERM
while kill -0 "$SMBD_PID" 2>/dev/null && kill -0 "$WEBMIN_PID" 2>/dev/null; do sleep 1; done
echo '服务异常退出，关闭容器。' >&2
terminate
exit 1
