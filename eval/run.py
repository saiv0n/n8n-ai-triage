"""Send every message in messages.json to the triage webhook and score the answers.

    python eval/run.py http://localhost:5678/webhook/triage [seconds between messages]

Free model tiers allow about 15 requests a minute, so pass 5 there.

Uses only the standard library, so it runs anywhere Python 3.10+ does.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent


def post(url: str, payload: dict, timeout: float = 150) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def check(expect: dict, got: dict) -> list[str]:
    problems = []
    if got.get("category") != expect["category"]:
        problems.append(f"category {got.get('category')!r}, expected {expect['category']!r}")
    score = got.get("lead_score")
    if "min_score" in expect and (score is None or score < expect["min_score"]):
        problems.append(f"lead_score {score}, expected >= {expect['min_score']}")
    if "max_score" in expect and score is not None and score > expect["max_score"]:
        problems.append(f"lead_score {score}, expected <= {expect['max_score']}")
    for key in ("urgency", "language"):
        if key in expect and got.get(key) != expect[key]:
            problems.append(f"{key} {got.get(key)!r}, expected {expect[key]!r}")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    url = argv[1]
    delay = float(argv[2]) if len(argv) == 3 else 0
    cases = json.loads((HERE / "messages.json").read_text(encoding="utf-8"))
    passed, rows = 0, []
    for n, case in enumerate(cases):
        if n and delay:
            time.sleep(delay)
        t = time.monotonic()
        try:
            got = post(url, case["input"])
            problems = check(case["expect"], got)
        except Exception as e:  # report and keep going, one bad case shouldn't hide the rest
            got, problems = {}, [f"request failed: {e}"]
        ms = (time.monotonic() - t) * 1000
        passed += not problems
        mark = "pass" if not problems else "FAIL"
        print(f"{mark}  {case['id']:<20} {got.get('category', '-'):<12} score {str(got.get('lead_score', '-')):>3}  "
              f"{ms:5.0f} ms  {'; '.join(problems)}")
        rows.append({"id": case["id"], "passed": not problems, "problems": problems, "got": got, "ms": round(ms)})
    print(f"\n{passed}/{len(cases)} passed")
    (HERE / "last-run.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
