"use strict";
const STORY = {
  introTitle: {
    vi: "Trời mưa, trạm bơm đổi lịch. Agent giúp HTX quyết định tưới ruộng nào trước",
    en: "Rain comes, the pump schedule changes. The agent helps the HTX decide which fields to water first",
    ja: "雨が降り、ポンプの予定が変わる。どの田に先に水を入れるか、エージェントがHTXの判断を助けます",
  },
  introLine: {
    vi: "6 thửa ruộng dùng chung một trạm bơm. Người phụ trách trạm duyệt mọi lịch bơm.",
    en: "Six fields share one pump. The pump-station manager approves every plan.",
    ja: "6つの田が1台のポンプを共有。送水計画はすべてポンプ場の責任者が承認します。",
  },
  startTitle: {
    vi: "Ruộng đang khô dần. Trạm bơm sẽ chạy {day}",
    en: "The fields are drying out. The pump runs on {day}",
    ja: "田んぼが乾いてきました。ポンプは{day}に動きます",
  },
  proposeOrder: {
    vi: "Agent đề xuất mở cống {order}.",
    en: "The agent proposes to water {order}.",
    ja: "提案：{order}の順に送水。",
  },
  proposePause: {
    vi: "Agent đề xuất hoãn lượt bơm {day}. Chưa thửa nào cần nước.",
    en: "The agent proposes to skip the {day} run. No field needs water yet.",
    ja: "{day}の送水は見送りを提案。今は水が必要な田はありません。",
  },
  rainTitle: {
    vi: "Mưa lớn qua đêm. Ruộng có nước trở lại",
    en: "Heavy rain overnight. The fields have water again",
    ja: "夜のうちに大雨。田んぼに水が戻りました",
  },
  photoTitle: {
    vi: "Ảnh nông dân gửi báo {field} khô, nhưng cảm biến báo có nước",
    en: "A farmer's photo says {field} is dry, but the sensor says it has water",
    ja: "農家の写真では{field}は乾いているのに、センサーでは水がある",
  },
  photoLine: {
    vi: "Agent chưa dùng ảnh này và nhờ người khác đo lại.",
    en: "The agent holds the photo and asks someone else to measure.",
    ja: "写真はまだ使わず、別の人に測り直しを頼みます。",
  },
  remeasureTitle: {
    vi: "{who} đo lại {field}: ruộng có nước {cm}",
    en: "{who} measures {field} again: {cm} of water",
    ja: "{who}が{field}を測り直し：水位{cm}",
  },
  remeasureLine: {
    vi: "Số đo mới được ghi lại. Ảnh cũ bị đánh dấu đọc sai nhưng vẫn được giữ.",
    en: "The new reading is saved. The photo is marked as wrong but kept on file.",
    ja: "新しい測定値を記録。写真は誤りとして印を付け、記録に残します。",
  },
  voiceTitle: {
    vi: "Bà Sáu không có điện thoại. HTX báo hộ bằng giọng nói",
    en: "Mrs Sau has no phone. The HTX reports her field by voice",
    ja: "サウさんは携帯電話を持っていません。HTXが音声で代わりに報告します",
  },
  voiceLine: {
    vi: "Agent hiểu {q} là 3 cm. Ruộng bà Sáu có số đo như mọi thửa khác.",
    en: "The agent reads {q} as 3 cm. Her field is on record like every other.",
    ja: "{q}を3 cmと理解。サウさんの田も他と同じく記録されます。",
  },
  pumpTitle: {
    vi: "Trạm bơm dời lượt bơm sang {day}",
    en: "The pump station moves the run to {day}",
    ja: "ポンプ場が送水を{day}に変更",
  },
  needsApproval: {
    vi: "Lịch mới chờ người phụ trách trạm duyệt.",
    en: "The new plan waits for the pump-station manager.",
    ja: "新しい計画はポンプ場責任者の承認待ちです。",
  },
  approvedTitle: {
    vi: "Đã duyệt. {day}: mở cống {order}",
    en: "Approved. {day}: water {order}",
    ja: "承認済み。{day}は{order}の順に送水",
  },
  approvedPauseTitle: {
    vi: "Đã duyệt. Tạm hoãn lượt bơm {day}",
    en: "Approved. The {day} run is skipped",
    ja: "承認済み。{day}の送水は見送り",
  },
  approvedLine: {
    vi: "Quyết định đã được ghi vào sổ bằng chứng.",
    en: "The decision is saved in the evidence log.",
    ja: "この決定は証跡記録に保存されました。",
  },
  rejectedTitle: {
    vi: "Lịch không được duyệt. Agent không tự bơm nước",
    en: "Plan rejected. The agent does nothing on its own",
    ja: "計画は却下。エージェントは自分では何もしません",
  },
  rejectedLine: {
    vi: "HTX sẽ tự quyết định lượt bơm này.",
    en: "The HTX decides this pump run itself.",
    ja: "この送水はHTXが自分で決めます。",
  },
  liveRecorded: {
    vi: "Đã ghi số đo: {field} có nước {cm}",
    en: "Reading saved: {field} has {cm} of water",
    ja: "記録しました：{field}の水位は{cm}",
  },
  liveVerified: {
    vi: "Số đo độc lập xác nhận {field}: {cm}",
    en: "An independent reading confirms {field}: {cm}",
    ja: "別の測定で{field}を確認：{cm}",
  },
  liveHeld: {
    vi: "Số đo {field} khác xa dự tính. Agent nhờ người khác đo lại",
    en: "The {field} reading is far from the forecast. The agent asks someone else to check",
    ja: "{field}の値が予測と大きく違うため、別の人に確認を頼みます",
  },
  liveRefused: {
    vi: "Agent từ chối. Tin nhắn đòi bỏ qua quy tắc",
    en: "Refused. The message asks the agent to break the rules",
    ja: "拒否しました。ルールを無視するよう求める内容です",
  },
  liveClarify: {
    vi: "Tin nhắn chưa có số đo rõ ràng. Agent hỏi lại",
    en: "No clear number in the message. The agent asks again",
    ja: "はっきりした数値がないため、聞き直します",
  },
  liveNotReading: {
    vi: "Tin nhắn này không phải số đo mực nước. Lịch không đổi",
    en: "This message is not a water reading. Nothing changes",
    ja: "水位の報告ではありません。計画は変わりません",
  },
  refusedStamp: { vi: "Từ chối", en: "Refused", ja: "拒否" },
  refusedNote: {
    vi: "Chỉ HTX được duyệt lịch bơm. Không có số đo nào được ghi.",
    en: "Only the HTX can approve a pump plan. No reading was saved.",
    ja: "送水計画を承認できるのはHTXだけです。測定値は記録していません。",
  },
  planChanged: {
    vi: "Lịch bơm thay đổi và chờ duyệt.",
    en: "The pump plan changed and waits for approval.",
    ja: "送水計画が変わり、承認待ちです。",
  },
  planWaiting: {
    vi: "Lịch bơm {day} vẫn chờ duyệt.",
    en: "The {day} pump plan still waits for approval.",
    ja: "{day}の送水計画はまだ承認待ちです。",
  },
  planSame: { vi: "Lịch bơm không đổi.", en: "The pump plan stays the same.", ja: "送水計画は変わりません。" },
  othersWait: {
    vi: "Các thửa khác chờ đợt sau, {day}.",
    en: "Other fields wait for the next run, {day}.",
    ja: "他の区画は次回（{day}）まで待機。",
  },
  noRun: { vi: "Không mở cống thửa nào.", en: "No field gets water in this run.", ja: "今回はどの区画にも送水しません。" },
  movedFrom: { vi: "trước đây: {day}", en: "was {day}", ja: "変更前：{day}" },
  stampApproved: { vi: "Đã duyệt", en: "Approved", ja: "承認済み" },
  stampRejected: { vi: "Không duyệt", en: "Rejected", ja: "却下" },
  btnStart: { vi: "Bắt đầu", en: "Start", ja: "はじめる" },
  btnNext: { vi: "Tiếp", en: "Next", ja: "次へ" },
  btnBack: { vi: "Quay lại", en: "Back", ja: "戻る" },
  btnApprove: { vi: "Duyệt lịch", en: "Approve", ja: "承認する" },
  btnReject: { vi: "Không duyệt", en: "Reject", ja: "却下" },
  btnEvidence: { vi: "Xem bằng chứng", en: "See the evidence", ja: "証跡を見る" },
  actWater: { vi: "Mở cống", en: "Water", ja: "送水" },
  actWait: { vi: "Chờ", en: "Wait", ja: "待機" },
  actRain: { vi: "Mưa đủ", en: "Rain is enough", ja: "雨で十分" },
  soonHeading: { vi: "sắp trổ bông", en: "flowering soon", ja: "まもなく出穂" },
  soonTopdress: { vi: "sắp bón thúc", en: "fertiliser due", ja: "まもなく追肥" },
  rainDays: { vi: "Lượng mưa từng ngày", en: "Rain per day", ja: "日ごとの雨量" },
  beforeRain: { vi: "Trước mưa", en: "Before rain", ja: "雨の前" },
  afterRain: { vi: "Sau mưa", en: "After rain", ja: "雨の後" },
  photoSays: { vi: "Ảnh báo", en: "Photo says", ja: "写真の値" },
  sensorSays: { vi: "Cảm biến báo", en: "Sensor says", ja: "センサーの値" },
  takenBeforeRain: { vi: "Ảnh chụp {day}, trước cơn mưa", en: "Photo taken {day}, before the rain", ja: "撮影は{day}、雨の前" },
  takenOn: { vi: "Ảnh chụp {day}", en: "Photo taken {day}", ja: "撮影日 {day}" },
  wrongPhoto: { vi: "Ảnh, đọc sai", en: "Photo, misread", ja: "写真（読み違い）" },
  secondGauge: { vi: "Ống đo thứ hai", en: "Second gauge", ja: "2本目の観測管" },
  gaugeNote: {
    vi: "Mực nước so với mặt ruộng. Dưới −15 cm là ruộng cần nước.",
    en: "Water level against the soil surface. Below −15 cm a field needs water.",
    ja: "田面を基準にした水位。−15 cmを下回ると送水が必要です。",
  },
  chartTitle: { vi: "Mưa và bốc hơi mỗi ngày ở Long Xuyên", en: "Daily rain and evaporation in Long Xuyen", ja: "ロンスエンの毎日の雨量と蒸発量" },
  chatTitle: { vi: "Nhóm chat HTX, cụm ruộng A", en: "HTX group chat, field cluster A", ja: "HTXのグループチャット（A地区）" },
  chatEmpty: {
    vi: "Tin nhắn trong nhóm sẽ hiện ở đây. Bấm Bắt đầu để xem câu chuyện.",
    en: "Group messages appear here. Press Start to follow the story.",
    ja: "グループのメッセージがここに表示されます。「はじめる」を押してください。",
  },
  busyMessage: { vi: "Agent đang đọc tin nhắn", en: "The agent is reading the message", ja: "エージェントがメッセージを読んでいます" },
  busyPlan: { vi: "Agent đang cập nhật lịch bơm", en: "The agent is updating the pump plan", ja: "エージェントが送水計画を更新しています" },
  busyDecision: { vi: "Đang ghi quyết định", en: "Saving the decision", ja: "決定を保存しています" },
  busyWrite: { vi: "Agent đang viết tin cho nông dân", en: "The agent is writing to the farmers", ja: "エージェントが農家への連絡文を書いています" },
  busyGeneric: { vi: "Agent đang làm việc", en: "The agent is working", ja: "エージェントが処理しています" },
  carbonTitle: {
    vi: "{n} trên 6 thửa có đủ bằng chứng tưới tiết kiệm nước",
    en: "{n} of 6 fields have complete water-saving evidence",
    ja: "6区画中{n}区画で節水かんがいの証跡がそろっています",
  },
  carbonLine: {
    vi: "Mỗi số đo, ảnh và quyết định đều được ghi lại và không sửa được.",
    en: "Every reading, photo and decision is logged and cannot be changed.",
    ja: "測定値・写真・決定はすべて記録され、書き換えできません。",
  },
  fieldsComplete: { vi: "thửa đủ bằng chứng", en: "fields complete", ja: "区画が完了" },
  exportLog: { vi: "Xuất sổ bằng chứng", en: "Export the log", ja: "記録を書き出す" },
  verifyLog: { vi: "Kiểm tra sổ", en: "Verify the log", ja: "記録を検証" },
  verifiedOk: {
    vi: "Sổ nguyên vẹn: cả {n} bản ghi đều khớp.",
    en: "Log verified: all {n} records match.",
    ja: "検証済み：{n}件すべて一致しています。",
  },
  verifiedBad: {
    vi: "Phát hiện dữ liệu bị sửa ở bản ghi #{n}.",
    en: "Tampering detected at record #{n}.",
    ja: "記録 #{n} で改ざんを検出しました。",
  },
  parcelMap: { vi: "Bản đồ thửa", en: "Parcel map", ja: "区画マップ" },
  complete: { vi: "Đủ bằng chứng", en: "Complete", ja: "そろっている" },
  incomplete: { vi: "Còn thiếu", en: "Missing", ja: "不足あり" },
  canal: { vi: "Kênh HTX", en: "HTX canal", ja: "HTXの水路" },
  pump: { vi: "Bơm", en: "Pump", ja: "ポンプ" },
  footStory: {
    vi: "Mưa và bốc hơi: số liệu thật Open-Meteo, Long Xuyên 16/02-12/03/2026. Ruộng, người và tin nhắn: kịch bản demo.",
    en: "Rain and evaporation: real Open-Meteo data, Long Xuyen, 16 Feb-12 Mar 2026. Fields, people and messages: demo scenario.",
    ja: "雨量と蒸発量：Open-Meteoの実測データ（ロンスエン、2026年2月16日-3月12日）。田・人物・メッセージはデモ用シナリオ。",
  },
  engToggle: { vi: "Cách hoạt động", en: "How it works", ja: "仕組み" },
  engToggleTip: {
    vi: "Bật để xem chi tiết kỹ thuật: các bước của agent, mô hình, kiểm tra an toàn (E)",
    en: "Show the technical detail: agent steps, models, safety checks (E)",
    ja: "技術的な詳細を表示：エージェントの手順、モデル、安全チェック（E）",
  },
  sendPlaceholder: {
    vi: "Gõ tin như nông dân",
    en: "Type in Vietnamese",
    ja: "ベトナム語で入力",
  },
};

