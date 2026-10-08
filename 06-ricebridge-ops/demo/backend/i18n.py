import datetime as dt
import hashlib
import json
import re

LANGS = ("en", "ja", "vi")
VI_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)
CJK_CHARS = re.compile(r"[぀-ヿ㐀-鿿＀-￯]")
QUOTED = re.compile(r"“[^”]*”|「[^」]*」|\"[^\"]*\"|(?:(?<=^)|(?<=[\s(]))'[^']+'(?=$|[\s.,;:)!?])")
EN_DATE = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\d{2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = {"en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"), "ja": "月火水木金土日", "vi": ("T2", "T3", "T4", "T5", "T6", "T7", "CN")}

T = {
    "err.stale_plan": ("The plan changed. Review the current plan before deciding.", "計画が更新されました。現在の計画を確認してください。", "Lịch đã thay đổi. Hãy xem lịch mới trước khi duyệt."),
    "basis.wb": ("water balance only", "水収支のみ", "chỉ theo cân bằng nước"),
    "basis.src": ("{source} {day}", "{source}（{day}）", "{source} {day}"),
    "src.sensor": ("sensor", "センサー", "cảm biến"),
    "src.photo": ("gauge photo", "観測管の写真", "ảnh ống đo"),
    "src.second_gauge": ("second-gauge reading", "2本目の観測管", "số đo ống thứ hai"),
    "src.htx_voice": ("HTX report", "HTXの報告", "báo cáo của HTX"),
    "src.htx_check": ("HTX field check", "HTXの圃場確認", "HTX kiểm tra ruộng"),
    "src.htx_record": ("HTX pump log", "HTXの送水記録", "sổ bơm của HTX"),
    "src.farmer_text": ("farmer chat report", "農家のチャット報告", "tin nhắn của nông dân"),
    "src.photo_rejected": ("gauge photo (rejected)", "観測管の写真（却下）", "ảnh ống đo (bị loại)"),
    "src.photo_suspicious": ("gauge photo (suspicious)", "観測管の写真（疑義あり）", "ảnh ống đo (nghi sai)"),
    "src.rain": ("rain forecast {mm} mm (Open-Meteo)", "降雨予報 {mm} mm（Open-Meteo）", "dự báo mưa {mm} mm (Open-Meteo)"),
    "src.wb": ("water balance", "水収支", "cân bằng nước"),

    "stage.establishment": ("Establishment", "苗立ち期", "Lúa mạ"),
    "stage.topdress": ("Top-dressing window", "追肥期", "Bón thúc"),
    "stage.heading": ("Flowering", "出穂期", "Trổ bông"),
    "stage.awd": ("AWD drying allowed", "落水可（AWD）", "Phơi ruộng"),
    "stage.drain": ("Pre-harvest drain", "収穫前の落水", "Rút nước trước gặt"),
    "stage.off": ("Off season", "作付け期間外", "Ngoài vụ"),
    "stagelow.establishment": ("establishment", "苗立ち期", "lúa mạ"),
    "stagelow.topdress": ("top-dressing window", "追肥期", "bón thúc"),

    "action.irrigate": ("Open inlet", "取水口を開く", "Mở cống"),
    "action.hold_rain": ("Hold: rain will refill", "保留：降雨で回復見込み", "Chờ mưa"),
    "action.keep_water": ("Wait: next run", "待機：次回送水まで", "Chờ đợt sau"),
    "action.deferred": ("Deferred: pump full", "延期：送水枠が満杯", "Dời lượt sau"),

    "why.flower_start": ("starts flowering without standing water", "湛水のないまま出穂期に入る", "bắt đầu trổ bông khi ruộng không còn nước"),
    "why.flower_lose": ("flowering field loses its standing water", "出穂期の区画で湛水がなくなる", "ruộng đang trổ bông bị cạn nước"),
    "why.stage_start": ("{stage} starts without standing water", "湛水のないまま{stage}に入る", "vào giai đoạn {stage} khi ruộng không còn nước"),
    "why.stage_need": ("{stage} needs standing water", "{stage}は湛水が必要", "giai đoạn {stage} cần giữ nước trên ruộng"),
    "why.awd": ("near the −15 cm AWD limit", "AWDの下限 −15 cm に近い", "gần ngưỡng AWD −15 cm"),

    "reason.need": ("{day}: {why} (projected {cm}).", "{day}：{why}（予測 {cm}）。", "{day}: {why} (dự báo {cm})."),
    "reason.fast": ("Fast-draining soil ({rate} mm/day): standing water gone by {day}, before the run.",
                    "水の抜けやすい土壌（{rate} mm/日）：送水前の{day}までに湛水がなくなる。",
                    "Đất rút nước nhanh ({rate} mm/ngày): ruộng hết nước trước {day}, trước lượt bơm."),
    "reason.hold": ("Today's {mm} mm (Open-Meteo) lifts it from {a} to about {b} by tomorrow; no pumping needed.",
                    "本日の雨 {mm} mm（Open-Meteo）で、明日までに {a} から約 {b} まで上がる。送水は不要。",
                    "Mưa hôm nay {mm} mm (Open-Meteo) nâng mực nước từ {a} lên khoảng {b} vào ngày mai; không cần bơm."),
    "reason.keep_reflooded": ("Re-flooded: lowest projected {cm} before {day}; can wait for the next run.",
                              "再び湛水：{day}までの予測最低水位は {cm}。次回の送水まで待てる。",
                              "Ruộng có nước lại: mực thấp nhất dự báo {cm} trước {day}; chờ được đợt bơm sau."),
    "reason.keep_enough": ("Enough water: lowest projected {cm} before {day}; can wait for the next run.",
                           "水は十分：{day}までの予測最低水位は {cm}。次回の送水まで待てる。",
                           "Đủ nước: mực thấp nhất dự báo {cm} trước {day}; chờ được đợt bơm sau."),
    "reason.deferred": ("Pump full ({n} fields/run); next slot {day}.", "送水枠が満杯（1回{n}区画まで）。次の枠は{day}。",
                        "Trạm bơm đã đủ lượt ({n} thửa/lượt); lượt kế tiếp {day}."),
    "reason.measure": ("Last reading is {age} days old: ask HTX to measure before opening the inlet.",
                       "最新の測定は{age}日前：取水口を開ける前にHTXへ測定を依頼。",
                       "Số đo gần nhất đã cũ {age} ngày: nhờ HTX đo trước khi mở cống."),

    "summary.run": ("Pump run {day}: open {list}; other fields wait for the next run.",
                    "{day}の送水：{list}の順に取水口を開ける。他の区画は次回まで待機。",
                    "Lượt bơm {day}: mở cống {list}; các thửa khác chờ đợt sau."),
    "summary.pause": ("Pause the {day} pump run: no field needs water before {next}.",
                      "{day}の送水を一時停止：{next}までに水が必要な区画はない。",
                      "Tạm hoãn lượt bơm {day}: chưa thửa nào cần nước trước {next}."),
    "list.then": (", then ", "→", ", rồi "),

    "alert.text": ("{fid} {why} on {day} ({cm}), before the {run} run.", "{fid}：{day}に{why}（{cm}）。{run}の送水より前。",
                   "{fid} {why} vào {day} ({cm}), trước lượt bơm {run}."),
    "alert.tech": ("Notify the technical officer.", "技術職員に連絡。", "Báo cán bộ kỹ thuật."),
    "alert.slot": ("Ask the pump station for an earlier slot.", "ポンプ場に早い枠を依頼。", "Xin trạm bơm cho lượt sớm hơn."),

    "title.start": ("Plan before the rain", "降雨前の計画", "Lịch trước cơn mưa"),
    "title.rain": ("Re-plan after the rain", "降雨後の再計画", "Lập lại lịch sau mưa"),
    "title.photo": ("Re-plan with the photo held", "写真を保留して再計画", "Lập lại lịch, tạm giữ ảnh"),
    "title.remeasure": ("Re-plan after the second-gauge reading", "2本目の観測管の測定後に再計画", "Lập lại lịch sau số đo ống thứ hai"),
    "title.voice": ("Re-plan with the HTX report", "HTXの報告で再計画", "Lập lại lịch theo báo cáo của HTX"),
    "title.pump": ("Re-plan after the pump moved", "送水日の変更後に再計画", "Lập lại lịch sau khi dời lượt bơm"),
    "title.message": ("Re-plan after a message from {who}", "{who}のメッセージ後に再計画", "Lập lại lịch sau tin nhắn của {who}"),
    "title.whatif": ("What-if: {label}", "What-if：{label}", "Giả định: {label}"),

    "tr.sched": ("{n} fields per run, ordered by crop-stage risk date, priority, lowest level → {summary}",
                 "1回{n}区画。生育段階のリスク日・優先度・最低水位の順 → {summary}",
                 "{n} thửa/lượt, xếp theo ngày rủi ro của giai đoạn, mức ưu tiên, mực nước thấp nhất → {summary}"),
    "tr.gate": ("{id} status = proposed; only the pump-station manager can approve. The LLM has no approve tool.",
                "{id}は承認待ち。承認できるのはポンプ場責任者だけで、LLMには承認ツールがない。",
                "{id} đang chờ duyệt; chỉ người phụ trách trạm bơm được duyệt. LLM không có công cụ duyệt."),
    "tr.advance": ("advanced {n} days with Open-Meteo rain + ET0, Kc by stage, percolation and seepage per field",
                   "{n}日分を計算：Open-Meteoの雨とET0、生育段階別のKc、区画ごとの浸透と漏水",
                   "tính thêm {n} ngày với mưa và ET0 từ Open-Meteo, Kc theo giai đoạn, thấm và rò rỉ từng thửa"),
    "tr.cropstage": ("stage per field from sowing date; flowering and top-dressing need standing water; AWD limit −15 cm",
                     "播種日から区画ごとの生育段階を算出。出穂期と追肥期は湛水が必要。AWDの下限は −15 cm",
                     "giai đoạn từng thửa tính từ ngày sạ; trổ bông và bón thúc cần giữ nước; ngưỡng AWD −15 cm"),
    "tr.rainlift": ("F2 {a} → {b}: 1 cm rain lifts the water table {x} cm", "F2 {a} → {b}：雨1 cmで地下水位が{x} cm上がる",
                    "F2 {a} → {b}: 1 cm mưa nâng mực nước ngầm {x} cm"),
    "tr.indep": ("pick {pick} · fallback {fallback}; rejected: {rejected}", "依頼先：{pick} · 代替：{fallback}。除外：{rejected}",
                 "chọn {pick} · dự phòng {fallback}; loại: {rejected}"),
    "tr.none": ("none", "なし", "không có"),
    "tr.noflags": ("no flags", "フラグなし", "không có cảnh báo"),
    "tr.photocheck": ("{codes} → photo usable: {usable}", "{codes} → 写真の使用：{usable}", "{codes} → dùng được ảnh: {usable}"),
    "tr.yes": ("yes", "可", "có"),
    "tr.no": ("no", "不可", "không"),
    "tr.scripted": ("scripted reading {cm} ({reason})", "シナリオ上の読み取り値 {cm}（{reason}）", "số đọc theo kịch bản {cm} ({reason})"),
    "tr.conflict_photo": ("photo {a} vs sensor {b}: gap {g} cm > {t} cm → photo held as suspicious",
                          "写真 {a} とセンサー {b}：差 {g} cm > {t} cm → 写真を疑義ありとして保留",
                          "ảnh {a} so với cảm biến {b}: lệch {g} cm > {t} cm → tạm giữ ảnh vì nghi sai"),
    "tr.evlog": ("#{new} accepted; #{old} marked {status} with its reason, never deleted (hash-chained)",
                 "#{new}を採用。#{old}は理由付きで「{status}」とし、削除しない（ハッシュチェーン）",
                 "#{new} được chấp nhận; #{old} đánh dấu {status} kèm lý do, không bao giờ xóa (chuỗi hash)"),
    "tr.guard": ("matched {hits} → message treated as data, never as a command",
                 "{hits} に一致 → メッセージはデータとして扱い、命令としては実行しない",
                 "khớp {hits} → tin nhắn chỉ được coi là dữ liệu, không bao giờ là lệnh"),
    "tr.indep_resolve": ("{fid} {cm} from an independent gauge resolves the open conflict",
                         "独立した観測管の {fid} {cm} で未解決の矛盾を解消",
                         "{fid} {cm} từ ống đo độc lập giải quyết mâu thuẫn đang mở"),
    "tr.conflict_held": ("{fid} report {v} vs water balance {m}: gap {g} cm > {t} cm → held, ask for an independent reading",
                         "{fid}の報告 {v} と水収支 {m}：差 {g} cm > {t} cm → 保留し、独立した測定を依頼",
                         "{fid} báo {v} so với cân bằng nước {m}: lệch {g} cm > {t} cm → tạm giữ, xin số đo độc lập"),
    "tr.conflict_ok": ("{fid} {v} vs water balance {m}: within {t} cm → accepted with recorder {who}",
                       "{fid} {v} と水収支 {m}：差は {t} cm 以内 → 記録者 {who} として採用",
                       "{fid} {v} so với cân bằng nước {m}: lệch trong {t} cm → chấp nhận, người ghi {who}"),
    "tr.pumpcal": ("HTX notice applied from the station record: {a} → {b} (the LLM only labels the message intent)",
                   "ポンプ場の記録からHTXの通知を反映：{a} → {b}（LLMはメッセージの意図を分類するだけ）",
                   "Áp dụng thông báo của HTX theo sổ của trạm: {a} → {b} (LLM chỉ gắn nhãn ý định tin nhắn)"),
    "tr.wi_rain": ("forecast {day}: {real} mm Open-Meteo + {mm} mm what-if = {tot} mm; projection re-run for 6 fields",
                   "{day}の予報：Open-Meteo {real} mm + What-if {mm} mm = {tot} mm。6区画の予測を再計算",
                   "dự báo {day}: {real} mm Open-Meteo + {mm} mm giả định = {tot} mm; tính lại dự báo cho 6 thửa"),
    "tr.wi_flower": ("{fid} set to flowering for {n} days: needs standing water (≥ {w} cm) every day; drying not allowed",
                     "{fid}を{n}日間の出穂期に設定：毎日の湛水（≥ {w} cm）が必要で、落水期間は設けない",
                     "{fid} đặt là trổ bông trong {n} ngày: ngày nào cũng cần nước (≥ {w} cm); không được phơi ruộng"),
    "tr.wi_pump": ("what-if: run {a} moved to {b}; every field must last {n} days instead of {m}",
                   "What-if：送水を{a}から{b}に変更。各区画は{m}日ではなく{n}日もたせる必要がある",
                   "giả định: dời lượt bơm {a} sang {b}; mỗi thửa phải giữ nước {n} ngày thay vì {m}"),
    "tr.wi_sched": ("{n} fields per run → {summary}", "1回{n}区画 → {summary}", "{n} thửa/lượt → {summary}"),
    "tr.wi_gate": ("what-if plans are a sandbox: nothing written to the evidence log, nothing can be approved",
                   "What-ifの計画はサンドボックス：証拠ログには何も書かれず、承認もできない",
                   "lịch giả định chỉ để thử: không ghi vào nhật ký bằng chứng, không thể duyệt"),
    "tr.wi_held": ("photo {r} vs water balance {ref}: gap {g} cm; usable {u} → held, plan keeps the water-balance level",
                   "写真 {r} と水収支 {ref}：差 {g} cm、使用 {u} → 保留し、計画は水収支の水位を維持",
                   "ảnh {r} so với cân bằng nước {ref}: lệch {g} cm; dùng được: {u} → tạm giữ, lịch giữ mực theo cân bằng nước"),
    "tr.wi_ok": ("photo {r} vs water balance {ref}: within {t} cm → accepted for the re-plan",
                 "写真 {r} と水収支 {ref}：差は {t} cm 以内 → 再計画に採用",
                 "ảnh {r} so với cân bằng nước {ref}: lệch trong {t} cm → dùng để lập lại lịch"),
    "tr.vision": ("{cm} · conf {c} · EXIF {when}", "{cm} · 信頼度 {c} · EXIF {when}", "{cm} · độ tin cậy {c} · EXIF {when}"),
    "tr.vision_short": ("{cm} · conf {c}", "{cm} · 信頼度 {c}", "{cm} · độ tin cậy {c}"),
    "tr.parse": ("{intent} · {fid} · {v} · conf {c}", "{intent} · {fid} · {v} · 信頼度 {c}", "{intent} · {fid} · {v} · độ tin cậy {c}"),
    "tr.ask": ("ask {pick} · fallback {fallback}", "依頼先：{pick} · 代替：{fallback}", "nhờ {pick} · dự phòng {fallback}"),

    "intent.water_level": ("water level", "水位の報告", "báo mực nước"),
    "intent.pump_schedule": ("pump schedule", "送水日程", "lịch bơm"),
    "intent.rain_report": ("rain report", "降雨の報告", "báo mưa"),
    "intent.question": ("question", "質問", "câu hỏi"),
    "intent.other": ("other", "その他", "khác"),

    "status.accepted": ("accepted", "採用", "chấp nhận"),
    "status.rejected": ("rejected", "却下", "bị loại"),
    "status.approved": ("approved", "承認", "đã duyệt"),
    "status.suspicious": ("suspicious", "疑義あり", "nghi sai"),

    "v.refused": ("message gives instructions to the agent ({hits}): nothing recorded; only the HTX approves plans",
                  "エージェントへの指示を含むメッセージ（{hits}）：何も記録しない。計画を承認するのはHTXだけ",
                  "tin nhắn ra lệnh cho trợ lý ({hits}): không ghi gì; chỉ HTX được duyệt lịch"),
    "v.not_reading": ("not a water-level reading: nothing recorded, no plan change", "水位の報告ではない：記録せず、計画も変えない",
                      "không phải số đo mực nước: không ghi, lịch không đổi"),
    "v.no_field": ("field unknown: ask which field", "区画が不明：どの区画か確認する", "chưa rõ thửa nào: hỏi lại"),
    "v.range": ("{v} is outside the physical range ({lo} to {hi}, bund height): not recorded; ask again",
                "{v} は物理的にありえない範囲（{lo}〜{hi}、畦畔の高さ）：記録せず、再確認",
                "{v} nằm ngoài khoảng thực tế ({lo} đến {hi}, chiều cao bờ): không ghi; hỏi lại"),
    "v.disagree": ("LLM {a} and rule parser {b} disagree: ask again", "LLMの {a} とルール解析の {b} が不一致：再確認",
                   "LLM đọc {a}, bộ đọc theo luật đọc {b}, không khớp: hỏi lại"),
    "v.lowconf": ("confidence {c} < {t}: estimate not recorded as evidence; ask for the gauge number",
                  "信頼度 {c} < {t}：推定値は証拠として記録せず、観測管の数値を尋ねる",
                  "độ tin cậy {c} < {t}: số ước lượng không ghi làm bằng chứng; xin số trên ống đo"),
    "v.held_photo": ("Photo {cm} held as suspicious; independent reading requested", "写真の {cm} を疑義ありとして保留。独立した測定を依頼",
                     "Tạm giữ ảnh {cm} vì nghi sai; đã xin số đo độc lập"),
    "v.verified": ("{fid} {cm} from an independent gauge · #{n} {status}", "独立した観測管で {fid} {cm} · #{n} {status}",
                   "{fid} {cm} từ ống đo độc lập · #{n} {status}"),
    "v.held": ("{fid} {v} held: {g} cm from the water balance", "{fid} {v} を保留：水収支との差 {g} cm",
               "Tạm giữ {fid} {v}: lệch {g} cm so với cân bằng nước"),
    "v.recorded": ("{fid} {v} recorded as evidence · recorder {who}", "{fid} {v} を証拠として記録 · 記録者 {who}",
                   "Đã ghi {fid} {v} làm bằng chứng · người ghi {who}"),
    "v.wi_unread": ("unreadable photo", "写真を読み取れない", "ảnh không đọc được"),
    "v.wi_notused": ("photo {cm} not used: {codes}", "写真の {cm} は使わない：{codes}", "không dùng ảnh {cm}: {codes}"),
    "v.wi_gap": ("photo {cm} is {g} cm from the water balance", "写真の {cm} は水収支と {g} cm の差", "ảnh {cm} lệch {g} cm so với cân bằng nước"),
    "v.wi_ok": ("photo {cm} accepted for {fid} (sandbox)", "写真の {cm} を{fid}に採用（サンドボックス）", "nhận ảnh {cm} cho {fid} (chỉ thử)"),

    "c.photo": ("Sensor and water balance agree after {mm} mm of rain; the photo is the odd one out. The agent suspects the photo, not the sensor, and does not use it.",
                "{mm} mmの雨の後、センサーと水収支は一致し、写真だけが外れている。エージェントはセンサーではなく写真を疑い、使わない。",
                "Sau {mm} mm mưa, cảm biến và cân bằng nước khớp nhau, chỉ có ảnh là lệch. Trợ lý nghi ảnh chứ không nghi cảm biến, và không dùng ảnh."),
    "c.chat": ("The report and the water balance disagree by more than 5 cm. The agent keeps the water-balance level and asks for an independent reading.",
               "報告と水収支の差が5 cmを超えている。エージェントは水収支の水位を維持し、独立した測定を依頼する。",
               "Số báo và cân bằng nước lệch hơn 5 cm. Trợ lý giữ mực nước theo cân bằng nước và xin số đo độc lập."),

    "res.confirmed": ("confirmed: the independent reading {v} agrees with entry #{n} ({d})", "確認済み：独立した測定値 {v} は記録#{n}（{d}）と一致",
                      "đã xác nhận: số đo độc lập {v} khớp với bản ghi #{n} ({d})"),
    "res.misread": ("misread: capture time {when} is before the {mm} mm rain (old photo re-sent)",
                    "読み違い：撮影時刻 {when} は {mm} mm の雨より前（古い写真の再送）",
                    "đọc sai: giờ chụp {when} trước trận mưa {mm} mm (gửi lại ảnh cũ)"),
    "res.replaced": ("replaced by an independent second-gauge reading", "独立した2本目の観測管の測定値で置き換え",
                     "được thay bằng số đo độc lập ở ống thứ hai"),

    "log.sensor": ("daily 06:00 reading", "毎日06:00の測定", "số đo 06:00 hằng ngày"),
    "log.routine": ("routine report", "定期報告", "báo cáo định kỳ"),
    "log.seed_fill": ("{day} run filled field", "{day}の送水で湛水", "lượt bơm {day} đã cấp đầy ruộng"),
    "log.seed_check": ("checked at the {day} run", "{day}の送水時に確認", "kiểm tra lúc lượt bơm {day}"),
    "log.filled": ("filled in run {day} ({id})", "{day}の送水で湛水（{id}）", "đã cấp nước ở lượt {day} ({id})"),
    "log.held_run": ("run {day} not executed by the agent: {id} was rejected; HTX decides manually",
                     "{day}の送水はエージェントが実行しない：{id}が却下されたため、HTXが手動で判断",
                     "trợ lý không chạy lượt {day}: {id} không được duyệt; HTX tự quyết định"),
    "log.paused": ("run {day} paused as proposed in {id}", "{id}の提案どおり{day}の送水を一時停止", "tạm hoãn lượt {day} theo đề xuất {id}"),
    "log.photo": ("uploaded {up}; capture time {cap}; {a} cm from sensor, {b} cm from water balance",
                  "送信 {up}、撮影 {cap}。センサーとの差 {a} cm、水収支との差 {b} cm",
                  "gửi lúc {up}; giờ chụp {cap}; lệch {a} cm so với cảm biến, {b} cm so với cân bằng nước"),
    "log.photo_read": ("read by {model} (confidence {c})", "{model}が読み取り（信頼度 {c}）", "{model} đọc (độ tin cậy {c})"),
    "log.sha": ("sha {sha}", "sha {sha}", "sha {sha}"),
    "log.total": ("(total {mm} mm)", "（合計 {mm} mm）", "(tổng {mm} mm)"),
    "log.day_mm": ("{day} {mm} mm", "{day} {mm} mm", "{day} {mm} mm"),
    "log.review": ("entry #{n} {reason}; kept for audit", "記録#{n}：{reason}。監査用に保存", "bản ghi #{n} {reason}; giữ lại để kiểm tra"),
    "log.replaced_by": (", replaced by #{m}", "、#{m}で置き換え", ", thay bằng #{m}"),
    "log.second": ("independent reading requested for entry #{n}", "記録#{n}に対して依頼した独立測定", "số đo độc lập được yêu cầu cho bản ghi #{n}"),
    "log.clarify": ("{quote} → not recorded ({verdict})", "{quote} → 記録せず（{verdict}）", "{quote} → không ghi ({verdict})"),
    "log.suspicious": ("{quote} → {v}; water balance {m}; gap > {t} cm", "{quote} → {v}。水収支 {m}。差 > {t} cm",
                       "{quote} → {v}; cân bằng nước {m}; lệch > {t} cm"),
    "log.accepted": ("{quote} → {v}; water balance {m}", "{quote} → {v}。水収支 {m}", "{quote} → {v}; cân bằng nước {m}"),
    "log.moved": ("run {a} moved to {b}", "送水を{a}から{b}に変更", "dời lượt bơm {a} sang {b}"),
    "log.decision": ("{id} {status}", "{id} {status}", "{id} {status}"),
    "log.proposal": ("{id}: {summary}", "{id}：{summary}", "{id}: {summary}"),
    "log.decision_row": ("{id} {action} ({run}): {reason}", "{id} {action}（{run}）：{reason}", "{id} {action} ({run}): {reason}"),
    "log.scripted_ok": ("confirmed before the run (scripted in the Team demo scenario)", "送水前に確認（チームのデモシナリオの台本）",
                        "xác nhận trước lượt bơm (theo kịch bản demo của nhóm)"),

    "miss.gap": ("{n}-day gap in water-level readings ({a} → {b})", "水位記録に{n}日間の空白（{a} → {b}）",
                 "{n} ngày liền không có số đo mực nước ({a} → {b})"),
    "miss.person": ("Sensor only: no gauge photo or HTX reading to cross-check it", "センサーのみ：照合できる観測管の写真やHTXの測定がない",
                    "Chỉ có cảm biến: không có ảnh ống đo hay số đo của HTX để đối chiếu"),
    "miss.pending": ("Waiting for an independent reading", "独立した測定を待っている", "Đang chờ số đo độc lập"),
    "miss.measure": ("Waiting for HTX reading before the inlet opens", "取水口を開ける前のHTXの測定を待っている", "Chờ HTX đo trước khi mở cống"),
    "miss.decision": ("Latest pump plan not yet approved", "最新の送水計画がまだ承認されていない", "Lịch bơm mới nhất chưa được duyệt"),
    "miss.meta": ("Record missing metadata", "記録のメタデータが不足", "Bản ghi thiếu thông tin"),

    "chat.sensor": ("Field 2 sensor: {cm} (AWD drying)", "区画2のセンサー：{cm}（落水期間中）", "Cảm biến thửa 2: {cm} (đang phơi ruộng)"),
    "chat.rain": ("Overnight rain {mm} mm (Open-Meteo archive)", "夜間の雨 {mm} mm（Open-Meteo、2026年2月26〜27日）",
                  "Mưa qua đêm {mm} mm (Open-Meteo, 26–27/02/2026)"),
    "chat.approved": ("Station approved plan {id} ({run}).", "ポンプ場が計画{id}（{run}）を承認しました。", "Trạm đã duyệt lịch {id} ({run})."),
    "chat.rejected": ("Station rejected plan {id} ({run}).", "ポンプ場が計画{id}（{run}）を却下しました。", "Trạm không duyệt lịch {id} ({run})."),
    "chat.reject_ack": ("Noted: plan {id} rejected. The agent never pumps on its own; waiting for the HTX decision.",
                        "計画{id}の却下を確認しました。エージェントが勝手に送水することはありません。HTXの判断を待ちます。",
                        "Dạ, em ghi nhận trạm không duyệt lịch {id}. Em không tự bơm; chờ HTX quyết định."),
    "chat.ask_field": ("Which field is this, please?", "どの区画のことか教えていただけますか？", "Dạ, anh/chị cho em biết thửa số mấy ạ?"),
    "chat.ask_gauge_field": ("Could you read the number on the gauge tube of field {n}: how many cm of water?",
                             "区画{n}の観測管の目盛りを読んでいただけますか？水は何cmですか？",
                             "Dạ, anh/chị đọc giúp em số trên ống đo thửa {n}, nước bao nhiêu phân ạ?"),
    "chat.ask_again": ("Just to be sure: how many cm of water in field {n}?", "念のため確認させてください。区画{n}の水は何cmですか？",
                       "Dạ cho em hỏi lại cho chắc: thửa {n} nước bao nhiêu phân ạ?"),
    "chat.ask_gauge": ("Could you read the number on the gauge tube: how many cm above or below the soil?",
                       "観測管の目盛りを読んでいただけますか？田面から何cm上か下かを教えてください。",
                       "Dạ, anh/chị đọc giúp em số trên ống đo, nước cao hay thấp bao nhiêu phân ạ?"),
    "chat.refusal": ("I only record gauge readings. HTX approves every pump plan.",
                     "私は観測管の測定値を記録するだけです。送水計画はすべてHTXが承認します。",
                     "Dạ, em chỉ ghi số đo mực nước từ ống đo thôi ạ. Mọi lịch bơm đều do HTX duyệt."),
    "chat.photo": ("[Gauge photo, field 2]", "［区画2の観測管の写真］", "[Ảnh ống đo thửa 2]"),

    "fm.remeasure": ("After the rain, field {n} should already have water. Please measure at the tube near the inlet, or I'll ask {officer} from the HTX to come.",
                     "雨の後なので、区画{n}にはもう水があるはずです。取水口近くの観測管で測っていただけますか。難しければHTXの{officer}に見に来てもらいます。",
                     "Sau mưa vừa rồi, ruộng thửa {n} lẽ ra đã có nước. Anh đo giúp em ở ống gần cống, hoặc em nhờ {officer} bên HTX ghé đo nhé."),
    "fm.hold_rain": ("It rained, so field {n} needs no pumping. Close the inlet and keep the rain water.",
                     "雨が降ったので、区画{n}は送水不要です。取水口を閉じて雨水をためておいてください。",
                     "Có mưa, chưa cần bơm cho thửa {n}. Đóng cống giữ nước mưa."),
    "fm.wait": ("Field {n} waits for the next pump run; keep the inlet closed.", "区画{n}は次回の送水まで待機です。取水口は閉じたままにしてください。",
                "Thửa {n} chờ đợt bơm sau, đóng cống giữ nước."),
    "fm.irrigate": ("Field {n} gets water on {run}. Open the inlet when the HTX calls.", "区画{n}は{run}に送水します。HTXから連絡があったら取水口を開けてください。",
                    "Thửa {n} được bơm {run}. Mở cống khi HTX báo."),
    "fm.line": ("Field {n}: {action} ({run}).", "区画{n}：{action}（{run}）。", "Thửa {n}: {action} ({run})."),

    "rule.unit": ("{unit} = {k} cm; {phrase} = {amount}", "{unit} = {k} cm、{phrase} = {amount}", "{unit} = {k} cm; {phrase} = {amount}"),
    "rule.half": ("{word} = +half", "{word} = +0.5", "{word} = +một nửa"),
    "rule.below": ("below-surface word found", "田面より下を表す語あり", "có từ chỉ dưới mặt ruộng"),
    "rule.above": ("no below-surface word, so water above soil", "田面より下を表す語がないので、田面より上の水", "không có từ chỉ dưới mặt ruộng nên nước nằm trên mặt ruộng"),
    "rule.none": ("no number + unit found", "数値と単位が見つからない", "không tìm thấy số và đơn vị"),
    "rule.instruction": ("message gives instructions to the agent; rules never record it", "エージェントへの指示を含むメッセージ。ルールでは記録しない",
                         "tin nhắn ra lệnh cho trợ lý; luật không bao giờ ghi nhận"),

    "wi.rain_label": ("+{mm} mm rain forecast for {day}", "{day}の降雨予報に +{mm} mm", "+{mm} mm mưa dự báo cho {day}"),
    "wi.rain_note": ("Forecast for today becomes {tot} mm ({real} mm Open-Meteo + {mm} mm what-if).",
                     "本日の予報は {tot} mm になる（Open-Meteo {real} mm + What-if {mm} mm）。",
                     "Dự báo hôm nay thành {tot} mm ({real} mm Open-Meteo + {mm} mm giả định)."),
    "wi.flower_label": ("{fid} flowers from {day}", "{fid}が{day}から出穂", "{fid} trổ bông từ {day}"),
    "wi.flower_note": ("{fid} is treated as flowering for {n} days, so it must keep standing water.",
                       "{fid}を{n}日間の出穂期として扱うため、湛水を保つ必要がある。",
                       "{fid} được coi là đang trổ bông trong {n} ngày nên phải giữ nước trên ruộng."),
    "wi.pump_label": ("next pump run {a} → {b}", "次回の送水 {a} → {b}", "lượt bơm tới {a} → {b}"),
    "wi.pump_note": ("Every field must now last {n} days instead of {m}.", "各区画は{m}日ではなく{n}日もたせる必要がある。",
                     "Mỗi thửa giờ phải giữ nước {n} ngày thay vì {m} ngày."),
    "wi.photo_label": ("gauge photo {img} for {fid}", "{fid}の観測管の写真 {img}", "ảnh ống đo {img} cho {fid}"),
    "wi.uploaded": ("uploaded photo", "アップロードした写真", "ảnh đã tải lên"),
    "wi.exif_note": ("What-if: capture time assumed to be the upload time (EXIF ignored).", "What-if：撮影時刻を送信時刻とみなす（EXIFは無視）。",
                     "Giả định: coi giờ chụp là giờ gửi (bỏ qua EXIF)."),
    "wi.unread_note": ("The photo could not be read, so nothing changes; the agent asks for a clearer photo.",
                       "写真を読み取れないため何も変わらない。エージェントはより鮮明な写真を依頼する。",
                       "Không đọc được ảnh nên không có gì thay đổi; trợ lý xin ảnh rõ hơn."),
    "wi.kind.rain": ("What-if: more rain", "What-if：雨を追加", "Giả định: mưa thêm"),
    "wi.kind.flowering": ("What-if: field flowering", "What-if：区画が出穂", "Giả định: thửa trổ bông"),
    "wi.kind.pump": ("What-if: pump day moved", "What-if：送水日を変更", "Giả định: dời ngày bơm"),
    "wi.kind.photo": ("What-if: another gauge photo", "What-if：別の観測管の写真", "Giả định: ảnh ống đo khác"),

    "vis.no_image": ("no image file for this event", "このイベントの画像ファイルがない", "không có tệp ảnh cho sự kiện này"),
    "vis.not_installed": ("vision module not installed", "画像認識モジュールが未導入", "chưa cài mô-đun đọc ảnh"),
    "vis.load_failed": ("vision module failed to load", "画像認識モジュールを読み込めない", "không tải được mô-đun đọc ảnh"),
    "vis.error": ("vision module error", "画像認識モジュールのエラー", "lỗi mô-đun đọc ảnh"),
    "vis.replay_miss": ("replay mode: no cached reading for this image", "再生モード：この画像の保存済み読み取り値がない",
                        "chế độ phát lại: chưa có số đọc lưu sẵn cho ảnh này"),
    "vis.llm_failed": ("the vision LLM call failed", "画像認識LLMの呼び出しに失敗", "gọi LLM đọc ảnh thất bại"),
    "vis.skipped": ("vision call skipped by presenter", "発表者が画像認識をスキップ", "người trình bày đã bỏ qua bước đọc ảnh"),

    "llmerr.replay": ("offline replay: no cached reply for this input", "オフライン再生：この入力の保存済み応答がない",
                      "phát lại ngoại tuyến: chưa có câu trả lời lưu sẵn cho đầu vào này"),
    "llmerr.rules": ("rules-only mode", "ルールのみのモード", "chế độ chỉ dùng luật"),
    "llmerr.timeout": ("Claude CLI timed out", "Claude CLIがタイムアウト", "Claude CLI hết thời gian chờ"),
    "llmerr.skipped": ("LLM call skipped by presenter", "発表者がLLMの呼び出しをスキップ", "người trình bày đã bỏ qua lệnh gọi LLM"),
    "llmerr.nocli": ("Claude CLI not found", "Claude CLIが見つからない", "không tìm thấy Claude CLI"),
    "llmerr.invalid": ("reply rejected by the validator", "検証で応答を却下", "câu trả lời bị bộ kiểm tra loại"),
    "llmerr.other": ("LLM unavailable", "LLMを利用できない", "LLM không dùng được"),

    "p.scheduler": ("Deterministic scheduler re-plans the whole cluster", "定められたルールに基づき、全区画の送水計画を再計算",
                    "Hệ thống tính lại lịch bơm cho cả cụm theo quy tắc"),
    "p.brief": ("LLM · Sonnet 5.5 explains the plan and writes one message per field", "LLM · Sonnet 5.5 が計画を説明し、区画ごとにメッセージを作成",
                "LLM · Sonnet 5.5 giải thích lịch và soạn tin cho từng thửa"),
    "p.ask": ("LLM · Haiku 4.5 chooses who re-measures and writes the ask", "LLM · Haiku 4.5 が再測定の依頼先を選び、依頼文を作成",
              "LLM · Haiku 4.5 chọn người đo lại và soạn lời nhờ"),
    "p.vision": ("LLM · Sonnet 5.5 reads the gauge photo (vision)", "LLM · Sonnet 5.5 が観測管の写真を読み取り（画像認識）",
                 "LLM · Sonnet 5.5 đọc ảnh ống đo"),
    "p.parse": ("LLM · Haiku 4.5 reads the message (Mekong dialect)", "LLM · Haiku 4.5 がメッセージを読解（メコン方言）",
                "LLM · Haiku 4.5 đọc tin nhắn (tiếng miền Tây)"),
    "p.guards": ("Deterministic guardrails: instruction guard, range, rule parser, confidence, conflict check",
                 "データを検証：不正な指示、数値の範囲、ルールによる読み取り、信頼度、他のデータとの整合性",
                 "Kiểm tra dữ liệu: yêu cầu trái quy tắc, khoảng giá trị, kết quả đọc số đo, độ tin cậy và chênh lệch giữa các nguồn"),
    "p.notice": ("LLM · Haiku 4.5 labels the HTX notice", "LLM · Haiku 4.5 がHTXの通知を分類", "LLM · Haiku 4.5 gắn nhãn thông báo của HTX"),
    "p.sandbox": ("Deterministic tools re-plan the cluster in a sandbox", "現在の計画を変更せず、別の条件で送水計画を試算",
                  "Tính thử lịch bơm với điều kiện mới, giữ nguyên lịch hiện tại"),
    "p.translate": ("LLM · Haiku 4.5 translates the new LLM text", "LLM · Haiku 4.5 が新しいLLMの文章を翻訳", "LLM · Haiku 4.5 dịch đoạn văn LLM mới"),

    "job.next": ("Agent processes the next event", "エージェントが次のイベントを処理", "Trợ lý xử lý sự kiện tiếp theo"),
    "job.goto": ("Replaying the scenario to step {n}", "ステップ{n}までシナリオを再生", "Phát lại kịch bản đến bước {n}"),
    "job.message": ("Live message from {who}", "{who}からのライブメッセージ", "Tin nhắn trực tiếp từ {who}"),
    "job.decision": ("Recording the station manager's decision", "ポンプ場責任者の判断を記録", "Ghi lại quyết định của người phụ trách trạm"),
    "job.whatif_clear": ("Closing the what-if lab", "条件変更の画面を閉じる", "Đóng phần thử tình huống"),
    "job.brief": ("LLM · Sonnet 5.5 explains {id} and writes farmer messages", "LLM · Sonnet 5.5 が{id}を説明し、農家向けメッセージを作成",
                  "LLM · Sonnet 5.5 giải thích {id} và soạn tin cho nông dân"),
    "job.whatif_brief": ("LLM · Sonnet 5.5 explains the what-if plan", "LLM · Sonnet 5.5 がWhat-ifの計画を説明", "LLM · Sonnet 5.5 giải thích lịch giả định"),
    "job.translate": ("Translating new LLM text", "新しいLLMの文章を翻訳中", "Đang dịch đoạn văn LLM mới"),

    "err.internal_job": ("Internal error ({kind}). The demo state is kept; press Reset if it looks wrong.",
                         "内部エラー（{kind}）。デモの状態は保持されています。おかしい場合はリセットしてください。",
                         "Lỗi nội bộ ({kind}). Trạng thái demo vẫn được giữ; nếu thấy sai, bấm Đặt lại."),
    "err.internal": ("Internal server error. The demo keeps running.", "サーバー内部エラー。デモは動作を続けます。",
                     "Lỗi máy chủ nội bộ. Demo vẫn chạy tiếp."),
    "err.busy": ("The agent is still working on “{label}” ({s} s). Wait, or press Skip LLM.",
                 "エージェントはまだ「{label}」を処理中です（{s}秒）。待つか、「LLMをスキップ」を押してください。",
                 "Trợ lý vẫn đang xử lý “{label}” ({s} giây). Chờ thêm hoặc bấm Bỏ qua LLM."),
    "err.reset_wait": ("The agent is still finishing a call. Try Reset again in a few seconds.",
                       "エージェントが処理を終えるところです。数秒後にもう一度リセットしてください。",
                       "Trợ lý đang hoàn tất một lệnh gọi. Vài giây nữa hãy bấm Đặt lại lần nữa."),
    "err.unknown_photo": ("Unknown photo. Pick one from the test set or upload a JPEG/PNG.", "不明な写真です。テストセットから選ぶか、JPEG/PNGをアップロードしてください。",
                          "Ảnh không xác định. Chọn ảnh trong bộ thử hoặc tải lên JPEG/PNG."),
    "err.not_found_page": ("No such page: {path}", "ページが見つかりません：{path}", "Không có trang: {path}"),
    "err.not_found_action": ("No such action: {path}", "その操作はありません：{path}", "Không có thao tác: {path}"),
    "err.too_large": ("Request too large.", "リクエストが大きすぎます。", "Yêu cầu quá lớn."),
    "err.bad_json": ("Request body is not valid JSON.", "リクエスト本文が正しいJSONではありません。", "Nội dung yêu cầu không phải JSON hợp lệ."),
    "err.not_object": ("Request body must be a JSON object.", "リクエスト本文はJSONオブジェクトである必要があります。", "Nội dung yêu cầu phải là một đối tượng JSON."),
    "err.cancelled": ("LLM call skipped; the agent falls back to cached replies or deterministic rules.",
                      "LLMへの問い合わせを中止しました。保存済みの応答を使うか、ルールに基づく処理に切り替えます。",
                      "Đã bỏ qua LLM. Agent sẽ dùng câu trả lời trong cache hoặc xử lý theo quy tắc."),
    "err.end": ("The scripted scenario is finished. Approve the plan, send a live message or press Reset.",
                "シナリオは終了しました。計画を承認するか、ライブメッセージを送るか、リセットしてください。",
                "Kịch bản đã xong. Hãy duyệt lịch, gửi tin nhắn trực tiếp hoặc bấm Đặt lại."),
    "err.step_int": ("step must be an integer", "ステップは整数で指定してください", "bước phải là số nguyên"),
    "err.type_message": ("Type a message first.", "先にメッセージを入力してください。", "Hãy nhập tin nhắn trước."),
    "err.unknown_sender": ("Unknown sender.", "不明な送信者です。", "Người gửi không xác định."),
    "err.unknown_sender_list": ("Unknown sender. Choose one of: {list}.", "不明な送信者です。次から選んでください：{list}。", "Người gửi không xác định. Chọn một trong: {list}."),
    "err.decision": ("decision must be approve or reject", "判断は承認か却下のどちらかです", "quyết định phải là duyệt hoặc không duyệt"),
    "err.no_plan": ("There is no proposed plan to decide on.", "判断する承認待ちの計画がありません。", "Không có lịch nào đang chờ duyệt."),
    "err.unknown_whatif": ("Unknown what-if.", "不明なWhat-ifです。", "Tình huống giả định không xác định."),
    "err.press_next": ("Press → once first: the what-if lab compares against the current plan.",
                       "まず→を押して計画を作成してください。その後、条件を変えて比較できます。",
                       "Bấm → để tạo lịch đầu tiên, rồi thử thay đổi điều kiện để so sánh."),
    "err.choose_field": ("Choose a field F1–F6.", "区画F1〜F6を選んでください。", "Chọn một thửa F1–F6."),
    "err.no_photo_data": ("No photo data.", "写真のデータがありません。", "Không có dữ liệu ảnh."),
    "err.bad_base64": ("Photo data is not valid base64.", "写真のデータが正しいbase64ではありません。", "Dữ liệu ảnh không phải base64 hợp lệ."),
    "err.photo_size": ("Photo larger than 8 MB.", "写真が8 MBを超えています。", "Ảnh lớn hơn 8 MB."),
    "err.photo_type": ("Only JPEG or PNG photos.", "JPEGまたはPNGの写真のみ対応しています。", "Chỉ nhận ảnh JPEG hoặc PNG."),
    "err.not_text": ("The message must be text.", "メッセージはテキストである必要があります。", "Tin nhắn phải là văn bản."),
    "err.empty": ("The message is empty.", "メッセージが空です。", "Tin nhắn đang trống."),
    "err.not_number": ("not a number: {value}", "数値ではありません：{value}", "không phải số: {value}"),
    "err.rain_range": ("Rain must be between 1 and {max} mm.", "雨量は1〜{max} mmで指定してください。", "Lượng mưa phải từ 1 đến {max} mm."),
    "err.choose_date": ("Choose a pump date.", "送水日を選んでください。", "Chọn ngày bơm."),
    "err.date_range": ("The pump date must be within {n} days after {day}.", "送水日は{day}から{n}日以内にしてください。",
                       "Ngày bơm phải trong vòng {n} ngày sau {day}."),
    "err.same_day": ("The next run is already {day}.", "次回の送水はすでに{day}です。", "Lượt bơm tới đã là {day}."),
    "err.no_reading": ("No photo reading.", "写真の読み取り値がありません。", "Chưa có số đọc từ ảnh."),
}

