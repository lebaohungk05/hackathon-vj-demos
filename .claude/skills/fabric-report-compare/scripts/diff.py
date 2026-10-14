# -*- coding: utf-8 -*-
"""Pixel-diff v0 vs each optimized version, per state, and draw red boxes on the differing regions."""
import os, io, json, collections
from PIL import Image, ImageDraw
import numpy as np

import os as _os
W = _os.environ.get("FRC_WORK") or _os.getcwd()
RUN = _os.environ.get("FRC_RUN") or W
SHOTS  = os.path.join(RUN, "shots")
ANNOT  = os.path.join(SHOTS, "annot")
STATES = ["load", "filter1", "filter2"]
# VS duoc dat sau khi doc inventory (xem ben duoi)

CHAN_TOL   = 26      # per-channel abs difference that counts as "changed"
BLOCK      = 8       # mask downsample factor for clustering
MAX_BOXES  = 10      # nhieu hon thi khoanh 1 o bao tron
MIN_BLOCKS = 4       # ignore clusters smaller than this (anti-alias noise)
SAME_PCT   = 0.02    # <= this % of changed pixels is treated as identical

inv = json.load(io.open(os.path.join(W, "inventory.json"), encoding="utf-8"))

# Danh sach ban dem so: lay tu inventory, khong go cung.
# FRC_VERSIONS (neu co) gioi han lai theo dung lua chon cua nguoi chay, nho vay
# che do "mot ban" hay "mot nhom ban" khong bi bao thieu anh cho cac ban khong chup.
_sel = [x for x in (_os.environ.get("FRC_VERSIONS") or "").split(",") if x.strip()]
VS = [v["id"] for v in inv["versions"] if v["id"] != "v0"]
if _sel:
    VS = [v for v in VS if v in _sel]
fil = json.load(io.open(os.path.join(W, "filters.json"), encoding="utf-8"))

TEXT = os.path.join(SHOTS, "text")


def canvas_text(state, tag):
    """Chu hien tren canvas. None = khong co file."""
    p = os.path.join(TEXT, "%s__%s.txt" % (state, tag))
    if not os.path.exists(p):
        return None
    return io.open(p, encoding="utf-8").read().strip()


def load(state, tag):
    p = os.path.join(SHOTS, state, tag + ".png")
    if not os.path.exists(p):
        return None, p
    try:
        return Image.open(p).convert("RGB"), p      # co the dang ghi do -> bo qua
    except Exception:
        return None, p

from scipy import ndimage


def zoom_artifact(base, other, tol=CHAN_TOL):
    """Hai anh chi khac vi MUC ZOOM luc chup, khong khac noi dung.

    Power BI nho muc zoom rieng cho tung ban report, nen v0 co the hien 98%
    trong khi v3.5 hien 113%. Khi do moi pixel deu lech du chu/so y het nhau.
    Ta thu thu nho/phong ban kia ve mot loat ti le; neu co ti le nao lam so
    pixel lech giam manh thi day la artifact chup, khong phai khac biet.
    """
    w = min(base.width, other.width); h = min(base.height, other.height)
    a = np.asarray(base.crop((0, 0, w, h)), dtype=np.int16)
    b0 = np.asarray(other.crop((0, 0, w, h)), dtype=np.int16)
    ref = int((np.abs(a - b0).max(axis=2) > tol).sum())
    if ref == 0:
        return None
    best = (1.0, ref)
    for k in range(-20, 21):
        sc = 1.0 + k * 0.01
        if abs(sc - 1.0) < 0.02:
            continue
        nw, nh = max(8, int(round(other.width * sc))), max(8, int(round(other.height * sc)))
        im = other.resize((nw, nh), Image.BILINEAR)
        ww, hh = min(base.width, nw), min(base.height, nh)
        aa = np.asarray(base.crop((0, 0, ww, hh)), dtype=np.int16)
        bb = np.asarray(im.crop((0, 0, ww, hh)), dtype=np.int16)
        n = int((np.abs(aa - bb).max(axis=2) > tol).sum())
        n = int(n * (float(w * h) / float(ww * hh)))
        if n < best[1]:
            best = (sc, n)
    # Phong/thu anh lam nhoe net chu nen khong bao gio khop 100%; chi can
    # muc lech giam ro ret o mot ti le khac 1.0 la du ket luan la lech zoom.
    if abs(best[0] - 1.0) >= 0.05 and best[1] <= ref * 0.72:
        return {"scale": round(best[0], 3), "before": ref, "after": best[1]}
    return None


