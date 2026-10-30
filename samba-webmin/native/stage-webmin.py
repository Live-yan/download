import os
from pathlib import Path
import shutil,subprocess,sys,tempfile
root=Path(sys.argv[1]).resolve()
assert root!=Path("/") and os.geteuid()==0
app=root/"usr/libexec/webmin"; config=root/"etc/webmin"; var=root/"var/webmin"
assert (app/"version").read_text().strip()=="2.670"
config.mkdir(parents=True,exist_ok=True); var.mkdir(parents=True,exist_ok=True)
setup=app/"setup.sh"; source=setup.read_text()
tls="\topenssl version >/dev/null 2>&1\n"
assert source.count(tls)==1
source=source.replace(tls,"\tfalse # Offline HTTP backend: no TLS key generation\n")
boot='(cd "$wadir/init" ; WEBMIN_CONFIG=$config_dir WEBMIN_VAR=$var_dir "$wadir/init/updateboot.pl" "$bootscript")'
assert source.count(boot)==1
source=source.replace(boot,": # RPM staging: no host boot integration")
setup.write_text(source)
with tempfile.TemporaryDirectory(prefix="webmin-rpm-stage-") as temp:
 env=dict(os.environ)
 env.update(config_dir=str(config),var_dir=str(var),tempdir=temp,perl="/usr/bin/perl",
 port="10000",login="root",crypt="x",ssl="0",atboot="0",nostart="1",
 nopostinstall="1",nouninstall="1",noportcheck="1",os_type="generic-linux",os_version="4.19",
 real_os_type="Kylin Linux Advanced Server",real_os_version="V10 SP3-2403")
 for key in ("makeboot","upgrading","webmin_upgrade","setup_pre","password","pam"): env.pop(key,None)
 subprocess.run(["/bin/sh",str(setup)],env=env,stdin=subprocess.DEVNULL,check=True)
assert (config/"miniserv.users").read_text()=="root:x:0\n"
assert not (config/"miniserv.pem").exists()
prefix=str(root); prefix_bytes=prefix.encode()
for p in root.rglob("*"):
 if p.is_symlink():
  target=os.readlink(p)
  if prefix in target:
   assert target.startswith(prefix+"/")
   p.unlink(); p.symlink_to(target[len(prefix):])
 elif p.is_file():
  original=p.read_bytes()
  replaced=original.replace(prefix_bytes,b"").replace(temp.encode(),b"/tmp/.webmin")
  if replaced!=original: p.write_bytes(replaced)
def update(path,values):
 lines=[l for l in path.read_text().splitlines() if l.split("=",1)[0] not in values]
 path.write_text("\n".join(lines+[f"{k}={v}" for k,v in values.items()])+"\n")
update(config/"config",dict(lang="zh",referers="localhost",referers_none="1",
 tempdir="/tmp/.webmin",os_type="generic-linux",os_version="4.19",
 real_os_type="Kylin Linux Advanced Server",real_os_version="V10 SP3-2403"))
update(config/"miniserv.conf",dict(root="/usr/libexec/webmin",mimetypes="/usr/libexec/webmin/mime.types",
 bind="127.0.0.1",port="10000",listen="10000",ipv6="0",ssl="0",ssl_enforce="0",ssl_hsts="0",
 no_ssl_warn="1",no_pam="1",trust_real_ip="0",logtrust="0",passwd_file="/etc/shadow",
 passwd_uindex="0",passwd_pindex="1",passwd_cindex="2",passwd_mindex="4",passwd_blank="0",
 passwd_mode="0",userfile="/etc/webmin/miniserv.users",env_WEBMIN_CONFIG="/etc/webmin",
 env_WEBMIN_VAR="/var/webmin",logfile="/var/webmin/miniserv.log",
 errorlog="/var/webmin/miniserv.error",pidfile="/run/webmin-offline/miniserv.pid",atboot="0"))
update(config/"samba/config",dict(smb_conf="/etc/samba-4.22.11/smb.conf",
 samba_server="/opt/samba-4.22.11/sbin/smbd",name_server="/opt/samba-4.22.11/sbin/nmbd",
 winbind_server="/opt/samba-4.22.11/sbin/winbindd",
 samba_password_program="/opt/samba-4.22.11/bin/smbpasswd",
 samba_status_program="/opt/samba-4.22.11/bin/smbstatus",pdbedit="/opt/samba-4.22.11/bin/pdbedit",
 net="/opt/samba-4.22.11/bin/net",
 restart_cmd="/opt/samba-4.22.11/bin/smbcontrol -s /etc/samba-4.22.11/smb.conf all reload-config"))
for name,action in dict(start="start",stop="stop",restart="restart",reload="reload",**{"restart-by-force-kill":"restart"}).items():
 p=config/name
 if p.exists() or p.is_symlink(): p.unlink()
 p.write_text("#!/bin/sh\nexec /usr/bin/systemctl --no-block "+action+" webmin-offline.service\n")
 p.chmod(0o755)
shutil.rmtree(var); var.mkdir(mode=0o700)
(config/"miniserv.users").chmod(0o600); (config/"miniserv.conf").chmod(0o600); config.chmod(0o750)
for p in root.rglob("*"):
 if p.is_symlink(): assert prefix not in os.readlink(p)
 elif p.is_file():
  b=p.read_bytes()
  assert prefix_bytes not in b and temp.encode() not in b, "Staging path leak: "+str(p)
assert (config/"perl-path").read_text().strip()=="/usr/bin/perl"
assert (config/"var-path").read_text().strip()=="/var/webmin"
assert not (config/"miniserv.pem").exists()
assert not (config/"uninstall.sh").exists()
