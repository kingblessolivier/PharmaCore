"""GS1 2D DataMatrix parsing, EPC identity, and EPCIS 2.0 event export.

A regulated medicine pack carries one 2D code holding four things at once — GTIN
(AI 01), batch (10), expiry (17) and serial (21). Everything downstream (receipt,
QC, dispatch, dispense, recall) depends on reading that code *correctly*, so the
parser here follows the GS1 General Specifications properly rather than splitting
on separators and hoping:

* fixed-length AIs consume exactly their defined length, with no separator;
* variable-length AIs run to the next **FNC1** (GS, ``\\x1d``) or end of string;
* symbology identifiers (``]d2``, ``]C1``, ``]Q3``, ``]e0``) are stripped;
* the human-readable bracketed form ``(01)…(17)…`` and **GS1 Digital Link** URIs
  are both accepted, because scanners and phone cameras emit them;
* GTIN/SSCC check digits are verified (mod-10) — a mis-scan is rejected, not stored.
"""

from __future__ import annotations

import calendar
import re
import uuid
from datetime import date, datetime
from typing import Any

from django.utils import timezone

GROUP_SEPARATOR = "\x1d"

# Symbology identifiers a scanner may prefix. ]d2 = DataMatrix/GS1, ]C1 = GS1-128,
# ]e0 = GS1 DataBar, ]Q3 = GS1 QR Code.
_SYMBOLOGY_IDS = ("]d2", "]C1", "]e0", "]Q3", "]d1", "]C0")


class GS1ParseError(ValueError):
    """Raised when a scanned string is not a well-formed GS1 element string."""


# ai -> (data length or None for variable, max length, field name, kind)
# Only the AIs a pharmaceutical supply chain actually meets are listed; anything
# else is captured verbatim under ``other`` so nothing scanned is silently lost.
_AI_TABLE: dict[str, tuple[int | None, int, str, str]] = {
    "00": (18, 18, "sscc", "id"),
    "01": (14, 14, "gtin", "id"),
    "02": (14, 14, "contained_gtin", "id"),
    "10": (None, 20, "batch_number", "text"),
    "11": (6, 6, "production_date", "date"),
    "12": (6, 6, "due_date", "date"),
    "13": (6, 6, "packaging_date", "date"),
    "15": (6, 6, "best_before_date", "date"),
    "16": (6, 6, "sell_by_date", "date"),
    "17": (6, 6, "expiry_date", "date"),
    "20": (2, 2, "variant", "text"),
    "21": (None, 20, "serial", "text"),
    "22": (None, 20, "consumer_product_variant", "text"),
    "30": (None, 8, "count", "int"),
    "37": (None, 8, "contained_count", "int"),
    "240": (None, 30, "additional_product_id", "text"),
    "241": (None, 30, "customer_part_number", "text"),
    "710": (None, 20, "nhrn_de", "text"),
    "711": (None, 20, "nhrn_fr", "text"),
    "712": (None, 20, "nhrn_es", "text"),
    "713": (None, 20, "nhrn_bg", "text"),
    "714": (None, 20, "nhrn_pt", "text"),
    "8018": (18, 18, "srin", "text"),
    "8020": (None, 25, "payment_reference", "text"),
}

# AIs whose *identifier* is longer than two digits. Resolution is longest-first.
_AI_LENGTHS = sorted({len(k) for k in _AI_TABLE if k.isdigit()}, reverse=True)


