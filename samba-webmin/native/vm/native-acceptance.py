#!/usr/bin/python3
"""Disposable VM acceptance only. Never distribute this file or the VM disk."""
import configparser
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.parse

STAGE = "bootstrap"
CASE = "unknown"
PASSWORD = None
PRIVATE = Path("/var/lib/ci-native")
STATE = PRIVATE / "state.json"
CONF = "/etc/samba-4.22.11/smb.conf"
SHARE = Path("/srv/ci-samba")
PREFIX = "/opt/samba-4.22.11"
SAMBA = False
WEBMIN = False
BUNDLES = []
UNITS = []

os.umask(0o077)
os.environ["PATH"] = PREFIX + "/bin:" + PREFIX + "/sbin:/usr/sbin:/usr/bin:/sbin:/bin"
os.environ["LC_ALL"] = "C"


def mark(label):
    global STAGE
    STAGE = label


def check(condition, label):
    mark(label)
    if not condition:
        raise RuntimeError(label)


def run(label, argv, data=None, good=True, timeout=180):
    mark(label)
    result = subprocess.run(
        argv, input=data, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout
    )
    # Do not expose command arguments, output, passwords or HTTP bodies.
    if good and result.returncode:
        raise RuntimeError(label)
    return result


def text(label, argv):
    return run(label, argv).stdout.strip()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def root_password_field():
    mark("read-root-shadow-field")
    rows = [
        line.split(":")
        for line in Path("/etc/shadow").read_text().splitlines()
        if line.startswith("root:")
    ]
    check(len(rows) == 1 and len(rows[0]) >= 2, "root-shadow-record")
    return rows[0][1]


def sb(command, *args):
    return [PREFIX + "/bin/" + command, *args]


def active(unit):
    return run("service-active-" + unit,
               ["systemctl", "is-active", "--quiet", unit],
               good=False).returncode == 0


def wait_active(unit):
    for unused in range(90):
        if active(unit):
            return
        time.sleep(1)
    check(False, "service-start-timeout-" + unit)


def authfile(account="fileshare", wrong=False):
    path = PRIVATE / ("auth-" + account + ("-wrong" if wrong else ""))
    path.write_text(
        "username = " + account + "\npassword = " +
        PASSWORD + ("-wrong" if wrong else "") + "\n"
    )
    path.chmod(0o600)
    return str(path)


def smb(label, commands, account="fileshare", wrong=False, anonymous=False,
        good=True):
    args = sb("smbclient", "//127.0.0.1/share", "-s", CONF, "-m", "SMB3")
    args += ["-N"] if anonymous else ["-A", authfile(account, wrong)]
    args += ["-c", commands]
    return run(label, args, good=good)


def account_sid(account):
    value = text("account-sid-" + account,
                 sb("pdbedit", "-s", CONF, "-L", "-v", "-u", account))
    match = re.search(r"(?m)^User SID:\s*(S-[0-9-]+)\s*$", value)
    check(match is not None, "account-sid-parsed-" + account)
    return match.group(1)


def ntacl(extra=None):
    args = sb("smbcacls", "//127.0.0.1/share", "ntacl.txt",
              "-s", CONF, "-m", "SMB3", "-A", authfile(), "--numeric")
    if extra:
        args += extra
    return text("remote-nt-acl", args)


def request(method, path, data=None, cookie=None):
    mark("webmin-http-request")
    connection = http.client.HTTPConnection("127.0.0.1", 10000, timeout=30)
    headers = {"Host": "localhost", "Referer": "https://localhost/"}
    if cookie:
        headers["Cookie"] = cookie
    if data is not None:
        data = urllib.parse.urlencode(data)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        connection.request(method, path, data, headers)
        response = connection.getresponse()
        return (
            response.status, response.getheaders(),
            response.read().decode("utf-8", "replace")
        )
    finally:
        connection.close()