const WEEKDAY_LONG = {
  vi: ["Chủ nhật", "thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy"],
  en: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
  ja: ["日", "月", "火", "水", "木", "金", "土"],
};

const sx = (key, params) => {
  const entry = STORY[key];
  let out = entry ? entry[lang] || entry.en : key;
  if (params) out = out.replace(/\{(\w+)\}/g, (m, k) => (params[k] === undefined || params[k] === null ? m : String(params[k])));
  return out;
};
const sxq = (key, params, quote) => esc(sx(key, params)).replace("{q}", src(`“${quote}”`));
const capFirst = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

function dayLong(iso) {
  if (!iso) return "";
  const d = asDate(iso);
  const wd = WEEKDAY_LONG[lang][d.getDay()];
  if (lang === "ja") return `${d.getMonth() + 1}月${d.getDate()}日(${wd})`;
  if (lang === "vi") return `${wd} ${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
  return `${wd} ${pad(d.getDate())} ${MONTHS[d.getMonth()]}`;
}

function decimal(v) {
  const a = Math.abs(Number(v));
  const r = Math.round(a * 10) / 10;
  const s = Number.isInteger(r) ? String(r) : r.toFixed(1);
  return lang === "vi" ? s.replace(".", ",") : s;
}
function cmS(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  const n = Number(v);
  return `${n > 0.04 ? "+" : n < -0.04 ? "−" : ""}${decimal(n)} cm`;
}
const mmS = (v) => `${decimal(v)} mm`;
const fieldNo = (fid) => String(fid || "").replace(/^F/, "");
function fieldName(fid, inSentence) {
  const n = fieldNo(fid);
  if (lang === "ja") return `区画${n}`;
  if (lang === "vi") return `${inSentence ? "thửa" : "Thửa"} ${n}`;
  return `Field ${n}`;
}
function orderText(rows) {
  const names = rows.map((r) => fieldName(r.fid, true));
  if (lang === "ja") return names.join("、");
  if (names.length < 2) return names.join("");
  const joiner = lang === "vi" ? ", rồi " : ", then ";
  return names.join(joiner);
}
const queued = (plan) => (plan ? plan.rows.filter((r) => r.action === "irrigate").sort((a, b) => (a.queue || 9) - (b.queue || 9)) : []);

function storyLevelColor(v) {
  if (v >= 0) return "var(--water)";
  if (v >= -15) return "var(--water-low)";
  return "var(--bad)";
}

function tubeSvg(level, cls = "") {
  const top = 10, min = -20, H = 100;
  const y = (v) => ((top - Math.max(min, Math.min(top, v))) / (top - min)) * H;
  const lv = Number(level);
  return `<svg class="tube ${cls}" viewBox="0 0 24 ${H}" preserveAspectRatio="none" aria-hidden="true">
    <rect x="4" y="${y(0)}" width="16" height="${H - y(0)}" class="tube-soil"/>
    <rect x="4" y="${y(lv)}" width="16" height="${H - y(lv)}" fill="${storyLevelColor(lv)}" class="tube-water"/>
    <line x1="0" x2="24" y1="${y(0)}" y2="${y(0)}" class="tube-zero"/>
    <line x1="0" x2="24" y1="${y(-15)}" y2="${y(-15)}" class="tube-limit"/>
    <rect x="4" y="0.5" width="16" height="${H - 1}" class="tube-glass"/>
  </svg>`;
}

function ownerLabel(owner) {
  if (!owner || /^Hộ thửa \d$/.test(owner)) return "";
  return nm(owner);
}

function fieldMap(opts = {}) {
  const plan = opts.plan;
  const order = new Map(queued(plan).map((r) => [r.fid, r.queue]));
  const tiles = S.fields.map((f) => {
    const q = order.get(f.fid);
    const owner = ownerLabel(f.owner);
    const focus = opts.focus && opts.focus.includes(f.fid);
    const alert = opts.alert && opts.alert.includes(f.fid);
    return `<div class="plot${focus ? " focus" : ""}${alert ? " alert" : ""}">
      <div class="plot-name"><b>${esc(fieldName(f.fid))}</b>${owner ? `<span>${esc(owner)}</span>` : ""}</div>
      <div class="plot-body">${tubeSvg(f.level)}<span class="plot-val">${esc(cmS(f.level))}</span></div>
      ${q ? `<div class="plot-act"><i>${q}</i>${esc(sx("actWater"))}</div>` : ""}
    </div>`;
  }).join("");
  return `<div class="sv sv-map"><div class="plots">${tiles}</div><p class="sv-note">${esc(sx("gaugeNote"))}</p></div>`;
}

function rainVisual(f) {
  const days = f.days || [];
  const max = Math.max(1, ...days.map((d) => d[1]));
  const bars = days.map(([label, mm, iso]) => `<div class="rbar"><span class="rbar-val">${esc(mmS(mm))}</span><i style="height:${Math.max(6, (mm / max) * 100)}%"></i><span class="rbar-day">${esc(iso ? dayLong(iso) : label)}</span></div>`).join("");
  const field = S.fields.find((x) => x.fid === (f.fid || "F2"));
  return `<div class="sv sv-rain">
    <div class="rain-total"><b>${esc(mmS(f.total_mm))}</b><span>${esc(sx("rainDays"))}</span><div class="rbars">${bars}</div></div>
    <div class="before-after">
      <div class="ba"><span>${esc(sx("beforeRain"))}</span>${tubeSvg(f.before_cm, "lg")}<b>${esc(cmS(f.before_cm))}</b></div>
      <div class="ba-arrow" aria-hidden="true"></div>
      <div class="ba"><span>${esc(sx("afterRain"))}</span>${tubeSvg(f.after_cm, "lg")}<b>${esc(cmS(f.after_cm))}</b></div>
      <div class="ba-name">${esc(fieldName(field ? field.fid : "F2"))}</div>
    </div>
  </div>`;
}

function photoVisual(r) {
  const v = r.vision || {};
  const c = (r.conflicts || [])[0];
  const sources = Object.fromEntries((c && c.sources) || []);
  const photoVal = sources["Gauge photo"] !== undefined ? sources["Gauge photo"] : v.used_cm;
  const sensorVal = sources.Sensor;
  const stale = (v.flags || []).some((x) => (x.code || x) === "STALE_PHOTO");
  const taken = v.captured_at ? sx(stale ? "takenBeforeRain" : "takenOn", { day: dayLong(v.captured_at) }) : "";
  return `<div class="sv sv-photo">
    ${v.image ? `<img class="sv-img" src="/media/${esc(v.image.split("/").pop())}" alt="${esc(sx("photoSays"))}">` : ""}
    <div class="readings">
      <div class="reading bad"><span>${esc(sx("photoSays"))}</span><b>${esc(cmS(photoVal))}</b>${taken ? `<small>${esc(taken)}</small>` : ""}</div>
      ${sensorVal !== undefined ? `<div class="reading water"><span>${esc(sx("sensorSays"))}</span><b>${esc(cmS(sensorVal))}</b></div>` : ""}
    </div>
  </div>`;
}

function remeasureVisual(f) {
  return `<div class="sv sv-compare">
    <div class="cmp old"><span>${esc(sx("wrongPhoto"))}</span><b><s>${esc(cmS(f.old_cm))}</s></b></div>
    <div class="ba-arrow" aria-hidden="true"></div>
    <div class="cmp new">${tubeSvg(f.new_cm, "lg")}<div><span>${esc(sx("secondGauge"))}, ${esc(nm(f.recorder))}</span><b>${esc(cmS(f.new_cm))}</b><small>${esc(fieldName(f.fid))}</small></div></div>
  </div>`;
}

function chatTranslation(vi) {
  const m = (S.chat || []).find((x) => x.vi === vi);
  if (!m || lang === "vi") return "";
  const tr = (m.tl && m.tl[lang]) || (lang === "en" ? m.en : "");
  return tr && tr !== vi ? tr : "";
}

function voiceBubble(who, text, tone = "") {
  const tr = chatTranslation(text);
  return `<div class="say ${tone}"><div class="say-who">${esc(who)}</div><div class="say-text" lang="vi" data-src>“${esc(text)}”</div>${tr ? `<div class="say-tl">${rich(tr)}</div>` : ""}</div>`;
}

function voiceVisual(f, transcript) {
  const field = S.fields.find((x) => x.fid === (f.fid || "F3")) || {};
  return `<div class="sv sv-voice">
    ${voiceBubble(nm(f.recorder || "HTX"), f.transcript || transcript)}
    <div class="ba-arrow" aria-hidden="true"></div>
    <div class="cmp new">${tubeSvg(f.value_cm, "lg")}<div><span>${esc(fieldName(field.fid || "F3"))}, ${esc(nm(f.owner || "Bà Sáu"))}</span><b>${esc(cmS(f.value_cm))}</b></div></div>
  </div>`;
}

function actionCell(r) {
  if (r.action === "irrigate") return `<span class="act water"><i>${r.queue || ""}</i>${esc(sx("actWater"))}</span>`;
  if (r.action === "hold_rain") return `<span class="act">${esc(sx("actRain"))}</span>`;
  return `<span class="act">${esc(sx("actWait"))}</span>`;
}

function soonNote(r) {
  if (r.action !== "irrigate") return "";
  if (r.next_stage_code === "heading") return sx("soonHeading");
  if (r.next_stage_code === "topdress") return sx("soonTopdress");
  return "";
}

function planVisual(plan, opts = {}) {
  if (!plan) return "";
  const q = queued(plan);
  const head = plan.pause_run || !q.length
    ? `<div class="pc-day">${esc(capFirst(dayLong(plan.run_date)))}</div><div class="pc-order">${esc(sx("noRun"))}</div>`
    : `<div class="pc-day">${esc(capFirst(dayLong(plan.run_date)))}</div><div class="pc-order">${q.map((r) => `<span><i>${r.queue}</i>${esc(fieldName(r.fid))}</span>`).join(`<em aria-hidden="true"></em>`)}</div>`;
  const moved = opts.movedFrom ? `<div class="pc-was">${esc(sx("movedFrom", { day: dayLong(opts.movedFrom) }))}</div>` : "";
  const others = plan.following_date ? `<p class="pc-others">${esc(sx("othersWait", { day: dayLong(plan.following_date) }))}</p>` : "";
  const stamp = plan.status === "approved" ? `<div class="pc-stamp ok">${esc(sx("stampApproved"))}</div>` : plan.status === "rejected" ? `<div class="pc-stamp bad">${esc(sx("stampRejected"))}</div>` : "";
  const rows = plan.rows.map((r) => {
    const note = soonNote(r);
    return `<li class="${r.action === "irrigate" ? "on" : ""}"><span class="pr-name"><b>${esc(fieldName(r.fid))}</b>${note ? `<small>${esc(note)}</small>` : ""}</span>${tubeSvg(r.level_now, "sm")}<span class="pr-val">${esc(cmS(r.level_now))}</span>${actionCell(r)}</li>`;
  }).join("");
  return `<div class="sv sv-plan"><div class="pcard">${moved}${head}${others}${stamp}</div><ul class="plist">${rows}</ul></div>`;
}

function lastAgentReplyAfter(text) {
  const chat = S.chat || [];
  let idx = -1;
  chat.forEach((m, i) => { if (m.vi === text && m.role !== "agent") idx = i; });
  if (idx < 0) return null;
  return chat.slice(idx + 1).find((m) => m.role === "agent") || null;
}

function agentBubble(m) {
  if (!m) return "";
  const tr = lang === "vi" ? "" : (m.tl && m.tl[lang]) || (lang === "en" ? m.en : "");
  return `<div class="say agent"><div class="say-who">${esc(nm("RiceBridge agent"))}</div><div class="say-text" lang="vi" data-src>${esc(m.vi)}</div>${tr && tr !== m.vi ? `<div class="say-tl">${rich(tr)}</div>` : ""}</div>`;
}

function liveStory(cur) {
  const r = cur.result;
  const v = r.verdict || {};
  const p = r.parse || {};
  const text = cur.event.transcript;
  const field = p.field ? fieldName(p.field, true) : fieldName("F2", true);
  const titles = {
    recorded: sx("liveRecorded", { field, cm: cmS(p.value_cm) }),
    verified: sx("liveVerified", { field, cm: cmS(p.value_cm) }),
    held: sx("liveHeld", { field }),
    refused: sx("liveRefused"),
    clarify: sx("liveClarify"),
  };
  const title = capFirst(titles[v.kind] || sx("liveNotReading"));
  const farmer = voiceBubble(nm(cur.event.sender), text, v.kind === "refused" ? "bad" : "");
  let outcome = "";
  if (v.kind === "refused") {
    outcome = `<div class="refusal"><b>${esc(sx("refusedStamp"))}</b><p>${esc(sx("refusedNote"))}</p></div>${agentBubble(lastAgentReplyAfter(text))}`;
  } else if (r.asks && r.asks[0]) {
    const a = r.asks[0];
    const tr = lang === "vi" ? "" : L(a.message_t);
    outcome = `<div class="say agent"><div class="say-who">${esc(nm("RiceBridge agent"))} → ${esc(nm(a.person))}</div><div class="say-text" lang="vi" data-src>${esc(a.message_vi)}</div>${tr ? `<div class="say-tl">${rich(tr)}</div>` : ""}</div>`;
  } else if ((r.diff && r.diff.length) || r.state_change) {
    outcome = planVisual(S.plan);
  } else {
    outcome = agentBubble(lastAgentReplyAfter(text));
  }
  const changed = (r.diff && r.diff.length) || r.state_change;
  const line = S.plan && S.plan.status === "proposed" ? (changed ? sx("planChanged") : sx("planWaiting", { day: dayLong(S.plan.run_date) })) : sx("planSame");
  const wide = outcome.includes("sv-plan");
  return { title: esc(title), visual: `<div class="sv sv-live${wide ? " wide" : ""}"><div class="live-in">${farmer}</div>${wide ? "" : `<div class="ba-arrow" aria-hidden="true"></div>`}<div class="live-out">${outcome}</div></div>`, line: esc(line) };
}

function storyScene() {
  const sc = sceneOf();
  const plan = S.plan;
  const last = S.step >= S.total_steps - 1;
  if (sc.kind === "intro") {
    return {
      title: esc(sx("introTitle")),
      visual: `<div class="sv sv-chart tile chartpanel">${scene(true)}<div class="chart-legend">${storyChartLegend()}</div><div class="wxbox" data-bare="1"></div></div>`,
      line: esc(sx("introLine")),
    };
  }
  if (sc.kind === "live") return liveStory(sc.cur);
  const r = sc.cur.result;
  const f = r.focal || {};
  if (last && plan && plan.status === "approved") {
    const q = queued(plan);
    const title = plan.pause_run || !q.length ? sx("approvedPauseTitle", { day: dayLong(plan.run_date) }) : sx("approvedTitle", { day: capFirst(dayLong(plan.run_date)), order: orderText(q) });
    return { title: esc(title), visual: planVisual(plan), line: esc(sx("approvedLine")) };
  }
  if (last && plan && plan.status === "rejected") {
    return { title: esc(sx("rejectedTitle")), visual: planVisual(plan), line: esc(sx("rejectedLine")) };
  }
  const proposal = () => {
    if (!plan) return "";
    const q = queued(plan);
    return plan.pause_run || !q.length ? sx("proposePause", { day: dayLong(plan.run_date) }) : sx("proposeOrder", { order: orderText(q) });
  };
  if (sc.kind === "start") {
    const q = queued(plan).map((x) => x.fid);
    return { title: esc(sx("startTitle", { day: dayLong(f.run_date || (plan && plan.run_date)) })), visual: fieldMap({ plan, focus: q }), line: esc(proposal()) };
  }
  if (sc.kind === "rain") return { title: esc(sx("rainTitle", { mm: mmS(f.total_mm) })), visual: rainVisual(f), line: esc(proposal()) };
  if (sc.kind === "photo") return { title: esc(capFirst(sx("photoTitle", { field: fieldName(f.fid || "F2", true) }))), visual: photoVisual(r), line: esc(sx("photoLine")) };
  if (sc.kind === "remeasure") return { title: esc(sx("remeasureTitle", { who: nm(f.recorder), field: fieldName(f.fid || "F2", true), cm: cmS(f.new_cm) })), visual: remeasureVisual(f), line: esc(sx("remeasureLine")) };
  if (sc.kind === "voice") return { title: esc(sx("voiceTitle")), visual: voiceVisual(f, sc.cur.event.transcript), line: sxq("voiceLine", null, "ba phân") };
  if (sc.kind === "pump_change") {
    return { title: esc(sx("pumpTitle", { day: dayLong(f.to_date) })), visual: planVisual(plan, { movedFrom: f.from_date }), line: esc(plan && plan.status === "proposed" ? sx("needsApproval") : proposal()) };
  }
  return { title: esc(L(sc.cur.event.title_t) || ""), visual: fieldMap({ plan }), line: esc(proposal()) };
}

function storyChartLegend() {
  return `<span class="lg-rain"><i></i>${esc(pick(RAIN_LABEL))} (${esc(pick(PER_DAY))})</span><span class="lg-et0"><i></i>${esc(pick(ET0_LABEL))} (${esc(pick(PER_DAY))}, ${esc(pick(ET0_AXIS))})</span>`;
}

function storyCanDecide() {
  const plan = S.plan;
  return !!plan && plan.status === "proposed" && S.step >= S.total_steps - 1;
}

function renderStory(animate) {
  const s = storyScene();
  const box = $("#story");
  box.classList.toggle("anim", animate);
  $("#storyTitle").innerHTML = s.title;
  $("#storyMain").innerHTML = s.visual;
  const line = $("#storyLine");
  line.dataset.line = s.line;
  line.dataset.busy = "";
  line.innerHTML = s.line;
  line.classList.remove("busy");
  const canDecide = storyCanDecide();
  const job = isBusy();
  $("#storyDecide").innerHTML = canDecide
    ? `<button class="dbtn no sbtn ghost" id="reject" ${job ? "disabled" : ""}>${esc(sx("btnReject"))}</button><button class="dbtn yes sbtn primary" id="approve" ${job ? "disabled" : ""}>${esc(sx("btnApprove"))}</button>`
    : "";
  const ap = $("#approve"), rj = $("#reject");
  if (ap) ap.onclick = (ev) => { ev.currentTarget.blur(); decide("approve"); };
  if (rj) rj.onclick = (ev) => { ev.currentTarget.blur(); decide("reject"); };
  drawCharts();
}

function storyBusyText() {
  const job = busyJob();
  if (job) {
    if (job.kind === "message") return sx("busyMessage");
    if (["next", "goto"].includes(job.kind)) return sx("busyPlan");
    if (job.kind === "decision") return sx("busyDecision");
    return sx("busyGeneric");
  }
  if (sideJobs().some((s) => s.kind === "brief")) return sx("busyWrite");
  return "";
}

function renderStoryBusy() {
  const line = $("#storyLine");
  if (!line) return;
  const text = storyBusyText();
  if (line.dataset.busy === text) return;
  line.dataset.busy = text;
  line.classList.toggle("busy", !!text);
  line.innerHTML = text ? `<span class="busytext">${esc(text)}</span><span class="busybar" aria-hidden="true"></span>` : line.dataset.line || "";
}

function storyMapCarbon() {
  const comp = Object.fromEntries(S.completeness.map((c) => [c.fid, c]));
  let svg = `<svg class="cmap" viewBox="0 0 600 372" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(sx("parcelMap"))}">`;
  svg += `<rect x="30" y="34" width="540" height="22" rx="4" class="cmap-canal"/><text x="300" y="50" text-anchor="middle" class="cmap-canal-t">${esc(sx("canal"))}</text>`;
  svg += `<rect x="2" y="26" width="34" height="38" rx="5" class="cmap-pump"/><text x="19" y="49" text-anchor="middle" class="cmap-pump-t">${esc(sx("pump"))}</text>`;
  S.fields.forEach((f) => {
    const c = comp[f.fid] || {};
    const ok = c.score === 100;
    const [lx, ly] = f.label_xy;
    const owner = ownerLabel(f.owner);
    svg += `<polygon points="${f.polygon}" class="cmap-plot ${ok ? "ok" : "miss"}"/>`;
    svg += `<text x="${lx}" y="${ly - 14}" text-anchor="middle" class="cmap-name">${esc(fieldName(f.fid))}${owner ? ` · ${esc(owner)}` : ""}</text>`;
    svg += `<text x="${lx}" y="${ly + 16}" text-anchor="middle" class="cmap-status ${ok ? "ok" : "miss"}">${esc(ok ? sx("complete") : sx("incomplete"))}</text>`;
  });
  svg += `</svg>`;
  const missing = S.completeness.filter((c) => c.score !== 100).map((c) => {
    const first = ((c.missing_t || []).map(L).filter(Boolean)[0]) || "";
    return `<li><b>${esc(fieldName(c.fid))}</b><span>${rich(first)}</span></li>`;
  }).join("");
  return `${svg}${missing ? `<ul class="cmiss">${missing}</ul>` : ""}`;
}

