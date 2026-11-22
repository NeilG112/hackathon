"""Bid & Risk Assistant — Streamlit UI. Task 007.

    streamlit run app.py

> It reads a construction tender file, finds the line items that will cost the
> contractor money, and writes the clarification letter he'd otherwise spend
> four hours on.

Lead with that sentence. No vocabulary lesson, no file extensions.

Wired: upload -> parse -> item table, trade groups, transparent bottom-up
calculation, risk/logic findings, and Bieterfragen export. Optional AI checks
are controlled separately from deterministic rules.

Fallbacks, in order: live parse -> `data/golden/` fixture -> an honest
"format not supported" with the sample loaded on a button. Degrade visibly
rather than fabricating output.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import traceback
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

from core import (angebotstexte, classify, clusters, constants, deep_logic,
                  exporter, parser_pdf,
                  domain, facts,
                  kalkulation, logic, objects, parser_gaeb90, parser_x83, pricer,
                  risk_engine, session_store, stammdaten, vergabe)
from views import vergabe as vergabe_view

SAMPLE = constants.REVEAL["blank_boq"]
PAGES = ("Tender", "Gruppen & Angebot", "Vergabe", "Logik", "Heikle Positionen")
# These caches live in st.session_state: switching pages reuses results, while
# a new browser session starts with a clean LV.
HYBRID_ANALYSIS_CACHE_VERSION = "item-rfi-v1"

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
PDF_SUFFIXES = (".pdf",)
GAEB90_SUFFIXES = (".d83", ".d81", ".d84", ".d86")

_SEVERITY_LABELS = {
    "high": "hoch",
    "medium": "mittel",
    "low": "niedrig",
}


def _severity_label(value: str) -> str:
    """Translate internal severity values for German UI display."""
    return _SEVERITY_LABELS.get(value.lower(), value)


st.set_page_config(
    page_title="Bid & Risk Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- parsing ---------------------------------------------------------------

def _project_path(path: str) -> str:
    """Resolve project-relative resources regardless of the launch directory."""
    if os.path.isabs(path):
        return path
    return os.path.join(constants.PROJECT_ROOT, path)


def parse_path(path: str):
    """Parse by format. Returns (items, remarks). Raises on unknown format."""
    path = _project_path(path)
    suffix = os.path.splitext(path)[1].lower()
    if suffix in XML_SUFFIXES:
        return parser_x83.parse(path), parser_x83.parse_remarks(path)
    if suffix in GAEB90_SUFFIXES:
        return parser_gaeb90.parse(path), []
    if suffix in PDF_SUFFIXES:
        # A PDF is a picture of a table, so this is recovery rather than
        # reading. parse_with_stats reports the yield and the UI shows it —
        # a tender where only a third of the positions came through must not
        # look like a clean import.
        items, stats = parser_pdf.parse_with_stats(path)
        confidence = parser_pdf.confidence(items, stats)
        st.session_state["pdf_confidence"] = confidence
        return items, []
    raise ValueError(f"unsupported format: {suffix or path}")


def load_from_disk(path: str):
    items, remarks = parse_path(path)
    return [i.as_dict() for i in items], remarks


def load_from_upload(name: str, payload: bytes):
    """Parse uploaded bytes."""
    suffix = os.path.splitext(name)[1] or ".x83"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        temp = handle.name
    try:
        items, remarks = parse_path(temp)
        return [i.as_dict() for i in items], remarks
    finally:
        os.unlink(temp)


def load_reference():
    return pricer.load_reference_prices()


def rehydrate(dicts: list[dict]):
    from core.models import NormalizedItem
    return [NormalizedItem.from_dict(d) for d in dicts]


def lv_analysis_session_key(
    item_dicts: list[dict],
    remarks: list[str],
    calculated_payload: list[dict],
    priced_payload: list[dict],
    use_jev: bool,
    model_signature: str,
) -> str:
    """Stable session key for one LV's current analysis inputs."""
    payload = {
        "items": item_dicts,
        "remarks": remarks,
        "calculated": calculated_payload,
        "priced": priced_payload,
        "use_jev": use_jev,
        "model_signature": model_signature,
        "rules_version": logic.RULES_VERSION,
        "analysis_version": HYBRID_ANALYSIS_CACHE_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def analyze_hybrid_cached(
    item_dicts: list[dict],
    remarks: list[str],
    calculated_payload: list[dict],
    priced_payload: list[dict],
    use_jev: bool,
    analysis_version: str,
):
    """Run hybrid analysis on a session-cache miss."""
    from core.kalkulation import CalculatedItem
    from core.pricer import PricedItem

    items = rehydrate(item_dicts)
    item_by_key = {item.key(): item for item in items}

    calculated = []
    for payload in calculated_payload:
        item = item_by_key.get(payload["key"])
        if item is not None:
            calculated.append(CalculatedItem(
                item=item,
                leistung=None,
                ep_low=payload["ep_low"],
                ep_mid=payload["ep_mid"],
                ep_high=payload["ep_high"],
            ))

    priced = []
    for payload in priced_payload:
        item = item_by_key.get(payload["key"])
        if item is not None:
            priced.append(PricedItem(
                item=item,
                unit_price=payload["unit_price"],
                total=payload["total"],
                source=payload["source"],
                comparables=payload["comparables"],
                spread=payload["spread"],
                bucket=payload["bucket"],
                distribution=payload["distribution"],
                note=payload["note"],
                similarity_score=payload.get("similarity_score", 0.0),
            ))

    return risk_engine.analyze_tender_hybrid(
        items,
        remarks,
        calculated,
        priced,
        use_jev=use_jev,
    )


def evaluate_cluster_deep_cached(
    filename: str,
    rules_version: str,
    payloads: dict[str, str],
) -> dict[str, dict]:
    """Cache deep cluster results for this browser session and model."""
    del filename
    adapter = deep_logic.get_adapter()
    payload_fingerprint = hashlib.sha256(
        json.dumps(payloads, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    session_cache_key = f"{rules_version}:{adapter.name}:{payload_fingerprint}"
    session_cache = st.session_state.setdefault("lv_cluster_analysis_cache", {})
    if session_cache_key in session_cache:
        return session_cache[session_cache_key]

    model = adapter.name
    from types import SimpleNamespace

    cluster_objects = []
    for cluster_id, payload in payloads.items():
        try:
            cluster_data = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            cluster_data = {}
        if not isinstance(cluster_data, dict):
            cluster_data = {}
        try:
            euro_exposure = float(cluster_data.get("euro_exposure") or 0.0)
        except (TypeError, ValueError):
            euro_exposure = 0.0
        kind = cluster_data.get("kind", "")
        cluster_objects.append(SimpleNamespace(
            cluster_id=cluster_id,
            kind=kind if isinstance(kind, str) else "",
            euro_exposure=euro_exposure,
        ))
    evaluations = deep_logic.evaluate_clusters(
        cluster_objects,
        payloads,
        use_llm=None,
        max_clusters=12,
        write_cache=True,
    )
    output = {
        cluster_id: {
            **evaluation.as_dict(),
            "model": model,
        }
        for cluster_id, evaluation in evaluations.items()
    }
    session_cache[session_cache_key] = output
    return output


# --- sections --------------------------------------------------------------

def linked_slider(
    label: str,
    min_value: float,
    max_value: float,
    default: float,
    step: float,
    key: str,
    *,
    help: str | None = None,
) -> float:
    """Render a slider with a directly editable number input."""
    slider_key = f"{key}_slider"
    number_key = f"{key}_number"
    if slider_key not in st.session_state:
        st.session_state[slider_key] = float(default)
    if number_key not in st.session_state:
        st.session_state[number_key] = float(default)

    def sync_number_from_slider() -> None:
        st.session_state[number_key] = st.session_state[slider_key]

    def sync_slider_from_number() -> None:
        st.session_state[slider_key] = st.session_state[number_key]

    number_format = "%.0f" if step >= 1.0 else "%.1f" if step == 0.5 else "%.2f"
    slider_format = "%.0f" if step >= 1.0 else "%.1f" if step == 0.5 else "%.2f"
    slider_column, number_column = st.sidebar.columns([3, 1])

    with slider_column:
        # No `value=` here. The key is already seeded in session_state above,
        # and passing both makes Streamlit warn and silently prefer the
        # session value — the slider then appears stuck, because the value you
        # pass is discarded on every rerun.
        value = st.slider(
            label,
            min_value=min_value,
            max_value=max_value,
            step=step,
            format=slider_format,
            key=slider_key,
            help=help,
            on_change=sync_number_from_slider,
        )
    with number_column:
        st.number_input(
            f"{label} eingeben",
            min_value=min_value,
            max_value=max_value,
            step=step,
            format=number_format,
            key=number_key,
            label_visibility="collapsed",
            on_change=sync_slider_from_number,
        )
    return float(value)


def sidebar_kalkulation() -> stammdaten.Company:
    """The cost base the bottom-up calculation uses."""
    st.sidebar.header("Kalkulationsgrundlage")
    defaults = stammdaten.Company()
    st.sidebar.caption(
        "Neutrale Startwerte, keine Firmenprofile. Passe sie an deine "
        "Kalkulationsgrundlage an."
    )

    wage = linked_slider(
        "Mittellohn (€/h)", 35.0, 95.0,
        float(defaults.mittellohn_eur_h), 0.5, "mittellohn",
    )

    # The markup, split into its three parts. Arithmetically a combined number
    # is identical — 15 + 5 is always 20 — but split, the estimator can see
    # which decision costs what: keep the AGK, waive the BGK on a strategic
    # job, set W&G where he wants it.
    st.sidebar.markdown("**Zuschläge**")
    agk = linked_slider(
        "AGK — Allgemeine Geschäftskosten (%)", 0.0, 30.0,
        float(defaults.agk_pct), 0.5, "agk",
        help="Kosten des Unternehmens außerhalb der Baustelle, auf ein "
             "ganzes Jahr gerechnet.")
    bgk = linked_slider(
        "BGK — Baustellengemeinkosten (%)", 0.0, 20.0,
        float(defaults.bgk_pct), 0.5, "bgk")
    wg = linked_slider(
        "W&G — Wagnis und Gewinn (%)", 0.0, 20.0,
        float(defaults.wg_pct), 0.5, "wg")

    # AGK is an annual figure. A ten-month job carries ten twelfths of it.
    months = linked_slider(
        "Bauzeit (Monate)", 1.0, 24.0, float(defaults.bauzeit_monate), 1.0,
        "bauzeit",
        help="Nur die AGK werden anteilig umgelegt — BGK und W&G nicht.")

    company = stammdaten.Company(
        "Eigene Kalkulation", wage, defaults.zuschlag_pct,
        defaults.leistungsfaktor, defaults.materialfaktor, "",
        agk_pct=agk, bgk_pct=bgk, wg_pct=wg, bauzeit_monate=months,
    )
    st.sidebar.metric("Zuschlag gesamt", f"{company.total_markup_pct:.1f} %")
    if months != 12:
        st.sidebar.caption(
            f"AGK {agk:.1f} % × {months:.0f}/12 = **{company.agk_wirksam_pct:.1f} %** "
            f"— {12 - months:+.0f} Monate gegenüber dem Jahr."
        )

    perf = linked_slider("Leistungsfaktor", 0.6, 1.6,
                         float(defaults.leistungsfaktor), 0.05,
                         "leistungsfaktor",
                         help=">1 = langsamer als die Richtwerte")
    mat = linked_slider("Materialfaktor", 0.6, 1.6,
                        float(defaults.materialfaktor), 0.05, "materialfaktor")
    company.leistungsfaktor = perf
    company.materialfaktor = mat
    return company


def section_upload(show_controls: bool = True):
    """Upload -> parse. Writes (items, remarks, label) into session state."""
    if show_controls:
        def upload_controls():
            upload = st.file_uploader(
                "Tender-Datei hochladen",
                type=[s.lstrip(".") for s in
                  XML_SUFFIXES + GAEB90_SUFFIXES + PDF_SUFFIXES],
            )
            if st.button("Beispiel-LV laden", type="primary"):
                st.session_state["source"] = ("disk", SAMPLE)
                st.rerun()
            if upload is not None:
                uploaded_source = ("upload", upload.name, upload.getvalue())
                if st.session_state.get("source") != uploaded_source:
                    st.session_state["source"] = uploaded_source
                    st.rerun()

        if st.session_state.get("source"):
            with st.expander("Tender-Datei wechseln"):
                upload_controls()
        else:
            upload_controls()

    source = st.session_state.get("source")
    if not source:
        if show_controls:
            st.info("Lade eine GAEB-Datei hoch oder öffne das Beispiel-LV.")
        else:
            st.info("Wechsle zu „Tender“, um eine GAEB-Datei zu laden.")
        return None

    try:
        if source[0] == "disk":
            source_path = _project_path(source[1])
            with open(source_path, "rb") as handle:
                source_bytes = handle.read()
            suffix = os.path.splitext(source_path)[1].lower()
            label = os.path.basename(source_path)
        else:
            source_bytes = source[2]
            suffix = os.path.splitext(source[1])[1].lower()
            label = source[1]
        parse_cache_key = hashlib.sha256(
            suffix.encode("utf-8") + b"\0" + source_bytes
        ).hexdigest()
        parse_cache = st.session_state.setdefault("lv_parse_cache", {})
        if parse_cache_key in parse_cache:
            raw, remarks, pdf_confidence = parse_cache[parse_cache_key]
            if pdf_confidence is not None:
                st.session_state["pdf_confidence"] = pdf_confidence
        else:
            if source[0] == "disk":
                raw, remarks = load_from_disk(source[1])
            else:
                raw, remarks = load_from_upload(source[1], source_bytes)
            pdf_confidence = st.session_state.get("pdf_confidence")
            parse_cache[parse_cache_key] = (raw, remarks, pdf_confidence)
    except ValueError as exc:
        # Known-unknown format. Say so plainly and offer the sample — do not
        # guess at a parse and present fabricated positions as real.
        st.error(f"{exc} — unterstützt werden GAEB X83 und GAEB 90 D83/D84/D86.")
        st.session_state.pop("source", None)
        return None
    except Exception:                                      # noqa: BLE001
        st.error(
            "Die Datei konnte nicht gelesen werden. "
            "Gespeicherte Beispieldaten werden versucht."
        )
        with st.expander("What went wrong"):
            st.code(traceback.format_exc())
        try:
            from scripts.dump_golden import load as load_golden
            items, remarks = load_golden(source[1])
            st.success(f"{len(items)} Positionen aus data/golden/ geladen.")
            return items, remarks, os.path.basename(source[1]) + " (fixture)"
        except Exception:                                  # noqa: BLE001
            st.session_state.pop("source", None)
            return None

    items = rehydrate(raw)
    if not items:
        # Spec-normal, not corruption: a .D84 bid submission can carry price
        # records and no quantity records, because it references the .D83/.D86
        # it was bid against. Say that, rather than showing an empty table.
        st.warning(
            f"**{label} enthält Preise, aber keine Mengen.** Das ist bei einem "
            "Angebot normal: Es verweist auf das zugehörige LV. Bitte lade "
            "stattdessen die Leistungsverzeichnis-Datei."
        )
        st.session_state.pop("source", None)
        return None

    priced_in_file = sum(1 for i in items if i.unit_price is not None)
    if show_controls:
        st.caption(
            f"{len(items)} Positionen aus {label}"
            + (f" — {priced_in_file} davon enthalten bereits Preise" if priced_in_file else "")
            + (f", dazu {len(remarks)} Vertragsvorbemerkungen" if remarks else "")
        )
    return items, remarks, label


def section_items(items, remarks, filename):
    """The parsed bill of quantities."""
    st.subheader("Ausgelesene Positionen")
    priced_in_lv = any(
        item.unit_price is not None or item.total_price is not None
        for item in items
    )
    st.caption(
        "EP und Gesamt zeigen nur Preise, die bereits in der Datei stehen. "
        "„Pauschalposition“ bezeichnet die Abrechnungsart, keinen Preis."
        if priced_in_lv else
        "Diese LV-Datei enthält noch keine Positionspreise. "
        "„Pauschalposition“ bezeichnet die Abrechnungsart, keinen Preis."
    )
    frame = pd.DataFrame([{
        "OZ": i.display_oz,
        "Position": i.short_text,
        "Menge": i.quantity,
        "Einheit": constants.normalize_unit(i.unit),
        "Abrechnung": "Pauschal" if i.is_lump_sum else "Menge × Einheit",
        "EP (€)": i.unit_price,
        "GP (€)": i.total_price,
    } for i in items])
    event = st.dataframe(
        frame,
        column_config={
            "EP (€)": st.column_config.NumberColumn(format="€ %.2f"),
            "GP (€)": st.column_config.NumberColumn(format="€ %.2f"),
        },
        width="stretch",
        hide_index=True,
        height="stretch",
        key="tender_items_table",
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_rows = event.selection.rows
    if selected_rows:
        row_index = selected_rows[0]
        if 0 <= row_index < len(items):
            _open_position_details(
                items[row_index], items, remarks, filename
            )


def source_document(source):
    """Return the original file name and bytes for the active tender."""
    if source[0] == "upload":
        return source[1], source[2]
    path = _project_path(source[1])
    with open(path, "rb") as handle:
        return os.path.basename(path), handle.read()


def source_location(filename: str, payload: bytes, source_ref: str) -> tuple[str, bool]:
    """Locate a source item without exposing its raw XML or fixed-width record."""
    suffix = os.path.splitext(filename)[1].lower()
    if suffix in XML_SUFFIXES:
        root = ET.fromstring(payload)
        for element in root.iter():
            local_tag = element.tag.rsplit("}", 1)[-1]
            if (
                local_tag == parser_x83.ITEM_TAG
                and element.attrib.get("ID") == source_ref
            ):
                return f"GAEB-XML · Element-ID {source_ref}", True
        return f"Kein XML-Element mit ID {source_ref} gefunden.", False

    match = re.fullmatch(r"type-21 #(\d+)", source_ref)
    if suffix in GAEB90_SUFFIXES and match:
        target = int(match.group(1))
        lines = payload.decode(
            parser_gaeb90.ENCODING,
            errors="replace",
        ).splitlines()
        records = [
            (line_number, line)
            for line_number, line in enumerate(lines, start=1)
            if line.startswith("21")
        ]
        if 1 <= target <= len(records):
            line_number, _ = records[target - 1]
            return f"GAEB 90 · Datensatz 21 · Zeile {line_number}", True
        return f"Datensatz {source_ref} nicht gefunden.", False

    return "Für dieses Dateiformat ist keine Fundstelle verfügbar.", False


def tender_document_html(
    items,
    remarks: list[str],
    selected_key: str,
    filename: str,
    overrides: dict | None = None,
    calculated_by_key: dict | None = None,
) -> str:
    """Render the parsed source tender as a navigable, highlighted document table."""
    rows = []
    if remarks:
        rows.append(
            '<tr class="section"><th colspan="6">'
            "Vertragsvorbemerkungen</th></tr>"
        )
        for index, remark in enumerate(remarks, start=1):
            rows.append(
                '<tr class="remark"><td colspan="6">'
                f'<strong>Vorbemerkung {index}</strong>'
                f'<div class="long-text">{html.escape(remark)}</div></td></tr>'
            )

    current_section = None
    for item in items:
        if item.section_path != current_section:
            current_section = item.section_path
            section = " › ".join(current_section) or "Ohne Abschnitt"
            rows.append(
                '<tr class="section"><th colspan="6">'
                f'{html.escape(section)}</th></tr>'
            )

        short_text = item.short_text or f"Position {item.display_oz}"
        long_text = item.long_text or short_text
        if long_text.startswith(short_text):
            long_text = long_text[len(short_text):].lstrip(" ,;:-")
        elif long_text.endswith(short_text):
            long_text = long_text[:-len(short_text)].rstrip(" ,;:-")
        description = f"<strong>{html.escape(short_text)}</strong>"
        if long_text:
            description += f'<div class="long-text">{html.escape(long_text)}</div>'
        if item.is_lump_sum:
            description += '<div class="flag">Pauschalposition</div>'

        override = (overrides or {}).get(item.key())
        if override:
            display_unit_price = override["ep"]
            display_total_price = override["gp"]
        else:
            display_unit_price = item.unit_price
            display_total_price = item.total_price
            estimate = (calculated_by_key or {}).get(item.key())
            if display_unit_price is None and estimate is not None:
                display_unit_price = estimate.ep_mid
            if display_total_price is None and estimate is not None:
                display_total_price = estimate.total
            if display_total_price is None and display_unit_price is not None:
                display_total_price = display_unit_price * item.quantity

        selected = " selected" if item.key() == selected_key else ""
        row_id = ' id="selected-position"' if selected else ""
        changed = " changed" if override else ""
        rows.append(
            f'<tr class="position{selected}"{row_id}>'
            f'<td class="oz">{html.escape(item.display_oz)}</td>'
            f'<td class="description">{description}</td>'
            f'<td class="number">{item.quantity:g}</td>'
            f'<td>{html.escape(item.unit)}</td>'
            f'<td class="number{changed}">{_price(display_unit_price)}</td>'
            f'<td class="number{changed}">{_price(display_total_price)}</td>'
            "</tr>"
        )

    return f"""<!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8">
        <style>
          * {{ box-sizing: border-box; }}
          body {{ margin: 0; color: #172033; background: #fff;
                 font: 14px/1.45 Arial, sans-serif; }}
          .file-name {{ padding: 12px 14px; border-bottom: 1px solid #cbd5e1;
                        font-weight: 700; }}
          table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
          thead {{ position: sticky; top: 0; z-index: 2; }}
          th {{ padding: 9px 10px; text-align: left; background: #e8edf4;
                border-bottom: 1px solid #cbd5e1; }}
          td {{ padding: 9px 10px; vertical-align: top;
                border-bottom: 1px solid #e2e8f0; overflow-wrap: anywhere; }}
          th:nth-child(1) {{ width: 11%; }}
          th:nth-child(2) {{ width: 53%; }}
          th:nth-child(3) {{ width: 9%; }}
          th:nth-child(4) {{ width: 8%; }}
          th:nth-child(5), th:nth-child(6) {{ width: 9.5%; }}
          .section th {{ padding: 11px 10px; color: #334155;
                         background: #f1f5f9; border-top: 1px solid #cbd5e1; }}
          .remark td {{ padding: 12px 14px; background: #fff;
                        border-bottom: 1px solid #e2e8f0; }}
          .position:nth-child(even) {{ background: #fafbfd; }}
          .position.selected td {{ background: #fff3bf; }}
          .position.selected td:first-child {{ border-left: 4px solid #d59b00;
                                                font-weight: 700; }}
          .position td.changed {{
            background: #ffedd5;
            color: #9a3412;
            font-weight: 700;
          }}
          .long-text {{ margin-top: 4px; white-space: pre-wrap; }}
          .number {{ text-align: right; white-space: nowrap; }}
          .flag {{ margin-top: 5px; font-size: 12px; color: #64748b; }}
        </style>
      </head>
      <body>
        <div class="file-name">{html.escape(filename)} · Leistungsverzeichnis</div>
        <table aria-label="Originale GAEB-Positionen">
          <thead><tr>
            <th>OZ</th><th>Leistungstext</th><th>Menge</th>
            <th>Einheit</th><th>EP</th><th>Gesamt</th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        <script>
          document.getElementById("selected-position")?.scrollIntoView(
            {{block: "center"}}
          );
        </script>
      </body>
    </html>
    """


def _price(value: float | None) -> str:
    return f"€{value:,.2f}" if value is not None else "—"


@st.dialog("Originales Leistungsverzeichnis", width="large")
def show_position_details(
    item,
    items,
    remarks: list[str],
    filename: str,
    payload: bytes | None,
    source_error: str | None,
    calculated_by_key: dict | None = None,
):
    """Show the entire source tender with the matching position highlighted."""
    if "manual_prices" not in st.session_state:
        st.session_state["manual_prices"] = {}
    manual_prices = st.session_state["manual_prices"]
    item_key = item.key()
    estimate = (calculated_by_key or {}).get(item_key)
    override = manual_prices.get(item_key)

    base_ep = item.unit_price
    base_gp = item.total_price
    if base_ep is None and estimate is not None:
        base_ep = estimate.ep_mid
    if base_gp is None and estimate is not None:
        base_gp = estimate.total
    if base_gp is None and base_ep is not None:
        base_gp = base_ep * item.quantity
    base_ep = float(base_ep or 0.0)
    base_gp = float(base_gp or 0.0)
    current_ep = float(override["ep"]) if override else base_ep
    current_gp = float(override["gp"]) if override else base_gp

    ep_key = f"dialog_ep_{item_key}"
    gp_key = f"dialog_gp_{item_key}"
    if ep_key not in st.session_state:
        st.session_state[ep_key] = current_ep
    if gp_key not in st.session_state:
        st.session_state[gp_key] = current_gp
    if override:
        st.session_state[ep_key] = current_ep
        st.session_state[gp_key] = current_gp

    st.markdown("**Preise bearbeiten**")
    reset_column, _ = st.columns([1, 3])
    with reset_column:
        if st.button("Zurücksetzen", disabled=override is None, width="stretch"):
            manual_prices.pop(item_key, None)
            st.session_state[ep_key] = base_ep
            st.session_state[gp_key] = base_gp
            st.rerun()

    def sync_gp_from_ep() -> None:
        ep = float(st.session_state[ep_key])
        gp = round(ep * item.quantity, 2)
        st.session_state[gp_key] = gp
        manual_prices[item_key] = {"ep": ep, "gp": gp}

    def sync_ep_from_gp() -> None:
        gp = float(st.session_state[gp_key])
        ep = round(gp / item.quantity, 2) if item.quantity else 0.0
        st.session_state[ep_key] = ep
        manual_prices[item_key] = {"ep": ep, "gp": gp}

    ep_column, gp_column = st.columns([1, 1])
    with ep_column:
        st.number_input(
            "EP (€)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key=ep_key,
            on_change=sync_gp_from_ep,
        )
    with gp_column:
        st.number_input(
            "GP (€)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key=gp_key,
            on_change=sync_ep_from_gp,
        )
    if override:
        st.caption("Bearbeiteter Preis · GP = EP × Menge, oder EP = GP ÷ Menge.")
    else:
        st.caption("EP und GP sind noch nicht manuell verändert.")

    location = item.source_ref or "Keine Quellreferenz vorhanden."
    if source_error:
        st.warning(f"Quelldokument konnte nicht geöffnet werden: {source_error}")
    elif payload is not None and item.source_ref:
        location, found = source_location(filename, payload, item.source_ref)
        if not found:
            st.info("Die Position ist in den geparsten Daten enthalten, "
                    "aber keine genaue Fundstelle wurde gefunden.")
    else:
        st.info("Für diese Position ist keine genaue Fundstelle verfügbar.")
    st.caption(f"{filename} · {len(items)} Positionen · Fundstelle: {location}")
    st.iframe(
        tender_document_html(
            items,
            remarks,
            item.key(),
            filename,
            manual_prices,
            calculated_by_key,
        ),
        height=600,
        alt=(
            f"Leistungsverzeichnis aus {filename}, "
            f"Position {item.display_oz} markiert"
        ),
    )


def _open_position_details(
    item, items, remarks, filename, calculated_by_key=None,
):
    st.session_state["opened_position_key"] = item.key()
    source = st.session_state.get("source")
    payload = None
    source_error = None
    fallback_filename = item.source_file or filename or "Quelldokument"
    if source:
        try:
            filename, payload = source_document(source)
        except OSError as exc:
            filename = fallback_filename
            source_error = str(exc)
    else:
        filename = fallback_filename
        source_error = "Keine Quelldatei im aktuellen Sitzungskontext."
    show_position_details(
        item,
        items,
        remarks,
        filename,
        payload,
        source_error,
        calculated_by_key,
    )


def _action_entry_is_selected(state_key, entry):
    selected_entries = st.session_state.get(state_key, [])
    if not isinstance(selected_entries, list):
        return False
    entry_id = entry.get("id")
    entry_oz = entry.get("oz")
    return any(
        isinstance(selected, dict)
        and (
            (entry_id and selected.get("id") == entry_id)
            or (entry_oz and selected.get("oz") == entry_oz)
        )
        for selected in selected_entries
    )


def _store_selected_action(state_key, entry, confirmation):
    selected_entries = st.session_state.get(state_key, [])
    if not isinstance(selected_entries, list):
        selected_entries = []
    if not _action_entry_is_selected(state_key, entry):
        selected_entries.append(entry)
    st.session_state[state_key] = selected_entries

    if state_key == "selected_rfis" and entry.get("kind") == "cluster":
        cluster_questions = st.session_state.get("rfi_cluster_questions", [])
        if not isinstance(cluster_questions, list):
            cluster_questions = []
        if not any(
            isinstance(question, dict)
            and question.get("cluster_id") == entry.get("cluster_id")
            for question in cluster_questions
        ):
            cluster_question = dict(entry)
            cluster_question.update({
                "category": entry.get("contradiction_category"),
                "title": entry.get("cluster_title"),
                "analysis": entry.get("reason_de"),
            })
            cluster_questions.append(cluster_question)
        st.session_state["rfi_cluster_questions"] = cluster_questions

    st.toast(confirmation)


def _position_action_entry(item, action_type, reason, source, severity="medium"):
    oz = item.display_oz
    short_text = item.short_text or item.long_text or "Leistung gemäß LV"
    unit = constants.normalize_unit(item.unit) or "—"
    quantity = f"{item.quantity:g} {unit}"
    if action_type == "RFI":
        question = (
            f"Bitte konkretisieren Sie im Sinne der VOB/A den Leistungsumfang "
            f"der Position {oz} („{short_text}“) mit {quantity} und bestätigen "
            f"Sie die für die Preisbildung maßgeblichen Angaben. "
            f"Prüfhinweis: {reason}"
        )
    else:
        question = (
            f"Bitte erstellen Sie ein Nachunternehmer-Angebot für Position "
            f"{oz} („{short_text}“), Menge {quantity}. Bitte weisen Sie den "
            f"Preis sowie enthaltene Nebenleistungen und notwendige "
            f"Schnittstellen aus. Prüfhinweis: {reason}"
        )
    return {
        "id": f"{action_type}:position:{item.key()}",
        "kind": "position",
        "action_type": action_type,
        "source": source,
        "position_key": item.key(),
        "oz": oz,
        "short_text": short_text,
        "quantity": item.quantity,
        "unit": unit,
        "severity": severity,
        "reason_de": reason,
        "question": question,
    }


def _cluster_action_entry(card, action_type):
    cluster_id = str(card["cluster_id"])
    affected_ozs = list(card.get("affected_ozs") or [])
    title = str(card.get("title") or cluster_id)
    reason = str(card.get("analysis") or "")
    oz_text = ", ".join(affected_ozs) if affected_ozs else "siehe Cluster"
    if action_type == "RFI":
        question = (
            f"Bitte erläutern Sie den Befund zum Cluster „{title}“ im Sinne "
            f"der VOB/A und konkretisieren Sie die betroffenen Leistungen "
            f"(OZ {oz_text}). Hintergrund: {reason}"
        )
    else:
        question = (
            f"Bitte prüfen Sie die Leistungen im Cluster „{title}“ "
            f"(OZ {oz_text}) und erstellen Sie ein Nachunternehmer-Angebot. "
            f"Bitte weisen Sie Preis, Nebenleistungen und Schnittstellen aus. "
            f"Prüfhinweis: {reason}"
        )
    return {
        "id": f"{action_type}:cluster:{cluster_id}",
        "kind": "cluster",
        "action_type": action_type,
        "source": "Logik",
        "cluster_id": cluster_id,
        "cluster_title": title,
        "contradiction_category": card.get("category"),
        "reason_de": reason,
        "question": question,
        "affected_ozs": affected_ozs,
        "euro_exposure_estimate": card.get("euro_exposure_estimate", 0.0),
        "severity": card.get("severity", "medium"),
    }


def _render_action_button(
    state_key, entry, label, selected_label, toast_message, widget_key,
):
    selected = _action_entry_is_selected(state_key, entry)
    st.button(
        selected_label if selected else label,
        key=widget_key,
        disabled=selected,
        on_click=_store_selected_action,
        args=(state_key, entry, toast_message),
        width="stretch",
    )


def _group_subgroups(items):
    section_labels = {
        item.location(depth=2)
        for item in items
        if item.section_path
    }
    if len(section_labels) > 1:
        labels = [item.location(depth=2) for item in items]
        source = "LV-Abschnitt"
    else:
        tags = [objects.tag_of(item) for item in items]
        if len(set(tags)) > 1:
            labels = tags
            source = "Positionstyp"
        else:
            labels = [next(iter(section_labels), "(ohne Untergruppe)")] * len(items)
            source = "LV-Abschnitt"

    subgroups = {}
    for label, item in zip(labels, items):
        subgroups.setdefault(label, []).append(item)
    return subgroups, source


def section_groups(items, assignments, data, filename: str, remarks: list[str],
                   calculated=None):
    """List trade groups; opening one shows the positions in that trade."""
    if "manual_prices" not in st.session_state:
        st.session_state["manual_prices"] = {}
    manual_prices = st.session_state["manual_prices"]
    calculated_by_key = {
        c.item.key(): c for c in (calculated or [])
    }
    rows = objects.by_trade(items, assignments, data, calculated)

    item_by_key = {item.key(): item for item in items}

    def position_total(position_key):
        item = item_by_key.get(position_key)
        if item is None:
            return 0.0
        override = manual_prices.get(position_key)
        if override is not None:
            return override["gp"]
        if item.total_price is not None:
            return item.total_price
        if item.unit_price is not None:
            return item.unit_price * item.quantity
        estimate = calculated_by_key.get(position_key)
        return (estimate.total or 0.0) if estimate is not None else 0.0

    selected_key = st.session_state.get("selected_group_key")
    selected = next((row for row in rows if row.key == selected_key), None)

    if selected is None:
        st.caption(f"{len(rows)} Gruppen · {len(items)} Positionen")
        query = st.text_input("Gruppe suchen", placeholder="Gewerk")
        query = query.casefold().strip()
        visible_rows = [row for row in rows if query in row.obj.casefold()]
        if not visible_rows:
            st.info("Keine passende Gruppe gefunden.")
            return

        with st.container(key="group_list"):
            for index, row in enumerate(visible_rows):
                with st.container(border=True):
                    name, details, action = st.columns(
                        [5, 2.5, 2],
                        vertical_alignment="center",
                    )
                    name.markdown(f"**{row.obj}**")
                    group_positions = [
                        item_by_key[position_key]
                        for position_key in row.positions
                        if position_key in item_by_key
                    ]
                    subgroups, _subgroup_source = _group_subgroups(group_positions)
                    name.caption(
                        f"{len(row.positions)} Positionen · "
                        f"{len(subgroups)} Untergruppen"
                    )
                    value = sum(position_total(key) for key in row.positions)
                    details.caption(
                        f"{row.unit or '—'} · Gesamt: €{value:,.2f}"
                    )
                    if action.button(
                        "Öffnen →",
                        key=f"open_group_{index}",
                        width="stretch",
                    ):
                        st.session_state["selected_group_key"] = row.key
                        st.session_state.pop("selected_group_subgroup_key", None)
                        st.session_state.pop("group_positions", None)
                        st.session_state.pop("opened_position_key", None)
                        st.rerun()
        return

    if st.button("← Alle Gruppen"):
        st.session_state.pop("selected_group_key", None)
        st.session_state.pop("selected_group_subgroup_key", None)
        st.session_state.pop("group_positions", None)
        st.session_state.pop("opened_position_key", None)
        st.rerun()
    st.subheader(selected.obj)
    st.caption(
        f"{len(selected.positions)} Positionen · "
        f"Einheiten: {selected.unit or '—'}"
    )
    item_by_key = {item.key(): item for item in items}
    group_items = [item_by_key[key] for key in selected.positions if key in item_by_key]
    subgroup_items, subgroup_source = _group_subgroups(group_items)
    selected_subgroup = st.session_state.get("selected_group_subgroup_key")
    if selected_subgroup not in subgroup_items:
        selected_subgroup = None
        st.session_state.pop("selected_group_subgroup_key", None)

    if len(subgroup_items) > 1:
        st.caption(
            f"Untergruppen nach {subgroup_source} · "
            "anklicken, um die Positionsübersicht zu öffnen."
        )
        with st.expander(
            f"Untergruppenübersicht ({len(subgroup_items)})",
            expanded=selected_subgroup is None,
        ):
            ordered_subgroups = sorted(
                subgroup_items.items(),
                key=lambda entry: (
                    -sum(position_total(item.key()) for item in entry[1]),
                    entry[0].casefold(),
                ),
            )
            for index, (subgroup_name, subgroup_positions) in enumerate(ordered_subgroups):
                with st.container(border=True):
                    name, details, action = st.columns(
                        [5, 2.5, 2],
                        vertical_alignment="center",
                    )
                    name.markdown(f"**{subgroup_name}**")
                    name.caption(f"{len(subgroup_positions)} Positionen")
                    details.caption(
                        f"Gesamt: €{sum(position_total(item.key()) for item in subgroup_positions):,.2f}"
                    )
                    if action.button(
                        "Übersicht öffnen →",
                        key=f"open_subgroup_{index}",
                        width="stretch",
                    ):
                        st.session_state["selected_group_subgroup_key"] = subgroup_name
                        st.session_state.pop("group_positions", None)
                        st.session_state.pop("opened_position_key", None)
                        st.rerun()

        if selected_subgroup is not None:
            if st.button(
                "Alle Positionen der Gruppe anzeigen",
                key="show_all_group_positions",
            ):
                st.session_state.pop("selected_group_subgroup_key", None)
                st.session_state.pop("group_positions", None)
                st.session_state.pop("opened_position_key", None)
                st.rerun()
            st.markdown(f"#### {selected_subgroup}")
            group_items = subgroup_items[selected_subgroup]

    st.caption(
        "EP und GP zeigen Angebotspreise; bei einer unbepriessten LV-Datei "
        "werden die kalkulierten Werte angezeigt. "
        "Wähle eine Zeile, um das Bearbeitungs- und Detailpanel zu öffnen."
    )

    position_rows = []
    for item in group_items:
        estimate = calculated_by_key.get(item.key())
        override = manual_prices.get(item.key())
        unit_price = override["ep"] if override else item.unit_price
        total_price = override["gp"] if override else item.total_price
        if unit_price is None and estimate is not None:
            unit_price = estimate.ep_mid
        if total_price is None and estimate is not None:
            total_price = estimate.total
        if total_price is None and unit_price is not None:
            total_price = unit_price * item.quantity

        position_rows.append({
            "OZ": item.display_oz,
            "Position": item.short_text or item.long_text or "—",
            "Menge": item.quantity,
            "Einheit": constants.normalize_unit(item.unit) or "—",
            "Pauschal": "ja" if item.is_lump_sum else "",
            "EP (€)": unit_price,
            "GP (€)": total_price,
            "Bearbeitet": "●" if override else "",
        })

    event = st.dataframe(
        pd.DataFrame(position_rows),
        width="stretch",
        hide_index=True,
        height="stretch",
        column_config={
            "OZ": st.column_config.TextColumn("OZ", width="small"),
            "Position": st.column_config.TextColumn("Position", width="large"),
            "Menge": st.column_config.NumberColumn(
                "Menge", width="small", format="%.3f"
            ),
            "Einheit": st.column_config.TextColumn("Einheit", width="small"),
            "EP (€)": st.column_config.NumberColumn(
                "EP (€)", width="small", format="€ %.2f"
            ),
            "GP (€)": st.column_config.NumberColumn(
                "GP (€)", width="small", format="€ %.2f"
            ),
            "Bearbeitet": st.column_config.TextColumn(
                "Bearbeitet", width="small"
            ),
        },
        key="group_positions",
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_rows = event.selection.rows
    if selected_rows:
        row_index = selected_rows[0]
        if 0 <= row_index < len(group_items):
            _open_position_details(
                group_items[row_index],
                items,
                remarks,
                filename,
                calculated_by_key,
            )


def section_angebot_export(items, calculated, label):
    """Hand the priced tender back as a file, not as a screenshot."""
    st.subheader("Angebot exportieren")
    stats = exporter.summarize(calculated)
    st.caption(
        f"{stats['priced']} von {stats['positions']} Positionen bepreist · "
        f"Angebotssumme €{stats['total']:,.2f}. Nicht kalkulierte Positionen "
        "bleiben im Export leer — das ist in einem Angebot zulässig und "
        "ehrlicher als eine erfundene Zahl."
    )

    source = st.session_state.get("source")
    csv_column, x84_column = st.columns(2)
    with csv_column:
        st.download_button(
            "Angebot als CSV",
            data=exporter.export_csv(calculated),
            file_name=f"{os.path.splitext(label)[0]}_Angebot.csv",
            mime="text/csv",
            width="stretch",
        )
        st.caption("Semikolon und Komma-Dezimal — öffnet in Excel ohne Assistent.")

    with x84_column:
        # X84 is written INTO the uploaded X83, so it needs that file. A PDF
        # or GAEB-90 source has no XML skeleton to stamp prices into.
        xml_source = (
            source[1] if source and source[0] == "disk"
            and source[1].lower().endswith(tuple(XML_SUFFIXES)) else None
        )
        if xml_source:
            payload, report = exporter.export_x84(xml_source, calculated)
            st.download_button(
                "Angebot als GAEB X84",
                data=payload,
                file_name=f"{os.path.splitext(label)[0]}_Angebot.x84",
                mime="application/xml",
                width="stretch",
            )
            if report["complete"]:
                st.caption(f"{report['written']} Positionen mit Preis geschrieben.")
            else:
                st.caption(
                    f"{report['written']} Positionen geschrieben, "
                    f"{report['unmatched_in_file']} ohne Preis "
                    f"(z. B. {', '.join(report['unmatched_examples'][:3])}). "
                    "Zuordnung über die Ordnungszahl, nie über die Reihenfolge."
                )
        else:
            st.button("Angebot als GAEB X84", disabled=True, width="stretch")
            st.caption(
                "X84 entsteht aus der hochgeladenen X83-Datei. Für PDF- oder "
                "GAEB-90-Quellen gibt es kein XML-Gerüst, in das Preise "
                "geschrieben werden könnten — bitte CSV verwenden."
            )


def section_position_table(items, assignments, calculated, data, company):
    """The full per-position cost breakdown.

    Lives on the Tender page, next to the positions it describes. On
    "Gruppen & Angebot" it buried the group overview — that page answers
    "where is the money and the risk", and a 248-row table pushed the answer
    below the fold.
    """
    st.subheader("Positionskalkulation")
    st.caption(
        "Jede Position mit allen Kostenbestandteilen. Die Zusammenfassung "
        "nach Gewerken steht unter „Gruppen & Angebot“."
    )
    st.caption(
        "Kosten und Arbeitsstunden gelten je Einheit; der Gesamtpreis ergibt "
        "sich aus Menge × Einheitspreis."
    )
    _render_position_table(items, assignments, calculated, data, company)


def section_kalkulation(
    items, assignments, calculated, cov, data, company, vergabe_ergebnis=None,
):
    """Show each cost component that makes up the position price."""
    st.subheader("Angebotssumme")
    stats = kalkulation.summarize(calculated)
    offer_total = (
        vergabe_ergebnis.angebotssumme
        if vergabe_ergebnis is not None
        else stats["total_mid"]
    )

    a, b, c, d = st.columns(4)
    a.metric(
        "Angebotssumme",
        f"€{offer_total:,.0f}",
        help=(
            "Inklusive der Entscheidungen auf der Seite Vergabe."
            if vergabe_ergebnis is not None
            else "Mittelwert der kalkulierten Spanne."
        ),
    )
    b.metric("Spanne", f"€{stats['total_low']:,.0f} – {stats['total_high']:,.0f}")
    c.metric("Kalkuliert", f"{stats['coverage_pct']:.0f}%",
             help=f"{stats['unpriced']} Positionen ohne zugeordnete Leistung")
    d.metric("davon Lohn", f"€{stats['labour_eur']:,.0f}")

    if cov["pct"] < 50:
        st.error(
            f"**Nur {cov['pct']}% der Positionen konnten einer Leistung "
            f"zugeordnet werden.** Der Katalog hat "
            f"{len(data.leistungen)} Einträge; dieses LV beschreibt Arbeiten, "
            "die darin nicht vorkommen. Die Summe oben deckt deshalb nur einen "
            "Teil des Leistungsverzeichnisses ab — sie ist kein vollständiges "
            "Angebot. Ein größerer Katalog oder ein semantischer Klassifikator "
            "behebt das; Stichwortabgleich reicht hier nicht."
        )
    if data.is_synthetic:
        st.caption(
            "⚠️ Die Stammdaten sind **synthetisch** (eigene Schätzungen in "
            "ARH-Größenordnung, keine Marktabfrage). Das Verfahren ist echt, "
            "die Zahlen sind Platzhalter, bis echte Firmenwerte hinterlegt sind."
        )
    return calculated


def _render_position_table(items, assignments, calculated, data, company):
    """Build and render the per-position breakdown table."""
    trade_by_key = {
        key: row.obj
        for row in objects.by_trade(items, assignments, data, calculated)
        for key in row.positions
    }
    rows = []
    for entry in calculated:
        breakdown = entry.breakdown
        ekt = breakdown.ekt if entry.priced else None
        agk = (
            ekt * company.agk_wirksam_pct / 100.0
            if ekt is not None else None
        )
        bgk = (
            ekt * company.bgk_pct / 100.0
            if ekt is not None else None
        )
        wg = (
            ekt * company.wg_pct / 100.0
            if ekt is not None else None
        )
        surcharge = entry.ep_mid - ekt if ekt is not None else None
        rows.append({
            "OZ": entry.item.display_oz,
            "Position": entry.item.short_text or entry.item.long_text,
            "Gewerk": trade_by_key.get(
                entry.item.key(),
                "nicht zugeordnet",
            ),
            "Leistung": (
                entry.leistung.label() if entry.leistung else "—"
            ),
            "Menge": entry.item.quantity,
            "Einheit": constants.normalize_unit(entry.item.unit) or "—",
            "Arbeitsstunden/Einh.": (
                breakdown.labour_hours if entry.priced else None
            ),
            "Lohn €/Einh.": (
                breakdown.labour_eur if entry.priced else None
            ),
            "Maschinenstunden/Einh.": (
                breakdown.machine_hours if entry.priced else None
            ),
            "Gerät €/Einh.": (
                breakdown.machine_eur if entry.priced else None
            ),
            "Material €/Einh.": (
                breakdown.material_eur if entry.priced else None
            ),
            "EKT €/Einh.": ekt,
            "AGK €/Einh.": agk,
            "BGK €/Einh.": bgk,
            "W&G €/Einh.": wg,
            "Zuschläge €/Einh.": surcharge,
            "EP €/Einh.": entry.ep_mid,
            "GP €": entry.total,
        })

    column_config = {
        "OZ": st.column_config.TextColumn("OZ", width="small"),
        "Position": st.column_config.TextColumn("Position", width="small"),
        "Gewerk": st.column_config.TextColumn("Gewerk", width="small"),
        "Leistung": st.column_config.TextColumn("Leistung", width="small"),
        "Menge": st.column_config.NumberColumn(
            "Menge", format="%.3f", width="small",
        ),
        "Einheit": st.column_config.TextColumn("Einheit", width="small"),
        "Arbeitsstunden/Einh.": st.column_config.NumberColumn(
            "Arbeitsstunden/Einh.", format="%.3f", width="small",
        ),
        "Lohn €/Einh.": st.column_config.NumberColumn(
            "Lohn €/Einh.", format="€ %.2f", width="small",
        ),
        "Maschinenstunden/Einh.": st.column_config.NumberColumn(
            "Maschinenstunden/Einh.", format="%.3f", width="small",
        ),
        "Gerät €/Einh.": st.column_config.NumberColumn(
            "Gerät €/Einh.", format="€ %.2f", width="small",
        ),
    }
    for column in (
        "Material €/Einh.",
        "EKT €/Einh.",
        "AGK €/Einh.",
        "BGK €/Einh.",
        "W&G €/Einh.",
        "Zuschläge €/Einh.",
        "EP €/Einh.",
        "GP €",
    ):
        column_config[column] = st.column_config.NumberColumn(
            column,
            format="€ %.2f",
            width="small",
        )

    st.dataframe(
        pd.DataFrame(rows),
        column_config=column_config,
        width="stretch",
        hide_index=True,
        height="stretch",
    )
    return calculated


def section_logic(
    items,
    remarks,
    hybrid_results,
    findings,
    calculated=None,
    filename: str = "",
    use_deep_logic: bool = False,
):
    """Cluster logic findings with deterministic and optional LLM evaluations."""
    del hybrid_results, findings
    item_by_key = {item.key(): item for item in items}
    item_by_display_oz = {item.display_oz: item for item in items}
    facts_by_key = {item.key(): facts.extract_facts(item) for item in items}
    active_domains = domain.detect_lv_domains(items, remarks)
    cluster_list = clusters.build_clusters(
        items,
        facts_by_key,
        calculated=calculated,
        preambles=remarks,
        domains=active_domains,
    )
    cluster_priority = {"SYSTEM": 0, "FRAME": 1}
    cluster_list.sort(
        key=lambda cluster: (
            -float(cluster.euro_exposure or 0.0),
            cluster_priority.get(cluster.kind, 2),
        )
    )

    cluster_flags = logic.check_cluster_rules(
        cluster_list,
        items,
        facts_by_key,
        calculated=calculated,
        remarks=remarks,
        domains=active_domains,
    )

    pre_prices = {
        entry.item.key(): float(entry.ep_mid)
        for entry in (calculated or [])
        if entry.ep_mid is not None
    }
    position_results = logic.run_logic_engine(
        items,
        pre_prices=pre_prices,
    )
    calculated_by_key = {
        calculated_item.item.key(): calculated_item
        for calculated_item in (calculated or [])
    }
    position_rows = []
    position_row_items = []
    for item in items:
        result = position_results[item.key()]
        if not result.flags:
            continue
        position_rows.append({
            "OZ": item.display_oz,
            "Kurztext": item.short_text,
            "Regelkategorie": ", ".join(result.flags),
            "Schweregrad": _severity_label(result.severity),
            "Begründung": " | ".join(result.details),
        })
        position_row_items.append(item)

    duplicate_findings = logic.check_duplicates(items, pre_prices)
    duplicate_rows = []
    duplicate_row_items = []
    for finding in duplicate_findings:
        duplicate_positions = [
            item_by_key[key]
            for key in finding.evidence.get("positions", [])
            if key in item_by_key
        ]
        for left_index, left_item in enumerate(duplicate_positions):
            for right_item in duplicate_positions[left_index + 1:]:
                similarity = SequenceMatcher(
                    None,
                    left_item.short_text.casefold(),
                    right_item.short_text.casefold(),
                ).ratio()
                duplicate_rows.append({
                    "OZ 1": left_item.display_oz,
                    "Kurztext 1": left_item.short_text,
                    "OZ 2": right_item.display_oz,
                    "Kurztext 2": right_item.short_text,
                    "Einheit": constants.normalize_unit(left_item.unit),
                    "Menge 1": left_item.quantity,
                    "Menge 2": right_item.quantity,
                    "Ähnlichkeit": similarity,
                })
                duplicate_row_items.append(left_item)

    def render_position_findings():
        st.subheader("Positionsbezogene Regelbefunde")
        position_event = None
        if position_rows:
            position_event = st.dataframe(
                pd.DataFrame(position_rows),
                width="stretch",
                hide_index=True,
                height="stretch",
                key="logic_position_findings_table",
                on_select="rerun",
                selection_mode="single-row",
            )
        else:
            st.caption("Keine positionsbezogenen Regelbefunde.")

        selected_position_rows = (
            list(position_event.selection.rows)
            if position_event is not None else []
        )
        if selected_position_rows:
            row_index = selected_position_rows[0]
            if 0 <= row_index < len(position_row_items):
                item = position_row_items[row_index]
                row = position_rows[row_index]
                st.caption(f"Aktionen für OZ {item.display_oz}")
                rfi_column, rfq_column = st.columns(2)
                with rfi_column:
                    _render_action_button(
                        "selected_rfis",
                        _position_action_entry(
                            item,
                            "RFI",
                            row["Begründung"],
                            "Logik",
                            row["Schweregrad"],
                        ),
                        "Als Bieterfrage übernehmen",
                        "✓ Als Bieterfrage übernommen",
                        "Bieterfrage wurde für den Export vorgemerkt.",
                        f"logic_position_rfi_{item.key()}",
                    )
                with rfq_column:
                    _render_action_button(
                        "selected_rfqs",
                        _position_action_entry(
                            item,
                            "RFQ",
                            row["Begründung"],
                            "Logik",
                            row["Schweregrad"],
                        ),
                        "Als Nachunternehmen weiterleiten",
                        "✓ Für NU-Anfrage vorgemerkt",
                        "Position wurde für die Nachunternehmer-Anfrage vorgemerkt.",
                        f"logic_position_rfq_{item.key()}",
                    )

        st.subheader("Mögliche Duplikate")
        duplicate_event = None
        if duplicate_rows:
            duplicate_event = st.dataframe(
                pd.DataFrame(duplicate_rows),
                width="stretch",
                hide_index=True,
                height="stretch",
                column_config={
                    "Menge 1": st.column_config.NumberColumn(format="%.3f"),
                    "Menge 2": st.column_config.NumberColumn(format="%.3f"),
                    "Ähnlichkeit": st.column_config.NumberColumn(
                        format="%.0%"
                    ),
                },
                key="logic_duplicate_pairs_table",
                on_select="rerun",
                selection_mode="single-row",
            )
        else:
            st.caption("Keine möglichen Duplikate gefunden.")

        current_selections = {
            "logic_position_findings_table": (
                list(position_event.selection.rows)
                if position_event is not None else []
            ),
            "logic_duplicate_pairs_table": (
                list(duplicate_event.selection.rows)
                if duplicate_event is not None else []
            ),
        }
        previous_selections = st.session_state.get(
            "_logic_table_selections", {}
        )
        changed_selection = next(
            (
                (key, rows)
                for key, rows in current_selections.items()
                if rows and rows != previous_selections.get(key, [])
            ),
            None,
        )
        st.session_state["_logic_table_selections"] = current_selections
        if changed_selection is None:
            return

        table_key, selected_rows = changed_selection
        row_index = selected_rows[0]
        selected_items = (
            position_row_items
            if table_key == "logic_position_findings_table"
            else duplicate_row_items
        )
        if 0 <= row_index < len(selected_items):
            _open_position_details(
                selected_items[row_index],
                items,
                remarks,
                filename,
                calculated_by_key,
            )

    payloads = {}
    cluster_by_id = {cluster.cluster_id: cluster for cluster in cluster_list}
    for cluster in cluster_list:
        payload = {
            "cluster_id": cluster.cluster_id,
            "kind": cluster.kind,
            "title": cluster.title,
            "euro_exposure": cluster.euro_exposure,
            "positions": [
                {
                    "oz": (
                        item_by_key[oz].display_oz
                        if oz in item_by_key else oz
                    ),
                    "short_text": item_by_key[oz].short_text if oz in item_by_key else "",
                    "long_text": item_by_key[oz].long_text if oz in item_by_key else "",
                    "quantity": item_by_key[oz].quantity if oz in item_by_key else None,
                    "unit": item_by_key[oz].unit if oz in item_by_key else "",
                    "remarks": list(remarks),
                    "facts": (
                        {
                            "object_tag": facts_by_key[oz].object_tag,
                            "phase": facts_by_key[oz].phase,
                            "dn": facts_by_key[oz].dn,
                            "pn": facts_by_key[oz].pn,
                            "depth_m": facts_by_key[oz].depth_m,
                            "thickness_cm": facts_by_key[oz].thickness_cm,
                            "material": facts_by_key[oz].material,
                            "inclusive_terms": facts_by_key[oz].inclusive_terms,
                        }
                        if oz in facts_by_key
                        else {}
                    ),
                }
                for oz in cluster.positions
                if oz in item_by_key
            ],
        }
        payloads[cluster.cluster_id] = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )

    raw_evaluations = (
        evaluate_cluster_deep_cached(
            filename or "uploaded-tender",
            logic.RULES_VERSION,
            payloads,
        )
        if use_deep_logic
        else {}
    )

    rule_by_id = {rule.id: rule for rule in logic.RULES}
    cards = []
    for flag in cluster_flags:
        cluster = cluster_by_id.get(flag.cluster_id)
        rule = rule_by_id.get(flag.rule_id)
        cards.append({
            "source": "deterministic",
            "category": flag.rule_id,
            "title": flag.cluster_title,
            "analysis": flag.reason_de,
            "severity": flag.severity,
            "confidence": 1.0,
            "model": None,
            "computed": dict(flag.computed),
            "affected_ozs": [
                item_by_key[oz].display_oz if oz in item_by_key else oz
                for oz in flag.affected_positions
            ],
            "euro_exposure_estimate": (
                cluster.euro_exposure if cluster is not None else 0.0
            ),
            "din_ref": rule.din_ref if rule is not None else "",
            "cluster_id": flag.cluster_id,
        })

    for cluster_id, evaluation in raw_evaluations.items():
        if evaluation.get("offline") is True:
            continue
        if evaluation.get("contradiction_category") in (None, "", "NONE"):
            continue
        cluster = cluster_by_id.get(cluster_id)
        affected = evaluation.get("affected_positions") or (
            [
                item_by_key[oz].display_oz if oz in item_by_key else oz
                for oz in cluster.positions
            ]
            if cluster is not None else []
        )
        cards.append({
            "source": "llm",
            "category": evaluation.get("contradiction_category", "UNKNOWN"),
            "title": cluster.title if cluster is not None else cluster_id,
            "analysis": evaluation.get("reason_de") or "",
            "severity": evaluation.get("severity") or "medium",
            "confidence": float(evaluation.get("confidence") or 0.0),
            "model": evaluation.get("model") or "LLM",
            "computed": {},
            "affected_ozs": list(affected),
            "euro_exposure_estimate": (
                cluster.euro_exposure if cluster is not None else 0.0
            ),
            "din_ref": "",
            "cluster_id": cluster_id,
        })

    cards.sort(
        key=lambda card: (
            -float(card["euro_exposure_estimate"]),
            card["title"],
        )
    )
    deterministic_count = sum(
        1 for card in cards if card["source"] == "deterministic"
    )
    llm_count = sum(
        1 for card in cards if card["source"] == "llm"
    )

    calculated_by_display_oz = {
        calculated_item.item.display_oz: calculated_item
        for calculated_item in (calculated or [])
    }
    affected_ozs = {
        oz for card in cards for oz in card["affected_ozs"]
    }
    unique_position_exposure = sum(
        float(calculated_by_display_oz[oz].total or 0.0)
        for oz in affected_ozs
        if oz in calculated_by_display_oz
    )

    st.subheader("Cluster- & Systemprüfungen")
    a, b = st.columns(2)
    a.metric("Cluster-Befunde", len(cards))
    b.metric(
        "Summe EUR",
        f"€{unique_position_exposure:,.0f}",
        help="Kalkulationswert der betroffenen Positionen; jede OZ wird nur "
             "einmal gezählt. Summe der eindeutigen betroffenen Positionen.",
    )
    c, d = st.columns(2)
    jev_enabled = bool(st.session_state.get("use_jev", False))
    llm_available = not isinstance(
        deep_logic.get_adapter(),
        deep_logic.OfflineAdapter,
    )
    llm_help = (
        "Deterministisch = Beanstandungen durch feste DIN-/VOB-Regeln; "
        "LLM = Beanstandungen durch die optionale KI-Tiefenprüfung. "
    )
    if not use_deep_logic:
        llm_help += "Die Cluster-Tiefenprüfung ist deaktiviert."
    else:
        llm_help += (
            "Die Cluster-Tiefenprüfung ist aktiviert."
            if llm_available
            else "Die Cluster-Tiefenprüfung läuft ohne LLM im Offline-Modus."
        )
    if not llm_available:
        llm_help += " Kein LLM-API-Key bzw. kein nutzbarer LLM-Adapter gesetzt."
    llm_help += (
        " Die separate Jev-Top-60-Prüfung (use_jev) ist "
        f"{'aktiv' if jev_enabled else 'deaktiviert'}."
    )
    c.metric(
        "Deterministisch vs. LLM",
        f"{deterministic_count} vs. {llm_count}",
        help=llm_help,
    )
    d.metric(
        "Geprüfte Cluster",
        len(cluster_list),
        help="Anzahl der gebildeten Cluster. Für die LLM-Prüfung werden "
             "höchstens 12 Cluster nach Euro-Exposure priorisiert.",
    )

    if not cards:
        st.success(
            f"Keine Cluster-Widersprüche gefunden. "
            f"{len(cluster_list)} Cluster wurden geprueft."
        )
        render_position_findings()
        return

    if "rfi_cluster_questions" not in st.session_state:
        st.session_state["rfi_cluster_questions"] = []

    for index, card in enumerate(cards):
        with st.container(border=True):
            top_left, top_right = st.columns([5, 2])
            top_left.markdown(f"**{card['title']}**")
            top_right.caption(f"€ {card['euro_exposure_estimate']:,.2f}")
            st.badge(card["category"], icon="⚠️")

            if card["source"] == "deterministic":
                st.caption("🔒 Deterministisch")
            else:
                confidence = card["confidence"]
                st.caption(
                    f"{card['model']} · Confidence {confidence:.0%}"
                )

            st.write(card["analysis"])
            with st.expander("Analyse und betroffene Positionen"):
                st.markdown("**Technische Einordnung**")
                st.write(card["analysis"])

                st.markdown("**Rechenweg**")
                computed = card["computed"]
                if computed:
                    st.dataframe(
                        pd.DataFrame([
                            {"Kennzahl": str(key), "Wert": str(value)}
                            for key, value in computed.items()
                        ]),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.caption("Keine deterministische Zwischenrechnung vorhanden.")

                st.markdown("**Kaufmännische Bedeutung**")
                st.write(
                    f"Geschätzter Wert des betroffenen Clusters: "
                    f"€ {card['euro_exposure_estimate']:,.2f}"
                    + (
                        f" · {card['din_ref']}"
                        if card["din_ref"]
                        else ""
                    )
                )

                affected_rows = []
                for oz in card["affected_ozs"]:
                    item = item_by_key.get(oz) or item_by_display_oz.get(oz)
                    if item is None:
                        continue
                    calculated_item = calculated_by_display_oz.get(item.display_oz)
                    euro = (
                        float(calculated_item.total or 0.0)
                        if calculated_item is not None
                        else 0.0
                    )
                    affected_rows.append({
                        "OZ": item.display_oz,
                        "Kurztext": item.short_text,
                        "Menge": item.quantity,
                        "Einheit": constants.normalize_unit(item.unit),
                        "EUR": round(euro, 2),
                    })
                if affected_rows:
                    st.dataframe(
                        pd.DataFrame(affected_rows),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.caption("Keine betroffenen OZ hinterlegt.")

            rfi_column, rfq_column = st.columns(2)
            with rfi_column:
                _render_action_button(
                    "selected_rfis",
                    _cluster_action_entry(card, "RFI"),
                    "Als Bieterfrage übernehmen",
                    "✓ Als Bieterfrage übernommen",
                    "Bieterfrage wurde für den Export vorgemerkt.",
                    f"rfi_cluster_{card['cluster_id']}_{index}",
                )
            with rfq_column:
                _render_action_button(
                    "selected_rfqs",
                    _cluster_action_entry(card, "RFQ"),
                    "Als Nachunternehmen weiterleiten",
                    "✓ Für NU-Anfrage vorgemerkt",
                    "Cluster wurde für die Nachunternehmer-Anfrage vorgemerkt.",
                    f"rfq_cluster_{card['cluster_id']}_{index}",
                )

    render_position_findings()


def _render_risk_entry(item, result, calculated_item, items, remarks,
                       filename, calculated_by_key):
    """One flagged position: why it is flagged, what to price, what to send."""
    badge = {"high": "hoch", "medium": "mittel"}.get(result.risk_level, "—")
    header = (f"{badge.upper()} · OZ {item.display_oz} · "
              f"€{result.euro_exposure:,.0f} · {item.short_text[:60]}")

    with st.expander(header):
        reasons = list(result.reasons)
        if result.judgments and result.judgments.reasons:
            reasons += list(result.judgments.reasons.values())

        st.markdown("**Warum diese Position auffällt**")
        if reasons:
            for reason in dict.fromkeys(reasons):
                st.markdown(f"- {reason}")
        else:
            st.caption("Keine Einzelbegründung — allein durch Wert priorisiert.")

        quantity = f"{item.quantity:,.3f}".replace(",", "X").replace(".", ",")
        st.caption(
            f"Menge {quantity.replace('X', '.')} {item.unit or '—'} · "
            f"vorläufiger EP €{result.pre_unit_price:,.2f} · "
            f"{result.strategy}"
        )

        nachtrag = (
            float(getattr(result.judgments, "nachtragspotenzial", 0.0) or 0.0)
            if result.judgments else 0.0
        )
        optionen = angebotstexte.preisoptionen(calculated_item, nachtrag)
        if optionen:
            st.markdown("**Preisvorschläge**")
            for option, column in zip(optionen, st.columns(len(optionen))):
                with column:
                    st.metric(
                        option.label + (" ✓" if option.empfohlen else ""),
                        f"€{option.ep:,.2f}",
                        f"GP €{option.gp:,.0f}",
                    )
                    st.caption(option.begruendung)
        else:
            st.caption(
                "Keine Preisvorschläge: Die Position konnte keiner Leistung "
                "zugeordnet werden."
            )

        st.markdown("**Anschreiben**")
        rfi_tab, rfq_tab = st.tabs(["An den Auftraggeber", "An Nachunternehmer"])
        for tab, builder, key in (
            (rfi_tab, angebotstexte.rfi_mail, "rfi"),
            (rfq_tab, angebotstexte.rfq_mail, "rfq"),
        ):
            with tab:
                mail = builder(item, calculated_item, reasons, filename)
                link = angebotstexte.mailto_link(mail)
                st.caption(f"Betreff: {mail['betreff']}")
                # st.code gives a copy button for free; the mailto link opens
                # the default client with everything prefilled.
                st.code(mail["body"], language=None)
                if link:
                    st.link_button("In E-Mail-Programm öffnen", link)
                else:
                    st.caption(
                        "Zu lang für einen Mail-Link — bitte den Text oben "
                        "kopieren."
                    )

        rfi_column, rfq_column = st.columns(2)
        reason_line = " | ".join(reasons)
        with rfi_column:
            _render_action_button(
                "selected_rfis",
                _position_action_entry(item, "RFI", reason_line,
                                       "Heikle Positionen",
                                       _severity_label(result.risk_level)),
                "Als Bieterfrage übernehmen", "✓ Als Bieterfrage übernommen",
                "Bieterfrage wurde für den Export vorgemerkt.",
                f"risk_entry_rfi_{item.key()}",
            )
        with rfq_column:
            _render_action_button(
                "selected_rfqs",
                _position_action_entry(item, "RFQ", reason_line,
                                       "Heikle Positionen",
                                       _severity_label(result.risk_level)),
                "Als NU-Anfrage vormerken", "✓ Für NU-Anfrage vorgemerkt",
                "Position wurde für die Nachunternehmer-Anfrage vorgemerkt.",
                f"risk_entry_rfq_{item.key()}",
            )


def section_hybrid_risky(
    items, hybrid_results, findings, remarks, filename, calculated,
):
    """Hybrid prioritized risk table and RFI export."""
    filtered = [
        result for result in hybrid_results
        if result.risk_level in ("high", "medium")
    ]
    high_count = sum(1 for r in filtered if r.risk_level == "high")
    medium_count = sum(1 for r in filtered if r.risk_level == "medium")
    positive = sorted(
        r.euro_exposure for r in hybrid_results if r.euro_exposure > 0
    )
    threshold = (
        pricer.percentile(positive, constants.HYBRID_EXPOSURE_PERCENTILE)
        if positive else constants.SEVERITY_HIGH_EUR
    )
    speculation_count = sum(
        1 for r in filtered if r.action_type == "SPECULATE_UP"
    )

    a, b, c, d = st.columns(4)
    a.metric("Positionen mit hohem Risiko", high_count)
    b.metric("Positionen mit mittlerem Risiko", medium_count)
    c.metric("Schwelle der obersten 10 %", f"€{threshold:,.2f}")
    d.metric("VOB/B-Nachtragskandidaten", speculation_count)

    filter_choice = st.segmented_control(
        "Filter",
        options=["Alle", "Hohes Risiko", "Mittleres Risiko", "VOB/B-Spekulation"],
        default="Alle",
        key="hybrid_risk_filter",
    )
    if filter_choice == "Hohes Risiko":
        filtered = [r for r in filtered if r.risk_level == "high"]
    elif filter_choice == "Mittleres Risiko":
        filtered = [r for r in filtered if r.risk_level == "medium"]
    elif filter_choice == "VOB/B-Spekulation":
        filtered = [r for r in filtered if r.action_type == "SPECULATE_UP"]

    filtered.sort(
        key=lambda r: (0 if r.risk_level == "high" else 1, -r.euro_exposure)
    )
    item_by_key = {item.key(): item for item in items}
    calculated_by_key = {c.item.key(): c for c in calculated}

    # One flat list of every flagged position is unreadable: the reason a
    # position is on it matters more than its rank. Group by the action the
    # estimator has to take, so each block is one decision he can work
    # through and close.
    groups: list[tuple[str, str, list]] = [
        ("Rückfrage an den Auftraggeber", "RFI",
         [r for r in filtered if r.action_type == "RFI"]),
        ("Anfrage an Nachunternehmer", "RFQ",
         [r for r in filtered if r.action_type == "RFQ"]),
        ("Nachtragspotenzial — bewusst bepreisen", "SPECULATE",
         [r for r in filtered
          if r.action_type in ("SPECULATE_UP", "SPECULATE_DOWN")]),
        ("Intern gegenprüfen", "CHECK",
         [r for r in filtered if r.action_type == "CHECK"]),
    ]
    tab_labels = [
        f"{title} ({len(entries)})" for title, _kind, entries in groups
    ]
    for tab, (title, _kind, entries) in zip(st.tabs(tab_labels), groups):
        with tab:
            if not entries:
                st.caption("Keine Position in dieser Gruppe.")
                continue
            summe = sum(r.euro_exposure for r in entries)
            st.caption(
                f"{len(entries)} Positionen · €{summe:,.0f} betroffen. "
                "Position anklicken für Begründung, Preisvorschläge und "
                "fertige Anschreiben."
            )
            for result in entries[:40]:
                item = item_by_key.get(result.key)
                if item is None:
                    continue
                _render_risk_entry(
                    item, result, calculated_by_key.get(result.key),
                    items, remarks, filename, calculated_by_key,
                )
    st.divider()
    # The flat table stays available — some people want to scan or sort all
    # of it — but collapsed and at a fixed height. Left open with
    # height="stretch" it grew into the expanders above and overlapped them.
    table_box = st.expander(
        f"Vollständige Tabelle aller {len(filtered)} bewerteten Positionen",
        expanded=False,
    )
    rows = []
    row_items = []
    row_results = []
    for result in filtered:
        item = item_by_key.get(result.key)
        if item is None:
            continue
        reasons = " | ".join(result.reasons)
        if result.judgments and result.judgments.reasons:
            reasons += " | KI: " + " | ".join(result.judgments.reasons.values())
        rows.append({
            "Risiko": _severity_label(result.risk_level),
            "OZ": item.display_oz,
            "Position": item.short_text[:58],
            "EP vorl.": round(result.pre_unit_price, 2),
            "€-Exposure": round(result.euro_exposure, 2),
            "Strategie": f"{result.action_type}: {result.strategy}",
            "KI- und Regelbegründung": reasons,
        })
        row_items.append(item)
        row_results.append(result)

    if rows:
        with table_box:
            event = st.dataframe(
                pd.DataFrame(rows),
                width="stretch",
                hide_index=True,
                height=420,
                key="risky_items_table",
                on_select="rerun",
                selection_mode="single-row",
            )
        selected_rows = list(event.selection.rows)
        previous_selection = st.session_state.get(
            "_risky_table_selection", []
        )
        st.session_state["_risky_table_selection"] = selected_rows
        calculated_by_key = {
            calculated_item.item.key(): calculated_item
            for calculated_item in calculated
        }
        if selected_rows:
            row_index = selected_rows[0]
            if 0 <= row_index < len(row_items):
                item = row_items[row_index]
                result = row_results[row_index]
                reason = " | ".join(result.reasons)
                st.caption(f"Aktionen für OZ {item.display_oz}")
                rfi_column, rfq_column = st.columns(2)
                with rfi_column:
                    _render_action_button(
                        "selected_rfis",
                        _position_action_entry(
                            item,
                            "RFI",
                            reason,
                            "Heikle Positionen",
                            _severity_label(result.risk_level),
                        ),
                        "Als Bieterfrage übernehmen",
                        "✓ Als Bieterfrage übernommen",
                        "Bieterfrage wurde für den Export vorgemerkt.",
                        f"risky_position_rfi_{item.key()}",
                    )
                with rfq_column:
                    _render_action_button(
                        "selected_rfqs",
                        _position_action_entry(
                            item,
                            "RFQ",
                            reason,
                            "Heikle Positionen",
                            _severity_label(result.risk_level),
                        ),
                        "Als Nachunternehmen weiterleiten",
                        "✓ Für NU-Anfrage vorgemerkt",
                        "Position wurde für die Nachunternehmer-Anfrage vorgemerkt.",
                        f"risky_position_rfq_{item.key()}",
                    )
                if selected_rows != previous_selection:
                    _open_position_details(
                        item,
                        items,
                        remarks,
                        filename,
                        calculated_by_key,
                    )
    else:
        st.success("Keine Position im gewählten Risiko-Filter.")

    st.divider()
    section_export(
        findings,
        cluster_evaluations=st.session_state.get("rfi_cluster_questions"),
    )


def section_tricky(calculated):
    """Show unpriced positions and material pricing risks."""
    st.caption(
        "Gezeigt werden nicht kalkulierbare Positionen, große Kostenspannen "
        "und Pauschalpositionen. Bezifferbare Risiken stehen nach €-Spanne "
        "sortiert; bei nicht kalkulierbaren Positionen ist der Betrag unbekannt."
    )
    rows = []
    for c in calculated:
        reasons = []
        if not c.priced:
            reasons.append("nicht kalkulierbar")
        elif c.band_width > 0.35:
            reasons.append(f"Preisspanne ±{100*c.band_width/2:.0f}%")
        if c.item.is_lump_sum:
            reasons.append("Pauschalposition")
        if not reasons:
            continue
        rows.append({
            "OZ": c.item.display_oz, "Position": c.item.short_text[:58],
            "Menge": c.item.quantity,
            "Einheit": constants.normalize_unit(c.item.unit),
            "€ unsicher": round(c.euro_at_stake, 2) if c.priced else None,
            "Grund": ", ".join(reasons),
            "_unpriced": not c.priced,
            "_band_width": c.band_width,
            "_lump_sum": c.item.is_lump_sum,
        })
    if not rows:
        st.success("Keine auffällig unsicheren Positionen.")
        return
    frame = pd.DataFrame(rows).sort_values(
        ["_unpriced", "€ unsicher", "_band_width", "_lump_sum"],
        ascending=[True, False, False, False],
    ).head(25)
    frame.insert(0, "Rang", range(1, len(frame) + 1))
    st.markdown(f"**Top {len(frame)} nach Risiko**")
    st.dataframe(
        frame.drop(columns=["_unpriced", "_band_width", "_lump_sum"]),
        width="stretch",
        hide_index=True,
        height="stretch",
    )


def section_export(findings, cluster_evaluations=None):
    """Download selected Bieterfragen and Nachunternehmer-Anfragen."""
    project_title = (
        "Export: Bieterfragen (VOB/A) & Nachunternehmer-Anfragen"
    )
    st.subheader(project_title)
    cluster_evaluations = [
        {
            **entry,
            "contradiction_category": (
                entry.get("contradiction_category") or entry.get("category")
            ),
            "cluster_title": (
                entry.get("cluster_title") or entry.get("title")
            ),
            "reason_de": (
                entry.get("question")
                or entry.get("reason_de")
                or entry.get("analysis")
            ),
        }
        for entry in (cluster_evaluations or [])
        if isinstance(entry, dict)
    ]
    import export_rfi
    project = {"title": project_title}
    catalog = export_rfi.build_catalog(
        findings or [],
        project,
        cluster_evaluations=cluster_evaluations,
    )

    def unique_selected_entries(state_key):
        entries = st.session_state.get(state_key, [])
        if not isinstance(entries, list):
            return []
        unique = []
        seen_ids = set()
        seen_ozs = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id") or entry.get("cluster_id")
            oz = entry.get("oz")
            if (
                (entry_id and entry_id in seen_ids)
                or (oz and oz in seen_ozs)
            ):
                continue
            if entry_id:
                seen_ids.add(entry_id)
            if oz:
                seen_ozs.add(oz)
            unique.append(entry)
        return unique

    selected_rfis = unique_selected_entries("selected_rfis")
    selected_rfqs = unique_selected_entries("selected_rfqs")
    legacy_cluster_ids = {
        str(entry.get("cluster_id"))
        for entry in cluster_evaluations
        if entry.get("cluster_id")
    }

    for state_key, entries in (
        ("selected_rfis", selected_rfis),
        ("selected_rfqs", selected_rfqs),
    ):
        for entry in entries:
            kind = entry.get("kind")
            cluster_id = entry.get("cluster_id")
            if (
                state_key == "selected_rfis"
                and kind == "cluster"
                and str(cluster_id) in legacy_cluster_ids
            ):
                continue

            action_group = (
                "rfq"
                if state_key == "selected_rfqs"
                else "cluster" if kind == "cluster" else "position"
            )
            affected_ozs = list(entry.get("affected_ozs") or [])
            oz = (
                ", ".join(str(value) for value in affected_ozs)
                if affected_ozs else str(entry.get("oz") or "—")
            )
            quantity = entry.get("quantity")
            try:
                quantity_text = f"{float(quantity):g}" if quantity is not None else ""
            except (TypeError, ValueError):
                quantity_text = str(quantity or "")
            try:
                exposure = float(
                    entry.get("euro_exposure_estimate")
                    or entry.get("euro_leverage")
                    or 0.0
                )
            except (TypeError, ValueError):
                exposure = 0.0
            catalog.append({
                "nr": 0,
                "id": entry.get("id"),
                "oz": oz,
                "kurztext": (
                    entry.get("short_text")
                    or entry.get("cluster_title")
                    or "Ausgewählte Position"
                ),
                "menge": quantity_text,
                "einheit": str(entry.get("unit") or ""),
                "detector": str(entry.get("action_type") or state_key),
                "severity": str(entry.get("severity") or "medium"),
                "euro_leverage": round(exposure, 2),
                "frage": str(
                    entry.get("question")
                    or entry.get("reason_de")
                    or "Bitte klären Sie die Angaben zu dieser Leistung."
                ),
                "cluster_title": str(entry.get("cluster_title") or ""),
                "din_ref": "",
                "affected_ozs": affected_ozs or [oz],
                "group": action_group,
            })

    for index, entry in enumerate(catalog, start=1):
        entry["nr"] = index

    if not catalog:
        st.download_button(
            "Export (.docx)",
            data=b"",
            file_name="Bieterfragen-und-NU-Anfragen.docx",
            disabled=True,
        )
        st.download_button(
            "Export (.md)",
            data=b"",
            file_name="Bieterfragen-und-NU-Anfragen.md",
            disabled=True,
        )
        st.caption("Es liegen keine exportierbaren Bieterfragen vor.")
        return

    markdown_payload = export_rfi.to_markdown(
        catalog, project
    ).encode("utf-8")
    st.download_button(
        "Export (.md)",
        data=markdown_payload,
        file_name="Bieterfragen-und-NU-Anfragen.md",
        mime="text/markdown",
        key="selected_questions_markdown_export",
    )

    out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            out_path = handle.name
        export_rfi.to_docx(catalog, out_path, project)
        with open(out_path, "rb") as handle:
            docx_payload = handle.read()
        st.download_button(
            "Export (.docx)",
            data=docx_payload,
            file_name="Bieterfragen-und-NU-Anfragen.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="selected_questions_docx_export",
        )
    except Exception as exc:
        st.warning("DOCX-Export nicht verfügbar; Markdown-Export ist bereit.")
        with st.expander("Exportdetails"):
            st.code(str(exc))
    finally:
        if out_path and os.path.exists(out_path):
            os.unlink(out_path)


def main():
    if "_persisted_session_restored" not in st.session_state:
        has_current_source = "source" in st.session_state
        has_current_page = "active_page" in st.session_state
        has_current_manual_prices = "manual_prices" in st.session_state
        has_current_vergabe = "vergabe_entscheidungen" in st.session_state
        has_current_selected_rfis = "selected_rfis" in st.session_state
        has_current_selected_rfqs = "selected_rfqs" in st.session_state
        has_current_cluster_questions = "rfi_cluster_questions" in st.session_state
        has_current_use_jev = "use_jev" in st.session_state
        has_current_use_deep_logic = "use_deep_logic" in st.session_state
        current_source = st.session_state.get("source")
        current_page = st.session_state.get("active_page")
        current_manual_prices = st.session_state.get("manual_prices")
        current_vergabe = st.session_state.get("vergabe_entscheidungen")
        current_selected_rfis = st.session_state.get("selected_rfis")
        current_selected_rfqs = st.session_state.get("selected_rfqs")
        current_cluster_questions = st.session_state.get("rfi_cluster_questions")
        current_use_jev = st.session_state.get("use_jev")
        current_use_deep_logic = st.session_state.get("use_deep_logic")
        session_store.restore(st.session_state)
        st.session_state["_persisted_session_restored"] = True
        if has_current_source:
            st.session_state["source"] = current_source
        else:
            st.session_state.pop("source", None)
        st.session_state["active_page"] = (
            current_page if has_current_page else "Tender"
        )
        st.session_state["manual_prices"] = (
            current_manual_prices if has_current_manual_prices else {}
        )
        st.session_state["vergabe_entscheidungen"] = (
            current_vergabe if has_current_vergabe else {}
        )
        st.session_state["selected_rfis"] = (
            current_selected_rfis if has_current_selected_rfis else []
        )
        st.session_state["selected_rfqs"] = (
            current_selected_rfqs if has_current_selected_rfqs else []
        )
        st.session_state["rfi_cluster_questions"] = (
            current_cluster_questions if has_current_cluster_questions else []
        )
        st.session_state.pop("selected_group_key", None)
        st.session_state.pop("opened_position_key", None)
        st.session_state["use_jev"] = (
            current_use_jev if has_current_use_jev else False
        )
        st.session_state["use_deep_logic"] = (
            current_use_deep_logic if has_current_use_deep_logic else False
        )
    st.session_state.setdefault("use_jev", False)
    st.session_state.setdefault("selected_rfis", [])
    st.session_state.setdefault("selected_rfqs", [])

    st.markdown(
        """
        <style>
        /* Keep the normal document flow. Earlier viewport-pinning made the
           end of long pages and export controls inaccessible on common laptop
           heights; this app has more content than a single viewport. */
        [data-testid="stMainBlockContainer"] {
            box-sizing: border-box;
            width: 100% !important;
            max-width: 100% !important;
            padding: 3.75rem clamp(0.75rem, 3vw, 3rem) 1.5rem !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stDataFrame"] {
            flex: 1 1 0% !important;
            width: 100% !important;
            height: 100% !important;
            min-height: 8rem !important;
        }
        [data-testid="stMainBlockContainer"] .st-key-group_list {
            flex: 1 1 0% !important;
            min-height: 8rem !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
            padding-right: 0.25rem;
        }
        [data-testid="stMainBlockContainer"] .st-key-group_list > * {
            flex-shrink: 0 !important;
        }

        /* Fluid type and spacing so the fixed part stays compact. */
        [data-testid="stMainBlockContainer"] h1 {
            margin: 0 !important;
            padding: 0 0 0.25rem !important;
            font-size: clamp(1.4rem, 2.2vw + 1dvh, 2.4rem) !important;
        }
        [data-testid="stMainBlockContainer"] h3 {
            padding: 0.25rem 0 !important;
        }
        [data-testid="stMetricValue"] {
            font-size: clamp(1.2rem, 2.4vw, 2.25rem) !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stMetric"] {
            padding: 0 !important;
            min-width: 0;
        }

        /* Columns wrap instead of overflowing on narrow screens. */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            min-width: min(100%, 11rem) !important;
        }

        /* Sidebar: its own scroll if the controls are taller than the window. */
        [data-testid="stSidebar"] {
            min-width: 15rem;
            max-width: 22rem;
        }
        [data-testid="stSidebarContent"] {
            overflow-y: auto !important;
        }
        [data-testid="stSidebar"] [data-testid="stButton"] > button[kind="secondary"] {
            border: 0;
            background: transparent;
            text-align: left;
            justify-content: flex-start;
        }

        /* Source-document dialog fits the viewport too. */
        [data-testid="stDialog"] iframe {
            height: min(600px, 62dvh) !important;
        }

        @media (max-width: 640px) {
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width: 100% !important;
            }
            .st-key-group_list [data-testid="stHorizontalBlock"] {
                gap: 0.25rem !important;
            }
        }
        @media (max-height: 700px) {
            [data-testid="stMainBlockContainer"] {
                padding-top: 3.25rem !important;
                padding-bottom: 0.4rem !important;
            }
            [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
            [data-testid="stCaptionContainer"] { margin: 0 !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("### Bid & Risk Assistant")
    st.sidebar.caption("Benutzermodus")
    active_page = st.session_state.get("active_page", PAGES[0])
    if active_page in ("Groups", "Das Angebot"):
        active_page = "Gruppen & Angebot"
        st.session_state["active_page"] = active_page
    for candidate in PAGES:
        if st.sidebar.button(
            candidate,
            key=f"navigate_{candidate}",
            type="primary" if candidate == active_page else "secondary",
            width="stretch",
        ):
            st.session_state["active_page"] = candidate
            st.rerun()

    page = st.session_state.get("active_page", PAGES[0])
    if page == "Logic":
        page = "Logik"
        st.session_state["active_page"] = page
    st.title(page)

    # The Jev deep check belongs on the page it affects, not in a global
    # sidebar: it only changes "Heikle Positionen" and "Logik", and a control
    # that does nothing on three of five pages reads as broken.
    # Streamlit drops widget state for any widget not rendered in a run, so a
    # page-local toggle would forget the choice the moment you navigate away.
    # The durable value lives in `use_jev`, which is never a widget key; the
    # toggle writes into it on change.
    st.session_state.setdefault("use_jev", False)
    if page == "Heikle Positionen":
        def _remember_jev() -> None:
            st.session_state["use_jev"] = st.session_state["use_jev_toggle"]

        st.toggle(
            "KI-Tiefenprüfung (Top 60 Risiko-Positionen)",
            value=bool(st.session_state["use_jev"]),
            key="use_jev_toggle",
            on_change=_remember_jev,
            help="Jev beurteilt die 60 risikoreichsten Positionen in fünf "
                 "Einzelfragen. Die deterministische Risikobewertung läuft "
                 "unabhängig davon und bleibt unverändert.",
        )
    use_jev = bool(st.session_state.get("use_jev", False))
    use_deep_logic = False
    if page == "Logik":
        st.session_state.setdefault("use_deep_logic", False)

        def _remember_deep_logic() -> None:
            st.session_state["use_deep_logic"] = (
                st.session_state["use_deep_logic_toggle"]
            )

        use_deep_logic = st.sidebar.toggle(
            "Cluster-Tiefenprüfung (Gemma 4)",
            value=bool(st.session_state["use_deep_logic"]),
            key="use_deep_logic_toggle",
            on_change=_remember_deep_logic,
            help="Prüft Cluster optional mit gemma-4-31B-it (deep_logic). "
                 "Deterministische Regeln laufen unabhängig davon.",
        )
        use_deep_logic = bool(st.session_state["use_deep_logic"])
    loaded = section_upload(show_controls=page == "Tender")
    if not loaded:
        return
    items, remarks, label = loaded

    company = sidebar_kalkulation()
    data = stammdaten.load()

    if page == "Tender":
        # The per-position breakdown lives here, beside the positions it
        # describes, so the group overview stays readable.
        assignments = classify.classify(items, data, use_jev=False)
        calculated = kalkulation.calculate(items, assignments, company, data)
        pdf_confidence = st.session_state.get("pdf_confidence")
        if pdf_confidence and label.lower().endswith(".pdf"):
            if pdf_confidence["usable"]:
                st.info(
                    f"PDF gelesen: {pdf_confidence['positions']} Positionen aus "
                    f"{pdf_confidence['oz_lines_seen']} Ordnungszahl-Zeilen "
                    f"({pdf_confidence['yield_pct']:.0f} % Ausbeute). "
                    "Mengen und Texte stammen aus der Druckdarstellung — "
                    "Preise im PDF werden bewusst ignoriert."
                )
            else:
                st.warning(
                    f"**Nur {pdf_confidence['positions']} von "
                    f"{pdf_confidence['oz_lines_seen']} Ordnungszahl-Zeilen "
                    f"wurden zu Positionen ({pdf_confidence['yield_pct']:.0f} % "
                    "Ausbeute).** Die Mengenspalte dieses PDFs ließ sich nicht "
                    "zuverlässig lesen. Das Angebot deckt damit nur einen Teil "
                    "des Leistungsverzeichnisses ab — bitte die GAEB-Datei "
                    "verwenden, falls vorhanden."
                )
        section_items(items, remarks, label)
        section_position_table(items, assignments, calculated, data, company)
        section_angebot_export(items, calculated, label)
    else:
        # Page navigation and pop-ups must be deterministic unless the user
        # explicitly starts a Jev deep check. Classification is cached, and
        # keyword fallback avoids surprise API calls on every rerun.
        assignments = classify.classify(items, data, use_jev=False)
        calculated = kalkulation.calculate(items, assignments, company, data)
        reference = load_reference()
        priced = pricer.price_boq(items, reference, {
            "mittellohn_eur_h": company.mittellohn_eur_h,
            "overhead_pct": company.total_markup_pct,
            "profit_pct": company.wg_pct,
        })
        calculated_payload = [{
            "key": c.item.key(),
            "ep_low": c.ep_low,
            "ep_mid": c.ep_mid,
            "ep_high": c.ep_high,
        } for c in calculated]
        priced_payload = [{
            "key": p.item.key(),
            "unit_price": p.unit_price,
            "total": p.total,
            "source": p.source,
            "comparables": p.comparables,
            "spread": p.spread,
            "bucket": p.bucket,
            "distribution": p.distribution,
            "note": p.note,
            "similarity_score": p.similarity_score,
        } for p in priced]
        item_dicts = [item.as_dict() for item in items]
        hybrid_use_jev = bool(
            use_jev
            and page in ("Logik", "Heikle Positionen")
        )
        model_signature = ""
        if hybrid_use_jev:
            model_signature = "|".join((
                classify.JEV_MODEL,
                deep_logic.ITEM_RFI_MODEL,
                deep_logic.get_adapter().name,
            ))
        analysis_session_key = lv_analysis_session_key(
            item_dicts,
            list(remarks),
            calculated_payload,
            priced_payload,
            hybrid_use_jev,
            model_signature,
        )
        analysis_session_cache = st.session_state.setdefault(
            "lv_hybrid_analysis_cache", {}
        )
        cached_hybrid = analysis_session_cache.get(analysis_session_key)
        if cached_hybrid is not None:
            hybrid_results, findings = cached_hybrid
        else:
            hybrid_results, findings = analyze_hybrid_cached(
                item_dicts,
                list(remarks),
                calculated_payload,
                priced_payload,
                hybrid_use_jev,
                HYBRID_ANALYSIS_CACHE_VERSION,
            )
            analysis_session_cache[analysis_session_key] = (
                hybrid_results,
                findings,
            )
        if page == "Gruppen & Angebot":
            cov = classify.coverage(assignments)
            entscheidungen = vergabe_view.gespeicherte_entscheidungen(label)
            vergabe_ergebnis = (
                vergabe.auswerten(
                    items,
                    assignments,
                    data,
                    calculated,
                    company,
                    entscheidungen,
                )
                if entscheidungen else None
            )
            section_kalkulation(
                items,
                assignments,
                calculated,
                cov,
                data,
                company,
                vergabe_ergebnis,
            )
            section_groups(
                items,
                assignments,
                data,
                label,
                remarks,
                calculated,
            )
        elif page == "Vergabe":
            vergabe_view.render(
                label,
                lambda entscheidungen: vergabe.auswerten(
                    items, assignments, data, calculated, company,
                    entscheidungen),
            )
        elif page == "Logik":
            section_logic(
                items,
                remarks,
                hybrid_results,
                findings,
                calculated=calculated,
                filename=label,
                use_deep_logic=use_deep_logic,
            )
        elif page == "Heikle Positionen":
            section_hybrid_risky(
                items,
                hybrid_results,
                findings,
                remarks,
                label,
                calculated,
            )

    session_store.persist(st.session_state)


main()
