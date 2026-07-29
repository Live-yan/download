## 按 CVE 自动下载银河麒麟补丁

新增工作流：

```text
银河麒麟 CVE 补丁打包发布
```

### 请求文件格式

在 `requests/kylin-cve/` 下新建一个 `.txt` 文件，例如 `openssh-20260729.txt`：

```text
银河麒麟高级服务器操作系统 V10 SP3 2403
CVE-2026-35386
CVE-2026-3497,CVE-2026-35414
CVE-2026-35387, CVE-2026-35388
```

规则：

1. 第一行必须是系统版本；
2. 第二行开始填写 CVE，支持换行、英文逗号或混合分隔；
3. 默认架构是 `aarch64`；也可在第一行末尾写 `| x86_64` 或 `| loongarch64`；
4. 支持 `#` 开头的注释和空行。

支持的系统名称：

```text
银河麒麟高级服务器操作系统 V10 SP3
银河麒麟高级服务器操作系统 V10 SP3 2403
银河麒麟高级服务器操作系统 V10 SP3 2309b
银河麒麟高级服务器操作系统（Host版）V10
```

### 运行方式

- 将 `.txt` 文件提交到 `main` 分支后，工作流会自动运行；
- 也可进入 Actions，手动运行工作流并指定请求文件和架构；
- 推送同一次提交中的多个请求文件时，会分别生成各自的 Release。

### 匹配与去重逻辑

- 从麒麟 UpdateInfo 元数据中查找 CVE 对应的安全公告及 RPM；
- 仅保留目标架构和 `noarch` 包；
- 同名且同架构 RPM 出现多个版本时，按 RPM `Epoch-Version-Release` 比较，只保留最高版本；
- `openssh`、`openssh-server`、`openssh-clients` 等不同子包会分别保留；
- 再从目标系统的 RPM 仓库 primary 元数据中精确确认包路径、大小和官方校验值；
- 任一 CVE 未匹配或包不属于目标仓库时，默认直接失败，避免漏包或混用系统版本。

> V10 SP3 2309b 没有独立 UpdateInfo，因此使用 V10 SP3 公告索引匹配，再到 2309B RPM 仓库逐包精确校验。校验不到时工作流会失败，不会发布结果。

### Release 内容

```text
*.tar.gz               全部 RPM、报告、清单和包内校验文件
manifest.json          机器可读的 CVE、公告、RPM、URL、校验值映射
REPORT.md              人工可读报告
SHA256SUMS              压缩包内 RPM 的 SHA256
RELEASE_SHA256SUMS      Release 各附件的 SHA256
```

下载后先执行：

```bash
sha256sum -c RELEASE_SHA256SUMS
```

解压后再执行：

```bash
tar -xzf *.tar.gz
sha256sum -c SHA256SUMS
```

工作流只负责匹配和下载补丁，不会判断目标服务器当前已安装了哪些子包，也不会自动安装。正式升级前仍应在目标服务器执行 RPM 签名检查、依赖测试、备份和回退准备。