PEOPLE = {
    "Bà Sáu": ("Mrs Sau", "サウさん", "Bà Sáu"),
    "anh Hùng": ("Hung", "フンさん", "anh Hùng"),
    "Anh Hùng (HTX)": ("Hung (HTX)", "フンさん（HTX）", "Anh Hùng (HTX)"),
    "Pump-station manager (người phụ trách trạm)": ("Pump-station manager", "ポンプ場責任者", "Người phụ trách trạm bơm"),
    "Cán bộ kỹ thuật": ("Technical officer", "技術職員", "Cán bộ kỹ thuật"),
    "Hộ thửa bên cạnh": ("Neighbouring farmer", "隣の区画の農家", "Hộ thửa bên cạnh"),
    "RiceBridge agent": ("RiceBridge agent", "RiceBridgeエージェント", "Trợ lý RiceBridge"),
    "RiceBridge Ops agent": ("RiceBridge Ops agent", "RiceBridge Opsエージェント", "Trợ lý RiceBridge Ops"),
    "Water-level sensor (simulated)": ("Water-level sensor (simulated)", "水位センサー（シミュレーション）", "Cảm biến mực nước (mô phỏng)"),
    "Open-Meteo": ("Open-Meteo", "Open-Meteo", "Open-Meteo"),
    "HTX": ("HTX", "HTX", "HTX"),
}
SUFFIXES = {
    ", same gauge": ("{x}, same gauge", "{x}（同じ観測管）", "{x}, cùng ống đo"),
    ", gauge near the inlet": ("{x}, gauge near the inlet", "{x}（取水口近くの観測管）", "{x}, ống gần cống"),
}
ROLES = {
    "re-photograph the same tube": ("re-photograph the same tube", "同じ観測管を撮り直す", "chụp lại cùng ống đo"),
    "farmer measures a second tube": ("farmer measures a second tube", "農家が2本目の観測管で測る", "nông dân đo ở ống thứ hai"),
    "HTX officer measures a second tube": ("HTX officer measures a second tube", "HTX職員が2本目の観測管で測る", "cán bộ HTX đo ở ống thứ hai"),
    "re-read the same tube": ("re-read the same tube", "同じ観測管を読み直す", "đọc lại cùng ống đo"),
    "neighbour reads a second tube": ("neighbour reads a second tube", "隣の農家が2本目の観測管を読む", "hộ bên cạnh đọc ống thứ hai"),
    "technical officer measures a second tube": ("technical officer measures a second tube", "技術職員が2本目の観測管で測る", "cán bộ kỹ thuật đo ở ống thứ hai"),
}
SAME_PERSON = " (same person who sent the disputed report)"
SAME_PERSON_T = ("{x} (same person who sent the disputed report)", "{x}（疑義のある報告を送った本人）", "{x} (chính người gửi số đo bị nghi)")
CANDIDATE_T = ("{name} ({role})", "{name}（{role}）", "{name} ({role})")


