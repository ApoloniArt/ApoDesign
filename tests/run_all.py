"""Runs every ApoDesign test and prints one clear PASS / FAIL line per test.

Normally started by RUN_TESTS.bat. It also saves everything it prints to
test_results.txt next to this file, so you can send that file back.
"""
import importlib
import os
import platform
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = []


def say(text=""):
    try:
        print(text)
    except UnicodeEncodeError:          # old Windows consoles
        print(text.encode("ascii", "replace").decode("ascii"))
    LOG.append(text)


def run_module(name):
    try:
        mod = importlib.import_module(name)
    except ImportError as e:
        if "torch" in str(e):
            say("SKIPPED  %s  (%s)" % (name, e))
            return 0, 0, 1
        say("FAIL     %s could not be loaded" % name)
        for line in traceback.format_exc().strip().splitlines()[-6:]:
            say("            " + line)
        return 0, 1, 0
    ok = bad = 0
    for tname in sorted(n for n in dir(mod) if n.startswith("test_")):
        t0 = time.time()
        try:
            getattr(mod, tname)()
            ok += 1
            say("PASS     %-55s %5.1fs" % (tname, time.time() - t0))
        except Exception:
            bad += 1
            say("FAIL     %s" % tname)
            for line in traceback.format_exc().strip().splitlines()[-6:]:
                say("            " + line)
    return ok, bad, 0


def main():
    say("ApoDesign tests - %s" % time.strftime("%Y-%m-%d %H:%M"))
    say("Python %s on %s" % (platform.python_version(), platform.platform()))
    try:
        import torch
        say("torch %s" % torch.__version__)
    except ImportError:
        say("torch NOT FOUND - the engine tests will be skipped")
    say("")
    total_ok = total_bad = total_skip = 0
    for name in ("test_pure", "test_fonts", "test_torch"):
        ok, bad, skip = run_module(name)
        total_ok, total_bad, total_skip = total_ok + ok, total_bad + bad, total_skip + skip
    say("")
    if total_bad == 0 and total_skip == 0:
        say("RESULT: ALL %d TESTS PASSED" % total_ok)
    else:
        say("RESULT: %d passed, %d FAILED, %d skipped" % (total_ok, total_bad, total_skip))
        say("Please send me the file test_results.txt (or paste this window).")
    with open(os.path.join(HERE, "test_results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
