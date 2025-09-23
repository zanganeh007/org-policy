#!/usr/bin/env python3
"""
Generic org-wide policy checker (language-agnostic).

Enforces:
  1) Presence of the canonical guide in the target repo under one of:
     - docs/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md
     - .github/policy/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md
  2) The guide must contain anchors "Principle 1:" .. "Principle 18:".
  3) Presence of a machine-readable compliance manifest:
     - policy/compliance.json  with:
       {
         "project": "...",
         "run_id": "...",
         "principles": { "P1": true, ..., "P18": true }
       }
     All P1..P18 must exist and be true. (می‌توان بعداً آستانه گذاشت.)
Exit codes: 0 OK, 2 violations, 1 unexpected error.
"""
from __future__ import annotations
import json, sys, pathlib, traceback

CANON_PATHS = [
    "docs/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md",
    ".github/policy/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md",
]
COMPLIANCE_JSON = pathlib.Path("policy/compliance.json")
PRINCIPLES = [f"Principle {i}:" for i in range(1, 19)]

def fail(msg: str, code: int = 2) -> None:
    print(f"FAIL: {msg}")
    sys.exit(code)

def main() -> None:
    # 1) guide presence
    guide_path = None
    for p in CANON_PATHS:
        if pathlib.Path(p).exists():
            guide_path = pathlib.Path(p)
            break
    if not guide_path:
        fail(f"Guide not found in any of: {', '.join(CANON_PATHS)}")

    # 2) anchors P1..P18
    try:
        txt = guide_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        traceback.print_exc()
        sys.exit(1)

    missing = [k for k in PRINCIPLES if k not in txt]
    if missing:
        fail(f"Guide missing anchors: {', '.join(missing)}")

    # 3) compliance manifest
    if not COMPLIANCE_JSON.exists():
        fail(f"Missing compliance manifest: {COMPLIANCE_JSON}")

    try:
        data = json.loads(COMPLIANCE_JSON.read_text(encoding="utf-8"))
    except Exception:
        traceback.print_exc()
        fail("Malformed compliance.json (invalid JSON)")

    if not isinstance(data, dict):
        fail("compliance.json must be an object")

    pr = data.get("principles")
    if not isinstance(pr, dict):
        fail("compliance.json.principles must be an object")

    missing_keys = [f"P{i}" for i in range(1, 19) if f"P{i}" not in pr]
    if missing_keys:
        fail(f"compliance.principles missing keys: {', '.join(missing_keys)}")

    false_keys = [k for k, v in pr.items() if k.startswith("P") and v is False]
    if false_keys:
        fail(f"non-compliant principles: {', '.join(sorted(false_keys))}")

    print(json.dumps({"ok": True, "guide": str(guide_path), "principles": "P1..P18"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
