# -*- coding: utf-8 -*-
"""Mot dong tinh trang CHAT LUONG (khong phai tien do).

Monitor cu chi dem so anh sinh ra, nen moi loi kieu "khoanh do nham",
"o thieu anh", "chup that bai" deu lot luoi. Script nay kiem dung nhung
chi so quyet dinh ket luan cuoi cung.
"""
import io, json, os, time, glob

D = os.environ.get("FRC_WORK") or os.getcwd()
RUN = os.environ.get("FRC_RUN") or D
def J(n, d):
    p = os.path.join(RUN, n)
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d

diff = J("diff_results.json", [])
st = {}
for r in diff:
    st[r.get("status")] = st.get(r.get("status"), 0) + 1
ui = sum(1 for r in diff if r.get("kind") == "UI")
val = sum(1 for r in diff if r.get("kind") == "VALUE")
unk = sum(1 for r in diff if r.get("kind") == "UNKNOWN")
zoom = sum(1 for r in diff if r.get("zoomArtifact"))

logs = [r for r in J("allstates_out.json", []) if "v" in r]
bad = sum(1 for r in logs if not r.get("ok"))
# Ten truong that trong log la apF1/apF2 (khong phai applyF1/applyF2). Doan kiem
# cu do nham ten nen luon bao 0 loi filter, che mat mot o filter khong an.
nofilter = sum(1 for r in logs for k in ("F1", "F2")
               if r.get("hasSlicer") and r.get("ap" + k) is False)
# Anh chup hai lan lien tiep khong trung nhau => trang con dang doi (v35 R4|P2
# vua khong on dinh vua doi muc zoom giua chung). Phai chup lai, khong duoc dung.
unstable = sum(1 for r in logs for k in ("load", "F1", "F2")
               if isinstance(r.get(k), dict) and r[k].get("stable") is False)

# O bao GIONG ma chu tren canvas lai KHAC => phan loai sai. Chu la tin hieu
# doc lap voi pixel, nen dung no de bat loi am tinh gia cua phep so pixel.
def _txt(st, v, rk, pk):
    f = os.path.join(RUN, "shots", "text", "%s__%s__%s__%s.txt" % (st, v, rk, pk))
    try:
        return io.open(f, encoding="utf-8").read()
    except Exception:
        return None

samebutdiff = 0
for r in diff:
    if r.get("status") != "SAME":
        continue
    if r.get("manual_verified"):
        # Da co nguoi/agent tu tay xac minh chu khac nhung KHONG phai regression
        # (xem manual_notes.json) — day la truong hop CO CHU DICH, khong phai
        # phep so pixel bao sai.
        continue
    a = _txt(r["state"], "v0", r["rk"], r["pk"])
    b = _txt(r["state"], r["v"], r["rk"], r["pk"])
    if a is not None and b is not None and a != b:
        samebutdiff += 1

html = os.environ.get("FRC_OUT") or os.path.join(RUN, "comparison_report.html")
age = int((time.time() - os.path.getmtime(html)) / 60) if os.path.exists(html) else -1
# Bao cao "cu" khong phai loi — mot ban da hoan tat thi cang de lau cang tot.
# Chi la van de khi DU LIEU moi hon BAO CAO, tuc la co thay doi chua duoc dung lai.
_srcs = [os.path.join(RUN, f) for f in ("diff_results.json", "allstates_out.json", "artifacts_log.json")]
_srcs += glob.glob(os.path.join(RUN, "shots", "*", "*.png"))
_newest = max((os.path.getmtime(f) for f in _srcs if os.path.exists(f)), default=0)
stale = int((_newest - os.path.getmtime(html)) / 60) if os.path.exists(html) and _newest > os.path.getmtime(html) else 0
npng = len(glob.glob(os.path.join(RUN, "shots", "*", "*.png")))

flags = []
if st.get("MISSING"):
    flags.append("THIEU=%d" % st["MISSING"])
if ui:
    flags.append("con-nhan-khac-giao-dien=%d" % ui)
if unk:
    flags.append("khong-phan-loai-duoc=%d" % unk)
if bad:
    flags.append("o-chup-loi=%d" % bad)
if nofilter:
    flags.append("filter-khong-an=%d" % nofilter)
if unstable:
    flags.append("anh-khong-on-dinh=%d" % unstable)
if samebutdiff:
    flags.append("bao-giong-nhung-chu-khac=%d" % samebutdiff)
if stale:
    flags.append("html-cu-hon-du-lieu-%dphut" % stale)

print("%s | anh=%d giong=%d khac-VALUE=%d zoom-artifact=%d html=%dph | %s" % (
    time.strftime("%H:%M"), npng, st.get("SAME", 0), val, zoom, age,
    ("CAN SUA: " + ", ".join(flags)) if flags else "SACH"))
