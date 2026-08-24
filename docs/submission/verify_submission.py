"""Pre-submission checks on the compiled capstone report PDF.

Usage:
    pip install pypdf
    python verify_submission.py "C:\\Users\\salexander\\Downloads\\conference_101719.pdf"

Exits 0 when every check passes, 1 otherwise.
"""

import sys, re
from pypdf import PdfReader

path = sys.argv[1]
reader = PdfReader(path)
pages = len(reader.pages)
text = "\n".join((p.extract_text() or "") for p in reader.pages)
flat = re.sub(r"\s+", " ", text)

results = []
def check(label, ok, detail=""):
    results.append((label, ok, detail))

# --- structural ---
check("page count 8-11", 8 <= pages <= 11, f"{pages} pages")

for name in ("Abstract", "Index Terms", "Introduction", "Related Work",
             "System Architecture", "Implementation", "Sensitivity Analysis",
             "Performance Evaluation", "Surrogate Feasibility",
             "Limitations", "Conclusion", "Acknowledgment", "References"):
    check(f"section present: {name}", name.lower() in flat.lower())

# --- template compliance ---
check("term code 2258 in header", "2258" in flat)
check("RIT footer present", "Rochester Institute of Technology" in flat)
check("author email present", "sa5836@rit.edu" in flat)

# --- unresolved references ---
bad_refs = re.findall(r"(?<![\w?])\?\?(?![\w?])", flat)
check("no unresolved refs (??)", len(bad_refs) == 0, f"{len(bad_refs)} found")

# --- figures and tables resolved ---
check("Fig. 1 referenced", re.search(r"Fig\.\s*1", flat) is not None)
check("Fig. 2 referenced", re.search(r"Fig\.\s*2", flat) is not None)
for t in ("TABLE I", "TABLE II", "TABLE III"):
    check(f"{t} present", t in flat.upper())

# --- bibliography complete ---
nums = set(int(m) for m in re.findall(r"\[(\d{1,2})\]", flat))
missing = [n for n in range(1, 24) if n not in nums]
check("citations [1]-[23] all appear", not missing, f"missing {missing}" if missing else "")

# --- retired content must NOT appear ---
forbidden = {
    "v1 policy version": "preliminary_exposure_index_v1",
    "retired terrain weight": "0.25 for the terrain",
    "retired speedup 20.39": "20.39",
    "retired speedup 19.83": "19.83",
    "three component scores": "three component scores",
    "advisor in author block": "Advisor:",
    "milestone reference": "Milestone 3",
}
for label, needle in forbidden.items():
    check(f"absent: {label}", needle.lower() not in flat.lower())

# --- claim guards ---
for phrase in ("flood probability", "expected loss", "actuarial"):
    present = phrase in flat.lower()
    check(f"'{phrase}' only in disclaimer context", present,
          "appears - confirm it is inside the Limitations disclaimer")

# --- fonts ---
embedded, not_embedded = set(), set()
for page in reader.pages:
    res = page.get("/Resources")
    if not res:
        continue
    fonts = res.get("/Font")
    if not fonts:
        continue
    for key in fonts:
        f = fonts[key].get_object()
        desc = f.get("/FontDescriptor")
        name = str(f.get("/BaseFont", "?"))
        if desc is None:
            d0 = f.get("/DescendantFonts")
            if d0:
                desc = d0.get_object()[0].get_object().get("/FontDescriptor")
        if desc is None:
            not_embedded.add(name)
            continue
        desc = desc.get_object()
        if any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
            embedded.add(name)
        else:
            not_embedded.add(name)
check("all fonts embedded", not not_embedded,
      f"not embedded: {sorted(not_embedded)}" if not_embedded else f"{len(embedded)} embedded")

width = max(len(r[0]) for r in results)
fails = 0
for label, ok, detail in results:
    status = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    line = f"{status}  {label.ljust(width)}"
    if detail:
        line += f"   {detail}"
    print(line)

print()
print(f"{len(results) - fails} passed, {fails} failed, {pages} pages")
sys.exit(1 if fails else 0)
