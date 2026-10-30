#!/usr/bin/env python3
"""CI-only offline runtime tests. Never shipped inside user archives."""
import json, os, pathlib, secrets, shutil, subprocess, sys, tempfile, time, uuid

IMAGE = "local/samba-webmin:4.22.11-webmin-2.670-arm64"
PASSWORD = secrets.token_hex(24)
print("::add-mask::" + PASSWORD, flush=True)
PREFIX = "swtest-" + uuid.uuid4().hex[:12]

def run(args, data=None, ok=True, cwd=None, env=None):
    p = subprocess.run(args, input=data, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, cwd=cwd, env=env)
    if ok and p.returncode:
        raise RuntimeError("Command failed: " + repr(args) + "\n" + p.stdout.replace(PASSWORD, "<masked>"))
    return p

def dx(c, script, data=None):
    return run(["docker", "exec", "-i", c, "sh", "-ec", script], data).stdout

def ready(c):
    for _ in range(90):
        if run(["docker", "exec", c, "curl", "-fsS", "--max-time", "2",
                "http://127.0.0.1:10000/session_login.cgi"], ok=False).returncode == 0:
            return
        state = run(["docker", "inspect", c, "--format", "{{.State.Running}}"]).stdout.strip()
        if state != "true":
            raise RuntimeError(run(["docker", "logs", c], ok=False).stdout)
        time.sleep(1)
    raise RuntimeError("Service readiness timeout\n" + run(["docker", "logs", c], ok=False).stdout)

INIT = r'''
IFS= read -r password
printf 'root:%s\n' "$password" | chpasswd
printf '%s\n%s\n' "$password" "$password" | smbpasswd -c /etc/samba/smb.conf -s -a fileshare
useradd -u 45678 -g smbusers -M -s /usr/sbin/nologin persistuser
umask 077
: > /etc/.samba-webmin-initialized
printf 'persistent-configuration\n' > /etc/ci-persistence-marker
printf 'owner-marker\n' > /srv/samba/share/owner-marker
chown 45678:smbusers /srv/samba/share/owner-marker
chmod 0640 /srv/samba/share/owner-marker
setfattr -n user.offline-test -v persistent /srv/samba/share/owner-marker
setfacl -m u:fileshare:r /srv/samba/share/owner-marker
'''

AUTH = r'''
import http.client,re,sys,urllib.parse
password=sys.stdin.readline().strip()
from pathlib import Path
import subprocess
def request(method,path,data=None,cookie=None):
 c=http.client.HTTPConnection("127.0.0.1",10000,timeout=20)
 headers={"Host":"localhost","Referer":"https://localhost/"}
 if cookie: headers["Cookie"]=cookie
 if data is not None:
  data=urllib.parse.urlencode(data)
  headers["Content-Type"]="application/x-www-form-urlencoded"
 c.request(method,path,data,headers)
 r=c.getresponse(); result=(r.status,r.getheaders(),r.read().decode("utf-8","replace")); c.close(); return result
def login(p):
 status,headers,body=request("POST","/session_login.cgi",{"user":"root","pass":p,"page":"/"},"testing=1")
 cookies=[v for k,v in headers if k.lower()=="set-cookie"]
 sids=[m.group(1) for v in cookies for m in [re.search(r"(?:^|;\s*)sid=([^; ]+)",v)] if m]
 return [x for x in sids if x not in ("0","deleted","")],cookies
bad,_=login(password+"wrong")
assert not bad,"Wrong Webmin password accepted"
sids,cookies=login(password)
assert sids and any("secure" in x.lower() for x in cookies),"No authenticated secure session"
cookie="sid="+sids[-1]
status,_,body=request("GET","/samba/",cookie=cookie)
assert status==200 and not re.search(r'name=["\x27]?pass(?:["\x27 >])',body),"Protected Samba page unavailable"
if Path("/etc/.ci-webmin-user-created").exists():
 actual=subprocess.run(["testparm","-s","--section-name=share","--parameter-name=comment","/etc/samba/smb.conf"],check=True,capture_output=True,text=True).stdout.strip()
 assert actual=="CI-Webmin-marker","Webmin share configuration was not retained"
else:
 status,_,body=request("POST","/samba/save_fshare.cgi",{
  "old_name":"share","share":"share","homes":"0","path":"/srv/samba/share",
  "available":"yes","browseable":"yes","comment":"CI-Webmin-marker"
 },cookie)
 assert status in (200,302,303),"Webmin share update failed"
if not Path("/etc/.ci-webmin-user-created").exists():
 status,_,body=request("POST","/samba/make_epass.cgi",{"who":"0","include_list":"persistuser","add":"1","newmode":"2","newpass":password},cookie)
 assert status in (200,302,303),"Webmin account creation failed"
 Path("/etc/.ci-webmin-user-created").touch()
status,_,body=request("GET","/samba/restart.cgi",cookie=cookie)
assert status in (200,302,303),"Webmin apply failed"
print("Webmin authentication, wrong-password rejection and protected module operation passed")
'''