def _mod10_check_digit(digits: str) -> str:
    """GS1 mod-10 check digit over the payload (excluding the check digit)."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return str((10 - (total % 10)) % 10)


def validate_gtin(gtin: str) -> bool:
    """True when a GTIN-8/12/13/14 carries a correct mod-10 check digit."""
    if not gtin.isdigit() or len(gtin) not in (8, 12, 13, 14):
        return False
    return _mod10_check_digit(gtin[:-1]) == gtin[-1]


def validate_sscc(sscc: str) -> bool:
    if not sscc.isdigit() or len(sscc) != 18:
        return False
    return _mod10_check_digit(sscc[:-1]) == sscc[-1]


def parse_gs1_date(value: str) -> date:
    """Parse a GS1 ``YYMMDD`` date.

    Two GS1 rules matter. ``DD == 00`` means "end of that month" (an expiry
    printed as 2612 00 expires on 31 December 2026 — treating it as day 0 would
    crash, and treating it as the 1st would expire the stock a month early). The
    century comes from the ±50-year pivot in the General Specifications.
    """
    if len(value) != 6 or not value.isdigit():
        raise GS1ParseError(f"Invalid GS1 date '{value}' — expected YYMMDD.")
    yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:6])
    if not 1 <= mm <= 12:
        raise GS1ParseError(f"Invalid GS1 date '{value}' — month {mm:02d} out of range.")

    current = timezone.localdate().year
    year = current - (current % 100) + yy
    if year - current >= 51:
        year -= 100
    elif year - current <= -50:
        year += 100

    if dd == 0:
        # "Day 00" = last day of that month.
        last_day = calendar.monthrange(year, mm)[1]
        return date(year, mm, last_day)
    try:
        return date(year, mm, dd)
    except ValueError as exc:
        raise GS1ParseError(f"Invalid GS1 date '{value}'.") from exc


def _strip_prefixes(raw: str) -> str:
    data = raw.strip()
    for sym in _SYMBOLOGY_IDS:
        if data.startswith(sym):
            data = data[len(sym) :]
            break
    # A leading FNC1 carries no data.
    return data.lstrip(GROUP_SEPARATOR)


def _parse_bracketed(data: str) -> dict[str, str]:
    """Human-readable form: ``(01)09506000134376(17)261231(10)LOT(21)SN``."""
    pairs = re.findall(r"\((\d{2,4})\)([^(]*)", data)
    if not pairs:
        raise GS1ParseError("No (AI) groups found in bracketed element string.")
    return {ai: value.strip() for ai, value in pairs}


def _parse_digital_link(data: str) -> dict[str, str]:
    """GS1 Digital Link: ``https://id.gs1.org/01/095…/10/LOT/21/SN?17=261231``."""
    from urllib.parse import parse_qsl, urlsplit

    parts = urlsplit(data)
    segments = [s for s in parts.path.split("/") if s]
    raw: dict[str, str] = {}
    for i in range(0, len(segments) - 1, 2):
        key, value = segments[i], segments[i + 1]
        if key.isdigit():
            raw[key] = value
    for key, value in parse_qsl(parts.query):
        if key.isdigit():
            raw[key] = value
    if not raw:
        raise GS1ParseError("No GS1 key/value pairs found in the Digital Link URI.")
    return raw


def _parse_element_string(data: str) -> dict[str, str]:
    """The real thing: concatenated AI + value, FNC1-terminated where variable."""
    raw: dict[str, str] = {}
    pos, length = 0, len(data)
    while pos < length:
        if data[pos] == GROUP_SEPARATOR:
            pos += 1
            continue
        ai = ""
        for ai_len in _AI_LENGTHS:
            candidate = data[pos : pos + ai_len]
            if candidate in _AI_TABLE:
                ai = candidate
                break
        if not ai:
            # Unknown AI: assume the 2-digit form and read to the next FNC1 so the
            # rest of the code still parses instead of the whole scan being lost.
            ai = data[pos : pos + 2]
            if not ai.isdigit():
                raise GS1ParseError(
                    f"Unrecognised application identifier at position {pos}: '{data[pos:pos + 4]}'."
                )
            pos += 2
            end = data.find(GROUP_SEPARATOR, pos)
            end = length if end == -1 else end
            raw[ai] = data[pos:end]
            pos = end
            continue

        pos += len(ai)
        fixed, _max_len, _name, _kind = _AI_TABLE[ai]
        if fixed is not None:
            value = data[pos : pos + fixed]
            if len(value) < fixed:
                raise GS1ParseError(f"AI ({ai}) needs {fixed} characters, got {len(value)}.")
            pos += fixed
            # A fixed-length field may still be followed by a redundant FNC1.
            if pos < length and data[pos] == GROUP_SEPARATOR:
                pos += 1
        else:
            end = data.find(GROUP_SEPARATOR, pos)
            end = length if end == -1 else end
            value = data[pos:end]
            pos = end + 1 if end < length else length
        raw[ai] = value
    if not raw:
        raise GS1ParseError("Empty GS1 element string.")
    return raw


