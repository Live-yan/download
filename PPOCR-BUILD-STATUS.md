# PP-OCRv6 tiny Android — 本次执行状态

记录日期：2026-09-18。

**当前未生成 APK 或 AAR，也未执行 Android 编译、模型推理或设备测试。不能将本分支源码或构建配置称为已验证可用的二进制交付。**

## 已写入仓库

分支：`build/ppocr-v6-tiny-android-20260918`。现有 main 分支、文件、仓库可见性、账单及权限设置均未修改。

- `ppocr_android/prepare.py`：从固定官方 PaddleOCR 提交准备 Android 工程，选择 PP-OCRv6_tiny_det/rec ONNX 模型，增加系统相机拍照、相册选图、照片方向纠正、中文入口及 SDK 生命周期保护。
- `ppocr_android/finish_prepare.py`：兼容性补丁，以及独立消费 release AAR 的 Android 仪器测试模块。
- `ppocr_android/README.md`：**预期构建产物**的说明及集成方式。文中列出的 APK、SDK ZIP、报告文件是成功执行工作流后才会产生的文件，并不表示当前已经存在。
- `.github/workflows/ppocr-v6-tiny-android.yml`：构建 APK/AAR、导出依赖、打包源码、检查签名及 ELF 对齐，并执行 Android 模拟器推理测试的配置。
- `.github/workflows/ppocr-runner-probe.yml`：无第三方 Action 的最小运行器诊断任务。

以上是已提交的实现和构建配方，尚未经编译或设备验证。源码基线：`PaddlePaddle/PaddleOCR@dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`。

## 实际运行结果

### 正式构建

https://github.com/Live-yan/download/actions/runs/35308843597

已执行两次尝试，均以 failure 结束。首次 job ID：`105486479619`；第二次：`105486969681`。首次任务元数据显示 `steps: []`、`runner_id: 0`、空 runner 名称。没有可读取的构建日志，Actions artifacts 列表为空。

### 最小诊断

https://github.com/Live-yan/download/actions/runs/35309047892

job ID：`105487085808`。此工作流没有任何 `uses:` 步骤，仅准备执行 shell 命令，仍在启动前失败；任务元数据显示 `steps: []`、`runner_id: 0`、空 runner 名称。

因此，当前可确定的问题是 **GitHub 托管任务未启动/未分配运行器**，不是已经观察到的 Kotlin、Gradle 或 OCR 模型错误。检查记录存在一条 annotation，但本次连接器无法读取该独立 annotations 端点，无法确定具体账户级原因。不要仅凭本记录断言账户欠费、额度耗尽或某个策略设置错误。

本地执行环境也没有可用的 Android SDK/Gradle 依赖，网络解析无法下载这些依赖，因此没有本地编译产物可以替代。

## 恢复构建所需条件

打开上述失败任务的 Summary / Annotations，按 GitHub 给出的实际错误处理运行器启动问题。可能需要检查 Actions 使用额度/预算、执行策略或运行器可用性，但具体原因尚未验证；本次没有修改账户计费或安全配置。

运行器恢复后，可对正式构建任务选择 Re-run all jobs，或在本分支修改 `ppocr_android/` 下文件触发新构建。恢复运行器不等于保证源码首次编译成功，仍需检查实际编译日志并修正问题，完成 AAR 推理和 APK 启动测试后才能称为已验证交付。

预期成功产物名称：`ppocr-v6-tiny-android-<run_number>`。其中 APK 使用测试证书签名，不是生产发布密钥。Android 支持范围计划为 API 26+；相机功能为拍照后 OCR，不是视频流逐帧识别。16 KB 对齐报告及模拟器结果必须实际执行后才能确认。
