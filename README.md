# microslop

A vibe-slopped collection of utilities that patch LibreOffice to do things a little bit more like Microsoft Office products.

## docx2pdf

Converts Word documents to PDF with LibreOffice, laid out like Word: same line breaks, page breaks and bullets on the documents it was tuned on. It converts an adjusted copy of each docx (the input is never changed) with substitute fonts that have Word's font metrics.

### Install

Needs Linux (x86_64), Python 3.10+, fontconfig (`fc-match`) and LibreOffice. Tuned with LibreOffice 26.8.1.1.

```sh
pip install "microslop[compare] @ git+https://github.com/CoolNamesAllTaken/microslop"
```

### CLI

```sh
microslop docx2pdf report.docx                 # report.pdf next to it
microslop docx2pdf a.docx b.docx --outdir pdf/
microslop docx2pdf report.docx -o out.pdf --soffice /opt/libreoffice26.8/program/soffice
microslop fonts --check                        # build the fonts, print the fontconfig file
microslop prep report.docx adjusted.docx       # just the adjusted copy
microslop compare word.pdf ours.pdf --png diff/
```

- `docx2pdf` finds LibreOffice via `--soffice`, `$SOFFICE`, `PATH` or `/opt/libreoffice*`.
- `fonts` downloads pinned font files (sha256 checked) to `~/.cache/microslop/fonts` and builds the substitutes. `docx2pdf` does this on first use.
- `compare` checks a PDF against Word's export of the same docx: page count, the page and position of every word, line breaks, and every list bullet (glyph, position, size, ink). `--png` writes Word/ours side-by-side renders of the worst page and bullet crops. Exits 1 on any difference.

### GitHub Action

```yaml
- uses: CoolNamesAllTaken/microslop@main  # pin a tag or commit
  id: docx2pdf
  with:
    files: docs/*.docx            # space/newline separated, globs allowed
    output-dir: docs/exports      # default: next to each docx
- run: echo "${{ steps.docx2pdf.outputs.pdfs }}"
```

Runs on `ubuntu-24.04`. It installs LibreOffice from the TDF archive (cached), builds the fonts and converts the files.

| Input | Default | |
|---|---|---|
| `files` | | docx files to convert |
| `output-dir` | next to each docx | |
| `lo-version` | `26.8.1.1` | set `lo-sha256` with it |
| `lo-sha256` | sha256 of the 26.8.1.1 debs | |
| `lo-url` | TDF debs for `lo-version` | another LibreOffice tarball, e.g. a patched build: TDF-style `*/DEBS/*.deb` or an install tree with `*/program/soffice` |
| `python-version` | `3.12` | |

### What it fixes

Fonts (free substitutes with Word's line metrics):

- Calibri: Carlito. Times New Roman, Arial: Liberation.
- Symbol bullets (U+F0B7): URW Standard Symbols PS with a symbol cmap, at SymbolMT's position.
- Courier New: URW Nimbus Mono PS (thin round `o` bullets like Word).
- Consolas: Inconsolata at Consolas's width.
- Segoe UI Symbol check marks, DengXian/SimSun full-width punctuation.
- Poppins from Google Fonts.
- List labels in Courier New or Poppins don't add line descent, like Word.

Document adjustments (`prep`):

- Line breaks before ` /`, ` )` and after hyphens in paths, like Word.
- Header/footer inheritance between sections; title pages without a footer.
- A page break before a continuous section break starts the next section on the new page.
- TOC tab runs don't make TOC lines taller.
- No bullet on a list paragraph holding only a page break.
- Table indent and cell margins of Word's 2007 compatibility mode.
- Check marks in their own Segoe UI Symbol runs (line height).
- Theme East Asian fonts.
- Spacing after a two-column section.
- Widow control off for one-line paragraphs (works around a LibreOffice bug that leaves a paragraph on the next page beside a header image).

### Known gaps

- Tables and paragraphs next to a wrapping image in the header: LibreOffice shrinks where Word moves down, and the reverse.
- Word's rule for splitting a table row across pages.
- TOC fields are not updated (Word's PDF keeps the saved numbers too).
- Only fonts listed above get Word metrics; others go through fontconfig as usual. Put extra fonts in `~/.local/share/fonts`.
- Local runs only match CI with the same LibreOffice version. Fonts are pinned, but system fonts with the same family names can still win in fontconfig.

## License

MIT
