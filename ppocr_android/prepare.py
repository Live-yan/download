#!/usr/bin/env python3
"""Prepare the pinned official PaddleOCR Android project. Apache-2.0."""
from pathlib import Path
import hashlib, json, re, shutil, sys, tarfile, time, urllib.request

ROOT = Path(sys.argv[1]).resolve()
P = ROOT / 'deploy/ppocr-android'
UPSTREAM = 'dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf'

def write(path, text):
    target = P / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')

def patch(path, old, new, count=None):
    target = P / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Pinned source mismatch: {path}: {old[:70]}')
    if count is not None and text.count(old) != count:
        raise RuntimeError(f'Unexpected patch count: {path}')
    target.write_text(text.replace(old, new), encoding='utf-8')

# Use the official Maven repositories, and a recent official OpenCV AAR.
settings = P / 'settings.gradle.kts'
settings.write_text('\n'.join(line for line in settings.read_text().splitlines() if 'maven.aliyun.com' not in line) + '\n')
patch('gradle/libs.versions.toml', 'opencv = "4.5.3"', 'opencv = "4.12.0"')
patch('gradle/libs.versions.toml', 'group = "com.quickbirdstudios", name = "opencv"', 'group = "org.opencv", name = "opencv"')
patch('gradle/libs.versions.toml', 'test-runner = "1.2.0"', 'test-runner = "1.6.2"')
patch('app/build.gradle.kts', 'applicationId = "com.paddle.ocr.demo"', 'applicationId = "com.liveyan.ppocr.tiny"')
patch('app/build.gradle.kts', 'versionName = "1.0.0"', 'versionName = "6.0.0-tiny-20260918"')
patch('app/build.gradle.kts', 'isMinifyEnabled = true', 'isMinifyEnabled = false\n            signingConfig = signingConfigs.getByName("debug")')
patch('app/build.gradle.kts', '    buildTypes {', '''    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "armeabi-v7a", "x86_64")
            isUniversalApk = true
        }
    }
    packaging {
        jniLibs.useLegacyPackaging = false
    }
    buildTypes {''')
patch('app/build.gradle.kts', 'dependencies {', '''dependencies {
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")''')
write('app/proguard-rules.pro', '-keep class ai.onnxruntime.** { *; }\n-keep class org.opencv.** { *; }\n')
# Include API protection rules for consuming apps that use R8.
write('ppocr-sdk/proguard-rules.pro', '-keep class com.paddle.ocr.** { *; }\n-keep class ai.onnxruntime.** { *; }\n-keep class org.opencv.** { *; }\n')

# Make the public SDK initialize its own native dependencies, serialize calls,
# and reject inference after release. No changes to the recognition algorithm.
patch('ppocr-sdk/src/main/java/com/paddle/ocr/engine/OCREngine.kt', '    init {', '''    init {
        check(com.paddle.ocr.util.OpenCVUtils.init(context)) { "OpenCV native library could not be loaded" }''', 1)
patch('ppocr-sdk/src/main/java/com/paddle/ocr/util/OpenCVUtils.kt', '    fun init(context: Context): Boolean {', '    @Synchronized\n    fun init(context: Context): Boolean {')
api = 'ppocr-sdk/src/main/java/com/paddle/ocr/PaddleOCR.kt'
patch(api, 'import kotlinx.coroutines.withContext', 'import kotlinx.coroutines.withContext\nimport kotlinx.coroutines.sync.Mutex\nimport kotlinx.coroutines.sync.withLock')
patch(api, '    /** Time spent loading', '    private val operationMutex = Mutex()\n    private var released = false\n\n    /** Time spent loading')
patch(api, '            val result = runEngine()', '            operationMutex.withLock {\n            check(!released) { "PaddleOCR has been released" }\n            val result = runEngine()')
patch(api, '                perLineRecMs = result.perLineRecMs,\n            )', '                perLineRecMs = result.perLineRecMs,\n            )\n            }')
patch(api, '            engine.release()', '            operationMutex.withLock {\n                if (!released) { engine.release(); released = true }\n            }')

