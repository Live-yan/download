import os,pathlib,re,stat,subprocess
root=pathlib.Path("/work/rootfs")
image="/work/root.ext4"
work=pathlib.Path("/work/labels")
work.mkdir()
contexts="/etc/selinux/targeted/contexts/files/file_contexts"
def run(args):
 return subprocess.check_output(args,universal_newlines=True).strip()
def quote(path):
 if any(c in path for c in ['"',"\\","\n","\r","\x00"]):
  raise RuntimeError("Unsupported debugfs pathname: "+repr(path))
 return '"'+path+'"'
def filetype(mode):
 for check,name in [(stat.S_ISREG,"file"),(stat.S_ISDIR,"dir"),(stat.S_ISLNK,"lnk_file"),(stat.S_ISCHR,"chr_file"),(stat.S_ISBLK,"blk_file"),(stat.S_ISFIFO,"pipe"),(stat.S_ISSOCK,"sock_file")]:
  if check(mode): return name
 raise RuntimeError("Unknown inode type")
paths=[root]
for directory,dirs,files in os.walk(str(root),followlinks=False):
 paths.extend(pathlib.Path(directory)/name for name in dirs+files)
writes,reads,checks=[],[],[]
seen={}
skipped=[]
for path in paths:
 guest="/"+str(path.relative_to(root))
 if guest=="/.": guest="/"
 info=path.lstat()
 context=run(["matchpathcon","-N","-n","-f",contexts,"-m",filetype(info.st_mode),guest])
 if context=="<<none>>":
  skipped.append(guest); continue
 if not re.fullmatch(r"[A-Za-z0-9_:.,-]+",context): raise RuntimeError("Unexpected context: "+repr(context))
 key=(info.st_dev,info.st_ino)
 if key in seen:
  if seen[key]!=context: raise RuntimeError("Conflicting hardlink labels: "+guest)
  continue
 seen[key]=context
 index=len(checks); value=work/("value-"+str(index)); output=work/("read-"+str(index))
 expected=context.encode()+b"\0"
 value.write_bytes(expected)
 writes.append("ea_set -f %s %s security.selinux"%(str(value),quote(guest)))
 reads.append("ea_get -f %s %s security.selinux"%(str(output),quote(guest)))
 checks.append((guest,output,expected))
for filename,commands in [("write.cmd",writes),("read.cmd",reads)]:
 command_file=work/filename
 command_file.write_text("\n".join(commands)+"\n")
 with (work/(filename+".log")).open("w") as log:
  subprocess.check_call(["debugfs","-w","-f",str(command_file),image],stdout=log,stderr=subprocess.STDOUT)
for guest,output,expected in checks:
 if not output.exists() or output.read_bytes()!=expected:
  raise RuntimeError("SELinux xattr round-trip failed: "+guest)
(work/"skipped.txt").write_text("\n".join(skipped)+"\n")
print("Verified SELinux labels:",len(checks))