def login(password):
    status, headers, body = request(
        "POST", "/session_login.cgi",
        {"user": "root", "pass": password, "page": "/"}, "testing=1"
    )
    result = []
    for key, value in headers:
        if key.lower() == "set-cookie":
            match = re.search(r"(?:^|;\s*)sid=([^; ]+)", value)
            if match and match.group(1) not in ("0", "deleted", ""):
                result.append(match.group(1))
    return result


def webmin_test(mutate=False):
    for unused in range(90):
        try:
            request("GET", "/session_login.cgi")
            break
        except (OSError, http.client.HTTPException):
            time.sleep(1)
    else:
        check(False, "webmin-readiness-timeout")

    # Confirm the endpoint exists in this installed package.
    check(Path("/usr/libexec/webmin/webmin/index.cgi").is_file(),
          "webmin-config-module-installed")
    status, headers, body = request("GET", "/webmin/index.cgi")
    check(not (status == 200 and "edit_access.cgi" in body),
          "webmin-protected-module-rejects-anonymous")

    check(not login(PASSWORD + "-wrong"), "webmin-rejects-wrong-password")
    sessions = login(PASSWORD)
    check(bool(sessions), "webmin-authenticates-native-root")
    cookie = "sid=" + sessions[-1]

    status, headers, body = request("GET", "/webmin/index.cgi", cookie=cookie)
    check(
        status == 200 and "edit_access.cgi" in body and
        not re.search(r'name=["\x27]?pass(?:["\x27 >])', body),
        "webmin-authenticated-config-module"
    )
    check(Path("/usr/libexec/webmin/version").read_text().strip() == "2.670",
          "webmin-exact-version")
    check("lang=zh" in Path("/etc/webmin/config").read_text().splitlines(),
          "webmin-chinese-default")
    config = Path("/etc/webmin/miniserv.conf").read_text().splitlines()
    check("bind=127.0.0.1" in config and "ssl=0" in config,
          "webmin-native-loopback-contract")
    check(not Path("/etc/webmin/miniserv.pem").exists(),
          "webmin-does-not-create-tls-credentials")

    endpoints = []
    for line in text("webmin-listeners", ["ss", "-H", "-ltn"]).splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[3].endswith(":10000"):
            endpoints.append(fields[3])
    check(endpoints == ["127.0.0.1:10000"], "webmin-listens-only-on-loopback")

    if not SAMBA:
        return

    status, headers, body = request("GET", "/samba/", cookie=cookie)
    check(
        status == 200 and
        not re.search(r'name=["\x27]?pass(?:["\x27 >])', body),
        "webmin-authenticated-samba-module"
    )
    if mutate:
        status, headers, body = request(
            "POST", "/samba/save_fshare.cgi", {
                "old_name": "share", "share": "share", "homes": "0",
                "path": str(SHARE), "available": "yes", "browseable": "yes",
                "comment": "CI-Webmin-marker"
            }, cookie
        )
        check(status in (200, 302, 303), "webmin-share-save-response")
        status, headers, body = request(
            "POST", "/samba/make_epass.cgi", {
                "who": "0", "include_list": "persistuser", "add": "1",
                "newmode": "2", "newpass": PASSWORD
            }, cookie
        )
        check(status in (200, 302, 303), "webmin-account-create-response")
        status, headers, body = request("GET", "/samba/restart.cgi", cookie=cookie)
        check(status in (200, 302, 303), "webmin-apply-response")

    comment = text("webmin-share-real-result", sb(
        "testparm", "-s", "--section-name=share",
        "--parameter-name=comment", CONF
    ))
    check(comment == "CI-Webmin-marker", "webmin-share-real-config")
    account = text("webmin-account-real-result",
                   sb("pdbedit", "-s", CONF, "-L", "-u", "persistuser"))
    check(account.startswith("persistuser:45679:"), "webmin-account-real-passdb")


