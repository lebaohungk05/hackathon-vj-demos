# -*- coding: utf-8 -*-
"""Diem vao duy nhat cho viec so sanh report Fabric giua cac ban semantic model.

Ba che do so sanh (deu doi chieu voi ban goc v0):
    python run.py --versions v1            # mot ban
    python run.py --versions v1,v3         # mot nhom ban
    python run.py --versions all           # tat ca cac ban co trong inventory

Cac buoc phu:
    python run.py --discover               # do slicer that cua tung page
    python run.py --pick "v3|R1|P2"        # chup lai dung vai o hong
    python run.py --confirm                # luot doi chung doc lap (shots2/)
    python run.py --report-only            # chi dung lai HTML tu anh da co

Doc README.md truoc khi chay lan dau.
"""
import argparse
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
CDP = "http://127.0.0.1:9222"

# Ma thoat: 0 = dat, 1 = co khac biet ve so lieu, 2 = chua ket luan duoc, 3 = loi
EXIT_PASS, EXIT_FAIL, EXIT_BLOCKED, EXIT_ERROR = 0, 1, 2, 3


def say(msg):
    print(msg, flush=True)


def die(msg, code=EXIT_ERROR):
    say("\n[DUNG] " + msg)
    sys.exit(code)


# ----------------------------------------------------------------- tien kiem
def preflight(work, inventory, filters, need_browser):
    """Kiem truoc moi thu, bao het mot the thay vi hong giua chung."""
    loi = []

    if not os.path.isdir(work):
        os.makedirs(work, exist_ok=True)

    if not os.path.exists(inventory):
        loi.append("Thieu inventory.json: %s\n"
                   "    -> copy config/inventory.example.json roi dien workspace + report id that."
                   % inventory)
    if not os.path.exists(filters):
        loi.append("Thieu filters.json: %s\n"
                   "    -> chay 'python run.py --discover' de do slicer, roi phan cong filter."
                   % filters)

    if shutil.which("node") is None:
        loi.append("Khong tim thay node trong PATH.")
    try:
        import numpy, scipy, PIL  # noqa: F401
    except ImportError as e:
        loi.append("Thieu thu vien Python: %s (can numpy, scipy, pillow)" % e.name)

    if need_browser:
        try:
            with urllib.request.urlopen(CDP + "/json/version", timeout=4) as r:
                json.load(r)
        except Exception:
            _chrome = r'"C:\Program Files\Google\Chrome\Application\chrome.exe"'
            _args = r' --remote-debugging-port=9222 --user-data-dir="C:\fabric-profile"'
            loi.append(
                "Khong ket noi duoc Chrome qua CDP tai %s.\n"
                "    -> Mo Chrome kem hai tham so nay, dang nhap Fabric, roi chay lai.\n"
                "       PowerShell (PHAI co dau & o dau, thieu la bao 'Unexpected token'):\n"
                "         & %s%s\n"
                "       cmd.exe (khong co dau &):\n"
                "         %s%s" % (CDP, _chrome, _args, _chrome, _args))

    if loi:
        say("\nChua chay duoc, can xu ly %d viec:" % len(loi))
        for i, x in enumerate(loi, 1):
            say("  %d. %s" % (i, x))
        sys.exit(EXIT_ERROR)


RUNS_SUBDIR = "runs"


