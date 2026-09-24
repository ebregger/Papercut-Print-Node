$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$javaHome = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { 'C:\Program Files\Android\Android Studio\jbr' }
$env:JAVA_HOME = $javaHome
$tools = Join-Path $sdk 'build-tools\35.0.0'
$platform = Join-Path $sdk 'platforms\android-35\android.jar'
$project = Join-Path $PSScriptRoot '..\android\multicast-helper'
$build = Join-Path $project 'build'
New-Item -ItemType Directory -Force (Join-Path $build 'classes') | Out-Null

$sources = @(Get-ChildItem (Join-Path $project 'src') -Recurse -Filter '*.java' | ForEach-Object FullName)
& (Join-Path $javaHome 'bin\javac.exe') -source 8 -target 8 -Xlint:-options -cp $platform -d (Join-Path $build 'classes') $sources
$classes = @(Get-ChildItem (Join-Path $build 'classes') -Recurse -Filter '*.class' | ForEach-Object FullName)
& (Join-Path $tools 'd8.bat') --lib $platform --output $build $classes
& (Join-Path $tools 'aapt.exe') package -f -M (Join-Path $project 'AndroidManifest.xml') -I $platform -F (Join-Path $build 'unsigned.apk') --min-sdk-version 26 --target-sdk-version 32
Push-Location $build
try { & (Join-Path $tools 'aapt.exe') add unsigned.apk classes.dex } finally { Pop-Location }
& (Join-Path $tools 'zipalign.exe') -f 4 (Join-Path $build 'unsigned.apk') (Join-Path $build 'aligned.apk')
$key = Join-Path $build 'debug.keystore'
if (!(Test-Path $key)) {
  & (Join-Path $javaHome 'bin\keytool.exe') -genkeypair -keystore $key -storepass android -keypass android -alias debug -dname 'CN=PaperCut Printer Discovery' -keyalg RSA -validity 3650 -noprompt
}
$apk = Join-Path $build 'multicast-helper.apk'
& (Join-Path $tools 'apksigner.bat') sign --ks $key --ks-pass pass:android --out $apk (Join-Path $build 'aligned.apk')
& (Join-Path $tools 'apksigner.bat') verify $apk
Write-Output $apk
