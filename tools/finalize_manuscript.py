#!/usr/bin/env python3
"""
finalize_manuscript.py
======================
Produces the submission file from the working manuscript.

The working file, `manuscript/manuscript_CLEAN.docx`, carries every revision
round as tracked changes so collaborators can see what moved. A journal needs
the resolved text. This script writes `manuscript/manuscript_SUBMISSION.docx`
with all changes accepted, deleted text gone, and comments removed.

The working file is never modified. Run the validation gate against the
submission file afterwards, which `--validate` does for you.

Run
    python tools/finalize_manuscript.py
    python tools/finalize_manuscript.py --validate
"""

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_tracked import TrackedDocument  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKING = os.path.join(BASE_DIR, "manuscript", "manuscript_CLEAN.docx")
SUBMISSION = os.path.join(BASE_DIR, "manuscript", "manuscript_SUBMISSION.docx")

#: Editorial scaffolding that must not survive into a submission file.
AUTHOR_NOTE = re.compile(
    r"^\s*(\[?(AUTHOR|EDITOR|TODO|NOTE|DRAFT|COMMENT)\b[^\]]*\]?|"
    r"\[to be (added|confirmed|completed)\]|XXX+)\s*$", re.I)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true",
                    help="run code/12_manuscript_numbers.py against the result")
    args = ap.parse_args()

    if not os.path.exists(WORKING):
        sys.exit(f"Working manuscript not found at {WORKING}")

    doc = TrackedDocument(WORKING, author="finalize")
    print("=" * 72)
    print("  FINALIZE MANUSCRIPT")
    print("=" * 72)
    print(f"  source: {os.path.relpath(WORKING, BASE_DIR)}")
    print("  revision rounds present:")
    for (author, date), n in doc.revision_summary():
        print(f"    {author or '(none)':<16} {date:<12} {n:>4} changes")

    counts = doc.accept_all()
    print()
    for k, v in counts.items():
        print(f"  {k.replace('_', ' '):<26} {v:>5}")

    notes = [t for t in (doc.accepted_text(p).strip() for p in doc.paragraphs())
             if t and AUTHOR_NOTE.match(t)]
    if notes:
        print(f"\n  WARNING: {len(notes)} paragraph(s) look like author notes:")
        for t in notes[:8]:
            print(f"    {t[:88]}")
        print("  Review these by hand; they are not removed automatically.")

    doc.save(SUBMISSION)
    print(f"\n  wrote {os.path.relpath(SUBMISSION, BASE_DIR)}")

    verify = TrackedDocument(SUBMISSION, author="verify")
    remaining = verify.revision_summary()
    print(f"  tracked changes remaining: "
          f"{sum(n for _, n in remaining) if remaining else 0}")

    if args.validate:
        print("\n  running the validation gate against the submission file...")
        env = dict(os.environ, MANUSCRIPT_OVERRIDE=SUBMISSION)
        r = subprocess.run([sys.executable,
                            os.path.join(BASE_DIR, "code", "12_manuscript_numbers.py")],
                           cwd=BASE_DIR, env=env, capture_output=True, text=True)
        report = os.path.join(BASE_DIR, "output", "validation", "manuscript_check.txt")
        if os.path.exists(report):
            head = open(report).read().splitlines()[:6]
            print("\n".join("  " + line for line in head))
        if r.returncode != 0:
            print(r.stderr[-800:])
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
