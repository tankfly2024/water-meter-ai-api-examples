"""Run the integration fixture on an available iPhone simulator in the cloud."""
import argparse
import json
from pathlib import Path
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
    subprocess.run(["flutter", "drive", "--driver=test_driver/integration_test.dart",
                    "--target=integration_test/app_test.dart", "-d", device["udid"], "--no-pub"],
                   cwd=project, check=True, timeout=1200)
