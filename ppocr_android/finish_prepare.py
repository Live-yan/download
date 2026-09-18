#!/usr/bin/env python3
"""Final compatibility checks and tests for the prepared Android tree."""
from pathlib import Path
import shutil, sys
P = Path(sys.argv[1]).resolve() / 'deploy/ppocr-android'
# Restrict localization to strings, not Compose's named parameters.
for f in (P / 'app/src/main/java').rglob('*.kt'):
    s = f.read_text().replace('on重试', 'onRetry').replace('on关闭', 'onDismiss')
    f.write_text(s)
f = P / 'app/src/main/java/com/paddle/ocr/demo/ImageLoader.kt'
s = f.read_text().replace('BitmapFactory.decodeStream(it, null, bounds) }', 'BitmapFactory.decodeStream(it, null, bounds); Unit }')
f.write_text(s)

# The test consumer uses the actual release AAR, not a project dependency.
with (P / 'settings.gradle.kts').open('a') as f: f.write('\ninclude(":sdk-check")\n')
Q = P / 'sdk-check'
Q.mkdir(exist_ok=True)
(Q / 'build.gradle.kts').write_text('''plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}
android {
    namespace = "com.liveyan.ppocr.sdkcheck"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.liveyan.ppocr.sdkcheck"
        minSdk = 26
        targetSdk = 35
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
}
dependencies {
    implementation(files("../ppocr-sdk/build/outputs/aar/ppocr-sdk-release.aar"))
    implementation(libs.onnxruntime.android)
    implementation(libs.opencv.android)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.core.ktx)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.ext.junit.ktx)
    androidTestImplementation(libs.androidx.test.monitor)
    androidTestImplementation(libs.junit)
}
''')
(Q / 'src/main').mkdir(parents=True, exist_ok=True)
(Q / 'src/main/AndroidManifest.xml').write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="SDK integration check" android:allowBackup="false" /></manifest>\n')
target = Q / 'src/androidTest/java/com/paddle/ocr/DeliverySmokeTest.kt'
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(P / 'ppocr-sdk/src/androidTest/java/com/paddle/ocr/DeliverySmokeTest.kt', target)
# Optional Gradle local override works with exported sources on other machines.
(P / 'gradle.properties').write_text('org.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\nkotlin.code.style=official\norg.gradle.workers.max=2\n')
print('Compatibility fixes and AAR consumer tests installed.')