def capitalized(node):
    return {lang: (v[:1].upper() + v[1:]) if v else v for lang, v in node.items()}


def lit(text):
    return {lang: text for lang in LANGS}


def tr(key, **params):
    tpl = T[key]
    out = {}
    for i, lang in enumerate(LANGS):
        values = {k: pick(v, lang) for k, v in params.items()}
        out[lang] = tpl[i].format(**values)
    return out


def pick(value, lang):
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or ""
    return value


def cat(*parts, sep=" "):
    out = {}
    for lang in LANGS:
        glue = "" if lang == "ja" and sep == " " else sep
        out[lang] = glue.join(p for p in (pick(x, lang) for x in parts if x) if p)
    return out


def join_list(items, sep_key=None, sep=", "):
    out = {}
    for i, lang in enumerate(LANGS):
        glue = T[sep_key][i] if sep_key else ("、" if lang == "ja" and sep == ", " else sep)
        out[lang] = glue.join(pick(x, lang) for x in items)
    return out


def day(d):
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    wd = d.weekday()
    return {"en": d.strftime("%a %d %b"), "ja": f"{d.month}月{d.day}日({WEEKDAYS['ja'][wd]})", "vi": f"{WEEKDAYS['vi'][wd]} {d:%d/%m}"}


def moment(when):
    if isinstance(when, str):
        when = dt.datetime.fromisoformat(when)
    base = day(when.date())
    return {lang: f"{base[lang]} {when:%H:%M}" for lang in LANGS}


