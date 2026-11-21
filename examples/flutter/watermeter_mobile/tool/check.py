"""Expose sanitized compiler/test diagnostics as readable GitHub annotations."""
import argparse
from pathlib import Path
import re
import subprocess


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--run", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    project = arguments.project.resolve()
    commands = [arguments.run] if arguments.run else [["flutter", "analyze"], ["flutter", "test", "--reporter", "expanded"]]
    for command in commands:
        result = subprocess.run(command, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout, flush=True)
        if result.returncode:
            output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout[-12000:])
            for index in range(0, len(output), 2500):
                escaped = output[index:index + 2500].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print("::error title=Mobile diagnostics part " + str(index // 2500 + 1) + "::" + escaped, flush=True)
            raise SystemExit(result.returncode)
