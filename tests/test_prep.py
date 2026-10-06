import re, shutil, subprocess, zipfile
import xml.dom.minidom

import pytest

from microslop import prep
from docx import BULLETS, SECT, STYLES, W, bullet, make_docx, p

ZWSP = "​"


def run_prep(tmp_path, body, **kw):
    src, dst = tmp_path / "in.docx", tmp_path / "out.docx"
    make_docx(src, body, **kw)
    prep.prep(src, dst)
    with zipfile.ZipFile(dst) as z:
        parts = {n: z.read(n).decode() for n in z.namelist()}
    return parts


def well_formed(parts):
    for name, data in parts.items():
        if name.endswith((".xml", ".rels")):
            xml.dom.minidom.parseString(data.encode())


def test_output_is_well_formed(tmp_path):
    parts = run_prep(tmp_path, p("Hello / world") + bullet("item") + p("x", '<w:pStyle w:val="TOC1"/>'))
    well_formed(parts)


def test_input_unchanged(tmp_path):
    src = tmp_path / "in.docx"
    make_docx(src, p("A / B"))
    before = src.read_bytes()
    prep.prep(src, tmp_path / "out.docx")
    assert src.read_bytes() == before


def test_break_before_slash_and_paren():
    xml = '<w:t>A / B (c )</w:t>'
    assert prep.fix_breaks(xml) == f'<w:t>A {ZWSP}/ B (c {ZWSP})</w:t>'


def test_break_after_url_hyphen():
    assert prep.fix_breaks("<w:t>see a/b-c</w:t>") == f"<w:t>see a/b-{ZWSP}c</w:t>"
    assert prep.fix_breaks("<w:t>well-known</w:t>") == "<w:t>well-known</w:t>"  # no path, no change


def test_title_page_gets_empty_footer(tmp_path):
    ftr = f'<w:ftr {W}>{p("Footer")}</w:ftr>'
    sect = SECT.replace("<w:sectPr>", '<w:sectPr><w:footerReference w:type="default" r:id="rIdfooter1"/>'
                        '<w:titlePg/>')
    parts = run_prep(tmp_path, p("Title"), sect=sect, parts={"word/footer1.xml": ftr})
    doc = parts["word/document.xml"]
    assert 'w:footerReference w:type="first" r:id="rIdDocxPrepfooter"' in doc
    assert 'w:footerReference w:type="default" r:id="rIdfooter1"' in doc
    assert "word/footerDocxPrep.xml" in parts
    assert 'Target="footerDocxPrep.xml"' in parts["word/_rels/document.xml.rels"]
    assert "/word/footerDocxPrep.xml" in parts["[Content_Types].xml"]
    well_formed(parts)


def test_headers_inherit_from_previous_section():
    doc = ('<w:p><w:pPr><w:sectPr><w:headerReference w:type="default" r:id="rId7"/></w:sectPr></w:pPr></w:p>'
           '<w:sectPr></w:sectPr>')
    parts = {"word/settings.xml": b"", "word/_rels/document.xml.rels": b"<Relationships></Relationships>",
             "[Content_Types].xml": b"<Types></Types>"}
    out = prep.explicit_headers(doc, parts)
    assert out.count('w:headerReference w:type="default" r:id="rId7"') == 2


def test_page_break_then_continuous_section():
    pb = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    end = '<w:p><w:pPr><w:sectPr><w:type w:val="continuous"/></w:sectPr></w:pPr></w:p>'
    doc = p("a") + pb + end + p("b") + '<w:sectPr><w:type w:val="continuous"/><w:titlePg/></w:sectPr>'
    out = prep.page_break_to_section_break(doc)
    assert 'w:type="page"' not in out
    assert '<w:sectPr><w:type w:val="nextPage"/><w:titlePg/></w:sectPr>' in out


def test_toc_tab_size():
    toc = ('<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="24"/></w:rPr><w:tab/></w:r>'
           '</w:p>')
    assert prep.toc_tab_size(toc) == toc.replace('<w:sz w:val="24"/>', "")
    other = toc.replace("TOC1", "Normal")
    assert prep.toc_tab_size(other) == other


def test_label_fonts():
    num = '<w:lvl w:ilvl="0"><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/></w:rPr></w:lvl>'
    assert 'w:ascii="Docx Courier Label" w:hAnsi="Docx Courier Label"' in prep.label_fonts(num)
    big = num.replace("</w:rPr>", '<w:sz w:val="28"/></w:rPr>')
    assert prep.label_fonts(big) == big