def resolve_run_dir(work, run_name, needs_existing):
    """Thu muc KET QUA cua mot lan chay: <work>/runs/<timestamp hoac ten>/.

    Moi lan chay day du ghi ra MOT thu muc rieng, khong bao gio de len ket qua
    lan truoc — do la ly do thu muc nay ton tai. inventory.json/filters.json
    (cau hinh dung chung) van nam o <work>, khong o day.

    needs_existing=True cho --pick/--confirm/--report-only: cac che do nay LAM
    TIEP tren mot lan chay da co (gop anh chup lai, doi chung luot 2, dung lai
    HTML), nen phai tro vao dung thu muc cua lan do — khong duoc tu tao moi.
    Khong chi ro --run thi lay thu muc moi nhat duoi runs/.
    """
    runs_root = os.path.join(work, RUNS_SUBDIR)
    if run_name:
        d = os.path.join(runs_root, run_name)
        if needs_existing and not os.path.isdir(d):
            die("Khong thay thu muc lan chay '%s' duoi %s.\n"
                "    -> Kiem tra lai ten, hoac bo --run de tu lay lan chay moi nhat."
                % (run_name, runs_root))
        return d
    if needs_existing:
        os.makedirs(runs_root, exist_ok=True)
        existing = sorted(x for x in os.listdir(runs_root)
                          if os.path.isdir(os.path.join(runs_root, x)))
        if not existing:
            die("Chua co lan chay day du nao duoi %s de lam tiep.\n"
                "    -> Chay 'python run.py --versions ...' (khong co --pick/--confirm/"
                "--report-only) truoc, roi moi dung cac che do lam-tiep nay."
                % runs_root)
        return os.path.join(runs_root, existing[-1])
    ts = time.strftime("%Y%m%d-%H%M%S")
    d = os.path.join(runs_root, ts)
    n = 1
    while os.path.isdir(d):
        n += 1
        d = os.path.join(runs_root, "%s-%d" % (ts, n))
    os.makedirs(d, exist_ok=True)
    return d


def resolve_versions(inventory, spec):
    """Doi chuoi --versions thanh danh sach id, luon kem v0."""
    inv = json.load(io.open(inventory, encoding="utf-8"))
    have = [v["id"] for v in inv["versions"]]
    if spec in (None, "", "all"):
        chon = list(have)
    else:
        chon = [x.strip() for x in spec.split(",") if x.strip()]
        la = [x for x in chon if x not in have]
        if la:
            die("Khong co version %s trong inventory. Dang co: %s"
                % (", ".join(la), ", ".join(have)))
    if "v0" not in chon:
        chon.insert(0, "v0")   # moi phep so deu doi chieu voi ban goc
    return inv, chon


# ------------------------------------------------------------------- chay lenh
def run(cmd, env, what, cwd=None):
    say("\n>>> %s" % what)
    t0 = time.time()
    p = subprocess.run(cmd, env=env, cwd=cwd)
    dt = time.time() - t0
    if p.returncode != 0:
        if p.returncode == 4:
            die("Phien Fabric chua dang nhap. Dang nhap trong cua so Chrome dang mo roi chay lai.")
        die("%s that bai (ma thoat %d) sau %.0f giay." % (what, p.returncode, dt))
    say("    xong sau %.0f giay" % dt)


def node_script(script, out_json, cfg_path, env, what):
    e = dict(env)
    e["FRC_CONFIG"] = cfg_path
    run(["node", os.path.join(HERE, "driver.js"), os.path.join(HERE, script), out_json],
        e, what)


def py_script(script, env, what):
    run([sys.executable, os.path.join(HERE, script)], env, what)


