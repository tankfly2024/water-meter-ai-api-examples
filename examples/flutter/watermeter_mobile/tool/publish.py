"""Package a simulator app/source, or publish successful cloud mobile builds."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = "tankfly2024/water-meter-ai-api-examples"


def bundles(project, output):
    output.mkdir(parents=True, exist_ok=True)
    app = project / "build/ios/iphonesimulator/Runner.app"
    if not app.is_dir():
        raise SystemExit("The iOS simulator app was not built")
    with zipfile.ZipFile(output / "watermeter-mobile-ios-simulator.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                archive.write(path, "WaterMeter.app/" + path.relative_to(app).as_posix())
    excluded = {"build", ".dart_tool", ".git", ".idea", "Pods", ".symlinks", "ephemeral", ".gradle", "xcuserdata"}
    excluded_files = {"local.properties", "Generated.xcconfig", "flutter_export_environment.sh", ".flutter-plugins-dependencies"}
    with zipfile.ZipFile(output / "watermeter-mobile-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project.rglob("*")):
            relative = path.relative_to(project)
            if path.is_file() and not (set(relative.parts) & excluded) and path.name not in excluded_files:
                if path.suffix in {".jks", ".keystore", ".p12", ".mobileprovision"} or path.name.startswith(".env"):
                    raise SystemExit("Private file in source build directory")
                archive.write(path, "watermeter_mobile/" + relative.as_posix())


def publish(output):
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise SystemExit("Publication requires the approved GitHub workflow")
    required = ["watermeter-mobile-android-debug.apk", "watermeter-mobile-ios-simulator.zip", "watermeter-mobile-source.zip"]
    if any(not (output / name).is_file() for name in required):
        raise SystemExit("Both platform outputs and full source are required")
    assets = [output / name for name in required]
    assets.extend(sorted((output / "screenshots").glob("demo-*.png")))
    metadata = [{"name": path.name, "bytes": path.stat().st_size,
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in assets]
    (output / "SHA256SUMS-mobile.txt").write_bytes("".join(item["sha256"] + "  " + item["name"] + "\n" for item in metadata).encode())
    assets.append(output / "SHA256SUMS-mobile.txt")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    tag = "mobile-preview-" + stamp + "-" + os.environ["GITHUB_SHA"][:7]
    token = os.environ["GITHUB_TOKEN"]
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    def request(method, url, payload=None, mime="application/json"):
        if urllib.parse.urlsplit(url).hostname not in {"api.github.com", "uploads.github.com"}:
            raise RuntimeError("Unexpected API host")
        data = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        req = urllib.request.Request(url, method=method, data=data, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "User-Agent": "WaterMeter-mobile-preview", "Content-Type": mime, "X-GitHub-Api-Version": "2026-03-10"})
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=180) as response: return json.load(response)
        except urllib.error.HTTPError as error:
            status = error.code; error.close()
            raise RuntimeError("GitHub release request failed (HTTP " + str(status) + ")") from None
    endpoint = "https://api.github.com/repos/" + REPOSITORY + "/releases"
    existing = request("GET", endpoint + "?per_page=100")
    if any(item["tag_name"] == tag for item in existing):
        raise SystemExit("A release for this commit already exists; no assets overwritten")
    body = """## WaterMeter Mobile 0.1.0 — Android and iOS testing preview

Visit [watermeterai.com](https://watermeterai.com/) to try water meter recognition. [Register for free](https://watermeterai.com/en/login?flow=register), then [create an API key for free](https://watermeterai.com/en/api-keys). Ordinary free accounts include **20 recognitions per day**, shared with the website and all clients; actual account policies apply.

中文：访问[水表识别官网](https://watermeterai.com/zh-cn)，免费注册并登录后即可[免费创建API Key](https://watermeterai.com/zh-cn/api-keys)。普通免费账号每天20次，与官网及所有工具共用额度，特殊账号按实际政策执行。

- **Android APK:** debug-signed testing build, not a Google Play release. Native camera and physical-device permissions still need device testing.
- **iOS ZIP:** unsigned **iPhone simulator .app**, for a Mac with Xcode. It is **not an IPA and cannot be installed directly on an iPhone**. Device signing and App Store/TestFlight distribution are not included.
- **Source ZIP:** generated native Android/iOS projects, Dart source, dependency lockfiles, and tests. Flutter/Android/Xcode tools ran in the cloud, not on the user's PC.
- **Screenshots:** actual simulator screenshots of the explicitly marked offline demo, with preset values. They are not production recognition evidence.

Shared flow: select/capture photo → explicitly upload to the public API → inspect AI result → save a separate user-confirmed reading. API keys stay in process memory; the local session stores task IDs and readings without keys or photo bytes. Unknown uploads are never automatically repeated; review website history before clearing them. JPEG/PNG/WEBP up to 20 MB; HEIC may require JPEG export.

Automated mock API/widget tests and simulator integration run passed before this release. Production API recognition requires a dedicated account/key and is not claimed as verified. See [English instructions](https://github.com/tankfly2024/water-meter-ai-api-examples/tree/main/examples/flutter/watermeter_mobile) or [中文说明](https://github.com/tankfly2024/water-meter-ai-api-examples/blob/main/examples/flutter/watermeter_mobile/README.zh-CN.md).
"""
    release = request("POST", endpoint, {"tag_name": tag, "target_commitish": os.environ["GITHUB_SHA"],
        "name": "WaterMeter Mobile 0.1.0 — Android and iOS preview", "body": body,
        "draft": True, "prerelease": True, "make_latest": "false"})
    upload = release["upload_url"].split("{")[0]
    for path in assets:
        mime = "image/png" if path.suffix == ".png" else "application/octet-stream"
        request("POST", upload + "?" + urllib.parse.urlencode({"name": path.name}), path.read_bytes(), mime)
    public = request("PATCH", endpoint + "/" + str(release["id"]), {"draft": False, "prerelease": True, "make_latest": "false"})
    print(json.dumps({"release": public["html_url"], "assets": metadata}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.build_only:
        bundles(arguments.project.resolve(), arguments.output.resolve())
    else:
        publish(arguments.output.resolve())
