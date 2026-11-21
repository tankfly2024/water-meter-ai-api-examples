"""Build two public source bundles; publish only on the approved preview tag."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "tankfly2024/water-meter-ai-api-examples"
TAG = "preview-20261121"
IMAGE_FILES = [
    "README.md", "README.zh-CN.md", ".gitignore", "run.py", "docs/使用说明.md",
    "src/app.js", "src/client.py", "src/index.html", "src/style.css", "tests/test_client.py",
]


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples/python/image_to_csv"
    image_zip = output / "watermeter-image-to-csv-0.1.0.zip"
    members = {"image_to_csv/" + name: (source / name).read_bytes().replace(b"\r\n", b"\n") for name in IMAGE_FILES}
    members["image_to_csv/LICENSE"] = (ROOT / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
    with zipfile.ZipFile(image_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(members.items()):
            if name.endswith(".py"):
                ast.parse(content.decode("utf-8"), filename=name)
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    spec = importlib.util.spec_from_file_location("watermeter_ha_package", ROOT / "examples/home_assistant/package.py")
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    ha_zip = output / "watermeter-ai-0.1.0.zip"
    package.build(ha_zip)
    assets = [image_zip, ha_zip]
    metadata = []
    for path in assets:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None or any(".." in Path(name).parts for name in archive.namelist()):
                raise ValueError("Invalid package")
            for name in archive.namelist():
                if name.endswith((".py", ".md", ".js", ".html", ".css", ".json")):
                    archive.read(name).decode("utf-8")
        metadata.append({"name": path.name, "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    checksums = output / "SHA256SUMS.txt"
    checksums.write_bytes("".join(item["sha256"] + "  " + item["name"] + "\n" for item in metadata).encode("utf-8"))
    return assets + [checksums], metadata


def publish(assets):
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/tags/" + TAG:
        raise RuntimeError("Publishing requires the approved repository and preview tag")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GitHub Actions token unavailable")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def request(method, url, payload=None, content_type="application/json"):
        if urllib.parse.urlsplit(url).hostname not in {"api.github.com", "uploads.github.com"}:
            raise RuntimeError("Unexpected GitHub API host")
        data = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        req = urllib.request.Request(url, method=method, data=data, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "User-Agent": "WaterMeter-preview-publisher", "Content-Type": content_type,
            "X-GitHub-Api-Version": "2026-03-10",
        })
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            raise RuntimeError("GitHub publication failed (HTTP " + str(status) + ")") from None

    endpoint = "https://api.github.com/repos/" + REPOSITORY + "/releases"
    existing = request("GET", endpoint + "?per_page=100")
    release = next((entry for entry in existing if entry["tag_name"] == TAG), None)
    if release and not release["draft"]:
        raise RuntimeError("This preview is already public; do not overwrite its assets")
    if release is None:
        release = request("POST", endpoint, {
            "tag_name": TAG, "target_commitish": os.environ["GITHUB_SHA"],
            "name": "WaterMeter AI clients 0.1.0 — testing preview",
            "body": (ROOT / "releases/preview-20261121.md").read_text(encoding="utf-8"),
            "draft": True, "prerelease": True, "make_latest": "false",
        })
    upload = release["upload_url"].split("{")[0]
    attached = {entry["name"]: entry for entry in release.get("assets", [])}
    for path in assets:
        if path.name in attached:
            entry = attached[path.name]
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if entry.get("digest") != digest:
                raise RuntimeError("Draft already contains different asset bytes")
            continue
        mime = "application/zip" if path.suffix == ".zip" else "text/plain"
        request("POST", upload + "?" + urllib.parse.urlencode({"name": path.name}), path.read_bytes(), mime)
    public = request("PATCH", endpoint + "/" + str(release["id"]), {"draft": False, "prerelease": True, "make_latest": "false"})
    print(json.dumps({"release": public["html_url"], "prerelease": public["prerelease"], "assets": [path.name for path in assets]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--publish", action="store_true")
    arguments = parser.parse_args()
    files, metadata = build(arguments.output_dir.resolve())
    print(json.dumps({"tag": TAG, "packages": metadata}, indent=2))
    if arguments.publish:
        publish(files)