# --------------------------------------------------------------- ket luan
def verdict(work, out_html):
    """Doc ket qua roi ra ket luan dat / khong dat / chua ket luan duoc."""
    try:
        rows = json.load(io.open(os.path.join(work, "diff_results.json"), encoding="utf-8"))
    except Exception:
        die("Khong doc duoc diff_results.json — buoc phan loai chua chay xong.")

    tong = len(rows)
    giong = sum(1 for r in rows if r.get("status") == "SAME")
    thieu = sum(1 for r in rows if r.get("status") == "MISSING")
    value = sum(1 for r in rows if r.get("kind") == "VALUE")
    ui = sum(1 for r in rows if r.get("kind") == "UI")
    unknown = sum(1 for r in rows if r.get("kind") == "UNKNOWN")

    logs = []
    try:
        logs = [r for r in json.load(io.open(os.path.join(work, "allstates_out.json"),
                                             encoding="utf-8")) if "v" in r]
    except Exception:
        pass
    chup_loi = sum(1 for r in logs if not r.get("ok"))
    filter_hong = sum(1 for r in logs for k in ("F1", "F2")
                      if r.get("hasSlicer") and r.get("ap" + k) is False)
    khong_on_dinh = sum(1 for r in logs for k in ("load", "F1", "F2")
                        if isinstance(r.get(k), dict) and r[k].get("stable") is False)

    say("\n" + "=" * 68)
    say("KET QUA")
    say("=" * 68)
    say("  phep so sanh        : %d" % tong)
    say("  giong het           : %d" % giong)
    say("  khac ve so lieu     : %d" % value)
    say("  khac ve giao dien   : %d" % ui)
    say("  chua phan loai duoc : %d" % unknown)
    say("  thieu anh           : %d" % thieu)
    say("  o chup loi          : %d" % chup_loi)
    say("  filter khong an     : %d" % filter_hong)
    say("  anh khong on dinh   : %d" % khong_on_dinh)
    say("  bao cao             : %s" % out_html)

    chan = thieu + chup_loi + filter_hong + khong_on_dinh + unknown
    if chan:
        say("\n[CHUA KET LUAN DUOC] Con %d o chua sach du lieu." % chan)
        say("  Nhung o nay chua du tin cay de ket luan. Chup lai chung roi chay lai:")
        say("    python run.py --pick \"<version>|<report>|<page>\"")
        say("  Xem chi tiet o muc 5 cua bao cao HTML.")
        return EXIT_BLOCKED

    if value:
        say("\n[KHONG DAT] Co %d o khac ve so lieu — report KHONG chay giong nhau." % value)
        say("  Mo muc 'Phat hien chinh' trong bao cao de xem page nao, ban nao, khac cho nao.")
        say("  Truoc khi bao cao ra ngoai, chay them luot doi chung:")
        say("    python run.py --confirm")
        return EXIT_FAIL

    say("\n[DAT] Khong co o nao khac ve so lieu. Report chay giong nhau qua moi phep so.")
    return EXIT_PASS


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="So sanh report Fabric giua ban goc v0 va cac ban toi uu.")
    ap.add_argument("--versions", default="all",
                    help='"v1" | "v1,v3" | "all" (mac dinh). v0 luon duoc them vao.')
    ap.add_argument("--reports", default="",
                    help="Chi chup mot so report, vi du R1,R3. Bo trong = tat ca.")
    ap.add_argument("--work", default=os.getcwd(),
                    help="Thu muc lam viec chua inventory.json va filters.json (cau hinh "
                         "dung chung, khong doi giua cac lan chay).")
    ap.add_argument("--run", default="",
                    help="Ten thu muc ket qua duoi <work>/runs/. Bo trong: lan chay day du "
                         "moi (khong --pick/--confirm/--report-only) tu tao ten theo "
                         "timestamp; cac che do lam-tiep lay lan chay MOI NHAT.")
    ap.add_argument("--out", default="",
                    help="Duong dan file HTML dau ra. Mac dinh <run>/comparison_report.html")
    ap.add_argument("--date-from", default="", help='Ep ngay bat dau, vi du "8/21/2026".')
    ap.add_argument("--date-to", default="", help='Ep ngay ket thuc, vi du "9/3/2026".')
    ap.add_argument("--pick", default="",
                    help='Chi chup lai vai o: "v3|R1|P2" hoac nhieu o cach nhau bang dau phay.')
    ap.add_argument("--discover", action="store_true",
                    help="Chi do slicer that cua tung page roi dung.")
    ap.add_argument("--confirm", action="store_true",
                    help="Luot doi chung doc lap, chup vao shots2/ roi so hai luot.")
    ap.add_argument("--report-only", action="store_true",
                    help="Bo qua chup, chi phan loai lai va dung HTML tu anh da co.")
    ap.add_argument("--refresh", default="no", choices=["no", "manual", "api"],
                    help='Refresh semantic model truoc khi chup. "no" (mac dinh) khong '
                         'refresh; "manual" dung lai de nguoi dung tu bam Refresh tren '
                         'Fabric; "api" goi Power BI REST API roi cho chay xong.')
    ap.add_argument("--skip-refresh-check", action="store_true",
                    help='Bo qua kiem tra moc refresh gan nhat giua cac ban truoc khi '
                         'chup. Mac dinh (khong dat co nay), voi --refresh no script tu '
                         'kiem tra ngay refresh gan nhat cua tung ban qua Power BI REST '
                         'API; neu lech ngay thi DUNG va yeu cau nguoi dung quyet dinh '
                         '(refresh lai, hoac chap nhan lech va them co nay de bo qua).')
    a = ap.parse_args()

    work = os.path.abspath(a.work)
    inventory = os.path.join(work, "inventory.json")
    filters = os.path.join(work, "filters.json")

    can_browser = not a.report_only
    preflight(work, inventory, filters if not a.discover else inventory, can_browser)

    # --pick / --confirm / --report-only LAM TIEP tren mot lan chay da co; moi
    # lan chay day du khac tu tao mot thu muc moi, khong bao gio de len ket qua
    # cu. --discover khong tao lan chay (chi do slicer, xem nhanh ben duoi).
    needs_existing = bool(a.pick or a.confirm or a.report_only)
    run_dir = None if a.discover else resolve_run_dir(work, a.run.strip() or None, needs_existing)
    out_html = os.path.abspath(a.out) if a.out else (
        os.path.join(run_dir, "comparison_report.html") if run_dir else "")

    env = dict(os.environ)
    env["FRC_WORK"] = work
    if run_dir:
        env["FRC_RUN"] = run_dir
    env["FRC_OUT"] = out_html

    # -------- chi do slicer
    if a.discover:
        cfg = os.path.join(work, "run_config.json")
        io.open(cfg, "w", encoding="utf-8").write(json.dumps(
            {"inventory": inventory, "out": os.path.join(work, "shots")}, ensure_ascii=False))
        node_script("discover.js", os.path.join(work, "slicers.json"), cfg, env,
                    "Do slicer that cua tung page")
        say("\nDa ghi %s." % os.path.join(work, "slicers.json"))
        say("Mo file do ra, chon cho moi page HAI slicer khac nhau, roi viet vao filters.json.")
        say("Quy tac: cung mot page thi ca 5 version phai dung y het slicer va gia tri.")
        return EXIT_PASS

    inv, versions = resolve_versions(inventory, a.versions)
    picks = [x.strip() for x in a.pick.split(",") if x.strip()]
    # Bao cho buoc phan loai va dung bao cao biet CHI xet nhung ban nay,
    # neu khong che do "mot ban" se bi bao thieu anh cho cac ban khong chup.
    env["FRC_VERSIONS"] = ",".join(v for v in versions if v != "v0")

    say("Thu muc lam viec : %s" % work)
    say("Thu muc ket qua  : %s%s" % (run_dir, "  (co san, lam tiep)" if needs_existing else "  (moi)"))
    say("Cac ban dem so   : %s" % ", ".join(versions))
    say("Report           : %s" % (a.reports or "tat ca"))
    if a.date_from and a.date_to:
        say("Ep khoang ngay   : %s -> %s" % (a.date_from, a.date_to))
    if picks:
        say("Chi chup lai     : %s" % ", ".join(picks))

    shots = os.path.join(run_dir, "shots2" if a.confirm else "shots")
    for sub in ("load", "filter1", "filter2", "text"):
        os.makedirs(os.path.join(shots, sub), exist_ok=True)

    cfg_path = os.path.join(run_dir, "run_config.json")
    io.open(cfg_path, "w", encoding="utf-8").write(json.dumps({
        "inventory": inventory,
        "filters": filters,
        "out": shots.replace("\\", "/"),
        "versions": versions,
        "reports": [x.strip() for x in a.reports.split(",") if x.strip()],
        "dateFrom": a.date_from or None,
        "dateTo": a.date_to or None,
        "pick": picks,
    }, ensure_ascii=False, indent=1))

    # -------- kiem tra moc refresh giua cac ban (truoc khi quyet dinh co refresh hay khong)
    #
    # "--refresh no" khong co nghia la an toan — no co nghia la NGUOI GOI TIN cac ban
    # dang cung moc. Nhieu lan nien tin do sai (mot ban vua refresh tay, ban kia thi
    # chua) va so sanh ra ket qua vo nghia ma khong ai biet. Tu kiem truoc, roi de
    # nguoi dung (qua Claude doc log nay) quyet dinh co refresh lai hay khong.
    if (not a.skip_refresh_check and a.refresh == "no"
            and not a.report_only and not a.confirm):
        import refresh as _rf
        aligned, info = _rf.check_refresh_alignment(inv, versions, say=say)
        if aligned is None:
            say("\n[ghi chu] Khong kiem duoc moc refresh gan nhat (thieu truong "
                "'dataset' trong inventory.json cho mot so ban, hoac khong lay duoc "
                "access token Power BI) — bo qua buoc kiem nay.")
        elif aligned is False:
            say("\n" + "=" * 68)
            say("MOC REFRESH CHUA KHOP GIUA CAC BAN")
            say("=" * 68)
            for vid in versions:
                say("  %-5s lan refresh THANH CONG gan nhat: %s" % (vid, info.get(vid) or "khong ro"))
            say("\nCac ban dang o nhung moc du lieu khac nhau -> moi khac biet tim duoc")
            say("se KHONG the ket luan la do model hay do du lieu lech nhau.")
            say("\nChon mot trong hai:")
            say("  - Refresh lai cho khop moc, roi chay lai lenh nay:")
            say("      python run.py --versions %s --refresh api" % a.versions)
            say("      (hoac --refresh manual de tu bam tren Fabric)")
            say("  - Van muon so sanh bat chap lech moc (khong khuyen nghi):")
            say("      python run.py --versions %s --skip-refresh-check" % a.versions)
            return EXIT_BLOCKED
        else:
            say("\nMoc refresh: cac ban da chon deu cung ngay (%s)." %
                (next(iter(info.values())) or "?"))

    # -------- refresh semantic model (neu duoc yeu cau)
    # Phai lam TRUOC khi chup: cac ban refresh lech thoi diem thi cua so du lieu
    # khac nhau, va moi khac biet tim duoc deu vo nghia.
    if a.refresh != "no" and not a.report_only:
        if a.refresh == "manual":
            say("\n" + "=" * 68)
            say("REFRESH THU CONG — lam theo cac buoc sau roi chay lai:")
            say("=" * 68)
            for v in versions:
                say("  - Mo semantic model cua ban %s tren Fabric, bam Refresh now" % v)
            say("\n  Doi TAT CA cac ban refresh xong (xem cot 'Refreshed' trong workspace),")
            say("  roi chay lai lenh nay bo di --refresh manual.")
            say("\n  Muon script tu lam viec nay thi dung --refresh api.")
            return EXIT_BLOCKED
        import refresh as _rf
        if not _rf.refresh_versions(inv, versions, say=say):
            die("Refresh khong hoan tat. Khong chup tiep vi cac ban co the dang o "
                "cac moc du lieu khac nhau — so sanh se vo nghia.", EXIT_BLOCKED)

    # -------- chup
    if not a.report_only:
        # Luot chup lai (--pick) PHAI ghi ra file rieng.
        #
        # Truoc day no ghi thang vao allstates_out.json, tuc la **de len log chinh**: mot lan
        # --pick hai o lam log tu 29 ban ghi con 3. Sau do merge_log() thoat ngay vi
        # fix_json == main_p, nen buoc gop ma SKILL.md hua ("log duoc gop nguoc vao log chinh,
        # nhung o khac giu nguyen") khong bao gio chay duoc. Anh chup van con tren dia, nhung
        # check_layout/quality_check/build_report deu doc log chinh -> muc 5 va so o lech bo cuc
        # bien mat, va bao cao tu 23 MB con 6.7 MB. Do la mat bang chung, khong phai mat hien thi.
        if a.confirm:
            out_json = os.path.join(run_dir, "pass2_out.json")
        elif picks:
            out_json = os.path.join(run_dir, "pick_out.json")
        else:
            out_json = os.path.join(run_dir, "allstates_out.json")
        n = len(versions) * (len(inv["reports"]) if not a.reports else len(a.reports.split(",")))
        say("\nSap chup. Khong dung chuot vao cua so Chrome trong luc chay —")
        say("con tro di lac vao visual se lam hien thanh cong cu va hong anh.")
        node_script("capture.js", out_json, cfg_path, env,
                    "Chup anh (%d lane, moi lane chay tuan tu cac report)" % n)

        if picks and not a.confirm:
            merge_log(run_dir, out_json)

    # -------- doi chung
    if a.confirm:
        py_script("confirm_pass2.py", env, "Doi chieu hai luot chup")
        say("\nQuy tac: chi khac biet lap o CA HAI luot moi tinh la that.")
        return EXIT_PASS

    # -------- phan loai va dung bao cao
    py_script("check_layout.py", env, "Doi chieu bo cuc va pham vi ngay")
    py_script("diff.py", env, "Phan loai khac biet")
    py_script("build_report.py", env, "Dung bao cao HTML")
    py_script("quality_check.py", env, "Tu kiem chat luong")

    return verdict(run_dir, out_html)


