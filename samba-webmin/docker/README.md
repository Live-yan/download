# Samba 4.22.11 + Webmin 2.670（Docker ARM64）

> 当前为构建材料，未通过端到端验收前不得作为正式离线交付包使用。

目标为 linux/arm64。需要 Docker Engine 与 Docker Compose V2 插件。管理界面仅通过宿主机回环地址 127.0.0.1:10000 提供 HTTP，适合同机 Nginx 反代；不要将管理端口暴露到公网。

首次初始化需要交互创建 Linux 用户并设置 Samba 密码、Webmin 管理员密码。当前构建脚本尚未实现独立初始化服务与最终五文件归档，不能直接用于生产安装。

Webmin 上游： https://webmin.com/download/
Samba 上游： https://www.samba.org/samba/download/
