#!/usr/bin/env python3
"""Finalize an ephemeral Kylin VM fixture; never part of a product bundle."""
import os, re, stat, subprocess, sys
from pathlib import Path
ROOT = Path("/work/rootfs").resolve()
SECRET = Path("/work/login-secret")
OUT = Path("/work/finalize-evidence.txt")
evidence = []
class GateError(Exception): pass
def require(ok, reason):
    if not ok: raise GateError(reason)
def rooted(name):
    # Interpret absolute symlinks relative to the image, never the host.
    pending = list(Path("/" + str(name).lstrip("/")).parts[1:])
    parts = []; links = 0
    while pending:
        x = pending.pop(0)
        if x in ("", "."): continue
        if x == "..":
            require(bool(parts), "path_escape")
            parts.pop(); continue
        p = ROOT.joinpath(*parts, x)
        if p.is_symlink():
            links += 1
            require(links <= 40, "symlink_loop")
            target = os.readlink(str(p))
            if target.startswith("/"): parts = []
            pending = target.split("/") + pending
        else: parts.append(x)
    p = ROOT.joinpath(*parts)
    require(os.path.commonpath([str(ROOT), str(p)]) == str(ROOT), "path_escape")
    return p
def read(name):
    return rooted(name).read_text(encoding="utf-8")
