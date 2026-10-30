#!/bin/sh
set -eu
mkdir -p /run/samba /var/log/samba /var/lib/samba/private /var/lib/samba/lock /srv/samba/share
getent group smbusers >/dev/null 2>&1 || groupadd --system smbusers
id fileshare >/dev/null 2>&1 || useradd --system --gid smbusers --home-dir /srv/samba/share --shell /usr/sbin/nologin fileshare
chown -R fileshare:smbusers /srv/samba/share
chmod 2770 /srv/samba/share
testparm -s /etc/samba/smb.conf >/dev/null
# Webmin is configured for HTTP only; no certificate/key is generated or required.
if [ ! -f /etc/webmin/miniserv.conf ]; then
  mkdir -p /etc/webmin
  printf '%s\n' 'port=10000' 'bind=0.0.0.0' 'ssl=0' 'listen=10000' > /etc/webmin/miniserv.conf
fi
/usr/sbin/smbd --foreground --no-process-group &
SMBD_PID=$!
if [ -x /usr/share/webmin/miniserv.pl ]; then
  perl /usr/share/webmin/miniserv.pl /etc/webmin/miniserv.conf &
  WEBMIN_PID=$!
else
  echo "Webmin server entrypoint missing" >&2
  exit 1
fi
term() { kill "$SMBD_PID" "$WEBMIN_PID" 2>/dev/null || true; wait || true; }
trap term INT TERM
while kill -0 "$SMBD_PID" 2>/dev/null && kill -0 "$WEBMIN_PID" 2>/dev/null; do sleep 2; done
term
exit 1