def install_bundle(name):
    base = Path("/opt/offline") / name
    rpms = list((base / "application").glob("*.rpm"))
    check(len(rpms) == 1, "exactly-one-application-rpm-" + name)
    parser = configparser.ConfigParser()
    check(parser.read(str(base / "offline.repo")), "offline-repo-present-" + name)
    check(set(parser.sections()) == {name + "-vendor", name + "-application"},
          "offline-repo-ids-" + name)
    for suffix, gpg in [("vendor", "1"), ("application", "0")]:
        section = parser[name + "-" + suffix]
        check(section["baseurl"] == "file://" + str(base / suffix),
              "offline-file-repo-" + name + "-" + suffix)
        check(section["gpgcheck"] == gpg, "offline-gpgcheck-" + name + "-" + suffix)
    check(
        file_sha(base / "keys/RPM-GPG-KEY-kylin") ==
        file_sha("/etc/pki/rpm-gpg/RPM-GPG-KEY-kylin"),
        "official-vendor-key-identity"
    )

    fmt = "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}"
    identity = text("candidate-nevra", ["rpm", "-qp", "--qf", fmt, str(rpms[0])])
    package = text("candidate-name",
                   ["rpm", "-qp", "--qf", "%{NAME}", str(rpms[0])])
    check(package == ("samba422-offline" if name == "samba422" else "webmin-offline"),
          "expected-application-name")

    root_before = root_password_field()
    transaction = run("offline-dnf-" + name, [
        "dnf", "-y", "--setopt=reposdir=" + str(base),
        "--disablerepo=*",
        "--enablerepo=" + name + "-vendor," + name + "-application",
        "--setopt=install_weak_deps=False", "install",
        identity, "iproute", "passwd", "shadow-utils", "acl", "attr"
    ], timeout=1200)

    # RPM scriptlet failures can coexist with a successful DNF process exit.
    failure = re.search(
        r"(?:scriptlet[^\n]*(?:fail|error|non.?zero)|"
        r"(?:fail|error)[^\n]*scriptlet|"
        r"%(?:pre|post|preun|postun|pretrans|posttrans|trigger)\b[^\n]*failed)",
        transaction.stdout, re.IGNORECASE
    )
    check(failure is None, "no-rpm-scriptlet-failure-" + name)
    check(root_password_field() == root_before, "installer-preserves-root-password-" + name)
    check(text("installed-nevra", ["rpm", "-q", "--qf", fmt, package]) == identity,
          "installed-exact-nevra-" + name)
    return {"nevra": identity, "sha256": file_sha(rpms[0])}


def setup_samba():
    run("fixture-group", ["groupadd", "-g", "45677", "ci_smb"])
    for user, uid in [("fileshare", "45678"), ("persistuser", "45679")]:
        run("fixture-user-" + user, [
            "useradd", "-u", uid, "-g", "ci_smb", "-M",
            "-s", "/sbin/nologin", user
        ])
    SHARE.mkdir(parents=True)
    run("fixture-share-owner", ["chown", "root:ci_smb", str(SHARE)])
    SHARE.chmod(0o2770)
    with open(CONF, "a") as stream:
        stream.write("""
[share]
    path = /srv/ci-samba
    read only = no
    browseable = yes
    guest ok = no
    valid users = fileshare persistuser
    create mask = 0660
    directory mask = 0770
    vfs objects = acl_xattr
    map acl inherit = yes
    acl_xattr:ignore system acls = no
""")

    # In combined mode, Webmin CGI must create persistuser's Samba account.
    for user in (["fileshare"] if WEBMIN else ["fileshare", "persistuser"]):
        run("fixture-smb-account-" + user,
            sb("smbpasswd", "-c", CONF, "-s", "-a", user),
            PASSWORD + "\n" + PASSWORD + "\n")

    for name in ["owner-marker", "denied-marker"]:
        path = SHARE / name
        path.write_bytes((name + "\n").encode())
        run("fixture-marker-owner", ["chown", "45679:ci_smb", str(path)])
        path.chmod(0o600)

    marker = SHARE / "owner-marker"
    run("fixture-xattr", ["setfattr", "-n", "user.offline-test",
                         "-v", "persistent", str(marker)])
    # Group has NO permission: fileshare must use the named-user ACL.
    run("fixture-posix-acl", [
        "setfacl", "-m", "u:fileshare:r--,g::---,m::r--", str(marker)
    ])
    # Only disposable share data receives a standard Samba data label.
    run("fixture-data-label", ["chcon", "-R", "-t", "samba_share_t", str(SHARE)])


