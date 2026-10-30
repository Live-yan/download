FROM cr.kylinos.cn/kylin/kylin-server-init@sha256:cd3739897bbf4d08348e9250b6fdfcc96dde1dbee04700e299a6bcd9617977fe
SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]
ARG KVER=4.19.90-89.11.v2401.ky10.aarch64
COPY kylin.repo /etc/ci-repos/kylin.repo
RUN test -s /etc/pki/rpm-gpg/RPM-GPG-KEY-kylin; \
    rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-kylin; \
    dnf -y --setopt=reposdir=/etc/ci-repos --disablerepo='*' \
      --enablerepo=ci-base,ci-updates --setopt=gpgcheck=1 install \
      kernel-core-$KVER kernel-modules-$KVER \
      systemd systemd-udev dracut e2fsprogs \
      selinux-policy-targeted policycoreutils libselinux \
      python3 tar findutils coreutils; \
    command -v matchpathcon; command -v getenforce; \
    command -v debugfs; command -v mkfs.ext4; \
    test -s /boot/vmlinuz-$KVER; test -s /boot/config-$KVER; \
    test -d /lib/modules/$KVER; \
    grep -q '^CONFIG_SECURITY_SELINUX=y$' /boot/config-$KVER; \
    printf 'SELINUX=enforcing\nSELINUXTYPE=targeted\n' > /etc/selinux/config; \
    printf '%s\n' "$KVER" > /etc/ci-expected-kernel; \
    printf '/dev/vda / ext4 defaults 0 1\n' > /etc/fstab; \
    truncate -s 0 /etc/machine-id
COPY probe.sh /usr/local/sbin/kylin-vm-probe
COPY probe.service /etc/systemd/system/kylin-vm-probe.service
RUN chmod 0755 /usr/local/sbin/kylin-vm-probe; \
    mkdir -p /etc/systemd/system/multi-user.target.wants; \
    ln -s ../kylin-vm-probe.service /etc/systemd/system/multi-user.target.wants/kylin-vm-probe.service; \
    ln -sf /usr/lib/systemd/system/multi-user.target /etc/systemd/system/default.target; \
    dracut --force --no-hostonly --add selinux /boot/ci-initramfs.img "$KVER"; \
    test -s /boot/ci-initramfs.img; \
    rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' | sort > /etc/ci-rpm-manifest; \
    dnf clean all
