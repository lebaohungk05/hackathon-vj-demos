from dataclasses import dataclass, field


PERSONA = {
    "description": "Mock applicant used in both procedures. All data is fake.",
    "full_name": "Nguyễn Văn An",
    "full_name_katakana": "グエン・ヴァン・アン",
    "date_of_birth_vn": "12/03/1985",
    "date_of_birth_jp": "1985年3月12日",
    "citizen_id_cccd": "001085012345",
    "email": "an.nguyen@example.com",
    "phone_vn": "0912345678",
    "phone_jp": "090-0000-0000",
    "permanent_registered_address_vn": "12 Phố Huế, Hà Nội",
    "current_address_jp": "みどり市中央1-2-3（架空）",
    "postal_code_jp": "123-4567",
    "nationality": "Vietnam",
    "nationality_ja": "ベトナム",
}


@dataclass
class Procedure:
    key: str
    country: str
    title: str
    title_en: str
    lang: str
    steps: list
    step_names: list
    goal: str
    standard: str
    rule_data: list = field(default_factory=list)


VN = Procedure(
    key="vn",
    country="Vietnam",
    title="Cấp Phiếu lý lịch tư pháp",
    title_en="Criminal-record certificate (Phiếu lý lịch tư pháp)",
    lang="vi-VN",
    steps=["step1.html", "step2.html", "step3.html", "step4.html"],
    step_names=["Người yêu cầu", "Liên hệ", "Mục đích", "Xác nhận"],
    goal="Reach the Confirmation step (Xác nhận) and stop before the submit button",
    standard="TT 21/2023 (WCAG 2.x)",
    rule_data=[
        ("ho va ten", PERSONA["full_name"]),
        ("ngay sinh", PERSONA["date_of_birth_vn"]),
        ("cccd", PERSONA["citizen_id_cccd"]),
        ("email", PERSONA["email"]),
        ("dien thoai", PERSONA["phone_vn"]),
        ("dia chi", PERSONA["permanent_registered_address_vn"]),
    ],
)

JP = Procedure(
    key="jp",
    country="Japan",
    title="住民票の写し交付申請（模擬）",
    title_en="Certificate of residence copy request (住民票の写し交付申請), mock municipality",
    lang="ja-JP",
    steps=["step1.html", "step2.html", "step3.html"],
    step_names=["申請者", "請求内容", "確認"],
    goal="Reach the confirmation step (確認) and stop before the 申請する button",
    standard="JIS X 8341-3:2016",
    rule_data=[
        ("氏名", PERSONA["full_name_katakana"]),
        ("生年月日", PERSONA["date_of_birth_jp"]),
        ("住所", PERSONA["current_address_jp"]),
        ("郵便番号", PERSONA["postal_code_jp"]),
        ("電話", PERSONA["phone_jp"]),
    ],
)

PROCEDURES = {"vn": VN, "jp": JP}