# Restrict the FileProvider to a private capture directory. System camera intents
# do not require the app to request CAMERA or broad storage permissions.
manifest = P / 'app/src/main/AndroidManifest.xml'
s = manifest.read_text()
s = re.sub(r'\s*<uses-permission[^>]+/\s*>', '', s)
s = s.replace('<application', '<uses-feature android:name="android.hardware.camera.any" android:required="false" />\n    <application', 1)
s = re.sub(r'android:allowBackup="[^"]+"', 'android:allowBackup="false"', s)
s = s.replace('</application>', '''    <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>
    </application>''')
manifest.write_text(s)
write('app/src/main/res/xml/file_paths.xml', '''<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <cache-path name="captures" path="captures/" />
</paths>
''')
write('app/src/main/res/values/strings.xml', '<resources><string name="app_name">轻量文字识别</string></resources>\n')

home = 'app/src/main/java/com/paddle/ocr/demo/ui/screen/HomeScreen.kt'
patch(home, 'import androidx.activity.compose.rememberLauncherForActivityResult', '''import android.net.Uri
import android.widget.Toast
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.FileProvider
import java.io.File
import androidx.activity.compose.rememberLauncherForActivityResult''')
patch(home, '    Column(modifier = Modifier.fillMaxSize()) {', '''    val context = LocalContext.current
    var pendingPhoto by rememberSaveable { mutableStateOf<String?>(null) }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val path = pendingPhoto
        pendingPhoto = null
        if (path != null) {
            val file = File(path)
            if (success && file.length() > 0) {
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
                viewModel.onImageSelected(uri, file)
            } else {
                file.delete()
            }
        }
    }
    val takePhoto: () -> Unit = {
        try {
            val dir = File(context.cacheDir, "captures").apply { mkdirs() }
            dir.listFiles()?.filter { System.currentTimeMillis() - it.lastModified() > 86_400_000L }?.forEach { it.delete() }
            val file = File.createTempFile("capture_", ".jpg", dir)
            pendingPhoto = file.absolutePath
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            cameraLauncher.launch(uri)
        } catch (e: Exception) {
            pendingPhoto?.let { File(it).delete() }
            pendingPhoto = null
            Toast.makeText(context, "无法打开相机：${e.message}", Toast.LENGTH_LONG).show()
        }
    }
    Column(modifier = Modifier.fillMaxSize()) {''', 1)
patch(home, '                        onSampleClick =', '                        onCameraClick = takePhoto,\n                        onSampleClick =', 2)
picker = 'app/src/main/java/com/paddle/ocr/demo/ui/component/ImagePicker.kt'
patch(picker, '    onGalleryClick: () -> Unit,', '    onGalleryClick: () -> Unit,\n    onCameraClick: () -> Unit,')
patch(picker, '        if (sampleImages.isNotEmpty()) {', '''        Spacer(modifier = Modifier.height(8.dp))
        Button(onClick = onCameraClick) { Text("拍照识别") }
        Spacer(modifier = Modifier.height(12.dp))
        Text("PP-OCRv6 tiny · 离线识别", style = MaterialTheme.typography.titleMedium)
        Text("图片仅在本机处理，不上传服务器", style = MaterialTheme.typography.bodySmall)
        if (sampleImages.isNotEmpty()) {''')

