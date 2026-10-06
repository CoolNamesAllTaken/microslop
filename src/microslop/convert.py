"""docx -> PDF with LibreOffice, prepared to match Word's layout."""
import glob, os, shutil, subprocess, sys, tempfile
from pathlib import Path

from . import fonts
from .prep import prep


def find_soffice(path=None):
    for cand in (path, os.environ.get("SOFFICE"), shutil.which("soffice"), shutil.which("libreoffice"),
                 *sorted(glob.glob("/opt/libreoffice*/program/soffice"), reverse=True),
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if cand and os.path.exists(cand):
            return cand
    raise SystemExit("LibreOffice not found: pass --soffice or set SOFFICE")


def docx2pdf(inputs, outputs, soffice=None, fonts_dir=None, keep=None):
    """Convert docx INPUTS to PDF OUTPUTS (same length)."""
    soffice = find_soffice(soffice)
    conf = fonts.build(fonts_dir)
    os.environ["FONTCONFIG_FILE"] = str(conf)  # prep measures text with the same fonts
    names = [Path(i).name for i in inputs]
    if len(set(names)) != len(names):
        raise SystemExit("input file names must be unique")
    with tempfile.TemporaryDirectory(prefix="microslop-") as tmp:
        tmp = Path(keep or tmp)
        (tmp / "in").mkdir(parents=True, exist_ok=True)
        for src, name in zip(inputs, names):
            prep(src, tmp / "in" / name)
        cmd = [soffice, f"-env:UserInstallation={(tmp / 'profile').as_uri()}", "--headless", "--convert-to", "pdf",
               "--outdir", str(tmp / "out"), *[str(tmp / "in" / n) for n in names]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        for name, out in zip(names, outputs):
            pdf = tmp / "out" / (Path(name).stem + ".pdf")
            if not pdf.exists():
                sys.stderr.write(r.stdout + r.stderr)
                raise SystemExit(f"LibreOffice did not convert {name}")
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, out)
            print(out)
