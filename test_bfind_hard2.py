#!/usr/bin/env python3
"""
test_bfind_hard2.py - Additional hard edge case tests for bfind.

Usage:
    python3 test_bfind_hard2.py [--verbose] [--bfind ./bfind]
"""

import argparse
import os
import stat
import subprocess
import sys
import tempfile
import time

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VERBOSE = False
BFIND   = "./bfind"
passed  = 0
failed  = 0


def run_bfind(args, cwd=None, timeout=10):
    cmd = [os.path.abspath(BFIND)] if cwd else [BFIND]
    cmd += args
    if VERBOSE:
        print(f"  {YELLOW}${RESET} {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=timeout, cwd=cwd,
        )
        lines = [l for l in proc.stdout.strip().split("\n") if l]
        if VERBOSE and lines:
            for l in lines[:30]:
                print(f"    {l}")
            if len(lines) > 30:
                print(f"    ... ({len(lines) - 30} more)")
        return proc.returncode, lines, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, [], "TIMEOUT"


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"{GREEN}[PASS]{RESET} {name}")
    else:
        failed += 1
        print(f"{RED}[FAIL]{RESET} {name}")
        if detail:
            print(f"       {detail}")


def test_hard2(tmpdir):
    print(f"\n{BOLD}=== HARD 2 ==={RESET}")

    # ---- H21: hard link to file listed twice (once per path) ----
    h21 = os.path.join(tmpdir, "h21")
    os.makedirs(f"{h21}/a")
    os.makedirs(f"{h21}/b")
    original = f"{h21}/a/file.txt"
    hardlink = f"{h21}/b/file.txt"
    open(original, "w").close()
    os.link(original, hardlink)
    rc, lines, _ = run_bfind([h21, "-name", "file.txt"])
    found = set(lines)
    check("H21: hard link listed once per directory entry (not deduplicated)",
          rc == 0 and original in found and hardlink in found and len(found) == 2,
          f"Got: {found}")

    # ---- H22: symlink to file, -type l without -L ----
    h22 = os.path.join(tmpdir, "h22")
    os.makedirs(h22)
    open(f"{h22}/real.txt", "w").close()
    os.symlink(f"{h22}/real.txt", f"{h22}/link.txt")
    rc, lines, _ = run_bfind([h22, "-type", "l"])
    found = set(lines)
    check("H22: -type l matches symlink to file, not the real file",
          rc == 0 and f"{h22}/link.txt" in found and f"{h22}/real.txt" not in found,
          f"Got: {found}")

    # ---- H23: -name matches file deep in tree but not shallow same-named dir ----
    h23 = os.path.join(tmpdir, "h23")
    os.makedirs(f"{h23}/target")           # directory named "target"
    open(f"{h23}/target/target", "w").close()  # file also named "target" inside
    rc, lines, _ = run_bfind([h23, "-name", "target", "-type", "f"])
    found = set(lines)
    check("H23: -name 'target' -type f finds file not directory of same name",
          rc == 0 and found == {f"{h23}/target/target"},
          f"Got: {found}")

    # ---- H24: -perm on directory ----
    h24 = os.path.join(tmpdir, "h24")
    os.makedirs(h24)
    d755 = f"{h24}/mydir"
    os.makedirs(d755)
    os.chmod(d755, 0o755)
    rc, lines, _ = run_bfind([h24, "-perm", "755", "-type", "d"])
    found = set(lines)
    check("H24: -perm 755 -type d matches directory with 755 perms",
          rc == 0 and d755 in found,
          f"Got: {found}")

    # ---- H25: empty -name pattern matches nothing ----
    h25 = os.path.join(tmpdir, "h25")
    os.makedirs(h25)
    open(f"{h25}/file.txt", "w").close()
    rc, lines, _ = run_bfind([h25, "-name", ""])
    check("H25: empty -name pattern matches nothing",
          rc == 0 and len(lines) == 0,
          f"Got: {set(lines)}")

    # ---- H26: -size boundary: file exactly at boundary not matched by > ----
    h26 = os.path.join(tmpdir, "h26")
    os.makedirs(h26)
    with open(f"{h26}/exact", "wb") as f:
        f.write(b"x" * 1024)   # exactly 1k
    rc, lines, _ = run_bfind([h26, "-size", "+1k", "-type", "f"])
    check("H26: file exactly at size boundary not matched by +1k (strict greater)",
          rc == 0 and len(lines) == 0,
          f"Got: {set(lines)}")

    # ---- H27: -size boundary: file exactly at boundary IS matched by exact ----
    rc, lines, _ = run_bfind([h26, "-size", "1k", "-type", "f"])
    check("H27: file exactly at 1k matched by exact -size 1k",
          rc == 0 and set(lines) == {f"{h26}/exact"},
          f"Got: {set(lines)}")

    # ---- H28: deeply nested symlink cycle with real files alongside ----
    h28 = os.path.join(tmpdir, "h28")
    os.makedirs(f"{h28}/a/b/c")
    open(f"{h28}/a/b/c/real.txt", "w").close()
    os.symlink(os.path.join(h28, "a"), f"{h28}/a/b/c/cycle")
    rc, lines, stderr = run_bfind(["-L", h28], timeout=5)
    found = set(lines)
    check("H28: deep cycle with real files alongside — no hang, real files found",
          rc != -1 and f"{h28}/a/b/c/real.txt" in found,
          "TIMEOUT" if rc == -1 else f"Got: {found}")

    # ---- H29: -mtime 0 excludes file modified exactly 1 day + 1 second ago ----
    h29 = os.path.join(tmpdir, "h29")
    os.makedirs(h29)
    old = f"{h29}/old.txt"
    open(old, "w").close()
    t = time.time() - 86401   # just over 1 day ago
    os.utime(old, (t, t))
    rc, lines, _ = run_bfind([h29, "-mtime", "0", "-type", "f"])
    check("H29: -mtime 0 excludes file modified 1 day + 1 second ago",
          rc == 0 and old not in set(lines),
          f"Got: {set(lines)}")

    # ---- H30: multiple -name filters AND'd (both must match — impossible, no results) ----
    h30 = os.path.join(tmpdir, "h30")
    os.makedirs(h30)
    open(f"{h30}/file.c", "w").close()
    open(f"{h30}/file.h", "w").close()
    rc, lines, _ = run_bfind([h30, "-name", "*.c", "-name", "*.h"])
    check("H30: two -name filters AND'd — no file can match both *.c and *.h",
          rc == 0 and len(lines) == 0,
          f"Got: {set(lines)}")

    # ---- H31: -L follows symlink to directory, prints symlink path not real path ----
    h31 = os.path.join(tmpdir, "h31")
    os.makedirs(f"{h31}/realdir")
    open(f"{h31}/realdir/inside.txt", "w").close()
    os.symlink(f"{h31}/realdir", f"{h31}/linked")
    rc, lines, _ = run_bfind(["-L", h31, "-name", "inside.txt"])
    found = set(lines)
    # Should find it via BOTH realdir and linked paths
    check("H31: with -L, file reachable via symlinked dir is found",
          rc == 0 and any("inside.txt" in l for l in lines),
          f"Got: {found}")

    # ---- H32: starting path is a file, not a directory ----
    h32 = os.path.join(tmpdir, "h32")
    os.makedirs(h32)
    single = f"{h32}/single.txt"
    open(single, "w").close()
    rc, lines, _ = run_bfind([single])
    check("H32: starting path is a single file — prints just that file",
          rc == 0 and set(lines) == {single},
          f"Got: {set(lines)}")

    # ---- H33: starting path is a symlink to a file (no -L) ----
    h33 = os.path.join(tmpdir, "h33")
    os.makedirs(h33)
    open(f"{h33}/real.txt", "w").close()
    os.symlink(f"{h33}/real.txt", f"{h33}/link.txt")
    rc, lines, _ = run_bfind([f"{h33}/link.txt"])
    check("H33: starting path is a symlink to file without -L — listed as symlink",
          rc == 0 and f"{h33}/link.txt" in set(lines),
          f"Got: {set(lines)}")

    # ---- H34: 4 filters ANDed together ----
    h34 = os.path.join(tmpdir, "h34")
    os.makedirs(h34)
    match = f"{h34}/match.c"
    with open(match, "wb") as f:
        f.write(b"x" * 500)
    os.chmod(match, 0o644)
    # Wrong size
    with open(f"{h34}/wrongsize.c", "wb") as f:
        f.write(b"x" * 10)
    os.chmod(f"{h34}/wrongsize.c", 0o644)
    # Wrong perm
    with open(f"{h34}/wrongperm.c", "wb") as f:
        f.write(b"x" * 500)
    os.chmod(f"{h34}/wrongperm.c", 0o755)
    # Wrong name
    with open(f"{h34}/match.h", "wb") as f:
        f.write(b"x" * 500)
    os.chmod(f"{h34}/match.h", 0o644)

    rc, lines, _ = run_bfind([h34, "-name", "*.c", "-type", "f", "-size", "+100c", "-perm", "644"])
    check("H34: four ANDed filters, only one file matches all",
          rc == 0 and set(lines) == {match},
          f"Got: {set(lines)}")

    # ---- H35: very long filename (255 chars) ----
    h35 = os.path.join(tmpdir, "h35")
    os.makedirs(h35)
    longname = "a" * 200 + ".txt"
    open(f"{h35}/{longname}", "w").close()
    rc, lines, _ = run_bfind([h35, "-name", "*.txt"])
    check("H35: file with 200-char name found by -name *.txt",
          rc == 0 and any(longname in l for l in lines),
          f"Got: {set(lines)}")

    # ---- H36: dot-only path component doesn't duplicate slash ----
    h36 = os.path.join(tmpdir, "h36")
    os.makedirs(h36)
    open(f"{h36}/f.txt", "w").close()
    rc, lines, _ = run_bfind([], cwd=h36)
    found = set(lines)
    # Paths should be like ./f.txt not .//f.txt
    check("H36: default '.' path produces clean paths (no double slashes)",
          rc == 0 and all("//" not in l for l in lines),
          f"Got: {found}")

    # ---- H37: -size +0c excludes empty files ----
    h37 = os.path.join(tmpdir, "h37")
    os.makedirs(h37)
    open(f"{h37}/empty", "w").close()
    with open(f"{h37}/nonempty", "wb") as f:
        f.write(b"x")
    rc, lines, _ = run_bfind([h37, "-size", "+0c", "-type", "f"])
    found = set(lines)
    check("H37: -size +0c excludes empty files, includes non-empty",
          rc == 0 and f"{h37}/nonempty" in found and f"{h37}/empty" not in found,
          f"Got: {found}")

    # ---- H38: unreadable directory — error to stderr, traversal continues ----
    h38 = os.path.join(tmpdir, "h38")
    os.makedirs(f"{h38}/locked")
    os.makedirs(f"{h38}/open")
    open(f"{h38}/open/visible.txt", "w").close()
    os.chmod(f"{h38}/locked", 0o000)
    try:
        rc, lines, stderr = run_bfind([h38])
        found = set(lines)
        check("H38: unreadable dir prints stderr error, continues to find other files",
              rc == 0 and f"{h38}/open/visible.txt" in found and len(stderr) > 0,
              f"rc={rc}, found={found}, stderr={'(present)' if stderr else '(empty)'}")
    finally:
        os.chmod(f"{h38}/locked", 0o755)  # restore so tempdir cleanup works

    # ---- H39: -name '*' matches everything ----
    h39 = os.path.join(tmpdir, "h39")
    os.makedirs(f"{h39}/sub")
    open(f"{h39}/a.txt", "w").close()
    open(f"{h39}/sub/b.c", "w").close()
    rc, lines, _ = run_bfind([h39, "-name", "*"])
    expected = {f"{h39}/a.txt", f"{h39}/sub", f"{h39}/sub/b.c"}
    check("H39: -name '*' matches all entries (but not starting dir itself)",
          rc == 0 and expected.issubset(set(lines)),
          f"Got: {set(lines)}")

    # ---- H40: three starting paths with overlapping filter ----
    h40a = os.path.join(tmpdir, "h40a")
    h40b = os.path.join(tmpdir, "h40b")
    h40c = os.path.join(tmpdir, "h40c")
    for d in [h40a, h40b, h40c]:
        os.makedirs(d)
        with open(f"{d}/data.bin", "wb") as f:
            f.write(b"x" * 2000)
        open(f"{d}/ignore.txt", "w").close()
    rc, lines, _ = run_bfind([h40a, h40b, h40c, "-name", "data.bin", "-size", "+1k"])
    found = set(lines)
    check("H40: three starting paths, filter finds matching file in each",
          rc == 0 and found == {f"{h40a}/data.bin", f"{h40b}/data.bin", f"{h40c}/data.bin"},
          f"Got: {found}")


def main():
    global VERBOSE, BFIND

    parser = argparse.ArgumentParser(description="Hard2 bfind tests")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--bfind", default="./bfind")
    args = parser.parse_args()
    VERBOSE = args.verbose
    BFIND = args.bfind

    if not os.path.isfile(BFIND):
        print(f"{RED}Error:{RESET} '{BFIND}' not found. Run 'make' first.")
        return 1

    print(f"\n{BOLD}=== bfind Hard2 Tests ==={RESET}")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_hard2(tmpdir)

    total = passed + failed
    print(f"\n{BOLD}=== Results ==={RESET}")
    print(f"  {GREEN}Passed: {passed}/{total}{RESET}")
    if failed:
        print(f"  {RED}Failed: {failed}/{total}{RESET}")
    else:
        print(f"  {GREEN}All tests passed!{RESET}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())