function renderStoryCarbon(animate) {
  const box = $("#view-carbon");
  box.classList.toggle("anim", animate);
  let verifyHtml = "";
  if (verifyResult) {
    verifyHtml = verifyResult.ok
      ? `<p class="verify ok" id="verify-result">${esc(sx("verifiedOk", { n: verifyResult.checked }))}</p>`
      : `<p class="verify bad" id="verify-result">${esc(sx("verifiedBad", { n: verifyResult.broken_at }))}</p>`;
  }
  box.innerHTML = `<section class="cstory">
    <div class="cs-left">
      <div class="cs-big" id="complete">${S.complete_fields}<span>/6</span></div>
      <h2 class="cs-title">${esc(sx("carbonTitle", { n: S.complete_fields }))}</h2>
      <p class="cs-line">${esc(sx("carbonLine"))}</p>
      <div class="cs-actions"><a class="sbtn primary" href="/api/evidence.csv" id="export" download>${esc(sx("exportLog"))}</a><button class="sbtn ghost" id="verify" type="button">${esc(sx("verifyLog"))}</button></div>
      ${verifyHtml}
    </div>
    <div class="cs-right"><div class="cs-maphead">${esc(sx("parcelMap"))}</div>${storyMapCarbon()}</div>
  </section>`;
  $("#verify").onclick = (ev) => { ev.currentTarget.blur(); verify(false); };
}
