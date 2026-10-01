"""Build stratum H (hard negatives) from the Antenatal Orientation Speech Dataset (ADR-0020).

    python scripts/build_adeola_items.py            # downloads the transcripts if needed

Source: Ajagbe S. A. (2024), GitHub Adeola80/Antenatal-Speech, MIT licence. The texts are
a health worker's antenatal teaching, not a woman reporting her own symptoms, so every
sentence's gold record is empty: the scribe must record nothing. Writes
data/bench/h.adeola.jsonl and the MIT notice beside it.
"""

from __future__ import annotations

import hashlib
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "serve"), str(ROOT)]

from bench.items import BenchItem, write_jsonl  # noqa: E402
from phc_scribe.encounter import Encounter  # noqa: E402

RAW = "https://raw.githubusercontent.com/Adeola80/Antenatal-Speech/main/"
FILES = {
    "en": "ANTINATAL ORIENTATION (English).docx",
    "yo": "ANTINATAL ORIENTATION TEXT YORUBA.docx",
    "pcm": "ANTINATAL ORIENTATION (Anti Pigin).docx",
}
# Pinned when downloaded and inspected (1 Oct 2026); only these exact files are parsed.
SHA256 = {
    "en": "fa7f9fad23e6fdb32e07bfc6c942fe8e6b03dccf80b9c8d901b4f10b8a07bf61",
    "yo": "3c7be28ae8c735a9506eb04c78d02961e69ab211c733a7ee5ea219eec6e65e8e",
    "pcm": "c80a2cdeb239972c399bd31ac8c5c1de25ce57227c5a395f48aed5c069dde931",
}
SRC_DIR = ROOT / "data" / "private" / "adeola"
OUT = ROOT / "data" / "bench" / "h.adeola.jsonl"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NOTICE = """Stratum H items are sentences from the Antenatal Orientation Speech Dataset:
Ajagbe S. A. (2024) Developing Nigeria Multilingual Languages Speech Datasets for
Antenatal Orientation, Applied Informatics (Springer CCIS), doi 10.1007/978-3-031-75147-9_11.
https://github.com/Adeola80/Antenatal-Speech

MIT License

Copyright (c) 2024 Ajagbe Sunday Adeola

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be included in all copies
or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


def paragraphs(docx: Path) -> list[str]:
    # The file is checksum-pinned before parsing (see build), so it is not untrusted input.
    root = ElementTree.fromstring(zipfile.ZipFile(docx).read("word/document.xml"))  # noqa: S314
    out = []
    for p in root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        if text:
            out.append(text)
    return out


def sentences(paragraph: str) -> list[str]:
    """Split on sentence ends and on numbered-list markers ("1.", "2.") inside a paragraph."""
    parts = re.split(r"(?<=[.?!])\s+|(?<!\d)\b\d{1,2}\.(?=\s*\S)", paragraph)
    return [" ".join(p.split()) for p in parts if p and len(p.split()) >= 3]


def build() -> list[BenchItem]:
    items: list[BenchItem] = []
    for lang, name in FILES.items():
        path = SRC_DIR / name
        if not path.exists():
            SRC_DIR.mkdir(parents=True, exist_ok=True)
            url = RAW + urllib.parse.quote(name)
            with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (fixed https URL)
                path.write_bytes(r.read())
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != SHA256[lang]:
            sys.exit(f"checksum mismatch for {name}: expected {SHA256[lang]}, got {got}")
        paras = paragraphs(path)[1:]  # the first paragraph is the document title
        n = 0
        for para in paras:
            for sent in sentences(para):
                n += 1
                items.append(
                    BenchItem(
                        item_id=f"h-adeola-{lang}-{n:03d}",
                        group_id=f"adeola:{lang}",
                        stratum="H",
                        language=lang,  # type: ignore[arg-type]
                        origin="real",
                        transcript=sent,
                        gold=Encounter(),
                    )
                )
    return items


def main() -> int:
    items = build()
    n = write_jsonl(OUT, items)
    OUT.with_suffix(".LICENSE").write_text(NOTICE)
    by_lang = {lang: sum(1 for i in items if i.language == lang) for lang in FILES}
    print(f"wrote {n} hard-negative items to {OUT.relative_to(ROOT)}: {by_lang}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
