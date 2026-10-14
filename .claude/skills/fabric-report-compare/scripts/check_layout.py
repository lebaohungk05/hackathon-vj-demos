# -*- coding: utf-8 -*-
"""Doi chieu chu ky bo cuc giua v0 va tung version.

Chu ky = toa do (x,y,w,h) cua moi visual so voi mep displayArea. Neu canvas bi
day ngang thi visual trai nhat bi cuon ra ngoai va visual khac tut vao vi tri 0,
nen kiem "min x >= 0" khong bat duoc. So chu ky thi bat duoc ngay: so visual
hoac toa do se lech.
"""
import io, json, os, sys, collections

# Report/page names carry real Japanese text (e.g. dataset/page labels), and Windows' default
# console codepage (cp1252) can't encode it - printing one crashes the whole date-range check
# after the (expensive, already-done) screenshot capture finishes. Force utf-8 on stdout/stderr
# so this script's own prints never fail on the very data it's built to report on.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os as _os
W = _os.environ.get("FRC_WORK") or _os.getcwd()
RUN = _os.environ.get("FRC_RUN") or W
VS = ["v1", "v2", "v3", "v35"]
STATES = [("load", "load"), ("filter1", "F1"), ("filter2", "F2")]

logs = [r for r in json.load(io.open(os.path.join(RUN, "allstates_out.json"), encoding="utf-8")) if "v" in r]
by = {(r["v"], r["rk"], r["pk"]): r for r in logs}

bad = []

def norm_sig(sig):
    """Chu ky bo cuc sau khi TRU DI do dich chung cua ca canvas.

    Power BI co the ve lai ca canvas lech tron 1 pixel; khi do MOI visual deu
    lech +1 va phep so chuoi bao "bo cuc khac" trong khi hai anh giong het.
    Neo theo visual dau tien de chi con lai khac biet bo cuc that su.
    """
    if not sig:
        return sig
    rects = []
    for part in sig.split("|"):
        try:
            x, y, w_, h_ = [int(t) for t in part.split(",")]
        except ValueError:
            return sig
        rects.append((x, y, w_, h_))
    if not rects:
        return sig
    ox, oy = rects[0][0], rects[0][1]
    return "|".join("%d,%d,%d,%d" % (x - ox, y - oy, w_, h_) for x, y, w_, h_ in rects)


for (v, rk, pk), r in sorted(by.items()):
    if v == "v0":
        continue
    base = by.get(("v0", rk, pk))
    if not base:
        continue
    for st, key in STATES:
        a, b = base.get(key), r.get(key)
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        if a.get("sig") is None or b.get("sig") is None:
            continue
        if norm_sig(a["sig"]) != norm_sig(b["sig"]):
            bad.append({"rk": rk, "pk": pk, "state": st, "v": v,
                        "nvis_v0": a.get("nvis"), "nvis_v": b.get("nvis"),
                        "date_v0": a.get("dateRange"), "date_v": b.get("dateRange")})

io.open(os.path.join(RUN, "layout_mismatch.json"), "w", encoding="utf-8").write(
    json.dumps(bad, ensure_ascii=False, indent=1))

print("o lech bo cuc:", len(bad))
for x in bad[:40]:
    print("   %s %s %-8s %-4s  so visual v0=%s / %s=%s" %
          (x["rk"], x["pk"], x["state"], x["v"], x["nvis_v0"], x["v"], x["nvis_v"]))

# them: doi chieu MUC ZOOM giua cac version
#
# Buoc nay truoc day khong ton tai, va do la ly do 15 o artifact di qua het moi cong kiem.
# norm_sig() o tren chi tru duoc do DICH CHUNG cua canvas; zoom la phep TI LE nen w/h cung doi,
# anchor khong cancel duoc. Ket qua: v0=114% / v1=113% cho ra "bo cuc khac" + "khac giao dien"
# tren 15 o, trong khi tung con so tren trang y het nhau.
#
# capture.js gio ep 100% cho moi version. Neu ep that bai thi phai NOI RA o day, chu khong de
# lech zoom di tiep xuong diff.py roi hien ra thanh khac biet.
print("\n--- muc zoom ---")
zm = collections.defaultdict(dict)
for (v, rk, pk), r in by.items():
    for st, key in STATES:
        d = r.get(key)
        if isinstance(d, dict) and d.get("zoom"):
            zm[(rk, pk, st)][v] = d["zoom"]

def _zn(txt):
    digits = "".join(ch for ch in str(txt) if ch.isdigit())
    return int(digits) if digits else None

nz = 0
for k, vs in sorted(zm.items()):
    if len(set(vs.values())) > 1:
        nz += 1
        print("   LECH ZOOM", k, vs, " <- moi khac biet pixel tren o nay deu dang nghi la artifact")
print("so o lech zoom:", nz, "/", len(zm))

# Chi bao "ep zoom that bai" khi rec.zoomSet THAT SU noi la that bai.
#
# Ban dau doan nay dem moi luot chup khong o muc 100% roi goi la "ep zoom that bai". Sai:
# nhung o chup boi ban code cu co zoomSet='bo-qua' — chua he thu ep — van bi tinh la thai bai,
# nen bao cao ghi "36 luot ep zoom that bai" trong khi thuc te 12/12 o co ep deu thanh cong.
failed = sorted("%s|%s|%s=%s" % (r["v"], r["rk"], r["pk"], r.get("zoomSet"))
                for r in logs if str(r.get("zoomSet", "")).startswith("zoom100-failed"))
skipped = sum(1 for r in logs if r.get("zoomSet") == "bo-qua")
if failed:
    print("canh bao: %d o EP ZOOM THAT BAI: %s" % (len(failed), ", ".join(failed)))
if skipped:
    print("ghi chu: %d o chup boi ban code chua co buoc ep zoom (zoomSet=bo-qua) — "
          "khong phai that bai; chup lai bang --pick de dua ve 100%%." % skipped)

zoom_bad = [{"rk": k[0], "pk": k[1], "state": k[2], "zoom": vs}
            for k, vs in sorted(zm.items()) if len(set(vs.values())) > 1]
io.open(os.path.join(RUN, "zoom_mismatch.json"), "w", encoding="utf-8").write(
    json.dumps(zoom_bad, ensure_ascii=False, indent=1))

# them: doi chieu pham vi ngay giua cac version
print("\n--- pham vi ngay ---")
dr = collections.defaultdict(dict)
for (v, rk, pk), r in by.items():
    for st, key in STATES:
        d = r.get(key)
        if isinstance(d, dict) and d.get("dateRange"):
            dr[(rk, pk, st)][v] = d["dateRange"]
nd = 0
for k, vs in sorted(dr.items()):
    if len(set(vs.values())) > 1:
        nd += 1
        print("   LECH NGAY", k, vs)
print("so o lech ngay:", nd, "/", len(dr))
