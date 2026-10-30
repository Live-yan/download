#!/usr/bin/env bash
set -euo pipefail
umask 077
case_name=$1
case "$case_name" in samba|webmin|combined) ;; *) exit 2;; esac
command -v qemu-system-aarch64
test -f samba-webmin/native/vm/native-acceptance.py
python3 -m py_compile samba-webmin/native/vm/console-run.py samba-webmin/native/vm/finalize-rootfs.py samba-webmin/native/vm/native-acceptance.py
docker build -t kylin-vm-probe samba-webmin/native/vm
docker build -t kylin-native-acceptance -f samba-webmin/native/vm/Dockerfile.native .
work="$PWD/vm-work/$case_name"
logs="$PWD/vm-evidence/$case_name"
test ! -e "$work"
mkdir -p "$work" "$logs"
cp samba-webmin/native/vm/label-image.py samba-webmin/native/vm/finalize-rootfs.py "$work/"
python3 - "$work/login-secret" <<'PY'
import os,secrets,sys
fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as stream:
 stream.write(secrets.token_hex(32)+"\n")
PY
cid=""
cleanup() {
 if [[ -n "$cid" ]]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi
 if [ -f "$work/finalize-evidence.txt" ]; then cp "$work/finalize-evidence.txt" "$logs/finalize-evidence.txt" || true; fi
 docker run --rm --network none -v "$work:/work" --entrypoint /bin/bash \
  kylin-native-acceptance -c 'rm -rf /work/rootfs /work/root.ext4 /work/rootfs.tar /work/labels /work/login-secret' >/dev/null 2>&1 || true
}
trap cleanup EXIT
cid=$(docker create kylin-native-acceptance /bin/true)
docker export "$cid" >"$work/rootfs.tar"
docker rm "$cid"
cid=""
docker run --rm --network none -e CASE_NAME="$case_name" \
 -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
 -v "$work:/work" -v "$PWD/native-bundles:/bundles:ro" \
 --entrypoint /bin/bash kylin-native-acceptance -euxo pipefail -c '
 mkdir /work/rootfs
 tar --numeric-owner -xpf /work/rootfs.tar -C /work/rootfs
 rm -f /work/rootfs/.dockerenv /work/rootfs/run/.containerenv
 mkdir -p /work/rootfs/{dev,proc,sys,run,opt/offline}
 printf "%s\n" "$CASE_NAME" >/work/rootfs/etc/ci-case
 case "$CASE_NAME" in samba) names=(samba422);; webmin) names=(webmin);; combined) names=(samba422 webmin);; esac
 for name in "${names[@]}"; do
  test -s "/bundles/$name/offline.repo"
  test -d "/bundles/$name/application"
  test -d "/bundles/$name/vendor"
  cp -a "/bundles/$name" "/work/rootfs/opt/offline/$name"
 done
 test ! -e /work/rootfs/var/lib/ci-native/state.json
 test ! -e /work/rootfs/opt/samba-4.22.11
 test ! -e /work/rootfs/usr/libexec/webmin
 python3 /work/finalize-rootfs.py
 chmod 0644 /work/finalize-evidence.txt
 truncate -s 8G /work/root.ext4
 mkfs.ext4 -F -L KYLINROOT -d /work/rootfs /work/root.ext4
 python3 /work/label-image.py
 e2fsck -fn /work/root.ext4
 cp /boot/ci-initramfs.img /work/initramfs.img
 cp "/boot/vmlinuz-$(cat /etc/ci-expected-kernel)" /work/vmlinuz
 cp /etc/ci-expected-kernel /work/expected-kernel.txt
 chown "$HOST_UID:$HOST_GID" /work/root.ext4 /work/initramfs.img /work/vmlinuz /work/expected-kernel.txt
'
python3 - "$work" <<'PY'
import gzip,pathlib,sys
p=pathlib.Path(sys.argv[1])
data=(p/"vmlinuz").read_bytes()
if data[:2]==b"\x1f\x8b": data=gzip.decompress(data)
if data[56:60]!=b"ARM\x64": raise SystemExit("Unexpected official ARM64 kernel format")
(p/"Image").write_bytes(data)
PY
run_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
printf 'case=%s\nrun=%s\nkernel=%s\n' "$case_name" "$run_id" "$(cat "$work/expected-kernel.txt")" >"$logs/metadata.txt"
for phase in 1 2; do
 python3 samba-webmin/native/vm/console-run.py \
  --secret "$work/login-secret" --log "$logs/phase-$phase.serial.log" \
  --case "$case_name" --phase "$phase" --run "$run_id" --timeout 2100 -- \
  qemu-system-aarch64 \
  -M virt,gic-version=3 -cpu max -accel tcg -m 4096 -smp 2 \
  -kernel "$work/Image" -initrd "$work/initramfs.img" \
  -append "console=ttyAMA0 root=/dev/vda rw rootfstype=ext4 security=selinux selinux=1 enforcing=1 ci.phase=$phase ci.run=$run_id" \
  -drive "if=none,id=root,file=$work/root.ext4,format=raw" -device virtio-blk-pci,drive=root \
  -object rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-pci,rng=rng0 \
  -nic none -nographic -monitor none -no-reboot

done
printf 'Two cold boots passed: case=%s run=%s\n' "$case_name" "$run_id"
