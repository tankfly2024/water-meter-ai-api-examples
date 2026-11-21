# WaterMeter Mobile：安卓与苹果水表演示

[English](README.md) · [水表识别官网](https://watermeterai.com/zh-cn) · [免费获取API Key](https://watermeterai.com/zh-cn/api-keys) · [中文API文档](https://watermeterai.com/zh-cn/api-docs)

一个Flutter项目覆盖安卓与苹果：拍照或选择水表图片，调用水表API，对照原图核查读数，单独保存人工确认值。服务当前支持指针表、机械数字表，不承诺LED表识别。

**欢迎先到[watermeterai.com](https://watermeterai.com/zh-cn)体验识别。[免费注册](https://watermeterai.com/zh-cn/login?flow=register)并登录后，即可免费创建API Key接入手机端。普通免费账号每天20次，与官网及所有客户端共用额度，未用完不累积，特殊账号按实际额度执行。** 本应用不会额外发放次数。

这是**测试预览版**。云端实际编译、模拟API测试、界面测试及iPhone模拟器流程作为构建门槛；真实相机、生产账号识别、真机权限、HEIC照片及不同机型仍需另行实测，不能把模拟读数算作识别准确率。仓库所有者的电脑无需安装手机SDK或模拟器，编译工具放在GitHub云端。

## 下载与操作

打开[GitHub发布页](https://github.com/tankfly2024/water-meter-ai-api-examples/releases)，选择最新的 **WaterMeter Mobile** 测试预览：

- `watermeter-mobile-android-debug.apk`：安卓调试签名测试包，不是商店正式发行包。下载后按系统提示允许从相应来源安装。
- `watermeter-mobile-ios-simulator.zip`：给Mac/Xcode的iPhone模拟器使用的未签名`.app`。**不是IPA，不能直接安装到iPhone。** 真机签名、TestFlight或App Store分发需另行落实账号和证书。
- `watermeter-mobile-source.zip`：包含完整安卓/苹果原生工程、Dart源码及依赖锁文件。
- `demo-en.png`、`demo-zh.png`：在模拟器中运行本应用所得的界面截图，演示使用明确标记的示意图和预设值，不是真实云端识别案例。
- `SHA256SUMS-mobile.txt`：发行文件的完整性校验表。

默认英文，可切换中文。先输入自己的Key并连接，这一步只查额度、不上传图片。点击拍照或从相册选择，核对预览后，再点击“识别水表”上传；AI读数和人工确认值分开保留。没有Key时可以体验离线演示，不产生识别调用。

## 保存、异常与隐私

Key仅在进程内存和遮蔽输入框中，连接后清空输入框，不进入任务文件、源码或日志。重启后需重新输入Key。照片属于用户数据，系统选择器可能生成应用/系统缓存文件；本应用不另存入相册，任务记录也不保存图片字节。

任务编号、图片摘要、AI读数、人工确认值保存到应用支持目录，不含Key。上传前刷新文件并原子替换；记录损坏或未完成写入时，阻止直接重新上传。应用备份可能包含这些记录，并非加密秘密存储，请保护自己的设备和备份。

查询超时或重启后可继续GET查询已有任务，不重新上传。提交状态不确定时不自动重发，须先在官网核查任务历史；恢复对话框要求用户明确确认已经核查。清除本地任务不会取消云端任务。字节完全相同的照片复用上次结果，避免重复提交。额度在完成识别后刷新，其他客户端的使用可能使当前显示滞后。

支持20MB以内的JPEG、PNG、WEBP。选择器会请求调整图片尺寸和质量；设备仍返回HEIC时，请先导出JPEG。读数单位不自动推断或换算；质量拦截和失败不会生成有效AI值，手工填写的值明确属于人工确认。

## 构建

GitHub源码目录保存应用与原生工程生成脚本；[云端工作流](../../../.github/workflows/mobile-preview.yml)只在云端安装固定Flutter版本，生成安卓/苹果工程，运行检查、测试、安卓构建与iPhone模拟器流程。经授权的提交消息带`[mobile-preview]`时，两端任务通过后才发布预览；构建不调用生产识别API，不需要真实服务Key。

已经安装Flutter的开发者可运行：

```bash
python3 tool/bootstrap.py --target /your/new/mobile-build
cd /your/new/mobile-build
flutter analyze
flutter test
flutter build apk --debug
# 苹果端需在具备Xcode的Mac上：
flutter build ios --simulator --debug
```

生成目录必须是源码目录之外的新目录，不覆盖已有工程。下载的完整源码ZIP已含`android/`和`ios/`，可直接`flutter pub get`后执行检查与构建，无需再次生成。云端仍有实际编译环境，只是不会把大型SDK放到用户电脑上；手机端不带识别模型。
