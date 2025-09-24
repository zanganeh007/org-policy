#!/usr/bin/env python3
"""
Generic org-wide policy checker (language-agnostic).

Enforces, in the CURRENT working directory (target repo):
  1) Presence of the canonical guide in one of:
     - docs/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md
     - .github/policy/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md
     (Or a custom path via --guide)
  2) The guide must contain anchors exactly: "Principle 1:" .. "Principle 18:".
  3) Presence of a machine-readable compliance manifest at:
       policy/compliance.json
     Schema (minimal):
       {
         "project": "<string>",
         "run_id": "<string>",
         "principles": { "P1": true, ..., "P18": true }
       }
     All P1..P18 must exist and be boolean true.

Exit codes:
  0  → OK
  2  → Policy violations
  1  → Unexpected error (I/O, JSON decode error, etc.)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

# ----------------------------- Constants ------------------------------------ #

CANON_PATHS: tuple[str, ...] = (
    "docs/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md",
    ".github/policy/MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md",
)
COMPLIANCE_JSON = Path("policy/compliance.json")
PRINCIPLES: tuple[str, ...] = tuple(f"Principle {i}:" for i in range(1, 19))

EXIT_OK = 0
EXIT_VIOLATION = 2
EXIT_ERROR = 1


# ----------------------------- Helpers -------------------------------------- #


def _eprint(msg: str) -> None:
    """Print to stderr."""
    print(msg, file=sys.stderr)


def fail(msg: str, code: int = EXIT_VIOLATION) -> int:
    """Return a failure exit code after logging a FAIL message."""
    _eprint(f"FAIL: {msg}")
    return code


def _find_guide(custom: Optional[str]) -> Optional[Path]:
    """Return the resolved guide path or None if not found."""
    if custom:
        p = Path(custom)
        return p if (p.exists() and p.is_file() and p.stat().st_size > 0) else None
    for p in CANON_PATHS:
        pp = Path(p)
        if pp.exists() and pp.is_file() and pp.stat().st_size > 0:
            return pp
    return None


def _missing_anchors(text: str, anchors: Iterable[str]) -> list[str]:
    """Return the list of anchors missing from text."""
    return [a for a in anchors if a not in text]


def _validate_manifest_schema(obj: object) -> Optional[str]:
    """
    Validate minimal schema of compliance.json.

    Returns:
        None if valid; otherwise a human-readable violation message.
    """
    if not isinstance(obj, dict):
        return "compliance.json root must be an object"

    project = obj.get("project")
    run_id = obj.get("run_id")
    principles = obj.get("principles")

    if not isinstance(project, str) or not project.strip():
        return "compliance.json.project must be a non-empty string"
    if not isinstance(run_id, str) or not run_id.strip():
        return "compliance.json.run_id must be a non-empty string"
    if not isinstance(principles, dict):
        return "compliance.json.principles must be an object"

    # Ensure all P1..P18 exist and are True
    missing = [f"P{i}" for i in range(1, 19) if f"P{i}" not in principles]
    if missing:
        return f"compliance.principles missing keys: {', '.join(missing)}"

    not_true = [k for k in (f"P{i}" for i in range(1, 19)) if principles.get(k) is not True]
    if not_true:
        return f"non-compliant principles (must be true): {', '.join(not_true)}"

    return None


# ------------------------------ Main ---------------------------------------- #


def run(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify presence and completeness of the enterprise coding principles guide "
        "and compliance manifest."
    )
    parser.add_argument(
        "--guide",
        help="Optional explicit path to MULTI_DOCUMENT_ENTERPRISE_CODING_PRINCIPLES_GUIDE.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON result on success or failure.",
    )
    args = parser.parse_args(argv)

    # 1) Guide presence (with optional override)
    guide_path = _find_guide(args.guide)
    if not guide_path:
        msg = (
            f"Guide not found. Checked: "
            f"{(args.guide or 'N/A (no --guide)')}, "
            f"{', '.join(CANON_PATHS)}; "
            f"files must exist and be non-empty."
        )
        if args.json:
            print(json.dumps({"ok": False, "error": msg, "code": EXIT_VIOLATION}))
            return EXIT_VIOLATION
        return fail(msg, EXIT_VIOLATION)

    # 2) Anchors P1..P18
    try:
        text = guide_path.read_text(encoding="utf-8", errors="strict")
    except Exception as exc:  # unexpected I/O
        msg = f"Failed to read guide '{guide_path}': {exc!s}"
        if args.json:
            print(json.dumps({"ok": False, "error": msg, "code": EXIT_ERROR}))
            return EXIT_ERROR
        _eprint(msg)
        return EXIT_ERROR

    missing = _missing_anchors(text, PRINCIPLES)
    if missing:
        msg = f"Guide missing required anchors: {', '.join(missing)}"
        if args.json:
            print(json.dumps({"ok": False, "error": msg, "code": EXIT_VIOLATION, "guide": str(guide_path)}))
            return EXIT_VIOLATION
        return fail(msg, EXIT_VIOLATION)

    # 3) compliance manifest
    if not COMPLIANCE_JSON.exists():
        msg = f"Missing compliance manifest: {COMPLIANCE_JSON}"
        if args.json:
            print(json.dumps({"ok": False, "error": msg, "code": EXIT_VIOLATION, "guide": str(guide_path)}))
            return EXIT_VIOLATION
        return fail(msg, EXIT_VIOLATION)

    try:
        manifest_obj = json.loads(COMPLIANCE_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        msg = f"Malformed compliance.json (invalid JSON): {exc!s}"
        if args.json:
            print(json.dumps({"ok": False, "error": msg, "code": EXIT_ERROR, "manifest": str(COMPLIANCE_JSON)}))
            return EXIT_ERROR
        _eprint(msg)
        return EXIT_ERROR

    schema_err = _validate_manifest_schema(manifest_obj)
    if schema_err:
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": schema_err,
                        "code": EXIT_VIOLATION,
                        "manifest": str(COMPLIANCE_JSON),
                        "guide": str(guide_path),
                    }
                )
            )
            return EXIT_VIOLATION
        return fail(schema_err, EXIT_VIOLATION)

    # Success
    result = {
        "ok": True,
        "guide": str(guide_path),
        "manifest": str(COMPLIANCE_JSON),
        "principles": "P1..P18",
    }
    print(json.dumps(result))
    return EXIT_OK


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