def robust_mask(a, b, tol=CHAN_TOL, r=1):
    """Mat na khac biet CHIU DUOC lech 1 pixel.

    Power BI ve lai canvas co the lech tron 1px giua hai lan chup; khi do phep
    tru thang bao het moi duong ke/chu la "khac", du hai anh giong het bang mat.
    Voi moi pixel ta lay do lech NHO NHAT so voi vung lan can 3x3 ben kia: lech
    do dich khung / khu rang cua bi triet tieu, con khac biet noi dung thuc su
    (mot con so doi, mot dong bien mat) van giu nguyen.
    """
    d = np.abs(a - b).max(axis=2)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            bs = np.roll(np.roll(b, dy, axis=0), dx, axis=1)
            d = np.minimum(d, np.abs(a - bs).max(axis=2))
    m = d > tol
    return ndimage.binary_opening(m, np.ones((2, 2), bool))


def content_box(img, pad=24):
    """Khung bao quanh phan CO NOI DUNG that su cua anh.

    Vai page (vi du 稼働玉利データ_s) chi ve trong mot goc nho cua khung rat lon,
    phan con lai la nen trang. Nhung nguyen ca khung roi thu ve 1500px thi noi
    dung chi con vai tram pixel -> nho va mo. Cat bo phan nen trang thua truoc.
    """
    a = np.asarray(img.convert("L"), dtype=np.uint8)
    # Nen ngoai canvas cua Fabric la xam 235 chu khong phai trang 255, nen lay
    # nguong 245 thi ca trang deu bi coi la "co noi dung" va khong cat duoc gi.
    ink = a < 230
    if not ink.any():
        return None
    ys, xs = np.where(ink)
    x0 = max(0, int(xs.min()) - pad); y0 = max(0, int(ys.min()) - pad)
    x1 = min(img.width, int(xs.max()) + pad); y1 = min(img.height, int(ys.max()) + pad)
    # khong cat neu chang tiet kiem duoc bao nhieu
    if (x1 - x0) * (y1 - y0) > 0.72 * img.width * img.height:
        return None
    return [x0, y0, x1, y1]