# Decode a bounded, correctly oriented software bitmap. Inference and preview
# use that exact bitmap, so bounding boxes use the same coordinate system.
write('app/src/main/java/com/paddle/ocr/demo/ImageLoader.kt', '''// SPDX-License-Identifier: Apache-2.0
package com.paddle.ocr.demo

import android.content.ContentResolver
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.graphics.Matrix
import android.net.Uri
import android.os.Build
import androidx.exifinterface.media.ExifInterface
import kotlin.math.roundToInt

object ImageLoader {
    fun load(resolver: ContentResolver, uri: Uri, maxSide: Int = 2048): Bitmap {
        require(maxSide > 0)
        if (Build.VERSION.SDK_INT >= 28) {
            return ImageDecoder.decodeBitmap(ImageDecoder.createSource(resolver, uri)) { decoder, info, _ ->
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                val ratio = minOf(1.0, maxSide.toDouble() / maxOf(info.size.width, info.size.height))
                decoder.setTargetSize(maxOf(1, (info.size.width * ratio).roundToInt()), maxOf(1, (info.size.height * ratio).roundToInt()))
            }
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            ?: error("无法读取图片")
        require(bounds.outWidth > 0 && bounds.outHeight > 0) { "不支持或已损坏的图片" }
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > maxSide * 2) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample; inPreferredConfig = Bitmap.Config.ARGB_8888 }
        var bitmap = resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
            ?: error("图片解码失败")
        val orientation = resolver.openInputStream(uri)?.use {
            ExifInterface(it).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
        } ?: ExifInterface.ORIENTATION_NORMAL
        val matrix = Matrix().apply {
            when (orientation) {
                ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> setScale(-1f, 1f)
                ExifInterface.ORIENTATION_ROTATE_180 -> setRotate(180f)
                ExifInterface.ORIENTATION_FLIP_VERTICAL -> setScale(1f, -1f)
                ExifInterface.ORIENTATION_TRANSPOSE -> { setRotate(90f); postScale(-1f, 1f) }
                ExifInterface.ORIENTATION_ROTATE_90 -> setRotate(90f)
                ExifInterface.ORIENTATION_TRANSVERSE -> { setRotate(-90f); postScale(-1f, 1f) }
                ExifInterface.ORIENTATION_ROTATE_270 -> setRotate(-90f)
            }
        }
        val ratio = minOf(1f, maxSide.toFloat() / maxOf(bitmap.width, bitmap.height))
        matrix.postScale(ratio, ratio)
        if (!matrix.isIdentity) {
            val changed = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            if (changed !== bitmap) bitmap.recycle()
            bitmap = changed
        }
        return bitmap
    }
}
''')
vm = P / 'app/src/main/java/com/paddle/ocr/demo/ui/viewmodel/OCRViewModel.kt'
s = vm.read_text()
a = s.index('    fun onImageSelected(uri: Uri) {')
b = s.index('    fun onSampleImageClicked', a)
s = s[:a] + '''    private var selecting = false

    fun onImageSelected(uri: Uri, captureFile: java.io.File? = null) {
        if (selecting || _uiState.value is UIState.Processing) { captureFile?.delete(); return }
        selecting = true
        viewModelScope.launch {
            try {
                val bitmap = withContext(Dispatchers.IO) {
                    com.paddle.ocr.demo.ImageLoader.load(OCRApplication.instance.contentResolver, uri)
                }
                processImageBytes(byteArrayOf(), bitmap)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                _uiState.value = UIState.Error(e.message ?: "图片加载失败")
            } finally {
                captureFile?.delete()
                selecting = false
            }
        }
    }

''' + s[b:]
s = s.replace('val result = ocr.recognize(bytes)', 'val result = ocr.recognize(bitmap)')
vm.write_text(s)
# Bound detector input; text crops retain up to 2048-pixel source resolution.
patch('app/src/main/java/com/paddle/ocr/demo/OCRApplication.kt', '                        recScoreThresh = 0.0f,', '''                        detLimitSideLen = 1280,
                        detLimitType = "max",
                        detMaxSideLimit = 1280,
                        recScoreThresh = 0.3f,''')
translations = {
    'Select from Gallery': '从相册选择图片',
    'Loading OCR models...': '正在加载离线模型…',
    'Processing...': '正在识别文字…',
    'Error occurred': '处理失败',
    'Copy All': '复制全部文字',
    'Copy all': '复制全部文字',
    'No text detected': '未检测到文字，请换一张清晰图片',
    'Retry': '重试',
    'Dismiss': '关闭',
    'PP-OCRv6 Demo': '轻量文字识别',
}
for f in (P / 'app/src/main/java').rglob('*.kt'):
    text = f.read_text()
    for old, new in translations.items(): text = text.replace(old, new)
    f.write_text(text)

