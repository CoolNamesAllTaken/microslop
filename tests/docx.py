"""Build small docx files from hand-written WordprocessingML."""
import sys, zipfile

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ' \
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
SECT = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" ' \
       'w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
STYLES = f'''<w:styles {W}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:asciiTheme="minorHAnsi"
 w:hAnsiTheme="minorHAnsi" w:eastAsiaTheme="minorEastAsia"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
 <w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
 <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
 <w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/><w:basedOn w:val="Normal"/></w:style>
 <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblCellMar>
 <w:left w:w="108" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style></w:styles>'''
THEME = '''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme"><a:themeElements>
 <a:fontScheme name="Office"><a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/><a:cs typeface=""/>
 <a:font script="Hans" typeface="DengXian Light"/></a:majorFont><a:minorFont><a:latin typeface="Calibri"/>
 <a:ea typeface=""/><a:cs typeface=""/><a:font script="Hans" typeface="DengXian"/></a:minorFont></a:fontScheme>
 </a:themeElements></a:theme>'''
BULLETS = f'''<w:numbering {W}><w:abstractNum w:abstractNumId="0">
 <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val=""/><w:lvlJc w:val="left"/>
 <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl>
 <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="o"/><w:lvlJc w:val="left"/>
 <w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New" w:hint="default"/></w:rPr></w:lvl>
 <w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val=""/><w:lvlJc w:val="left"/>
 <w:pPr><w:ind w:left="2160" w:hanging="360"/></w:pPr><w:rPr><w:rFonts w:ascii="Wingdings" w:hAnsi="Wingdings" w:hint="default"/></w:rPr></w:lvl>
 </w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''


def make_docx(path, body, sect=SECT, styles=STYLES, numbering=BULLETS, settings="", theme=THEME, parts=None):
    """Write a docx whose body is BODY (paragraphs and tables) followed by SECT. PARTS: extra
    {"word/name.xml": xml} parts, related to the document by relationship id rId<name>."""
    parts = dict(parts or {})
    rels = [("styles", "styles.xml"), ("settings", "settings.xml"), ("theme", "theme/theme1.xml")]
    if numbering:
        rels.append(("numbering", "numbering.xml"))
    for name in parts:
        kind = "header" if "header" in name else "footer"
        rels.append((kind, name[5:]))
    types = "".join(f'<Override PartName="/word/{t}" ContentType="application/vnd.openxmlformats-officedocument.'
                    f'{"theme+xml" if k == "theme" else f"wordprocessingml.{k}+xml"}"/>' for k, t in rels)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
                   f'wordprocessingml.document.main+xml"/>{types}</Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                   'officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(
                       f'<Relationship Id="rId{t.split("/")[-1][:-4]}" Type="http://schemas.openxmlformats.org/'
                       f'officeDocument/2006/relationships/{k}" Target="{t}"/>' for k, t in rels) + "</Relationships>")
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   f'<w:document {W}><w:body>{body}{sect}</w:body></w:document>')
        z.writestr("word/styles.xml", styles)
        z.writestr("word/settings.xml", f"<w:settings {W}>{settings}</w:settings>")
        z.writestr("word/theme/theme1.xml", theme)
        if numbering:
            z.writestr("word/numbering.xml", numbering)
        for name, xml in parts.items():
            z.writestr(name, xml)


def p(text="", ppr="", rpr=""):
    run = f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{text}</w:t></w:r>' if text else ""
    return f'<w:p>{f"<w:pPr>{ppr}</w:pPr>" if ppr else ""}{run}</w:p>'


def bullet(text, level=0):
    return p(text, f'<w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr>')


def sample(path):
    """A one-page doc with the things docx2pdf fixes: Calibri, bullets, Consolas, Courier New, a table,
    check marks, a line with " /"."""
    lorem = ("Microslop converts Word documents with LibreOffice and keeps Word's line breaks, bullets "
             "and page breaks. ")
    body = p("Sample document", rpr='<w:b/><w:sz w:val="32"/>') + p(lorem * 3) + bullet("Level one bullet") \
        + bullet("Level two bullet", 1) + bullet("Level three bullet", 2) + bullet("Back to level one") \
        + p("int main(void) { return 0; }", rpr='<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>') \
        + p("AT+COMMAND=value", rpr='<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>') \
        + p("Supported ✔ / unsupported ✘ / path/to/some-file-name") \
        + '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tblGrid>' \
          '<w:gridCol w:w="4680"/><w:gridCol w:w="4680"/></w:tblGrid>' + "".join(
              f'<w:tr><w:tc><w:tcPr><w:tcW w:w="4680" w:type="dxa"/></w:tcPr>{p(a)}</w:tc>'
              f'<w:tc><w:tcPr><w:tcW w:w="4680" w:type="dxa"/></w:tcPr>{p(b)}</w:tc></w:tr>'
              for a, b in (("Name", "Value"), ("Times New Roman", "Arial"))) + "</w:tbl>" \
        + p("Serif text", rpr='<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>') + p(lorem * 2)
    make_docx(path, body)


if __name__ == "__main__":
    sample(sys.argv[1])
