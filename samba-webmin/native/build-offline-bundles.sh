#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
BASE=/work/native-bundles
EVIDENCE=/work/native-evidence/closure
KEY=/etc/pki/rpm-gpg/RPM-GPG-KEY-kylin
mkdir -p "$BASE" "$EVIDENCE"
test -s "$KEY"
rpm --import "$KEY"
make_bundle() {
 local name=$1 rpmfile=$2 rootid bundle work candidate arch
 bundle="$BASE/$name"
 test -s "$rpmfile"
 rootid=$(rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' "$rpmfile")
 test "$(basename "$rpmfile")" = "$rootid.rpm"
 test ! -e "$bundle"
 mkdir -p "$bundle"/{application,vendor,keys}
 cp "$KEY" "$bundle/keys/RPM-GPG-KEY-kylin"
 work=$(mktemp -d)
 mkdir -p "$work"/{built,download,repos}
 cp "$rpmfile" "$work/built/"
 createrepo_c "$work/built"
 cat >"$work/repos/closure.repo" <<EOF
[closure-base]
name=Kylin 2403 signed base
baseurl=https://update.cs2c.com.cn/NS/V10/V10SP3-2403/os/adv/lic/base/aarch64/
enabled=1
gpgcheck=1
gpgkey=file://$KEY
[closure-updates]
name=Kylin 2403 signed updates
baseurl=https://update.cs2c.com.cn/NS/V10/V10SP3-2403/os/adv/lic/updates/aarch64/
enabled=1
gpgcheck=1
gpgkey=file://$KEY
[closure-built]
name=Exact application built by this workflow only
baseurl=file://$work/built
enabled=1
gpgcheck=0
EOF
 dnf --setopt="reposdir=$work/repos" --disablerepo='*' \
  --enablerepo=closure-base,closure-updates,closure-built \
  --setopt=install_weak_deps=False download --resolve --alldeps \
  --destdir="$work/download" "$rootid" iproute passwd shadow-utils acl attr
 test -s "$work/download/$rootid.rpm"
 cmp "$rpmfile" "$work/download/$rootid.rpm"
 cp "$rpmfile" "$bundle/application/"
 : >"$EVIDENCE/$name-signatures.log"
 shopt -s nullglob
 local packages=("$work/download/"*.rpm)
 test "${#packages[@]}" -gt 1
 for candidate in "${packages[@]}"; do
  arch=$(rpm -qp --qf '%{ARCH}' "$candidate")
  case "$arch" in aarch64|noarch) ;; *) exit 1;; esac
  if [[ "$(basename "$candidate")" == "$rootid.rpm" ]]; then continue; fi
  rpmkeys --checksig --verbose "$candidate" >"$work/signature.txt" 2>&1
  cat "$work/signature.txt" >>"$EVIDENCE/$name-signatures.log"
  grep -Eq 'Signature.*: OK' "$work/signature.txt"
  if grep -Eq 'NOKEY|NOT OK|BAD|NOTTRUSTED' "$work/signature.txt"; then exit 1; fi
  cp "$candidate" "$bundle/vendor/"
 done
 test "$(find "$bundle/application" -maxdepth 1 -name '*.rpm' | wc -l)" -eq 1
 createrepo_c "$bundle/application"
 createrepo_c "$bundle/vendor"
 rpm -qpR "$rpmfile" >"$EVIDENCE/$name-root-requires.txt"
 find "$bundle" -name '*.rpm' -print0 | sort -z |
  xargs -0 rpm -qp --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' >"$EVIDENCE/$name-packages.txt"
 cat >"$bundle/offline.repo" <<EOF
[$name-vendor]
name=$name signed Kylin dependencies
baseurl=file:///opt/offline/$name/vendor
enabled=1
gpgcheck=1
gpgkey=file:///opt/offline/$name/keys/RPM-GPG-KEY-kylin
[$name-application]
name=$name locally built application
baseurl=file:///opt/offline/$name/application
enabled=1
gpgcheck=0
EOF
 cp "/work/samba-webmin/native/offline/README-$name.md" "$bundle/README.md"
 case "$name" in
  samba422) cp /work/samba-webmin/native/offline/samba422-manage.sh "$bundle/samba-manage.sh";;
  webmin) cp /work/samba-webmin/native/offline/webmin-manage.sh "$bundle/webmin-manage.sh";;
 esac
 chmod 0755 "$bundle/"*-manage.sh
 rm -rf "$work"
}
make_bundle samba422 "$(cat /work/native-evidence/samba-rpm-path.txt)"
make_bundle webmin "$(cat /work/native-evidence/webmin-rpm-path.txt)"
