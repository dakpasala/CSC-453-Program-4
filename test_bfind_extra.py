#!/usr/bin/env python3

import os
import subprocess
import tempfile
import sys

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

BFIND = "./bfind"

passed = 0
failed = 0


def run(args, cwd=None):
    try:
        p = subprocess.run(
            [BFIND] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            timeout=5
        )
        lines = [l for l in p.stdout.strip().split("\n") if l]
        return p.returncode, lines
    except subprocess.TimeoutExpired:
        return -1, []


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"{GREEN}[PASS]{RESET} {name}")
    else:
        failed += 1
        print(f"{RED}[FAIL]{RESET} {name}")
        if detail:
            print("   ", detail)


print("\n=== Extra bfind Tests ===\n")

with tempfile.TemporaryDirectory() as tmp:

    # ----------------------------------------------------
    # Deep BFS traversal
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/deep/a/b/c/d")

    open(f"{tmp}/deep/root.txt", "w").close()
    open(f"{tmp}/deep/a/a.txt", "w").close()
    open(f"{tmp}/deep/a/b/b.txt", "w").close()
    open(f"{tmp}/deep/a/b/c/c.txt", "w").close()

    rc, lines = run([f"{tmp}/deep"])

    base_depth = f"{tmp}/deep".count("/")
    depths = [l.count("/") - base_depth for l in lines]

    check(
        "Deep BFS ordering",
        all(depths[i] <= depths[i+1] for i in range(len(depths)-1)),
        depths
    )

    # ----------------------------------------------------
    # Multiple start paths
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/multi1")
    os.makedirs(f"{tmp}/multi2")

    open(f"{tmp}/multi1/a.txt", "w").close()
    open(f"{tmp}/multi2/b.txt", "w").close()

    rc, lines = run([f"{tmp}/multi1", f"{tmp}/multi2"])

    check(
        "Multiple start paths",
        f"{tmp}/multi1/a.txt" in lines and f"{tmp}/multi2/b.txt" in lines
    )

    # ----------------------------------------------------
    # Complex symlink cycle
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/cycle/a/b")

    open(f"{tmp}/cycle/a/file.txt", "w").close()

    os.symlink("../", f"{tmp}/cycle/a/b/up")
    os.symlink("../../a", f"{tmp}/cycle/a/b/back")

    rc, lines = run(["-L", f"{tmp}/cycle"])

    check(
        "Complex symlink cycle detection",
        rc == 0 and len(lines) > 0
    )

    # ----------------------------------------------------
    # Name filter + symlink traversal
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/linktest/real")

    open(f"{tmp}/linktest/real/code.c", "w").close()
    open(f"{tmp}/linktest/real/file.txt", "w").close()

    os.symlink("real", f"{tmp}/linktest/link")

    rc, lines = run(["-L", f"{tmp}/linktest", "-name", "*.c"])

    check(
        "Filters still work when following symlinks",
        any("code.c" in l for l in lines)
    )

    # ----------------------------------------------------
    # Multiple filters
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/combo")

    with open(f"{tmp}/combo/a.c", "wb") as f:
        f.write(b"x" * 500)

    with open(f"{tmp}/combo/b.c", "wb") as f:
        f.write(b"x" * 5000)

    rc, lines = run([f"{tmp}/combo", "-name", "*.c", "-size", "+1k"])

    check(
        "Multiple filters combined",
        len(lines) == 1 and "b.c" in lines[0]
    )

    # ----------------------------------------------------
    # Weird filenames
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/weird")

    open(f"{tmp}/weird/file with space.txt", "w").close()
    open(f"{tmp}/weird/#special!.txt", "w").close()

    rc, lines = run([f"{tmp}/weird"])

    check(
        "Handles weird filenames",
        any("space" in l for l in lines) and any("#special" in l for l in lines)
    )

    # ----------------------------------------------------
    # Directory type filter
    # ----------------------------------------------------

    os.makedirs(f"{tmp}/typetest/dir")

    open(f"{tmp}/typetest/file.txt", "w").close()

    rc, lines = run([f"{tmp}/typetest", "-type", "d"])

    check(
        "-type d only returns directories",
        all(os.path.isdir(l) for l in lines)
    )


print("\n=== Results ===")
total = passed + failed

print(f"Passed: {passed}/{total}")

if failed:
    print(f"{RED}Failed: {failed}/{total}{RESET}")
else:
    print(f"{GREEN}All tests passed!{RESET}")

sys.exit(0 if failed == 0 else 1)