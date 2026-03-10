#!/usr/bin/env python3
"""
test_bfind_extended.py - Extended tests for bfind.

Covers easy, medium, and hard edge cases beyond the basic sanity suite.

Usage:
    python3 test_bfind_extended.py [--verbose] [--bfind ./bfind]
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


# ================================================================== #
#  EASY TESTS                                                          #
# ================================================================== #

def test_easy(tmpdir):
    print(f"\n{BOLD}=== EASY ==={RESET}")

    # ---- E1: empty directory ----
    empty = os.path.join(tmpdir, "empty_dir")
    os.makedirs(empty)
    rc, lines, _ = run_bfind([empty])
    check("E1: empty directory prints only itself",
          rc == 0 and set(lines) == {empty},
          f"Got: {set(lines)}")

    # ---- E2: single file in root ----
    e2 = os.path.join(tmpdir, "e2")
    os.makedirs(e2)
    open(f"{e2}/only.txt", "w").close()
    rc, lines, _ = run_bfind([e2])
    check("E2: single file found",
          rc == 0 and f"{e2}/only.txt" in set(lines),
          f"Got: {set(lines)}")

    # ---- E3: -type f returns no dirs ----
    e3 = os.path.join(tmpdir, "e3")
    os.makedirs(f"{e3}/sub")
    open(f"{e3}/f.txt", "w").close()
    rc, lines, _ = run_bfind([e3, "-type", "f"])
    found = set(lines)
    check("E3: -type f never returns directories",
          rc == 0 and e3 not in found and f"{e3}/sub" not in found and f"{e3}/f.txt" in found,
          f"Got: {found}")

    # ---- E4: -type d returns no files ----
    rc, lines, _ = run_bfind([e3, "-type", "d"])
    found = set(lines)
    check("E4: -type d never returns files",
          rc == 0 and f"{e3}/f.txt" not in found and e3 in found and f"{e3}/sub" in found,
          f"Got: {found}")

    # ---- E5: -name exact filename ----
    e5 = os.path.join(tmpdir, "e5")
    os.makedirs(e5)
    open(f"{e5}/needle.txt", "w").close()
    open(f"{e5}/other.txt", "w").close()
    rc, lines, _ = run_bfind([e5, "-name", "needle.txt"])
    check("E5: -name exact match",
          rc == 0 and set(lines) == {f"{e5}/needle.txt"},
          f"Got: {set(lines)}")

    # ---- E6: -name with ? wildcard ----
    e6 = os.path.join(tmpdir, "e6")
    os.makedirs(e6)
    open(f"{e6}/a1.c", "w").close()
    open(f"{e6}/a22.c", "w").close()
    open(f"{e6}/b1.c", "w").close()
    rc, lines, _ = run_bfind([e6, "-name", "a?.c"])
    check("E6: -name with ? wildcard",
          rc == 0 and set(lines) == {f"{e6}/a1.c"},
          f"Got: {set(lines)}")

    # ---- E7: -size 0c finds empty files ----
    e7 = os.path.join(tmpdir, "e7")
    os.makedirs(e7)
    open(f"{e7}/empty1", "w").close()
    open(f"{e7}/empty2", "w").close()
    with open(f"{e7}/nonempty", "w") as f:
        f.write("x")
    rc, lines, _ = run_bfind([e7, "-size", "0c", "-type", "f"])
    check("E7: -size 0c finds exactly empty files",
          rc == 0 and set(lines) == {f"{e7}/empty1", f"{e7}/empty2"},
          f"Got: {set(lines)}")

    # ---- E8: -size +Nc greater-than ----
    e8 = os.path.join(tmpdir, "e8")
    os.makedirs(e8)
    with open(f"{e8}/big", "wb") as f:
        f.write(b"x" * 500)
    with open(f"{e8}/small", "wb") as f:
        f.write(b"x" * 10)
    rc, lines, _ = run_bfind([e8, "-size", "+100c", "-type", "f"])
    check("E8: -size +100c greater-than",
          rc == 0 and set(lines) == {f"{e8}/big"},
          f"Got: {set(lines)}")

    # ---- E9: -size -Nc less-than ----
    rc, lines, _ = run_bfind([e8, "-size", "-100c", "-type", "f"])
    check("E9: -size -100c less-than",
          rc == 0 and set(lines) == {f"{e8}/small"},
          f"Got: {set(lines)}")

    # ---- E10: multiple paths given ----
    e10a = os.path.join(tmpdir, "e10a")
    e10b = os.path.join(tmpdir, "e10b")
    os.makedirs(e10a)
    os.makedirs(e10b)
    open(f"{e10a}/fa.txt", "w").close()
    open(f"{e10b}/fb.txt", "w").close()
    rc, lines, _ = run_bfind([e10a, e10b])
    found = set(lines)
    check("E10: multiple starting paths are all traversed",
          rc == 0 and f"{e10a}/fa.txt" in found and f"{e10b}/fb.txt" in found,
          f"Got: {found}")

    # ---- E11: --help exits cleanly ----
    rc, lines, stderr = run_bfind(["--help"])
    check("E11: --help exits with code 0 and prints usage",
          rc == 0,
          f"rc={rc}")

    # ---- E12: -size with k suffix ----
    e12 = os.path.join(tmpdir, "e12")
    os.makedirs(e12)
    with open(f"{e12}/kfile", "wb") as f:
        f.write(b"x" * 2048)   # exactly 2 KiB
    with open(f"{e12}/small", "wb") as f:
        f.write(b"x" * 512)
    rc, lines, _ = run_bfind([e12, "-size", "+1k", "-type", "f"])
    check("E12: -size +1k (KiB suffix)",
          rc == 0 and set(lines) == {f"{e12}/kfile"},
          f"Got: {set(lines)}")

    # ---- E13: -perm exact match ----
    e13 = os.path.join(tmpdir, "e13")
    os.makedirs(e13)
    path644 = f"{e13}/f644"
    path755 = f"{e13}/f755"
    open(path644, "w").close()
    open(path755, "w").close()
    os.chmod(path644, 0o644)
    os.chmod(path755, 0o755)
    rc, lines, _ = run_bfind([e13, "-perm", "644", "-type", "f"])
    check("E13: -perm 644 exact match",
          rc == 0 and set(lines) == {path644},
          f"Got: {set(lines)}")


# ================================================================== #
#  MEDIUM TESTS                                                        #
# ================================================================== #

def test_medium(tmpdir):
    print(f"\n{BOLD}=== MEDIUM ==={RESET}")

    # ---- M1: BFS depth ordering across wide tree ----
    m1 = os.path.join(tmpdir, "m1")
    os.makedirs(f"{m1}/a/aa")
    os.makedirs(f"{m1}/b/bb")
    open(f"{m1}/root.txt", "w").close()
    open(f"{m1}/a/a.txt", "w").close()
    open(f"{m1}/b/b.txt", "w").close()
    open(f"{m1}/a/aa/deep.txt", "w").close()
    open(f"{m1}/b/bb/deep.txt", "w").close()

    rc, lines, _ = run_bfind([m1])
    base_depth = m1.count("/")
    depths = [l.count("/") - base_depth for l in lines]
    check("M1: BFS depth is non-decreasing in wide tree",
          rc == 0 and all(depths[i] <= depths[i+1] for i in range(len(depths)-1)),
          f"Depths: {depths}")

    # ---- M2: -name matches only basename, not full path ----
    m2 = os.path.join(tmpdir, "m2")
    os.makedirs(f"{m2}/sub")
    open(f"{m2}/sub/test.c", "w").close()
    open(f"{m2}/test.c", "w").close()
    rc, lines, _ = run_bfind([m2, "-name", "test.c"])
    found = set(lines)
    check("M2: -name matches basename only (not full path components)",
          rc == 0 and found == {f"{m2}/test.c", f"{m2}/sub/test.c"},
          f"Got: {found}")

    # ---- M3: -name does NOT match directory name for -type f ----
    m3 = os.path.join(tmpdir, "m3")
    os.makedirs(f"{m3}/foo.c")        # directory named like a .c file
    open(f"{m3}/foo.c/actual.c", "w").close()
    rc, lines, _ = run_bfind([m3, "-name", "*.c", "-type", "f"])
    found = set(lines)
    check("M3: -name *.c -type f skips directory named foo.c",
          rc == 0 and found == {f"{m3}/foo.c/actual.c"},
          f"Got: {found}")

    # ---- M4: -mtime 0 finds recently modified file ----
    m4 = os.path.join(tmpdir, "m4")
    os.makedirs(m4)
    open(f"{m4}/recent.txt", "w").close()   # just created = mtime within last day
    rc, lines, _ = run_bfind([m4, "-mtime", "0", "-type", "f"])
    check("M4: -mtime 0 finds file modified today",
          rc == 0 and f"{m4}/recent.txt" in set(lines),
          f"Got: {set(lines)}")

    # ---- M5: -mtime excludes old file ----
    m5 = os.path.join(tmpdir, "m5")
    os.makedirs(m5)
    old = f"{m5}/old.txt"
    open(old, "w").close()
    old_time = time.time() - 10 * 86400   # 10 days ago
    os.utime(old, (old_time, old_time))
    rc, lines, _ = run_bfind([m5, "-mtime", "2", "-type", "f"])
    check("M5: -mtime 2 excludes file modified 10 days ago",
          rc == 0 and old not in set(lines),
          f"Got: {set(lines)}")

    # ---- M6: combined -name and -type ----
    m6 = os.path.join(tmpdir, "m6")
    os.makedirs(f"{m6}/libdir")
    open(f"{m6}/lib.c", "w").close()
    open(f"{m6}/libdir/inner.c", "w").close()
    rc, lines, _ = run_bfind([m6, "-name", "lib*", "-type", "f"])
    found = set(lines)
    check("M6: -name 'lib*' -type f doesn't match directory named libdir",
          rc == 0 and f"{m6}/lib.c" in found and f"{m6}/libdir" not in found,
          f"Got: {found}")

    # ---- M7: -xdev stays on same filesystem ----
    m7 = os.path.join(tmpdir, "m7")
    os.makedirs(m7)
    open(f"{m7}/local.txt", "w").close()
    # /proc is almost always a different device; we expect bfind not to descend into it
    # We test a simpler version: just make sure -xdev doesn't crash and returns local file
    rc, lines, _ = run_bfind(["-xdev", m7])
    check("M7: -xdev flag doesn't crash, returns local files",
          rc == 0 and f"{m7}/local.txt" in set(lines),
          f"Got: {set(lines)}")

    # ---- M8: path with trailing slash ----
    m8 = os.path.join(tmpdir, "m8")
    os.makedirs(m8)
    open(f"{m8}/x.txt", "w").close()
    rc, lines, _ = run_bfind([m8 + "/"])
    found = set(lines)
    check("M8: path with trailing slash still finds files",
          rc == 0 and any("x.txt" in l for l in lines),
          f"Got: {found}")

    # ---- M9: -size exact with k suffix ----
    m9 = os.path.join(tmpdir, "m9")
    os.makedirs(m9)
    with open(f"{m9}/exact1k", "wb") as f:
        f.write(b"x" * 1024)
    with open(f"{m9}/not1k", "wb") as f:
        f.write(b"x" * 1025)
    rc, lines, _ = run_bfind([m9, "-size", "1k", "-type", "f"])
    check("M9: -size 1k exact match (1024 bytes only)",
          rc == 0 and set(lines) == {f"{m9}/exact1k"},
          f"Got: {set(lines)}")

    # ---- M10: -perm 755 ----
    m10 = os.path.join(tmpdir, "m10")
    os.makedirs(m10)
    p755 = f"{m10}/exec"
    p644 = f"{m10}/noexec"
    open(p755, "w").close()
    open(p644, "w").close()
    os.chmod(p755, 0o755)
    os.chmod(p644, 0o644)
    rc, lines, _ = run_bfind([m10, "-perm", "755"])
    found = set(lines)
    check("M10: -perm 755 matches only 755 files",
          rc == 0 and p755 in found and p644 not in found,
          f"Got: {found}")

    # ---- M11: deeply nested (5 levels) ----
    m11 = os.path.join(tmpdir, "m11")
    deep = f"{m11}/a/b/c/d/e"
    os.makedirs(deep)
    open(f"{deep}/treasure.txt", "w").close()
    rc, lines, _ = run_bfind([m11, "-name", "treasure.txt"])
    check("M11: -name finds file 5 levels deep",
          rc == 0 and set(lines) == {f"{deep}/treasure.txt"},
          f"Got: {set(lines)}")

    # ---- M12: no filters prints everything ----
    m12 = os.path.join(tmpdir, "m12")
    os.makedirs(f"{m12}/sub")
    open(f"{m12}/a", "w").close()
    open(f"{m12}/sub/b", "w").close()
    rc, lines, _ = run_bfind([m12])
    expected = {m12, f"{m12}/a", f"{m12}/sub", f"{m12}/sub/b"}
    check("M12: no filters prints every entry",
          rc == 0 and set(lines) == expected,
          f"Expected: {expected}\n       Got:      {set(lines)}")


# ================================================================== #
#  HARD TESTS                                                          #
# ================================================================== #

def test_hard(tmpdir):
    print(f"\n{BOLD}=== HARD ==={RESET}")

    # ---- H1: symlink to file (no -L) ----
    h1 = os.path.join(tmpdir, "h1")
    os.makedirs(h1)
    open(f"{h1}/real.txt", "w").close()
    os.symlink("real.txt", f"{h1}/link.txt")
    rc, lines, _ = run_bfind([h1, "-type", "l"])
    check("H1: without -L, symlink to file shows as type l",
          rc == 0 and f"{h1}/link.txt" in set(lines),
          f"Got: {set(lines)}")

    # ---- H2: symlink to file WITH -L: appears as regular file ----
    rc, lines, _ = run_bfind(["-L", h1, "-type", "f"])
    found = set(lines)
    check("H2: with -L, symlink to file appears as type f",
          rc == 0 and f"{h1}/link.txt" in found,
          f"Got: {found}")

    # ---- H3: -type l not listed when -L is active (symlink resolved) ----
    # With -L, lstat is still used for type check in original find behaviour.
    # Here we verify at minimum that following the symlink doesn't hide entries.
    rc, lines, _ = run_bfind(["-L", h1])
    found = set(lines)
    check("H3: with -L, all entries present (real + symlink children)",
          rc == 0 and f"{h1}/real.txt" in found and f"{h1}/link.txt" in found,
          f"Got: {found}")

    # ---- H4: double cycle (two symlinks pointing to same ancestor) ----
    h4 = os.path.join(tmpdir, "h4")
    os.makedirs(f"{h4}/core")
    open(f"{h4}/core/data.txt", "w").close()
    os.symlink(os.path.join(h4, "core"), f"{h4}/core/loop1")
    os.symlink(os.path.join(h4, "core"), f"{h4}/core/loop2")
    rc, lines, stderr = run_bfind(["-L", h4], timeout=5)
    check("H4: double symlink cycle doesn't hang",
          rc != -1,
          "TIMEOUT" if rc == -1 else f"rc={rc}, {len(lines)} entries")

    # ---- H5: -xdev with a bind-mount-like situation using /proc ----
    # Just check that bfind -xdev . doesn't descend into /proc when started from /
    # (hard to simulate without root, so we check that it at least doesn't crash
    # and that files on the same device are found)
    h5 = os.path.join(tmpdir, "h5")
    os.makedirs(f"{h5}/sub")
    open(f"{h5}/f.txt", "w").close()
    rc, lines, _ = run_bfind(["-xdev", h5])
    found = set(lines)
    check("H5: -xdev finds local files on same device",
          rc == 0 and f"{h5}/f.txt" in found,
          f"Got: {found}")

    # ---- H6: -name with bracket glob ----
    h6 = os.path.join(tmpdir, "h6")
    os.makedirs(h6)
    open(f"{h6}/file1.c", "w").close()
    open(f"{h6}/file2.c", "w").close()
    open(f"{h6}/file3.c", "w").close()
    open(f"{h6}/file4.c", "w").close()
    rc, lines, _ = run_bfind([h6, "-name", "file[13].c"])
    found = set(lines)
    check("H6: -name with bracket glob [13]",
          rc == 0 and found == {f"{h6}/file1.c", f"{h6}/file3.c"},
          f"Got: {found}")

    # ---- H7: three filters ANDed ----
    h7 = os.path.join(tmpdir, "h7")
    os.makedirs(h7)
    with open(f"{h7}/match.c", "wb") as f:
        f.write(b"x" * 200)
    os.chmod(f"{h7}/match.c", 0o644)
    with open(f"{h7}/wrong_perm.c", "wb") as f:
        f.write(b"x" * 200)
    os.chmod(f"{h7}/wrong_perm.c", 0o755)
    with open(f"{h7}/wrong_size.c", "wb") as f:
        f.write(b"x" * 10)
    os.chmod(f"{h7}/wrong_size.c", 0o644)

    rc, lines, _ = run_bfind([h7, "-name", "*.c", "-size", "+100c", "-perm", "644"])
    check("H7: three ANDed filters (-name, -size, -perm)",
          rc == 0 and set(lines) == {f"{h7}/match.c"},
          f"Got: {set(lines)}")

    # ---- H8: large flat directory (500 files) ----
    h8 = os.path.join(tmpdir, "h8")
    os.makedirs(h8)
    for i in range(500):
        open(f"{h8}/f{i:04d}.txt", "w").close()
    rc, lines, _ = run_bfind([h8, "-type", "f"], timeout=15)
    check("H8: 500-file flat directory, all found",
          rc == 0 and len(lines) == 500,
          f"Got {len(lines)} entries")

    # ---- H9: wide tree (10 dirs each with 10 files) ----
    h9 = os.path.join(tmpdir, "h9")
    os.makedirs(h9)
    for d in range(10):
        os.makedirs(f"{h9}/d{d}")
        for f in range(10):
            open(f"{h9}/d{d}/f{f}.txt", "w").close()
    rc, lines, _ = run_bfind([h9, "-type", "f"], timeout=15)
    check("H9: wide tree 10×10, all 100 files found",
          rc == 0 and len(lines) == 100,
          f"Got {len(lines)} files")
    base_depth = h9.count("/")
    if lines:
        depths = [l.count("/") - base_depth for l in lines]
        check("H9b: BFS order preserved in wide tree",
              all(depths[i] <= depths[i+1] for i in range(len(depths)-1)),
              f"Depth sequence broken: {depths[:20]}...")

    # ---- H10: -size with M suffix ----
    h10 = os.path.join(tmpdir, "h10")
    os.makedirs(h10)
    big = f"{h10}/bigfile"
    with open(big, "wb") as f:
        f.write(b"x" * (2 * 1024 * 1024))   # 2 MiB
    small = f"{h10}/smallfile"
    with open(small, "wb") as f:
        f.write(b"x" * 512)
    rc, lines, _ = run_bfind([h10, "-size", "+1M", "-type", "f"])
    check("H10: -size +1M finds 2 MiB file",
          rc == 0 and set(lines) == {big},
          f"Got: {set(lines)}")

    # ---- H11: broken symlink without -L ----
    h11 = os.path.join(tmpdir, "h11")
    os.makedirs(h11)
    open(f"{h11}/real.txt", "w").close()
    os.symlink("/nonexistent/target", f"{h11}/broken_link")
    rc, lines, stderr = run_bfind([h11])
    found = set(lines)
    check("H11: broken symlink listed without -L (lstat succeeds)",
          rc == 0 and f"{h11}/broken_link" in found,
          f"Got: {found}")

    # ---- H12: broken symlink WITH -L ----
    rc, lines, stderr = run_bfind(["-L", h11])
    check("H12: broken symlink with -L prints stderr error, doesn't crash",
          rc == 0 and len(stderr) > 0,
          f"rc={rc}, stderr={'(present)' if stderr else '(empty)'}")

    # ---- H13: file named with spaces ----
    h13 = os.path.join(tmpdir, "h13")
    os.makedirs(h13)
    spaced = f"{h13}/has spaces.txt"
    open(spaced, "w").close()
    rc, lines, _ = run_bfind([h13, "-name", "has spaces.txt"])
    check("H13: file with spaces in name found by -name",
          rc == 0 and spaced in set(lines),
          f"Got: {set(lines)}")

    # ---- H14: -name pattern with leading dot (hidden files) ----
    h14 = os.path.join(tmpdir, "h14")
    os.makedirs(h14)
    open(f"{h14}/.hidden", "w").close()
    open(f"{h14}/visible", "w").close()
    rc, lines, _ = run_bfind([h14, "-name", ".*"])
    found = set(lines)
    check("H14: -name '.*' matches hidden files",
          rc == 0 and f"{h14}/.hidden" in found and f"{h14}/visible" not in found,
          f"Got: {found}")

    # ---- H15: symlink chain (A -> B -> real_dir) with -L ----
    h15 = os.path.join(tmpdir, "h15")
    os.makedirs(f"{h15}/real_dir")
    open(f"{h15}/real_dir/file.txt", "w").close()
    os.symlink(f"{h15}/real_dir", f"{h15}/linkB")
    os.symlink(f"{h15}/linkB", f"{h15}/linkA")
    rc, lines, stderr = run_bfind(["-L", h15], timeout=5)
    found = set(lines)
    check("H15: symlink chain A->B->dir followed with -L",
          rc != -1 and f"{h15}/real_dir/file.txt" in found,
          "TIMEOUT" if rc == -1 else f"Got: {found}")

    # ---- H16: -mtime 0 on file with mtime exactly at boundary ----
    h16 = os.path.join(tmpdir, "h16")
    os.makedirs(h16)
    borderline = f"{h16}/border.txt"
    open(borderline, "w").close()
    # Set mtime to exactly 23 hours ago (still within 1 day = mtime 0)
    t = time.time() - 23 * 3600
    os.utime(borderline, (t, t))
    rc, lines, _ = run_bfind([h16, "-mtime", "0"])
    check("H16: -mtime 0 includes file modified 23 hours ago",
          rc == 0 and borderline in set(lines),
          f"Got: {set(lines)}")

    # ---- H17: unknown option gives non-zero exit + stderr ----
    rc, lines, stderr = run_bfind([tmpdir, "-bogus"])
    check("H17: unknown filter exits non-zero with error message",
          rc != 0 and len(stderr) > 0,
          f"rc={rc}, stderr={'(present)' if stderr else '(empty)'}")

    # ---- H18: missing argument to -name gives non-zero exit ----
    rc, lines, stderr = run_bfind([tmpdir, "-name"])
    check("H18: -name with no argument exits non-zero",
          rc != 0,
          f"rc={rc}")

    # ---- H19: multiple starting paths, -name filter applies across all ----
    h19a = os.path.join(tmpdir, "h19a")
    h19b = os.path.join(tmpdir, "h19b")
    os.makedirs(h19a)
    os.makedirs(h19b)
    open(f"{h19a}/target.txt", "w").close()
    open(f"{h19b}/target.txt", "w").close()
    open(f"{h19a}/other.txt", "w").close()
    rc, lines, _ = run_bfind([h19a, h19b, "-name", "target.txt"])
    found = set(lines)
    check("H19: -name filter applies across multiple starting paths",
          rc == 0 and found == {f"{h19a}/target.txt", f"{h19b}/target.txt"},
          f"Got: {found}")

    # ---- H20: -size -0c matches no regular file (nothing is < 0 bytes) ----
    h20 = os.path.join(tmpdir, "h20")
    os.makedirs(h20)
    open(f"{h20}/f.txt", "w").close()
    rc, lines, _ = run_bfind([h20, "-size", "-0c", "-type", "f"])
    check("H20: -size -0c matches no files (nothing is < 0 bytes)",
          rc == 0 and len(lines) == 0,
          f"Got: {set(lines)}")


# ================================================================== #
#  Main                                                                #
# ================================================================== #

def main():
    global VERBOSE, BFIND

    parser = argparse.ArgumentParser(description="Extended bfind tests")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--bfind", default="./bfind")
    args = parser.parse_args()
    VERBOSE = args.verbose
    BFIND = args.bfind

    if not os.path.isfile(BFIND):
        print(f"{RED}Error:{RESET} '{BFIND}' not found. Run 'make' first.")
        return 1

    print(f"\n{BOLD}=== bfind Extended Tests ==={RESET}")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_easy(tmpdir)
        test_medium(tmpdir)
        test_hard(tmpdir)

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