"""Compare a LibreOffice PDF against Word's PDF of the same docx.

Lines: words are aligned by text (difflib); for each aligned word, page, baseline y and x are compared.
A line break difference is an aligned word that starts a visual line in one PDF but not the other.

Bullets: every list bullet in Word's PDF must appear in ours with the same glyph type at the same
position (within BULLET_TOL), with the text after it at the same x, and no extra bullets. Glyph shape
and weight come from 600 dpi renders: ink bbox (w x h, pt) and ink mass (sum of darkness, pt^2).
"""
import difflib, json, os, re, unicodedata

import pymupdf

TOL = 2.0  # points, lines
BULLET_TOL = 1.0


def norm(t):
    t = unicodedata.normalize("NFKC", t).replace("\u200b", "")
    # Word/Quartz maps some Calibri ligatures to wrong Unicode (ti -> 9 / U)
    t = re.sub(r"(?<=[a-z])[9U](?=[a-z])", "ti", t)
    t = re.sub(r"(?<=[a-z])[9U]$", "ti", t)
    t = t.translate(str.maketrans("‘’“”–—", "''\"\"--"))
    return t.lower()


def words(path):
    """Words with baseline y (from glyph origins), in content order."""
    d = pymupdf.open(path)
    out = []
    for pno, page in enumerate(d):
        prev = None
        for b in page.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                cur = []
                chars = [c for s in l["spans"] for c in s["chars"]] + [None]
                for i, c in enumerate(chars):
                    # Tab leaders: a run of dots separates words
                    leader = c is not None and c["c"] == "." and any(
                        x is not None and x["c"] == "." for x in chars[max(0, i - 2):i] + chars[i + 1:i + 3])
                    if c is None or c["c"].isspace() or leader:
                        if cur:
                            t = "".join(x["c"] for x in cur)
                            x0, y = cur[0]["origin"]
                            start = prev is None or abs(y - prev[1]) > 1.0 or x0 < prev[0]
                            out.append(dict(p=pno + 1, x=round(x0, 1), y=round(y, 1), t=t, n=norm(t), start=start))
                            prev = (x0, y)
                        cur = []
                    else:
                        cur.append(c)
    return d, out


def compare_lines(word_pdf, our_pdf):
    """Word-by-word page, line break and position check."""
    dw, ww = words(word_pdf)
    do, wo = words(our_pdf)
    sm = difflib.SequenceMatcher(None, [w["n"] for w in ww], [w["n"] for w in wo], autojunk=False)
    pairs = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        # Same-size replacements are mostly Word's garbled ligature text (ti -> N etc.) and bullet code points
        if op == "equal" or (op == "replace" and a2 - a1 == b2 - b1):
            pairs += zip(ww[a1:a2], wo[b1:b2])
    res = dict(word_pages=dw.page_count, our_pages=do.page_count, words_word=len(ww), words_ours=len(wo),
               aligned=len(pairs))
    page_bad, first_page, first_y, first_break = {}, None, None, None
    n_page = n_y = n_x = n_break = 0
    first_x = None
    for i, (a, b) in enumerate(pairs):
        bad = False
        if a["p"] != b["p"]:
            n_page += 1; bad = True
            first_page = first_page or (a, b)
        elif abs(a["y"] - b["y"]) > TOL:
            n_y += 1; bad = True
            first_y = first_y or (a, b)
        elif abs(a["x"] - b["x"]) > TOL:
            n_x += 1; bad = True
            first_x = first_x or (a, b)
        if i and a["start"] != b["start"]:
            n_break += 1; bad = True
            first_break = first_break or (a, b)
        if bad:
            page_bad[a["p"]] = page_bad.get(a["p"], 0) + 1
    res.update(wrong_page=n_page, wrong_y=n_y, wrong_x=n_x, break_diff=n_break, bad_words_per_word_page=page_bad)

    def ctx(pair):
        if not pair:
            return None
        a, b = pair
        # Show the Word line containing a
        line = " ".join(w["t"] for w in ww if w["p"] == a["p"] and abs(w["y"] - a["y"]) < 1)
        return dict(word=a["t"], word_page=a["p"], word_y=a["y"], word_x=a["x"], our_page=b["p"], our_y=b["y"],
                    our_x=b["x"], word_start=a["start"], our_start=b["start"], line=line[:120])
    res["first_page_diff"] = ctx(first_page)
    res["first_y_diff"] = ctx(first_y)
    res["first_break_diff"] = ctx(first_break)
    res["first_x_diff"] = ctx(first_x)
    res["worst_page"] = max(page_bad, key=page_bad.get) if page_bad else None
    return res, dw, do


def side_by_side(dw, do, pno, out, dpi=70):
    pa = dw[pno - 1].get_pixmap(dpi=dpi)
    pb = do[pno - 1].get_pixmap(dpi=dpi) if pno <= do.page_count else None
    w, h = pa.width, pa.height
    img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2 * w + 10, h), False)
    img.clear_with(160)
    for i, p in enumerate((pa, pb)):
        if p is None:
            continue
        if p.alpha:
            p = pymupdf.Pixmap(p, 0)
        p.set_origin(i * (w + 10), 0)
        img.copy(p, p.irect)
    img.save(out)


