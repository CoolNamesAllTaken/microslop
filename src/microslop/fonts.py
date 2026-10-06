"""Substitute fonts for Word fonts that have no metric-compatible free clone.

Each substitute keeps free glyphs and takes the line metrics of the Word font it replaces, so lines get
the same height as in Word:

- Symbol: URW Standard Symbols PS (Adobe Symbol widths) with a symbol cmap (U+F020-F0FF), for list
  bullets such as U+F0B7. Metrics of Word's SymbolMT, bullet moved down to SymbolMT's position.
- Docx Courier New: URW Nimbus Mono PS (thin strokes and round "o" like Courier New, same advance),
  Courier New metrics. Liberation Mono is metric-compatible but much heavier, which shows in "o" bullets.
- Docx Courier Label: Nimbus Mono PS for list bullets, without descent (see prep.py).
- Docx Consolas: Inconsolata at the width where its advance matches Consolas, Consolas metrics.
- Docx Poppins Label: Poppins for body-size list numbers, without descent (see prep.py).
- Docx Segoe Symbol: DejaVu Sans symbols (check marks), Segoe UI Symbol metrics.
- Docx DengXian, Docx SimSun: Droid Sans Fallback (full-width punctuation), DengXian / SimSun metrics.

Sources and plain fonts (Carlito, Liberation, DejaVu, Poppins) are downloaded from pinned URLs and
checked by sha256, so every machine lays out with the same font files.
"""
import hashlib, io, logging, lzma, os, shutil, subprocess, tarfile, time, urllib.request
from importlib import resources
from pathlib import Path

from fontTools import subset
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import cmap_format_4
from fontTools.varLib.instancer import instantiateVariableFont

UBUNTU = "http://archive.ubuntu.com/ubuntu/pool"
GFONTS = "https://raw.githubusercontent.com/google/fonts/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5/ofl"
# Ubuntu 24.04 packages: (url, sha256, {member: role}); role "font" installs, "src" feeds the substitutes.
DEBS = [
    (f"{UBUNTU}/universe/f/fonts-crosextra-carlito/fonts-crosextra-carlito_20230309-2_all.deb",
     "c238087a909a4f1d1c5c1a5e1ed42ab9cb522f09ea2715e8deab6ee2751b9a01", {"Carlito-": "font"}),
    (f"{UBUNTU}/main/f/fonts-liberation/fonts-liberation_2.1.5-3_all.deb",
     "065c2ab1abc9108b17d401016dc594b79750904390f095845c93bb06e1153acc", {"Liberation": "font"}),
    (f"{UBUNTU}/main/f/fonts-dejavu/fonts-dejavu-core_2.37-8_all.deb",
     "40049660c194f3b8a2541fc7369efebb10e9f94bdac836a2f38fafedd10fa73a", {"DejaVu": "font", "DejaVuSans.ttf": "src"}),
    (f"{UBUNTU}/main/f/fonts-urw-base35/fonts-urw-base35_20200910-8_all.deb",
     "46e75490faa7fd6fddbc8df234d14e0f7b60ea5e98563227a24d6bf5e5008647",
     {"StandardSymbolsPS.otf": "src", "NimbusMonoPS-": "src"}),
    (f"{UBUNTU}/main/f/fonts-android/fonts-droid-fallback_6.0.1r16-1.1build1_all.deb",
     "353e093dd32677e48edbdc9c94c4e92db0e80763fc326ddec1ba8281d8553a5e", {"DroidSansFallbackFull.ttf": "src"}),
]
# (url, sha256, file name, role)
FILES = [(f"{GFONTS}/poppins/Poppins-{style}.ttf", sha, f"Poppins-{style}.ttf", "font") for style, sha in (
    ("Regular", "7e65201e9b79159e2300267cc885e16c8dcef2424cdfa09a29bfb0980a94a7ba"),
    ("Italic", "4fa76ae75b40f926420514044722cb97f32186cafd3b38263cc34dad7174d46d"),
    ("Light", "650ba57fa99d12ec40c31ccfb680be656be4497fbe14164617d67e32ffe9cd46"),
    ("Medium", "90373e7d838d32468438fc3e152dca0bdb12edcab99ea639f158790b1ba1fd05"),
    ("SemiBold", "d3bf1bdaf0550e83da9ac0b1d1d9fe6db086835a83aa28578e609a394b9a0286"),
    ("SemiBoldItalic", "16bb118aa232c9a13fa238027d24d7854dd1a1d9cbaf99b17fec4388d56b432c"),
    ("Bold", "983676516167748b74de6f4771fb384c664fd913acb8b471122ecacf5da5ea6c"),
    ("BoldItalic", "3572ac8116a0ac7317d342262b29937bcbaf94d8f03f90df6fe666fa7e2fb43a"),
)] + [(f"{GFONTS}/inconsolata/Inconsolata%5Bwdth,wght%5D.ttf",
       "23ded25b447074d00659392bf9b1123d89df55cb07b0ad9bfef3366d199b5fcb", "Inconsolata[wdth,wght].ttf", "src")]