def verify(c):
    ready(c)
    dx(c, "umask 077; cat > /tmp/auth", "username = fileshare\npassword = " + PASSWORD + "\n")
    # Execute Python source from a file, with password only on stdin.
    dx(c, "umask 077; cat > /tmp/auth-test.py", AUTH)
    out = run(["docker", "exec", "-i", c, "python3", "/tmp/auth-test.py"], PASSWORD+"\n").stdout
    print(out.strip())
    dx(c, r'''
test "$(id -u persistuser)" = 45678
test "$(stat -c %u:%a /srv/samba/share/owner-marker)" = 45678:640
grep -qx persistent-configuration /etc/ci-persistence-marker
pdbedit -s /etc/samba/smb.conf -L -u persistuser | grep -q "^persistuser:45678:"
sed "s/username = fileshare/username = persistuser/" /tmp/auth > /tmp/persist-auth
smbclient //127.0.0.1/share -s /etc/samba/smb.conf -A /tmp/persist-auth -c ls
getfattr --only-values -n user.offline-test /srv/samba/share/owner-marker | grep -qx persistent
getfacl -cp /srv/samba/share/owner-marker | grep -q 'user:fileshare:r--'
test "$(testparm -s --section-name=share --parameter-name=comment /etc/samba/smb.conf 2>/dev/null)" = CI-Webmin-marker
printf 'offline-read-write-delete\n' > /tmp/input
smbclient //127.0.0.1/share -s /etc/samba/smb.conf -A /tmp/auth -c 'put /tmp/input 中文文件.txt; get 中文文件.txt /tmp/output; del 中文文件.txt'
cmp /tmp/input /tmp/output
if smbclient //127.0.0.1/share -N -c ls; then exit 1; fi
printf 'username = fileshare\npassword = definitely-wrong\n' > /tmp/bad-auth
if smbclient //127.0.0.1/share -A /tmp/bad-auth -c ls; then exit 1; fi
test ! -e /etc/webmin/miniserv.pem
''')