def cm(value):
    return f"{value:+.1f} cm".replace("-", "−")


def stage(code):
    return tr("stage." + code)


def stage_lower(code):
    return tr("stagelow." + code) if "stagelow." + code in T else tr("stage." + code)


def action(code):
    return tr("action." + code)


def source(code):
    return tr("src." + code) if "src." + code in T else lit(code)


def quote(text):
    return lit(f"“{text}”")


def person(name):
    if name is None:
        return lit("")
    name = str(name)
    if name in PEOPLE:
        return dict(zip(LANGS, PEOPLE[name]))
    for suffix, tpl in SUFFIXES.items():
        if name.endswith(suffix):
            base = person(name[: -len(suffix)])
            return {lang: tpl[i].format(x=base[lang]) for i, lang in enumerate(LANGS)}
    m = re.fullmatch(r"Hộ thửa (\d)", name)
    if m:
        n = m.group(1)
        return {"en": f"Field {n} farmer", "ja": f"区画{n}の農家", "vi": name}
    m = re.fullmatch(r"Cảm biến thửa (\d)", name)
    if m:
        n = m.group(1)
        return {"en": f"Field {n} sensor", "ja": f"区画{n}のセンサー", "vi": name}
    return lit(name)


def role(text):
    text = str(text or "")
    same = text.endswith(SAME_PERSON)
    base = text[: -len(SAME_PERSON)] if same else text
    out = dict(zip(LANGS, ROLES.get(base, (base, base, base))))
    if same:
        out = {lang: SAME_PERSON_T[i].format(x=out[lang]) for i, lang in enumerate(LANGS)}
    return out


