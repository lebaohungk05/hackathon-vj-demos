from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .i18n import tr
from .llm.interpreter import instruction_hits
from .sim.policies import SENSOR_PHOTO_CONFLICT_CM
from .sim.scenario import BUND_CM

ACCEPT_CONFIDENCE = 0.75
PARSER_AGREEMENT_CM = 0.5
GAUGE_FLOOR_CM = -40.0

REFUSED = "refused"
NOT_READING = "not_reading"
CLARIFY = "clarify"
ACCEPTED = "accepted"
SUSPICIOUS = "suspicious"
BLOCKING_KINDS = (REFUSED, NOT_READING, CLARIFY)


def fmt_cm(value: float) -> str:
    return f"{value:+.1f} cm".replace("-", "−")


@dataclass(frozen=True)
class Verdict:
    kind: str
    check: str
    text: str | None = None
    text_t: dict | None = None
    ask_again: bool = False
    hits: tuple[str, ...] = ()
    gap_cm: float | None = None

    @property
    def blocked(self) -> bool:
        return self.kind in BLOCKING_KINDS


def check_reading(text: str | None, parsed: Mapping[str, Any], rule: Mapping[str, Any] | None = None,
                  model_level: float | None = None, hits: tuple[str, ...] | list[str] | None = None) -> Verdict:
    hits = tuple(instruction_hits(text) if hits is None and text else hits or ())
    fid, value, conf = parsed.get("field"), parsed.get("value_cm"), parsed.get("confidence", 0)
    rule_value = (rule or {}).get("value_cm")
    if hits:
        quoted = ", ".join(f"“{h}”" for h in hits)
        return Verdict(REFUSED, "instructions", f"message gives instructions to the agent ({', '.join(hits)}): nothing recorded; only the HTX approves plans",
                       tr("v.refused", hits=quoted), hits=hits)
    if parsed.get("intent") != "water_level" or value is None:
        return Verdict(NOT_READING, "reading", "not a water-level reading: nothing recorded, no plan change", tr("v.not_reading"))
    if fid is None:
        return Verdict(CLARIFY, "reading", "field unknown: ask which field", tr("v.no_field"))
    if not GAUGE_FLOOR_CM <= value <= BUND_CM:
        return Verdict(CLARIFY, "range",
                       f"{fmt_cm(value)} is outside the physical range ({fmt_cm(GAUGE_FLOOR_CM)} to {fmt_cm(BUND_CM)}, bund height): not recorded; ask again",
                       tr("v.range", v=fmt_cm(value), lo=fmt_cm(GAUGE_FLOOR_CM), hi=fmt_cm(BUND_CM)), ask_again=True)
    if rule_value is not None and abs(rule_value - value) > PARSER_AGREEMENT_CM:
        return Verdict(CLARIFY, "parser_agreement", f"LLM {fmt_cm(value)} and rule parser {fmt_cm(rule_value)} disagree: ask again",
                       tr("v.disagree", a=fmt_cm(value), b=fmt_cm(rule_value)), ask_again=True)
    if conf < ACCEPT_CONFIDENCE:
        return Verdict(CLARIFY, "confidence", f"confidence {conf:.2f} < {ACCEPT_CONFIDENCE}: estimate not recorded as evidence; ask for the gauge number",
                       tr("v.lowconf", c=f"{conf:.2f}", t=ACCEPT_CONFIDENCE))
    if model_level is None:
        return Verdict(ACCEPTED, "passed")
    gap = abs(value - model_level)
    return Verdict(SUSPICIOUS if gap > SENSOR_PHOTO_CONFLICT_CM else ACCEPTED, "water_balance", gap_cm=gap)
