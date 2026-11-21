"""Expose sanitized compiler/test diagnostics as readable GitHub annotations."""
import argparse
from pathlib import Path
import re
import subprocess


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    project = parser.parse_args().project.resolve()
    for command in [["flutter", "analyze"], ["flutter", "test", "--reporter", "expanded"]]:
        result = subprocess.run(command, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout, flush=True)
        if result.returncode:
            output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout[-14000:])
            escaped = output.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print("::error title=Mobile compilation or test diagnostics::" + escaped, flush=True)
            raise SystemExit(result.returncode)
