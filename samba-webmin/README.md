# Samba + Webmin 离线交付工程

固定目标版本：Samba 4.22.11、Webmin 2.670、ARM64。Docker 基础镜像为 Debian 13 ARM64。

目录：
- docker/：Docker 镜像、Compose 和容器入口构建材料。
- native/：麒麟 V10 SP3-2403 原生 RPM 与 Webmin 离线构建材料（待完善）。
- tests/：自动化验证（待完善）。

本仓库不会把 Debian 包或容器内程序复制成麒麟原生 RPM。只有完成独立原生 ARM64 安装验证后，才允许发布原生包。