def clusters(mask, min_blocks=None):
    """Group changed-pixel blocks into bounding boxes (vectorised)."""
    from scipy import ndimage
    h, w = mask.shape
    bh, bw = h // BLOCK, w // BLOCK
    if bh == 0 or bw == 0:
        return []
    m = mask[:bh * BLOCK, :bw * BLOCK].reshape(bh, BLOCK, bw, BLOCK).any(axis=(1, 3))
    # Gop cac vung lech gan nhau lai: mot nguyen nhan duy nhat (vi du layout dich
    # ngang) sinh ra hang chuc manh roi rac -> khoanh 40 o do trong khi chi co 1 loi.
    m = ndimage.binary_dilation(m, structure=np.ones((5, 5), dtype=bool))
    lab, n = ndimage.label(m, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return []
    sizes = ndimage.sum_labels(m, lab, index=np.arange(1, n + 1))
    boxes = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        if sl is None or sizes[i] < (MIN_BLOCKS if min_blocks is None else min_blocks):
            continue
        ys, xs = sl
        boxes.append([xs.start * BLOCK, ys.start * BLOCK, xs.stop * BLOCK, ys.stop * BLOCK])
    boxes.sort(key=lambda b: -((b[2] - b[0]) * (b[3] - b[1])))
    # Qua nhieu o thi khoanh mot o bao tron thay vi rac do khap trang.
    if len(boxes) > MAX_BOXES:
        xs0 = min(b[0] for b in boxes); ys0 = min(b[1] for b in boxes)
        xs1 = max(b[2] for b in boxes); ys1 = max(b[3] for b in boxes)
        return [[xs0, ys0, xs1, ys1]]
    return boxes

def union(boxes, w, h, pad=45, minw=900, minh=520):
    x0 = max(0, min(b[0] for b in boxes) - pad)
    y0 = max(0, min(b[1] for b in boxes) - pad)
    x1 = min(w, max(b[2] for b in boxes) + pad)
    y1 = min(h, max(b[3] for b in boxes) + pad)
    # Vung lech co the chi rong vai chuc pixel (mot o so bi trong). Cat sat qua
    # thi phong to len se vo net va nguoi doc cung khong biet dang nhin cho nao
    # trong trang. No rong ra mot khung du de thay ngu canh xung quanh.
    if x1 - x0 < minw:
        cx = (x0 + x1) // 2
        x0 = max(0, cx - minw // 2); x1 = min(w, x0 + minw); x0 = max(0, x1 - minw)
    if y1 - y0 < minh:
        cy = (y0 + y1) // 2
        y0 = max(0, cy - minh // 2); y1 = min(h, y0 + minh); y0 = max(0, y1 - minh)
    return [x0, y0, x1, y1]

def annotate(img, boxes, out, crop=None):
    im = img.copy()
    d = ImageDraw.Draw(im)
    lw = max(3, im.width // 500)
    for (x0, y0, x1, y1) in boxes:
        pad = lw * 2
        d.rectangle([max(0, x0-pad), max(0, y0-pad),
                     min(im.width-1, x1+pad), min(im.height-1, y1+pad)],
                    outline=(255, 0, 0), width=lw)
    if crop:
        im = im.crop(tuple(crop))
        # Vung lech cat ra thuong chi rong vai tram pixel; de nguyen thi chu nho
        # li ti khong doc noi. Phong to bang LANCZOS (toi da 3 lan) cho de nhin.
        if im.width and im.width < 1800:
            k = min(3.0, 1800.0 / im.width)
            if k > 1.05:
                im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out, optimize=True)

results = []
SCOPE = [R["key"] for R in inv["reports"]
         if any(os.path.exists(os.path.join(SHOTS, "load", "v0__%s__%s.png" % (R["key"], PG["k"])))
                for PG in R["pages"])]
print("scope:", SCOPE)

for R in inv["reports"]:
    if R["key"] not in SCOPE:
        continue
    for PG in R["pages"]:
        key = R["key"] + "|" + PG["k"]
        for state in STATES:
            no_slicer = (state != "load" and not fil.get(key))
            base, bpath = load(state, "v0__%s__%s" % (R["key"], PG["k"]))
            for v in VS:
                tag = "%s__%s__%s" % (v, R["key"], PG["k"])
                rec = {"rk": R["key"], "rn": R["name"], "pk": PG["k"], "pn": PG["nm"],
                       "state": state, "v": v, "noSlicer": bool(no_slicer)}
                other, opath = load(state, tag)
                if base is None or other is None:
                    rec["status"] = "MISSING"
                    rec["miss"] = ("v0" if base is None else "") + ("," + v if other is None else "")
                    results.append(rec); continue
                if base.size != other.size:
                    rec["sizeMismatch"] = "%dx%d vs %dx%d" % (base.size + other.size)
                w = min(base.width, other.width); h = min(base.height, other.height)
                a = np.asarray(base.crop((0, 0, w, h)), dtype=np.int16)
                b = np.asarray(other.crop((0, 0, w, h)), dtype=np.int16)
                mask = robust_mask(a, b)
                pct = 100.0 * mask.sum() / mask.size
                rec["pct"] = round(pct, 4)
                # CHU TRUOC, PIXEL SAU. Neu chu tren canvas khac nhau thi day la
                # khac biet ve so lieu, du chi lech vai chuc pixel. Truoc day
                # nguong pixel duoc xet TRUOC nen mot page ve rat nho (R5|P1) da
                # giau mat 8 o that su thieu so lieu.
                t0 = canvas_text(state, "v0__%s__%s" % (R["key"], PG["k"]))
                tv = canvas_text(state, tag)
                text_differs = (t0 is not None and tv is not None and t0 != tv)
                if pct <= SAME_PCT and not text_differs and "sizeMismatch" not in rec:
                    rec["status"] = "SAME"
                else:
                    rec["status"] = "DIFF"
                    if t0 is None or tv is None:
                        rec["kind"] = "UNKNOWN"      # khong co text de doi chieu
                    elif t0 != tv:
                        rec["kind"] = "VALUE"        # chu tren canvas khac nhau
                    else:
                        rec["kind"] = "UI"           # chu y het, chi pixel khac
                        za = zoom_artifact(base, other)
                        if za:
                            # Cung noi dung, chi khac muc zoom luc chup ->
                            # loi chup, khong phai khac biet giua hai ban.
                            rec["status"] = "SAME"
                            rec["zoomArtifact"] = za
                            rec.pop("kind", None)
                            rec["desc"] = ("Nội dung giống nhau, chỉ khác mức zoom lúc chụp "
                                           "(khớp lại ở tỉ lệ %.0f%%: %d pixel lệch còn %d) — "
                                           "tính là giống, sẽ chụp lại ô này." %
                                           (za["scale"] * 100, za["before"], za["after"]))
                            results.append(rec); continue
                    bx = clusters(mask)
                    if not bx:
                        # Khac biet rat nho (mot o so bi trong) van phai duoc khoanh,
                        # neu khong nguoi doc khong biet nhin vao dau.
                        bx = clusters(mask, min_blocks=1)
                    if not bx:
                        # Phep so "chiu dich 1px" co the xoa gan het mot con so nho
                        # (o cho chu li ti, so ben canh cung khop duoc khi dich).
                        # O da xac dinh la KHAC thi phai chi duoc cho khac -> dung
                        # phep tru THO de dinh vi.
                        raw = (np.abs(a - b).max(axis=2) > CHAN_TOL)
                        bx = clusters(raw, min_blocks=1)
                        if not bx and raw.any():
                            ys_, xs_ = np.where(raw)
                            bx = [[int(xs_.min()), int(ys_.min()),
                                   int(xs_.max()) + 1, int(ys_.max()) + 1]]
                    rec["boxes"] = len(bx)
                    # Mo ta cu the LECH CAI GI, thay vi chi khoanh do. Nguoi doc
                    # phai biet do la duong vien 1px hay la so lieu doi.
                    from scipy import ndimage as _nd
                    lab2, n2 = _nd.label(_nd.binary_dilation(mask, np.ones((3, 3), bool)))
                    dims = []
                    for sl2 in _nd.find_objects(lab2):
                        if sl2 is None:
                            continue
                        ys2, xs2 = sl2
                        dims.append((xs2.stop - xs2.start, ys2.stop - ys2.start))
                    thin = [d for d in dims if min(d) <= 4]
                    npx = int(mask.sum())
                    biggest = max(dims, key=lambda d: d[0] * d[1]) if dims else (0, 0)
                    rec["px"] = npx
                    rec["maxDelta"] = int(np.abs(a - b).max())
                    rec["regions"] = len(dims)
                    rec["biggest"] = "%dx%d" % biggest
                    rec["allThin"] = bool(dims) and len(thin) == len(dims)
                    if rec.get("kind") == "VALUE":
                        rec["desc"] = "Chữ/số hiển thị khác nhau — xem bảng đối chiếu chữ bên dưới."
                    elif (rec["allThin"] and npx < 3000) or (npx < 2000 and biggest[0] * biggest[1] < 4000):
                        # Lech duoi nguong nhin thay duoc (chi la duong manh 1-4px:
                        # vien, thanh cuon, thanh tieu de) -> XEP LA GIONG, khong
                        # tinh la khac biet. Chi giu lai mot ghi chu ky thuat.
                        rec["status"] = "SAME"
                        rec["subpixel"] = True
                        rec.pop("kind", None)
                        rec["desc"] = ("Lệch dưới ngưỡng nhìn thấy được (%d pixel trên %d, "
                                       "vùng lớn nhất %dx%d) — tính là giống." %
                                       (npx, mask.size, biggest[0], biggest[1]))
                    else:
                        rec["desc"] = ("Lệch %d pixel trên %d, %d vùng rời rạc, vùng lớn nhất %dx%d, "
                                       "lệch màu tối đa %d/255." %
                                       (npx, mask.size, len(dims), biggest[0], biggest[1], rec["maxDelta"]))
                    if bx:
                        cb = union(bx, w, h)
                        rec["crop"] = cb
                        bimg = base.crop((0, 0, w, h))
                        oimg = other.crop((0, 0, w, h))
                        # ban day du, khoanh do dung cho lech
                        fc = content_box(bimg)
                        annotate(bimg, bx, os.path.join(ANNOT, state, "full__%s__%s__%s__v0.png" % (R["key"], PG["k"], v)), fc)
                        annotate(oimg, bx, os.path.join(ANNOT, state, "full__%s__%s__%s__%s.png" % (R["key"], PG["k"], v, v)), fc)
                        # ban phong to dung vao vung lech, de nguoi doc thay ro khac cho nao
                        annotate(bimg, bx, os.path.join(ANNOT, state, "zoom__%s__%s__%s__v0.png" % (R["key"], PG["k"], v)), cb)
                        annotate(oimg, bx, os.path.join(ANNOT, state, "zoom__%s__%s__%s__%s.png" % (R["key"], PG["k"], v, v)), cb)
                results.append(rec)

# Voi o khac VALUE, ghi lai vai doan chu khac nhau de bao cao chi dich danh.
import difflib
for rec in results:
    if rec.get("kind") != "VALUE":
        continue
    t0 = canvas_text(rec["state"], "v0__%s__%s" % (rec["rk"], rec["pk"]))
    tv = canvas_text(rec["state"], "%s__%s__%s" % (rec["v"], rec["rk"], rec["pk"]))
    a, b = (t0 or "").split(" "), (tv or "").split(" ")
    ch = []
    for tag_, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag_ == "equal":
            continue
        ch.append({"v0": " ".join(a[i1:i2])[:120], "vx": " ".join(b[j1:j2])[:120]})
        if len(ch) >= 12:
            break
    rec["textDiff"] = ch

io.open(os.path.join(RUN, "diff_results.json"), "w", encoding="utf-8").write(
    json.dumps(results, ensure_ascii=False, indent=1))

cnt = collections.Counter(r["status"] for r in results)
print("kind:", dict(collections.Counter(r.get("kind") for r in results if r.get("kind"))))
print("comparisons:", len(results))
for k, v in sorted(cnt.items()):
    print("  %-10s %d" % (k, v))