def samba_test(create_ntacl=False):
    check(text("samba-version", [PREFIX + "/sbin/smbd", "-V"]) ==
          "Version 4.22.11", "samba-exact-version")
    check(text("persistent-unix-uid", ["id", "-u", "persistuser"]) ==
          "45679", "unix-uid-persistence")
    check(text("persistent-owner-mode",
               ["stat", "-c", "%u:%a", str(SHARE / "owner-marker")]) ==
          "45679:640", "owner-mode-persistence")
    acl = text("persistent-posix-acl",
               ["getfacl", "-cp", str(SHARE / "owner-marker")])
    check("user:fileshare:r--" in acl and "group::---" in acl,
          "named-user-acl-not-group-permission")
    check(text("persistent-user-xattr", [
        "getfattr", "--only-values", "-n", "user.offline-test",
        str(SHARE / "owner-marker")
    ]) == "persistent", "user-xattr-persistence")
    vfs = text("configured-vfs", sb(
        "testparm", "-s", "--section-name=share", "--parameter-name=vfs objects", CONF
    ))
    check("acl_xattr" in vfs.split(), "acl-xattr-still-enabled")

    source = PRIVATE / "input"
    output = PRIVATE / "output"
    source.write_bytes("离线中文内容\n".encode("utf-8") + b"\x00\xff\x01")
    if output.exists():
        output.unlink()
    smb("chinese-smb-io",
        "put %s 中文文件.txt; get 中文文件.txt %s; del 中文文件.txt" % (source, output))
    check(output.exists() and output.read_bytes() == source.read_bytes(),
          "chinese-binary-roundtrip")
    check(not (SHARE / "中文文件.txt").exists(), "smb-delete-effective")
    smb("second-user-authentication", "ls", account="persistuser")

    check(smb("anonymous-smb-attempt", "ls", anonymous=True, good=False).returncode != 0,
          "anonymous-smb-rejected")
    check(smb("incorrect-smb-password", "ls", wrong=True, good=False).returncode != 0,
          "incorrect-smb-password-rejected")
    smb("posix-acl-network-read",
        "get owner-marker " + str(PRIVATE / "owner-read"))
    check((PRIVATE / "owner-read").read_bytes() ==
          (SHARE / "owner-marker").read_bytes(), "named-acl-real-network-read")
    denied = smb("no-acl-network-read",
                 "get denied-marker " + str(PRIVATE / "denied-read"), good=False)
    check(denied.returncode != 0 and "NT_STATUS_ACCESS_DENIED" in denied.stdout,
          "no-acl-real-network-denial")

    sid = account_sid("persistuser")
    if create_ntacl:
        smb("ntacl-fixture-upload", "put " + str(source) + " ntacl.txt")
        ntacl(["--add", "ACL:" + sid + ":ALLOWED/0x0/READ"])
    descriptor = ntacl()
    check("ACL:" + sid + ":" in descriptor, "remote-nt-acl-user-ace")
    mark("nt-acl-xattr-read")
    check(bool(os.getxattr(str(SHARE / "ntacl.txt"), "security.NTACL")),
          "native-security-ntacl-written")


def snapshot():
    result = {}
    if SAMBA:
        result.update({
            "server_sid": text("persistent-server-sid",
                               sb("net", "-s", CONF, "getlocalsid")),
            "fileshare_sid": account_sid("fileshare"),
            "persistuser_sid": account_sid("persistuser"),
            "smb_conf": file_sha(CONF),
            "owner_marker": file_sha(SHARE / "owner-marker"),
            "ntacl_xattr": sha(os.getxattr(str(SHARE / "ntacl.txt"), "security.NTACL"))
        })
    if WEBMIN:
        for path in [
            "/etc/webmin/config", "/etc/webmin/miniserv.conf",
            "/etc/webmin/miniserv.users", "/etc/webmin/samba/config"
        ]:
            result[path] = file_sha(path)
        result["root_password_field_sha256"] = sha(root_password_field().encode())
    return result