# Word font -> family fontconfig must pick (checked by `microslop fonts --check`)
EXPECTED = {
    "Calibri": "Carlito", "Calibri Light": "Carlito", "Poppins": "Poppins", "Poppins SemiBold": "Poppins SemiBold",
    "Docx Poppins Label": "Docx Poppins Label", "Symbol": "Symbol", "Consolas": "Docx Consolas",
    "Segoe UI Symbol": "Docx Segoe Symbol", "SimSun": "Docx SimSun", "DengXian": "Docx DengXian",
    "Times New Roman": "Liberation Serif", "Arial": "Liberation Sans", "Docx Courier New": "Docx Courier New",
    "Docx Courier Label": "Docx Courier Label",
}
VERSION = "1"  # bump when the font set or a substitute changes


def default_dir():
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "microslop" / "fonts"


def download(url, sha, dest):
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha:
        return dest.read_bytes()
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        raise RuntimeError(f"sha256 mismatch for {url}: {got}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def deb_members(data):
    """(name, bytes) of the files in a .deb's data archive."""
    assert data[:8] == b"!<arch>\n", "not a .deb"
    pos = 8
    while pos < len(data):
        name, size = data[pos:pos + 16].decode().strip().rstrip("/"), int(data[pos + 48:pos + 58])
        body = data[pos + 60:pos + 60 + size]
        pos += 60 + size + size % 2
        if name.startswith("data.tar"):
            if name.endswith(".zst"):
                import zstandard
                body = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(body)).read()
            elif name.endswith(".xz"):
                body = lzma.decompress(body)
            with tarfile.open(fileobj=io.BytesIO(body)) as tar:
                for m in tar.getmembers():
                    if m.isfile():
                        yield os.path.basename(m.name), tar.extractfile(m).read()
            return


