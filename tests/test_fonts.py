import io, lzma, tarfile

from microslop import fonts


def test_deb_members():
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w") as t:
        info = tarfile.TarInfo("./usr/share/fonts/X.ttf")
        info.size = 3
        t.addfile(info, io.BytesIO(b"abc"))
    data = lzma.compress(tar.getvalue())

    def member(name, body):
        return f"{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(body):<10}`\n".encode() + body + b"\n" * (len(body) % 2)
    deb = b"!<arch>\n" + member("debian-binary", b"2.0\n") + member("data.tar.xz", data)
    assert list(fonts.deb_members(deb)) == [("X.ttf", b"abc")]


def test_pins():
    for url, sha, *_ in fonts.DEBS + fonts.FILES:
        assert len(sha) == 64 and url.startswith(("http://archive.ubuntu.com/", "https://raw.githubusercontent.com/"))
