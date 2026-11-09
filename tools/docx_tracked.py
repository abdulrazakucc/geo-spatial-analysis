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
import os
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

    def delete_paragraph(self, p):
        """Delete a whole paragraph: every run of its text and its paragraph mark.

        Marking the paragraph mark as deleted (w:pPr/w:rPr/w:del) is how Word
        records a removed paragraph, so accepting the change removes the
        paragraph itself rather than leaving an empty one behind.
        """
        for run, cont, txt in self._segments(p):
            d = self._del([copy.deepcopy(run)])
            run.addprevious(d)
            (cont if cont is not None else p).remove(run)
        ppr = p.find(_w("pPr"))
        if ppr is None:
            ppr = etree.Element(_w("pPr"))
            p.insert(0, ppr)
        rpr = ppr.find(_w("rPr"))
        if rpr is None:
            rpr = etree.SubElement(ppr, _w("rPr"))
        rpr.insert(0, self._stamp(etree.Element(_w("del"))))

    def replace(self, p, old, new):
        """Replace `old` with `new`: one insertion followed by one deletion."""
        if old not in self.accepted_text(p):
            raise AnchorNotFound(f"span not found in paragraph: {old!r}")
        self.insert(p, old, new, before=True)
        self.delete(p, old)

    def insert_paragraph_after(self, p, text, model=None):
        """Insert a new paragraph after `p`, recorded as a tracked insertion.

        Paragraph and run formatting are copied from `model` (default `p`), so
        the new paragraph matches its neighbours. Both the text and the new
        paragraph mark are marked as inserted, which is how Word records a
        paragraph typed in with Track Changes on.
        """
        model = p if model is None else model
        new = etree.Element(_w("p"))
        ppr = model.find(_w("pPr"))
        ppr = copy.deepcopy(ppr) if ppr is not None else etree.Element(_w("pPr"))
        mark_rpr = ppr.find(_w("rPr"))
        if mark_rpr is None:
            mark_rpr = etree.SubElement(ppr, _w("rPr"))
        for child in list(mark_rpr):
            if child.tag in (_w("ins"), _w("del")):
                mark_rpr.remove(child)
        mark_rpr.insert(0, self._stamp(etree.Element(_w("ins"))))
        new.append(ppr)
        segs = self._segments(model)
        rpr = segs[0][0].find(_w("rPr")) if segs else None
        new.append(self._ins([self._new_run(text, rpr)]))
        p.addnext(new)
        return new

    @classmethod
    def row_texts(cls, tr):
        """Accepted text of each cell in a table row."""
        return [" ".join(filter(None, (cls.accepted_text(q).strip()
                                       for q in tc.findall(_w("p"))))).strip()
                for tc in tr.findall(_w("tc"))]

    def find_row(self, table, label, section=None):
        """Row whose first cell reads `label`, optionally under a section row.

        A section row is one whose only non-empty cell is the first, such as
        "Cardiac MR"; row labels repeat under different sections.
        """
        current = None
        for tr in table.findall(_w("tr")):
            cells = self.row_texts(tr)
            if not cells:
                continue
            if cells[0] and not any(cells[1:]):
                current = cells[0]
            if cells[0] == label and (section is None or current == section):
                return tr
        raise AnchorNotFound(f"row {label!r} under {section!r} not found")

    def cell_paragraph(self, tr, col):
        """First paragraph of cell `col` in row `tr`."""
        return tr.findall(_w("tc"))[col].find(_w("p"))

    def insert_table_row_after(self, tr, values, model=None):
        """Insert a row after `tr`, copying the layout of `model` (default `tr`).

        The row is marked as a tracked insertion (w:trPr/w:ins) and its text as
        inserted runs, so accepting all changes keeps it and rejecting removes it.
        """
        model = tr if model is None else model
        new = copy.deepcopy(model)
        trpr = new.find(_w("trPr"))
        if trpr is None:
            trpr = etree.Element(_w("trPr"))
            new.insert(0, trpr)
        for child in list(trpr):
            if child.tag in (_w("ins"), _w("del")):
                trpr.remove(child)
        trpr.append(self._stamp(etree.Element(_w("ins"))))
        cells = new.findall(_w("tc"))
        if len(values) != len(cells):
            raise ValueError(f"{len(values)} values for {len(cells)} cells")
        for tc, value in zip(cells, values):
            paras = tc.findall(_w("p"))
            first_run = next(tc.iter(_w("r")), None)
            rpr = first_run.find(_w("rPr")) if first_run is not None else None
            rpr = copy.deepcopy(rpr) if rpr is not None else None
            for q in paras[1:]:
                tc.remove(q)
            target = paras[0]
            for child in list(target):
                if child.tag != _w("pPr"):
                    target.remove(child)
            if value:
                target.append(self._ins([self._new_run(str(value), rpr)]))
        tr.addnext(new)
        return new

    def insert_table_after(self, anchor, rows, model_table, widths, bold_rows=(0,)):
        """Insert a new table after `anchor` (a paragraph or table), every row a
        tracked insertion, so accepting all changes keeps it and rejecting removes it.

        Table properties and cell paragraph and run formatting are copied from
        `model_table`; `widths` gives each column in twips. The first row repeats
        as a header on continuation pages.
        """
        tbl = etree.Element(_w("tbl"))
        tblpr = model_table.find(_w("tblPr"))
        tbl.append(copy.deepcopy(tblpr) if tblpr is not None else etree.Element(_w("tblPr")))
        grid = etree.SubElement(tbl, _w("tblGrid"))
        for wd in widths:
            etree.SubElement(grid, _w("gridCol")).set(_w("w"), str(int(wd)))
        mrows = model_table.findall(_w("tr"))
        mtc = (mrows[1] if len(mrows) > 1 else mrows[0]).find(_w("tc"))
        mp = mtc.find(_w("p"))
        mppr = mp.find(_w("pPr")) if mp is not None else None
        mrun = next(mtc.iter(_w("r")), None)
        mrpr = mrun.find(_w("rPr")) if mrun is not None else None
        for i, values in enumerate(rows):
            if len(values) != len(widths):
                raise ValueError(f"row {i}: {len(values)} values for {len(widths)} columns")
            tr = etree.SubElement(tbl, _w("tr"))
            trpr = etree.SubElement(tr, _w("trPr"))
            if i == 0:
                etree.SubElement(trpr, _w("tblHeader"))
            trpr.append(self._stamp(etree.Element(_w("ins"))))
            for j, value in enumerate(values):
                tc = etree.SubElement(tr, _w("tc"))
                tcw = etree.SubElement(etree.SubElement(tc, _w("tcPr")), _w("tcW"))
                tcw.set(_w("w"), str(int(widths[j])))
                tcw.set(_w("type"), "dxa")
                p = etree.SubElement(tc, _w("p"))
                if mppr is not None:
                    ppr = copy.deepcopy(mppr)
                    for child in list(ppr):
                        if child.tag == _w("rPr"):
                            ppr.remove(child)
                    p.append(ppr)
                if value:
                    rpr = copy.deepcopy(mrpr) if mrpr is not None else etree.Element(_w("rPr"))
                    for child in list(rpr):
                        if child.tag in (_w("b"), _w("bCs")):
                            rpr.remove(child)
                    if i in bold_rows:
                        rpr.insert(0, etree.Element(_w("b")))
                    p.append(self._ins([self._new_run(str(value), rpr)]))
        anchor.addnext(tbl)
        return tbl

    # ------------------------------------------------------------------- misc
    def revision_summary(self):
        """(author, date) pairs for every tracked change in the document."""
        seen = {}
        for tag in ("ins", "del"):
            for el in self._root.iter(_w(tag)):
                key = (el.get(_w("author")), (el.get(_w("date")) or "")[:10])
                seen[key] = seen.get(key, 0) + 1
        return sorted(seen.items())

    def tables(self):
        """Every w:tbl in the body, in document order."""
        return list(self._body.iter(_w("tbl")))

    def insert_table_column(self, table, after_index, values):
        """Insert a column after `after_index`, one value per row.

        `values` must have one entry per row including the header. The new
        cell copies the formatting of the cell it follows, so the column
        matches the table it joins. Marked as a tracked insertion when the
        document is being edited with revision tracking.
        """
        rows = table.findall(_w("tr"))
        if len(values) != len(rows):
            raise ValueError(
                f"{len(values)} values for {len(rows)} rows")
        for row, value in zip(rows, values):
            cells = row.findall(_w("tc"))
            model = cells[min(after_index, len(cells) - 1)]
            new = copy.deepcopy(model)
            # Strip the copied text, keeping the cell and paragraph properties.
            for para in new.findall(_w("p")):
                for child in list(para):
                    if child.tag != _w("pPr"):
                        para.remove(child)
            target = new.find(_w("p"))
            if target is None:
                target = etree.SubElement(new, _w("p"))
            rpr = None
            for m_para in model.findall(_w("p")):
                m_run = m_para.find(_w("r"))
                if m_run is not None:
                    rpr = m_run.find(_w("rPr"))
                    break
            run = self._new_run(str(value), rpr)
            target.append(self._ins([run]) if self.author else run)
            model.addnext(new)
        self.fit_table_width(table)
        return len(rows)

    def fit_table_width(self, table, total=None):
        """Rebuild w:tblGrid and rescale columns so the table fits its width.

        A copied cell brings the width of the cell it followed, and w:tblGrid
        is not touched by the copy, so inserting columns leaves a table whose
        cells are wider than the page and whose grid no longer describes it.
        Word lays such a table out past the right margin. Rescaling here keeps
        the table inside the width it already had, in proportion to the columns
        the author chose.

        `total` defaults to the table's existing declared width.
        """
        rows = table.findall(_w("tr"))
        if not rows:
            return 0
        grid = table.find(_w("tblGrid"))
        if total is None:
            if grid is not None and len(grid):
                total = sum(int(g.get(_w("w"))) for g in grid.findall(_w("gridCol")))
            else:
                tbl_w = table.find(_w("tblPr") + "/" + _w("tblW"))
                total = int(tbl_w.get(_w("w"))) if tbl_w is not None else 9360

        def widths(row):
            out = []
            for tc in row.findall(_w("tc")):
                el = tc.find(_w("tcPr") + "/" + _w("tcW"))
                out.append(int(el.get(_w("w"))) if el is not None else 0)
            return out

        # The widest row defines the column count; header rows can be merged.
        model_row = max(rows, key=lambda r: len(r.findall(_w("tc"))))
        base = widths(model_row)
        ncols = len(base)
        if not ncols:
            return 0
        if sum(base) <= 0:
            base = [total // ncols] * ncols

        scaled = [max(1, round(w * total / sum(base))) for w in base]
        scaled[-1] += total - sum(scaled)          # absorb rounding drift

        for row in rows:
            cells = row.findall(_w("tc"))
            if len(cells) != ncols:
                continue                            # merged row, leave alone
            for tc, w in zip(cells, scaled):
                pr = tc.find(_w("tcPr"))
                if pr is None:
                    pr = etree.SubElement(tc, _w("tcPr"))
                el = pr.find(_w("tcW"))
                if el is None:
                    el = etree.SubElement(pr, _w("tcW"))
                el.set(_w("w"), str(w))
                el.set(_w("type"), "dxa")

        if grid is not None:
            table.remove(grid)
        grid = etree.Element(_w("tblGrid"))
        for w in scaled:
            etree.SubElement(grid, _w("gridCol")).set(_w("w"), str(w))
        pr = table.find(_w("tblPr"))
        pr.addnext(grid) if pr is not None else table.insert(0, grid)
        return ncols

    def accept_all(self):
        """Resolve every tracked change into final text.

        Insertions are unwrapped and kept, deletions are removed outright, and
        formatting-only revision marks are dropped. Comment anchors, comment
        ranges and the comment parts themselves are stripped, because a
        submission file must not carry review apparatus.

        Returns a dict describing what was resolved.
        """
        counts = {"insertions_accepted": 0, "deletions_removed": 0,
                  "format_marks_cleared": 0, "comment_marks_removed": 0,
                  "paragraphs_removed": 0}

        # A deleted paragraph mark joins the paragraph to the next one; a
        # paragraph whose text is also wholly deleted disappears. Resolve these
        # before the w:del elements (including the mark's own) are removed.
        for p in list(self._root.iter(_w("p"))):
            mark = p.find(f"{_w('pPr')}/{_w('rPr')}/{_w('del')}")
            if mark is None:
                continue
            live = [r for r in p.iter(_w("r"))
                    if not any(a.tag == _w("del") for a in r.iterancestors())
                    and r.find(_w("t")) is not None]
            nxt = p.getnext()
            if live and nxt is not None and nxt.tag == _w("p"):
                anchor = nxt.find(_w("pPr"))
                pos = 0 if anchor is None else list(nxt).index(anchor) + 1
                for child in [c for c in p if c.tag != _w("pPr")]:
                    nxt.insert(pos, child)
                    pos += 1
            counts["paragraphs_removed"] += 1
            p.getparent().remove(p)

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

        # Drop the comment parts from the package, and every reference to
        # them. Removing the part alone leaves a dangling relationship in
        # word/_rels/document.xml.rels and an orphan override in
        # [Content_Types].xml, which some validators flag as a corrupt package.
        removed = [n for n in self._names if "comments" in n.lower()]
        for name in removed:
            self._names.remove(name)
            self._blobs.pop(name, None)
        if removed:
            self._prune_part_references(removed)
        return counts

    def _prune_part_references(self, removed_parts):
        """Drop relationship and content-type entries for deleted parts."""
        basenames = {os.path.basename(n) for n in removed_parts}

        for rels_name in [n for n in self._names if n.endswith(".rels")]:
            root = etree.fromstring(self._blobs[rels_name])
            changed = False
            for rel in list(root):
                target = (rel.get("Target") or "").lstrip("./")
                if os.path.basename(target) in basenames:
                    root.remove(rel)
                    changed = True
            if changed:
                self._blobs[rels_name] = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True)

        ct = "[Content_Types].xml"
        if ct in self._blobs:
            root = etree.fromstring(self._blobs[ct])
            changed = False
            for node in list(root):
                part = (node.get("PartName") or "").lstrip("/")
                if part and os.path.basename(part) in basenames:
                    root.remove(node)
                    changed = True
            if changed:
                self._blobs[ct] = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True)

    def scrub_identity(self, name=""):
        """Blank the author fields of the package properties (creator and last
        modified by in docProps/core.xml; company and manager in app.xml), so a
        blinded copy does not name its authors in its file metadata."""
        for part, tags in (("docProps/core.xml", ("creator", "lastModifiedBy")),
                           ("docProps/app.xml", ("Company", "Manager"))):
            if part not in self._blobs:
                continue
            root = etree.fromstring(self._blobs[part])
            for el in root.iter():
                if isinstance(el.tag, str) and el.tag.split("}")[-1] in tags:
                    el.text = name
            self._blobs[part] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                               standalone=True)

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
