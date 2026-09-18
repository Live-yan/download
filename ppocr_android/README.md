# PP-OCRv6 tiny Android 交付

本工程使用 PaddlePaddle 官方 **PP-OCRv6_tiny_det + PP-OCRv6_tiny_rec ONNX 模型**，不是 PP-OCRv5，也不是 PaddleOCR-VL。官方 Android 基线固定为 `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`。

## APK

- Android 8.0 / API 26 起；优先安装 `ppocr-v6-tiny-arm64-v8a.apk`。`universal` 包体更大，适用于多种 CPU 架构。
- 从相册/系统图片选择器读取图片；调用系统相机拍照后识别。**不是摄像头视频逐帧实时 OCR**。
- 检测与识别模型内置，首次启动不下载模型。没有联网权限，不使用云端服务或 API Key。
- 中文入口、图片预览、文字结果、识别耗时和复制全文。照片按 EXIF 方向处理；用于识别的图片最长边不超过 2048，检测输入最长边 1280。
- 拍摄文件只写入应用私有缓存，经解码识别后删除；过期缓存再次打开相机时清理。相册原文件不修改。
- 相册不索取整个图库/存储权限。相机使用 Android 系统相机应用的临时 URI 授权，因此本应用不直接索取 CAMERA 权限。
- APK 为 **release 配置、测试证书签名**，可侧载安装；不是你自己的正式发布证书。不要直接当作已完成商店上架的正式发行包。后续不同构建的测试签名可能不同，覆盖安装失败时需卸载旧包。校验签名见 `APK_CERTIFICATE.txt`。

## SDK

`ppocr-v6-tiny-sdk.aar` 为标准 Android AAR，包含 SDK 类及模型、字典；**不把 ONNX Runtime/OpenCV 塞成 fat AAR**。`sdk/libs/` 同时提供本次解析出的运行时依赖归档，版本见 `DEPENDENCIES.txt`。新项目推荐用 Maven 坐标解析传递依赖，避免现有项目出现重复类。

```kotlin
// app/build.gradle.kts; JDK 17，Kotlin 2.1.0，compileSdk 35，minSdk 26
android { defaultConfig { minSdk = 26 } }
dependencies {
    implementation(files("libs/ppocr-v6-tiny-sdk.aar"))
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.21.1")
    implementation("org.opencv:opencv:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("androidx.core:core-ktx:1.15.0")
}
```

```kotlin
import com.paddle.ocr.PaddleOCR
import com.paddle.ocr.PaddleOCRConfig

// 在协程中调用；输入为已经按 EXIF 纠正方向的普通 Bitmap。
val ocr = PaddleOCR.create(
    context = applicationContext,
    config = PaddleOCRConfig(
        detLimitSideLen = 1280,
        detLimitType = "max",
        detMaxSideLimit = 1280,
        recScoreThresh = 0.3f,
    ),
)
try {
    val result = ocr.recognize(bitmap)
    val text = result.results.joinToString("\n") { it.text }
    result.results.forEach { item ->
        println("${item.text} | ${item.confidence} | ${item.box.points}")
    }
    println(text)
} finally {
    ocr.release()
}
```

通常复用一个 OCR 实例，不要每张图片重新加载模型。SDK 自动初始化原生库，同一实例的推理/释放操作串行化；释放可重复调用，释放后识别会报错。SDK 返回检测框、文字和置信度；相册与拍照 UI 属于 app 模块，不属于 AAR 的界面 API。ByteArray 重载也可用；照片方向处理参考 `ImageLoader.kt`。

完全离线构建时，可使用归档中的依赖文件配置本地仓库或 flat-file 依赖。不要既把所有归档放进 `fileTree`，又通过 Maven 重复添加同一批库；已有项目需统一 Kotlin/AndroidX 依赖。

## 源码与构建

GitHub Actions 在独立分支执行，不覆盖 main。`prepare.py` + `finish_prepare.py` 从固定官方源码生成完整 Android 工程；`ppocr-v6-tiny-source.zip` 包含最终实际编译的工程、内置模型、测试、Gradle 配置和许可证。

导入源码后，先配置本机 Android SDK 的 `local.properties`，使用 JDK 17、Gradle 8.9：

```bash
gradle :ppocr-sdk:assembleRelease :app:assembleRelease
gradle :sdk-check:connectedDebugAndroidTest
```

`sdk-check` 是一个独立消费实际 release AAR 的测试模块。不是直接对源码模块做替代测试。

## 校验与限制

- `MODEL_PROVENANCE.json`：官方模型下载地址、固定源码提交、模型文件字节数及 SHA-256。
- `SHA256SUMS.txt`：交付文件校验值。
- `NATIVE_ALIGNMENT.json`：64 位 .so ELF 装载段对齐检查；以该报告为准，不能把编译成功等同于 16 KB 真机测试。
- `validation/`：实际执行的 Android 仪器测试结果、日志和应用启动截图。测试包括中英文合成图片真实推理、PNG 字节输入、空白图和释放后调用。
- 模拟器验证不能替代各厂商真机相机、全部图片格式、复杂版面准确率或性能验收。未执行的检查不得视为通过。
- OCR 不保证每字正确；小字号、运动模糊、密集页面、手写和弯曲文本需自行校验；这不是文档版面分析/表格结构恢复的大模型。

## 来源与许可

官方部署说明：https://www.paddleocr.ai/main/version3.x/inference_deployment/cross_platform/android_deployment.html
官方源码：https://github.com/PaddlePaddle/PaddleOCR
PaddleOCR 及本次附加代码遵循 Apache-2.0；保留源文件版权。ONNX Runtime、OpenCV、AndroidX、Kotlin/Coroutines 等第三方依赖保留各自许可证。模型来源及哈希记录在交付清单中。此为基于官方工程的定制构建，不是 PaddlePaddle 官方签名发行版。
