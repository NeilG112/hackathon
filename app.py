"""Bid & Risk Assistant — Streamlit UI. Task 007.

    streamlit run app.py

> It reads a construction tender file, finds the line items that will cost the
> contractor money, and writes the clarification letter he'd otherwise spend
> four hours on.

Lead with that sentence. No vocabulary lesson, no file extensions.

Wired: upload -> parse -> item table, trade groups, bottom-up calculation,
benchmark cross-check, risk/logic findings, reveal and RFI export. Optional AI
checks are controlled separately from deterministic rules.

Fallbacks, in order: live parse -> `data/golden/` fixture -> an honest
"format not supported" with the sample loaded on a button. Degrade visibly
rather than fabricating output.
"""

from __future__ import annotations

import html
import json
import os
import re
import tempfile
import traceback
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from core import (classify, clusters, constants, deep_logic, detectors, facts,
                  kalkulation, logic, objects, parser_gaeb90, parser_x83, pricer,
                  risk_engine, session_store, stammdaten, vergabe)
from views import reveal
from views import vergabe as vergabe_view

SAMPLE = constants.REVEAL["blank_boq"]
ANSWER_KEY = constants.REVEAL["answer_key"]
PAGES = ("Tender", "Gruppen & Angebot", "Vergabe", "Logik", "Heikle Positionen")
HYBRID_ANALYSIS_CACHE_VERSION = "item-rfi-v1"

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
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

def parse_path(path: str):
    """Parse by format. Returns (items, remarks). Raises on unknown format."""
    suffix = os.path.splitext(path)[1].lower()
    if suffix in XML_SUFFIXES:
        return parser_x83.parse(path), parser_x83.parse_remarks(path)
    if suffix in GAEB90_SUFFIXES:
        return parser_gaeb90.parse(path), []
    raise ValueError(f"unsupported format: {suffix or path}")


@st.cache_data(show_spinner=False)
def load_from_disk(path: str):
    items, remarks = parse_path(path)
    return [i.as_dict() for i in items], remarks


@st.cache_data(show_spinner=False)
def load_from_upload(name: str, payload: bytes):
    """Parse uploaded bytes. Cached on content, so sliders don't re-parse."""
    suffix = os.path.splitext(name)[1] or ".x83"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        temp = handle.name
    try:
        items, remarks = parse_path(temp)
        return [i.as_dict() for i in items], remarks
    finally:
        os.unlink(temp)


@st.cache_data(show_spinner=False)
def load_reference():
    return pricer.load_reference_prices()


def rehydrate(dicts: list[dict]):
    from core.models import NormalizedItem
    return [NormalizedItem.from_dict(d) for d in dicts]


@st.cache_data(show_spinner=False)
def analyze_hybrid_cached(
    item_dicts: list[dict],
    remarks: list[str],
    calculated_payload: list[dict],
    priced_payload: list[dict],
    use_jev: bool,
    analysis_version: str,
):
    """Cache hybrid analysis; version invalidates results from older pipelines."""
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


