"""Generate Android/iOS shells with Flutter, then overlay the reviewed app source."""
import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[1]


def bootstrap(target):
    target = target.resolve()
    if target.exists() or target == SOURCE or SOURCE in target.parents:
        raise SystemExit("Choose a new build directory outside the source recipe")
    subprocess.run(["flutter", "create", "--no-pub", "--platforms=android,ios", "--org", "com.watermeterai",
                    "--project-name", "watermeter_mobile", "--empty", str(target)], check=True)
    for name in ["lib", "test", "integration_test", "test_driver"]:
        shutil.copytree(SOURCE / name, target / name, dirs_exist_ok=True)
    for name in ["pubspec.yaml", "analysis_options.yaml", "README.md", "README.zh-CN.md"]:
        shutil.copy2(SOURCE / name, target / name)
    shutil.copy2(SOURCE.parents[2] / "LICENSE", target / "LICENSE")
    android = "http://schemas.android.com/apk/res/android"
    ET.register_namespace("android", android)
    path = target / "android/app/src/main/AndroidManifest.xml"
    tree = ET.parse(path)
    permission = ET.Element("uses-permission", {"{" + android + "}name": "android.permission.INTERNET"})
    tree.getroot().insert(0, permission)
    app = tree.getroot().find("application")
    app.set("{" + android + "}label", "WaterMeter Mobile")
    app.set("{" + android + "}usesCleartextTraffic", "false")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    gradle = target / "android/app/build.gradle.kts"
    gradle.write_text(gradle.read_text().replace("minSdk = flutter.minSdkVersion", "minSdk = 24"), encoding="utf-8")
    path = target / "ios/Runner/Info.plist"
    with path.open("rb") as handle:
        info = plistlib.load(handle)
    info.update(CFBundleDisplayName="WaterMeter", CFBundleLocalizations=["en", "zh-Hans"],
                NSCameraUsageDescription="Take a water meter photo for recognition after you choose to upload it.",
                NSPhotoLibraryUsageDescription="Choose a water meter photo for recognition after you choose to upload it.")
    with path.open("wb") as handle:
        plistlib.dump(info, handle)
    for language, camera, photo in [
        ("en", "Take a water meter photo for recognition after you choose to upload it.", "Choose a water meter photo for recognition after you choose to upload it."),
        ("zh-Hans", "拍摄水表照片，由你点击识别后上传处理。", "选择水表照片，由你点击识别后上传处理。"),
    ]:
        folder = target / "ios/Runner" / (language + ".lproj")
        folder.mkdir(exist_ok=True)
        (folder / "InfoPlist.strings").write_text('"NSCameraUsageDescription" = "' + camera + '";\n"NSPhotoLibraryUsageDescription" = "' + photo + '";\n', encoding="utf-8")
    subprocess.run(["flutter", "pub", "get"], cwd=target, check=True)
    print("Native app prepared at " + str(target))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    bootstrap(parser.parse_args().target)
