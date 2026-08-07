#!/usr/bin/env python3
"""
docx_tracked.py
===============
Apply edits to a Word document as *tracked changes*, so that every revision
round stays reviewable in Word's Reviewing Pane, attributed to an author and a
date.

Why this exists
---------------
The manuscript is a single file that accumulates revision rounds from several
people. Editing it by hand loses the audit trail, and keeping parallel CLEAN and
TRACKED copies has caused version confusion before. This module edits the
document in place and records each change as a `w:ins` or `w:del` element, which
is exactly what Word itself writes. Accepting all changes yields the submission
version.

What it handles
---------------
Word splits a sentence across arbitrarily many `w:r` runs, and text from an
earlier revision round is already wrapped in `w:ins`. A naive string replacement
in `document.xml` therefore fails on most real paragraphs. The traversal here
works on the *accepted text* of a paragraph — what you would see after accepting
every existing change — and maps offsets in that string back to the runs that
produce it, splitting runs and `w:ins` wrappers as needed.

Deleting text that another author inserted nests the `w:del` inside their
`w:ins`, so the record reads "inserted by X, later deleted by Y" rather than
silently reassigning authorship.

Usage
-----
    from docx_tracked import TrackedDocument

    doc = TrackedDocument("manuscript.docx", author="Abdul Razak")
    para = doc.find_paragraph("CMR rates fell monotonically")
    doc.replace(para, "fell monotonically across", "declined across")
    doc.save("manuscript.docx")

Limitations
-----------
Operates on `word/document.xml` only. Text inside footnotes, endnotes, headers,
and text boxes is not reachable. Edits are confined to a single paragraph; to
change text spanning a paragraph break, edit each paragraph separately.
"""

from __future__ import annotations

import copy
import datetime as _dt
import re
import shutil
import zipfile

from lxml import etree

__all__ = ["TrackedDocument", "AnchorNotFound"]

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _w(tag: str) -> str:
    return f"{{{_W}}}{tag}"


class AnchorNotFound(LookupError):
    """Raised when the text an edit refers to is not present in the document."""