def merge_log(work, fix_json):
    """Gop log cua luot chup lai vao log chinh theo khoa (version, report, page)."""
    main_p = os.path.join(work, "allstates_out.json")
    if fix_json == main_p:
        # Khong con xay ra sau khi --pick ghi ra pick_out.json, nhung giu lai de neu ai doi
        # duong dan ve nhu cu thi bao to chu khong am tham de len log chinh.
        say("    CANH BAO: log chup lai trung duong dan voi log chinh, khong gop duoc.")
        return
    if not os.path.exists(main_p):
        # Khong co log chinh de gop vao: downstream se chi thay may o vua chup, con lai
        # bien mat. Noi ro chu khong de nguoi doc tuong ca bo da duoc kiem.
        say("    CANH BAO: chua co allstates_out.json de gop vao. Cac o khong nam trong "
            "--pick se khong co trong bao cao — chay lai ca bo truoc khi ket luan.")
        return
    main = json.load(io.open(main_p, encoding="utf-8"))
    fix = [r for r in json.load(io.open(fix_json, encoding="utf-8")) if "v" in r]
    key = lambda r: (r.get("v"), r.get("rk"), r.get("pk"))
    fx = {key(r): r for r in fix}
    seen = set()
    out = []
    for r in main:
        if "v" not in r:
            out.append(r)
            continue
        k = key(r)
        seen.add(k)
        out.append(fx.get(k, r))
    # O duoc chup lai ma log chinh chua tung co thi PHAI them vao, khong bo im lang.
    added = [r for k, r in fx.items() if k not in seen]
    out.extend(added)
    io.open(main_p, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
    say("    da gop %d ban ghi vao allstates_out.json (%d thay the, %d them moi, con %d ban ghi)"
        % (len(fix), len(fix) - len(added), len(added), len(out)))


if __name__ == "__main__":
    sys.exit(main())
