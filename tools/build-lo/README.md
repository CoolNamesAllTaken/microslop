# build-lo

Builds headless LibreOffice with `patches/libreoffice/*.patch` and packages it as
`libreoffice-<version>-<rev>-linux-x86_64.tar.gz` (versions in `versions.env`).

```sh
tools/build-lo/build.sh /path/to/workdir   # outside any git checkout
```

- Configure options: `autogen.input`. No GUI, Java, Python, help or database drivers.
- Build dependencies (Ubuntu 24.04): `autoconf automake bison ccache flex gperf libfontconfig-dev
  libfreetype-dev nasm pkg-config uuid-dev zip zlib1g-dev`, GCC 13 or newer.
- Disk: about 25 GB. Time: about 1 h 45 min on 7 cores, about 2 h 15 min on a GitHub runner (cold ccache).
- Run: `libreoffice/program/soffice --headless --convert-to pdf file.docx`. The tree is
  relocatable; it needs only libraries in a standard Ubuntu 24.04 install (glibc 2.38+, libstdc++,
  fontconfig, freetype, zlib).

The `build-libreoffice` workflow runs this on `ubuntu-24.04` (manual dispatch), keeps ccache between
runs, and publishes the tarball as a release asset tagged `libreoffice-<version>-<rev>`.
