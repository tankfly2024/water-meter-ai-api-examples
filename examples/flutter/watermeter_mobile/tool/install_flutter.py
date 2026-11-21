"""Install the reviewed Flutter revision in a GitHub runner, never on the user's PC."""
import os
from pathlib import Path
import subprocess

FLUTTER_REVISION = "ae9b586f34a8443573f82ef57c3bf914a908cbf7"

if __name__ == "__main__":
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("This SDK installer is for GitHub Actions only. No local SDK was installed.")
    root = Path(os.environ["RUNNER_TEMP"]) / "watermeter-flutter-sdk"
    root.mkdir()
    def run(*arguments):
        subprocess.run(arguments, cwd=root, check=True)
    run("git", "init", "--quiet")
    run("git", "remote", "add", "origin", "https://github.com/flutter/flutter.git")
    run("git", "fetch", "--depth=1", "--filter=blob:none", "origin", "refs/tags/3.50.1:refs/tags/3.50.1")
    actual = subprocess.check_output(["git", "rev-parse", "3.50.1^{}"], cwd=root, text=True).strip()
    if actual != FLUTTER_REVISION:
        raise SystemExit("Flutter tag differs from the reviewed commit")
    run("git", "checkout", "--quiet", "--detach", "3.50.1")
    run(str(root / "bin/flutter"), "--version")
    run(str(root / "bin/flutter"), "--disable-analytics")
    with open(os.environ["GITHUB_PATH"], "a", encoding="utf-8") as output:
        output.write(str(root / "bin") + "\n")
