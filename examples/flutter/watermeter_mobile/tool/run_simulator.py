"""Run the integration fixture on an available iPhone simulator in the cloud."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    project = parser.parse_args().project.resolve()
    devices = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
    candidates = [device for runtime, group in devices["devices"].items() if "iOS" in runtime
                  for device in group if device.get("isAvailable") and "iPhone" in device["name"]]
    if not candidates:
        raise SystemExit("No iPhone simulator available; do not mark the native run as tested")
    device = next((device for device in candidates if device["state"] == "Booted"), candidates[0])
    if device["state"] != "Booted":
        subprocess.run(["xcrun", "simctl", "boot", device["udid"]], check=True)
    subprocess.run(["xcrun", "simctl", "bootstatus", device["udid"], "-b"], check=True, timeout=300)
    try:
        subprocess.run(["flutter", "test", "integration_test/app_test.dart", "-d", device["udid"],
                        "--no-pub", "--no-dds", "--reporter", "expanded", "--verbose"],
                       cwd=project, check=True, timeout=480)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logs = subprocess.run(["xcrun", "simctl", "spawn", device["udid"], "log", "show", "--last", "3m",
                               "--style", "compact", "--predicate", 'process == "Runner"'],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        print(logs.stdout[-9000:], flush=True)
        raise
    with (project / "build/ios/iphonesimulator/Runner.app/Info.plist").open("rb") as handle:
        identifier = plistlib.load(handle)["CFBundleIdentifier"]
    container = Path(subprocess.check_output(["xcrun", "simctl", "get_app_container", device["udid"], identifier, "data"], text=True).strip())
    screenshots = Path(os.environ["WM_SCREENSHOT_DIR"])
    screenshots.mkdir(parents=True, exist_ok=True)
    for name in ["demo-en", "demo-zh"]:
        images = list(container.rglob("watermeter-" + name + ".png"))
        if len(images) != 1:
            raise SystemExit("Expected one rendered simulator screenshot: " + name)
        shutil.copy2(images[0], screenshots / (name + ".png"))
