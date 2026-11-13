#!/usr/bin/env bash
# One PASS/FAIL line per test + a total, for one service or both.
# Usage: bash run_tests.sh [script|mark] [extra pytest arguments, e.g. -m m1]
set -u
cd "$(dirname "$0")" || exit 1
PY=${PY:-python3}
which_service=${1:-all}
case "$which_service" in script|mark) shift ;; *) which_service=all ;; esac
services=(script mark); [ "$which_service" != all ] && services=("$which_service")
status=0
for svc in "${services[@]}"; do
  REPORT=$(mktemp -t scriptchain_junit_XXXXXX.xml)
  (cd "services/$svc" && $PY -m pytest -q --tb=no -p no:cacheprovider --junitxml="$REPORT" "$@" > /dev/null 2>&1)
  echo "=== $svc service"
  $PY - "$REPORT" <<'PYEOF' || status=1
import sys
import xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except (OSError, ET.ParseError):
    print("FAIL pytest could not start (import error?) -- run: make test-" + "service")
    sys.exit(1)
passed = failed = 0
for case in root.iter("testcase"):
    parts = case.get("classname", "").split(".")
    name = "::".join(x for x in ("/".join(parts[:2]) + ".py", "::".join(parts[2:]), case.get("name")) if x)
    if case.find("failure") is not None or case.find("error") is not None:
        failed += 1; print(f"FAIL {name}")
    elif case.find("skipped") is not None:
        print(f"SKIP {name}")
    else:
        passed += 1; print(f"PASS {name}")
print(f"total: {passed} passed, {failed} failed")
sys.exit(1 if failed or passed + failed == 0 else 0)
PYEOF
  rm -f "$REPORT"
done
exit $status
