"""Build a source-only manual installation ZIP from an explicit allowlist."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = [
    "__init__.py", "api.py", "button.py", "config_flow.py", "const.py", "engine.py",
    "runtime.py", "sensor.py", "manifest.json", "strings.json",
    "translations/en.json", "translations/zh-Hans.json",
]


def build(output):
    component = ROOT / "custom_components" / "watermeter_ai"
    members = {}
    for name in FILES:
        content = (component / name).read_bytes().replace(b"\r\n", b"\n")
        if name.endswith(".py"):
            ast.parse(content.decode("utf-8"), filename=name)
        else:
            json.loads(content)
        members["custom_components/watermeter_ai/" + name] = content
    for name in ["README.md", "README.zh-CN.md", "examples/automation.yaml"]:
        members[name] = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
    members["LICENSE"] = (ROOT.parents[1] / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(members):
            raise ValueError("Package verification failed")
    return {"file": output.name, "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "members": len(members)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="watermeter-ai-0.1.0.zip")
    print(json.dumps(build(parser.parse_args().output), indent=2))