FONTS = ("Symbol", "Courier", "Wingding", "LiberationMono", "NimbusMono", "OpenSymbol", "DejaVu", "Docx")
KIND = {"•": "disc", "": "disc", "·": "disc", "o": "ring", "": "ring", "◦": "ring",
        "": "square", "§": "square", "▪": "square", "■": "square", "": "arrow"}
DPI = 600


def bullets(path):
    """List bullets: the first visible char of a line, in a bullet font, followed by a gap (tab)."""
    d = pymupdf.open(path)
    out = []
    for pno, page in enumerate(d):
        for b in page.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                chars = [(c, s) for s in l["spans"] for c in s["chars"]]
                for i, (c, s) in enumerate(chars):
                    if c["c"].isspace():
                        continue
                    # the first visible char of the line, in a bullet font, followed by a gap (tab)
                    font = s["font"].split("+")[-1]
                    if c["c"] in KIND and font.startswith(FONTS):
                        rest = [x for x, _ in chars[i + 1:] if not x["c"].isspace()]
                        if not rest or rest[0]["bbox"][0] - c["bbox"][2] > 3:
                            out.append(dict(p=pno + 1, x=round(c["origin"][0], 2), y=round(c["origin"][1], 2),
                                            kind=KIND[c["c"]], font=font, size=round(s["size"], 1),
                                            text_x=round(rest[0]["origin"][0], 2) if rest else None,
                                            text=("".join(x["c"] for x in rest))[:40] if rest else "",
                                            bbox=c["bbox"]))
                    break
    return d, out


def ink(doc, bl, pad=None):
    """Ink bbox and mass of the bullet glyph, from a DPI render of a clip around its origin."""
    page = doc[bl["p"] - 1]
    x, y, sz = bl["x"], bl["y"], bl["size"]
    clip = pymupdf.Rect(x - 1, y - 0.6 * sz, x + 0.62 * sz, y + 0.15 * sz)  # bullet glyphs only
    pix = page.get_pixmap(dpi=DPI, clip=clip, colorspace=pymupdf.csGRAY)
    w, h, s = pix.width, pix.height, pix.samples
    k = 72 / DPI
    xs, ys, mass = [], [], 0
    for j in range(h):
        row = s[j * w:(j + 1) * w]
        for i, v in enumerate(row):
            if v < 200:
                xs.append(i), ys.append(j)
            mass += 255 - v
    if not xs:
        return dict(w=0, h=0, mass=0, cx=None, cy=None)
    return dict(w=round((max(xs) - min(xs) + 1) * k, 2), h=round((max(ys) - min(ys) + 1) * k, 2),
                mass=round(mass / 255 * k * k, 2),
                cx=round(clip.x0 + (min(xs) + max(xs) + 1) / 2 * k, 2),
                cy=round(clip.y0 + (min(ys) + max(ys) + 1) / 2 * k, 2))


def match(ww, oo):
    """Pair bullets by page and order of y, allowing small drifts; returns pairs, missing, extra."""
    pairs, missing, used = [], [], set()
    for w in ww:
        cands = [(abs(o["y"] - w["y"]) + abs(o["x"] - w["x"]), j) for j, o in enumerate(oo)
                 if j not in used and o["p"] == w["p"] and abs(o["y"] - w["y"]) < 8 and abs(o["x"] - w["x"]) < 20]
        if cands:
            j = min(cands)[1]
            used.add(j)
            pairs.append((w, oo[j]))
        else:
            missing.append(w)
    extra = [o for j, o in enumerate(oo) if j not in used]
    return pairs, missing, extra


def bullet_crops(dw, do, pairs, outdir, name):
    """Per bullet kind: Word | ours, the first few examples, 600 dpi, glyph plus start of text."""
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for kind in ("disc", "ring", "square", "arrow"):
        ex = [p for p in pairs if p[0]["kind"] == kind]
        if not ex:
            continue
        # spread examples over the doc
        ex = [ex[i * len(ex) // min(4, len(ex))] for i in range(min(4, len(ex)))]
        tiles = []
        for w, o in ex:
            row = []
            for doc, b, ref in ((dw, w, w), (do, o, w)):
                # same clip for both, anchored at Word's bullet, so offsets show
                clip = pymupdf.Rect(ref["x"] - 4, ref["y"] - 11, ref["x"] + 60, ref["y"] + 4)
                row.append(doc[b["p"] - 1].get_pixmap(dpi=DPI, clip=clip))
            tiles.append(row)
        tw, th = tiles[0][0].width, tiles[0][0].height
        gap = 20
        sheet = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2 * tw + 3 * gap, len(tiles) * (th + gap) + gap), 0)
        sheet.clear_with(255)
        for r, (a, b) in enumerate(tiles):
            for c, px in enumerate((a, b)):
                px.set_origin(gap + c * (tw + gap), gap + r * (th + gap))
                sheet.copy(px, px.irect)
        # red guide lines at Word's baseline and bullet x in both columns
        for r in range(len(tiles)):
            for c in range(2):
                x0, y0 = gap + c * (tw + gap), gap + r * (th + gap)
                bx = x0 + round(4 * DPI / 72)
                by = y0 + round(11 * DPI / 72)
                for yy in range(y0, y0 + th):
                    sheet.set_pixel(bx, yy, (255, 0, 0))
                for xx in range(x0, x0 + tw):
                    sheet.set_pixel(xx, by, (255, 0, 0))
        p = f"{outdir}/{name}_{kind}_word_left_ours_right.png"
        sheet.save(p)
        paths.append(p)
    return paths


