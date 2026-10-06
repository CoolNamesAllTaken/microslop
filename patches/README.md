# Patches

## libreoffice/

LibreOffice Writer layout fixes for DOCX files, applied to LibreOffice 26.8.1.1 by
`tools/build-lo/build.sh`. Each patch is a `git format-patch` commit with a unit test, ready for
[gerrit](https://gerrit.libreoffice.org) review. None has been submitted upstream yet.

| Patch | Fixes |
|---|---|
| `0001-sw-header-fly-move-back.patch` | A paragraph pushed to the next page beside an image in the page header never moves back, though it fits on the previous page as fewer lines. |
| `0002-sw-docx-table-beside-fly.patch` | Tables next to a wrapped image: Word 2013+ (DOCX compatibilityMode 15) moves the table below the image; older modes narrow an autofit table to fit beside it. LibreOffice did the opposite in some cases. |
| `0003-sw-docx-widows-in-split-rows.patch` | Widow and orphan control in table rows split across pages, as Word 2013+ does. |

`master/0002-sw-docx-table-beside-fly.patch` is 0002 rebased onto LibreOffice master (October 2026;
`SwTabFrame::Format()` changed there). 0001 and 0003 apply to master as they are.

To work on a patch: unpack the LibreOffice source, `git init` and commit it, `git am` the patches,
edit, then `git format-patch` again.
