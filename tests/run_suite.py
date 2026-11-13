"""The whole suite, timed. Run from anywhere: python3 tests/run_suite.py"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEPS = [
    ("helpers: money, percent, bar, parse_cents, is_date, parse_fields vs oracles", ["tests.test_units"]),
    ("behaviour: whole reports vs the csv + decimal oracle, 3 engines, fuzz", ["tests.test_data"]),
    ("gap probes: what NovaLang lacks, pinned so docs/GAPS.md cannot rot", ["tests.test_gaps"]),
    ("sandbox: restricted profile, read-only, default limits, the ceiling", ["tests.test_sandbox"]),
]
failed = False
total = 0
for title, modules in STEPS:
    started = time.time()
    done = subprocess.run([sys.executable, "-m", "unittest"] + modules, cwd=ROOT, capture_output=True, text=True)
    ran = [l for l in done.stderr.splitlines() if l.startswith("Ran ")]
    if ran:
        total += int(ran[0].split()[1])
    print("%-78s %5.1fs  exit %d  %s" % (title, time.time() - started, done.returncode, ran[0] if ran else ""))
    if done.returncode:
        failed = True
        print(done.stderr)
print("%d tests, %s" % (total, "RED" if failed else "GREEN"))
sys.exit(1 if failed else 0)
