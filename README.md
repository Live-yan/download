# GitHub Actions 通用下载器

通过 GitHub Actions 在云端下载文件或拉取指定架构的 Docker 镜像，并自动发布到 GitHub Release。

适合以下场景：

- 本地网络难以访问 Docker Hub 或国外下载站；
- 在 Windows x86 电脑上准备 ARM64 Docker 镜像；
- 将镜像通过 U 盘带到离线 Linux/麒麟服务器；
- 下载普通 HTTP/HTTPS 文件并生成 SHA256 校验值。

## 功能

- 支持普通 URL 下载；
- 支持 Docker 镜像跨架构拉取；
- 支持 `linux/amd64`、`linux/arm64/v8` 等平台；
- 支持不压缩、gzip、zip；
- 自动生成 `SHA256SUMS`；
- 自动上传 Actions Artifact；
- 可自动创建或更新 GitHub Release；
- 同名 Release 文件可覆盖更新。

## 一、下载 ARM64 MySQL 镜像

进入仓库的 **Actions** 页面，选择：

```text
通用下载并发布 Release
```

点击：

```text
Run workflow
```

填写以下参数：

| 参数 | 值 |
|---|---|
| mode | `docker` |
| source | `mysql:8.0.46` |
| platform | `linux/arm64/v8` |
| output_name | `mysql-8.0.46-arm64.tar` |
| compression | `gzip` |
| release_tag | `mysql-8.0.46-arm64` |
| release_title | `MySQL 8.0.46 ARM64 离线镜像` |
| publish_release | 勾选 |

运行成功后进入仓库的 **Releases** 页面，下载：

```text
mysql-8.0.46-arm64.tar.gz
mysql-8.0.46-arm64-image-info.json
mysql-8.0.46-arm64-README.txt
SHA256SUMS
```

## 二、麒麟 V10 SP3 ARM64 服务器导入

确认服务器架构：

```bash
uname -m
docker info --format 'OS={{.OSType}} ARCH={{.Architecture}}'
```

正确结果应包含：

```text
aarch64
ARCH=arm64
```

将 Release 中的文件复制到同一目录，例如：

```bash
mkdir -p /opt/offline-images/mysql
cd /opt/offline-images/mysql
```

校验文件：

```bash
sha256sum -c SHA256SUMS
```

从 gzip 文件直接导入 Docker，不需要先解压到磁盘：

```bash
gzip -dc mysql-8.0.46-arm64.tar.gz | docker load
```

查看镜像：

```bash
docker images | grep mysql
```

校验镜像架构：

```bash
docker image inspect mysql:8.0.46 \
  --format 'OS={{.Os}} ARCH={{.Architecture}} TAGS={{json .RepoTags}}'
```

结果必须包含：

```text
OS=linux ARCH=arm64
```

> `docker load` 会恢复原始标签，通常为 `mysql:8.0.46`。

## 三、下载普通 URL 文件

在 Actions 手动运行时填写：

| 参数 | 示例 |
|---|---|
| mode | `url` |
| source | `https://example.com/files/package.tar.gz` |
| platform | 任意，URL 模式忽略 |
| output_name | `package.tar.gz`，也可以留空 |
| compression | 建议 `none`，避免二次压缩 |
| release_tag | 例如 `package-20260729` |
| release_title | 自定义标题 |
| publish_release | 勾选 |

工作流使用 `curl`，具备重定向跟随、失败重试、连接超时和下载错误检查。

## 四、其他 Docker 镜像示例

### ARM64 Redis

```text
mode: docker
source: redis:7.4
platform: linux/arm64/v8
output_name: redis-7.4-arm64.tar
compression: gzip
```

### AMD64 Nginx

```text
mode: docker
source: nginx:1.28
platform: linux/amd64
output_name: nginx-1.28-amd64.tar
compression: gzip
```

### ARM64 指定私有镜像

```text
mode: docker
source: registry.example.com/project/app:1.0.0
platform: linux/arm64/v8
output_name: app-1.0.0-arm64.tar
compression: gzip
```

私有镜像需要先在工作流中增加对应仓库的登录步骤，并将账号和令牌保存为 GitHub Actions Secrets。不要把密码直接写进工作流文件。

## 五、Release 标签规则

- 填写 `release_tag`：使用指定标签；
- 不填写：自动生成 `download-运行序号-尝试次数`；
- 标签已经存在：覆盖该 Release 中的同名文件；
- 标签不存在：创建新 Release。

## 六、文件说明

| 文件 | 用途 |
|---|---|
| `*.tar` / `*.tar.gz` / `*.zip` | 下载或导出的主文件 |
| `*-image-info.json` | Docker 镜像详细信息 |
| `*-README.txt` | Docker 导入命令及平台信息 |
| `SHA256SUMS` | 所有输出文件的 SHA256 校验值 |

## 七、注意事项

1. Docker 镜像模式会检查实际系统和 CPU 架构，不匹配时工作流直接失败。
2. GitHub Release 单个附件存在平台大小限制，超大文件可能无法发布。
3. 仓库为私有仓库时，下载 Release 通常需要登录有权限的 GitHub 账号。
4. Actions Artifact 默认保留 7 天；Release 文件会持续保留，直到手动删除。
5. 导入新 MySQL 镜像不等于可以直接删除旧容器，数据库升级前仍需完成数据备份、数据卷确认和回退准备。
