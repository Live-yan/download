#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
OUT=/work/native-evidence
mkdir -p "$OUT"
exec > >(tee "$OUT/prerequisites.log") 2>&1
test "$(uname -m)" = aarch64
test -s /etc/pki/rpm-gpg/RPM-GPG-KEY-kylin
cat /etc/os-release
rpm -q glibc rpm systemd
rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-kylin
mkdir -p /tmp/native-probe-repos
cat >/tmp/native-probe-repos/kylin.repo <<'EOF'
[probe-kylin-base]
name=Kylin V10 SP3 2403 Base aarch64
baseurl=https://update.cs2c.com.cn/NS/V10/V10SP3-2403/os/adv/lic/base/aarch64/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-kylin
[probe-kylin-updates]
name=Kylin V10 SP3 2403 Updates aarch64
baseurl=https://update.cs2c.com.cn/NS/V10/V10SP3-2403/os/adv/lic/updates/aarch64/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-kylin
EOF
DNF=(dnf --setopt=reposdir=/tmp/native-probe-repos '--disablerepo=*'
 --enablerepo=probe-kylin-base,probe-kylin-updates --setopt=install_weak_deps=False)
"${DNF[@]}" -y install dnf-plugins-core
candidates=(gcc gcc-c++ make binutils rpm-build rpm-devel createrepo_c
 python3 python3-devel perl perl-Parse-Yapp perl-ExtUtils-MakeMaker
 pkgconfig pkgconf-pkg-config gnutls-devel libacl-devel libattr-devel libcap-devel
 jansson-devel pam-devel popt-devel zlib-devel libarchive-devel libicu-devel
 libuuid-devel libblkid-devel readline-devel ncurses-devel systemd-devel
 krb5-devel openldap-devel lmdb-devel dbus-devel libtirpc-devel flex bison libxslt docbook-style-xsl
 tar gzip xz curl patch perl-Digest-SHA perl-Encode-Detect perl-IO-Tty perl-Net-SSLeay)
: >"$OUT/available.tsv"
: >"$OUT/missing.txt"
for package in "${candidates[@]}"; do
 result=$("${DNF[@]}" repoquery --available --archlist=aarch64,noarch --qf '%{name} %{epoch}:%{version}-%{release} %{arch}' "$package")
 if [[ -n "$result" ]]; then printf '%s\n' "$result" >>"$OUT/available.tsv"
 else printf '%s\n' "$package" >>"$OUT/missing.txt"; fi
done
cat "$OUT/available.tsv"
cat "$OUT/missing.txt"
required=(gcc gcc-c++ make binutils rpm-build createrepo_c python3 python3-devel
 perl perl-Parse-Yapp gnutls-devel libacl-devel libattr-devel libcap-devel
 jansson-devel pam-devel popt-devel zlib-devel libarchive-devel libicu-devel
 libuuid-devel libblkid-devel readline-devel ncurses-devel systemd-devel
 krb5-devel openldap-devel lmdb-devel dbus-devel libtirpc-devel flex bison tar gzip xz curl patch pkgconfig)
"${DNF[@]}" -y install "${required[@]}"
rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' | sort >"$OUT/installed.tsv"
gcc --version
python3 --version
python3 -c 'import sys; assert sys.version_info >= (3,6,0), sys.version'
perl -MParse::Yapp -e 'print "$Parse::Yapp::VERSION\n"'
pkg-config --modversion gnutls
cat >/tmp/getrandom-check.c <<'EOF'
#include <sys/random.h>
int main(void) { char x; return getrandom(&x, 0, 0) < 0; }
EOF
if gcc /tmp/getrandom-check.c -o /tmp/getrandom-check; then minimum=3.6.13; else minimum=3.7.2; fi
pkg-config --atleast-version="$minimum" gnutls
printf 'Prerequisite probe passed; NOT a package or native VM acceptance result.\n'