def parse_gs1(raw: str, *, validate_check_digits: bool = True) -> dict[str, Any]:
    """Parse any of the three shapes a scanner emits into named fields.

    Returns the decoded fields plus ``ais`` (the raw AI→value map), ``warnings``
    for anything suspicious but survivable, and the derived EPC identity.
    """
    if not raw or not raw.strip():
        raise GS1ParseError("Nothing to parse — the scan was empty.")

    data = _strip_prefixes(raw)
    if data.startswith("("):
        ais = _parse_bracketed(data)
    elif data.lower().startswith(("http://", "https://")):
        ais = _parse_digital_link(data)
    else:
        ais = _parse_element_string(data)

    out: dict[str, Any] = {"ais": ais, "other": {}, "warnings": []}
    for ai, value in ais.items():
        spec = _AI_TABLE.get(ai)
        if spec is None:
            out["other"][ai] = value
            continue
        _fixed, max_len, name, kind = spec
        if len(value) > max_len:
            out["warnings"].append(f"AI ({ai}) is longer than the {max_len}-character maximum.")
        if kind == "date":
            try:
                out[name] = parse_gs1_date(value).isoformat()
            except GS1ParseError as exc:
                out["warnings"].append(str(exc))
        elif kind == "int":
            out[name] = int(value) if value.isdigit() else value
        else:
            out[name] = value

    gtin = out.get("gtin", "")
    if gtin:
        # Digital Link may carry a GTIN-13/12; pad to the 14-digit canonical form.
        if len(gtin) < 14 and gtin.isdigit():
            gtin = gtin.zfill(14)
            out["gtin"] = gtin
        if validate_check_digits and not validate_gtin(gtin):
            raise GS1ParseError(f"GTIN '{gtin}' fails its mod-10 check digit — re-scan the code.")
    sscc = out.get("sscc", "")
    if sscc and validate_check_digits and not validate_sscc(sscc):
        raise GS1ParseError(f"SSCC '{sscc}' fails its mod-10 check digit — re-scan the code.")

    out["epc"] = build_epc(gtin=gtin, serial=out.get("serial", ""), sscc=sscc)
    out["digital_link"] = build_digital_link(
        gtin=gtin,
        serial=out.get("serial", ""),
        batch=out.get("batch_number", ""),
        expiry=ais.get("17", ""),
    )
    out["is_serialised"] = bool(out.get("serial")) or bool(sscc)
    out["level"] = "PALLET" if sscc and not gtin else ("EACH" if gtin else "")
    return out


def build_epc(*, gtin: str = "", serial: str = "", sscc: str = "", gcp_length: int = 7) -> str:
    """Canonical EPC URI for an SGTIN or SSCC.

    Splitting a GTIN into company prefix + item reference needs the GS1 Company
    Prefix length, which is a property of the brand owner rather than of the code.
    ``gcp_length`` defaults to 7 (the common GS1 Rwanda / GS1 global allocation);
    pass the real length when the trading partner publishes it.
    """
    if sscc and len(sscc) == 18:
        extension, rest = sscc[0], sscc[1:-1]
        prefix, serial_ref = rest[:gcp_length], rest[gcp_length:]
        return f"urn:epc:id:sscc:{prefix}.{extension}{serial_ref}"
    if gtin and serial and len(gtin) == 14:
        indicator, body = gtin[0], gtin[1:-1]
        prefix, item_ref = body[:gcp_length], body[gcp_length:]
        return f"urn:epc:id:sgtin:{prefix}.{indicator}{item_ref}.{serial}"
    if gtin and len(gtin) == 14:
        return f"urn:epc:idpat:sgtin:{gtin}.*"
    return ""


