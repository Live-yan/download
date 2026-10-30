#!/usr/bin/env bash
set -euo pipefail
umask 022
TOP=/work/native-webmin-rpmbuild
OUT=/work/native-evidence
mkdir -p "$TOP"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} "$OUT"
cp /work/sources/webmin-2.670.tar.gz "$TOP/SOURCES/"
echo "617af07a890bea18a83dca5c9d7168de1ad4d5f3076d8a1df3475f123748dc21  $TOP/SOURCES/webmin-2.670.tar.gz" | sha256sum -c -
cp /work/samba-webmin/native/{stage-webmin.py,webmin-offline.service} "$TOP/SOURCES/"
cp /work/samba-webmin/native/webmin-offline.spec "$TOP/SPECS/"
rpmbuild --define "_topdir $TOP" -ba "$TOP/SPECS/webmin-offline.spec" 2>&1 | tee "$OUT/webmin-rpmbuild.log"
mapfile -t results < <(find "$TOP/RPMS/noarch" -maxdepth 1 -name 'webmin-offline-2.670-*.noarch.rpm' -type f)
test "${#results[@]}" -eq 1
RPM="${results[0]}"
test "$(rpm -qp --qf '%{NAME} %{VERSION} %{ARCH}' "$RPM")" = 'webmin-offline 2.670 noarch'
printf '%s\n' "$RPM" > "$OUT/webmin-rpm-path.txt"
test -s "$RPM"
rpm -qpR "$RPM" > "$OUT/webmin-requires.txt"
rpm -qp --scripts "$RPM" > "$OUT/webmin-scripts.txt"
rpm -qpl "$RPM" > "$OUT/webmin-files.txt"
mkdir -p "$TOP/payload-check"
cd "$TOP/payload-check"
rpm2cpio "$RPM" | cpio -idm --quiet
test ! -e etc/webmin/miniserv.pem
grep -qx root:x:0 etc/webmin/miniserv.users
grep -qx bind=127.0.0.1 etc/webmin/miniserv.conf
grep -qx ssl=0 etc/webmin/miniserv.conf
grep -qx lang=zh etc/webmin/config
if grep -R -a -l -F "$TOP" etc usr; then echo 'Staging path leakage' >&2; exit 1; fi
echo 'Webmin RPM payload gate passed; runtime/dependency/VM acceptance still required.'