def lifecycle():
    pairs = ([("samba422", "samba422")] if SAMBA else [])
    pairs += ([("webmin", "webmin-offline")] if WEBMIN else [])
    for bundle, unit in pairs:
        helper = Path("/opt/offline") / bundle / (
            "samba-manage.sh" if bundle == "samba422" else "webmin-manage.sh"
        )
        check(helper.is_file(), "management-helper-present-" + bundle)
        check(run("management-invalid-" + bundle,
                  ["sh", str(helper), "invalid"], good=False).returncode != 0,
              "management-invalid-rejected-" + bundle)
        for action in ["stop", "start", "restart"]:
            run("management-" + unit + "-" + action, ["sh", str(helper), action])
            if action == "stop":
                for unused in range(30):
                    if not active(unit):
                        break
                    time.sleep(1)
                check(not active(unit), "management-stop-effective-" + unit)
            else:
                wait_active(unit)


def write_state(value):
    temporary = PRIVATE / "state.new"
    temporary.write_text(json.dumps(value))
    temporary.chmod(0o600)
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    temporary.replace(STATE)
    directory = os.open(str(PRIVATE), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main():
    global CASE, SAMBA, WEBMIN, BUNDLES, UNITS, PASSWORD
    check(sys.getfilesystemencoding().lower().replace("_", "-") == "utf-8",
          "python-utf8-filesystem-mode")
    CASE = Path("/etc/ci-case").read_text().strip()
    check(CASE in ("samba", "webmin", "combined"), "known-case")
    SAMBA = CASE in ("samba", "combined")
    WEBMIN = CASE in ("webmin", "combined")
    BUNDLES = (["samba422"] if SAMBA else []) + (["webmin"] if WEBMIN else [])
    UNITS = (["samba422"] if SAMBA else []) + (["webmin-offline"] if WEBMIN else [])

    cmdline = dict(
        word.split("=", 1) for word in Path("/proc/cmdline").read_text().split()
        if "=" in word
    )
    phase = int(cmdline["ci.phase"])
    nonce = cmdline["ci.run"]
    check(phase in (1, 2) and bool(re.fullmatch(r"[A-Za-z0-9-]+", nonce)),
          "phase-and-run-id")
    check(text("guest-architecture", ["uname", "-m"]) == "aarch64", "aarch64-guest")
    check(text("guest-kernel", ["uname", "-r"]) ==
          Path("/etc/ci-expected-kernel").read_text().strip(), "official-guest-kernel")
    check(Path("/proc/1/comm").read_text().strip() == "systemd", "systemd-pid-one")
    check(text("selinux-mode", ["getenforce"]) == "Enforcing", "selinux-enforcing")
    check(Path("/sys/fs/selinux/enforce").read_text().strip() == "1",
          "kernel-selinux-enforcing")
    check(sorted(p.name for p in Path("/sys/class/net").iterdir()) == ["lo"],
          "no-guest-network-interface")
    check(not Path("/.dockerenv").exists(), "not-container-execution")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()

    if phase == 1:
        check(not PRIVATE.exists(), "pristine-private-test-state")
        check(set(p.name for p in Path("/opt/offline").iterdir()) == set(BUNDLES),
              "case-specific-bundles-only")
        PRIVATE.mkdir(mode=0o700)
        # Blocking secrets API: never use weak/fixed entropy as a fallback.
        PASSWORD = secrets.token_hex(32)
        for package in ["samba422-offline", "webmin-offline"]:
            check(run("application-absent", ["rpm", "-q", package],
                      good=False).returncode != 0, "pristine-no-application")
        original_root_field = root_password_field()
        candidates = {}
        for bundle in BUNDLES:
            candidates[bundle] = install_bundle(bundle)
        check(root_password_field() == original_root_field,
              "all-installation-preserves-root-password")

        run("load-installed-units", ["systemctl", "daemon-reload"])
        for unit in UNITS:
            check(not active(unit), "rpm-did-not-start-" + unit)
            check(run("rpm-enable-state", ["systemctl", "is-enabled", "--quiet", unit],
                      good=False).returncode != 0, "rpm-did-not-enable-" + unit)

        # This is a private disposable VM test fixture, never product initialization.
        if WEBMIN:
            run("fixture-root-password", ["chpasswd"], "root:" + PASSWORD + "\n")
        if SAMBA:
            setup_samba()
        for unit in UNITS:
            run("fixture-enable-start", ["systemctl", "enable", "--now", unit])
            wait_active(unit)
    else:
        check(STATE.is_file(), "previous-successful-phase-required")
        saved = json.loads(STATE.read_text())
        check(saved["case"] == CASE and saved["run"] == nonce, "same-case-and-run")
        check(saved["boot_id"] != boot_id, "new-kernel-boot-id")
        PASSWORD = saved["password"]
        candidates = saved["candidates"]
        # IMPORTANT: no install, start, enable, restart or account initialization.
        for unit in UNITS:
            check(run("persisted-enable-state",
                      ["systemctl", "is-enabled", "--quiet", unit],
                      good=False).returncode == 0, "service-enabled-after-cold-boot")
            wait_active(unit)
        check(snapshot() == saved["snapshot"], "cold-boot-config-sid-ntacl-password")

    if not SAMBA:
        check(run("standalone-samba-absence", ["rpm", "-q", "samba422-offline"],
                  good=False).returncode != 0, "webmin-without-samba")
    if not WEBMIN:
        check(run("standalone-webmin-absence", ["rpm", "-q", "webmin-offline"],
                  good=False).returncode != 0, "samba-without-webmin")

    if WEBMIN:
        webmin_test(mutate=(phase == 1))
    if SAMBA:
        samba_test(create_ntacl=(phase == 1))
        if phase == 1:
            (PRIVATE / "persist-input").write_bytes(b"survives-cold-boot\n")
            smb("persistent-data-upload",
                "put " + str(PRIVATE / "persist-input") + " persisted.txt")
        else:
            smb("persistent-data-download",
                "get persisted.txt " + str(PRIVATE / "persist-output"))
            check((PRIVATE / "persist-output").read_bytes() ==
                  b"survives-cold-boot\n", "cold-boot-smb-data")

    if phase == 1:
        before = snapshot()
        lifecycle()
        check(snapshot() == before, "helpers-preserve-identity-and-config")
        if WEBMIN:
            webmin_test(mutate=False)
        if SAMBA:
            samba_test(create_ntacl=False)
        write_state({
            "case": CASE, "run": nonce, "boot_id": boot_id,
            "password": PASSWORD, "candidates": candidates, "snapshot": snapshot()
        })

    check(text("final-selinux-mode", ["getenforce"]) == "Enforcing",
          "selinux-remains-enforcing")
    for unit in UNITS:
        pid = text("real-service-pid",
                   ["systemctl", "show", "-p", "MainPID", "--value", unit])
        check(pid.isdigit() and int(pid) > 1, "real-service-process")
        context = Path("/proc/" + pid + "/attr/current").read_text().strip()
        print("SERVICE_CONTEXT unit=" + unit + " context=" + context, flush=True)
    for name, candidate in sorted(candidates.items()):
        print("CANDIDATE bundle=%s nevra=%s sha256=%s" %
              (name, candidate["nevra"], candidate["sha256"]), flush=True)
    os.sync()
    print("NATIVE_PASS case=%s phase=%s run=%s" % (CASE, phase, nonce), flush=True)
    run("orderly-poweroff", ["systemctl", "--no-block", "poweroff"])


try:
    main()
except Exception:
    # Fixed labels only: omit exception text, traceback, argv and captured output.
    print("NATIVE_FAIL case=%s stage=%s" % (CASE, STAGE), flush=True)
    try:
        subprocess.run(
            ["systemctl", "--no-block", "poweroff"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30
        )
    except Exception:
        pass
    sys.exit(1)