def check_bullets(dw, ww, do, oo):
    """Pairs, missing, extra and off bullets ((word, ours, errors) for each off one)."""
    pairs, missing, extra = match(ww, oo)
    bad = []
    for w, o in pairs:
        iw, io = ink(dw, w), ink(do, o)
        w["ink"], o["ink"] = iw, io
        errs = []
        if w["kind"] != o["kind"]:
            errs.append(f"kind {w['kind']}->{o['kind']}")
        if abs(w["x"] - o["x"]) > BULLET_TOL or abs(w["y"] - o["y"]) > BULLET_TOL:
            errs.append(f"pos dx {o['x'] - w['x']:+.2f} dy {o['y'] - w['y']:+.2f}")
        if w["text_x"] and o["text_x"] and abs(w["text_x"] - o["text_x"]) > BULLET_TOL:
            errs.append(f"text dx {o['text_x'] - w['text_x']:+.2f}")
        if iw["cx"] and io["cx"]:
            if abs(iw["w"] - io["w"]) > 0.4 or abs(iw["h"] - io["h"]) > 0.4:
                errs.append(f"glyph {iw['w']}x{iw['h']} -> {io['w']}x{io['h']}")
            if abs(io["mass"] - iw["mass"]) > 0.25 * max(iw["mass"], 0.5):
                errs.append(f"ink {iw['mass']} -> {io['mass']}")
            if abs(iw["cx"] - io["cx"]) > BULLET_TOL or abs(iw["cy"] - io["cy"]) > BULLET_TOL:
                errs.append(f"ink center d{io['cx'] - iw['cx']:+.2f},{io['cy'] - iw['cy']:+.2f}")
        if errs:
            bad.append((w, o, errs))
    return pairs, missing, extra, bad


def run(word_pdf, our_pdf, png=None, pages=None, json_out=None):
    """Run both checks, print a report; returns True if everything matches."""
    name = os.path.basename(word_pdf).split(".")[0]
    res, dw, do = compare_lines(word_pdf, our_pdf)
    _, ww = bullets(word_pdf)
    _, oo = bullets(our_pdf)
    pairs, missing, extra, bad = check_bullets(dw, ww, do, oo)
    print(f"{name}: pages Word {res['word_pages']} ours {res['our_pages']}, words aligned {res['aligned']}"
          f"/{res['words_word']}, wrong page {res['wrong_page']}, wrong y {res['wrong_y']}, wrong x "
          f"{res['wrong_x']}, line breaks {res['break_diff']}")
    for key in ("first_page_diff", "first_break_diff", "first_y_diff", "first_x_diff"):
        d = res[key]
        if d:
            print(f"  {key.replace('_', ' ')}: Word p{d['word_page']} y{d['word_y']} x{d['word_x']}, ours "
                  f"p{d['our_page']} y{d['our_y']} x{d['our_x']}: {d['line'][:70]!r}")
    if res["bad_words_per_word_page"]:
        print("  differing words per Word page:", res["bad_words_per_word_page"])
    print(f"  bullets: Word {len(ww)}, ours {len(oo)}, matched {len(pairs)}, missing {len(missing)}, "
          f"extra {len(extra)}, off {len(bad)}")
    for w in missing:
        print(f"    missing p{w['p']} y{w['y']} {w['kind']} {w['text']!r}")
    for o in extra:
        print(f"    extra p{o['p']} y{o['y']} {o['kind']} {o['text']!r}")
    for w, o, errs in bad[:15]:
        print(f"    off p{w['p']} y{w['y']} {w['kind']} {w['text'][:25]!r}: {'; '.join(errs)}")
    if len(bad) > 15:
        print(f"    ... {len(bad) - 15} more")
    if png:
        os.makedirs(png, exist_ok=True)
        for p in pages or ([res["worst_page"]] if res["worst_page"] else []):
            f = f"{png}/{name}_p{p}_word_left_ours_right.png"
            side_by_side(dw, do, p, f)
            print("  png", f)
        for f in bullet_crops(dw, do, pairs, png, name):
            print("  png", f)
    res["bullets"] = dict(word=len(ww), ours=len(oo), matched=len(pairs), missing=missing, extra=extra,
                          off=[dict(word=w, ours=o, errors=e) for w, o, e in bad])
    if json_out:
        with open(json_out, "w") as f:
            json.dump(res, f, indent=1)
    return res["word_pages"] == res["our_pages"] and not (
        res["wrong_page"] or res["wrong_y"] or res["wrong_x"] or res["break_diff"] or missing or extra or bad)
