#!/usr/bin/env python3

import os
import subprocess
import tempfile
import time
import sys

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

BFIND = "./bfind"

passed = 0
failed = 0


def run(args, cwd=None, timeout=5):
    try:
        p = subprocess.run(
            [BFIND] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            timeout=timeout
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


print("\n=== EVIL bfind Tests ===\n")

with tempfile.TemporaryDirectory() as tmp:

    # ------------------------------------------------
    # 1. Massive fan-out directory
    # ------------------------------------------------

    fan = f"{tmp}/fan"
    os.makedirs(fan)

    for i in range(200):
        open(f"{fan}/file{i}.txt", "w").close()

    rc, lines = run([fan])

    check(
        "Handles large directory fan-out",
        len(lines) == 201
    )

    # ------------------------------------------------
    # 2. Deep directory chain
    # ------------------------------------------------

    deep = f"{tmp}/deep"
    cur = deep

    for i in range(50):
        cur = f"{cur}/d{i}"
        os.makedirs(cur)

    open(f"{cur}/end.txt", "w").close()

    rc, lines = run([deep])

    check(
        "Handles very deep directory chains",
        any("end.txt" in l for l in lines)
    )

    # ------------------------------------------------
    # 3. Multiple symlinks to same directory
    # ------------------------------------------------

    same = f"{tmp}/same"
    os.makedirs(f"{same}/real")

    open(f"{same}/real/file.txt", "w").close()

    os.symlink("real", f"{same}/link1")
    os.symlink("real", f"{same}/link2")
    os.symlink("real", f"{same}/link3")

    rc, lines = run(["-L", same])

    count = sum("file.txt" in l for l in lines)

    check(
        "Multiple symlinks to same target",
        count >= 1
    )

    # ------------------------------------------------
    # 4. Symlink pointing to file
    # ------------------------------------------------

    filelink = f"{tmp}/filelink"
    os.makedirs(filelink)

    open(f"{filelink}/data.txt", "w").close()

    os.symlink("data.txt", f"{filelink}/sym")

    rc, lines = run(["-L", filelink])

    check(
        "Symlink to file handled correctly",
        any("sym" in l for l in lines)
    )

    # ------------------------------------------------
    # 5. mtime boundary test
    # ------------------------------------------------

    mtime = f"{tmp}/mtime"
    os.makedirs(mtime)

    open(f"{mtime}/recent.txt", "w").close()

    oldfile = f"{mtime}/old.txt"
    open(oldfile, "w").close()

    # make old file 3 days old
    old = time.time() - (3 * 86400)
    os.utime(oldfile, (old, old))

    rc, lines = run([mtime, "-mtime", "1"])

    check(
        "mtime boundary behavior",
        any("recent.txt" in l for l in lines)
    )

    # ------------------------------------------------
    # 6. Permission exact match
    # ------------------------------------------------

    perm = f"{tmp}/perm"
    os.makedirs(perm)

    f = f"{perm}/secret.txt"
    open(f, "w").close()

    os.chmod(f, 0o600)

    rc, lines = run([perm, "-perm", "600"])

    check(
        "Exact permission matching",
        any("secret.txt" in l for l in lines)
    )

    # ------------------------------------------------
    # 7. Size boundary
    # ------------------------------------------------

    size = f"{tmp}/size"
    os.makedirs(size)

    with open(f"{size}/small.bin", "wb") as f:
        f.write(b"x" * 1024)

    with open(f"{size}/big.bin", "wb") as f:
        f.write(b"x" * 5000)

    rc, lines = run([size, "-size", "+1k"])

    check(
        "Size comparison boundaries",
        any("big.bin" in l for l in lines)
    )

    # ------------------------------------------------
    # 8. Weird nested symlink cycles
    # ------------------------------------------------

    cyc = f"{tmp}/crazy"
    os.makedirs(f"{cyc}/a/b/c")

    os.symlink("../../", f"{cyc}/a/b/c/up")
    os.symlink("../c", f"{cyc}/a/b/loop")

    open(f"{cyc}/a/file.txt", "w").close()

    rc, lines = run(["-L", cyc], timeout=5)

    check(
        "Crazy nested symlink cycles don't infinite loop",
        rc != -1
    )

    # ------------------------------------------------
    # 9. Empty directory
    # ------------------------------------------------

    empty = f"{tmp}/empty"
    os.makedirs(empty)

    rc, lines = run([empty])

    check(
        "Empty directory handled",
        lines == [empty]
    )

    # ------------------------------------------------
    # 10. Multiple filters extreme
    # ------------------------------------------------

    combo = f"{tmp}/combo"
    os.makedirs(combo)

    with open(f"{combo}/a.c", "wb") as f:
        f.write(b"x" * 500)

    with open(f"{combo}/b.c", "wb") as f:
        f.write(b"x" * 5000)

    with open(f"{combo}/c.txt", "wb") as f:
        f.write(b"x" * 5000)

    rc, lines = run([combo, "-name", "*.c", "-size", "+1k"])

    check(
        "Extreme combined filters",
        len(lines) == 1 and "b.c" in lines[0]
    )


print("\n=== Results ===")

total = passed + failed

print(f"Passed: {passed}/{total}")

if failed:
    print(f"{RED}Failed: {failed}/{total}{RESET}")
else:
    print(f"{GREEN}All EVIL tests passed!{RESET}")

sys.exit(0 if failed == 0 else 1)