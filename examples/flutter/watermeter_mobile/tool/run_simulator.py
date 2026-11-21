"""Run the integration fixture on an available iPhone simulator in the cloud."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import signal
import subprocess
import time


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    project = parser.parse_args().project.resolve()
    devices = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
    candidates = [dict(device, runtime=runtime) for runtime, group in devices["devices"].items() if "iOS" in runtime
                  for device in group if device.get("isAvailable") and "iPhone" in device["name"]]
    if not candidates:
        raise SystemExit("No iPhone simulator available; do not mark the native run as tested")
    # The hosted macOS 26 image stalled in CoreLocation data migration before
    # launching our app. Prefer the installed iOS 18 runtime on macOS 15.
    stable = [device for device in candidates if "iOS-18-" in device["runtime"]]
    candidates = sorted(stable or candidates, key=lambda item: tuple(
        int(part) for part in re.findall(r"\d+", item["runtime"])), reverse=True)
    device = next((device for device in candidates if device["state"] == "Booted"), candidates[0])
    print("Simulator: " + device["name"] + " / " + device["runtime"], flush=True)
    if device["state"] != "Booted":
        subprocess.run(["xcrun", "simctl", "boot", device["udid"]], check=True)
    subprocess.run(["xcrun", "simctl", "bootstatus", device["udid"], "-b"], check=True, timeout=300)
    # Execute the same integration_test assertions inside the installed app.
    # Collect its completed test results without Flutter's stalled VM-port log
    # discovery. A missing, failing, or incomplete receipt fails the CI job.
    subprocess.run(["flutter", "build", "ios", "--simulator", "--debug", "--no-pub",
                    "--target", "integration_test/app_test.dart",
                    "--dart-define=INTEGRATION_TEST_SHOULD_REPORT_RESULTS_TO_NATIVE=false"],
                   cwd=project, check=True, timeout=600)
    app = project / "build/ios/iphonesimulator/Runner.app"
    with (project / "build/ios/iphonesimulator/Runner.app/Info.plist").open("rb") as handle:
        identifier = plistlib.load(handle)["CFBundleIdentifier"]
    subprocess.run(["xcrun", "simctl", "install", device["udid"], str(app)], check=True, timeout=120)
    container = Path(subprocess.check_output(["xcrun", "simctl", "get_app_container", device["udid"], identifier, "data"], text=True).strip())
    log_path = project / "build/simulator-fixture-console.txt"
    receipt = None
    with log_path.open("w") as console:
        process = subprocess.Popen(["xcrun", "simctl", "launch", "--console-pty", device["udid"], identifier],
                                   stdout=console, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                matches = list(container.rglob("watermeter-native-check.json"))
                if len(matches) == 1:
                    try:
                        receipt = json.loads(matches[0].read_text())
                        break
                    except json.JSONDecodeError:
                        pass
                if process.poll() is not None:
                    break
                time.sleep(2)
        finally:
            subprocess.run(["xcrun", "simctl", "terminate", device["udid"], identifier],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
    if receipt is None or receipt.get("passed") is not True or len(receipt.get("tests", [])) != 1:
        print(log_path.read_text(errors="replace")[-12000:], flush=True)
        if receipt is not None:
            print(json.dumps(receipt), flush=True)
        raise SystemExit("Native integration assertions did not pass; no mobile release")
    screenshots = Path(os.environ["WM_SCREENSHOT_DIR"])
    screenshots.mkdir(parents=True, exist_ok=True)
    for name in ["demo-en", "demo-zh"]:
        images = list(container.rglob("watermeter-" + name + ".png"))
        if len(images) != 1:
            raise SystemExit("Expected one rendered simulator screenshot: " + name)
        shutil.copy2(images[0], screenshots / (name + ".png"))
    print("::notice title=iPhone simulator assertions::" + json.dumps(receipt), flush=True)
