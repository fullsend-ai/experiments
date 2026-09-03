#!/usr/bin/env python3
"""Filesystem policy probe for OpenShell sandbox.

Runs 24 assertions against the active Landlock policy and
emits one JSON line per test to stdout. Always exits 0 so the
host orchestrator can parse results even when assertions fail.
"""

import errno
import json
import os


OVERLAP_BASE = "/sandbox/workspace/target-repo"


def emit(test_id, cat, op, path, expect, actual, passed,
         detail=""):
    print(
        json.dumps(
            {
                "id": test_id,
                "cat": cat,
                "op": op,
                "path": path,
                "expect": expect,
                "actual": actual,
                "pass": passed,
                "detail": detail,
            }
        ),
        flush=True,
    )


def ename(code):
    return errno.errorcode.get(code, f"errno={code}")


def try_read(path):
    try:
        if os.path.isdir(path):
            os.listdir(path)
        else:
            with open(path, "rb") as f:
                f.read(1)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_write(path, content=b"probe-test\n"):
    try:
        with open(path, "wb") as f:
            f.write(content)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_write_readback(path, content=b"probe-test\n"):
    actual, detail = try_write(path, content)
    if actual != "ok":
        return actual, detail
    try:
        with open(path, "rb") as f:
            got = f.read()
        if got != content:
            return "MISMATCH", f"wrote {content!r}, read {got!r}"
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), f"readback failed: {exc}"


def try_mkdir(path):
    try:
        os.mkdir(path)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_listdir(path):
    try:
        os.listdir(path)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_unlink(path):
    try:
        os.unlink(path)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_symlink_write(link_path, target, content=b"x\n"):
    try:
        os.symlink(target, link_path)
    except OSError as exc:
        return ename(exc.errno), f"symlink failed: {exc}"
    try:
        with open(link_path, "wb") as f:
            f.write(content)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def check(test_id, cat, op, path, expect, result):
    actual, detail = result
    emit(test_id, cat, op, path, expect, actual,
         actual == expect, detail)


def run_overlap():
    tr = OVERLAP_BASE
    check("1.1", "overlap", "read", f"{tr}/README.md", "ok",
          try_read(f"{tr}/README.md"))
    check("1.2", "overlap", "listdir", f"{tr}/", "ok",
          try_listdir(tr))
    check("1.3", "overlap", "write", f"{tr}/README.md",
          "EACCES", try_write(f"{tr}/README.md"))
    check("1.4", "overlap", "create", f"{tr}/new-file.txt",
          "EACCES", try_write(f"{tr}/new-file.txt"))
    check("1.5", "overlap", "mkdir", f"{tr}/newdir/",
          "EACCES", try_mkdir(f"{tr}/newdir"))
    sibling = "/sandbox/workspace/other-project"
    os.makedirs(sibling, exist_ok=True)
    check("1.6", "overlap", "write",
          f"{sibling}/file.txt", "ok",
          try_write(f"{sibling}/file.txt"))
    check("1.7", "overlap", "write",
          "/sandbox/workspace/file.txt", "ok",
          try_write("/sandbox/workspace/file.txt"))


def run_readwrite():
    check("2.1", "rw", "write+read", "/sandbox/test-rw",
          "ok", try_write_readback("/sandbox/test-rw"))
    check("2.2", "rw", "write+read", "/tmp/test-rw",
          "ok", try_write_readback("/tmp/test-rw"))
    check("2.3", "rw", "write", "/dev/null",
          "ok", try_write("/dev/null"))
    check("2.4", "rw", "mkdir", "/sandbox/newdir/",
          "ok", try_mkdir("/sandbox/newdir"))


def run_readonly():
    check("3.1", "ro", "read", "/usr/bin/ls",
          "ok", try_read("/usr/bin/ls"))
    check("3.2", "ro", "write", "/usr/test-write",
          "EACCES", try_write("/usr/test-write"))
    check("3.3", "ro", "read", "/etc/hostname",
          "ok", try_read("/etc/hostname"))
    check("3.4", "ro", "write", "/etc/test-write",
          "EACCES", try_write("/etc/test-write"))
    check("3.5", "ro", "read", "/proc/self/status",
          "ok", try_read("/proc/self/status"))
    check("3.6", "ro", "read", "/dev/urandom",
          "ok", try_read("/dev/urandom"))


def run_deny():
    check("4.1", "deny", "read", "/home/",
          "EACCES", try_listdir("/home"))
    check("4.2", "deny", "read", "/root/",
          "EACCES", try_listdir("/root"))
    check("4.3", "deny", "read", "/opt/",
          "EACCES", try_listdir("/opt"))
    check("4.4", "deny", "write", "/opt/test-write",
          "EACCES", try_write("/opt/test-write"))


def run_edge():
    check("5.1", "edge", "symlink_write",
          "/tmp/link-to-etc-passwd", "EACCES",
          try_symlink_write("/tmp/link-to-etc-passwd",
                            "/etc/passwd"))
    traversal = (
        "/sandbox/workspace/target-repo/../other/file"
    )
    os.makedirs("/sandbox/workspace/other", exist_ok=True)
    check("5.2", "edge", "traversal_write",
          traversal, "ok", try_write(traversal))
    check("5.3", "edge", "delete",
          f"{OVERLAP_BASE}/README.md", "EACCES",
          try_unlink(f"{OVERLAP_BASE}/README.md"))


def main():
    run_overlap()
    run_readwrite()
    run_readonly()
    run_deny()
    run_edge()


if __name__ == "__main__":
    main()
