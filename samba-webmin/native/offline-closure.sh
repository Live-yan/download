#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
name=${1:?samba422 or webmin}
case "$name" in
 samba422) package=samba422-offline; original=$(cat /work/native-evidence/samba-rpm-path.txt);;
 webmin) package=webmin-offline; original=$(cat /work/native-evidence/webmin-rpm-path.txt);;
 *) exit 2;;
esac
expected=$(rpm -qp --qf '%{VERSION}-%{RELEASE}' "$original")
bundle="/work/native-bundles/$name"
evidence="/work/native-evidence/closure/$name"
mkdir -p "$evidence"
exec > >(tee "$evidence/offline-install.log") 2>&1
root=$(mktemp -d)
repos=$(mktemp -d)
trap 'rm -rf "$root" "$repos"' EXIT
test -z "$(find "$root" -mindepth 1 -print -quit)"
mapfile -t applications < <(find "$bundle/application" -maxdepth 1 -name '*.rpm')
test "${#applications[@]}" -eq 1
cmp "$original" "${applications[0]}"
mkdir -p "$root/etc/pki/rpm-gpg"
cp "$bundle/keys/RPM-GPG-KEY-kylin" "$root/etc/pki/rpm-gpg/"
rpm --root "$root" --initdb
rpm --root "$root" --import /etc/pki/rpm-gpg/RPM-GPG-KEY-kylin
cat >"$repos/offline.repo" <<EOF
[test-vendor]
name=Signed local Kylin dependencies
baseurl=file://$bundle/vendor
enabled=1
gpgcheck=1
gpgkey=file://$bundle/keys/RPM-GPG-KEY-kylin
[test-application]
name=Exact locally built application
baseurl=file://$bundle/application
enabled=1
gpgcheck=0
EOF
dnf -y --installroot="$root" --releasever=V10 --setopt="reposdir=$repos" \
 --disablerepo='*' --enablerepo=test-vendor,test-application \
 --setopt=install_weak_deps=False install "$package-$expected" iproute passwd shadow-utils acl attr
test "$(rpm --root "$root" -q --qf '%{VERSION}-%{RELEASE}' "$package")" = "$expected"
rpm --root "$root" -qa --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' | sort >"$evidence/installed-packages.txt"
if [[ "$name" == samba422 ]]; then
 prefix=/opt/samba-4.22.11
 chroot "$root" "$prefix/sbin/smbd" -V | grep -Fx 'Version 4.22.11'
 chroot "$root" "$prefix/bin/testparm" -s /etc/samba-4.22.11/smb.conf
 : >"$evidence/ldd.txt"
 for binary in sbin/smbd bin/smbclient bin/pdbedit bin/smbcontrol bin/testparm bin/net; do
  test -x "$root$prefix/$binary"
  chroot "$root" /usr/bin/ldd "$prefix/$binary" >>"$evidence/ldd.txt"
 done
 ! grep -Fq 'not found' "$evidence/ldd.txt"
 awk '/lib(talloc|tdb|tevent|ldb)/ && /=>/ {if ($3 !~ "^/opt/samba-4[.]22[.]11/") bad=1} END {exit bad}' "$evidence/ldd.txt"
else
 chroot "$root" /usr/bin/perl -c /usr/libexec/webmin/miniserv.pl
 modules=(lib open FindBin Socket Data::Dumper File::Path File::Basename Digest::SHA Digest::MD5
  Time::Local Time::HiRes Time::Piece Net::SSLeay DateTime DateTime::Locale DateTime::TimeZone
  Encode::Detect Socket6 Sys::Syslog JSON::XS)
 for module in "${modules[@]}"; do
  chroot "$root" /usr/bin/perl -e 'my $m=shift; $m =~ s!::!/!g; require "$m.pm";' "$module"
 done
 grep -qx 'bind=127.0.0.1' "$root/etc/webmin/miniserv.conf"
 grep -qx 'ssl=0' "$root/etc/webmin/miniserv.conf"
 test ! -e "$root/etc/webmin/miniserv.pem"
fi
echo 'PASS: empty-installroot offline userspace closure only; NOT native VM acceptance.'
