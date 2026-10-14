#!/usr/bin/env bash
# Build the public site into ./site: the landing page and demo console (website/) at the root, the MkDocs documentation
# under /docs/. Screenshots and films are committed; they come from demo/ on an invented mailbox, never from real mail.
#   pip install -r requirements-docs.txt && bash scripts/build-site.sh       # then: python3 -m http.server -d site 8000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
rm -rf site
mkdocs build --strict -d site/docs
cp -R website/. site/
# the landing page and the console read their data, fonts and media from the docs' assets
for f in demo/run.json js/linemap.js brand/transit.css video/film.en.mp4 video/film.fr.mp4; do
  test -f "site/docs/assets/$f" || { echo "missing site/docs/assets/$f" >&2; exit 1; }
done
echo "site/ ready: $(du -sh site | cut -f1)"
