# -*- coding: utf-8 -*-
"""Refresh semantic model truoc khi chup.

Vi sao can: neu cac ban model duoc refresh o nhung thoi diem khac nhau thi cua so
du lieu cua chung lech nhau, va moi khac biet tim duoc deu VO NGHIA — khong biet
la do model tinh khac hay do du lieu khac. Da tung mat mot dem vi chuyen nay.

Ba lua chon:
    no      khong refresh (mac dinh) — dung khi vua refresh xong hoac chac chan
            cac ban dang o cung mot moc du lieu
    manual  nguoi dung tu bam Refresh tren Fabric roi chay lai
    api     goi Power BI REST API de refresh, cho chay xong roi moi chup

Che do api can mot access token cho Power BI. Neu lay khong duoc thi script noi
ro cach lay chu khong am tham bo qua buoc refresh.
"""
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request

PBI_RESOURCE = "https://analysis.windows.net/powerbi/api"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"


def get_token():
    """Lay access token Power BI qua az CLI. Tra ve None neu khong lay duoc.

    Tren Windows, 'az' la mot file .cmd (batch script), khong phai .exe. Goi
    subprocess.run(["az", ...]) THANG khong qua shell se nem FileNotFoundError
    ngay lap tuc (CreateProcess khong tu resolve .cmd nhu cmd.exe van lam) —
    truoc day loi nay bi 'except Exception: return None' nuot mat, nen ham nay
    LUON tra ve None tren Windows du da 'az login' that su, va moi noi dung
    kiem tra refresh (check_refresh_alignment, refresh_versions --refresh api)
    lang le bao 'khong lay duoc token' thay vi chay that. shutil.which() resolve
    dung duong dan that (vi du az.cmd) truoc khi goi, hoat dong ca hai OS.
    """
    az = shutil.which("az")
    if not az:
        return None
    try:
        p = subprocess.run(
            [az, "account", "get-access-token", "--resource", PBI_RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    tok = (p.stdout or "").strip()
    return tok or None


def _call(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read().decode("utf-8", "replace")
        return r.status, (json.loads(raw) if raw.strip() else {})


def start_refresh(ws, dataset, token):
    """Bam refresh. Tra ve (thanh_cong, thong_diep)."""
    url = "%s/groups/%s/datasets/%s/refreshes" % (PBI_BASE, ws, dataset)
    try:
        status, _ = _call("POST", url, token, {"notifyOption": "NoNotification"})
        return True, "da bam refresh (HTTP %d)" % status
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code == 409:
            return True, "dang co mot lan refresh chay do — se cho lan do xong"
        return False, "HTTP %d: %s" % (e.code, detail)
    except Exception as e:
        return False, str(e)[:200]


def last_status(ws, dataset, token):
    """Trang thai lan refresh gan nhat: Completed / Failed / Unknown (dang chay)."""
    url = "%s/groups/%s/datasets/%s/refreshes?$top=1" % (PBI_BASE, ws, dataset)
    try:
        _, body = _call("GET", url, token)
        items = body.get("value") or []
        if not items:
            return "NoHistory", ""
        it = items[0]
        return it.get("status", "?"), it.get("serviceExceptionJson", "") or ""
    except Exception as e:
        return "Error", str(e)[:200]


def wait_done(ws, dataset, token, timeout_s=1800, poll_s=20, say=print):
    """Cho toi khi refresh xong. Tra ve (xong_tot, thong_diep)."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st, err = last_status(ws, dataset, token)
        if st == "Completed":
            return True, "xong sau %.0f giay" % (time.time() - t0)
        if st == "Failed":
            return False, "refresh THAT BAI: " + (err or "khong ro ly do")
        if st in ("Error",):
            return False, err
        time.sleep(poll_s)
    return False, "qua %d giay van chua xong" % timeout_s


def get_last_refresh_date(ws, dataset, token):
    """Ngay (YYYY-MM-DD) cua lan refresh THANH CONG gan nhat, hoac None neu khong ro."""
    url = "%s/groups/%s/datasets/%s/refreshes?$top=5" % (PBI_BASE, ws, dataset)
    try:
        _, body = _call("GET", url, token)
        items = body.get("value") or []
        for it in items:
            if it.get("status") == "Completed" and it.get("endTime"):
                return it["endTime"][:10]
        return None
    except Exception:
        return None


def check_refresh_alignment(inv, version_ids, say=print):
    """So sanh moc refresh gan nhat giua cac ban se duoc dem so.

    Tra ve (aligned, info):
      True  -> tat ca cung mot ngay refresh gan nhat, an toan so sanh
      False -> lech ngay giua it nhat hai ban -> phai hoi nguoi dung truoc khi so
      None  -> khong kiem duoc (thieu 'dataset' trong inventory, hoac khong lay
               duoc token Power BI) -> bo qua kiem tra, chi canh bao
      info  -> {version_id: "YYYY-MM-DD" hoac None}
    """
    targets = []
    for v in inv["versions"]:
        if v["id"] not in version_ids:
            continue
        ds = v.get("dataset")
        if not ds:
            return None, {}
        targets.append((v["id"], v["ws"], ds))
    if not targets:
        return None, {}

    token = get_token()
    if not token:
        return None, {}

    info = {}
    for vid, ws, ds in targets:
        info[vid] = get_last_refresh_date(ws, ds, token)

    if any(d is None for d in info.values()):
        return None, info
    if len(set(info.values())) <= 1:
        return True, info
    return False, info


def refresh_versions(inv, version_ids, say=print):
    """Refresh cac ban duoc chon. Tra ve True neu tat ca deu xong tot."""
    targets = []
    for v in inv["versions"]:
        if v["id"] not in version_ids:
            continue
        ds = v.get("dataset")
        if not ds:
            say("  %-5s THIEU truong 'dataset' trong inventory.json — bo qua." % v["id"])
            continue
        targets.append((v["id"], v["ws"], ds))

    if not targets:
        say("\nKhong co ban nao khai bao 'dataset' trong inventory.json.")
        say("Them GUID cua semantic model vao tung muc trong 'versions', vi du:")
        say('    {"id": "v1", "ws": "<workspace-guid>", "dataset": "<semantic-model-guid>"}')
        say("GUID lay tu URL khi mo semantic model tren Fabric.")
        return False

    token = get_token()
    if not token:
        say("\nKhong lay duoc access token cho Power BI.")
        say("Chay lenh nay roi thu lai (se hien man hinh dang nhap MFA):")
        say('    az login --scope "%s/.default"' % PBI_RESOURCE)
        say("Hoac chon refresh thu cong: bo --refresh api, tu bam Refresh tren Fabric.")
        return False

    say("\nBam refresh %d ban..." % len(targets))
    started = []
    for vid, ws, ds in targets:
        ok, msg = start_refresh(ws, ds, token)
        say("  %-5s %s" % (vid, msg))
        if ok:
            started.append((vid, ws, ds))
    if not started:
        return False

    say("\nCho refresh chay xong (toi da 30 phut moi ban)...")
    all_ok = True
    for vid, ws, ds in started:
        ok, msg = wait_done(ws, ds, token, say=say)
        say("  %-5s %s" % (vid, msg))
        all_ok = all_ok and ok
    return all_ok
