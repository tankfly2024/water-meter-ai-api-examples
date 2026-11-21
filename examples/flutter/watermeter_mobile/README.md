# WaterMeter Mobile — Android and iOS preview

[简体中文](README.zh-CN.md) · [Website](https://watermeterai.com/) · [Free API key](https://watermeterai.com/en/api-keys) · [API documentation](https://watermeterai.com/en/api-docs)

Take or choose a water meter photo, call the public WaterMeter AI API, compare the result with the original, and save a separate user-confirmed reading. One Flutter codebase targets Android and iOS. Current service capabilities include pointer and mechanical digit meters; LED recognition is not promised.

**Start on [watermeterai.com](https://watermeterai.com/). [Register for free](https://watermeterai.com/en/login?flow=register), sign in, and create an API key for free.** Ordinary free accounts receive **20 recognitions per day**, shared with the website and every API client. Unused calls do not roll over; paid, custom, and cooperation policies follow your account's actual quota. This app does not grant extra allowance.

This is a **testing preview**. Cloud compilation, mock transport tests, widget tests, and an iPhone simulator workflow are the build gates. Physical camera behavior, real-account production recognition, device permissions, HEIC handling, and compatibility with real phones require separate testing. Simulator/demo results are not recognition accuracy measurements. No phone SDK or simulator needs to be installed on the repository owner's PC to run the GitHub workflow.

## Downloads and use

Open [GitHub Releases](https://github.com/tankfly2024/water-meter-ai-api-examples/releases) and choose the newest **WaterMeter Mobile** prerelease:

- `watermeter-mobile-android-debug.apk`: Android testing APK with a debug signature, not a store release. Android may require permission to install from your chosen download source.
- `watermeter-mobile-ios-simulator.zip`: unsigned iPhone simulator `.app`, for a Mac with Xcode. **Not an IPA; it cannot be installed directly on an iPhone.** TestFlight/App Store and physical-device distribution require their own signing and account setup.
- `watermeter-mobile-source.zip`: complete generated native projects plus Dart source and dependency lockfiles, ready for a developer with the required build tools.
- `demo-en.png` and `demo-zh.png`: actual simulator screenshots of the clearly marked offline illustration and preset value, not live recognition.
- `SHA256SUMS-mobile.txt`: published file integrity checksums.

The default app language is English, with a Chinese toggle. Enter your own key and press **Connect** to check quota without uploading a photo. Choose **Take photo** or **Choose photo**, inspect the preview, then press **Recognize water meter** to send it to the cloud. AI and manually confirmed readings are separate. Selecting a photo does not upload it. The offline demo works without a key and never calls the recognition API.

## Quota, persistence, and privacy

The key exists only in process memory and the masked input field; it is cleared from that field after connection and is never written to the session, source, or logs. After restarting the app, reconnect with your key. Selected pictures and returned readings are private user data. The photo picker may place photos in its OS/app cache; this app does not add copies to your photo library or store photo bytes in its task session.

Task IDs, the image digest, AI result, and manual reading are stored in the application's support directory without the key. The file is flushed before upload and replaced atomically; an incomplete/corrupt record blocks new uploads until reviewed. App backups may contain session data; it is not an encrypted secret store. Your own device and service policies apply.

A saved task can be resumed with GET requests after polling timeout or restart. An uncertain POST is never automatically repeated. Check your account's task history on the website first, then use the explicit recovery dialog only after acknowledging the check. Forgetting a local task does not cancel it in the cloud. Identical image bytes reuse the previous result rather than submit again. Quota refresh follows completed recognition, so activity in another client can make the display stale.

Supported upload formats are JPEG, PNG, and WEBP, up to 20 MB. The picker requests a resized, quality-adjusted image; if the device still returns HEIC, export it as JPEG. No unit conversion is inferred. Failed/quality-rejected AI values remain empty; a separately entered manual value is identified as the user's confirmation.

## Build locally or in the cloud

This repository contains the reviewed app source and a native-project generation recipe. The [mobile GitHub workflow](../../../.github/workflows/mobile-preview.yml) installs a pinned Flutter revision **only on hosted runners**, generates Android/iOS shells, checks the Dart code, runs tests, builds Android, and runs the mocked workflow on an iPhone simulator. A `[mobile-preview]` marker in the authorized commit message enables a prerelease after both jobs pass. It does not call production recognition or require a service API key.

With Flutter already installed, generate a **new directory outside this source recipe**:

```bash
python3 tool/bootstrap.py --target /your/new/mobile-build
cd /your/new/mobile-build
flutter analyze
flutter test
flutter build apk --debug
# On a Mac with Xcode:
flutter build ios --simulator --debug
```

The downloadable full source ZIP already contains `android/` and `ios/`; extract it, run `flutter pub get`, then the same analyze/test/build commands. The compiler, Android SDK, or Xcode must exist somewhere; the cloud workflow keeps these large tools off the user's PC. No model is bundled.
