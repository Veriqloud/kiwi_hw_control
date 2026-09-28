#!/usr/bin/env bash
# Render config_reference.md to config_reference.pdf (needs pandoc and chromium).
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/style.css" <<'CSS'
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 9.5pt; line-height: 1.4; color: #1b2530; max-width: none; margin: 0; }
header { border-bottom: 2px solid #1e7f66; margin-bottom: 14pt; padding-bottom: 6pt; }
h1.title { font-size: 20pt; margin: 0; }
p.subtitle { font-size: 12pt; color: #1e7f66; margin: 2pt 0 0; }
h1 { font-size: 15pt; margin: 20pt 0 6pt; color: #13212b; break-after: avoid; }
h2 { font-size: 11.5pt; margin: 14pt 0 4pt; color: #1e7f66; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; }
th, td { border: 0.5pt solid #c9cfc9; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #e4e7e1; }
tr { break-inside: avoid; }
td:first-child code { white-space: nowrap; }
td:last-child { width: 55%; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.5pt; background: #f1f2ee; padding: 0 2pt; border-radius: 2pt; }
pre { background: #f1f2ee; padding: 6pt 8pt; border-radius: 3pt; }
pre code { background: none; padding: 0; }
CSS
pandoc config_reference.md -s --embed-resources -c "$tmp/style.css" -o "$tmp/ref.html"
# Let the browser size the columns to their content.
perl -0pi -e 's{<colgroup>.*?</colgroup>}{}gs' "$tmp/ref.html"
chromium --headless --no-sandbox --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PWD/config_reference.pdf" "file://$tmp/ref.html" 2>/dev/null
echo "wrote config_reference.pdf"
