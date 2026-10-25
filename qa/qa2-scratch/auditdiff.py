import json, re, sys
b = json.load(open(sys.argv[1])); a = json.load(open(sys.argv[2]))
norm = lambda u: re.sub(r"/b/\d+", "/b/N", re.sub(r"projects/\d+", "projects/P", u))
lab = lambda s: re.sub(r"\[\d+\]", "", s)
B = {norm(k): v for k, v in b.items()}
for k, av in ((norm(k), v) for k, v in a.items()):
    bv = B.get(k, {"sideways": 0, "small": []})
    old = {lab(s) for s in bv["small"]}
    new = [s for s in av["small"] if lab(s) not in old]
    fixed = sorted(old - {lab(s) for s in av["small"]})
    if av["sideways"] or new or fixed:
        print(k, "| sideways", av["sideways"], "| NEW <44:", new, "| fixed:", fixed)
print("pages:", len(a))