def test_courier_new_renamed(tmp_path):
    parts = run_prep(tmp_path, p("code", rpr='<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>'))
    assert 'w:ascii="Docx Courier New"' in parts["word/document.xml"]
    # bullet level 2 is a label
    assert 'w:ascii="Docx Courier Label"' in parts["word/numbering.xml"]
    assert "Courier New\"" not in parts["word/numbering.xml"].replace("Docx Courier", "")


def test_page_break_bullet_hidden():
    para = ('<w:p><w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/></w:numPr></w:pPr>'
            '<w:r><w:br w:type="page"/></w:r></w:p>')
    assert '<w:numId w:val="0"/>' in prep.page_break_bullets(para)
    text = bullet("item")
    assert prep.page_break_bullets(text) == text


def test_cell_margins():
    doc = '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblLook w:val="04A0"/></w:tblPr></w:tbl>'
    out = prep.cell_margins(doc, STYLES)
    assert '<w:tblCellMar><w:right w:w="106" w:type="dxa"/></w:tblCellMar><w:tblLook' in out
    direct = '<w:tcMar><w:right w:w="100" w:type="dxa"/></w:tcMar>'
    assert prep.cell_margins(direct, STYLES) == direct.replace("100", "98")


def test_table_indent():
    plain = '<w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
    assert prep.table_indent(plain) == '<w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblInd w:w="0" w:type="dxa"/></w:tblPr>'
    styled = '<w:tblPr><w:tblStyle w:val="TableGrid"/></w:tblPr>'
    assert prep.table_indent(styled) == styled


def test_theme_east_asia(tmp_path):
    parts = run_prep(tmp_path, p("x"))
    assert 'w:eastAsia="DengXian"' in parts["word/styles.xml"]
    assert "w:eastAsiaTheme" not in parts["word/styles.xml"]


def test_symbol_runs():
    run = '<w:r><w:rPr><w:b/></w:rPr><w:t>Yes ✔ no</w:t></w:r>'
    out = prep.symbol_runs(run)
    assert out.count("<w:r>") == 3
    assert '<w:rPr><w:rFonts w:ascii="Segoe UI Symbol" w:hAnsi="Segoe UI Symbol"/><w:b/></w:rPr>' \
           '<w:t xml:space="preserve">✔</w:t>' in out
    assert prep.symbol_runs("<w:r><w:t>plain</w:t></w:r>") == "<w:r><w:t>plain</w:t></w:r>"


def test_space_after_two_columns():
    cols = ('<w:p><w:pPr><w:sectPr><w:type w:val="continuous"/><w:cols w:num="2" w:space="720"/></w:sectPr>'
            '</w:pPr></w:p>')
    doc = p("a") + cols + p("next", '<w:pStyle w:val="Normal"/>') + '<w:sectPr><w:type w:val="continuous"/></w:sectPr>'
    styles = STYLES.replace('<w:name w:val="Normal"/>', '<w:name w:val="Normal"/><w:pPr><w:spacing w:before="200" '
                            'w:after="160"/></w:pPr>')
    out = prep.after_columns(doc, styles)
    assert '<w:pStyle w:val="Normal"/><w:spacing w:before="40"/>' in out


def fonts_available():
    if not shutil.which("fc-match"):
        return False
    out = subprocess.run(["fc-match", "-f", "%{family}", "Calibri"], capture_output=True, text=True).stdout
    return "Carlito" in out


@pytest.mark.skipif(not fonts_available(), reason="needs `microslop fonts` and FONTCONFIG_FILE")
def test_one_line_widows(tmp_path):
    short, long = "A short paragraph.", "A long paragraph that wraps onto a second line. " * 4
    parts = run_prep(tmp_path, p(short) + p(long))
    paras = re.findall(r"<w:p>.*?</w:p>", parts["word/document.xml"])
    assert '<w:widowControl w:val="0"/>' in paras[0]
    assert "widowControl" not in paras[1]


def test_bullet_fixture_numbering_kept(tmp_path):
    parts = run_prep(tmp_path, bullet("one") + bullet("two", 1), numbering=BULLETS)
    assert parts["word/numbering.xml"].count("<w:lvl ") == 3
