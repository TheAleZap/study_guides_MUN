#!/usr/bin/env python3
"""Extract the native slice of TeX Live's universal `biber` into .tools/biber.

The universal binary shells out to `lipo`, which refuses to run until the
Xcode licence has been accepted (`sudo xcodebuild -license`). A thin binary
avoids that step; latexmkrc picks it up automatically.
"""

import platform
import shutil
import struct
import sys
from pathlib import Path

CPU_TYPES = {"arm64": 0x0100000C, "x86_64": 0x01000007}

src = Path(shutil.which("biber") or "/Library/TeX/texbin/biber").resolve()
dest = Path(__file__).resolve().parent.parent / ".tools" / "biber"
data = src.read_bytes()

magic, count = struct.unpack(">II", data[:8])
if magic != 0xCAFEBABE:
    sys.exit(f"{src} is not a universal binary; nothing to do.")

wanted = CPU_TYPES[platform.machine()]
for i in range(count):
    cpu, _sub, offset, size, _align = struct.unpack(">iiIII", data[8 + i * 20: 28 + i * 20])
    if cpu == wanted:
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(data[offset: offset + size])
        dest.chmod(0o755)
        print(f"Wrote {dest}")
        break
else:
    sys.exit(f"No {platform.machine()} slice in {src}.")
