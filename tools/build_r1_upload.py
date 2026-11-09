#!/usr/bin/env python3
"""
build_r1_upload.py
==================
Builds the folder the corresponding author uploads to the journal for revision 1:
only the files the submission system takes, copied from the R1 package
(tools/build_r1_package.py must run first), plus a one-page upload guide and the
author-order confirmation form the journal's authorship policy requires.

Writes manuscript/jacrad-reviews-2026/JACRAD-D-26-00740_R1_Upload/
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_r1_package as pkg  # noqa: E402

OUT = os.path.join(pkg.REV, f"{pkg.MS_ID}_R1_Upload")

#: (file in the package, name in the upload folder, submission item, note)
FILES = [
    ("14_Cover_Letter.docx", "01_Cover_Letter.docx", "Cover Letter", ""),
    ("03_Response_to_Reviewers.docx", "02_Response_to_Reviewers.docx", "Response to Reviewers",
     "blinded"),
    ("02_Revised_Manuscript_TRACKED.docx", "03_Manuscript_Tracked_Changes.docx",
     "Revised Manuscript with Changes Marked", "blinded"),
    ("01_Revised_Manuscript_CLEAN.docx", "04_Manuscript_Clean.docx", "Manuscript",
     "blinded; Tables 1-4 are embedded and editable"),
    ("01_Revised_Manuscript_CLEAN.pdf", "05_Manuscript_Clean_Line_Numbered.pdf",
     "Supplementary/Other (for reviewers)", "the response letter's page and line numbers refer to it"),
    ("13_Title_Page.docx", "06_Title_Page.docx", "Title Page", "not blinded"),
    ("04_Supplementary_Material.docx", "07_Supplementary_Material.docx", "Supplementary Material",
     "Methods S1-S8, Tables S1-S6, Figures S1-S3"),
    ("05_Figures/Figure1A_CMR_Choropleth.tif", "08_Figure1A.tif", "Figure", "TIFF, 600 dpi"),
    ("05_Figures/Figure1B_Forest.tif", "09_Figure1B.tif", "Figure", "TIFF, 600 dpi"),
    ("05_Figures/Figure2_External_Validation.tif", "10_Figure2.tif", "Figure", "TIFF, 600 dpi"),
]


def authors():
    F = pkg._title_page_facts()
    return [a.strip().rstrip("¹²³⁴⁵⁶⁷⁸⁹") for a in F["Authors"][0].split(";")]


def confirmation(path):
    d = pkg.new_doc("Confirmation of Change in Author Order",
                    f"Manuscript {pkg.MS_ID} | Revision 1")
    pkg.P(d, f"Manuscript: {pkg.TITLE}")
    pkg.P(d, "Each author below agrees to the revised author order, in which Abdul Razak, PhD, is first "
             "author and Muhammad Naeem, MBBS, MD, remains the corresponding author. The order is:")
    for i, a in enumerate(authors(), 1):
        pkg.P(d, f"{i}. {a}")
    pkg.T(d, ["Author", "Signature", "Date"], [[a, "", ""] for a in authors()],
          widths=[2.6, 2.6, 1.3], size=10)
    d.save(path)


def guide(path):
    d = pkg.new_doc("Revision 1: Upload Guide", f"Manuscript {pkg.MS_ID} | {pkg.TITLE}")
    pkg.H(d, "Files and where each goes", 11.5)
    rows = [[new, item, note] for _, new, item, note in FILES]
    rows.append(["11_Author_Order_Confirmation.docx", "Other (authorship change)",
                 "signed by all eight authors"])
    pkg.T(d, ["File", "Submission item", "Note"], rows, widths=[2.6, 2.1, 1.8], size=9.5)
    pkg.H(d, "Before uploading", 11.5)
    for t in [
        "Have all eight authors sign 11_Author_Order_Confirmation. The journal requires every author's "
        "written agreement to a change in author order; the cover letter says it is enclosed.",
        "Generate the conflict-of-interest statement in the Elsevier Declarations tool and upload it.",
        "On the title page, add your telephone number and each author's leadership roles "
        "(institutional or ACR). JACR asks for both.",
        "JACR allows seven authors on an Original Article without the Editor-in-Chief's agreement; this "
        "one has eight. If that agreement was given at first submission, nothing else is needed; if "
        "not, request it in the cover letter.",
        "Confirm the author-contribution statement on the title page.",
        "If an AI tool was used in writing, add Elsevier's AI declaration before the references.",
    ]:
        pkg.B(d, t, size=10.5)
    pkg.P(d, "The repository address is withheld until acceptance, so no GitHub details are needed now.",
          size=10.5, italic=True)
    d.save(path)


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for src, new, _, _ in FILES:
        shutil.copy2(os.path.join(pkg.PKG, src), os.path.join(OUT, new))
    confirmation(os.path.join(OUT, "11_Author_Order_Confirmation.docx"))
    guide(os.path.join(OUT, "00_Upload_Guide.docx"))
    print(f"  wrote {os.path.relpath(OUT, pkg.BASE)} ({len(os.listdir(OUT))} files)")


if __name__ == "__main__":
    main()
