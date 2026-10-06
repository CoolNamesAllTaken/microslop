import pymupdf

from microslop import compare


def pdf(path, dy=0, bullet=True):
    d = pymupdf.open()
    page = d.new_page()
    for i, text in enumerate(("First line of text", "Second line of text", "Third line")):
        page.insert_text((72, 100 + 20 * i + (dy if i else 0)), text, fontname="helv", fontsize=11)
    if bullet:
        page.insert_text((72, 200), "o", fontname="cour", fontsize=11)
        page.insert_text((100, 200), "Bullet item", fontname="helv", fontsize=11)
    d.save(path)
    return str(path)


def test_same(tmp_path):
    a = pdf(tmp_path / "a.pdf")
    assert compare.run(a, pdf(tmp_path / "b.pdf"), png=str(tmp_path / "png"))
    assert list((tmp_path / "png").glob("*_ring_word_left_ours_right.png"))


def test_moved_line(tmp_path):
    res, _, _ = compare.compare_lines(pdf(tmp_path / "a.pdf"), pdf(tmp_path / "b.pdf", dy=5))
    assert res["wrong_y"] == 6 and res["first_y_diff"]["word"] == "Second"
    assert not compare.run(str(tmp_path / "a.pdf"), str(tmp_path / "b.pdf"))


def test_missing_bullet(tmp_path):
    _, ww = compare.bullets(pdf(tmp_path / "a.pdf"))
    _, oo = compare.bullets(pdf(tmp_path / "b.pdf", bullet=False))
    assert [w["kind"] for w in ww] == ["ring"]
    pairs, missing, extra = compare.match(ww, oo)
    assert len(missing) == 1 and not pairs and not extra
