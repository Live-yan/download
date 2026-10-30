FROM debian:13-slim AS builder
ARG DEBIAN_FRONTEND=noninteractive
ARG SAMBA_VERSION=4.22.11
ARG WEBMIN_VERSION=2.670
RUN apt-get update && apt-get install -y --no-install-recommends \
    passwd acl attr ca-certificates curl gcc g++ make flex bison xsltproc docbook-xml docbook-xsl libparse-yapp-perl pkg-config python3 python3-dev \
    python3-dnspython python3-cryptography python3-markdown python3-requests \
    python3-setproctitle python3-ldb python3-tdb python3-talloc \
    libacl1-dev libarchive-dev libattr1-dev libavahi-client-dev libblkid-dev \
    libbsd-dev libcups2-dev libcap-dev libgnutls28-dev libgpgme-dev \
    libicu-dev libjansson-dev libldap2-dev libldb-dev liblmdb-dev libncurses-dev \
    libnss-wrapper libpam0g-dev libpopt-dev libreadline-dev libssl-dev \
    libsystemd-dev libtasn1-dev libtdb-dev libtevent-dev libtalloc-dev \
    libtirpc-dev libunwind-dev liburing-dev zlib1g-dev \
    perl perl-modules libio-socket-ssl-perl libnet-ssleay-perl \
    procps smbclient tini wget xz-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/build
RUN curl -fsSLO https://download.samba.org/pub/samba/stable/samba-${SAMBA_VERSION}.tar.gz \
 && tar -xzf samba-${SAMBA_VERSION}.tar.gz \
 && cd samba-${SAMBA_VERSION} \
 && ./configure --enable-fhs --prefix=/usr --sysconfdir=/etc/samba --localstatedir=/var \
      --with-privatedir=/var/lib/samba/private --with-lockdir=/run/samba \
      --with-statedir=/var/lib/samba --without-ad-dc \
 && make -j"$(nproc)" && make install DESTDIR=/stage \
 && mkdir -p /stage/run \
 && if [ -d /stage/var/run ]; then cp -a /stage/var/run/. /stage/run/; rm -rf /stage/var/run; fi \
 && cp -a /stage/. / && ldconfig \
 && rm -rf /tmp/build
RUN curl -fsSL https://github.com/webmin/webmin/releases/download/${WEBMIN_VERSION}/webmin-${WEBMIN_VERSION}.tar.gz -o /tmp/webmin.tar.gz \
 && echo '617af07a890bea18a83dca5c9d7168de1ad4d5f3076d8a1df3475f123748dc21  /tmp/webmin.tar.gz' | sha256sum -c - \
 && mkdir -p /usr/share/webmin \
 && tar -xzf /tmp/webmin.tar.gz --strip-components=1 -C /usr/share/webmin \
 && rm -f /tmp/webmin.tar.gz
RUN python3 - <<'PY'
from pathlib import Path
p=Path("/usr/share/webmin/setup.sh")
s=p.read_text()
old="\topenssl version >/dev/null 2>&1\n"
assert s.count(old)==1, "Pinned Webmin setup TLS block changed"
p.write_text(s.replace(old,"\tfalse # HTTP-only: no TLS key generation\n"))
PY
RUN config_dir=/etc/webmin var_dir=/var/webmin perl=/usr/bin/perl autoos=1 \
    port=10000 login=root crypt=x ssl=0 atboot=0 nostart=1 nopostinstall=1 \
    /bin/sh /usr/share/webmin/setup.sh </dev/null \
 && test -s /etc/webmin/config && test -s /etc/webmin/samba/config \
 && grep -qx 'root:x:0' /etc/webmin/miniserv.users \
 && test ! -e /etc/webmin/miniserv.pem && passwd -l root
COPY smb.conf /etc/samba/smb.conf
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN chmod 0755 /usr/local/sbin/entrypoint.sh \
 && mkdir -p /var/lib/samba/private /run/samba /var/log/samba /srv/samba/share \
 && groupadd -g 20001 smbusers \
 && useradd -u 20001 --gid smbusers --home-dir /srv/samba/share --shell /usr/sbin/nologin fileshare \
 && chown fileshare:smbusers /srv/samba/share && chmod 2770 /srv/samba/share \
 && chmod 0700 /var/lib/samba/private
RUN python3 - <<'PY'
from pathlib import Path
def update(path,values):
    p=Path(path)
    lines=[l for l in p.read_text().splitlines() if l.split("=",1)[0] not in values]
    p.write_text("\n".join(lines+[f"{k}={v}" for k,v in values.items()])+"\n")
update("/etc/webmin/miniserv.conf",dict(bind="0.0.0.0",port="10000",listen="10000",ipv6="0",ssl="0",ssl_enforce="0",no_ssl_warn="1",no_pam="1",passwd_file="/etc/shadow",passwd_uindex="0",passwd_pindex="1",passwd_cindex="2",passwd_mindex="4",passwd_blank="0",passwd_mode="0",trust_real_ip="0",logtrust="0"))
update("/etc/webmin/config",dict(lang="zh_CN.UTF-8"))
update("/etc/webmin/samba/config",dict(smb_conf="/etc/samba/smb.conf",samba_password_program="/usr/bin/smbpasswd",samba_status_program="/usr/bin/smbstatus",samba_server="/usr/sbin/smbd",pdbedit="/usr/bin/pdbedit",net="/usr/bin/net",restart_cmd="/usr/bin/smbcontrol -s /etc/samba/smb.conf all reload-config"))
PY
FROM debian:13-slim
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    passwd acl attr ca-certificates curl python3 python3-cryptography python3-dnspython \
    python3-ldb python3-tdb python3-talloc perl perl-modules \
    libio-socket-ssl-perl libnet-ssleay-perl procps smbclient tini \
    libarchive13t64 libavahi-client3 libgpgme11t64 libjansson4 liblmdb0 liburing2 libunwind8 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /stage/ /
COPY --from=builder /usr/share/webmin/ /usr/share/webmin/
COPY --from=builder /etc/webmin/ /etc/webmin/
COPY --from=builder /etc/samba/smb.conf /etc/samba/smb.conf
COPY --from=builder /usr/local/sbin/entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN ldconfig && groupadd -g 20001 smbusers \
 && useradd -u 20001 --gid smbusers --home-dir /srv/samba/share --shell /usr/sbin/nologin fileshare \
 && passwd -l root \
 && mkdir -p /var/lib/samba/private /run/samba /var/log/samba /var/webmin /srv/samba/share \
 && chown fileshare:smbusers /srv/samba/share && chmod 2770 /srv/samba/share \
 && chmod 0700 /var/lib/samba/private \
 && test -x /usr/bin/smbcontrol && smbd -V \
 && test ! -e /etc/webmin/miniserv.pem
EXPOSE 445 10000
HEALTHCHECK --interval=10s --timeout=8s --start-period=30s --retries=6 CMD testparm -s /etc/samba/smb.conf >/dev/null 2>&1 && pgrep -x smbd >/dev/null && curl -fsS --max-time 5 http://127.0.0.1:10000/session_login.cgi >/dev/null
ENTRYPOINT ["/usr/bin/tini","--","/usr/local/sbin/entrypoint.sh"]
CMD ["serve"]