@st.cache_data(show_spinner=False)
def evaluate_cluster_deep_cached(
    filename: str,
    rules_version: str,
    payloads: dict[str, str],
) -> dict[str, dict]:
    """Deep cluster cache key: filename + rule catalogue version + payload."""
    del filename
    adapter = deep_logic.get_adapter()
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
    return {
        cluster_id: {
            **evaluation.as_dict(),
            "model": model,
        }
        for cluster_id, evaluation in evaluations.items()
    }


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
        value = st.slider(
            label,
            min_value=min_value,
            max_value=max_value,
            value=float(st.session_state[slider_key]),
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
            value=float(st.session_state[number_key]),
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
                type=[s.lstrip(".") for s in XML_SUFFIXES + GAEB90_SUFFIXES],
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
            raw, remarks = load_from_disk(source[1])
            label = os.path.basename(source[1])
        else:
            raw, remarks = load_from_upload(source[1], source[2])
            label = source[1]
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


def section_items(items):
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
    st.dataframe(
        frame,
        column_config={
            "EP (€)": st.column_config.NumberColumn(format="€ %.2f"),
            "GP (€)": st.column_config.NumberColumn(format="€ %.2f"),
        },
        width="stretch",
        hide_index=True,
        height="stretch",
    )


def source_document(source):
    """Return the original file name and bytes for the active tender."""
    if source[0] == "upload":
        return source[1], source[2]
    with open(source[1], "rb") as handle:
        return os.path.basename(source[1]), handle.read()


@st.cache_data(show_spinner=False)
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


def section_groups(items, assignments, data, filename: str, remarks: list[str],
                   calculated=None, vergabe_ergebnis=None):
    """List trade groups; opening one shows the positions in that trade."""
    if "manual_prices" not in st.session_state:
        st.session_state["manual_prices"] = {}
    manual_prices = st.session_state["manual_prices"]
    calculated_by_key = {
        c.item.key(): c for c in (calculated or [])
    }
    rows = objects.by_trade(items, assignments, data, calculated)
    if calculated:
        stats = kalkulation.summarize(calculated)
        a, b, c = st.columns(3)
        if vergabe_ergebnis is not None:
            a.metric("Angebotssumme", f"€{vergabe_ergebnis.angebotssumme:,.0f}",
                     help="Inklusive der Entscheidungen auf der Seite Vergabe "
                          "(Nachunternehmerangebote ersetzen die eigene "
                          "Kalkulation des Gewerks).")
        else:
            a.metric("Angebotssumme", f"€{stats['total_mid']:,.0f}",
                     help="Mittelwert der Spanne")
        b.metric("Spanne", f"€{stats['total_low']:,.0f} – "
                 f"{stats['total_high']:,.0f}")
        c.metric("Kalkuliert", f"{stats['coverage_pct']:.0f}%",
                 help=f"{stats['unpriced']} Positionen ohne zugeordnete Leistung")

    item_by_key = {item.key(): item for item in items}

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
                    name.caption(f"{len(row.positions)} Positionen")
                    value = 0.0
                    for position_key in row.positions:
                        item = item_by_key.get(position_key)
                        if item is None:
                            continue
                        override = manual_prices.get(position_key)
                        if override:
                            value += override["gp"]
                        elif item.total_price is not None:
                            value += item.total_price
                        elif item.unit_price is not None:
                            value += item.unit_price * item.quantity
                        else:
                            estimate = calculated_by_key.get(position_key)
                            if estimate is not None:
                                value += estimate.total or 0.0
                    details.caption(
                        f"{row.unit or '—'} · Gesamt: €{value:,.2f}"
                    )
                    if action.button(
                        "Öffnen →",
                        key=f"open_group_{index}",
                        width="stretch",
                    ):
                        st.session_state["selected_group_key"] = row.key
                        st.session_state.pop("group_positions", None)
                        st.session_state.pop("opened_position_key", None)
                        st.rerun()
        return

    if st.button("← Alle Gruppen"):
        st.session_state.pop("selected_group_key", None)
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
            item = group_items[row_index]
            st.session_state["opened_position_key"] = item.key()
            source = st.session_state.get("source")
            payload = None
            source_error = None
            if source:
                try:
                    filename, payload = source_document(source)
                except OSError as exc:
                    filename = item.source_file or "Quelldokument"
                    source_error = str(exc)
            else:
                filename = item.source_file or "Quelldokument"
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


def section_kalkulation(calculated, cov, data):
    """Bottom-up Aufschlagskalkulation — the bid. Returns calculated items."""
    stats = kalkulation.summarize(calculated)

    a, b, c, d = st.columns(4)
    a.metric("Angebotssumme", f"€{stats['total_mid']:,.0f}",
             help="Mittelwert der Spanne")
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

    st.dataframe(pd.DataFrame([{
        "OZ": c.item.display_oz,
        "Position": c.item.short_text[:52],
        "Menge": c.item.quantity,
        "Einheit": constants.normalize_unit(c.item.unit),
        "Leistung": c.leistung.code if c.leistung else "—",
        "EP min": c.ep_low, "EP mittel": c.ep_mid, "EP max": c.ep_high,
        "GP": c.total,
        "Grundlage": c.note[:60],
    } for c in calculated]), width="stretch", hide_index=True, height="stretch")
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
    cluster_list = clusters.build_clusters(
        items,
        facts_by_key,
        calculated=calculated,
    )

    cluster_flags = logic.check_cluster_rules(
        cluster_list,
        items,
        facts_by_key,
        calculated=calculated,
        remarks=remarks,
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
    position_rows = []
    for item in items:
        result = position_results[item.key()]
        if not result.flags:
            continue
        position_rows.append({
            "OZ": item.display_oz,
            "Schweregrad": _severity_label(result.severity),
            "Regeln": ", ".join(result.flags),
            "Befund": " | ".join(result.details),
        })

    duplicate_findings = logic.check_duplicates(items, pre_prices)
    st.subheader("Positionsregeln und mögliche Duplikate")
    st.markdown("**Positionsbezogene Regeln**")
    if position_rows:
        st.dataframe(
            pd.DataFrame(position_rows),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Keine positionsbezogenen Regelbefunde.")

    st.markdown("**Mögliche Duplikate**")
    if duplicate_findings:
        st.dataframe(
            pd.DataFrame([{
                "OZ": finding.item.display_oz,
                "Vergleichspositionen": ", ".join(
                    item_by_key[key].display_oz
                    if key in item_by_key else key
                    for key in finding.evidence.get("positions", [])
                ),
                "Schweregrad": _severity_label(finding.severity),
                "EUR-Exposure": round(finding.euro_leverage, 2),
                "Befund": finding.rationale,
            } for finding in duplicate_findings]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Keine möglichen Duplikate gefunden.")

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

    a, b = st.columns(2)
    a.metric("Cluster-Befunde", len(cards))
    b.metric(
        "Summe EUR",
        f"€{unique_position_exposure:,.0f}",
        help="Kalkulationswert der betroffenen Positionen; jede OZ wird nur "
             "einmal gezählt.",
    )
    c, d = st.columns(2)
    c.metric("Deterministisch vs. LLM", f"{deterministic_count} vs. {llm_count}")
    d.metric("Geprüfte Cluster", len(cluster_list))

    if not cards:
        st.success(
            f"Keine Cluster-Widersprueche gefunden. "
            f"{len(cluster_list)} Cluster wurden geprueft."
        )
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

            if st.button(
                "Als Bieterfrage uebernehmen",
                key=f"rfi_cluster_{card['cluster_id']}_{index}",
            ):
                question = dict(card)
                question.update({
                    "contradiction_category": card["category"],
                    "cluster_title": card["title"],
                    "reason_de": card["analysis"],
                })
                question["affected_ozs"] = list(card["affected_ozs"])
                existing_ids = {
                    entry.get("cluster_id")
                    for entry in st.session_state["rfi_cluster_questions"]
                }
                if card["cluster_id"] not in existing_ids:
                    st.session_state["rfi_cluster_questions"].append(question)


def section_hybrid_risky(items, hybrid_results, findings):
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
    c.metric("Top-10-%-Schwelle", f"€{threshold:,.2f}")
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
    rows = []
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
            "KI- & Regel-Begründung": reasons,
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch",
                     hide_index=True, height="stretch")
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


def section_pricing(items, company, reference, priced=None):
    """Comparable-price cross-check. Secondary to the calculation above."""
    st.subheader("7 · Quercheck gegen echte Angebotspreise")
    st.caption(
        "A second, independent estimate from 720 unit prices in three real "
        "submitted bids. Where the two engines agree, confidence is higher; "
        "where they diverge, look. Measured on its own (answer key held out) "
        "this engine is −50% on the total, so it is a cross-check, not a bid."
    )
    if priced is None:
        priced = pricer.price_boq(items, reference, company)
    stats = pricer.summarize(priced)

    a, b, c, d = st.columns(4)
    a.metric("Estimated total", f"€{stats['total']:,.0f}")
    b.metric("Priced from real bids", f"{stats['benchmark_share_pct']:.0f}%")
    c.metric("No comparable", stats["no_comparable"],
             help="Positions we refuse to price rather than invent a number for.")
    d.metric("On fallback rates", f"€{stats['fallback_value']:,.0f}",
             help="Value resting on hand-authored rates, not observed prices.")

    frame = pd.DataFrame([{
        "OZ": p.item.display_oz,
        "Position": p.item.short_text[:60],
        "Menge": p.item.quantity,
        "Einheit": constants.normalize_unit(p.item.unit),
        "EP €": p.unit_price if p.unit_price is not None else None,
        "GP €": p.total if p.total is not None else None,
        "Quelle": {
            "benchmark_match": "matched comparable",
            "benchmark": "bucket median",
            "benchmark_unit": "unit median",
            "fallback_rate": "fallback rate",
            "none": constants.NO_COMPARABLE_LABEL,
        }[p.source],
        "Basis": p.note[:70],
    } for p in priced])
    st.dataframe(frame, width="stretch", hide_index=True, height=320)

    if stats["no_comparable"]:
        st.caption(
            f"{stats['no_comparable']} positions print "
            f"“{constants.NO_COMPARABLE_LABEL}”. These are mostly rental and "
            "time-on-site units with nothing comparable in the benchmark. "
            "An honest blank beats an invented euro."
        )
    return priced, stats


def section_findings(priced, remarks):
    """Top findings by € leverage. Lights up when task 004 lands."""
    st.subheader(f"8 · Top {constants.TOP_N_FINDINGS} positions worth arguing about")
    st.caption(
        "Ranked by € leverage (quantity × price exposure). Where no comparable "
        f"exists we print “{constants.NO_COMPARABLE_LABEL}” rather than invent a number."
    )
    try:
        findings = detectors.run_all(priced, remarks, top_n=constants.TOP_N_FINDINGS)
    except NotImplementedError:
        st.info(
            "Detectors are task 004 — not built yet. The pricing above is live; "
            "this panel fills in once `core/detectors.py` is implemented."
        )
        return []

    if not findings:
        st.success("No findings above the detection thresholds.")
        return []

    st.dataframe(pd.DataFrame([{
        "OZ": f.item.display_oz,
        "Position": f.item.short_text[:60],
        "Detector": f.detector,
        "Schweregrad": _severity_label(f.severity),
        "€ leverage": round(f.euro_leverage, 2),
        "Why": f.rationale,
    } for f in findings]), width="stretch", hide_index=True)
    return findings


def section_reveal(priced, answer, source_label):
    """The reveal. PLAN.md step 4 — this is the whole pitch."""
    st.subheader("9 · How wrong are we?")

    if answer is None:
        st.caption(
            "This tender has no submitted bid to check against. Load the sample "
            "tender to see the comparison that does."
        )
        return

    reveal.render(priced, answer, source_label)


def answer_key_for(label: str):
    """Find a real submitted bid to measure this tender against.

    Two cases exist. The demo blank has a known sibling bid for the same BoQ.
    A file the user uploads may itself be priced (.D84/.D86), in which case it
    is its own answer key — and must then be held out of the benchmark, or we
    would be checking our homework against our own source.
    """
    if label.startswith(os.path.basename(SAMPLE)):
        raw, _ = load_from_disk(ANSWER_KEY)
        return rehydrate(raw), os.path.basename(ANSWER_KEY), os.path.basename(ANSWER_KEY)

    for source in constants_sources():
        if label.startswith(os.path.basename(source)):
            raw, _ = load_from_disk(source)
            return rehydrate(raw), os.path.basename(source), os.path.basename(source)
    return None, "", ""


def constants_sources() -> list[str]:
    """The bids the benchmark was built from, per reference_prices.json."""
    return load_reference().get("meta", {}).get("sources", [])


def section_export(findings, cluster_evaluations=None):
    """Download a Bieterfragen catalogue from position or cluster findings."""
    st.subheader("10 · The letter")
    cluster_evaluations = [
        {
            **entry,
            "contradiction_category": (
                entry.get("contradiction_category") or entry.get("category")
            ),
            "cluster_title": (
                entry.get("cluster_title") or entry.get("title")
            ),
            "reason_de": entry.get("reason_de") or entry.get("analysis"),
        }
        for entry in (cluster_evaluations or [])
        if isinstance(entry, dict)
    ]
    if not findings and not cluster_evaluations:
        st.button("Export clarification letter (.docx)", disabled=True)
        st.caption("No findings are available for export.")
        return

    import export_rfi
    project = {"title": "Bieterfragen-Katalog"}
    catalog = export_rfi.build_catalog(
        findings or [],
        project,
        cluster_evaluations=cluster_evaluations,
    )
    if not catalog:
        st.button("Export clarification letter (.docx)", disabled=True)
        st.caption("No findings are available for export.")
        return

    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            out_path = handle.name
        export_rfi.to_docx(catalog, out_path, project)
        with open(out_path, "rb") as handle:
            payload = handle.read()
        os.unlink(out_path)
        st.download_button(
            "Export clarification letter (.docx)",
            data=payload,
            file_name="Bieterfragen-Katalog.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        fallback = export_rfi.to_markdown(catalog, project).encode("utf-8")
        st.warning("DOCX export is unavailable; the Markdown fallback is ready.")
        st.download_button(
            "Export clarification letter (.md)",
            data=fallback,
            file_name="Bieterfragen-Katalog.md",
            mime="text/markdown",
        )
        with st.expander("Export details"):
            st.code(str(exc))


def main():
    if "_persisted_session_restored" not in st.session_state:
        session_store.restore(st.session_state)
        st.session_state["_persisted_session_restored"] = True

    st.markdown(
        """
        <style>
        /* The page never scrolls: everything is pinned to the viewport. */
        html, body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"] {
            height: 100dvh !important;
            max-height: 100dvh !important;
            overflow: hidden !important;
        }
        [data-testid="stMain"] {
            height: 100dvh !important;
            min-width: 0 !important;
            overflow: hidden !important;
        }
        /* Main area is a flex column exactly one viewport tall. The top
           padding clears Streamlit's fixed header (Deploy / menu). */
        [data-testid="stMainBlockContainer"] {
            box-sizing: border-box;
            display: flex !important;
            flex-direction: column !important;
            width: 100% !important;
            max-width: 100% !important;
            height: 100dvh !important;
            min-height: 0 !important;
            overflow: hidden !important;
            padding: 3.75rem clamp(0.75rem, 3vw, 3rem) 0.75rem !important;
        }
        [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
            flex: 1 1 0% !important;
            min-height: 0 !important;
            gap: clamp(0.35rem, 1.2dvh, 1rem) !important;
            /* Last resort only: if the fixed header content cannot fit at
               all (tiny window), scroll inside the panel, never the page. */
            overflow-y: auto;
            overflow-x: hidden;
        }
        /* Fixed-size content keeps its natural height ... */
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > * {
            flex-shrink: 0;
        }
        /* Keep tab headers intrinsic; only their active panel takes leftover space. */
        [data-testid="stMainBlockContainer"] [data-testid="stTabs"] {
            flex: 1 1 0% !important;
            min-height: 8rem !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stTabs"] > div {
            display: flex;
            flex-direction: column;
            min-height: 0;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stTabs"] > div > [role="tablist"] {
            flex: 0 0 auto !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stTabs"] > div > [data-testid="stTabPanel"][role="tabpanel"] {
            flex: 1 1 0% !important;
            min-height: 0 !important;
            overflow-y: auto;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stTabs"] > div > [data-testid="stTabPanel"][role="tabpanel"] > [data-testid="stVerticalBlock"] {
            flex: 1 1 0% !important;
            min-height: 0 !important;
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
    use_jev = False
    use_deep_logic = False
    if page == "Logik":
        use_deep_logic = st.sidebar.checkbox(
            "Cluster-Tiefenprüfung (Gemma 4)",
            value=False,
            help="Prüft Cluster optional mit gemma-4-31B-it (deep_logic). "
                 "Deterministische Regeln laufen unabhängig davon.",
            key="use_deep_logic",
        )
    elif page == "Heikle Positionen":
        use_jev = st.sidebar.checkbox(
            "Jev-Risikotriage (Top 60 Positionen)",
            value=False,
            help="Übergibt die priorisierten Positionen optional an Jev. "
                 "Die Offline-Risikobewertung läuft unabhängig davon.",
            key="use_jev",
        )
    loaded = section_upload(show_controls=page == "Tender")
    if not loaded:
        return
    items, remarks, label = loaded

    if page == "Tender":
        section_items(items)
    else:
        company = sidebar_kalkulation()
        data = stammdaten.load()
        # No use_jev=False here: the cache still answers the prepared tender
        # offline, but an uploaded file is not in it and the keyword fallback
        # scores near zero on real wording — that is the 3% coverage bug.
        assignments = classify.classify(items, data)
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
        hybrid_results, findings = analyze_hybrid_cached(
            [item.as_dict() for item in items],
            list(remarks),
            calculated_payload,
            priced_payload,
            bool(use_jev),
            HYBRID_ANALYSIS_CACHE_VERSION,
        )
        if page == "Gruppen & Angebot":
            group_tab, calculation_tab, pricing_tab, reveal_tab = st.tabs([
                "Gewerke & Positionen",
                "Positionskalkulation",
                "Benchmark-Quercheck",
                "Angebots-Reveal",
            ])
            with group_tab:
                cov = classify.coverage(assignments)
                if cov["pct"] < 50:
                    st.warning(
                        f"Nur {cov['pct']}% der Positionen konnten einer "
                        "Leistung zugeordnet werden."
                    )
                entscheidungen = vergabe_view.gespeicherte_entscheidungen(label)
                section_groups(
                    items,
                    assignments,
                    data,
                    label,
                    remarks,
                    calculated,
                    vergabe.auswerten(
                        items, assignments, data, calculated, company,
                        entscheidungen,
                    ) if entscheidungen else None,
                )
            with calculation_tab:
                section_kalkulation(calculated, cov, data)
            pricing_company = {
                "mittellohn_eur_h": company.mittellohn_eur_h,
                "overhead_pct": company.total_markup_pct,
                "profit_pct": company.wg_pct,
            }
            with pricing_tab:
                section_pricing(
                    items,
                    pricing_company,
                    reference,
                    priced=priced,
                )
            with reveal_tab:
                answer, _answer_label, source_label = answer_key_for(label)
                section_reveal(priced, answer, source_label)
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
            section_hybrid_risky(items, hybrid_results, findings)

    session_store.persist(st.session_state)


main()
