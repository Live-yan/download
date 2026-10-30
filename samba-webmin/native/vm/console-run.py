#!/usr/bin/env python3
"""Private serial login driver. Raw serial exists only in RAM."""
import argparse, os, re, selectors, signal, stat, subprocess, sys, time
from pathlib import Path
class GateError(Exception): pass
def require(ok, reason):
    if not ok: raise GateError(reason)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--case", choices=("samba", "webmin", "combined"), required=True)
    ap.add_argument("--phase", choices=("1", "2"), required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--timeout", type=int, default=2100)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    raw = bytearray(); secret = b""; process = None
    stage = "prepare"; reason = "unexpected_exception"; passed = False
    def fail(label): raise GateError(label)
    def send(data):
        try:
            process.stdin.write(data); process.stdin.flush()
        except (BrokenPipeError, OSError): fail("serial_write_failed")
    try:
        p = Path(a.secret); st = p.lstat()
        require(stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o600
                and st.st_uid == os.geteuid(), "secret_metadata")
        secret = p.read_bytes().strip()
        require(re.fullmatch(b"Aa9![0-9a-f]{60}", secret) is not None, "secret_format")
        require(re.fullmatch(r"[a-zA-Z0-9-]+", a.run) is not None, "run_format")
        cmd = a.command
        if cmd and cmd[0] == "--": cmd = cmd[1:]
        require(bool(cmd), "missing_command")
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True, bufsize=0)
        sel = selectors.DefaultSelector(); sel.register(process.stdout, selectors.EVENT_READ)
        started = time.monotonic(); deadline = started + 600
        stage = "login_prompt"; offset = 0; eof = False
        while not eof:
            now = time.monotonic()
            require(now - started < a.timeout, "overall_timeout")
            if stage != "acceptance":
                require(now < deadline, "prompt_timeout")
            for key, _ in sel.select(1):
                block = os.read(key.fd, 65536)
                if not block:
                    eof = True; break
                raw.extend(block)
                require(len(raw) <= 32 * 1024 * 1024, "serial_output_limit")
            tail = bytes(raw[offset:])
            if stage == "login_prompt" and re.search(rb"(?:^|[\r\n])[^\r\n]*login:\s*$", tail):
                offset = len(raw); send(b"root\n"); stage = "password_prompt"; deadline = now + 120
            elif stage == "password_prompt" and re.search(rb"(?:^|[\r\n])Password:\s*$", tail, re.I):
                offset = len(raw); send(secret + b"\n"); stage = "pam_session"; deadline = now + 120
            elif stage == "pam_session":
                match = re.search(rb"(?:^|[\r\n])CI_ROOT_LOGIN_READY uid=(\d+) context=([^\s\r\n]+)[\r\n]", tail)
                if match:
                    require(match.group(1) == b"0", "login_not_root")
                    context = match.group(2).split(b":")
                    require(len(context) >= 4, "invalid_selinux_context")
                    require(context[2] not in (b"unconfined_service_t", b"init_t", b"kernel_t",
                                              b"rpm_t", b"groupadd_t", b"useradd_t"), "non_admin_context")
                    offset = len(raw)
                    send(b"exec env PYTHONUTF8=1 /usr/bin/python3 /usr/local/libexec/native-acceptance.py\n")
                    stage = "acceptance"
                elif re.search(rb"Login incorrect|Authentication failure", tail, re.I):
                    fail("pam_login_failed")
        remaining = max(1, int(a.timeout - (time.monotonic() - started)))
        try: rc = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired: fail("shutdown_timeout")
        require(stage == "acceptance", "login_ready_missing")
        require(rc == 0, "qemu_exit_nonzero")
        text = bytes(raw).replace(b"\r", b"")
        marker = ("NATIVE_PASS case=" + a.case + " phase=" + a.phase + " run=" + a.run).encode()
        require(marker in text.splitlines(), "pass_marker_missing")
        require(b"NATIVE_FAIL" not in text, "guest_failure_marker")
        require(b"Power down" in text or b"Powerdown" in text, "powerdown_missing")
        passed = True; reason = "ok"
    except GateError as exc:
        reason = str(exc)  # Only our fixed labels, never external exception messages.
    except Exception:
        reason = "unexpected_exception"
    finally:
        if process is not None:
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    process.wait()
            # Drain final bytes before writing the one sanitized log.
            try:
                rest = process.stdout.read(1024 * 1024)
                if rest: raw.extend(rest)
            except Exception: pass
        text = bytes(raw)
        text = re.sub(rb"\x1b\][^\x07]*(?:\x07|\x1b\\)", b"", text)
        text = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", text)
        if secret:
            # Full-buffer matching also handles a secret split across read chunks.
            pattern = rb"[\x00-\x20\x7f]*".join(bytes([ch]) for ch in secret)
            text = re.sub(pattern, b"[REDACTED]", text)
            text = text.replace(secret, b"[REDACTED]")
        try:
            log = Path(a.log)
            log.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(log), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(text)
                f.write(("\nCONSOLE_" + ("PASS" if passed else "FAIL") + " stage=" + stage
                         + " reason=" + reason + "\n").encode())
        except Exception:
            passed = False; reason = "sanitized_log_write_failed"
    # Publish only structured, already-redacted guest evidence to job logs.
    for line in text.decode("utf-8", errors="replace").splitlines():
        if "avc:  denied" in line or re.match(r"^(?:CI_ROOT_LOGIN_READY |LOGIN_CONTEXT[ =:]|SELINUX_DIAG[ =:]|BASELINE_UNIT[ =:]|NATIVE_(?:PASS|FAIL)[ =:])", line):
            print(line)
    print("CONSOLE_" + ("PASS" if passed else "FAIL") + " stage=" + stage + " reason=" + reason)
    return 0 if passed else 1
if __name__ == "__main__":
    sys.exit(main())
