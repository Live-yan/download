# 验收测试

发布门禁要求：
1. Docker linux/arm64 镜像构建、保存/加载、SMB 文件操作、持久化和 HTTP Webmin 认证。
2. Kylin V10 SP3-2403 原生 ARM64 Samba RPM 断网安装与 systemd 测试。
3. Webmin 原生依赖离线安装、HTTP 回环监听和登录测试。
4. Samba + Webmin 联合安装，通过 Webmin 修改共享/用户权限后验证 SMB 行为。
5. 测试失败保留日志并阻止 Release。
