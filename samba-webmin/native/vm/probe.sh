#!/usr/bin/bash
set -euo pipefail
trap 'echo KYLIN_VM_PROBE_FAILED' ERR
test "$(uname -m)" = aarch64
test "$(uname -r)" = "$(cat /etc/ci-expected-kernel)"
test "$(cat /proc/1/comm)" = systemd
test "$(getenforce)" = Enforcing
test "$(cat /sys/fs/selinux/enforce)" = 1
test -d /run/systemd/system
test ! -e /.dockerenv
test ! -e /run/.containerenv
uname -a
cat /etc/os-release
systemctl --version
getenforce
cat /proc/1/attr/current
cat /etc/ci-rpm-manifest
echo KYLIN_VM_BOOT_SELINUX_ENFORCING_PASS
sync
systemctl --no-block poweroff
