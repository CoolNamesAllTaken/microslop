#!/bin/bash
# Builds headless LibreOffice with patches/libreoffice/*.patch and packages it.
#   tools/build-lo/build.sh WORKDIR
# Output: WORKDIR/libreoffice-$LO_VERSION-$MS_REV-linux-x86_64.tar.gz (top dir libreoffice/).
# Env: LO_VERSION, LO_SHA256, MS_REV (see versions.env), PARALLELISM (default nproc).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
. "$HERE/versions.env"
WORK=$(mkdir -p "$1" && cd "$1" && pwd)
SRC=$WORK/libreoffice-$LO_VERSION
TARBALL=$WORK/libreoffice-$LO_VERSION.tar.xz
NAME=libreoffice-$LO_VERSION-$MS_REV-linux-x86_64

if [ ! -f "$TARBALL" ]; then
  series=${LO_VERSION%.*}
  curl -fL -o "$TARBALL.part" "https://download.documentfoundation.org/libreoffice/src/$series/libreoffice-$LO_VERSION.tar.xz" ||
    curl -fL -o "$TARBALL.part" "https://downloadarchive.documentfoundation.org/libreoffice/old/$LO_VERSION/src/libreoffice-$LO_VERSION.tar.xz"
  mv "$TARBALL.part" "$TARBALL"
fi
echo "$LO_SHA256  $TARBALL" | sha256sum -c -

if [ ! -d "$SRC" ]; then
  tar -C "$WORK" -xf "$TARBALL"
  for p in "$REPO"/patches/libreoffice/*.patch; do
    echo "Applying $(basename "$p")"
    git -C "$SRC" apply "$p"
  done
fi

cd "$SRC"
cp "$HERE/autogen.input" autogen.input
printf -- "--with-parallelism=%s\n--with-external-tar=%s\n" "${PARALLELISM:-$(nproc)}" "$WORK/tarballs" >> autogen.input
[ -f config_host.mk ] || ./autogen.sh
make build

# Relocatable install tree: instdir/ renamed to libreoffice/.
rm -rf "$WORK/$NAME" && mkdir -p "$WORK/$NAME"
cp -a instdir "$WORK/$NAME/libreoffice"
tar -C "$WORK/$NAME" -czf "$WORK/$NAME.tar.gz" libreoffice
(cd "$WORK" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256")
echo "Built $WORK/$NAME.tar.gz"
