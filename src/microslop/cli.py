"""microslop command line."""
import argparse, sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="microslop", description="Make LibreOffice output look more like Office.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("docx2pdf", help="convert docx to PDF with Word's layout")
    p.add_argument("inputs", nargs="+", metavar="IN.docx")
    out = p.add_mutually_exclusive_group()
    out.add_argument("-o", "--output", metavar="OUT.pdf", help="output file (one input only)")
    out.add_argument("--outdir", help="output directory (default: next to each input)")
    p.add_argument("--soffice", help="LibreOffice soffice binary (default: $SOFFICE, PATH, /opt/libreoffice*)")
    p.add_argument("--fonts-dir", help="font cache (default: ~/.cache/microslop/fonts)")
    p.add_argument("--keep", metavar="DIR", help="keep the prepared docx copies and LibreOffice output in DIR")

    p = sub.add_parser("prep", help="write the adjusted docx copy that docx2pdf converts")
    p.add_argument("input", metavar="IN.docx")
    p.add_argument("output", metavar="OUT.docx")
    p.add_argument("--fonts-dir", help="font cache (default: ~/.cache/microslop/fonts)")

    p = sub.add_parser("fonts", help="download and build the substitute fonts; print the fontconfig file")
    p.add_argument("--fonts-dir", help="font cache (default: ~/.cache/microslop/fonts)")
    p.add_argument("--check", action="store_true", help="fail if a Word font has no intended substitute")

    p = sub.add_parser("compare", help="compare our PDF against Word's PDF of the same docx")
    p.add_argument("word", metavar="WORD.pdf")
    p.add_argument("ours", metavar="OURS.pdf")
    p.add_argument("--png", metavar="DIR", help="write side-by-side renders (worst page, bullets) to DIR")
    p.add_argument("--pages", help="pages to render, e.g. 1,3 (default: the worst page)")
    p.add_argument("--json", metavar="FILE", help="write details to FILE")

    a = ap.parse_args(argv)
    if a.cmd == "docx2pdf":
        from .convert import docx2pdf
        if a.output and len(a.inputs) > 1:
            ap.error("-o takes one input; use --outdir")
        outs = [a.output] if a.output else [
            str(Path(a.outdir or Path(i).parent) / (Path(i).stem + ".pdf")) for i in a.inputs]
        docx2pdf(a.inputs, outs, a.soffice, a.fonts_dir, a.keep)
    elif a.cmd == "prep":
        import os
        from . import fonts
        from .prep import prep
        os.environ["FONTCONFIG_FILE"] = str(fonts.build(a.fonts_dir))
        prep(a.input, a.output)
    elif a.cmd == "fonts":
        from . import fonts
        conf = fonts.build(a.fonts_dir)
        print(conf)
        if a.check:
            bad = fonts.check(conf)
            for b in bad:
                print("wrong substitute:", b, file=sys.stderr)
            return 1 if bad else 0
    elif a.cmd == "compare":
        from .compare import run
        pages = [int(x) for x in a.pages.split(",")] if a.pages else None
        return 0 if run(a.word, a.ours, a.png, pages, a.json) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
