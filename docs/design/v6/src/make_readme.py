"""Writes ../README.md: what v6 is, how to read the boards, and an index of every board (read from html/)."""
import os, re, html

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for f in sorted(os.listdir(os.path.join(HERE, "html")), key=lambda x: (x.startswith("P-"), x)):
    s = open(os.path.join(HERE, "html", f)).read()
    m = re.search(r'<div class="label"><b>(.*?)</b><span>(.*?)</span><span class="tag">(.*?)</span>', s)
    rows.append(tuple(html.unescape(x) for x in m.groups()))

SECTIONS = [("S0", "The frame and folder tree"), ("S1", "Brand home: an open folder"), ("S2", "New video"), ("S3", "The video: chat + preview panel"),
            ("S4", "Ask cards"), ("S5", "Cast and presenter"), ("S6", "Clips"), ("S7", "Cut editor"), ("S8", "Brand library"), ("S9", "Needs you"), ("P-", "Phone (390)"), ("S-gaps", "Gaps the builders found (options for Reed)")]

out = [open(os.path.join(HERE, "README.head.md")).read().rstrip(), ""]
for pre, name in SECTIONS:
    rs = [r for r in rows if r[0].startswith(pre)]
    out += [f"### {name}", "", "| Board | State |", "|---|---|"]
    out += [f"| [{b}](boards/{b}.jpg) | {st} |" for b, t, st in rs]
    out.append("")
out.append(f"{len(rows)} boards in all: {sum(1 for r in rows if not r[0].startswith('P-'))} desktop (1440) and sheets, {sum(1 for r in rows if r[0].startswith('P-'))} phone (390).")
open(os.path.join(HERE, "..", "README.md"), "w").write("\n".join(out) + "\n")
print(len(rows))