def candidate(name, role_text):
    who, what = person(name), role(role_text)
    return {lang: CANDIDATE_T[i].format(name=who[lang], role=what[lang]) for i, lang in enumerate(LANGS)}


def vision_reason(reason):
    text = str(reason or "")
    for prefix, key in (("no image file", "vis.no_image"), ("vision module not installed", "vis.not_installed"),
                        ("vision module failed", "vis.load_failed"), ("vision module error", "vis.error"),
                        ("replay mode", "vis.replay_miss"), ("LLM failed", "vis.llm_failed"), ("vision call skipped", "vis.skipped")):
        if text.startswith(prefix):
            return tr(key)
    return {"en": text} if text else tr("v.wi_unread")


def llm_error(error):
    text = str(error or "")
    for needle, key in (("offline replay", "llmerr.replay"), ("rules-only", "llmerr.rules"), ("timed out", "llmerr.timeout"),
                        ("skipped", "llmerr.skipped"), ("not found", "llmerr.nocli"), ("attempt", "llmerr.invalid"),
                        ("rejected", "llmerr.invalid")):
        if needle in text:
            return tr(key)
    return tr("llmerr.other")


def localize_dates(text, lang):
    if lang == "en" or not text:
        return text

    def repl(m):
        month = MONTHS.index(m.group(3)) + 1
        wd = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun").index(m.group(1))
        d = int(m.group(2))
        if lang == "ja":
            return f"{month}月{d}日({WEEKDAYS['ja'][wd]})"
        return f"{WEEKDAYS['vi'][wd]} {d:02d}/{month:02d}"
    return EN_DATE.sub(repl, text)


def unquoted(text):
    return QUOTED.sub(" ", str(text or ""))


def foreign(text, lang):
    body = unquoted(text)
    if lang == "en":
        return bool(VI_CHARS.search(body) or CJK_CHARS.search(body))
    if lang == "ja":
        return bool(VI_CHARS.search(body))
    return bool(CJK_CHARS.search(body))


def is_text(node):
    return isinstance(node, dict) and node and set(node) <= set(LANGS) and all(isinstance(v, str) for v in node.values())


def text_key(node):
    body = {k: node[k] for k in ("en", "vi") if node.get(k)}
    if not body and node.get("ja"):
        body = {"ja": node["ja"]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]


def needs(node):
    missing = [lang for lang in LANGS if not node.get(lang)]
    dirty = [lang for lang in LANGS if node.get(lang) and foreign(node[lang], lang)]
    return missing + [lang for lang in dirty if lang not in missing]