class TrackedDocument:
    """A .docx opened for tracked-change editing.

    Parameters
    ----------
    path
        Source document. Not modified until :meth:`save` is called.
    author
        Name recorded on every change this session writes. Shown in Word's
        Reviewing Pane.
    date
        ISO-8601 timestamp recorded on every change. Defaults to now, UTC.
    revision_id_base
        Starting value for the `w:id` counter. Choose a value above any id
        already in the document; the default is high enough for normal use.
    """

    def __init__(self, path, author, date=None, revision_id_base=100_000):
        self.path = str(path)
        self.author = author
        if date is None:
            date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.date = date
        self._next_id = revision_id_base

        with zipfile.ZipFile(self.path) as zf:
            self._names = zf.namelist()
            self._blobs = {n: zf.read(n) for n in self._names}
        self._root = etree.fromstring(self._blobs["word/document.xml"])
        self._body = self._root.find(_w("body"))

    # ---------------------------------------------------------------- helpers
    def _rev_id(self) -> str:
        self._next_id += 1
        return str(self._next_id)

    def _stamp(self, el):
        el.set(_w("id"), self._rev_id())
        el.set(_w("author"), self.author)
        el.set(_w("date"), self.date)
        return el

    @staticmethod
    def _new_run(text, rpr=None):
        r = etree.Element(_w("r"))
        if rpr is not None:
            r.append(copy.deepcopy(rpr))
        t = etree.SubElement(r, _w("t"))
        t.text = text
        t.set(_XML_SPACE, "preserve")
        return r

    def _ins(self, runs):
        el = self._stamp(etree.Element(_w("ins")))
        for r in runs:
            el.append(r)
        return el

    def _del(self, runs):
        """Wrap runs as a deletion, converting w:t to w:delText as Word requires."""
        el = self._stamp(etree.Element(_w("del")))
        for r in runs:
            for t in r.findall(_w("t")):
                t.tag = _w("delText")
                t.set(_XML_SPACE, "preserve")
            el.append(r)
        return el

    # -------------------------------------------------------------- traversal
    @staticmethod
    def _segments(p):
        """Runs contributing visible text, as (run, ins_wrapper_or_None, text).

        Runs inside `w:del` are already deleted and contribute nothing.
        """
        out = []
        for child in p:
            if child.tag == _w("r"):
                txt = "".join(t.text or "" for t in child.findall(_w("t")))
                if txt:
                    out.append((child, None, txt))
            elif child.tag == _w("ins"):
                for r in child.findall(_w("r")):
                    txt = "".join(t.text or "" for t in r.findall(_w("t")))
                    if txt:
                        out.append((r, child, txt))
        return out

    @classmethod
    def accepted_text(cls, p) -> str:
        """The paragraph as it would read with every existing change accepted."""
        return "".join(s[2] for s in cls._segments(p))

    def paragraphs(self):
        return list(self._body.iter(_w("p")))

    def find_paragraph(self, needle, nth=0):
        """The `nth` paragraph whose accepted text contains `needle`."""
        hits = [p for p in self.paragraphs() if needle in self.accepted_text(p)]
        if not hits:
            raise AnchorNotFound(f"no paragraph contains {needle!r}")
        if nth >= len(hits):
            raise AnchorNotFound(
                f"only {len(hits)} paragraph(s) contain {needle!r}, wanted index {nth}")
        return hits[nth]

    def _split_at(self, p, offset):
        """Split paragraph content at `offset` in accepted text.

        Returns the element after which new content should be inserted, or None
        to prepend. Splits a run, and any `w:ins` wrapping it, when the offset
        falls mid-run.
        """
        acc = 0
        for run, cont, txt in self._segments(p):
            if acc + len(txt) < offset:
                acc += len(txt)
                continue
            k = offset - acc
            if k == 0:
                target = cont if cont is not None else run
                return target.getprevious()
            if k >= len(txt):
                return cont if cont is not None else run
            rpr = run.find(_w("rPr"))
            left = self._new_run(txt[:k], rpr)
            right = self._new_run(txt[k:], rpr)
            if cont is None:
                run.addprevious(left)
                run.addprevious(right)
                p.remove(run)
                return left
            # Split the containing w:ins in two, preserving its author and date
            # so the earlier round's attribution survives.
            kids = list(cont)
            i = kids.index(run)
            second = etree.Element(_w("ins"))
            for a, v in cont.attrib.items():
                second.set(a, v)
            second.set(_w("id"), self._rev_id())
            cont.remove(run)
            for kid in kids[i + 1:]:
                cont.remove(kid)
                second.append(kid)
            cont.append(left)
            second.insert(0, right)
            cont.addnext(second)
            return cont
        segs = self._segments(p)
        if not segs:
            return None
        return segs[-1][1] or segs[-1][0]

    # ------------------------------------------------------------------ edits
    def insert(self, p, anchor, text, before=True):
        """Insert `text` immediately before or after `anchor` within `p`."""
        full = self.accepted_text(p)
        i = full.find(anchor)
        if i < 0:
            raise AnchorNotFound(f"anchor not found in paragraph: {anchor!r}")
        offset = i if before else i + len(anchor)
        after = self._split_at(p, offset)
        segs = self._segments(p)
        rpr = segs[0][0].find(_w("rPr")) if segs else None
        el = self._ins([self._new_run(text, rpr)])
        if after is None:
            p.insert(0, el)
        else:
            after.addnext(el)
        return el

    def delete(self, p, span):
        """Mark an existing span of accepted text as deleted."""
        full = self.accepted_text(p)
        i = full.find(span)
        if i < 0:
            raise AnchorNotFound(f"span not found in paragraph: {span!r}")
        self._split_at(p, i)
        self._split_at(p, i + len(span))
        acc = 0
        for run, cont, txt in self._segments(p):
            if acc >= i and acc + len(txt) <= i + len(span):
                d = self._del([copy.deepcopy(run)])
                run.addprevious(d)
                (cont if cont is not None else p).remove(run)
            acc += len(txt)

    def replace(self, p, old, new):
        """Replace `old` with `new`: one insertion followed by one deletion."""
        if old not in self.accepted_text(p):
            raise AnchorNotFound(f"span not found in paragraph: {old!r}")
        self.insert(p, old, new, before=True)
        self.delete(p, old)

    # ------------------------------------------------------------------- misc
    def revision_summary(self):
        """(author, date) pairs for every tracked change in the document."""
        seen = {}
        for tag in ("ins", "del"):
            for el in self._root.iter(_w(tag)):
                key = (el.get(_w("author")), (el.get(_w("date")) or "")[:10])
                seen[key] = seen.get(key, 0) + 1
        return sorted(seen.items())

    def accept_all(self):
        """Resolve every tracked change into final text.

        Insertions are unwrapped and kept, deletions are removed outright, and
        formatting-only revision marks are dropped. Comment anchors, comment
        ranges and the comment parts themselves are stripped, because a
        submission file must not carry review apparatus.

        Returns a dict describing what was resolved.
        """
        counts = {"insertions_accepted": 0, "deletions_removed": 0,
                  "format_marks_cleared": 0, "comment_marks_removed": 0}

        for el in list(self._root.iter(_w("del"))):
            counts["deletions_removed"] += 1
            el.getparent().remove(el)

        for el in list(self._root.iter(_w("ins"))):
            counts["insertions_accepted"] += 1
            parent = el.getparent()
            index = list(parent).index(el)
            for child in list(el):
                el.remove(child)
                parent.insert(index, child)
                index += 1
            parent.remove(el)

        # Paragraph-mark and run-property revisions, and numbering/section marks.
        for tag in ("rPrChange", "pPrChange", "tblPrChange", "tcPrChange",
                    "sectPrChange", "numberingChange", "cellIns", "cellDel",
                    "cellMerge"):
            for el in list(self._root.iter(_w(tag))):
                counts["format_marks_cleared"] += 1
                el.getparent().remove(el)

        for tag in ("commentRangeStart", "commentRangeEnd", "commentReference"):
            for el in list(self._root.iter(_w(tag))):
                counts["comment_marks_removed"] += 1
                el.getparent().remove(el)

        # Drop the comment parts from the package entirely.
        for name in [n for n in self._names
                     if "comments" in n.lower() or "commentsExtended" in n]:
            self._names.remove(name)
            self._blobs.pop(name, None)
        return counts

    def save(self, dest=None):
        """Write the document. Backs up in place when overwriting the source."""
        dest = str(dest or self.path)
        if dest == self.path:
            shutil.copy(self.path, self.path + ".bak")
        blob = etree.tostring(self._root, xml_declaration=True,
                              encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in self._names:
                zf.writestr(name, blob if name == "word/document.xml"
                            else self._blobs[name])
        return dest
