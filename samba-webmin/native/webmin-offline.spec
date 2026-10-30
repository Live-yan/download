%global debug_package %{nil}
Name: webmin-offline
Version: 2.670
Release: 1.kylin.offline
Summary: HTTP loopback Webmin for offline Kylin administration
License: BSD-3-Clause
URL: https://webmin.com/
Source0: webmin-2.670.tar.gz
Source1: stage-webmin.py
Source2: webmin-offline.service
BuildArch: noarch
# Upstream makerpm.pl deliberately uses explicit core dependencies.
AutoReq: 0
AutoProv: 0
BuildRequires: python3, perl, coreutils, findutils, grep, sed, tar, gzip
Requires: /bin/sh
Requires: /usr/bin/perl
Requires: perl(lib), perl(open), perl(FindBin), perl(Socket), perl(Data::Dumper)
Requires: perl(File::Path), perl(File::Basename), perl(Digest::SHA), perl(Digest::MD5)
Requires: perl(Time::Local), perl(Time::HiRes), perl(Time::Piece), perl(Net::SSLeay)
# Optional upstream date-localization enhancement; core has a tested fallback.
Recommends: perl(DateTime), perl(DateTime::Locale), perl(DateTime::TimeZone)
Requires: perl(Encode::Detect), perl(Socket6), perl(Sys::Syslog), perl(JSON::XS)
Requires: coreutils, findutils, grep, sed, procps-ng, shadow-utils, systemd
Requires: openssl, tar, gzip, unzip, shared-mime-info
Conflicts: webmin
%description
Webmin using the generic Linux 4.19 module backend on Kylin V10 SP3-2403.
HTTP binds only to loopback. Installation does not start or enable the service,
change any password, or generate TLS credentials. Samba is independently optional.
%prep
%setup -q -n webmin-%{version}
%build
%install
rm -rf "%{buildroot}"
install -d "%{buildroot}/usr/libexec/webmin"
cp -a . "%{buildroot}/usr/libexec/webmin/"
rm -f "%{buildroot}"/usr/libexec/webmin/mount/freebsd-mounts*
rm -f "%{buildroot}"/usr/libexec/webmin/mount/openbsd-mounts*
rm -f "%{buildroot}"/usr/libexec/webmin/mount/macos-mounts*
rm -f "%{buildroot}/usr/libexec/webmin/webmin-openrc-init"
rm -rf "%{buildroot}/usr/libexec/webmin/format" \
 "%{buildroot}/usr/libexec/webmin/bsdexports" "%{buildroot}/usr/libexec/webmin/hpuxexports" \
 "%{buildroot}/usr/libexec/webmin/sgiexports" "%{buildroot}/usr/libexec/webmin/zones" \
 "%{buildroot}/usr/libexec/webmin/rbac" "%{buildroot}/usr/libexec/webmin/bsdfdisk"
rm -rf "%{buildroot}"/usr/libexec/webmin/acl/Authen-SolarisRBAC-0.1*
python3 "%{SOURCE1}" "%{buildroot}"
install -D -m 0644 "%{SOURCE2}" "%{buildroot}/usr/lib/systemd/system/webmin-offline.service"
%check
grep -qx 'root:x:0' "%{buildroot}/etc/webmin/miniserv.users"
grep -qx 'bind=127.0.0.1' "%{buildroot}/etc/webmin/miniserv.conf"
grep -qx 'ssl=0' "%{buildroot}/etc/webmin/miniserv.conf"
grep -qx 'lang=zh' "%{buildroot}/etc/webmin/config"
test ! -e "%{buildroot}/etc/webmin/miniserv.pem"
%pre
if [ "$1" -eq 1 ] && { [ -e /etc/webmin/miniserv.conf ] || [ -e /usr/libexec/webmin/version ]; }; then
 echo "Existing Webmin found; resolve the existing installation without overwriting it." >&2
 exit 1
fi
exit 0
%files
%defattr(-,root,root)
/usr/libexec/webmin
%config(noreplace) /etc/webmin
%dir %attr(0700,root,root) /var/webmin
/usr/lib/systemd/system/webmin-offline.service
