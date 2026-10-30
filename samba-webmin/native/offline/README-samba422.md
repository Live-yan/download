# Samba 4.22.11 麒麟 ARM64 原生离线包

目标：麒麟 V10 SP3-2403 aarch64，新安装。无需 Docker，不现场编译，不联网下载。
程序独立安装到 /opt/samba-4.22.11，不替换系统自带 Samba。不要与旧 Samba 或 Docker 同时占用 445。
厂商依赖保留 RPM 签名验证；application 中的程序 RPM 是本次 Actions 构建的独立未签名应用，只有该本地仓库不要求厂商签名。

## 解压和离线安装

在压缩包所在目录执行，需管理员权限：

```sh
sudo mkdir -p /opt/offline
sudo tar -xzf samba-kylin-v10sp3-arm64-offline.tar.gz -C /opt/offline
cd /opt/offline/samba422
sudo dnf --setopt=install_weak_deps=False --setopt=reposdir="$PWD" --disablerepo='*' --enablerepo='samba422-*' install samba422-offline iproute passwd shadow-utils acl attr
sudo systemctl daemon-reload
```

包内仓库路径固定为 /opt/offline/samba422；不要更名后不修改 offline.repo。依赖已随包提供。安装不会自动启动服务或创建密码。

## 新建共享用户和目录

仅用于新账号，遇到同名账号或目录先人工确认，不能覆盖旧数据：

```sh
sudo groupadd smbusers
sudo useradd -M -g smbusers -s /sbin/nologin fileshare
sudo /opt/samba-4.22.11/bin/smbpasswd -c /etc/samba-4.22.11/smb.conf -a fileshare
sudo install -d -m 2770 -o fileshare -g smbusers /srv/samba422/share
sudo vi /etc/samba-4.22.11/smb.conf
```

保留已有 global 段，在其中设置实际内网地址，例如 interfaces = lo 192.168.1.10，并设置 bind interfaces only = yes。再添加：

```ini
[share]
    path = /srv/samba422/share
    browseable = yes
    read only = no
    guest ok = no
    valid users = @smbusers
    force group = smbusers
    create mask = 0660
    directory mask = 2770
    vfs objects = acl_xattr
    map acl inherit = yes
```

```sh
sudo /opt/samba-4.22.11/bin/testparm -s /etc/samba-4.22.11/smb.conf
sudo sh samba-manage.sh start
sudo systemctl enable samba422.service
```

Windows 使用 \\\\服务器IP\\share，用户 fileshare。请实际验证中文文件读写、删除和权限。
不关闭 SELinux 或防火墙；实际网络访问规则由管理员按现有策略处理。

## 日常管理

```sh
sudo sh /opt/offline/samba422/samba-manage.sh start
sudo sh /opt/offline/samba422/samba-manage.sh stop
sudo sh /opt/offline/samba422/samba-manage.sh restart
```

脚本只控制 samba422.service，不初始化、不删数据、不停止其他服务。停止前结束文件写入。

配置：/etc/samba-4.22.11。状态、SID 和密码库：/var/lib/samba-4.22.11。共享数据：你配置的目录。备份须同时保留这些数据、系统账号 UID/GID 与文件 ACL/xattr。

卸载前停止并禁用服务，再用 dnf remove samba422-offline。不要默认清理配置、状态、账号或共享目录；不要批量删除依赖包。

独立 Samba 不需要 Webmin。若要用 Webmin 管理，另安装配套原生 Webmin 包，其中已配置本程序的独立路径。
最终验证范围以对应 Release 和 Actions 记录为准；官方组件组装的麒麟 VM 不等于实体麒麟服务器验收。
