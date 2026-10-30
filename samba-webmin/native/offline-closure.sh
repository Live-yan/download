#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
case ${1:?samba422, webmin or combined} in
 samba422) names=(samba422);;
 webmin) names=(webmin);;
 combined) names=(samba422 webmin);;
 *) exit 2;;
esac
case_name=$1
evidence="/work/native-evidence/closure/$case_name"
mkdir -p "$evidence"
exec > >(tee "$evidence/offline-install.log") 2>&1
root=$(mktemp -d)
repos=$(mktemp -d)
trap 'rm -rf "$root" "$repos"' EXIT
test -z "$(find "$root" -mindepth 1 -print -quit)"
mkdir -p "$root/etc/pki/rpm-gpg"
rpm --root "$root" --initdb
packages=()
repoflags=()
for name in "${names[@]}"; do
 bundle="/work/native-bundles/$name"
 case "$name" in
  samba422) original=$(cat /work/native-evidence/samba-rpm-path.txt);;
  webmin) original=$(cat /work/native-evidence/webmin-rpm-path.txt);;
 esac
 mapfile -t apps < <(find "$bundle/application" -maxdepth 1 -name '*.rpm')
 test "${#apps[@]}" -eq 1
 cmp "$original" "${apps[0]}"
 identity=$(rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' "$original")
 packages+=("$identity")
 rpm --root "$root" --import "$bundle/keys/RPM-GPG-KEY-kylin"
 repoflags+=("--enablerepo=test-$name-vendor,test-$name-application")
 cat >"$repos/$name.repo" <<EOF
[test-$name-vendor]
name=Signed local Kylin dependencies
baseurl=file://$bundle/vendor
enabled=1
gpgcheck=1
gpgkey=file://$bundle/keys/RPM-GPG-KEY-kylin
[test-$name-application]
name=Exact locally built application
baseurl=file://$bundle/application
enabled=1
gpgcheck=0
EOF
done
dnf -y --installroot="$root" --releasever=V10 --setopt="reposdir=$repos" \
 --disablerepo='*' "${repoflags[@]}" --setopt=install_weak_deps=False \
 install "${packages[@]}" iproute passwd shadow-utils acl attr \
 | tee "$evidence/dnf-transaction.log"
if grep -Ei 'scriptlet.*failed|Error in .*scriptlet' "$evidence/dnf-transaction.log"; then exit 1; fi
rpm --root "$root" -qa --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' | sort >"$evidence/installed-packages.txt"
for name in "${names[@]}"; do
 case "$name" in
 samba422)
  original=$(cat /work/native-evidence/samba-rpm-path.txt)
  package=samba422-offline
  prefix=/opt/samba-4.22.11
  chroot "$root" "$prefix/sbin/smbd" -V | grep -Fx 'Version 4.22.11'
  chroot "$root" "$prefix/bin/testparm" -s /etc/samba-4.22.11/smb.conf
  python3 /work/samba-webmin/native/check-linkage.py "$root" "$evidence/ldd.txt"
  ;;
 webmin)
  original=$(cat /work/native-evidence/webmin-rpm-path.txt)
  package=webmin-offline
  chroot "$root" /usr/bin/perl -c /usr/libexec/webmin/miniserv.pl
  modules=(lib open FindBin Socket Data::Dumper File::Path File::Basename Digest::SHA Digest::MD5
   Time::Local Time::HiRes Time::Piece Net::SSLeay Encode::Detect Socket6 Sys::Syslog JSON::XS)
  for module in "${modules[@]}"; do
   chroot "$root" /usr/bin/perl -e 'my $m=shift; $m =~ s!::!/!g; require "$m.pm";' "$module"
  done
  chroot "$root" /usr/bin/env TZ=UTC WEBMIN_CONFIG=/etc/webmin WEBMIN_VAR=/var/webmin \
   /usr/bin/perl -I/usr/libexec/webmin -e '
    for my $m ("DateTime","DateTime::Locale","DateTime::TimeZone") {
     die "Fallback test requires optional modules absent\n" if eval "require $m; 1";
    }
    chdir "/usr/libexec/webmin" or die "chdir";
    require "./web-lib.pl"; &init_config();
    die "Date formatting fallback failed\n" unless &make_date(0,1,"yyyy-mm-dd") eq "1970-01-01";
    print "Optional DateTime absent: built-in date fallback passed\n";
   '
  grep -qx 'bind=127.0.0.1' "$root/etc/webmin/miniserv.conf"
  grep -qx 'ssl=0' "$root/etc/webmin/miniserv.conf"
  test ! -e "$root/etc/webmin/miniserv.pem"
  ;;
 esac
 expected=$(rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' "$original")
 test "$(rpm --root "$root" -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' "$package")" = "$expected"
done
echo 'PASS: empty-installroot offline userspace closure only; NOT native VM acceptance.'