def command(argv, data=None):
    evidence.append("RUN " + " ".join(argv))
    p = subprocess.run(["chroot", str(ROOT)] + argv, input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    evidence.append("EXIT " + str(p.returncode))
    if p.returncode != 0 and Path(argv[0]).name == "chpasswd":
        message = (p.stdout + p.stderr).lower()
        for label, pattern in (
            ("password_quality_rejection", b"bad password"),
            ("password_classes", b"classes"),
            ("password_complexity", b"complex"),
            ("password_too_short", b"short"),
            ("password_too_long", b"long"),
            ("pam_token_error", b"authentication token"),
            ("pam_module_load", b"module"),
            ("permission_denied", b"permission denied"),
            ("password_lock", b"lock"),
            ("missing_file", b"no such file"),
            ("system_error", b"system error"),
        ):
            if pattern in message: evidence.append("CHPASSWD_DIAG " + label)
    require(p.returncode == 0, "initialization_command_failed")
def main():
    require(os.geteuid() == 0, "host_not_root")
    spec = {
        "systemd-sysusers.service": ("systemd-sysusers", []),
        "ldconfig.service": ("ldconfig", ["-X"]),
        "systemd-hwdb-update.service": ("systemd-hwdb", ["update"]),
        "systemd-journal-catalog-update.service": ("journalctl", ["--update-catalog"]),
        "systemd-update-done.service": ("systemd-update-done", []),
    }
    found = {}; problems = []; seen = set()
    for directory in ("/usr/lib/systemd/system", "/lib/systemd/system",
                      "/usr/local/lib/systemd/system", "/run/systemd/system",
                      "/etc/systemd/system"):
        base = rooted(directory)
        evidence.append("UNIT_DIRECTORY " + directory + " -> " + str(base.relative_to(ROOT)))
        if not base.exists(): continue
        for dp, ds, fs in os.walk(str(base), followlinks=False):
            ds[:] = [d for d in ds if not Path(dp, d).is_symlink()]
            for fn in sorted(fs):
                if not fn.endswith((".service", ".conf")): continue
                path = Path(dp, fn)
                if path.is_symlink(): continue
                if path in seen: continue
                seen.add(path)
                text = path.read_text(encoding="utf-8")
                conditions = re.findall(r"(?m)^\s*ConditionNeedsUpdate\s*=(.*)$", text)
                if not conditions: continue
                starts = re.findall(r"(?m)^\s*ExecStart\s*=(.*)$", text)
                evidence.append("HOOK " + str(path.relative_to(ROOT)))
                evidence.extend("ConditionNeedsUpdate=" + x for x in conditions)
                evidence.extend("ExecStart=" + x for x in starts)
                if any(x.strip().lstrip("|") not in ("/etc", "/var") for x in conditions):
                    problems.append("unexpected_hook_condition")
                if fn not in spec or fn.endswith(".conf"):
                    problems.append("unknown_update_hook"); continue
                if len(starts) != 1:
                    problems.append("unexpected_exec_count"); continue
                argv = starts[0].split()
                expected, args = spec[fn]
                if not argv or not argv[0].startswith("/") or Path(argv[0]).name != expected or argv[1:] != args:
                    problems.append("unexpected_hook_command"); continue
                if fn in found and found[fn] != argv:
                    problems.append("conflicting_hook"); continue
                found[fn] = argv
    # Snapshot actual PAM include chain before making assumptions about it.
    pam = {}; queue = ["login", "chpasswd"]
    while queue:
        name = queue.pop(0)
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", name) is not None, "pam_include_name")
        if name in pam: continue
        require(len(pam) < 32, "pam_include_limit")
        if name == "chpasswd" and not rooted("/etc/pam.d/chpasswd").exists():
            evidence.append("PAM_SERVICE chpasswd has no dedicated file")
            pam[name] = ""
            if rooted("/etc/pam.d/other").exists(): queue.append("other")
            continue
        content = read("/etc/pam.d/" + name)
        pam[name] = content
        evidence.append("PAM_FILE /etc/pam.d/" + name)
        evidence.extend(content.splitlines())
        for line in content.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line: continue
            if line.startswith("@include "):
                queue.append(line.split()[1]); continue
            match = re.match(r"^-?(?:auth|account|password|session)\s+(?:include|substack)\s+(\S+)", line)
            if match: queue.append(match.group(1))
    secure = rooted("/etc/securetty")
    evidence.append("SECURETTY_PRESENT " + str(secure.exists()))
    entries = []
    if secure.exists():
        content = secure.read_text(encoding="utf-8")
        evidence.append("SECURETTY_CONTENT")
        evidence.extend(content.splitlines())
        entries = [x.split("#", 1)[0].strip() for x in content.splitlines()]
    evidence.append("SECURETTY_EXPLICIT_TTYAMA0 " + str("ttyAMA0" in entries))
    active_pam = "\n".join(line.split("#", 1)[0] for text in pam.values() for line in text.splitlines())
    require(not problems, problems[0] if problems else "hook_validation")
    require(set(found) == set(spec), "missing_expected_hook")
    # Do not silently ignore local overrides/drop-ins affecting vendor hooks.
    for unit in spec:
        for d in ("/usr/lib/systemd/system", "/lib/systemd/system", "/usr/local/lib/systemd/system",
                  "/etc/systemd/system", "/run/systemd/system"):
            require(not rooted(d + "/" + unit + ".d").exists(), "hook_dropin_present")
        for d in ("/etc/systemd/system", "/run/systemd/system", "/usr/local/lib/systemd/system"):
            require(not os.path.lexists(str(ROOT / d.lstrip("/") / unit)), "hook_override_present")
    require(re.search(r"(?m)^-?session\s+.*pam_selinux\.so\s+.*\bopen\b", active_pam) is not None, "pam_selinux_open_missing")
    require(re.search(r"(?m)^-?session\s+.*pam_selinux\.so\s+.*\bclose\b", active_pam) is not None, "pam_selinux_close_missing")
    if re.search(r"\bpam_securetty\.so\b", active_pam):
        require("ttyAMA0" in entries, "securetty_ttyama0_not_explicit")
    qualities = [rooted("/etc/security/pwquality.conf")]
    quality_dir = rooted("/etc/security/pwquality.conf.d")
    if quality_dir.is_dir():
        qualities += sorted(quality_dir.glob("*.conf"))
    for quality in qualities:
        if not quality.is_file() or quality.is_symlink(): continue
        allowed_options = {"minlen","minclass","maxrepeat","maxclassrepeat","dcredit","ucredit","lcredit","ocredit","difok","enforce_for_root"}
        for row in quality.read_text().splitlines():
            clean = row.split("#",1)[0].strip()
            key = clean.split("=",1)[0].strip()
            if key in allowed_options: evidence.append("PWQUALITY " + str(quality.relative_to(ROOT)) + " " + clean)
    dev = rooted("/dev")
    dev.mkdir(exist_ok=True)
    for name, minor in (("null", 3), ("zero", 5), ("random", 8), ("urandom", 9)):
        p = dev / name
        if os.path.lexists(str(p)):
            st = p.lstat()
            require(stat.S_ISCHR(st.st_mode) and os.major(st.st_rdev) == 1 and os.minor(st.st_rdev) == minor,
                    "device_metadata")
        else:
            try: os.mknod(str(p), stat.S_IFCHR | 0o666, os.makedev(1, minor))
            except PermissionError: raise GateError("device_creation_denied")
        os.chmod(str(p), 0o666)
        evidence.append("DEVICE " + name + " verified")
    for unit in ("systemd-sysusers.service", "ldconfig.service", "systemd-hwdb-update.service",
                 "systemd-journal-catalog-update.service"):
        command(found[unit])
    st = SECRET.lstat()
    require(stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o600 and st.st_uid == int(os.environ["HOST_UID"]),
            "secret_file_metadata")
    secret = SECRET.read_bytes().strip()
    require(re.fullmatch(b"Aa9![0-9a-f]{60}", secret) is not None, "secret_format")
    # Pass only on stdin; never print captured chpasswd output.
    chpasswd = next((p for p in ("/usr/sbin/chpasswd", "/sbin/chpasswd") if rooted(p).is_file()), None)
    require(chpasswd is not None, "chpasswd_missing")
    command([chpasswd], b"root:" + secret + b"\n")
    fixture = ROOT / "etc/ci-root-password"
    require(not fixture.is_symlink(), "fixture_symlink")
    fd = os.open(str(fixture), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        os.fchmod(f.fileno(), 0o600); os.fchown(f.fileno(), 0, 0)
        f.write(secret + b"\n")
    # Never log passwd/shadow contents.
    roots = [x.split(":") for x in read("/etc/passwd").splitlines() if x.startswith("root:")]
    require(len(roots) == 1 and roots[0][2] == "0" and roots[0][5] == "/root"
            and roots[0][6] in ("/bin/bash", "/usr/bin/bash"), "root_login_shell")
    profile = rooted("/root/.bash_profile")
    with profile.open("a", encoding="utf-8") as f:
        f.write("\nprintf 'CI_ROOT_LOGIN_READY uid=%s context=%s\\n' \"$(id -u)\" \"$(id -Z)\"\n")
    os.chmod(str(profile), 0o600); os.chown(str(profile), 0, 0)
    # Only remove our obsolete test fixture, never vendor units.
    test = ROOT / "etc/systemd/system/multi-user.target.wants/native-acceptance.service"
    if test.is_symlink(): test.unlink()
    else: require(not test.exists(), "unexpected_test_unit_entry")
    command(found["systemd-update-done.service"])
    usr_time = rooted("/usr").stat().st_mtime_ns
    for name in ("/etc/.updated", "/var/.updated"):
        stamp = rooted(name)
        require(stamp.stat().st_mtime_ns == usr_time, "updated_timestamp_mismatch")
        require("TIMESTAMP_NSEC=" + str(usr_time) in stamp.read_text(), "updated_content_mismatch")
        evidence.append("STAMP " + name + " matches_usr_ns=" + str(usr_time))
    evidence.append("FINALIZE_PASS")
if __name__ == "__main__":
    code = 0
    try: main()
    except GateError as exc:
        evidence.append("FINALIZE_FAIL reason=" + str(exc)); code = 1
    except Exception:
        evidence.append("FINALIZE_FAIL reason=unexpected_exception"); code = 1
    finally:
        OUT.write_text("\n".join(evidence) + "\n", encoding="utf-8")
        os.chmod(str(OUT), 0o644)
        print(OUT.read_text(), end="")
    sys.exit(code)
