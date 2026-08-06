#!/usr/bin/env python3
"""
revise_manuscript.py
====================
Applies a dated round of tracked changes to the manuscript.

Each round is a list of edits declared below. Running this script twice is safe:
an edit whose target text is already gone is reported as "already applied" and
skipped, so a round is idempotent.

Every edit records *why* it was made. Corrections of fact cite the generated
output that establishes them, so a reviewer can trace any wording change back to
a number the pipeline produces.

Run
    python tools/revise_manuscript.py            # apply, then re-validate
    python tools/revise_manuscript.py --dry-run  # report what would change

After applying, always re-run the validation gate:
    python code/12_manuscript_numbers.py
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_tracked import AnchorNotFound, TrackedDocument  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUSCRIPT = os.path.join(BASE_DIR, "manuscript", "manuscript_CLEAN.docx")

AUTHOR = "Abdul Razak"
DATE = "2026-08-06T12:00:00Z"

# Each edit: (locator, old_text, new_text, rationale)
# `locator` need only be long enough to identify the paragraph uniquely.
EDITS = [
    (
        "fell monotonically across EDI quintiles",
        "CMR rates fell monotonically across EDI quintiles",
        "Mean county-level CMR rates declined across EDI quintiles",
        "The decline is not monotonic. Mean rates by quintile are 0.2715, "
        "0.1491, 0.1870, 0.0806, 0.0622: Q3 exceeds Q2 by 0.038. See "
        "output/validation/manuscript_numbers.json -> quintiles. The word "
        "'monotonically' also duplicated the Spearman result reported earlier "
        "in the same section.",
    ),
    (
        "a 4.4-fold gradient (Kruskal-Wallis",
        "a 4.4-fold gradient",
        "a 4.4-fold difference between the extreme quintiles",
        "'Gradient' implies a monotonic trend that the quintile means do not "
        "show. The quantity reported is the ratio of the Q1 and Q5 means.",
    ),
    (
        "statsmodels 0.14 and SciPy 1.11",
        "statsmodels 0.14 and SciPy 1.11",
        "statsmodels 0.14 and SciPy 1.13",
        "The committed results were produced under SciPy 1.13.0 "
        "(Python 3.11.7, statsmodels 0.14.6, NumPy 1.26.4).",
    ),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing")
    args = ap.parse_args()

    if not os.path.exists(MANUSCRIPT):
        sys.exit(f"Manuscript not found at {MANUSCRIPT}")

    doc = TrackedDocument(MANUSCRIPT, author=AUTHOR, date=DATE)

    print("=" * 74)
    print(f"  TRACKED REVISION ROUND   {AUTHOR}   {DATE[:10]}")
    print("=" * 74)
    print(f"  Document: {os.path.relpath(MANUSCRIPT, BASE_DIR)}")
    print("  Existing revision rounds in this file:")
    for (author, date), count in doc.revision_summary():
        print(f"    {author or '(none)':<16} {date:<12} {count:>4} changes")
    print()

    applied = skipped = 0
    for locator, old, new, why in EDITS:
        try:
            para = doc.find_paragraph(locator)
        except AnchorNotFound:
            print(f"  SKIP  already applied, or text absent: {locator!r}")
            skipped += 1
            continue
        if old not in doc.accepted_text(para):
            print(f"  SKIP  already applied: {old!r}")
            skipped += 1
            continue
        if not args.dry_run:
            doc.replace(para, old, new)
        applied += 1
        print(f"  EDIT  {old!r}")
        print(f"     -> {new!r}")
        for line in _wrap(why, 66):
            print(f"        {line}")
        print()

    print("-" * 74)
    print(f"  {applied} applied, {skipped} skipped")
    if args.dry_run:
        print("  Dry run: nothing written.")
        return
    if applied:
        doc.save()
        print(f"  Written to {os.path.relpath(MANUSCRIPT, BASE_DIR)}")
        print(f"  Backup at  {os.path.relpath(MANUSCRIPT, BASE_DIR)}.bak")
        print()
        print("  Now re-run the validation gate:")
        print("    python code/12_manuscript_numbers.py")


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    main()
