# Webmin 2.670 麒麟原生离线包

目标：麒麟 V10 SP3-2403 aarch64，新安装。无需 Docker，不联网安装依赖。
使用通用 Linux 4.19 模块配置适配麒麟，保留真实系统名称；不是 Debian/RHEL 安装包冒充麒麟。
后端仅 HTTP 127.0.0.1:10000，由你的同机 Nginx 处理外部 HTTPS。本包不生成证书、不内置密码。
Webmin 可独立运行；Samba 管理功能需要另安装配套 Samba 原生包。

## 解压和离线安装

```sh
sudo mkdir -p /opt/offline
sudo tar -xzf webmin-kylin-v10sp3-arm64-offline.tar.gz -C /opt/offline
cd /opt/offline/webmin
sudo dnf --setopt=install_weak_deps=False --setopt=reposdir="$PWD" --disablerepo='*' --enablerepo='webmin-*' install webmin-offline iproute passwd shadow-utils acl attr
sudo systemctl daemon-reload
```

路径固定为 /opt/offline/webmin。厂商依赖保留签名验证；application 是本次 Actions 构建的独立未签名应用，只有该本地仓库不要求厂商签名。
安装不自动启动、不修改系统密码；检测到已有 Webmin 会拒绝接管，应先人工处理。

## 管理员和 Nginx

初始管理员为 root，采用本机 Unix 密码认证，没有默认密码。若需要设置 root 密码，可由管理员交互执行 passwd root；这会修改宿主机 root 密码，请按你的账号策略决定，不要把它当作 Docker 内独立密码。

编辑 /etc/webmin/config 中的 referers 为已有 Nginx 的外部域名。编辑 /etc/webmin/miniserv.conf，保留 ssl=0 和 bind=127.0.0.1，并配置：

```ini
redirect_host=webmin.example.com
redirect_ssl=1
redirect_port=443
```

把示例域名改为实际域名。仅设置外部跳转，不启用后端 TLS。
Nginx 在同宿主机的现有 server 块中使用 proxy_pass http://127.0.0.1:10000，并转发 Host 与 WebSocket Upgrade/Connection。已有入口证书由你管理，不要把 Webmin 10000 直接暴露公网。

```sh
sudo sh webmin-manage.sh start
sudo systemctl enable webmin-offline.service
```

通过 Nginx 域名登录。系统账号权限和 Samba 密码是不同层；新增共享用户需配置两者。

## 日常管理

```sh
sudo sh /opt/offline/webmin/webmin-manage.sh start
sudo sh /opt/offline/webmin/webmin-manage.sh stop
sudo sh /opt/offline/webmin/webmin-manage.sh restart
```

配置：/etc/webmin；运行状态：/var/webmin。脚本不改配置或密码，不删除数据。
Samba 模块已指向 /opt/samba-4.22.11 与 /etc/samba-4.22.11/smb.conf；未安装 Samba 时不影响 Webmin 自身启动。

卸载前停止、禁用 webmin-offline.service，再使用 dnf remove webmin-offline；不要默认删除 /etc/webmin、/var/webmin 或已有共享数据。

最终验证范围以 Release 和 Actions 为准。官方组件组装的麒麟 VM 不是你的实体服务器验收，真实 Nginx/客户端配置需现场确认。

未包含上游可选 DateTime 本地化增强模块；日期使用 Webmin 内置格式，增强区域日期/时区选择不可用。简体中文界面、身份认证、用户与 Samba 管理不依赖这些模块。

依据：[Webmin 2.670 官方 RPM 依赖定义](https://github.com/webmin/webmin/blob/2.670/makerpm.pl)。