def build(out=None):
    """Download, build and install the fonts into OUT (default ~/.cache/microslop/fonts) and write
    OUT/fonts.conf. Returns the fonts.conf path. Does nothing if OUT is already complete."""
    out = Path(out or default_dir()).resolve()
    conf = out / "fonts.conf"
    stamp = out / "version"
    if conf.exists() and stamp.exists() and stamp.read_text() == VERSION:
        return conf
    dl, src, fonts = out / "download", out / "src", out / "fonts"
    for d in (src, fonts):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    for url, sha, members in DEBS:
        data = download(url, sha, dl / url.rsplit("/", 1)[1])
        for name, body in deb_members(data):
            if not name.endswith((".ttf", ".otf")):
                continue
            for prefix, role in members.items():
                if name.startswith(prefix):
                    ((fonts if role == "font" else src) / name).write_bytes(body)
    for url, sha, name, role in FILES:
        data = download(url, sha, dl / name)
        ((fonts if role == "font" else src) / name).write_bytes(data)
    make_substitutes(src, fonts)
    shutil.copy(resources.files(__package__) / "fonts.conf", out / "substitutes.conf")
    conf.write_text(f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>{fonts}</dir>
  <cachedir>{out / "cache"}</cachedir>
  <include>{out / "substitutes.conf"}</include>
</fontconfig>
""")
    subprocess.run(["fc-cache", "-f"], env={**os.environ, "FONTCONFIG_FILE": str(conf)}, check=False,
                   capture_output=True)
    stamp.write_text(VERSION)
    return conf


def check(conf):
    """Problems with the fontconfig substitution (empty if fine)."""
    bad = []
    for word, want in EXPECTED.items():
        got = subprocess.run(["fc-match", "-f", "%{family}", word], capture_output=True, text=True,
                             env={**os.environ, "FONTCONFIG_FILE": str(conf)}).stdout
        if want not in got.split(","):
            bad.append(f"{word} -> {got or '?'} (want {want})")
    return bad




def set_names(font, family, style="Regular"):
    name = font["name"]
    ps = (family + "-" + style).replace(" ", "")
    for nid in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
        name.removeNames(nameID=nid)
    for nid, val in ((1, family), (2, style), (3, ps), (4, f"{family} {style}"), (6, ps)):
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)
    if "CFF " in font:
        cff = font["CFF "].cff
        cff.fontNames = [ps]
        top = cff.topDictIndex[0]
        top.FullName, top.FamilyName = f"{family} {style}", family


def set_vmetrics(font, asc, desc):
    """Ascent and descent in em, written to hhea, typo and win alike."""
    upem = font["head"].unitsPerEm
    asc, desc = round(asc * upem), round(desc * upem)
    hhea, os2 = font["hhea"], font["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = asc, -desc, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = asc, -desc, 0
    os2.usWinAscent, os2.usWinDescent = asc, desc


def symbol(src, out):
    f = TTFont(src)
    # Standard Symbols PS maps Symbol-encoding positions as code points (0x20-0xFF).
    sym = cmap_format_4(4)
    sym.platformID, sym.platEncID, sym.language = 3, 0, 0
    sym.cmap = {0xF000 + k: v for k, v in f.getBestCmap().items() if k < 0x100}
    f["cmap"].tables = [sym]
    os2 = f["OS/2"]
    os2.ulCodePageRange1, os2.ulCodePageRange2 = 1 << 31, 0  # symbol character set
    os2.usFirstCharIndex, os2.usLastCharIndex = min(sym.cmap), max(sym.cmap)
    set_vmetrics(f, 2059 / 2048, 450 / 2048)
    # SymbolMT's bullet spans 0.103-0.460 em above the baseline, Standard Symbols PS's 0.155-0.518.
    move_glyph(f, "bullet", -0.055)
    set_names(f, "Symbol")
    f.recalcTimestamp = False  # reproducible files
    f.save(out)


def move_glyph(f, name, dy):
    """Shift a CFF glyph up by dy em."""
    cs = f["CFF "].cff.topDictIndex[0].CharStrings
    old = cs[name]
    width = f["hmtx"][name][0]
    pen = T2CharStringPen(None if width == old.private.defaultWidthX else width - old.private.nominalWidthX, None)
    f.getGlyphSet()[name].draw(TransformPen(pen, (1, 0, 0, 1, 0, round(dy * f["head"].unitsPerEm))))
    cs[name] = pen.getCharString(private=old.private, globalSubrs=old.globalSubrs)


def consolas(src, out):
    target = 1126 / 2048  # Consolas advance, em
    lo, hi = 100.0, 200.0
    for _ in range(30):  # advance grows with wdth
        wdth = (lo + hi) / 2
        f = instantiateVariableFont(TTFont(src), {"wdth": wdth, "wght": 400})
        adv = f["hmtx"]["a"][0] / f["head"].unitsPerEm
        if abs(adv - target) < 0.0005:
            break
        lo, hi = (wdth, hi) if adv < target else (lo, wdth)
    for t in ("STAT", "MVAR"):
        if t in f:
            del f[t]
    set_vmetrics(f, 1884 / 2048, 514 / 2048)
    set_names(f, "Docx Consolas")
    f.recalcTimestamp = False  # reproducible files
    f.save(out)


def shim(src, out, family, asc, desc, unicodes=None, style="Regular"):
    f = TTFont(src)
    if unicodes:
        opts = subset.Options()
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        logging.getLogger("fontTools.subset").setLevel(logging.ERROR)  # dropped FFTM table
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=unicodes)
        sub.subset(f)
    set_vmetrics(f, asc, desc)
    set_names(f, family, style)
    f.recalcTimestamp = False  # reproducible files
    f.save(out)


def make_substitutes(src, out):
    """Build the substitutes from the sources in SRC (Poppins from OUT) into OUT."""
    symbol(f"{src}/StandardSymbolsPS.otf", f"{out}/DocxSymbol.otf")
    consolas(f"{src}/Inconsolata[wdth,wght].ttf", f"{out}/DocxConsolas.ttf")
    shim(f"{out}/Poppins-Regular.ttf", f"{out}/DocxPoppinsLabel.ttf", "Docx Poppins Label", 1135 / 1000, 0)
    for style in ("Regular", "Bold", "Italic", "BoldItalic"):
        shim(f"{src}/NimbusMonoPS-{style}.otf", f"{out}/DocxCourierNew-{style}.otf", "Docx Courier New",
             1705 / 2048, 615 / 2048, style=style.replace("BoldI", "Bold I"))
    shim(f"{src}/NimbusMonoPS-Regular.otf", f"{out}/DocxCourierLabel.otf", "Docx Courier Label", 1705 / 2048, 0)
    symbols = [*range(0x2190, 0x2200), *range(0x2600, 0x27C0), *range(0x2B00, 0x2C00)]
    shim(f"{src}/DejaVuSans.ttf", f"{out}/DocxSegoeSymbol.ttf", "Docx Segoe Symbol", 2210 / 2048, 514 / 2048,
         symbols)
    shim(f"{src}/DroidSansFallbackFull.ttf", f"{out}/DocxDengXian.ttf", "Docx DengXian", 1659 / 2048, 475 / 2048)
    shim(f"{src}/DroidSansFallbackFull.ttf", f"{out}/DocxSimSun.ttf", "Docx SimSun", 220 / 256, 36 / 256)
