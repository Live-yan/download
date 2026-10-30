import os,pathlib,re,struct,subprocess,sys
root=pathlib.Path(sys.argv[1])
prefix="/opt/samba-4.22.11/"
log=pathlib.Path(sys.argv[2])
count=0
with log.open("w") as out:
 for directory,dirs,names in os.walk(str(root/prefix.lstrip("/")),followlinks=False):
  for name in names:
   p=pathlib.Path(directory)/name
   if p.is_symlink() or not p.is_file(): continue
   with p.open("rb") as f:
    h=f.read(64)
    if h[:4]!=b"\x7fELF": continue
    assert h[4:6]==b"\x02\x01",str(p)
    assert struct.unpack_from("<H",h,18)[0]==183,str(p)
    if struct.unpack_from("<H",h,16)[0] not in (2,3): continue
    off=struct.unpack_from("<Q",h,32)[0]
    size,num=struct.unpack_from("<HH",h,54)
    assert num<4096 and size>=56
    f.seek(off); ph=f.read(size*num)
    assert len(ph)==size*num
    if not any(struct.unpack_from("<I",ph,i*size)[0]==2 for i in range(num)): continue
   guest="/"+str(p.relative_to(root))
   result=subprocess.run(["chroot",str(root),"/usr/bin/ldd",guest],
    universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
    env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LC_ALL":"C"})
   out.write(guest+"\n"+result.stdout+"\n")
   assert result.returncode==0,(guest,result.stdout)
   assert "not found" not in result.stdout,(guest,result.stdout)
   for line in result.stdout.splitlines():
    if re.search(r"lib(talloc|tdb|tevent|ldb)",line) and "=>" in line:
     resolved=line.split("=>",1)[1].strip().split()[0]
     assert resolved.startswith(prefix),(guest,line)
   count+=1
assert count>=6,"Expected program and module ELF coverage"
print("Verified dynamic ELF objects:",count)
