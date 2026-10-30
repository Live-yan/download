#!/usr/bin/env bash
set -euo pipefail
TOP=/work/native-rpmbuild
OUT=/work/native-evidence
mkdir -p "$TOP"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} "$OUT"
cp /work/sources/samba-4.22.11.tar.gz "$TOP/SOURCES/"
cp /work/samba-webmin/native/{samba422.service,smb.conf} "$TOP/SOURCES/"
cp /work/samba-webmin/native/samba422.spec "$TOP/SPECS/"
trap 'find "$TOP/BUILD" -name config.log -exec cp {} "$OUT/samba-config.log" \; 2>/dev/null || true' EXIT
rpmbuild -ba --define "_topdir $TOP" --define "_smp_mflags -j2" "$TOP/SPECS/samba422.spec" 2>&1 | tee "$OUT/rpmbuild.log"
mapfile -t results < <(find "$TOP/RPMS/aarch64" -maxdepth 1 -name 'samba422-offline-4.22.11-*.aarch64.rpm' -type f)
test "${#results[@]}" -eq 1
RPM="${results[0]}"
test "$(rpm -qp --qf '%{NAME} %{VERSION} %{ARCH}' "$RPM")" = 'samba422-offline 4.22.11 aarch64'
printf '%s\n' "$RPM" > "$OUT/samba-rpm-path.txt"
test -s "$RPM"
rpm -qp --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' "$RPM"
rpm -qpR "$RPM" > "$OUT/samba-requires.txt"
rpm -qp --provides "$RPM" > "$OUT/samba-provides.txt"
rpm -qpl "$RPM" > "$OUT/samba-files.txt"
rpm -Uvh "$RPM"
for tool in sbin/smbd bin/smbclient bin/testparm bin/pdbedit bin/net bin/smbcontrol; do
 test -x "/opt/samba-4.22.11/$tool"
 ldd "/opt/samba-4.22.11/$tool" | tee -a "$OUT/samba-linkage.txt"
done
if grep -q 'not found' "$OUT/samba-linkage.txt"; then exit 1; fi
if grep -E 'lib(talloc|tdb|tevent|ldb).*=> /usr/lib' "$OUT/samba-linkage.txt"; then exit 1; fi
/opt/samba-4.22.11/sbin/smbd -V | grep -Fx 'Version 4.22.11'
/opt/samba-4.22.11/bin/testparm -s /etc/samba-4.22.11/smb.conf
echo 'RPM build/linkage only: NOT offline closure or VM acceptance.'
