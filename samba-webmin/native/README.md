# 麒麟原生构建状态

目标基线为 Kylin Linux Advanced Server V10 SP3-2403 aarch64。官方发布说明给出的基线包含 glibc 2.28、GCC 7.3.0，包管理体系为 RPM/DNF(YUM)。官方发行说明： https://kylinos.cn/

本目录暂不包含伪装为麒麟原生的 Debian 包，也不从容器复制二进制。需要在麒麟原生 ARM64 构建环境中生成 RPM 及完整依赖闭包，并在干净麒麟环境断网安装、启动和执行 SMB/Webmin 联合测试。