def build_digital_link(
    *, gtin: str = "", serial: str = "", batch: str = "", expiry: str = ""
) -> str:
    """GS1 Digital Link URI — the resolver-friendly form of the same identity."""
    if not gtin:
        return ""
    url = f"https://id.gs1.org/01/{gtin}"
    if batch:
        url += f"/10/{batch}"
    if serial:
        url += f"/21/{serial}"
    if expiry:
        url += f"?17={expiry}"
    return url


def encode_element_string(
    *, gtin: str = "", expiry: date | None = None, batch: str = "", serial: str = ""
) -> str:
    """Build the ``(01)…(17)…(10)…(21)…`` string a label printer needs.

    Fixed-length AIs are placed first so no FNC1 separators are needed for them —
    the compact ordering GS1 recommends for a healthcare DataMatrix.
    """
    parts: list[str] = []
    if gtin:
        parts.append(f"(01){gtin.zfill(14)}")
    if expiry:
        parts.append(f"(17){expiry.strftime('%y%m%d')}")
    if batch:
        parts.append(f"(10){batch}")
    if serial:
        parts.append(f"(21){serial}")
    return "".join(parts)


# --- EPCIS 2.0 -------------------------------------------------------------

_CBV_BIZ_STEP = "https://ref.gs1.org/cbv/BizStep-"
_CBV_DISPOSITION = "https://ref.gs1.org/cbv/Disp-"
_EPCIS_CONTEXT = "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"


def new_event_id() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


def _tz_offset(moment: datetime) -> str:
    offset = moment.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def event_to_epcis_json(event: Any) -> dict[str, Any]:
    """Render one stored :class:`EpcisEvent` as an EPCIS 2.0 JSON-LD event."""
    type_map = {
        "OBJECT": "ObjectEvent",
        "AGGREGATION": "AggregationEvent",
        "TRANSACTION": "TransactionEvent",
        "TRANSFORMATION": "TransformationEvent",
    }
    doc: dict[str, Any] = {
        "type": type_map.get(event.event_type, "ObjectEvent"),
        "eventID": event.event_id,
        "eventTime": event.event_time.isoformat(),
        "eventTimeZoneOffset": _tz_offset(event.event_time),
        "recordTime": event.record_time.isoformat() if event.record_time else None,
        "action": event.action,
    }
    if event.event_type == "AGGREGATION":
        doc["parentID"] = event.parent_epc
        doc["childEPCs"] = list(event.epc_list or [])
    else:
        doc["epcList"] = list(event.epc_list or [])
    if event.biz_step:
        doc["bizStep"] = f"{_CBV_BIZ_STEP}{event.biz_step}"
    if event.disposition:
        doc["disposition"] = f"{_CBV_DISPOSITION}{event.disposition}"
    if event.read_point:
        doc["readPoint"] = {"id": event.read_point}
    if event.biz_location:
        doc["bizLocation"] = {"id": event.biz_location}
    if event.quantity_list:
        doc["quantityList"] = list(event.quantity_list)
    if event.reference_type and event.reference_id:
        doc["bizTransactionList"] = [
            {"type": event.reference_type, "bizTransaction": event.reference_id}
        ]
    return {k: v for k, v in doc.items() if v not in (None, [], "")}


def build_epcis_document(events: Any, *, sender: str = "") -> dict[str, Any]:
    """Wrap events in an EPCIS 2.0 ``EPCISDocument`` ready to hand to a partner."""
    from django.utils import timezone as dj_timezone

    return {
        "@context": [_EPCIS_CONTEXT],
        "type": "EPCISDocument",
        "schemaVersion": "2.0",
        "creationDate": dj_timezone.now().isoformat(),
        "sender": sender,
        "epcisBody": {"eventList": [event_to_epcis_json(e) for e in events]},
    }
