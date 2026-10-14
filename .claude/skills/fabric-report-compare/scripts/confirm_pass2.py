# -*- coding: utf-8 -*-
"""Doi chung luot 2: khac biet chi duoc tinh la THAT khi lap lai o ca hai luot.

Luot 1 nam o shots/, luot 2 chup doc lap vao shots2/. Voi moi o da bi bao khac,
so lai chu cua v0 va ban do TRONG CUNG MOT LUOT, roi doi chieu hai luot voi nhau.
"""
import io, json, os

D = os.environ.get("FRC_WORK") or os.getcwd()
RUN = os.environ.get("FRC_RUN") or D


def txt(root, st, v, rk, pk):
    p = os.path.join(RUN, root, "text", "%s__%s__%s__%s.txt" % (st, v, rk, pk))
    try:
        return io.open(p, encoding="utf-8").read()
    except Exception:
        return None


rows = json.load(io.open(os.path.join(RUN, "diff_results.json"), encoding="utf-8"))
diffs = [r for r in rows if r.get("status") == "DIFF"]

lap, khong, thieu = [], [], []
for r in diffs:
    st, v, rk, pk = r["state"], r["v"], r["rk"], r["pk"]
    a2, b2 = txt("shots2", st, "v0", rk, pk), txt("shots2", st, v, rk, pk)
    if a2 is None or b2 is None:
        thieu.append(r); continue
    (lap if a2 != b2 else khong).append(r)

print("o bao khac o luot 1: %d" % len(diffs))
print("  lap lai o luot 2  : %d" % len(lap))
print("  KHONG lap lai     : %d" % len(khong))
print("  chua chup luot 2  : %d" % len(thieu))
for r in khong:
    print("    KHONG LAP:", r["rk"], r["pk"], r["v"], r["state"])
for r in lap:
    print("    lap:", r["rk"], r["pk"], r["v"], r["state"])

io.open(os.path.join(RUN, "pass2_confirm.json"), "w", encoding="utf-8").write(
    json.dumps({"lap": [[r["rk"], r["pk"], r["v"], r["state"]] for r in lap],
                "khong": [[r["rk"], r["pk"], r["v"], r["state"]] for r in khong],
                "thieu": [[r["rk"], r["pk"], r["v"], r["state"]] for r in thieu]},
               ensure_ascii=False, indent=1))
