#!/usr/bin/env bash
set -euo pipefail
command -v qemu-system-aarch64
docker build -t kylin-vm-probe samba-webmin/native/vm
mkdir -p vm-work
cp samba-webmin/native/vm/label-image.py vm-work/
cid=$(docker create kylin-vm-probe /bin/true)
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
docker export "$cid" > vm-work/rootfs.tar
docker rm "$cid"
trap - EXIT
docker run --rm --network none -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" -v "$PWD/vm-work:/work" --entrypoint /bin/bash kylin-vm-probe -euxo pipefail -c '
 mkdir /work/rootfs
 tar --numeric-owner -xpf /work/rootfs.tar -C /work/rootfs
 rm -f /work/rootfs/.dockerenv /work/rootfs/run/.containerenv
 mkdir -p /work/rootfs/dev /work/rootfs/proc /work/rootfs/sys /work/rootfs/run
 truncate -s 4G /work/root.ext4
 mkfs.ext4 -F -L KYLINROOT -d /work/rootfs /work/root.ext4
 python3 /work/label-image.py
 e2fsck -fn /work/root.ext4
 cp /boot/ci-initramfs.img /work/initramfs.img
 cp /boot/vmlinuz-$(cat /etc/ci-expected-kernel) /work/vmlinuz
 cp /etc/ci-rpm-manifest /work/rpm-manifest.txt
 chown "$HOST_UID:$HOST_GID" /work/root.ext4 /work/initramfs.img /work/vmlinuz /work/rpm-manifest.txt
'
python3 - <<'PY'
import gzip
from pathlib import Path
data=Path("vm-work/vmlinuz").read_bytes()
if data[:2]==b"\x1f\x8b": data=gzip.decompress(data)
if data[56:60]!=b"ARM\x64": raise SystemExit("Unrecognized arm64 Image format; do not substitute kernel")
Path("vm-work/Image").write_bytes(data)
PY
timeout --signal=TERM --kill-after=30s 15m qemu-system-aarch64 \
 -M virt,gic-version=3 -cpu max -accel tcg -m 4096 -smp 2 \
 -kernel vm-work/Image -initrd vm-work/initramfs.img \
 -append 'console=ttyAMA0 root=/dev/vda rw rootfstype=ext4 security=selinux selinux=1 enforcing=1' \
 -drive if=none,id=root,file=vm-work/root.ext4,format=raw \
 -device virtio-blk-pci,drive=root -nic none -nographic -monitor none -no-reboot \
 2>&1 | tee vm-work/serial.log
grep -q 'KYLIN_VM_BOOT_SELINUX_ENFORCING_PASS' vm-work/serial.log
! grep -q 'KYLIN_VM_PROBE_FAILED' vm-work/serial.log
