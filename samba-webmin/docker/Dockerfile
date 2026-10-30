FROM --platform=linux/arm64 debian:13-slim
ARG DEBIAN_FRONTEND=noninteractive
ARG SAMBA_VERSION=4.22.11
ARG WEBMIN_VERSION=2.670
RUN apt-get update && apt-get install -y --no-install-recommends \
    acl attr ca-certificates curl gcc g++ make pkg-config python3 python3-dev \
    python3-dnspython python3-cryptography python3-markdown python3-requests \
    python3-setproctitle python3-ldb python3-tdb python3-talloc python3-tevent \
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
 && ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
      --with-privatedir=/var/lib/samba/private --with-lockdir=/run/samba \
      --with-statedir=/var/lib/samba --without-ad-dc \
 && make -j"$(nproc)" && make install DESTDIR=/stage \
 && cp -a /stage/. / \
 && rm -rf /stage /tmp/build
RUN curl -fsSL https://download.webmin.com/download/2.0/webmin-${WEBMIN_VERSION}.tar.gz -o /tmp/webmin.tar.gz \
 && mkdir -p /usr/share/webmin \
 && tar -xzf /tmp/webmin.tar.gz --strip-components=1 -C /usr/share/webmin \
 && rm -f /tmp/webmin.tar.gz
COPY smb.conf /etc/samba/smb.conf
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
COPY manage.sh /usr/local/sbin/manage.sh
RUN chmod 0755 /usr/local/sbin/entrypoint.sh /usr/local/sbin/manage.sh \
 && mkdir -p /var/lib/samba/private /var/lib/samba/lock /var/lib/samba/state /srv/samba/share \
 && (getent group smbusers >/dev/null 2>&1 || groupadd --system smbusers) \
 && (id fileshare >/dev/null 2>&1 || useradd --system --gid smbusers --home-dir /srv/samba/share --shell /usr/sbin/nologin fileshare)
EXPOSE 445
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD testparm -s >/dev/null 2>&1 && pgrep smbd >/dev/null && pgrep -f miniserv.pl >/dev/null
ENTRYPOINT ["/usr/bin/tini","--","/usr/local/sbin/entrypoint.sh"]
