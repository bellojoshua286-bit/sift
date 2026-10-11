import glob
import os
import sys

SITE = os.path.join("venv", "Lib", "site-packages")

# (name, license name, dist-info folder pattern, license files inside it)
LIBRARIES = [
    ("customtkinter", "CC0 1.0 Universal",
     "customtkinter-*.dist-info", ["licenses/LICENSE"]),
    ("Pillow", "MIT-CMU",
     "pillow-*.dist-info", ["licenses/LICENSE"]),
    ("Send2Trash", "BSD 3-Clause",
     "send2trash-*.dist-info", ["licenses/LICENSE"]),
    ("darkdetect", "BSD 3-Clause",
     "darkdetect-*.dist-info", ["LICENSE"]),
    ("packaging", "BSD 2-Clause (the BSD option of its dual license)",
     "packaging-*.dist-info", ["licenses/LICENSE", "licenses/LICENSE.BSD"]),
]

LINE = "=" * 72


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def section(title, texts):
    return f"{LINE}\n{title}\n{LINE}\n\n" + "\n\n".join(texts) + "\n"


parts = [
    "THIRD-PARTY NOTICES\n\n"
    "Sift includes the third-party software listed below. The license text "
    "of each component is reproduced as provided by its authors.\n"
]
missing = []

# Libraries installed in the virtual environment
for name, license_name, pattern, files in LIBRARIES:
    folders = glob.glob(os.path.join(SITE, pattern))
    if not folders:
        missing.append(name)
        continue

    folder = folders[0]
    version = os.path.basename(folder).replace(".dist-info", "").split("-", 1)[1]

    texts = []
    for rel in files:
        path = os.path.join(folder, *rel.split("/"))
        if os.path.exists(path):
            texts.append(read(path))
        else:
            missing.append(f"{name}: {rel}")

    if texts:
        parts.append(section(f"{name} {version} - {license_name}", texts))
        print(f"Added: {name} {version} ({len(texts)} file(s))")

# Python itself
python_license = os.path.join(sys.base_prefix, "LICENSE.txt")
if os.path.exists(python_license):
    py_version = ".".join(map(str, sys.version_info[:3]))
    parts.append(section(
        f"Python {py_version} - Python Software Foundation License",
        [read(python_license)],
    ))
    print(f"Added: Python {py_version}")
else:
    missing.append("Python: LICENSE.txt")

# Tcl/Tk (the toolkit behind the window)
tk_texts = []
pattern = os.path.join(sys.base_prefix, "tcl", "**", "license.terms")
for path in glob.glob(pattern, recursive=True):
    text = read(path)
    if text not in tk_texts:
        tk_texts.append(text)
if tk_texts:
    parts.append(section("Tcl/Tk - Tcl/Tk License", tk_texts))
    print(f"Added: Tcl/Tk ({len(tk_texts)} license text(s))")
else:
    missing.append("Tcl/Tk: license.terms")

with open("THIRD_PARTY_NOTICES.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(parts))

print("\nWrote THIRD_PARTY_NOTICES.txt")
if missing:
    print("NOT FOUND:")
    for item in missing:
        print("  -", item)