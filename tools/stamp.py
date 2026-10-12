#!/usr/bin/env python3
"""Set the software version — version, build, date, note.

    python3 tools/stamp.py 2.1 "short description"
    python3 tools/stamp.py --check

The version lives in three places that must agree:

  code.py                 EL_VERSION / EL_BUILD / EL_DATE / EL_NOTE
  html/app.js             UI_VERSION / UI_BUILD / UI_DATE
  html/service-worker.js  CACHE_NAME

The cache name depends on the build, so bumping it when rolling out can no
longer be forgotten — otherwise the phone shows the old UI on first open.

Build = number of commits on HEAD + 1, i.e. the number of the commit the stamp
lands in. Commit right afterwards, or the number is off.

--check changes nothing and reports mismatches (exit code 1).
(Taken from the SolarLoader.)
"""
import datetime, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CODE = ROOT / "code.py"
APP  = ROOT / "html" / "app.js"
SW   = ROOT / "html" / "service-worker.js"

PATTERNS = {
    CODE: {
        "version": r'^(EL_VERSION = )"([^"]*)"',
        "build":   r'^(EL_BUILD   = )(\d+)',
        "date":    r'^(EL_DATE    = )"([^"]*)"',
        "note":    r'^(EL_NOTE    = )"([^"]*)"',
    },
    APP: {
        "version": r"^(const UI_VERSION = )'([^']*)'",
        "build":   r"^(const UI_BUILD   = )(\d+)",
        "date":    r"^(const UI_DATE    = )'([^']*)'",
    },
    SW: {
        "cache":   r'^(const CACHE_NAME = )"([^"]*)"',
    },
}


def _read():
    values = {}
    for path, fields in PATTERNS.items():
        text = path.read_text(encoding="utf-8")
        for field, pattern in fields.items():
            m = re.search(pattern, text, re.M)
            if not m:
                sys.exit(f"{path.name}: {field} not found")
            values[(path.name, field)] = m.group(2)
    return values


def _cache_name(version, build):
    return f"energy-logger-v{version}-b{build}"


def check():
    v = _read()
    version, build, date = (v[("code.py", k)] for k in ("version", "build", "date"))
    problems = []
    for field, want in (("version", version), ("build", build), ("date", date)):
        have = v[("app.js", field)]
        if have != want:
            problems.append(f"app.js {field} = {have}, code.py says {want}")
    want_cache = _cache_name(version, build)
    if v[("service-worker.js", "cache")] != want_cache:
        problems.append(f"service-worker.js CACHE_NAME = "
                        f"{v[('service-worker.js', 'cache')]}, expected {want_cache}")
    for p in problems:
        print("MISMATCH  " + p)
    if not problems:
        print(f"OK  v{version} build {build} of {date}: {v[('code.py', 'note')]}")
    return not problems


def stamp(version, note):
    if not re.fullmatch(r"\d+\.\d+", version):
        sys.exit(f"Version '{version}' is not of the form 2.1")
    if '"' in note or "'" in note:
        sys.exit("Note without quotes, please")
    build = int(subprocess.check_output(
        ["git", "rev-list", "--count", "HEAD"], cwd=ROOT, text=True)) + 1
    date = datetime.date.today().isoformat()
    new = {
        CODE: {"version": f'"{version}"', "build": str(build),
               "date": f'"{date}"', "note": f'"{note}"'},
        APP:  {"version": f"'{version}'", "build": str(build), "date": f"'{date}'"},
        SW:   {"cache": f'"{_cache_name(version, build)}"'},
    }
    for path, fields in new.items():
        text = path.read_text(encoding="utf-8")
        for field, value in fields.items():
            text, n = re.subn(PATTERNS[path][field],
                              lambda m, w=value: m.group(1) + w, text,
                              count=1, flags=re.M)
            if n != 1:
                sys.exit(f"{path.name}: {field} not found")
        path.write_text(text, encoding="utf-8")
    print(f"Stamped: v{version} build {build} of {date} — commit now.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--check"]:
        sys.exit(0 if check() else 1)
    if len(args) != 2:
        sys.exit(__doc__)
    stamp(*args)
    sys.exit(0 if check() else 1)