def offline_test():
    c=PREFIX+"-server"
    volumes=[PREFIX+"-"+s for s in ("etc","state","share","webmin")]
    mounts=sum((["-v",v+":"+p] for v,p in zip(volumes,("/etc","/var/lib/samba","/srv/samba/share","/var/webmin"))),[])
    try:
        for v in volumes: run(["docker","volume","create",v])
        assert run(["docker","image","inspect",IMAGE,"--format","{{.Os}}/{{.Architecture}}"]).stdout.strip()=="linux/arm64"
        run(["docker","run","--rm","--network","none","--entrypoint","sh",IMAGE,"-ec",
             'test "$(cat /usr/share/webmin/version)" = 2.670; smbd -V | grep -F 4.22.11; test ! -e /etc/.samba-webmin-initialized; test ! -e /etc/webmin/miniserv.pem; grep -qx "lang=zh" /etc/webmin/config; grep -Eq "^root:[!*]" /etc/shadow'])
        assert run(["docker","run","--rm","--network","none",*mounts,IMAGE],ok=False).returncode != 0
        run(["docker","run","--rm","-i","--network","none",*mounts,"--entrypoint","sh",IMAGE,"-ec",INIT],PASSWORD+"\n")
        def start():
            run(["docker","run","-d","--name",c,"--network","none","-e","WEBMIN_HOST=localhost",*mounts,IMAGE])
        start()
        verify(c)
        sid=dx(c,"net -s /etc/samba/smb.conf getlocalsid").strip()
        dx(c,"smbclient //127.0.0.1/share -s /etc/samba/smb.conf -A /tmp/auth -c 'put /tmp/input persisted.txt'")
        run(["docker","stop","-t","30",c])
        assert run(["docker","inspect",c,"--format","{{.State.ExitCode}}"]).stdout.strip()=="0"
        run(["docker","start",c]); verify(c)
        run(["docker","restart","-t","30",c]); verify(c)
        run(["docker","rm","-f",c]); start(); verify(c)
        assert dx(c,"net -s /etc/samba/smb.conf getlocalsid").strip()==sid
        dx(c,"smbclient //127.0.0.1/share -s /etc/samba/smb.conf -A /tmp/auth -c 'get persisted.txt /tmp/persisted'; cmp /tmp/input /tmp/persisted")
        print("PASS: offline SMB/Webmin, identity/ACL/xattr/data persistence and lifecycle")
    finally:
        run(["docker","logs",c],ok=False)
        run(["docker","rm","-f",c],ok=False)
        for v in volumes: run(["docker","volume","rm",v],ok=False)

def compose_test(package):
    with tempfile.TemporaryDirectory(prefix=PREFIX) as tmp:
        root=pathlib.Path(tmp)
        for name in ("compose.yaml","webmin-samba-manage.sh"):
            shutil.copyfile(pathlib.Path(package)/name,root/name)
        (root/".env").write_text("SMB_BIND_IP=127.0.0.1\nWEBMIN_HOST=localhost\nWEBMIN_PUBLIC_SCHEME=https\nWEBMIN_PUBLIC_PORT=443\n")
        env={**os.environ,"COMPOSE_PROJECT_NAME":PREFIX}
        base=["docker","compose"]
        try:
            config=json.loads(run(base+["config","--format","json"],cwd=root,env=env).stdout)
            service=config["services"]["samba-webmin"]
            assert service["pull_policy"]=="never" and service["restart"]=="unless-stopped"
            assert all(p["host_ip"]=="127.0.0.1" for p in service["ports"])
            assert config["services"]["initialize"]["network_mode"]=="none"
            # Internal bridge prevents outbound internet while preserving real published-port testing.
            (root/"compose.override.yaml").write_text("networks:\n  default:\n    internal: true\n")
            run(base+["run","--rm","-T","--entrypoint","sh","initialize","-ec",INIT],PASSWORD+"\n",cwd=root,env=env)
            script=str(root/"webmin-samba-manage.sh")
            assert run(["sh",script,"invalid"],cwd="/tmp",env=env,ok=False).returncode!=0
            run(["sh",script,"start"],cwd="/tmp",env=env)
            c=run(base+["ps","-q","samba-webmin"],cwd=root,env=env).stdout.strip()
            verify(c)
            ports=json.loads(run(["docker","inspect",c,"--format","{{json .HostConfig.PortBindings}}"]).stdout)
            assert ports["10000/tcp"][0]["HostIp"]=="127.0.0.1"
            for action in ("stop","start","restart"):
                run(["sh",script,action],cwd="/tmp",env=env)
                if action!="stop": verify(c)
            print("PASS: unpacked Compose configuration and actual three-action helper")
        finally:
            run(base+["down","-v","--remove-orphans"],cwd=root,env=env,ok=False)

if __name__=="__main__":
    if len(sys.argv)>1: compose_test(sys.argv[1])
    else: offline_test()