# Fetch only regular files from the official model archives (never extract paths).
provenance = {'upstream_commit': UPSTREAM, 'model_family': 'PP-OCRv6_tiny', 'models': {}}
for kind in ('det', 'rec'):
    url = f'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv6_tiny_{kind}_onnx_infer.tar'
    archive = ROOT.parent / f'PP-OCRv6_tiny_{kind}.tar'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as out:
                shutil.copyfileobj(response, out)
            break
        except Exception:
            if attempt == 2: raise
            time.sleep(3)
    target = P / f'ppocr-sdk/src/main/assets/models/{kind}'
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if not member.isfile() or name in ('', '.', '..'): continue
            if member.size > 512 * 1024 * 1024: raise RuntimeError('Unexpected model size')
            if name in files: raise RuntimeError('Duplicate model filename')
            data = tar.extractfile(member).read()
            (target / name).write_bytes(data)
            files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    if not (target / 'inference.onnx').is_file(): raise RuntimeError('ONNX missing')
    if kind == 'rec' and not (target / 'inference.yml').is_file(): raise RuntimeError('Character dictionary missing')
    provenance['models'][kind] = {'url': url, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': files}
(P / 'MODEL_PROVENANCE.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + '\n')
shutil.copy(ROOT / 'LICENSE', P / 'LICENSE')

# Export all resolved SDK runtime AAR/JAR dependencies for an offline fileTree integration.
with (P / 'ppocr-sdk/build.gradle.kts').open('a') as f:
    f.write('''

tasks.register("exportSdkDependencies") {
    doLast {
        val destination = rootProject.layout.projectDirectory.dir("dist/sdk/libs").asFile
        destination.mkdirs()
        val artifacts = configurations.getByName("releaseRuntimeClasspath").resolvedConfiguration.resolvedArtifacts
        val coordinates = mutableListOf<String>()
        artifacts.forEach { artifact ->
            artifact.file.copyTo(java.io.File(destination, artifact.file.name), overwrite = true)
            coordinates.add(artifact.moduleVersion.id.toString() + " -> " + artifact.file.name)
        }
        java.io.File(destination.parentFile, "DEPENDENCIES.txt").writeText(coordinates.sorted().joinToString("\\n"))
    }
}
''')

# Device tests exercise actual model inference, PNG input, blank input, native
# initialization, and lifecycle. Run only this class, not the benchmark suite.
write('ppocr-sdk/src/androidTest/java/com/paddle/ocr/DeliverySmokeTest.kt', '''// SPDX-License-Identifier: Apache-2.0
package com.paddle.ocr

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream

@RunWith(AndroidJUnit4::class)
class DeliverySmokeTest {
    @Test fun actualTinyModelInferenceAndLifecycle() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val bitmap = Bitmap.createBitmap(1000, 320, Bitmap.Config.ARGB_8888)
        Canvas(bitmap).apply {
            drawColor(Color.WHITE)
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.BLACK; textSize = 96f; typeface = Typeface.create("sans-serif", Typeface.BOLD)
            }
            drawText("HELLO 2026", 40f, 150f, paint)
            paint.textSize = 64f
            drawText("文字识别测试", 40f, 260f, paint)
        }
        val ocr = PaddleOCR.create(context, PaddleOCRConfig(detLimitSideLen = 1280, detLimitType = "max", detMaxSideLimit = 1280))
        try {
            val result = ocr.recognize(bitmap)
            val text = result.results.joinToString(" ") { it.text }
            android.util.Log.i("DeliverySmokeTest", "BITMAP_RESULT: $text")
            assertTrue("Expected HELLO: $text", text.uppercase().contains("HELLO"))
            assertTrue("Expected 2026: $text", text.contains("2026"))
            assertTrue("Expected Chinese text: $text", text.contains("文字"))
            val bytes = ByteArrayOutputStream().use { out -> bitmap.compress(Bitmap.CompressFormat.PNG, 100, out); out.toByteArray() }
            val fromBytes = ocr.recognize(bytes).results.joinToString(" ") { it.text }
            assertEquals(text, fromBytes)
            val blank = Bitmap.createBitmap(512, 512, Bitmap.Config.ARGB_8888)
            Canvas(blank).drawColor(Color.WHITE)
            try { assertTrue(ocr.recognize(blank).results.isEmpty()) } finally { blank.recycle() }
        } finally { ocr.release(); bitmap.recycle() }
        ocr.release()
        val another = Bitmap.createBitmap(32, 32, Bitmap.Config.ARGB_8888)
        try {
            var rejected = false
            try { ocr.recognize(another) } catch (e: IllegalStateException) { rejected = true }
            assertTrue("Inference after release must be rejected", rejected)
        } finally { another.recycle() }
    }
}
''')

print(json.dumps(provenance, indent=2, ensure_ascii=False))
print('Prepared:', P)
