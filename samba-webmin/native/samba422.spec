%global debug_package %{nil}
%global sprefix /opt/samba-4.22.11
%global sconf /etc/samba-4.22.11
%global sstate /var/lib/samba-4.22.11
Name: samba422-offline
Version: 4.22.11
Release: 1.ky10
Summary: Isolated Samba file server for Kylin V10 SP3 2403 ARM64
License: GPLv3+
URL: https://www.samba.org/
Source0: samba-%{version}.tar.gz
Source1: samba422.service
Source2: smb.conf
ExclusiveArch: aarch64
BuildRequires: gcc, gcc-c++, make, binutils, python3-devel >= 3.6, perl, perl-Parse-Yapp
BuildRequires: pkgconfig, gnutls-devel >= 3.6.13, libacl-devel, libattr-devel, libcap-devel
BuildRequires: jansson-devel, pam-devel, popt-devel, zlib-devel, libarchive-devel, libicu-devel
BuildRequires: libuuid-devel, libblkid-devel, readline-devel, ncurses-devel, systemd-devel
BuildRequires: krb5-devel, openldap-devel, lmdb-devel, flex, bison, dbus-devel, libtirpc-devel
Requires: systemd
Requires: python3 >= 3.6
%description
Isolated versioned file server. Distribution Samba is not replaced.
No service is automatically enabled or started.
%prep
%setup -q -n samba-%{version}
%build
./configure \
 --prefix=%{sprefix} --sysconfdir=%{sconf} --localstatedir=%{sstate} \
 --with-privatelibdir=%{sprefix}/lib/private \
 --with-privatedir=%{sstate}/private --with-lockdir=%{sstate}/lock \
 --with-statedir=%{sstate}/state --with-cachedir=%{sstate}/cache \
 --with-piddir=/run/samba422 \
 --bundled-libraries=talloc,tdb,tevent,ldb --private-libraries=ALL \
 --without-ad-dc --without-cluster-support --without-smb1-server
make %{?_smp_mflags}
%install
rm -rf %{buildroot}
make install DESTDIR=%{buildroot}
# RuntimeDirectory is created by systemd, never shipped as persistent state.
rm -rf %{buildroot}/run
install -d -m 0755 %{buildroot}%{sconf} %{buildroot}/usr/lib/systemd/system
install -m 0644 %{SOURCE2} %{buildroot}%{sconf}/smb.conf
install -m 0644 %{SOURCE1} %{buildroot}/usr/lib/systemd/system/samba422.service
install -d -m 0700 %{buildroot}%{sstate}/private
for d in lock state cache; do install -d -m 0755 %{buildroot}%{sstate}/$d; done
%files
%license COPYING
%{sprefix}
%dir %{sconf}
%config(noreplace) %{sconf}/smb.conf
/usr/lib/systemd/system/samba422.service
%dir %{sstate}
%dir %attr(0700,root,root) %{sstate}/private
%dir %{sstate}/lock
%dir %{sstate}/state
%dir %{sstate}/cache
