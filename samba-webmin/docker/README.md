# Samba + Webmin ARM64 Docker 离线包

用于新安装的 ARM64 Linux。镜像内为 Debian 13、Samba 4.22.11、Webmin 2.670。麒麟真机仍需现场验收。本包只含镜像、配置、本文和三合一管理脚本。

前置条件：已安装 Docker Engine 20.10+ 与 Docker Compose V2（建议 2.20+）。只有 Docker 不一定有 Compose，离线机器需提前安装对应 ARM64 插件。本包不会在线下载或安装 Docker/Compose。

## 加载与填写地址

解压后进入本目录，执行：

```sh
docker load -i webmin-samba-arm64.tar.gz
cp .env.example .env
vi .env
```

SMB_BIND_IP 填服务器内网 IPv4，不使用 0.0.0.0；WEBMIN_HOST 填已有 Nginx 对外域名，不含协议/路径/端口。默认外部入口为 HTTPS 443，由你的 Nginx 处理；容器后端始终 HTTP，不生成证书。445 与本机 10000 不能被其他服务占用。

## 首次初始化

仅用于新数据卷。不要与已有同名 Compose 项目混用，不覆盖旧系统。

```sh
docker compose run --rm initialize
```

按提示交互设置容器 root（Webmin 管理员）密码和 fileshare（SMB）密码。二者可以不同，不修改宿主 root，不在 .env 保存密码。初始化无网络、无端口，完成后退出并删除临时容器。不要同时运行初始化与正式服务。

## 启动、停止、重启

```sh
sh webmin-samba-manage.sh start
docker compose ps
docker compose logs --tail 50 samba-webmin
```

等待服务 healthy。按需要执行：

```sh
sh webmin-samba-manage.sh stop
sh webmin-samba-manage.sh restart
```

start 支持首次创建及容器重建，不拉镜像、不编译；stop/restart 不删数据。停止前结束正在进行的文件写入，30 秒超时后可能强制结束。

Windows 访问 \\\\服务器IP\\share，账号 fileshare。请实测中文文件上传、下载与删除。Webmin 通过你已有的 Nginx 域名访问，账号 root。管理范围是容器，不是宿主机。

## Nginx

后端只发布在宿主 127.0.0.1:10000。以下 location 加入你已有的同域名 server 配置，已有的 TLS/证书由你管理。支持 WebSocket：

```nginx
# http 块中定义一次
map $http_upgrade $webmin_connection {
    default upgrade;
    '' close;
}

# 已有 server 块内
location / {
    proxy_pass http://127.0.0.1:10000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $webmin_connection;
    proxy_set_header X-Forwarded-For "";
    proxy_set_header X-Real-IP "";
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 3600s;
    client_max_body_size 1g;
}
```

这适用于 Nginx 直接运行在同一宿主机。Nginx 在容器内时，127.0.0.1 是其自身，需要专用共享网络；在另一台机器时，需要另行设计受控连接，不能直接把后端暴露到公网。WEBMIN_HOST/外部端口与实际入口一致；只改 .env 后用 start 应用新配置，restart 不更新环境变量。

## 账号和数据

```sh
docker compose exec samba-webmin passwd root
docker compose exec samba-webmin smbpasswd -c /etc/samba/smb.conf fileshare
```

Webmin 可管理 Unix 用户及 Samba 用户，新增共享用户需同时具有 Unix 身份和 Samba 密码。共享配置在 /etc/samba/smb.conf。

配置与系统账号保存在 system_config 卷，Samba 状态在 samba_state，文件在 samba_share，Webmin 运行状态在 webmin_var。不要执行 down -v、volume prune 或删除这些卷。备份需覆盖所有相关卷并保证一致性。本包固定软件组合；全量 /etc 持久化意味着跨版本升级须另做迁移验证，不应盲换镜像。

## 开机启动

Compose 已配置 unless-stopped。由管理员执行：

```sh
systemctl enable docker.service
```

若本机存在独立 containerd.service，再执行 systemctl enable containerd.service。手工 stop 后，服务器重启仍保持停止，需手工 start；不需要另建容器 systemd 单元。

## 验证边界

Release 以对应 Actions 运行记录为准。ARM64 runner、离线容器和保存/加载测试不等于麒麟宿主真机、实际 Nginx TLS/WebSocket、客户端及开机流程验收。无 privileged、docker.sock 或关闭 SELinux 的要求。
