# Project File Tree
```text
.gitignore
ai_engine.py
app.py
calculator.py
data/
  benchmarks/
    .gitkeep
  benchmarks.json
  raw_benchmarks/
    .gitkeep
    8209.003_Leistungsverzeichnis_leer.D83
    [ORT_024] LV24069.D86
    Abgabe LV.pdf
    Angebot AN24-0305.D84
    Angebot AN24-0305.pdf
    HEM2301-2_Gesamt-LV.pdf
    Leistungsverzeichnis.pdf
    Leistungsverzeichnis_leer.pdf
    LV-Ausdruck-[PROJEKT_004].pdf
    LV-Positionen.docx
    LV-Schachtbauwerk.pdf
    LV_00_Roh_und_Erdauarbeiten.pdf
    LV_01_Fertigteiltreppen.pdf
    LV_02_PVC_Fussbodenbelag.pdf
    LV_03_Malerarbeiten.pdf
    LV_04_Porenbetonfassade.pdf
    LV_05_[FIRMA_096].pdf
    LV_06_Kautschukboden.pdf
    LV_07_Teppichboden.pdf
    LV_08_Fliesen_und_Natursteinarbeiten.pdf
    LV_09_Porenbetondach.pdf
    LV_10_Stahlbetonfertigeile_Stuetzen_Binder.pdf
    LV_11_Stahlbetonfertigeile_Sandwichsockel.pdf
    LV_12_Dachabdichtung.pdf
    LV_13_ELT.pdf
    LV_14_Sanitaeranlage.pdf
    LV_14a_Betonkernaktivierung.pdf
    LV_14b_Dachentwaesserung.pdf
    LV_14c_Industriebodenheizung.pdf
    LV_15_Abdichtung_Aussenwaende.pdf
    LV_15a_Abdichtung_Bodenplatte_Buero.pdf
    LV_17_Trockenbau.pdf
    LV_18_Estrich.pdf
    LV_19_Sektionaltore_Stahltueren.pdf
    LV_20_Bodenbelagsarbeiten.pdf
    LV_21_Natursteinarbeiten.pdf
    LV_22_Schreinerarbeiten.pdf
    LV_23_Sanitaertrennwaende.pdf
    StBALV23040.D84
    StBALV23040.D86
exporter.py
frontend_demo/
  .prettierrc
  .vercel/
    output/
      config.json
      functions/
        __server.func/
          .vc-config.json
          _chunks/
            ssr-renderer.mjs
          _libs/
            @tanstack/
              react-router+[...].mjs
              router-core+[...].mjs
            h3+rou3+srvx.mjs
            h3-v2+rou3.mjs
            lucide-react.mjs
            tanstack__history.mjs
          _runtime.mjs
          _ssr/
            draft-rfi-BCcg_iVe.mjs
            empty-plugin-adapters-D9UWiqvJ.mjs
            router-Cdp50kSt.mjs
            routes-DvTkTdoK.mjs
            ssr.mjs
            start-5Z2QO8AU.mjs
          _tanstack-start-manifest_v-C1wz4kaJ.mjs
          index.mjs
      nitro.json
      static/
        assets/
          index-BcgHBPiW.js
          routes-iHJqnnMA.js
          styles-CMHoM8DC.css
        favicon.svg
  eslint.config.mjs
  migrations/
    auth/
      0001_auth.sql
  package.json
  public/
    favicon.svg
  scripts/
    install-page.html
    migrate.mjs
    migration-plan.mjs
    migration-plan.test.mjs
    sign-out-plan.mjs
    sign-out-plan.test.mjs
    write-atomic.mjs
    write-atomic.test.mjs
  src/
    lib/
      app-data/
        app-data.test.ts
        client.server.ts
        errors.ts
        index.ts
        login.ts
        readiness-schedule.test.ts
        readiness-schedule.ts
        readiness.ts
        server-only.ts
        types.ts
        use-connector-readiness.ts
      auth/
        client.ts
        email-password.ts
        gate-identity.server.ts
        gate-identity.test.ts
        gate-session-marker.ts
        gate-session.server.ts
        gates.tsx
        isolation.server.ts
        middleware.ts
        pglite-dialect.ts
        popup.server.ts
        preview.ts
        provider.tsx
        providers.ts
        server.ts
        sign-in-gate.test.ts
        sign-in-gate.ts
        use-current-user.ts
        verify.server.ts
      boq.ts
      db.ts
      draft-rfi.ts
      env.server.ts
      error-component.tsx
    router.tsx
    routes/
      __root.tsx
      index.tsx
    routeTree.gen.ts
    styles.css
  tsconfig.json
  vercel.json
  vite.config.ts
ingest_benchmarks.py
models.py
parser.py
README.md
requirements.txt
risk_engine.py
rules_engine.py
test_parser_gaeb.py
```

# Codebase

## `.gitignore`
````
# Secrets & Environment
.env
.env.*

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Frontend / Build
node_modules/
.vercel/
dist/

# OS
.DS_Store
Thumbs.db
uploads/

"search.exclude": {
	"**/node_modules": true,
	"**/.venv": true,
	"**/venv": true,
	"**/__pycache__": true,
	"**/dist": true,
	"**/uploads": true,
	"**/data": true,
	"**/*.D83": true,
	"**/*.D84": true,
	"**/*.D86": true,
	"**/*.X83": true,
	"**/*.pdf": true,
	"**/package-lock.json": true,
	"**/*.lock": true
}
````

## `ai_engine.py`
````py
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Tuple

import streamlit as st
from dotenv import load_dotenv

from models import AIItemResult, NormalizedItem

load_dotenv()

FALLBACK_REASON = "Unknown fallback"


def get_fallback_reason() -> str:
    return FALLBACK_REASON


def _safe_float(value, default=0.0):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def classify_construction_phase(hierarchy: str, text: str = "") -> str:
    section = f"{hierarchy} {text}".lower()
    if re.search(r"(?:^|[ /])01(?:[ .]|$)", section) or any(
        keyword in section
        for keyword in (
            "baustelleneinrichtung",
            "verkehrsregelung",
            "bauzaun",
            "beleuchtung",
            "si-ge-ko",
            "sigeko",
        )
    ):
        return "Baustelleneinrichtung"
    if any(
        keyword in section
        for keyword in ("begrün", "begru", "ansaat", "rasen", "oberboden", "pflanz")
    ) or (re.search(r"(?:^|[ /])02(?:[ .]|$)", section) and "rohr" not in section):
        if any(w in section for w in ("begrün", "begru", "ansaat", "rasen")):
            return "Erdarbeiten / Außenanlagen"
        return "Erdarbeiten"
    if re.search(r"(?:^|[ /])03(?:[ .]|$)", section) or any(
        keyword in section
        for keyword in (
            "stahlbetonrohr",
            "uhpc",
            "schacht",
            "kanalrohr",
            "einlaufbauwerk",
            "tangential",
        )
    ):
        return "Rohrleitungsbau"
    if re.search(r"(?:^|[ /])04(?:[ .]|$)", section) or "stundenlohn" in section:
        return "Stundenlohnarbeiten"
    if any(keyword in section for keyword in ("asphalt", "pflaster", "bordstein", "frostschutz")):
        return "Straßenbau"
    if any(keyword in section for keyword in ("rohbau", "beton", "stahlbeton", "mauer")):
        return "Rohbau"
    return "Allgemein"


def _build_rfi_rfq_drafts(
    item: NormalizedItem,
    risks: List[str],
    rfi_question: str,
    text_lower: str,
) -> tuple[str, str]:
    risk_details = (
        "; ".join(risk for risk in risks[:5])
        if risks
        else "Keine eindeutigen Schnittstellenrisiken erkannt"
    )
    interface_note = ""
    if "bauseits" in text_lower:
        interface_note = (
            " Bitte klären Sie die Schnittstelle/Anbindung bauseits zu liefernder Komponenten,"
            " Montageverantwortung und Leistungsübergabe."
        )
    extra_q = f"\nKonkrete Rückfrage: {rfi_question}" if rfi_question else ""
    rfi = (
        f"Sehr geehrte Damen und Herren,\n\n"
        f"für Position {item.oz} ({item.short_text}) bitten wir um Bestätigung des Leistungsumfangs und "
        f"der Mengenbasis. Folgende Risikohinweise bestehen: {risk_details}.{interface_note}{extra_q}\n"
        f"Bitte nennen Sie Annahme/Ausführung, Schnittstellen, bauseitige Leistungen und erforderliche Detailunterlagen."
        f"\n\nMit freundlichen Grüßen"
    )
    clean_short = re.sub(
        r"\[(?:PERSON|FIRMA|TELEFON|ORT|PROJEKT|[A-Z]+)_[^\]]*\]",
        "[...]",
        item.short_text or "",
    )
    clean_long = re.sub(
        r"\[(?:PERSON|FIRMA|TELEFON|ORT|PROJEKT|[A-Z]+)_[^\]]*\]",
        "[...]",
        item.long_text or item.short_text or "",
    )
    rfq = (
        f"Sehr geehrte Damen und Herren,\n\n"
        f"bitte erstellen Sie ein Angebot für Position {item.oz}: {clean_short}. "
        f"Beschreibung: {clean_long}. "
        f"Menge: {item.qty:g} {item.unit}. Bitte Ausschlüsse, Lieferzeit und Leistungen getrennt aufführen."
        f"\n\nMit freundlichen Grüßen"
    )
    return rfi, rfq


def fallback_analyze(item: NormalizedItem) -> AIItemResult:
    raw_text = f"{item.short_text} {item.long_text}".lower()
    text = re.sub(r"\[(?:PERSON|FIRMA|TELEFON|ORT|PROJEKT|[A-Z]+)_[^]]*\]", "", raw_text).replace("[...]", "")
    risks = []
    unit = (item.unit or "").lower().replace(" ", "").replace(".", "")

    # 1. Gewerk / Kolonne priorisiert bestimmen (Landschafts-/Erdbau vor generischem 'rohr' im Kontext)
    crew = "general"
    if any(k in text for k in ("polier", "vorarbeiter")):
        crew = "foreman"
    elif any(k in text for k in ("begrün", "begru", "ansaat", "rasen", "oberboden", "feinplanum", "erd", "boden", "aushub", "bagger", "verfüll")):
        crew = "earthworks"
    elif any(k in text for k in ("pflaster", "asphalt", "bordstein", "fräsen", "fugenband", "bankett")):
        crew = "paving"
    elif any(k in text for k in ("rohr", "leitung", "kanal", "schacht", "kupplung", "uhpc")):
        crew = "pipe_crew"
    elif any(k in text for k in ("montage", "fitter", "stahl", "gerüst")):
        crew = "fitter"

    vague = (
        "nach vorgabe",
        "bauseits",
        "o.ä.",
        "ggf.",
        "pauschal",
        "nach aufwand",
        "wie angeordnet",
        "nach weis",
    )
    found_vague = [phrase for phrase in vague if phrase in text]
    if found_vague:
        risks.append("Vage Beschreibung: " + ", ".join(found_vague))

    if item.qty > 0:
        if unit in ("m²", "m2", "qm") and item.qty >= 1000:
            risks.append("Prüfung empfohlen: große Flächenmenge")
        if unit in ("stk", "stück", "st") and item.qty >= 200:
            risks.append("Prüfung empfohlen: sehr hohe Stückzahl")

    specialist = any(
        k in text for k in ("komplett", "gesamte", "anlage", "raumsystem", "nach vorgabe", "wasserhaltung", "statische berechnung")
    )
    if not item.long_text or len(item.long_text) < 20:
        if unit in ("psch", "pauschal", "ls"):
            specialist = True

    base = {
        "foreman": (1.0, 0.0, 0.0),
        "earthworks": (0.35, 0.25, 8.0),
        "pipe_crew": (0.55, 0.12, 18.0),
        "paving": (0.45, 0.18, 22.0),
        "fitter": (0.65, 0.05, 30.0),
        "general": (0.30, 0.02, 12.0),
    }
    labor, machine, material = base[crew]

    # 2. Stundenlohn- und Gerätestunden-Positionen sauber ohne Materialaufschlag rechnen
    if unit in ("std", "h", "stunde", "stunden"):
        material = 0.0
        is_machine = any(
            k in text
            for k in ("bagger", "minibagger", "mini-bagger", "lkw", "transporter", "radlader", "walze", "raupe", "kran")
        )
        with_driver = any(k in text for k in ("fahrer", "maschinist", "bedienung", "inkl"))
        if is_machine:
            labor = 1.0 if with_driver else 0.0
            if "mini" in text or "transporter" in text:
                machine = 0.65
            elif "lkw" in text:
                machine = 0.85
            else:
                machine = 1.15
        else:
            labor = 1.0
            machine = 0.0
    elif unit in ("m", "lfm"):
        labor *= 0.8
    elif unit in ("stk", "stück", "st"):
        labor = 1.25
        machine = 0.05
        material = max(material, 25.0)
    elif unit in ("psch", "pauschal", "ls"):
        labor = 8.0
        machine = 1.0 if any(k in text for k in ("anlage", "montage", "wasserhaltung", "einricht")) else 0.0
        material = max(material, 150.0)

    material_cost_estimate = None
    dn_match = re.search(r"\b(?:dn|nennweite)\s*([0-9]{3,4})\b", text)
    dn = int(dn_match.group(1)) if dn_match else 0
    if unit in ("m", "lfm") and (
        dn >= 300
        or any(k in text for k in ("uhpc", "stahlbetonrohr", "kanalrohr", "betonrohr"))
    ):
        if "uhpc" in text or dn >= 800:
            material_cost_estimate = 350.0
        elif dn >= 600:
            material_cost_estimate = 220.0
        elif dn >= 400:
            material_cost_estimate = 160.0
        else:
            material_cost_estimate = 95.0
        material = material_cost_estimate
    elif unit in ("stk", "stück", "st") and any(
        k in text for k in ("tangentialschacht", "schacht", "einlaufbauwerk", "fertigteil")
    ):
        if "einlaufbauwerk" in text:
            material_cost_estimate = 4200.0
        elif "tangential" in text:
            material_cost_estimate = 4000.0
        elif "abdeckung" in text:
            material_cost_estimate = 280.0
        else:
            material_cost_estimate = 1800.0
        material = material_cost_estimate
        labor = max(labor, 2.0)
        machine = max(machine, 0.5)

    tactic = "STANDARD"
    if "eventual" in text or item.item_type in ("Eventual", "Bedarf"):
        tactic = "LOW_EVENTUAL"
    elif any(k in text for k in ("hochbau", "gelände", "untersuchung")):
        tactic = "HIGH_SPECULATE"

    phase = classify_construction_phase(item.hierarchy, text)
    if specialist and phase == "Allgemein":
        phase = "TGA/Spezial"
    change_potential = (
        "hoch" if specialist or risks else ("mittel" if tactic != "STANDARD" else "niedrig")
    )

    tier_low = tier_mid = tier_high = None
    rationale = ""
    if specialist:
        scale = item.qty if item.qty > 0 else 1.0
        tier_low = round(scale * (labor * 58 + machine * 90 + material) * 0.85, 2)
        tier_mid = round(scale * (labor * 58 + machine * 90 + material), 2)
        tier_high = round(scale * (labor * 58 + machine * 90 + material) * 1.25, 2)
        rationale = (
            "Marktklassifizierung ohne bindendes Angebot: Leistungsumfang vor Auswahl bestätigen."
        )
        risks.append("Spezialist oder unklare Leistung: Marktpreis-Tiers erforderlich")

    risks = list(dict.fromkeys(risks))
    rfi_question = ""
    if specialist or "nach beigefügter zeichnung" in text or "beiliegender zeichnung" in text:
        rfi_question = (
            f"Bitte bestätigen Sie für Position {item.oz} die bauseitige Schnittstellenzuständigkeit, "
            "Montage-/Anschlussdetails sowie die maßgebende technische Zeichnung und den geforderten Hersteller."
        )
    elif "oder gleichwertiger hersteller" in text:
        rfi_question = (
            f"Für Position {item.oz}: Welcher Mindeststandard und welche technischen Merkmale sind für "
            "den Hersteller-/Gleichwertigkeitsnachweis verbindlich?"
        )
    elif "bauseits" in text:
        rfi_question = (
            f"Für Position {item.oz}: Welche Leistungen werden bauseits bereitgestellt (z. B. Anschlüsse, "
            "Montagefläche, Strom/Wasser), und ab welchem Übergabepunkt übernimmt der Auftragnehmer?"
        )
    elif any(word in text for word in ("bodenklasse", "grundwasser", "schichtwasser", "erdklasse")):
        rfi_question = (
            f"Für Position {item.oz}: Bitte bestätigen Sie Boden-/Grundwasserklasse, Baugrunddaten und "
            "die für die Kalkulation anzusetzenden Schutz-, Verbau- oder Entsorgungsmaßnahmen."
        )

    rfi, rfq = _build_rfi_rfq_drafts(item, risks, rfi_question, text)
    if material_cost_estimate is None and material > 0:
        material_cost_estimate = round(material, 2)

    return AIItemResult(
        oz=item.oz,
        crew_type=crew,
        labor_hours_per_unit=round(labor, 3),
        machine_hours_per_unit=round(machine, 3),
        base_material_cost_per_unit=round(material, 2),
        material_or_subcontract_cost_per_unit=round(material, 2),
        material_cost_estimate=round(material_cost_estimate, 2) if material_cost_estimate else None,
        errors_and_risks=risks,
        suggested_tactic=tactic,
        is_specialist_or_unclear=specialist,
        tier_low=tier_low,
        tier_mid=tier_mid,
        tier_high=tier_high,
        tier_rationale=rationale,
        client_rfi_draft=rfi,
        subcontractor_rfq_draft=rfq,
        confidence=0.62 if not specialist and not risks else 0.45,
        construction_phase=phase,
        change_order_potential=change_potential,
        rfi_question=rfi_question,
    )


def _extract_json_rows(raw_content: str) -> list[dict]:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_content or "", flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
            return parsed["items"]
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Partial-JSON-Recovery, falls der Output abgeschnitten wurde
    recovered = []
    for match in re.finditer(r"\{[^{}]*\"key\"\s*:\s*\"[^\"]+\"[^{}]*\}", cleaned):
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict) and "key" in obj:
                recovered.append(obj)
        except json.JSONDecodeError:
            continue
    return recovered


@st.cache_data(show_spinner=False)
def analyze_items(
    items: Iterable,
    batch_size: int = 6,
    target_keys: Optional[Tuple[str, ...]] = None,
) -> Dict[str, AIItemResult]:
    global FALLBACK_REASON
    normalized: List[NormalizedItem] = []
    for x in items:
        if isinstance(x, tuple):
            values = list(x)
            if len(values) >= 8:
                normalized.append(
                    NormalizedItem(
                        oz=values[0],
                        hierarchy=values[1],
                        short_text=values[2],
                        long_text=values[3],
                        qty=values[4],
                        unit=values[5],
                        item_type=values[6],
                        source_file=values[7],
                        reference_unit_price=values[8] if len(values) > 8 else None,
                        data_defects=list(values[9]) if len(values) > 9 and values[9] else [],
                        xml_id=values[10] if len(values) > 10 else "",
                        context_from_previous_item=values[11] if len(values) > 11 else "",
                        remarks=list(values[12]) if len(values) > 12 and values[12] else [],
                        project_metadata=list(values[13]) if len(values) > 13 and values[13] else [],
                    )
                )
        else:
            normalized.append(x)

    if not normalized:
        return {}

    results: Dict[str, AIItemResult] = {}
    target_set = set(target_keys) if target_keys is not None else None
    llm_indexed_items: List[Tuple[int, NormalizedItem]] = []

    for index, item in enumerate(normalized):
        key = f"{index}|{item.oz}"
        if target_set is not None and key not in target_set:
            results[key] = fallback_analyze(item)
        else:
            llm_indexed_items.append((index, item))

    api_key = os.getenv("MORPHEUS_API_KEY")
    base_url = os.getenv("MORPHEUS_BASE_URL", "https://api.morpheusai.com/v1")
    model = os.getenv("MORPHEUS_MODEL", "morpheus")

    if not api_key or not llm_indexed_items:
        if not api_key:
            FALLBACK_REASON = "Missing MORPHEUS_API_KEY"
        for index, item in llm_indexed_items:
            results[f"{index}|{item.oz}"] = fallback_analyze(item)
        return results

    item_lookup: Dict[str, NormalizedItem] = {
        f"{index}|{item.oz}": item for index, item in llm_indexed_items
    }

    # Maximal 6 Positionen pro Call verhindern max_tokens-Abbrüche und Timeouts
    effective_batch_size = min(6, max(1, int(batch_size)))

    def make_batches(
        indexed_list: List[Tuple[int, NormalizedItem]],
        b_size: int,
    ) -> List[List[Tuple[int, NormalizedItem]]]:
        batches: List[List[Tuple[int, NormalizedItem]]] = []
        current: List[Tuple[int, NormalizedItem]] = []
        chars = 0
        for idx, item in indexed_list:
            item_chars = len(item.short_text or "") + len((item.long_text or "")[:550])
            if current and (len(current) >= b_size or chars + item_chars > 7500):
                batches.append(current)
                current = []
                chars = 0
            current.append((idx, item))
            chars += item_chars
        if current:
            batches.append(current)
        return batches

    def _call_llm_batch(batch: List[Tuple[int, NormalizedItem]]) -> Dict[str, AIItemResult]:
        from openai import OpenAI

        payload = [
            {
                "key": f"{idx}|{item.oz}",
                "oz": item.oz,
                "unit": item.unit,
                "qty": item.qty,
                "short_text": (item.short_text or "")[:300],
                "long_text": (item.long_text or "")[:550],
            }
            for idx, item in batch
        ]

        # Kompaktes Output-Schema (ohne lange Brieftexte -> 70 % weniger Output-Tokens)
        prompt = (
            'Analysiere diesen GAEB-Batch kompakt. Antworte NUR als JSON {"items": [...]}.\n'
            "Felder je Item: key, crew_type (general|earthworks|pipe_crew|paving|fitter|foreman), "
            "labor_hours_per_unit, machine_hours_per_unit, base_material_cost_per_unit, "
            "errors_and_risks (max 3 kurze Strings), is_specialist_or_unclear (bool), "
            "tier_low, tier_mid, tier_high, rfi_question (1 kurzer Satz oder ''), "
            "confidence (0..1), construction_phase, change_order_potential (niedrig|mittel|hoch).\n"
            + json.dumps(payload, ensure_ascii=False)
        )

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0, max_retries=0)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein deutscher Baukalkulator. Antworte kompakt und ausschließlich mit gültigem JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2200,
            response_format={"type": "json_object"},
        )
        rows = _extract_json_rows(response.choices[0].message.content)
        batch_results: Dict[str, AIItemResult] = {}
        for row in rows:
            key = str(row.get("key", ""))
            item = item_lookup.get(key)
            if item is not None:
                fallback = fallback_analyze(item)
                merged_risks = list(
                    dict.fromkeys(list(row.get("errors_and_risks") or []) + fallback.errors_and_risks)
                )
                rfi_q = str(row.get("rfi_question") or fallback.rfi_question)
                rfi, rfq = _build_rfi_rfq_drafts(
                    item,
                    merged_risks,
                    rfi_q,
                    f"{item.short_text} {item.long_text}".lower(),
                )
                mat_val = _safe_float(
                    row.get("base_material_cost_per_unit"),
                    fallback.base_material_cost_per_unit,
                )
                batch_results[key] = AIItemResult(
                    oz=item.oz,
                    crew_type=str(row.get("crew_type", fallback.crew_type)),
                    labor_hours_per_unit=_safe_float(
                        row.get("labor_hours_per_unit"), fallback.labor_hours_per_unit
                    ),
                    machine_hours_per_unit=_safe_float(
                        row.get("machine_hours_per_unit"), fallback.machine_hours_per_unit
                    ),
                    base_material_cost_per_unit=mat_val,
                    material_or_subcontract_cost_per_unit=mat_val,
                    material_cost_estimate=mat_val if mat_val > 0 else fallback.material_cost_estimate,
                    errors_and_risks=merged_risks,
                    suggested_tactic=fallback.suggested_tactic,
                    is_specialist_or_unclear=bool(
                        row.get("is_specialist_or_unclear", fallback.is_specialist_or_unclear)
                    ),
                    tier_low=(
                        _safe_float(row.get("tier_low"), fallback.tier_low)
                        if row.get("tier_low") is not None
                        else fallback.tier_low
                    ),
                    tier_mid=(
                        _safe_float(row.get("tier_mid"), fallback.tier_mid)
                        if row.get("tier_mid") is not None
                        else fallback.tier_mid
                    ),
                    tier_high=(
                        _safe_float(row.get("tier_high"), fallback.tier_high)
                        if row.get("tier_high") is not None
                        else fallback.tier_high
                    ),
                    tier_rationale=fallback.tier_rationale,
                    rfi_question=rfi_q,
                    client_rfi_draft=rfi,
                    subcontractor_rfq_draft=rfq,
                    confidence=min(
                        1.0, max(0.0, _safe_float(row.get("confidence"), fallback.confidence))
                    ),
                    construction_phase=str(
                        row.get("construction_phase", fallback.construction_phase)
                    ),
                    change_order_potential=str(
                        row.get("change_order_potential", fallback.change_order_potential)
                    ).lower(),
                )
        return batch_results

    def process_batch(batch: List[Tuple[int, NormalizedItem]]) -> Dict[str, AIItemResult]:
        try:
            res = _call_llm_batch(batch)
            # Fehlende Items im Batch sauber mit Fallback auffüllen
            for idx, item in batch:
                k = f"{idx}|{item.oz}"
                if k not in res:
                    res[k] = fallback_analyze(item)
            return res
        except Exception as exc:
            # Bei Timeout einmalig mit halbiertem Batch wiederholen
            if len(batch) > 2:
                mid = len(batch) // 2
                try:
                    res = {}
                    res.update(_call_llm_batch(batch[:mid]))
                    res.update(_call_llm_batch(batch[mid:]))
                    for idx, item in batch:
                        k = f"{idx}|{item.oz}"
                        if k not in res:
                            res[k] = fallback_analyze(item)
                    return res
                except Exception:
                    pass

            fallback_map: Dict[str, AIItemResult] = {}
            for idx, item in batch:
                key = f"{idx}|{item.oz}"
                fb = fallback_analyze(item)
                fb.errors_and_risks.append(f"LLM-Timeout-Fallback ({type(exc).__name__})")
                fallback_map[key] = fb
            return fallback_map

    batches = make_batches(llm_indexed_items, effective_batch_size)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_batch, b) for b in batches]
        for future in as_completed(futures):
            results.update(future.result())

    for index, item in llm_indexed_items:
        key = f"{index}|{item.oz}"
        if key not in results:
            results[key] = fallback_analyze(item)

    return results
````

## `app.py`
````py
import hashlib
import inspect
import io
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
import pandas as pd
import streamlit as st

from ai_engine import analyze_items, get_fallback_reason
from calculator import calculate_items, project_quantity_plausibility, project_time
from exporter import export_x84, export_xlsx
from parser import (
    extract_project_metadata,
    extract_project_quantities,
    parse_benchmarks,
    parse_boq,
)
from risk_engine import calculate_risk, select_top_llm_keys
from rules_engine import compute_category_sums, run_logic_engine


st.set_page_config(page_title="AI Estimation & Bidding Assistant", layout="wide")
st.title("AI Estimation and Bidding Assistant")
st.caption("Challenge A — Bills of Quantities")

DATA_DIR = Path("data")
BENCHMARK_DIR = DATA_DIR / "benchmarks"
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_FILE = DATA_DIR / "benchmarks.json"
RATES_FILE = DATA_DIR / "company_rates.json"

COMPANY_PRESETS = {
    "Tief- & Kanalbau (Standard)": {
        "labor_rate": 58.0,
        "machine_rate": 92.0,
        "material_index": 1.00,
        "agk_pct": 12.0,
        "bgk_pct": 8.5,
        "wg_pct": 6.0,
    },
    "Hoch- & Rohbau": {
        "labor_rate": 56.0,
        "machine_rate": 75.0,
        "material_index": 1.00,
        "agk_pct": 11.5,
        "bgk_pct": 8.0,
        "wg_pct": 5.5,
    },
    "Spezialtiefbau": {
        "labor_rate": 64.0,
        "machine_rate": 135.0,
        "material_index": 1.05,
        "agk_pct": 14.0,
        "bgk_pct": 10.0,
        "wg_pct": 7.5,
    },
    "Generalunternehmer (GU)": {
        "labor_rate": 60.0,
        "machine_rate": 80.0,
        "material_index": 1.02,
        "agk_pct": 10.0,
        "bgk_pct": 9.0,
        "wg_pct": 5.0,
    },
}

CREW_MULTIPLIERS = {
    "general": ("Allgemeine Kolonne", 1.00),
    "earthworks": ("Erdbau-Kolonne", 0.95),
    "pipe_crew": ("Rohrleitungsbau-Kolonne", 1.05),
    "paving": ("Straßen- & Pflasterkolonne", 1.00),
    "fitter": ("Montage- / Stahlbaukolonne", 1.12),
    "foreman": ("Vorarbeiter / Polier", 1.17),
}

FLAG_EXPLANATIONS = {
    "META_MISMATCH": "Pauschalposition hat eine Menge ungleich 1 (Abrechnungs-/Mengenfehler)",
    "ZERO_QTY": "Normalposition ohne positive Menge (0 oder negativ)",
    "QTY_OUTLIER": "Ungewöhnlich hohe Menge – Verdacht auf Zahlendreher oder Kommafehler",
    "MISSING_SPEC": "Komplexe Leistungsposition ohne ausreichenden Langtext",
    "SCOPE_GAP": "Reine Materiallieferung ohne zugehörige Montage-/Einbauposition",
    "CATEGORY_MISMATCH": "Fläche der Fußbodenheizung übersteigt gesamte Bodenfläche im LV",
    "MISSING_FOLLOW_UP": "Fehlende Folgeposition im Gewerk (z. B. Aushub ohne Verfüllung oder Beton ohne Schalung/Bewehrung)",
}


class CrewRatesDict(dict):
    """Dict für Kolonnensätze mit automatischem Fallback auf 'general'."""

    def __missing__(self, key):
        return self.get("general", 58.0)


def build_default_crew_rates(base_labor_rate: float) -> CrewRatesDict:
    return CrewRatesDict(
        {
            crew_key: round(base_labor_rate * mult, 2)
            for crew_key, (_, mult) in CREW_MULTIPLIERS.items()
        }
    )


def load_company_rates() -> dict:
    default_rates = COMPANY_PRESETS["Tief- & Kanalbau (Standard)"].copy()
    if RATES_FILE.exists():
        try:
            saved = json.loads(RATES_FILE.read_text(encoding="utf-8"))
            default_rates.update({k: float(v) for k, v in saved.items() if k in default_rates})
        except Exception:
            pass
    return default_rates


def save_company_rates(rates: dict) -> None:
    RATES_FILE.write_text(json.dumps(rates, indent=2, ensure_ascii=False), encoding="utf-8")


@st.cache_data(show_spinner=False)
def load_valid_benchmarks(bench_path_str: str):
    target = Path(bench_path_str)
    if not target.exists():
        return []
    bms = parse_benchmarks(target)
    return [b for b in bms if not getattr(b, "is_outlier", False)]


def _read_num(obj, names, default: float = 0.0) -> float:
    for attr in names:
        val = obj.get(attr) if isinstance(obj, dict) else getattr(obj, attr, None)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return default


def _sanitize_item_flags(item, raw_flags: list[str]) -> list[str]:
    """Entfernt projektweite Erdbau-Summenwarnungen von fachfremden Positionen (z. B. Geotextil, Frostschutz)."""
    desc = f"{getattr(item, 'short_text', '')} {getattr(item, 'long_text', '')}".lower()
    is_earth_related = any(
        kw in desc for kw in ("aushub", "verfüll", "graben", "erd", "boden", "abfuhr", "kippe")
    )
    cleaned = []
    for f in raw_flags or []:
        fl = f.lower()
        if "verfüllung im verhältnis zum aushub" in fl and not is_earth_related:
            continue
        cleaned.append(f)
    return list(dict.fromkeys(cleaned))


def extract_prices_and_ekt(
    p_item,
    fallback_qty: float = 0.0,
    ai_res=None,
    crew_rates=None,
    machine_rate: float = 92.0,
    material_index: float = 1.0,
    agk_pct: float = 12.0,
    bgk_pct: float = 8.5,
    wg_pct: float = 6.0,
) -> tuple[float, float, float]:
    """
    Liefert (ekt, ep, gp) mit garantierter Selbstkosten-Invariante:
    EP >= EKT * (1 + (AGK% + BGK% + W&G%) / 100) in 100 % aller Positionen.
    """
    ekt = _read_num(
        p_item,
        ("ekt", "direct_cost", "direct_unit_cost", "herstellkosten", "unit_cost"),
        0.0,
    )
    ep = _read_num(
        p_item,
        (
            "final_unit_price",
            "unit_price",
            "up",
            "suggested_unit_price",
            "estimated_unit_price",
            "net_unit_price",
            "calculated_unit_price",
            "ep",
            "price",
        ),
        0.0,
    )

    if ekt == 0.0 and ai_res is not None:
        lh = float(getattr(ai_res, "labor_hours_per_unit", 0.0) or 0.0)
        mh = float(getattr(ai_res, "machine_hours_per_unit", 0.0) or 0.0)
        mat = float(
            getattr(ai_res, "material_or_subcontract_cost_per_unit", None)
            or getattr(ai_res, "base_material_cost_per_unit", 0.0)
            or 0.0
        )
        c_type = getattr(ai_res, "crew_type", "general") or "general"
        c_rate = crew_rates[c_type] if crew_rates is not None else 58.0
        ekt = round((lh * c_rate) + (mh * machine_rate) + (mat * material_index), 2)

    markup_factor = 1.0 + (agk_pct + bgk_pct + wg_pct) / 100.0

    # Wenn kein EKT vorlag, aber ein valider EP (z. B. Benchmark), EKT konsistent rückrechnen
    if ekt == 0.0 and ep > 0.0:
        ekt = round(ep / markup_factor, 2)

    # Invariante erzwingen: EP darf niemals unter den Einzelkosten (EKT) liegen
    min_valid_ep = round(ekt * markup_factor, 2)
    if ep == 0.0 or ep < ekt or abs(ep - min_valid_ep) > 0.02 and ep < min_valid_ep:
        ep = min_valid_ep

    gp = round(ep * fallback_qty, 2) if fallback_qty > 0.0 else 0.0
    return ekt, ep, gp


def sync_priced_item_object(p_item, ekt: float, ep: float, gp: float):
    """Aktualisiert auch das PricedItem-Objekt für GAEB-.X84- und Excel-Exporte."""
    if isinstance(p_item, dict):
        p_item["ekt"] = ekt
        p_item["unit_price"] = ep
        p_item["final_unit_price"] = ep
        p_item["total_price"] = gp
        p_item["final_total_price"] = gp
        return p_item

    for attr in ("ekt", "direct_cost", "unit_cost"):
        if hasattr(p_item, attr):
            try:
                setattr(p_item, attr, ekt)
            except Exception:
                pass
    for attr in ("unit_price", "final_unit_price", "up", "net_unit_price"):
        if hasattr(p_item, attr):
            try:
                setattr(p_item, attr, ep)
            except Exception:
                pass
    for attr in ("total_price", "final_total_price", "it", "net_total_price"):
        if hasattr(p_item, attr):
            try:
                setattr(p_item, attr, gp)
            except Exception:
                pass
    return p_item


def evaluate_actual_review(item, sanitized_flags: list[str], risk: dict, ai_res) -> tuple[bool, str, list[str]]:
    """
    Trennt echtes fachliches Risiko vom reinen LLM-Preisschätz-Budget:
    Nur Positionen mit echten Risiko-Signalen erscheinen in der Review-Queue.
    """
    categories = []
    reasons = []

    for flag in sanitized_flags:
        code = flag.split(":", 1)[0].strip()
        categories.append(code)
        readable = FLAG_EXPLANATIONS.get(code)
        reasons.append(f"{readable} ({flag})" if readable else flag)

    desc = f"{getattr(item, 'short_text', '')} {getattr(item, 'long_text', '')}".lower()
    vague_hits = [
        kw
        for kw in (
            "bauseits",
            "nach vorgabe",
            "komplettanlage",
            "pauschal",
            "nach aufwand",
            "o.ä.",
            "ggf.",
            "wie angeordnet",
            "wasserhaltung",
            "statische berechnung",
            "sonderkonstruktion",
        )
        if kw in desc
    ]
    if vague_hits:
        categories.append("VAGE_SPEZIAL")
        reasons.append(f"Unklare/vage Leistungsbeschreibung (Signalwörter: {', '.join(vague_hits)})")

    if getattr(item, "item_type", "Normal") in ("Bedarf", "Eventual"):
        categories.append("BEDARFS_POS")
        reasons.append(f"VOB/A {item.item_type}-Position (nicht in Hauptangebotssumme enthalten)")

    if ai_res is not None:
        for ai_risk in getattr(ai_res, "errors_and_risks", []) or []:
            if "timeout-fallback" in ai_risk.lower() or "api error" in ai_risk.lower():
                continue
            if ai_risk not in reasons and not any(ai_risk in r for r in reasons):
                reasons.append(ai_risk)

    has_real_risk = bool(reasons) or risk.get("risk_score", "").lower() == "high"
    if has_real_risk:
        if not reasons:
            reasons.append("Sonder-/Pauschalposition mit erhöhtem Nachtrags- oder Schnittstellenrisiko")
        return True, " | ".join(reasons), list(dict.fromkeys(categories)) or ["SONDERPOSITION"]

    crew_label = CREW_MULTIPLIERS.get(
        getattr(ai_res, "crew_type", "general") if ai_res else "general",
        ("Standardkolonne", 1.0),
    )[0]
    approval_reason = (
        f"Auto-Approved: Eindeutiger Leistungstext, plausible Menge ({item.qty:g} {item.unit}), "
        f"keine Regel-Flags, kalkuliert über {crew_label}."
    )
    return False, approval_reason, ["APPROVED"]


def build_formula_excel(
    enriched_rows: list[dict],
    agk_pct: float,
    bgk_pct: float,
    wg_pct: float,
    main_net: float,
    optional_net: float,
) -> bytes:
    """
    Erzeugt eine saubere Excel-Kalkulation mit:
    - Echten Excel-Formeln (=EKT*(1+Zuschläge) und =Menge*EP)
    - Konsistenter Prozent-Fußzeile (AGK %, BGK %, W&G %)
    - VOB/A-konformer Trennung von Hauptangebot und Bedarfs-/Eventualpositionen
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kalkulation"

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    sub_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    bold_font = Font(bold=True)
    white_bold = Font(bold=True, color="FFFFFF")

    # Parameter-Block oben (Zeilen 1–5) für transparente Formeln
    ws["A1"] = "Kalkulations-Parameter"
    ws["A1"].font = bold_font
    ws["B2"] = "AGK-Zuschlag"
    ws["C2"] = round(agk_pct / 100.0, 4)
    ws["C2"].number_format = "0.0%"
    ws["B3"] = "BGK-Zuschlag"
    ws["C3"] = round(bgk_pct / 100.0, 4)
    ws["C3"].number_format = "0.0%"
    ws["B4"] = "Wagnis & Gewinn (W&G)"
    ws["C4"] = round(wg_pct / 100.0, 4)
    ws["C4"].number_format = "0.0%"
    ws["B5"] = "Gesamtzuschlag auf EKT"
    ws["C5"] = "=SUM(C2:C4)"
    ws["C5"].number_format = "0.0%"
    ws["C5"].font = bold_font

    headers = [
        "OZ",
        "Gewerk / Titel",
        "Kurztext",
        "Typ",
        "Menge",
        "Einheit",
        "EKT (€/Einh.)",
        "EP (€/Einh.)",
        "Gesamt (€)",
        "Status",
    ]
    start_row = 7
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col_idx, value=h)
        cell.font = white_bold
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center" if col_idx in (1, 4, 5, 6, 10) else "left")

    normal_rows = [r for r in enriched_rows if r["item"].item_type == "Normal"]
    optional_rows = [r for r in enriched_rows if r["item"].item_type != "Normal"]

    curr = start_row + 1
    first_normal = curr
    for r in normal_rows:
        it = r["item"]
        ws.cell(row=curr, column=1, value=it.oz)
        ws.cell(row=curr, column=2, value=it.hierarchy)
        ws.cell(row=curr, column=3, value=it.short_text)
        ws.cell(row=curr, column=4, value=it.item_type)
        ws.cell(row=curr, column=5, value=float(it.qty or 0.0)).number_format = "#,##0.00"
        ws.cell(row=curr, column=6, value=it.unit)
        ws.cell(row=curr, column=7, value=float(r["ekt"])).number_format = "#,##0.00 €"
        # EP = ROUND(EKT * (1 + Gesamtzuschlag), 2) -> garantiert EP >= EKT
        ep_cell = ws.cell(row=curr, column=8, value=f"=ROUND(G{curr}*(1+$C$5),2)")
        ep_cell.number_format = "#,##0.00 €"
        # Gesamt = ROUND(Menge * EP, 2)
        gp_cell = ws.cell(row=curr, column=9, value=f"=ROUND(E{curr}*H{curr},2)")
        gp_cell.number_format = "#,##0.00 €"
        ws.cell(row=curr, column=10, value="Review" if r["needs_review"] else "Auto-Approved")
        curr += 1
    last_normal = curr - 1

    # Hauptangebot-Fußzeile (nach VOB/A ohne Bedarfspositionen)
    curr += 1
    sum_row = curr
    ws.cell(row=sum_row, column=3, value="Summe Einzelkosten (EKT) Hauptangebot").font = bold_font
    if last_normal >= first_normal:
        ws.cell(
            row=sum_row,
            column=9,
            value=f"=SUMPRODUCT(E{first_normal}:E{last_normal},G{first_normal}:G{last_normal})",
        ).number_format = "#,##0.00 €"
    else:
        ws.cell(row=sum_row, column=9, value=0.0).number_format = "#,##0.00 €"

    curr += 1
    ws.cell(row=curr, column=3, value="AGK-Zuschlag (%)")
    ws.cell(row=curr, column=8, value="=C2").number_format = "0.0%"
    ws.cell(row=curr, column=9, value=f"=ROUND(I{sum_row}*H{curr},2)").number_format = "#,##0.00 €"

    curr += 1
    ws.cell(row=curr, column=3, value="BGK-Zuschlag (%)")
    ws.cell(row=curr, column=8, value="=C3").number_format = "0.0%"
    ws.cell(row=curr, column=9, value=f"=ROUND(I{sum_row}*H{curr},2)").number_format = "#,##0.00 €"

    curr += 1
    ws.cell(row=curr, column=3, value="Wagnis & Gewinn (%)")
    ws.cell(row=curr, column=8, value="=C4").number_format = "0.0%"
    ws.cell(row=curr, column=9, value=f"=ROUND(I{sum_row}*H{curr},2)").number_format = "#,##0.00 €"

    curr += 1
    main_total_row = curr
    ws.cell(row=main_total_row, column=3, value="Angebotssumme Netto (Hauptangebot ohne Bedarf)").font = bold_font
    ws.cell(row=main_total_row, column=3).fill = sub_fill
    tot_cell = ws.cell(
        row=main_total_row,
        column=9,
        value=f"=SUM(I{first_normal}:I{last_normal})" if last_normal >= first_normal else 0.0,
    )
    tot_cell.font = bold_font
    tot_cell.fill = sub_fill
    tot_cell.number_format = "#,##0.00 €"

    # Getrennter Abschnitt für Bedarfs- / Eventualpositionen (nachrichtlich VOB/A)
    if optional_rows:
        curr += 2
        ws.cell(row=curr, column=3, value="Bedarfs- & Eventualpositionen (nachrichtlich VOB/A – nicht in Hauptsumme)").font = bold_font
        curr += 1
        first_opt = curr
        for r in optional_rows:
            it = r["item"]
            ws.cell(row=curr, column=1, value=it.oz)
            ws.cell(row=curr, column=2, value=it.hierarchy)
            ws.cell(row=curr, column=3, value=it.short_text)
            ws.cell(row=curr, column=4, value=it.item_type)
            ws.cell(row=curr, column=5, value=float(it.qty or 0.0)).number_format = "#,##0.00"
            ws.cell(row=curr, column=6, value=it.unit)
            ws.cell(row=curr, column=7, value=float(r["ekt"])).number_format = "#,##0.00 €"
            ws.cell(row=curr, column=8, value=f"=ROUND(G{curr}*(1+$C$5),2)").number_format = "#,##0.00 €"
            ws.cell(row=curr, column=9, value=f"=ROUND(E{curr}*H{curr},2)").number_format = "#,##0.00 €"
            ws.cell(row=curr, column=10, value="Bedarf / Optional")
            curr += 1
        last_opt = curr - 1
        ws.cell(row=curr, column=3, value="Summe Bedarfs-/Eventualpositionen Netto (nachrichtlich)").font = bold_font
        opt_sum = ws.cell(row=curr, column=9, value=f"=SUM(I{first_opt}:I{last_opt})")
        opt_sum.font = bold_font
        opt_sum.number_format = "#,##0.00 €"

    widths = {1: 14, 2: 28, 3: 52, 4: 11, 5: 12, 6: 10, 7: 15, 8: 15, 9: 16, 10: 16}
    for col_idx, width in widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


if "company_rates" not in st.session_state:
    st.session_state["company_rates"] = load_company_rates()

# --- SIDEBAR ---
with st.sidebar:
    morpheus_active = bool(os.getenv("MORPHEUS_API_KEY"))
    if morpheus_active:
        st.success("Morpheus AI: aktiv")
    else:
        st.warning("Morpheus AI: Regelbasierter Fallback")

    st.subheader("1. Firmen-Stammdaten & Zuschläge")
    preset_choice = st.selectbox(
        "Unternehmensprofil (Vorlage)",
        options=["Benutzerdefiniert"] + list(COMPANY_PRESETS.keys()),
        index=0,
    )
    if preset_choice != "Benutzerdefiniert":
        if st.button("Vorlage übernehmen", use_container_width=True):
            st.session_state["company_rates"] = COMPANY_PRESETS[preset_choice].copy()
            save_company_rates(st.session_state["company_rates"])

    rates = st.session_state["company_rates"]
    labor_rate = st.number_input(
        "Mittellohn Basis (€/h)",
        min_value=20.0,
        max_value=150.0,
        value=float(rates["labor_rate"]),
        step=1.0,
    )
    machine_rate = st.number_input(
        "Maschinenstundensatz (€/h)",
        min_value=10.0,
        max_value=500.0,
        value=float(rates["machine_rate"]),
        step=5.0,
    )
    material_index = st.number_input(
        "Materialpreis-Index (1.00 = 100%)",
        min_value=0.50,
        max_value=2.50,
        value=float(rates["material_index"]),
        step=0.02,
    )
    col_z1, col_z2, col_z3 = st.columns(3)
    agk_pct = col_z1.number_input(
        "AGK %", min_value=0.0, max_value=40.0, value=float(rates["agk_pct"]), step=0.5
    )
    bgk_pct = col_z2.number_input(
        "BGK %", min_value=0.0, max_value=40.0, value=float(rates["bgk_pct"]), step=0.5
    )
    wg_pct = col_z3.number_input(
        "W&G %", min_value=0.0, max_value=40.0, value=float(rates["wg_pct"]), step=0.5
    )

    crew_size = st.number_input(
        "Standard-Kolonnenstärke (Personen)",
        min_value=1,
        max_value=50,
        value=4,
        step=1,
    )

    default_crews = build_default_crew_rates(labor_rate)
    crew_rates = CrewRatesDict()
    with st.expander("Kolonnen-Stundensätze (€/h)", expanded=False):
        for crew_key, (crew_label, _) in CREW_MULTIPLIERS.items():
            crew_rates[crew_key] = st.number_input(
                crew_label,
                min_value=20.0,
                max_value=200.0,
                value=float(default_crews[crew_key]),
                step=0.5,
                key=f"crew_{crew_key}_{labor_rate}",
            )

    current_rates = {
        "labor_rate": labor_rate,
        "machine_rate": machine_rate,
        "material_index": material_index,
        "agk_pct": agk_pct,
        "bgk_pct": bgk_pct,
        "wg_pct": wg_pct,
    }
    if current_rates != st.session_state["company_rates"]:
        st.session_state["company_rates"] = current_rates
        save_company_rates(current_rates)

    scenario = st.radio(
        "What-If Bietstrategie",
        options=["Standard (100%)", "Aggressiv (-5% W&G/Index)", "Defensiv (+10% Puffer)"],
        index=0,
    )
    eff_material_index = material_index
    eff_wg_pct = wg_pct
    if scenario.startswith("Aggressiv"):
        eff_material_index = round(material_index * 0.95, 3)
        eff_wg_pct = max(0.0, round(wg_pct - 2.0, 2))
    elif scenario.startswith("Defensiv"):
        eff_material_index = round(material_index * 1.10, 3)
        eff_wg_pct = round(wg_pct + 3.0, 2)

    st.divider()
    st.subheader("2. Analyse- & Benchmark-Optionen")
    max_llm_items = st.slider(
        "Top-Risiko-Fokus für KI-Analyse",
        min_value=10,
        max_value=200,
        value=60,
        step=10,
    )

    strip_prices = st.checkbox(
        "Strip existing prices (Blind Estimation)",
        value=True,
    )

    reference_offer = st.file_uploader(
        "Reference Offer (.d84 / .x84)",
        type=["d84", "x84"],
        key="reference_offer",
    )

benchmark_target = BENCHMARK_FILE if BENCHMARK_FILE.exists() else BENCHMARK_DIR
valid_benchmarks = load_valid_benchmarks(str(benchmark_target))

with st.sidebar:
    st.caption(f"Historische Benchmarks geladen: {len(valid_benchmarks)}")

uploaded = st.file_uploader(
    "Upload GAEB BoQ (.X83 / .D83 / .PDF / .XLSX)",
    type=["x83", "d83", "x84", "pdf", "xlsx", "csv"],
)

if uploaded is None:
    st.info("Bitte eine GAEB-DA .X83 / .D83 oder PDF/Excel-LV-Datei hochladen.")
    st.stop()

file_bytes = uploaded.getvalue()
file_hash = hashlib.sha256(file_bytes).hexdigest()
suffix = Path(uploaded.name).suffix.lower()

# --- CACHED ANALYSIS PIPELINE ---
pipeline_key = (file_hash, strip_prices, max_llm_items, morpheus_active)
if st.session_state.get("pipeline_key") != pipeline_key:
    with st.spinner("LV wird geparst und analysiert..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name

        parsed_items = parse_boq(tmp_path)
        if strip_prices:
            parsed_items = [
                replace(it, reference_unit_price=None) if hasattr(it, "reference_unit_price") else it
                for it in parsed_items
            ]

        if not parsed_items:
            st.error("Keine LV-Positionen in der hochgeladenen Datei gefunden.")
            st.stop()

        logic_res = run_logic_engine(parsed_items)
        # Fachfremde Erdbau-Flags bereinigen
        for it, lg in zip(parsed_items, logic_res):
            lg["flags"] = _sanitize_item_flags(it, lg.get("flags", []))

        cat_sums = compute_category_sums(parsed_items)
        risk_res = [calculate_risk(it, lg) for it, lg in zip(parsed_items, logic_res)]
        llm_k = select_top_llm_keys(parsed_items, risk_res, max_llm_items=max_llm_items)

        ai_res_map = analyze_items(
            parsed_items,
            batch_size=6,
            target_keys=tuple(sorted(llm_k)),
        )
        for idx, (item, logic, risk) in enumerate(zip(parsed_items, logic_res, risk_res)):
            key = f"{idx}|{item.oz}"
            ai_r = ai_res_map.get(key)
            if ai_r is not None:
                ai_r.errors_and_risks = list(dict.fromkeys(logic["flags"] + list(ai_r.errors_and_risks)))
                if risk["risk_score"] == "high":
                    ai_r.change_order_potential = "hoch"

        st.session_state["pipeline_key"] = pipeline_key
        st.session_state["pipeline_data"] = {
            "tmp_path": tmp_path,
            "items": parsed_items,
            "logic_results": logic_res,
            "category_sums": cat_sums,
            "risk_results": risk_res,
            "llm_keys": llm_k,
            "ai_results": ai_res_map,
        }

pdata = st.session_state["pipeline_data"]
tmp_path = pdata["tmp_path"]
items = pdata["items"]
logic_results = pdata["logic_results"]
category_sums = pdata["category_sums"]
risk_results = pdata["risk_results"]
llm_keys = pdata["llm_keys"]
ai_results = pdata["ai_results"]

# Optionales Referenzangebot cachen
ref_price_by_oz = {}
ref_hash = None
if reference_offer is not None:
    ref_bytes = reference_offer.getvalue()
    ref_hash = hashlib.sha256(ref_bytes).hexdigest()
    if st.session_state.get("ref_hash") != ref_hash:
        ref_suffix = Path(reference_offer.name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ref_suffix) as ref_tmp:
            ref_tmp.write(ref_bytes)
            ref_path = ref_tmp.name
        parsed_ref = {}
        try:
            for r_it in parse_boq(ref_path):
                r_ep = getattr(r_it, "reference_unit_price", None)
                if r_ep and float(r_ep) > 0:
                    parsed_ref[str(r_it.oz)] = float(r_ep)
        except Exception as exc:
            st.warning(f"Referenzangebot konnte nicht gelesen werden: {exc}")
        st.session_state["ref_hash"] = ref_hash
        st.session_state["ref_prices"] = parsed_ref
    ref_price_by_oz = st.session_state.get("ref_prices", {})

# --- CACHED KALKULATION ---
calc_key = (
    pipeline_key,
    ref_hash,
    labor_rate,
    machine_rate,
    eff_material_index,
    agk_pct,
    bgk_pct,
    eff_wg_pct,
    tuple(sorted(crew_rates.items())),
)
if st.session_state.get("calc_key") != calc_key:
    ai_results_dual = dict(ai_results)
    for idx, item in enumerate(items):
        res_obj = ai_results.get(f"{idx}|{item.oz}")
        if res_obj is not None and item.oz not in ai_results_dual:
            ai_results_dual[item.oz] = res_obj

    calc_params = inspect.signature(calculate_items).parameters
    available_args = {
        "items": items,
        "ai_results": ai_results_dual,
        "crew_rates": crew_rates,
        "labor_rate": labor_rate,
        "machine_rate": machine_rate,
        "material_index": eff_material_index,
        "agk_pct": agk_pct,
        "bgk_pct": bgk_pct,
        "wg_pct": eff_wg_pct,
        "benchmarks": valid_benchmarks,
        "valid_benchmarks": valid_benchmarks,
        "reference_prices": ref_price_by_oz,
    }
    calc_kwargs = {k: available_args[k] for k in calc_params if k in available_args}
    priced = calculate_items(**calc_kwargs)

    main_net_val = 0.0
    optional_net_val = 0.0
    review_net_val = 0.0
    approved_net_val = 0.0
    r_counts: dict[str, int] = {}
    rows = []

    for idx, (item, p_item, logic, risk) in enumerate(
        zip(items, priced, logic_results, risk_results)
    ):
        key = f"{idx}|{item.oz}"
        ai_res = ai_results.get(key)
        ekt, ep, gp = extract_prices_and_ekt(
            p_item,
            fallback_qty=float(item.qty or 0.0),
            ai_res=ai_res,
            crew_rates=crew_rates,
            machine_rate=machine_rate,
            material_index=eff_material_index,
            agk_pct=agk_pct,
            bgk_pct=bgk_pct,
            wg_pct=eff_wg_pct,
        )
        sync_priced_item_object(p_item, ekt, ep, gp)

        # VOB/A-Trennung: Bedarfs-/Eventualpositionen nicht in die Hauptangebotssumme
        if getattr(item, "item_type", "Normal") == "Normal":
            main_net_val += gp
        else:
            optional_net_val += gp

        needs_review, explanation, cats = evaluate_actual_review(
            item, logic.get("flags", []), risk, ai_res
        )
        if needs_review:
            review_net_val += gp
            for c in cats:
                r_counts[c] = r_counts.get(c, 0) + 1
        else:
            approved_net_val += gp

        rows.append(
            {
                "idx": idx,
                "key": key,
                "item": item,
                "p_item": p_item,
                "logic": logic,
                "risk": risk,
                "ai_res": ai_res,
                "ekt": ekt,
                "ep": ep,
                "gp": gp,
                "needs_review": needs_review,
                "status": "⚠️ Review" if needs_review else "✅ Auto-Approved",
                "analysis_mode": (
                    "KI Deep-Dive"
                    if key in llm_keys
                    else ("Regel-Review" if needs_review else "Deterministisch")
                ),
                "explanation": explanation,
                "categories": cats,
            }
        )

    st.session_state["calc_key"] = calc_key
    st.session_state["calc_data"] = {
        "priced_items": priced,
        "main_net": round(main_net_val, 2),
        "optional_net": round(optional_net_val, 2),
        "review_net": round(review_net_val, 2),
        "approved_net": round(approved_net_val, 2),
        "reason_counts": r_counts,
        "enriched_rows": rows,
    }
    st.session_state.pop("export_cache", None)

cdata = st.session_state["calc_data"]
priced_items = cdata["priced_items"]
main_net = cdata["main_net"]
optional_net = cdata["optional_net"]
review_net = cdata["review_net"]
approved_net = cdata["approved_net"]
reason_counts = cdata["reason_counts"]
enriched_rows = cdata["enriched_rows"]

# --- KPI DASHBOARD ---
total_count = len(enriched_rows)
review_count = sum(1 for r in enriched_rows if r["needs_review"])
auto_count = total_count - review_count
approval_quote = (auto_count / total_count * 100.0) if total_count else 0.0
review_quote = (review_count / total_count * 100.0) if total_count else 0.0
total_all_net = main_net + optional_net
review_value_share = (review_net / total_all_net * 100.0) if total_all_net > 0 else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Positionen gesamt", total_count)
c2.metric("Auto-Approved Quote", f"{approval_quote:.1f} %", delta=f"{auto_count} von {total_count} Pos.")
c3.metric(
    "Review-Quote (Fokus)",
    f"{review_quote:.1f} %",
    delta=f"{review_count} Pos. ({len(llm_keys)} im KI-Deep-Dive)",
    delta_color="inverse",
)
c4.metric(
    "Risiko-Volumen (€-Quote)",
    f"{review_value_share:.1f} %",
    delta=f"{review_net:,.2f} € im Review",
    delta_color="off",
)
c5.metric(
    "Hauptangebot Netto (VOB/A)",
    f"{main_net:,.2f} €",
    delta=f"+ {optional_net:,.2f} € Bedarfspos." if optional_net > 0 else "0,00 € Bedarfspos.",
    delta_color="off",
)

# --- REVIEW-URSACHEN ÜBERSICHT ---
if reason_counts:
    with st.expander("Warum wurden Positionen ausgesteuert? (Review-Gründe & Verteilung)", expanded=True):
        reason_labels = {
            "VAGE_SPEZIAL": "Vage / unklare Beschreibung",
            "BEDARFS_POS": "Bedarfs- / Eventualposition (VOB/A)",
            "META_MISMATCH": "Meta-Widerspruch (Pauschale ≠ 1)",
            "QTY_OUTLIER": "Mengen-Ausreißer / Zahlendreher",
            "MISSING_SPEC": "Fehlender Langtext",
            "SCOPE_GAP": "Lieferung ohne Montage",
            "CATEGORY_MISMATCH": "Flächen-Widerspruch",
            "MISSING_FOLLOW_UP": "Fehlende Folgeposition",
            "SONDERPOSITION": "Sonstige Sonderposition",
        }
        stat_cols = st.columns(min(4, len(reason_counts)))
        for i, (code, count) in enumerate(
            sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        ):
            pct = (count / max(1, review_count)) * 100.0
            stat_cols[i % len(stat_cols)].metric(
                label=reason_labels.get(code, code),
                value=f"{count} Pos.",
                delta=f"{pct:.0f} % der Reviews",
                delta_color="off",
            )

# --- MATERIAL- & MENGEN-AGGREGATION ---
if category_sums:
    st.subheader("Projekt-Mengengerüst (Material-Aggregation)")
    labels = {
        "concrete_m3": ("Beton gesamt", "m³"),
        "formwork_m2": ("Schalung gesamt", "m²"),
        "rebar_t": ("Bewehrung gesamt", "t"),
        "excavation_m3": ("Erdaushub gesamt", "m³"),
        "backfill_m3": ("Verfüllung gesamt", "m³"),
        "pipe_m": ("Rohrleitungen gesamt", "m"),
        "floor_m2": ("Bodenflächen gesamt", "m²"),
        "floor_heating_m2": ("Fußbodenheizung", "m²"),
        "wall_m2": ("Wand-/Malerflächen", "m²"),
        "shaft_stk": ("Schächte / Bauwerke", "Stk"),
    }
    cols = st.columns(min(5, len(category_sums)))
    for i, (tag, val) in enumerate(category_sums.items()):
        title, unit_lbl = labels.get(tag, (tag, ""))
        cols[i % len(cols)].metric(title, f"{val:,.2f} {unit_lbl}".strip())

# --- AUDIT TABS ---
tab_review, tab_approved, tab_all = st.tabs(
    [
        f"⚠️ Review-Queue ({review_count} | {review_quote:.1f} %)",
        f"✅ Auto-Approved ({auto_count} | {approval_quote:.1f} %)",
        f"💰 Vollständige Kalkulation ({total_count})",
    ]
)

with tab_review:
    if review_count == 0:
        st.success("Alle Positionen wurden ohne kritische Risikohinweise automatisch freigegeben.")
    else:
        col_f1, col_f2 = st.columns([1, 2])
        risk_filter = col_f1.selectbox(
            "Risikostufe filtern",
            options=["Alle", "HIGH", "MEDIUM", "LOW"],
            index=0,
            key="risk_filter_select",
        )
        search_review = col_f2.text_input(
            "Suche in Review-Positionen (OZ, Text, Begründung)",
            value="",
            key="search_review_input",
        ).strip().lower()

        filtered_reviews = []
        for entry in enriched_rows:
            if not entry["needs_review"]:
                continue
            r_lvl = entry["risk"]["risk_score"].upper()
            if risk_filter != "Alle" and r_lvl != risk_filter:
                continue
            if search_review:
                haystack = f"{entry['item'].oz} {entry['item'].short_text} {entry['explanation']}".lower()
                if search_review not in haystack:
                    continue
            filtered_reviews.append(entry)

        if not filtered_reviews:
            st.info(f"Keine Review-Positionen für Filter '{risk_filter}' gefunden.")
        else:
            st.caption(f"Angezeigt: {len(filtered_reviews)} von {review_count} Review-Positionen")
            review_table = []
            for entry in filtered_reviews:
                item = entry["item"]
                ai_res = entry["ai_res"]
                row = {
                    "OZ": item.oz,
                    "Typ": item.item_type,
                    "Kurztext": item.short_text,
                    "Menge": f"{item.qty:g} {item.unit}",
                    "Risiko": entry["risk"]["risk_score"].upper(),
                    "Warum Review? (Begründung)": entry["explanation"],
                    "EKT (€)": round(entry["ekt"], 2),
                    "EP (€)": round(entry["ep"], 2),
                    "Gesamt (€)": round(entry["gp"], 2),
                    "Nachtragspotenzial": (
                        getattr(ai_res, "change_order_potential", "-").upper() if ai_res else "-"
                    ),
                }
                if ref_price_by_oz:
                    row["Ref-EP (€)"] = ref_price_by_oz.get(str(item.oz))
                review_table.append(row)

            st.dataframe(pd.DataFrame(review_table), use_container_width=True, height=380)

            st.markdown("#### Positions-Inspektor (Langtext, Preis-Tiers & Bieterfrage)")
            options_map = {
                f"{e['idx'] + 1}. [{e['item'].oz}] {e['item'].short_text[:65]} ({e['risk']['risk_score'].upper()})": e
                for e in filtered_reviews
            }
            selected_label = st.selectbox(
                "Position im Detail prüfen",
                list(options_map.keys()),
                key=f"inspector_select_{risk_filter}",
            )
            sel = options_map[selected_label]
            sel_item = sel["item"]
            sel_ai = sel["ai_res"]

            st.info(f"**Warum Review erforderlich:** {sel['explanation']}")
            if sel_item.long_text:
                with st.expander("Vollständigen LV-Langtext anzeigen", expanded=False):
                    st.write(sel_item.long_text)

            if sel_ai is not None:
                if getattr(sel_ai, "tier_mid", None):
                    t1, t2, t3 = st.columns(3)
                    t1.metric("Markt-Tier Low", f"{sel_ai.tier_low:,.2f} €")
                    t2.metric("Markt-Tier Mid", f"{sel_ai.tier_mid:,.2f} €")
                    t3.metric("Markt-Tier High", f"{sel_ai.tier_high:,.2f} €")
                    if getattr(sel_ai, "tier_rationale", ""):
                        st.caption(sel_ai.tier_rationale)

                col_q1, col_q2 = st.columns(2)
                with col_q1:
                    st.text_area(
                        "Entwurf Bieterfrage an Auftraggeber (RFI)",
                        value=getattr(sel_ai, "client_rfi_draft", ""),
                        height=140,
                        key=f"rfi_{sel['key']}",
                    )
                with col_q2:
                    st.text_area(
                        "Entwurf Nachunternehmer-Anfrage (RFQ)",
                        value=getattr(sel_ai, "subcontractor_rfq_draft", ""),
                        height=140,
                        key=f"rfq_{sel['key']}",
                    )

with tab_approved:
    if auto_count == 0:
        st.warning("Keine Positionen wurden automatisch freigegeben.")
    else:
        st.caption(
            f"{auto_count} von {total_count} Positionen ({approval_quote:.1f} %, "
            f"Netto-Volumen {approved_net:,.2f} €) erfüllen alle Plausibilitätsregeln."
        )
        search_app = st.text_input(
            "Suche in Auto-Approved Positionen (OZ, Kurztext, Kolonne)",
            value="",
            key="search_approved_input",
        ).strip().lower()

        approved_table = []
        for entry in enriched_rows:
            if entry["needs_review"]:
                continue
            item = entry["item"]
            ai_res = entry["ai_res"]
            crew_name = CREW_MULTIPLIERS.get(
                getattr(ai_res, "crew_type", "general") if ai_res else "general",
                ("Standardkolonne", 1.0),
            )[0]
            if search_app and search_app not in f"{item.oz} {item.short_text} {crew_name}".lower():
                continue
            row = {
                "OZ": item.oz,
                "Gewerk / Titel": item.hierarchy,
                "Kurztext": item.short_text,
                "Menge": item.qty,
                "Einheit": item.unit,
                "Kolonne": crew_name,
                "EKT (€)": round(entry["ekt"], 2),
                "EP (€)": round(entry["ep"], 2),
                "Gesamt (€)": round(entry["gp"], 2),
                "Approval-Begründung": entry["explanation"],
            }
            if ref_price_by_oz:
                row["Ref-EP (€)"] = ref_price_by_oz.get(str(item.oz))
            approved_table.append(row)

        st.dataframe(pd.DataFrame(approved_table), use_container_width=True, height=420)

with tab_all:
    overview_rows = []
    for entry in enriched_rows:
        item = entry["item"]
        row = {
            "Status": entry["status"],
            "OZ": item.oz,
            "Typ": item.item_type,
            "Gewerk / Titel": item.hierarchy,
            "Kurztext": item.short_text,
            "Menge": item.qty,
            "Einheit": item.unit,
            "EKT (€)": round(entry["ekt"], 2),
            "EP (€)": round(entry["ep"], 2),
            "Gesamt (€)": round(entry["gp"], 2),
            "Risiko": entry["risk"]["risk_score"].upper(),
            "Begründung / Flags": entry["explanation"],
        }
        if ref_price_by_oz:
            ref_ep = ref_price_by_oz.get(str(item.oz))
            row["Ref-EP (€)"] = ref_ep
            row["Delta (%)"] = round(((entry["ep"] - ref_ep) / ref_ep) * 100, 1) if ref_ep else None
        overview_rows.append(row)
    st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, height=450)

# --- ON-DEMAND EXPORT ---
with st.expander("Export Results (GAEB .X84 & Excel mit Formeln)", expanded=False):
    if st.button("Export-Dateien generieren (.X84 & .xlsx)", use_container_width=True):
        with st.spinner("Erzeuge GAEB .X84 und Excel-Kalkulation..."):
            exp_result = {}
            if suffix in (".x83", ".d83", ".x84"):
                try:
                    x84_params = list(inspect.signature(export_x84).parameters.values())
                    first_name = x84_params[0].name.lower() if x84_params else ""
                    first_ann = x84_params[0].annotation if x84_params else inspect.Parameter.empty
                    source_arg = (
                        file_bytes
                        if (first_ann is bytes or "byte" in first_name or "content" in first_name)
                        else tmp_path
                    )
                    if len(x84_params) >= 3:
                        x84_out = export_x84(source_arg, uploaded.name, priced_items)
                    elif len(x84_params) == 2:
                        x84_out = export_x84(source_arg, priced_items)
                    else:
                        x84_out = export_x84(priced_items)

                    if isinstance(x84_out, (str, Path)) and Path(x84_out).exists():
                        exp_result["x84"] = Path(x84_out).read_bytes()
                    elif isinstance(x84_out, (bytes, bytearray)):
                        exp_result["x84"] = bytes(x84_out)
                except Exception as exc:
                    exp_result["x84_err"] = str(exc)

            try:
                exp_result["xlsx"] = build_formula_excel(
                    enriched_rows=enriched_rows,
                    agk_pct=agk_pct,
                    bgk_pct=bgk_pct,
                    wg_pct=eff_wg_pct,
                    main_net=main_net,
                    optional_net=optional_net,
                )
            except Exception as exc:
                exp_result["xlsx_err"] = str(exc)

            st.session_state["export_cache"] = exp_result

    exp_cache = st.session_state.get("export_cache")
    if exp_cache:
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if "x84" in exp_cache:
                st.download_button(
                    label="Download GAEB .X84",
                    data=exp_cache["x84"],
                    file_name=f"{Path(uploaded.name).stem}_angebot.x84",
                    mime="application/xml",
                )
            elif "x84_err" in exp_cache:
                st.warning(f"X84-Export Hinweis: {exp_cache['x84_err']}")
        with col_exp2:
            if "xlsx" in exp_cache:
                st.download_button(
                    label="Download Excel Kalkulation (.xlsx)",
                    data=exp_cache["xlsx"],
                    file_name=f"{Path(uploaded.name).stem}_kalkulation.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            elif "xlsx_err" in exp_cache:
                st.warning(f"Excel-Export Hinweis: {exp_cache['xlsx_err']}")
````

## `calculator.py`
````py
import re
from dataclasses import replace
from typing import Dict, Iterable, List, Optional

from models import NormalizedItem, AIItemResult, PricedItem
from parser import find_benchmark, normalize_benchmark_unit
from ai_engine import classify_construction_phase


CREW_RATES = {
    "earthworks": "Erdbau",
    "pipe_crew": "Rohrleger",
    "paving": "Pflasterer",
    "fitter": "Monteur",
    "general": "Allgemein",
    "specialist_subcontractor": "Allgemein",
}


def round_money(value: float) -> float:
    return round(value + 1e-8, 2)


def benchmark_for(item: NormalizedItem, benchmarks) -> Optional[float]:
    match = find_benchmark(item, benchmarks)
    if match is None:
        return None
    benchmark, similarity = match
    if normalize_benchmark_unit(item.unit) != normalize_benchmark_unit(benchmark.unit):
        return None
    if benchmark.is_outlier:
        return None
    return benchmark.unit_price


def benchmark_match(item: NormalizedItem, benchmarks):
    match = find_benchmark(item, benchmarks)
    if match is None:
        return None, 0.0
    benchmark, similarity = match
    item_unit = normalize_benchmark_unit(item.unit)
    benchmark_unit = normalize_benchmark_unit(benchmark.unit)
    if item_unit != benchmark_unit or benchmark.is_outlier:
        return None, 0.0
    return benchmark, similarity


def plausibility_risk(item: NormalizedItem, all_items: List[NormalizedItem]) -> List[str]:
    risks = list(getattr(item, "data_defects", []) or [])
    text = f"{item.short_text} {item.long_text}".lower()
    unit = item.unit.lower().replace(" ", "").replace(".", "")
    qty = item.qty

    if unit in ("psch", "pauschal", "ls") and qty > 1:
        risks.append("Pauschale Position hat Menge > 1; Leistung und Zeit-/Stückbezug prüfen")
    if unit in ("m3", "m³", "cbm") and any(k in text for k in ("aushub", "boden", "erd", "graben")):
        if qty > 1000:
            risks.append("Erdmengen-Anomalie: sehr große Kubatur; Mengenordnung prüfen")
        elif qty <= 0:
            risks.append("Erdmengen-Anomalie: Menge fehlt oder ist null")
    if unit in ("m", "lfm") and any(k in text for k in ("leitung", "rohr", "kanal")):
        if qty > 20000:
            risks.append("Rohrleitungsmenge wirkt unplausibel groß; Mengenordnung prüfen")
    if unit in ("m2", "qm") and qty > 50000:
        risks.append("Flächenmenge wirkt unplausibel groß; Mengenordnung prüfen")

    all_text = " ".join(
        f"{x.short_text} {x.long_text}".lower() for x in all_items
    )
    if any(k in text for k in ("graben", "aushub", "ausbau")):
        if not any(k in all_text for k in ("entsorgung", "abfuhr", "disposal", "lade")):
            risks.append("Fehlende Nachbarposition: Entsorgung/Abfuhr für Erd-/Grabearbeiten prüfen")
    if any(k in text for k in ("baustelleneinrichtung", "baustelle einrichten")):
        if not any(k in all_text for k in ("baustelle", "einrichtung")):
            risks.append("Baustelleneinrichtung fehlt als abhängige Leistungsposition")
    return list(dict.fromkeys(risks))


def project_quantity_plausibility(
    items: List[NormalizedItem],
    preamble_quantities: dict,
) -> List[str]:
    statuses = []
    pipeline_expected = preamble_quantities.get("pipeline_m")
    if pipeline_expected is not None:
        pipeline_sum = sum(
            item.qty for item in items
            if item.unit.lower().replace(".", "") in ("m", "lfm")
            and any(keyword in f"{item.short_text} {item.long_text}".lower()
                    for keyword in ("rohr", "kanal", "leitung"))
        )
        tolerance = max(2.0, pipeline_expected * 0.03)
        if abs(pipeline_sum - pipeline_expected) <= tolerance:
            statuses.append(
                f"Pipeline-Länge passend: BoQ {pipeline_sum:g} m vs. Vorbemerkung {pipeline_expected:g} m"
            )
        else:
            statuses.append(
                f"Pipeline-Länge abweichend: BoQ {pipeline_sum:g} m vs. Vorbemerkung {pipeline_expected:g} m"
            )

    structure_expected = preamble_quantities.get("structure_count")
    if structure_expected is not None:
        structure_sum = sum(
            item.qty for item in items
            if any(keyword in f"{item.short_text} {item.long_text}".lower()
                   for keyword in ("tangentialschacht", "einlaufbauwerk", "schacht"))
        )
        if abs(structure_sum - structure_expected) <= 0:
            statuses.append(
                f"Strukturanzahl passend: BoQ {structure_sum:g} vs. Vorbemerkung {structure_expected:g}"
            )
        else:
            statuses.append(
                f"Strukturanzahl abweichend: BoQ {structure_sum:g} vs. Vorbemerkung {structure_expected:g}"
            )

    diameters = preamble_quantities.get("diameters") or []
    if diameters:
        boq_text = " ".join(
            f"{item.short_text} {item.long_text}".lower() for item in items
        )
        missing = [
            diameter for diameter in diameters
            if str(diameter) not in boq_text
        ]
        if missing:
            statuses.append(
                "DN aus Vorbemerkung fehlt im BoQ: " + ", ".join(f"DN {value}" for value in missing)
            )
        else:
            statuses.append(
                "DN aus Vorbemerkung im BoQ enthalten: " + ", ".join(f"DN {value}" for value in diameters)
            )
    return statuses


def calculate_items(
    items: List[NormalizedItem],
    ai_results: Dict[str, AIItemResult],
    crew_rates: Dict[str, float],
    machine_rate: float,
    material_index: float,
    agk_pct: float,
    bgk_pct: float,
    wg_pct: float,
    tactic_multipliers: Optional[Dict[str, float]] = None,
    edits: Optional[Dict[str, dict]] = None,
    benchmarks=None,
    project_weeks: float = 12.0,
    use_reference_prices: bool = False,
) -> List[PricedItem]:
    tactic_multipliers = tactic_multipliers or {
        "STANDARD": 1.0,
        "HIGH_SPECULATE": 1.10,
        "LOW_EVENTUAL": 0.85,
    }
    edits = edits or {}
    benchmarks = benchmarks or []
    priced = []
    overhead_factor = 1.0 + agk_pct + bgk_pct + wg_pct

    for item_index, item in enumerate(items):
        ai = ai_results.get(f"{item_index}|{item.oz}")
        if ai is None:
            ai = AIItemResult(oz=item.oz)
        item_key = f"{item_index}|{item.oz}"
        edit = edits.get(item_key, edits.get(item.oz, {}))
        qty = float(edit.get("qty", item.qty))
        tactic = str(edit.get("tactic", ai.suggested_tactic)).upper()
        if tactic not in tactic_multipliers:
            tactic = "STANDARD"
        labor = ai.labor_hours_per_unit
        machine = ai.machine_hours_per_unit
        material = ai.base_material_cost_per_unit
        material_subcontract = getattr(
            ai, "material_or_subcontract_cost_per_unit",
            0.0,
        )
        crew_key = ai.crew_type if ai.crew_type in crew_rates else "general"
        crew_rate = crew_rates.get(crew_key, crew_rates.get("general", 45.0))
        ai.construction_phase = classify_construction_phase(
            item.hierarchy,
            f"{item.short_text} {item.long_text}",
        )

        benchmark_match_item, benchmark_similarity = benchmark_match(item, benchmarks)
        benchmark = benchmark_match_item.unit_price if benchmark_match_item else None
        unit_normalized = item.unit.lower().replace(" ", "").replace(".", "")
        hourly_text = f"{item.short_text} {item.long_text}".lower()
        is_hourly = unit_normalized in ("std", "std.", "h")
        if is_hourly:
            if any(k in hourly_text for k in ("vorarbeiter", "polier", "meister")):
                crew_rate = crew_rates.get("polier", crew_rates.get("general", 68.0))
                labor, machine, material = 1.0, 0.0, 0.0
            elif any(k in hourly_text for k in ("bagger", "lkw", "fahrzeug", "maschine", "transporter", "mini-bagger", "minibagger")):
                crew_rate = 0.0
                labor, machine, material = 0.0, 1.0, 0.0
            elif any(k in hourly_text for k in ("facharbeiter", "monteur")):
                crew_rate = crew_rates.get("fitter", crew_rates.get("general", 65.0))
                labor, machine, material = 1.0, 0.0, 0.0
            else:
                crew_rate = crew_rates.get("general", 52.0)
                labor, machine, material = 1.0, 0.0, 0.0

        ekt = labor * crew_rate + machine * machine_rate + material * material_index
        ekt = ekt + material_subcontract * material_index
        ep = ekt * overhead_factor * tactic_multipliers[tactic]
        selected_tier = str(edit.get("selected_tier", ""))
        custom_price = edit.get("custom_price")
        if ai.is_specialist_or_unclear:
            tier_map = {"Low": ai.tier_low, "Mid": ai.tier_mid, "High": ai.tier_high}
            if custom_price is not None:
                ep = float(custom_price)
            elif selected_tier in tier_map and tier_map[selected_tier] is not None:
                ep = float(tier_map[selected_tier])
            else:
                ep = float(ai.tier_mid or 0.0)

        benchmark_valid = (
            benchmark_match_item is not None
            and benchmark_similarity >= 0.65
            and not benchmark_match_item.is_outlier
            and normalize_benchmark_unit(item.unit)
            == normalize_benchmark_unit(benchmark_match_item.unit)
        )
        if benchmark_valid:
            if is_hourly:
                ep = benchmark_match_item.unit_price
            elif unit_normalized in ("psch", "pauschal", "ls") or ai.is_specialist_or_unclear:
                calculated_mid = ep
                ep = (0.70 * benchmark_match_item.unit_price) + (0.30 * calculated_mid)

        domain_text = f"{item.short_text} {item.long_text}".lower()
        high_confidence_match = (
            benchmark_match_item is not None
            and benchmark_similarity >= 0.65
            and not benchmark_match_item.is_outlier
        )
        if not high_confidence_match:
            if unit_normalized in ("m2", "qm") and any(
                word in domain_text for word in ("begruen", "begrün", "ansaat", "rasen")
            ):
                ep = max(2.50, min(8.50, ep))
            if unit_normalized == "m" and "asphalt schneiden" in domain_text:
                ep = max(6.00, min(18.00, ep))
            dn_match = re.search(r"\b(?:dn|nennweite)\s*([0-9]{3,4})\b", domain_text)
            dn = int(dn_match.group(1)) if dn_match else 0
            structural_text = any(
                word in domain_text for word in (
                    "uhpc", "stahlbetonrohr", "tangentialschacht",
                    "einlaufbauwerk", "betonauflager",
                )
            )
            if unit_normalized == "m" and (dn >= 400 or structural_text):
                floor = 180.00 if dn >= 800 or "uhpc" in domain_text else 140.00
                ep = max(floor, ep)
                material_subcontract = max(material_subcontract, floor * 0.55)
            if unit_normalized == "stk" and structural_text:
                ep = max(2800.00, ep)
                material_subcontract = max(material_subcontract, 1800.00)
            if unit_normalized in ("m3", "cbm") and any(
                word in domain_text for word in ("beton", "stahlbeton", "tangentialschacht")
            ):
                ep = max(140.00, ep)
                material_subcontract = max(material_subcontract, 90.00)
            if unit_normalized in ("psch", "pauschal", "ls") and "wasserhaltung" in domain_text:
                ep = max(ep, 250.00 * max(1.0, project_weeks))
                material_subcontract = max(
                    material_subcontract,
                    180.00 * max(1.0, project_weeks),
                )

        material_estimate = getattr(ai, "material_cost_estimate", None)
        if material_estimate is None:
            material_estimate = getattr(ai, "material_or_subcontract_cost_per_unit", None)

        selected_tier_price = None
        if ai.is_specialist_or_unclear:
            tier_map = {"Low": ai.tier_low, "Mid": ai.tier_mid, "High": ai.tier_high}
            if selected_tier in tier_map and tier_map[selected_tier] is not None:
                selected_tier_price = float(tier_map[selected_tier])
            elif custom_price is not None:
                selected_tier_price = float(custom_price)

        if selected_tier_price is not None:
            raw_unit_price = selected_tier_price
        elif material_estimate is not None and float(material_estimate) > 0:
            small_labor_cost = labor * crew_rate
            raw_unit_price = float(material_estimate) + (0.25 * small_labor_cost)
        elif benchmark_valid:
            raw_unit_price = benchmark_match_item.unit_price
        else:
            raw_unit_price = ep

        unit_price = round_money(float(raw_unit_price))
        item_total = round_money(qty * unit_price)
        risks = list(ai.errors_and_risks)
        risks.extend(plausibility_risk(item, items))
        if benchmark is not None:
            difference = (unit_price - benchmark) / benchmark if benchmark else 0.0
            if abs(difference) >= 0.50 or unit_price < 0.5:
                risks.append(
                    f"Historischer Benchmark: {benchmark:.2f} €/Einheit; kalkulierter EP "
                    f"{unit_price:.2f} € ({difference:+.0%})."
                )
        # Needs-review follows the risk policy from risk_engine + high-severity flags.
        confirmed = bool(edit.get("confirmed", False))
        high_flags = [
            flag for flag in (getattr(ai, "risk_flags", None) or [])
            if getattr(flag, "severity", "").lower() == "high"
        ]
        benchmark_deviation = None
        if benchmark is not None and benchmark > 0:
            benchmark_deviation = abs((unit_price - benchmark) / benchmark)

        needs_review = (
            (getattr(ai, "change_order_potential", "") == "hoch")
            or (ai.is_specialist_or_unclear and not confirmed)
            or bool(high_flags)
            or (benchmark_deviation is not None and benchmark_deviation > 0.55)
        )
        # Once the estimator confirms, the position is no longer in review.
        if confirmed:
            needs_review = False

        comparison = ""
        if benchmark is not None:
            difference = (unit_price - benchmark) / benchmark if benchmark else 0.0
            comparison = f"{difference:+.1%} zum historischen Benchmark"
        risks = list(dict.fromkeys(risks))

        priced.append(PricedItem(
            oz=item.oz, hierarchy=item.hierarchy, short_text=item.short_text,
            long_text=item.long_text, qty=qty, unit=item.unit, item_type=item.item_type,
            crew_type=ai.crew_type,
            labor_hours_per_unit=labor, machine_hours_per_unit=machine,
            base_material_cost_per_unit=material,
            labor_hours=labor * qty, machine_hours=machine * qty,
            ekt=ekt, ep_per_unit=unit_price, item_total=item_total,
            tactic=tactic, risks=risks,
            needs_review=needs_review,
            confirmed=bool(edit.get("confirmed", False)),
            selected_price_tier=selected_tier,
            benchmark_unit_price=benchmark, benchmark_comparison=comparison,
            client_rfi_draft=ai.client_rfi_draft,
            subcontractor_rfq_draft=ai.subcontractor_rfq_draft,
            reference_unit_price=item.reference_unit_price,
            confidence=ai.confidence,
            construction_phase=ai.construction_phase,
            change_order_potential=ai.change_order_potential,
            xml_id=getattr(item, "xml_id", ""),
            material_or_subcontract_cost_per_unit=material_subcontract,
            rfi_question=getattr(ai, "rfi_question", ""),
        ))
    return priced


def project_time(priced: Iterable[PricedItem], crew_size: int = 4, hours_per_day: float = 8.0):
    priced = list(priced)
    labor = sum(p.labor_hours for p in priced)
    machine = sum(p.machine_hours for p in priced)
    man_days = labor / hours_per_day
    duration_weeks = man_days / max(1, crew_size) / 5.0
    return labor, machine, man_days, duration_weeks

````

## `data/benchmarks/.gitkeep`
````

````

## `data/benchmarks.json`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/.gitkeep`
````


````

## `data/raw_benchmarks/8209.003_Leistungsverzeichnis_leer.D83`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/[ORT_024] LV24069.D86`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/Abgabe LV.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/Angebot AN24-0305.D84`
*(?bersprungen: Bin?rdatei)*

## `data/raw_benchmarks/Angebot AN24-0305.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/HEM2301-2_Gesamt-LV.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/Leistungsverzeichnis.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/Leistungsverzeichnis_leer.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV-Ausdruck-[PROJEKT_004].pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV-Positionen.docx`
*(?bersprungen: Bin?rdatei)*

## `data/raw_benchmarks/LV-Schachtbauwerk.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_00_Roh_und_Erdauarbeiten.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_01_Fertigteiltreppen.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_02_PVC_Fussbodenbelag.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_03_Malerarbeiten.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_04_Porenbetonfassade.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_05_[FIRMA_096].pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_06_Kautschukboden.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_07_Teppichboden.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_08_Fliesen_und_Natursteinarbeiten.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_09_Porenbetondach.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_10_Stahlbetonfertigeile_Stuetzen_Binder.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_11_Stahlbetonfertigeile_Sandwichsockel.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_12_Dachabdichtung.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_13_ELT.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_14_Sanitaeranlage.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_14a_Betonkernaktivierung.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_14b_Dachentwaesserung.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_14c_Industriebodenheizung.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_15_Abdichtung_Aussenwaende.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_15a_Abdichtung_Bodenplatte_Buero.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_17_Trockenbau.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_18_Estrich.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_19_Sektionaltore_Stahltueren.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_20_Bodenbelagsarbeiten.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_21_Natursteinarbeiten.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_22_Schreinerarbeiten.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/LV_23_Sanitaertrennwaende.pdf`
*(?bersprungen: Datei gr??er als 200 KB)*

## `data/raw_benchmarks/StBALV23040.D84`
*(?bersprungen: Bin?rdatei)*

## `data/raw_benchmarks/StBALV23040.D86`
*(?bersprungen: Datei gr??er als 200 KB)*

## `exporter.py`
````py
import copy
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from typing import Iterable, List

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from models import PricedItem


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].split(":")[-1]


def round_money(value: float) -> float:
    return round(value + 1e-8, 2)


def export_x84(source_path: str | Path, priced_items: Iterable[PricedItem]) -> bytes:
    tree = ET.parse(str(source_path))
    root = tree.getroot()
    priced_list = list(priced_items)
    priced_by_oz = {}
    for item in priced_list:
        priced_by_oz.setdefault(item.oz, []).append(item)
    priced_by_xml_id = {
        item.xml_id: item for item in priced_list if getattr(item, "xml_id", "")
    }
    sequential_index = 0

    root.attrib.clear()

    namespace = "http://www.gaeb.de/GAEB_DA_XML/DA84/3.2"
    ns = f"{{{namespace}}}"
    ET.register_namespace("", namespace)
    root.tag = ns + _local(root.tag)

    for elem in root.iter():
        elem.tag = ns + _local(elem.tag)

    for elem in root.iter():
        if _local(elem.tag).lower() == "dp":
            elem.text = "84"

    for elem in root.iter():
        if _local(elem.tag).lower() not in ("boqitem", "boqline", "boqbodyitem", "item"):
            continue
        oz = ""
        oz = str(elem.attrib.get("RNoPart", elem.attrib.get("RNo", elem.attrib.get("ID", ""))))
        xml_id = str(elem.attrib.get("ID", ""))
        for child in elem.iter():
            if _local(child.tag).lower() in ("rnopart", "boqno", "id"):
                value = " ".join(child.itertext()).strip()
                if value:
                    oz = value
                    break
        priced = None
        if xml_id and xml_id in priced_by_xml_id:
            priced = priced_by_xml_id[xml_id]
        matches = priced_by_oz.get(oz, []) if priced is None else []
        if matches:
            priced = matches.pop(0)
        elif sequential_index < len(priced_list):
            priced = priced_list[sequential_index]
        else:
            continue
        sequential_index += 1
        up = None
        it = None
        for child in elem.iter():
            if _local(child.tag).lower() in ("up", "unitprice"):
                up = child
            if _local(child.tag).lower() in ("it", "itemtotal", "total"):
                it = child
        if up is None:
            namespace = elem.tag.rpartition("}")[0] + "}" if "}" in elem.tag else ""
            up = ET.SubElement(elem, f"{namespace}UP")
        if it is None:
            namespace = elem.tag.rpartition("}")[0] + "}" if "}" in elem.tag else ""
            it = ET.SubElement(elem, f"{namespace}IT")
        # Strict rounding order for GAEB DA84: UP first, then IT = qty * UP
        up_val = round_money(priced.ep_per_unit)
        it_val = round_money(float(priced.qty) * up_val)
        up.text = f"{up_val:.2f}"
        it.text = f"{it_val:.2f}"

    def remove_old_totals(parent):
        for child in list(parent):
            if _local(child.tag).lower() == "totals":
                parent.remove(child)

    # Insert totals directly under every category and under the BoQ level.
    for category in list(root.iter()):
        if _local(category.tag).lower() != "boqctgy":
            continue
        remove_old_totals(category)
        category_items = []
        for descendant in category.iter():
            if descendant is category:
                continue
            if _local(descendant.tag).lower() not in ("boqitem", "boqline", "boqbodyitem", "item"):
                continue
            xml_id = str(descendant.attrib.get("ID", ""))
            oz = ""
            for child in descendant.iter():
                if _local(child.tag).lower() in ("rnopart", "boqno", "id"):
                    oz = " ".join(child.itertext()).strip()
                    if oz:
                        break
            if xml_id in priced_by_xml_id:
                category_items.append(priced_by_xml_id[xml_id])
            else:
                matches = priced_by_oz.get(oz, [])
                if matches:
                    category_items.append(matches[0])
        category_total = round_money(
            sum(round_money(p.item_total) for p in category_items)
        )
        totals = ET.Element(ns + "Totals")
        ET.SubElement(totals, ns + "Total").text = f"{category_total:.2f}"
        category.append(totals)

    for boq in list(root.iter()):
        if _local(boq.tag).lower() != "boq":
            continue
        remove_old_totals(boq)
        boq_total = round_money(
            sum(round_money(p.item_total) for p in priced_list)
        )
        totals = ET.Element(ns + "Totals")
        ET.SubElement(totals, ns + "Total").text = f"{boq_total:.2f}"
        boq.append(totals)

    output = BytesIO()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    data = output.getvalue()
    data = data.replace(b"<UP>", b"<UP>")
    return data


def _sheet_title(ws, title: str):
    ws.title = title


def _autofit(ws):
    for col in range(1, ws.max_column + 1):
        width = 12
        for row in range(1, ws.max_row + 1):
            value = ws.cell(row, col).value
            width = max(width, min(50, len(str(value or "")) + 2))
        ws.column_dimensions[get_column_letter(col)].width = width


def export_xlsx(priced_items: List[PricedItem], agk: float, bgk: float, wg: float,
                labor_hours: float, machine_hours: float, man_days: float,
                duration_weeks: float, crew_size: int) -> bytes:
    wb = Workbook()
    boq = wb.active
    _sheet_title(boq, "Priced BoQ")
    headers = [
        "OZ", "Gewerk/Titel", "Kurztext", "Langtext", "Menge", "Einheit",
        "Typ", "Crew", "Arbeitsstd/Einh.", "Maschinenstd/Einh.",
        "Material €/Einh.", "Arbeitsstd ges.", "Maschinenstd ges.",
        "EKT €/Einh.", "EP €/Einh.", "Gesamt €", "Taktik",
        "Benchmark €/Einh.", "Benchmark-Abweichung", "Status", "Risikohinweise",
        "Referenz-/Blindpreis €/Einh.", "Referenz-Abweichung",
        "Konfidenz", "Bauphase", "Nachtragsrisiko",
        "Material-/Nachunternehmerkosten €/Einh."
    ]
    boq.append(headers)
    for cell in boq[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="BDD7EE")
    for p in priced_items:
        excel_long = p.long_text or ""
        if p.short_text and excel_long.startswith(p.short_text):
            excel_long = excel_long[len(p.short_text):].strip(" \n.-")
        if not excel_long:
            excel_long = p.long_text or p.short_text
        boq.append([
            p.oz, p.hierarchy, p.short_text, excel_long, p.qty, p.unit,
            p.item_type, p.crew_type, p.labor_hours_per_unit,
            p.machine_hours_per_unit, p.base_material_cost_per_unit,
            p.labor_hours, p.machine_hours, round_money(p.ekt),
            round_money(p.ep_per_unit),
            round_money(p.item_total), p.tactic,
            p.benchmark_unit_price, p.benchmark_comparison,
            "Freigegeben" if p.confirmed else ("Needs Review" if p.needs_review else "Bereit"),
            " | ".join(p.risks),
            p.reference_unit_price,
            (
                (p.ep_per_unit - p.reference_unit_price) / p.reference_unit_price
                if p.reference_unit_price else None
            ),
            p.confidence,
            p.construction_phase,
            p.change_order_potential,
            p.material_or_subcontract_cost_per_unit,
        ])
    boq.append([])
    boq.append(["Aufschlagskalkulation"])
    boq.append(["AGK-Zuschlag", agk])
    boq.append(["BGK-Zuschlag", bgk])
    boq.append(["Wagnis & Gewinn", wg])
    _autofit(boq)

    time_ws = wb.create_sheet("Time & Resource Plan")
    time_ws.append(["Kennzahl", "Wert"])
    time_ws.append(["Personalstunden gesamt", labor_hours])
    time_ws.append(["Maschinenstunden gesamt", machine_hours])
    time_ws.append(["Manntage", man_days])
    time_ws.append(["Crew-Größe", crew_size])
    time_ws.append(["Geschätzte Projektdauer (Wochen)", duration_weeks])
    time_ws.append([])
    time_ws.append(["OZ", "Kurztext", "Arbeitsstd ges.", "Maschinenstd ges.", "Crew"])
    for p in priced_items:
        time_ws.append([p.oz, p.short_text, p.labor_hours, p.machine_hours, p.crew_type])
    for cell in time_ws[1]:
        cell.font = Font(bold=True)
    _autofit(time_ws)

    risks_ws = wb.create_sheet("Risks & Inquiries")
    risks_ws.append([
        "OZ", "Kurztext", "Status", "Risiken", "Bieterfrage Auftraggeber",
        "Nachunternehmer-Anfrage"
    ])
    for cell in risks_ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="F4B183")
    for p in priced_items:
        if p.needs_review or p.risks or p.client_rfi_draft or p.subcontractor_rfq_draft:
            risks_ws.append([
                p.oz, p.short_text,
                "Freigegeben" if p.confirmed else "Needs Review",
                " | ".join(p.risks), p.client_rfi_draft, p.subcontractor_rfq_draft,
            ])
    _autofit(risks_ws)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()

````

## `frontend_demo/.prettierrc`
````
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "printWidth": 100
}

````

## `frontend_demo/.vercel/output/config.json`
````json
{
  "version": 3,
  "framework": {
    "name": "nitro",
    "version": "3.0.260610-beta"
  },
  "overrides": {},
  "routes": [
    {
      "headers": {
        "cache-control": "public, max-age=31536000, immutable"
      },
      "src": "/assets/(.*)"
    },
    {
      "handle": "filesystem"
    },
    {
      "src": "/(.*)",
      "dest": "/__server"
    }
  ]
}
````

## `frontend_demo/.vercel/output/functions/__server.func/.vc-config.json`
````json
{
  "handler": "index.mjs",
  "launcherType": "Nodejs",
  "shouldAddHelpers": false,
  "supportsResponseStreaming": true,
  "runtime": "nodejs24.x"
}
````

## `frontend_demo/.vercel/output/functions/__server.func/_chunks/ssr-renderer.mjs`
````mjs
import { i as toRequest, n as HTTPError } from "../_libs/h3+rou3+srvx.mjs";
//#region #nitro/virtual/vite-services
function lazyService(loader) {
	let promise, mod;
	return { fetch(req) {
		if (mod) return mod.fetch(req);
		if (!promise) promise = loader().then((_mod) => mod = _mod.default || _mod);
		return promise.then((mod) => mod.fetch(req));
	} };
}
var viteServices = { ["ssr"]: lazyService(() => import("../_ssr/ssr.mjs").then((n) => n.i)) };
//#endregion
//#region node_modules/nitro/dist/runtime/vite.mjs
function fetchViteEnv(viteEnvName, input, init) {
	const viteEnv = viteServices[viteEnvName];
	if (!viteEnv) throw HTTPError.status(404);
	return Promise.resolve(viteEnv.fetch(toRequest(input, init)));
}
//#endregion
//#region node_modules/nitro/dist/runtime/internal/vite/ssr-renderer.mjs
/** @param {{ req: Request }} HTTPEvent */
function ssrRenderer({ req }) {
	return fetchViteEnv("ssr", req);
}
//#endregion
export { ssrRenderer as default };

````

## `frontend_demo/.vercel/output/functions/__server.func/_libs/@tanstack/react-router+[...].mjs`
*(?bersprungen: Datei gr??er als 200 KB)*

## `frontend_demo/.vercel/output/functions/__server.func/_libs/@tanstack/router-core+[...].mjs`
````mjs
import { A as getStylesheetHref, D as createInlineCssPlaceholderAsset, I as invariant, L as createSieveCache, N as waitForReason, O as createInlineCssStyleAsset, P as _getRenderedMatches, R as decodePath, S as crossSerializeStream, V as dehydrateSsrMatchId, W as rootRouteId, b as createPlugin, l as createHydrationScripts, u as GLOBAL_TSR, w as isStream, x as createStream } from "./react-router+[...].mjs";
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/transformer.js
/**
* Create a strongly-typed serialization adapter for SSR hydration.
* Use to register custom types with the router serializer.
*/
function createSerializationAdapter(opts) {
	return opts;
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/makeSerovalPlugin.js
/** Create a Seroval plugin for client/server symmetric (de)serialization. */
/* @__NO_SIDE_EFFECTS__ */
function makeSerovalPlugin(serializationAdapter) {
	return /* @__PURE__ */ createPlugin({
		tag: "$TSR/t/" + serializationAdapter.key,
		test: serializationAdapter.test,
		parse: {
			sync(value, ctx) {
				return { v: ctx.parse(serializationAdapter.toSerializable(value)) };
			},
			async async(value, ctx) {
				return { v: await ctx.parse(serializationAdapter.toSerializable(value)) };
			},
			stream(value, ctx) {
				return { v: ctx.parse(serializationAdapter.toSerializable(value)) };
			}
		},
		serialize: void 0,
		deserialize(node, ctx) {
			return serializationAdapter.fromSerializable(ctx.deserialize(node.v));
		}
	});
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/RawStream.js
/**
* Marker class for ReadableStream<Uint8Array> that should be serialized
* with base64/text encoding (JSON and SSR) or binary framing
* (server-function responses).
*
* Wrap your binary streams with this to get efficient serialization:
* ```ts
* // For binary data (files, images, etc.)
* return { data: new RawStream(file.stream()) }
*
* // For text-heavy data (RSC payloads, etc.)
* return { data: new RawStream(rscStream, { hint: 'text' }) }
* ```
*
* RawStreams returned from one server function share one ordered response.
* Arbitrary or sequential consumption can require potentially unbounded client
* buffering for unread data. Cancelling one RawStream discards it locally;
* abort the whole server-function call to cancel the response and server work.
* Consume streams concurrently, cancel unused streams promptly, or use separate
* calls when independent backpressure is required.
*/
var RawStream = class {
	constructor(stream, options) {
		this.stream = stream;
		this.hint = options?.hint ?? "binary";
	}
};
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/ShallowErrorPlugin.js
/**
* this plugin serializes only the `message` part of an Error
* this helps with serializing e.g. a ZodError which has functions attached that cannot be serialized
*/
var ShallowErrorPlugin = /* @__PURE__ */ createPlugin({
	tag: "$TSR/Error",
	test(value) {
		return value instanceof Error;
	},
	parse: {
		sync(value, ctx) {
			return { message: ctx.parse(value.message) };
		},
		async async(value, ctx) {
			return { message: await ctx.parse(value.message) };
		},
		stream(value, ctx) {
			return { message: ctx.parse(value.message) };
		}
	},
	serialize(node, ctx) {
		return "new Error(" + ctx.serialize(node.message) + ")";
	},
	deserialize(node, ctx) {
		return new Error(ctx.deserialize(node.message));
	}
});
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/rawStreamCodec.js
function toBase64(bytes) {
	const chunks = [];
	for (let i = 0; i < bytes.length; i += 32768) chunks.push(String.fromCharCode.apply(null, bytes.subarray(i, i + 32768)));
	return btoa(chunks.join(""));
}
function fromBase64(value) {
	const binary = atob(value);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
	return bytes;
}
var textDecoder = /* @__PURE__ */ new TextDecoder("utf-8", {
	fatal: true,
	ignoreBOM: true
});
/** `'t' + utf8` for a valid UTF-8 chunk, otherwise `'b' + base64`. */
function encodeText(value) {
	try {
		return "t" + textDecoder.decode(value);
	} catch {
		return "b" + toBase64(value);
	}
}
var textEncoder = /* @__PURE__ */ new TextEncoder();
function decodeText(value) {
	const data = value.slice(1);
	return value[0] === "t" ? textEncoder.encode(data) : fromBase64(data);
}
/**
* Pump a byte stream into a Seroval stream, one encoded chunk per read.
* Returns the Seroval stream and a `stop` function that cancels the reader
* without signalling the Seroval stream; the abort signal and read failures
* stop the pump and throw through the Seroval stream.
*/
function pumpEncodedStream(readable, encode, signal) {
	signal?.throwIfAborted();
	const stream = createStream();
	const reader = readable.getReader();
	let active = true;
	const release = () => {
		active = false;
		signal?.removeEventListener("abort", abort);
		reader.releaseLock();
	};
	const stop = (reason) => {
		if (!active) return false;
		reader.cancel(reason).catch(() => {});
		release();
		return true;
	};
	const abort = () => {
		if (stop(signal.reason)) stream.throw(signal.reason);
	};
	signal?.addEventListener("abort", abort);
	(async () => {
		try {
			while (active) {
				const { done, value } = await reader.read();
				if (!active) return;
				if (done) {
					release();
					stream.return(void 0);
					return;
				}
				stream.next(encode(value));
			}
		} catch (error) {
			if (stop(error)) stream.throw(error);
		}
	})();
	return [stream, stop];
}
/** Rebuild a byte stream from encoded Seroval stream chunks. */
function fromEncodedStream(source, decode) {
	let unsubscribe;
	let done = false;
	return new ReadableStream({
		start(controller) {
			const dispose = source.on({
				next(value) {
					if (done) return;
					try {
						controller.enqueue(decode(value));
					} catch (error) {
						done = true;
						const stop = unsubscribe;
						unsubscribe = void 0;
						stop?.();
						controller.error(error);
					}
				},
				throw(error) {
					if (!done) {
						done = true;
						unsubscribe = void 0;
						controller.error(error);
					}
				},
				return() {
					if (!done) {
						done = true;
						unsubscribe = void 0;
						controller.close();
					}
				}
			});
			if (done) dispose();
			else unsubscribe = dispose;
		},
		cancel() {
			const dispose = unsubscribe;
			unsubscribe = void 0;
			dispose?.();
		}
	});
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/RawStreamJSONPlugin.js
/**
* Serializes a RawStream into JSON requests and static-cache responses.
* The optional signal stops the source pump when the request is aborted.
*/
/* @__NO_SIDE_EFFECTS__ */
function createRawStreamJSONPlugin(signal) {
	return /* @__PURE__ */ createPlugin({
		tag: "tss/RawStream",
		test: (value) => value instanceof RawStream,
		parse: { async: async (value, ctx) => {
			const text = await ctx.parse(value.hint === "text");
			const [stream] = pumpEncodedStream(value.stream, value.hint === "text" ? encodeText : toBase64, signal);
			return {
				text,
				stream: await ctx.parse(stream)
			};
		} },
		serialize: void 0,
		deserialize: void 0
	});
}
var RawStreamJSONPlugin = /* @__PURE__ */ createRawStreamJSONPlugin();
/**
* Deserializes the JSON shape above back into a `ReadableStream<Uint8Array>`.
* `test` never matches, so this plugin is inert during serialization and can
* share a plugin list with `RawStreamJSONPlugin`.
*/
var RawStreamJSONDeserializePlugin = /* @__PURE__ */ createPlugin({
	tag: "tss/RawStream",
	test: () => false,
	parse: {},
	serialize: void 0,
	deserialize(node, ctx) {
		return fromEncodedStream(ctx.deserialize(node.stream), ctx.deserialize(node.text) ? decodeText : fromBase64);
	}
});
//#endregion
//#region node_modules/seroval-plugins/dist/web-CDQeyEaf.js
var READABLE_STREAM_FACTORY = {};
var READABLE_STREAM_FACTORY_CONSTRUCTOR = (stream) => new ReadableStream({ start(controller) {
	stream.on({
		next(value) {
			try {
				controller.enqueue(value);
			} catch (_error) {}
		},
		throw(value) {
			controller.error(value);
		},
		return() {
			try {
				controller.close();
			} catch (_error) {}
		}
	});
} });
var ReadableStreamFactoryPlugin = /* @__PURE__ */ createPlugin({
	tag: "seroval-plugins/web/ReadableStreamFactory",
	test(value) {
		return value === READABLE_STREAM_FACTORY;
	},
	parse: {
		sync() {
			return READABLE_STREAM_FACTORY;
		},
		async async() {
			return await Promise.resolve(READABLE_STREAM_FACTORY);
		},
		stream() {
			return READABLE_STREAM_FACTORY;
		}
	},
	serialize() {
		return READABLE_STREAM_FACTORY_CONSTRUCTOR.toString();
	},
	deserialize() {
		return READABLE_STREAM_FACTORY;
	}
});
async function drainStream(stream, reader) {
	try {
		while (true) {
			const result = await reader.read();
			if (result.done) {
				stream.return(result.value);
				reader.releaseLock();
				break;
			}
			stream.next(result.value);
		}
	} catch (error) {
		reader.releaseLock();
		stream.throw(error);
	}
}
function cleanupStream(reader) {
	reader.cancel().catch(() => {});
	reader.releaseLock();
}
function toStream(value) {
	const stream = createStream();
	const reader = value.getReader();
	const cleanup = cleanupStream.bind(null, reader);
	drainStream(stream, reader).catch(cleanup);
	return [stream, cleanup];
}
var ReadableStreamPlugin = /* @__PURE__ */ createPlugin({
	tag: "seroval/plugins/web/ReadableStream",
	extends: [ReadableStreamFactoryPlugin],
	test(value) {
		if (typeof ReadableStream === "undefined") return false;
		return value instanceof ReadableStream;
	},
	parse: {
		sync(_value, ctx) {
			return {
				factory: ctx.parse(READABLE_STREAM_FACTORY),
				stream: ctx.parse(createStream())
			};
		},
		async async(value, ctx) {
			return {
				factory: await ctx.parse(READABLE_STREAM_FACTORY),
				stream: await ctx.parse(toStream(value)[0])
			};
		},
		stream(value, ctx) {
			const [stream, cleanup] = toStream(value);
			ctx.addCleanup(cleanup);
			return {
				factory: ctx.parse(READABLE_STREAM_FACTORY),
				stream: ctx.parse(stream)
			};
		}
	},
	serialize(node, ctx) {
		return "(" + ctx.serialize(node.factory) + ")(" + ctx.serialize(node.stream) + ")";
	},
	deserialize(node, ctx) {
		const stream = ctx.deserialize(node.stream);
		if (!stream || typeof stream !== "object" || !isStream(stream)) throw new Error("Expected a stream source.");
		return READABLE_STREAM_FACTORY_CONSTRUCTOR(stream);
	}
});
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/seroval-plugins.js
/**
* Plugins for JSON transport from a client: serializes RawStream arguments
* and reads plain JSON responses, which never carry RawStream nodes.
*/
/* @__NO_SIDE_EFFECTS__ */
function createDefaultSerovalPlugins(signal) {
	return [
		ShallowErrorPlugin,
		signal ? /* @__PURE__ */ createRawStreamJSONPlugin(signal) : RawStreamJSONPlugin,
		ReadableStreamPlugin
	];
}
/**
* `defaultSerovalPlugins` plus RawStream deserialization, for JSON that may
* carry RawStream nodes: server-function request bodies and cached static
* responses. Seroval deserializes by first tag match, so the deserialize half
* precedes the serialize half; it never matches during serialization.
*/
var defaultSerovalDeserializerPlugins = [RawStreamJSONDeserializePlugin, .../* @__PURE__ */ createDefaultSerovalPlugins()];
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/RawStreamRPCPlugin.js
/**
* Server-side RawStream plugin for multiplexed server-function responses.
* The `hint` is ignored: framed responses always carry raw bytes.
*/
/* @__NO_SIDE_EFFECTS__ */
function createRawStreamRPCPlugin(onRawStream) {
	let nextStreamId = 1;
	return /* @__PURE__ */ createPlugin({
		tag: "tss/RawStream",
		test(value) {
			return value instanceof RawStream;
		},
		parse: { stream(value, ctx) {
			const streamId = nextStreamId++;
			onRawStream(streamId, value.stream);
			return { streamId: ctx.parse(streamId) };
		} },
		serialize: void 0,
		deserialize: void 0
	});
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/makeSsrSerovalPlugin.js
/**
* Create a Seroval plugin for server-side serialization only. `tracker.didRun`
* becomes true once the plugin serialized a value.
*/
/* @__NO_SIDE_EFFECTS__ */
function makeSsrSerovalPlugin(serializationAdapter, tracker) {
	return /* @__PURE__ */ createPlugin({
		tag: "$TSR/t/" + serializationAdapter.key,
		test: serializationAdapter.test,
		parse: { stream(value, ctx) {
			return { v: ctx.parse(serializationAdapter.toSerializable(value)) };
		} },
		serialize(node, ctx) {
			if (tracker) tracker.didRun = true;
			return GLOBAL_TSR + ".t.get(\"" + serializationAdapter.key + "\")(" + ctx.serialize(node.v) + ")";
		},
		deserialize: void 0
	});
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/RawStreamSSRPlugin.js
var nodeBuffer = globalThis.Buffer;
var toBase64Fast = nodeBuffer ? (bytes) => nodeBuffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength).toString("base64") : toBase64;
var BINARY_FACTORY = () => {};
var TEXT_FACTORY = () => {};
var FACTORY_BINARY = `((s,u=1)=>new ReadableStream({start(c,f){f=s.on({next(b){const d=atob(b),a=new Uint8Array(d.length);for(let i=0;i<d.length;i++)a[i]=d.charCodeAt(i);c.enqueue(a)},throw(e){s=u=0;c.error(e)},return(){s=u=0;c.close()}});u=u&&f},cancel(){u&&u()}}))`;
var FACTORY_TEXT = `((s,u=1,e=new TextEncoder)=>new ReadableStream({start(c,f){f=s.on({next(v){const x=v.slice(1);if(v[0]==='t')c.enqueue(e.encode(x));else{const d=atob(x),a=new Uint8Array(d.length);for(let i=0;i<d.length;i++)a[i]=d.charCodeAt(i);c.enqueue(a)}},throw(x){s=u=0;c.error(x)},return(){s=u=0;c.close()}});u=u&&f},cancel(){u&&u()}}))`;
function makeFactoryPlugin(tag, sentinel, source) {
	return createPlugin({
		tag,
		test(value) {
			return value === sentinel;
		},
		parse: { stream() {
			return {};
		} },
		serialize() {
			return source;
		},
		deserialize: void 0
	});
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/serializer/seroval-plugins.ssr.js
/** Server-only plugins for streaming hydration data into HTML. */
var ssrSerovalPlugins = [
	ShallowErrorPlugin,
	/* @__PURE__ */ createPlugin({
		tag: "tss/RawStream",
		extends: [/* @__PURE__ */ makeFactoryPlugin("tss/RawStreamFactory", BINARY_FACTORY, FACTORY_BINARY), /* @__PURE__ */ makeFactoryPlugin("tss/RawStreamFactoryText", TEXT_FACTORY, FACTORY_TEXT)],
		test(value) {
			return value instanceof RawStream;
		},
		parse: { stream(value, ctx) {
			const text = value.hint === "text";
			const factory = ctx.parse(text ? TEXT_FACTORY : BINARY_FACTORY);
			const [stream, stop] = pumpEncodedStream(value.stream, text ? encodeText : toBase64Fast);
			ctx.addCleanup(stop);
			return {
				factory,
				stream: ctx.parse(stream)
			};
		} },
		serialize(node, ctx) {
			return "(" + ctx.serialize(node.factory) + ")(" + ctx.serialize(node.stream) + ")";
		},
		deserialize: void 0
	}),
	ReadableStreamPlugin
];
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/ssr-server.js
function dehydrateMatch(match) {
	const dehydratedMatch = {
		i: dehydrateSsrMatchId(match.id),
		u: match.updatedAt,
		s: match.status
	};
	for (const [key, shorthand] of [
		["__beforeLoadContext", "b"],
		["loaderData", "l"],
		["error", "e"],
		["ssr", "ssr"]
	]) if (match[key] !== void 0) dehydratedMatch[shorthand] = match[key];
	if (match._notFound) dehydratedMatch.g = true;
	return dehydratedMatch;
}
function disposeSerializationSafely(dispose) {
	try {
		dispose?.();
	} catch (err) {
		console.error("Error disposing SSR serialization:", err);
	}
}
function notifyAndClearListeners(listeners, errorMessage, arg) {
	const pending = listeners.slice();
	listeners.length = 0;
	for (const listener of pending) try {
		listener(arg);
	} catch (error) {
		console.error(errorMessage, error);
	}
}
var MANIFEST_CACHE_SIZE = 100;
var manifestCaches = /* @__PURE__ */ new WeakMap();
function getManifestCache(manifest) {
	const cache = manifestCaches.get(manifest);
	if (cache) return cache;
	const newCache = createSieveCache(MANIFEST_CACHE_SIZE);
	manifestCaches.set(manifest, newCache);
	return newCache;
}
function getInlineCssForPreparedRoutes(manifest, preparedRoutes) {
	const styles = manifest.inlineCss?.styles;
	const hrefs = preparedRoutes.inlineCssHrefs;
	if (!styles || !hrefs?.length) return;
	let css = "";
	for (const href of hrefs) css += styles[href];
	return css;
}
function getInlineCssAssetForPreparedRoutes(manifest, preparedRoutes) {
	const css = getInlineCssForPreparedRoutes(manifest, preparedRoutes);
	return css === void 0 ? void 0 : createInlineCssStyleAsset(css);
}
function getMatchedRoutesCacheKey(matches) {
	let cacheKey = "";
	for (let i = 0; i < matches.length; i++) cacheKey += (i === 0 ? "" : "\0") + matches[i].routeId;
	return cacheKey;
}
function getPreparedMatchedManifestRoutes(manifest, matches, cacheKey) {
	{
		const cached = getManifestCache(manifest).get(cacheKey);
		if (cached) return cached;
	}
	const preparedRoutes = prepareMatchedManifestRoutes(manifest, matches);
	getManifestCache(manifest).set(cacheKey, preparedRoutes);
	return preparedRoutes;
}
function prepareMatchedManifestRoutes(manifest, matches) {
	const inlineStyles = manifest.inlineCss?.styles;
	const routes = {};
	if (!inlineStyles) {
		for (const match of matches) {
			const route = manifest.routes[match.routeId];
			if (route) routes[match.routeId] = route;
		}
		return {
			routes,
			hasStrippedRoutes: false
		};
	}
	const inlineCssHrefs = [];
	const seenInlineCssHrefs = /* @__PURE__ */ new Set();
	let hasStrippedRoutes = false;
	for (const match of matches) {
		const routeId = match.routeId;
		const route = manifest.routes[routeId];
		if (!route) continue;
		const nextRoute = stripInlinedStylesheetAssetsFromRoute(inlineStyles, route, inlineCssHrefs, seenInlineCssHrefs);
		if (nextRoute !== route) hasStrippedRoutes = true;
		routes[routeId] = nextRoute;
	}
	return {
		routes,
		hasStrippedRoutes,
		...inlineCssHrefs.length ? { inlineCssHrefs } : {}
	};
}
function stripInlinedStylesheetAssetsFromRoute(inlineStyles, route, inlineCssHrefs, seenInlineCssHrefs) {
	const css = route.css;
	if (!css) return route;
	if (css.length === 0) {
		const nextRoute = { ...route };
		delete nextRoute.css;
		return nextRoute;
	}
	let cssLinks;
	for (let i = 0; i < css.length; i++) {
		const link = css[i];
		const href = getStylesheetHref(link);
		if (inlineStyles[href] === void 0) {
			if (cssLinks) cssLinks.push(link);
			continue;
		}
		if (!seenInlineCssHrefs.has(href)) {
			seenInlineCssHrefs.add(href);
			inlineCssHrefs.push(href);
		}
		if (!cssLinks) cssLinks = css.slice(0, i);
	}
	if (!cssLinks) return route;
	if (cssLinks.length > 0) return {
		...route,
		css: cssLinks
	};
	const nextRoute = { ...route };
	delete nextRoute.css;
	return nextRoute;
}
function hasRouteAssets(route) {
	return !!route.scripts?.length || !!route.css?.length;
}
function hasRequestAssets(assets) {
	return !!assets && (!!assets.preloads?.length || hasRouteAssets(assets));
}
function mergeRequestAssetsIntoRootRoute(rootRoute, requestAssets) {
	const preloads = requestAssets?.preloads?.length ? [...requestAssets.preloads, ...rootRoute?.preloads ?? []] : rootRoute?.preloads;
	const scripts = requestAssets?.scripts?.length ? [...requestAssets.scripts, ...rootRoute?.scripts ?? []] : rootRoute?.scripts;
	const cssLinks = requestAssets?.css?.length ? [...requestAssets.css, ...rootRoute?.css ?? []] : rootRoute?.css;
	return {
		...rootRoute ?? {},
		...preloads?.length ? { preloads } : {},
		...scripts?.length ? { scripts } : {},
		...cssLinks?.length ? { css: cssLinks } : {}
	};
}
/**
* Compose a client-facing manifest from prepared routes, an optional inline
* style, and optional request-scoped assets merged into the root route.
* Shared by the `router.ssr.manifest` getter and `dehydrate()` so the two
* compositions cannot drift.
*/
function composeManifest(scriptFormat, inlineStyle, routes, requestAssets) {
	const base = {
		...scriptFormat ? { scriptFormat } : {},
		...inlineStyle ? { inlineStyle } : {},
		routes
	};
	if (!hasRequestAssets(requestAssets)) return base;
	return {
		...base,
		routes: {
			...routes,
			[rootRouteId]: mergeRequestAssetsIntoRootRoute(routes[rootRouteId], requestAssets)
		}
	};
}
function attachRouterServerSsrUtils({ router, manifest, getRequestAssets }) {
	let memoizedPreparedManifest;
	router.ssr = { get manifest() {
		if (!manifest) return manifest;
		const requestAssets = getRequestAssets?.();
		const hasAssets = hasRequestAssets(requestAssets);
		if (!hasAssets && !manifest.inlineCss) return manifest;
		let inlineCssAsset;
		let routes = manifest.routes;
		if (manifest.inlineCss) {
			const matches = _getRenderedMatches(router.stores.matches.get());
			const cacheKey = getMatchedRoutesCacheKey(matches);
			if (memoizedPreparedManifest?.cacheKey === cacheKey) {
				inlineCssAsset = memoizedPreparedManifest.inlineCssAsset;
				routes = memoizedPreparedManifest.routes;
			} else {
				const preparedManifest = getPreparedMatchedManifestRoutes(manifest, matches, cacheKey);
				inlineCssAsset = getInlineCssAssetForPreparedRoutes(manifest, preparedManifest);
				if (preparedManifest.hasStrippedRoutes) routes = {
					...manifest.routes,
					...preparedManifest.routes
				};
				memoizedPreparedManifest = {
					cacheKey,
					inlineCssAsset,
					routes
				};
			}
		}
		return composeManifest(manifest.scriptFormat, inlineCssAsset, routes, hasAssets ? requestAssets : void 0);
	} };
	let dehydrationPhase = "idle";
	let renderFinished = false;
	const renderFinishedListeners = [];
	const cleanupListeners = [];
	let cleanupStarted = false;
	let settled = false;
	let disposeSerialization;
	const hydrationScripts = createHydrationScripts(router.options.ssr?.nonce);
	const serverSsr = {
		hydrationScripts,
		dehydrate: async (opts) => {
			if (dehydrationPhase !== "idle") invariant();
			opts?.signal?.throwIfAborted();
			dehydrationPhase = "started";
			let matchesToDehydrate = _getRenderedMatches(router.stores.matches.get());
			if (router.isShell()) matchesToDehydrate = matchesToDehydrate.slice(0, 1);
			const matches = matchesToDehydrate.map(dehydrateMatch);
			let manifestToDehydrate = void 0;
			if (manifest) {
				const cacheKey = getMatchedRoutesCacheKey(matchesToDehydrate);
				const preparedManifest = getPreparedMatchedManifestRoutes(manifest, matchesToDehydrate, cacheKey);
				manifestToDehydrate = composeManifest(manifest.scriptFormat, preparedManifest.inlineCssHrefs ? createInlineCssPlaceholderAsset() : void 0, preparedManifest.routes, opts?.requestAssets);
			}
			const dehydratedRouter = {
				manifest: manifestToDehydrate,
				matches
			};
			const dehydrate = router.options.dehydrate;
			const dehydratedData = dehydrate ? opts?.signal ? await waitForReason(dehydrate.call(router.options), opts.signal) : await dehydrate.call(router.options) : void 0;
			opts?.signal?.throwIfAborted();
			if (cleanupStarted) return;
			if (dehydratedData !== void 0) dehydratedRouter.dehydratedData = dehydratedData;
			const trackPlugins = { didRun: false };
			const serializationAdapters = router.options.serializationAdapters;
			const plugins = serializationAdapters ? [...serializationAdapters.map((adapter) => /* @__PURE__ */ makeSsrSerovalPlugin(adapter, trackPlugins)), ...ssrSerovalPlugins] : ssrSerovalPlugins;
			let serializationCompleteSignaled = false;
			let initialSerialized = false;
			const completeScriptSerialization = (result) => {
				if (serializationCompleteSignaled || cleanupStarted) return;
				serializationCompleteSignaled = true;
				const dispose = disposeSerialization;
				disposeSerialization = void 0;
				if (result === true) {
					settled = true;
					hydrationScripts.finish();
				} else if (result) hydrationScripts.fail(result.error);
				if (dispose) queueMicrotask(() => disposeSerializationSafely(dispose));
			};
			let synchronousFailure;
			const dispose = crossSerializeStream(dehydratedRouter, {
				refs: /* @__PURE__ */ new Map(),
				plugins,
				onSerialize: (data, initial) => {
					if (serializationCompleteSignaled || cleanupStarted) return;
					initialSerialized ||= initial;
					if (!hydrationScripts.pushSerializedSource(data, initial, trackPlugins.didRun)) completeScriptSerialization(false);
				},
				onError: (err) => {
					if (serializationCompleteSignaled || cleanupStarted) return;
					console.error("Serialization error:", err);
					synchronousFailure = { error: err };
					completeScriptSerialization({ error: err });
				},
				scopeId: "tsr",
				onDone: () => {
					if (initialSerialized) completeScriptSerialization(true);
				}
			});
			if (cleanupStarted || serializationCompleteSignaled) disposeSerializationSafely(dispose);
			else disposeSerialization = dispose;
			if (synchronousFailure) throw synchronousFailure.error;
		},
		onRenderFinished: (listener) => {
			if (cleanupStarted) return;
			if (renderFinished) {
				try {
					listener();
				} catch (error) {
					console.error("Error in render finished listener:", error);
				}
				return;
			}
			renderFinishedListeners.push(listener);
		},
		onCleanup: (listener) => {
			if (cleanupStarted) {
				try {
					listener(settled);
				} catch (error) {
					console.error("Error in SSR cleanup listener:", error);
				}
				return;
			}
			cleanupListeners.push(listener);
		},
		setRenderFinished: () => {
			if (cleanupStarted || renderFinished) return;
			renderFinished = true;
			hydrationScripts.liftBarrier();
			notifyAndClearListeners(renderFinishedListeners, "Error in render finished listener:", void 0);
		},
		disableHydration: () => {
			if (cleanupStarted || dehydrationPhase === "disabled") return;
			if (dehydrationPhase !== "idle") invariant();
			hydrationScripts.disableHydration();
			dehydrationPhase = "disabled";
		},
		takeInitialHydrationScriptTags: hydrationScripts.takeInitialHydrationScriptTags,
		cleanup() {
			if (cleanupStarted) return;
			cleanupStarted = true;
			hydrationScripts.cleanup();
			const dispose = disposeSerialization;
			disposeSerialization = void 0;
			disposeSerializationSafely(dispose);
			notifyAndClearListeners(cleanupListeners, "Error in SSR cleanup listener:", settled);
			renderFinishedListeners.length = 0;
			router.ssr = void 0;
			router.serverSsr = void 0;
		}
	};
	router.serverSsr = serverSsr;
	for (const listener of router.serverSsrLifecycle?.onServerSsrAttach ?? []) try {
		listener(serverSsr);
	} catch (err) {
		console.error("SSR attach listener error:", err);
	}
}
function getNormalizedURL(url, base) {
	if (typeof url === "string") url = url.replace("\\", "%5C");
	const rawUrl = new URL(url, base);
	const handledProtocolRelativeURL = rawUrl.pathname.startsWith("//");
	const decodedPathname = decodePath(handledProtocolRelativeURL ? rawUrl.pathname.replace(/^\/+/, "/") : rawUrl.pathname);
	const searchParams = new URLSearchParams(rawUrl.search);
	const normalizedHref = decodedPathname + (searchParams.size > 0 ? "?" : "") + searchParams.toString() + rawUrl.hash;
	return {
		url: new URL(normalizedHref, rawUrl.origin),
		handledProtocolRelativeURL
	};
}
//#endregion
//#region node_modules/cookie-es/dist/index.mjs
function splitSetCookieString(cookiesString) {
	if (Array.isArray(cookiesString)) return cookiesString.flatMap((c) => splitSetCookieString(c));
	if (typeof cookiesString !== "string") return [];
	const cookiesStrings = [];
	let pos = 0;
	let start;
	let ch;
	let lastComma;
	let nextStart;
	let cookiesSeparatorFound;
	const skipWhitespace = () => {
		while (pos < cookiesString.length && /\s/.test(cookiesString.charAt(pos))) pos += 1;
		return pos < cookiesString.length;
	};
	const notSpecialChar = () => {
		ch = cookiesString.charAt(pos);
		return ch !== "=" && ch !== ";" && ch !== ",";
	};
	while (pos < cookiesString.length) {
		start = pos;
		cookiesSeparatorFound = false;
		while (skipWhitespace()) {
			ch = cookiesString.charAt(pos);
			if (ch === ",") {
				lastComma = pos;
				pos += 1;
				skipWhitespace();
				nextStart = pos;
				while (pos < cookiesString.length && notSpecialChar()) pos += 1;
				if (pos < cookiesString.length && cookiesString.charAt(pos) === "=") {
					cookiesSeparatorFound = true;
					pos = nextStart;
					cookiesStrings.push(cookiesString.slice(start, lastComma));
					start = pos;
				} else pos = lastComma + 1;
			} else pos += 1;
		}
		if (!cookiesSeparatorFound || pos >= cookiesString.length) cookiesStrings.push(cookiesString.slice(start));
	}
	return cookiesStrings;
}
//#endregion
//#region node_modules/@tanstack/router-core/dist/esm/ssr/headers.js
function toHeadersInstance(init) {
	if (init instanceof Headers) return init;
	else if (Array.isArray(init)) return new Headers(init);
	else if (typeof init === "object") return new Headers(init);
	else return null;
}
function mergeHeaders(...headers) {
	return headers.reduce((acc, header) => {
		const headersInstance = toHeadersInstance(header);
		if (!headersInstance) return acc;
		for (const [key, value] of headersInstance.entries()) if (key === "set-cookie") splitSetCookieString(value).forEach((cookie) => acc.append("set-cookie", cookie));
		else acc.set(key, value);
		return acc;
	}, new Headers());
}
//#endregion
export { defaultSerovalDeserializerPlugins as a, createRawStreamRPCPlugin as i, attachRouterServerSsrUtils as n, makeSerovalPlugin as o, getNormalizedURL as r, createSerializationAdapter as s, mergeHeaders as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_libs/h3+rou3+srvx.mjs`
````mjs
import { PassThrough, Readable } from "node:stream";
//#region node_modules/srvx/dist/_chunks/_url.mjs
function lazyInherit(target, source, sourceKey) {
	for (const key of [...Object.getOwnPropertyNames(source), ...Object.getOwnPropertySymbols(source)]) {
		if (key === "constructor") continue;
		const targetDesc = Object.getOwnPropertyDescriptor(target, key);
		const desc = Object.getOwnPropertyDescriptor(source, key);
		let modified = false;
		if (desc.get) {
			modified = true;
			desc.get = targetDesc?.get || function() {
				return this[sourceKey][key];
			};
		}
		if (desc.set) {
			modified = true;
			desc.set = targetDesc?.set || function(value) {
				this[sourceKey][key] = value;
			};
		}
		if (!targetDesc?.value && typeof desc.value === "function") {
			modified = true;
			desc.value = function(...args) {
				return this[sourceKey][key](...args);
			};
		}
		if (modified) Object.defineProperty(target, key, desc);
	}
}
var _needsNormRE = /(?:(?:^|\/)(?:\.|\.\.|%2e|%2e\.|\.%2e|%2e%2e)(?:\/|$))|[\\^#"<>{}`\x80-\uffff]/i;
var _searchNeedsNormRE = /[#"'<>]/;
var FastURL = /* @__PURE__ */ (() => {
	const NativeURL = globalThis.URL;
	const FastURL = class URL {
		#url;
		#href;
		#protocol;
		#host;
		#pathname;
		#search;
		#searchParams;
		#pos;
		constructor(url) {
			if (typeof url === "string") {
				const isOriginForm = url[0] === "/";
				if (isOriginForm && !_searchNeedsNormRE.test(url)) this.#href = url;
				else this.#url = new NativeURL(isOriginForm ? `http://localhost${url}` : url);
			} else if (_needsNormRE.test(url.pathname) || url.search && _searchNeedsNormRE.test(url.search)) this.#url = new NativeURL(`${url.protocol || "http:"}//${url.host || "localhost"}${url.pathname}${url.search || ""}`);
			else {
				this.#protocol = url.protocol;
				this.#host = url.host;
				this.#pathname = url.pathname;
				this.#search = url.search;
			}
		}
		static [Symbol.hasInstance](val) {
			return val instanceof NativeURL;
		}
		get _url() {
			if (this.#url) return this.#url;
			this.#url = new NativeURL(this.href);
			this.#href = void 0;
			this.#protocol = void 0;
			this.#host = void 0;
			this.#pathname = void 0;
			this.#search = void 0;
			this.#searchParams = void 0;
			this.#pos = void 0;
			return this.#url;
		}
		get href() {
			if (this.#url) return this.#url.href;
			if (!this.#href) this.#href = `${this.#protocol || "http:"}//${this.#host || "localhost"}${this.#pathname || "/"}${this.#search || ""}`;
			return this.#href;
		}
		#getPos() {
			if (!this.#pos) {
				const url = this.href;
				const protoIndex = url.indexOf("://");
				const pathnameIndex = protoIndex === -1 ? -1 : url.indexOf("/", protoIndex + 4);
				const qIndex = pathnameIndex === -1 ? -1 : url.indexOf("?", pathnameIndex);
				this.#pos = [
					protoIndex,
					pathnameIndex,
					qIndex
				];
			}
			return this.#pos;
		}
		get pathname() {
			if (this.#url) return this.#url.pathname;
			if (this.#pathname === void 0) {
				const [, pathnameIndex, queryIndex] = this.#getPos();
				if (pathnameIndex === -1) return this._url.pathname;
				this.#pathname = this.href.slice(pathnameIndex, queryIndex === -1 ? void 0 : queryIndex);
			}
			return this.#pathname;
		}
		get search() {
			if (this.#url) return this.#url.search;
			if (this.#search === void 0) {
				const [, pathnameIndex, queryIndex] = this.#getPos();
				if (pathnameIndex === -1) return this._url.search;
				const url = this.href;
				this.#search = queryIndex === -1 || queryIndex === url.length - 1 ? "" : url.slice(queryIndex);
			}
			return this.#search;
		}
		get searchParams() {
			if (this.#url) return this.#url.searchParams;
			if (!this.#searchParams) this.#searchParams = new URLSearchParams(this.search);
			return this.#searchParams;
		}
		get protocol() {
			if (this.#url) return this.#url.protocol;
			if (this.#protocol === void 0) {
				const [protocolIndex] = this.#getPos();
				if (protocolIndex === -1) return this._url.protocol;
				const url = this.href;
				this.#protocol = url.slice(0, protocolIndex + 1);
			}
			return this.#protocol;
		}
		toString() {
			return this.href;
		}
		toJSON() {
			return this.href;
		}
	};
	lazyInherit(FastURL.prototype, NativeURL.prototype, "_url");
	Object.setPrototypeOf(FastURL.prototype, NativeURL.prototype);
	Object.setPrototypeOf(FastURL, NativeURL);
	return FastURL;
})();
//#endregion
//#region node_modules/srvx/dist/adapters/node.mjs
var NodeResponse = /* @__PURE__ */ (() => {
	const NativeResponse = globalThis.Response;
	const STATUS_CODES = globalThis.process?.getBuiltinModule?.("node:http")?.STATUS_CODES || {};
	class NodeResponse {
		#body;
		#init;
		#headers;
		#response;
		constructor(body, init) {
			this.#body = body;
			this.#init = init;
		}
		static [Symbol.hasInstance](val) {
			return val instanceof NativeResponse;
		}
		get status() {
			return this.#response?.status || this.#init?.status || 200;
		}
		get statusText() {
			return this.#response?.statusText || this.#init?.statusText || STATUS_CODES[this.status] || "";
		}
		get headers() {
			if (this.#response) return this.#response.headers;
			if (this.#headers) return this.#headers;
			const initHeaders = this.#init?.headers;
			return this.#headers = initHeaders instanceof Headers ? initHeaders : new Headers(initHeaders);
		}
		get ok() {
			if (this.#response) return this.#response.ok;
			const status = this.status;
			return status >= 200 && status < 300;
		}
		get _response() {
			if (this.#response) return this.#response;
			let body = this.#body;
			if (body && typeof body.pipe === "function" && !(body instanceof Readable)) {
				const stream = new PassThrough();
				body.pipe(stream);
				const abort = body.abort;
				if (abort) stream.once("close", () => abort());
				body = stream;
			}
			this.#response = new NativeResponse(body, this.#headers ? {
				...this.#init,
				headers: this.#headers
			} : this.#init);
			this.#init = void 0;
			this.#headers = void 0;
			this.#body = void 0;
			return this.#response;
		}
		_toNodeResponse() {
			const status = this.status;
			const statusText = this.statusText;
			let body;
			let contentType;
			let contentLength;
			if (this.#response) body = this.#response.body;
			else if (this.#body) if (this.#body instanceof ReadableStream) body = this.#body;
			else if (typeof this.#body === "string") {
				body = this.#body;
				contentType = "text/plain; charset=UTF-8";
				contentLength = Buffer.byteLength(this.#body);
			} else if (this.#body instanceof ArrayBuffer) {
				body = Buffer.from(this.#body);
				contentLength = this.#body.byteLength;
			} else if (this.#body instanceof Uint8Array) {
				body = this.#body;
				contentLength = this.#body.byteLength;
			} else if (this.#body instanceof DataView) {
				body = Buffer.from(this.#body.buffer);
				contentLength = this.#body.byteLength;
			} else if (this.#body instanceof Blob) {
				body = this.#body.stream();
				contentType = this.#body.type;
				contentLength = this.#body.size;
			} else if (typeof this.#body.pipe === "function") body = this.#body;
			else body = this._response.body;
			const headers = [];
			const initHeaders = this.#init?.headers;
			const headerEntries = this.#response?.headers || this.#headers || (initHeaders ? Array.isArray(initHeaders) ? initHeaders : initHeaders?.entries ? initHeaders.entries() : Object.entries(initHeaders) : void 0);
			let hasContentTypeHeader;
			let hasContentLength;
			if (headerEntries) for (const [key, value] of headerEntries) {
				const lowerKey = typeof key === "string" ? key.toLowerCase() : String(key);
				if (Array.isArray(value)) for (const v of value) headers.push(lowerKey, v);
				else headers.push(lowerKey, value);
				if (lowerKey === "content-type") hasContentTypeHeader = true;
				else if (lowerKey === "content-length") hasContentLength = true;
			}
			if (contentType && !hasContentTypeHeader) headers.push("content-type", contentType);
			if (contentLength && !hasContentLength) headers.push("content-length", String(contentLength));
			this.#init = void 0;
			this.#headers = void 0;
			this.#response = void 0;
			this.#body = void 0;
			return {
				status,
				statusText,
				headers,
				body
			};
		}
	}
	lazyInherit(NodeResponse.prototype, NativeResponse.prototype, "_response");
	Object.setPrototypeOf(NodeResponse, NativeResponse);
	Object.setPrototypeOf(NodeResponse.prototype, NativeResponse.prototype);
	return NodeResponse;
})();
//#endregion
//#region node_modules/h3/node_modules/rou3/dist/index.mjs
var NullProtoObj = /* @__PURE__ */ (() => {
	const e = function() {};
	return e.prototype = Object.create(null), Object.freeze(e.prototype), e;
})();
//#endregion
//#region node_modules/h3/dist/h3.mjs
function decodePathname(pathname) {
	return decodeURI(pathname.includes("%25") ? pathname.replace(/%25/g, "%2525") : pathname);
}
var kEventNS = "h3.internal.event.";
var kEventRes = /* @__PURE__ */ Symbol.for(`${kEventNS}res`);
var kEventResHeaders = /* @__PURE__ */ Symbol.for(`${kEventNS}res.headers`);
var kEventResErrHeaders = /* @__PURE__ */ Symbol.for(`${kEventNS}res.err.headers`);
var H3Event = class {
	app;
	req;
	url;
	context;
	static __is_event__ = true;
	constructor(req, context, app) {
		this.context = context || req.context || new NullProtoObj();
		this.req = req;
		this.app = app;
		const _url = req._url;
		const url = _url && _url instanceof URL ? _url : new FastURL(req.url);
		if (url.pathname.includes("%")) url.pathname = decodePathname(url.pathname);
		this.url = url;
	}
	get res() {
		return this[kEventRes] ||= new H3EventResponse();
	}
	get runtime() {
		return this.req.runtime;
	}
	waitUntil(promise) {
		this.req.waitUntil?.(promise);
	}
	toString() {
		return `[${this.req.method}] ${this.req.url}`;
	}
	toJSON() {
		return this.toString();
	}
	get node() {
		return this.req.runtime?.node;
	}
	get headers() {
		return this.req.headers;
	}
	get path() {
		return this.url.pathname + this.url.search;
	}
	get method() {
		return this.req.method;
	}
};
var H3EventResponse = class {
	status;
	statusText;
	get headers() {
		return this[kEventResHeaders] ||= new Headers();
	}
	get errHeaders() {
		return this[kEventResErrHeaders] ||= new Headers();
	}
};
var DISALLOWED_STATUS_CHARS = /[^\u0009\u0020-\u007E]/g;
function sanitizeStatusMessage(statusMessage = "") {
	return statusMessage.replace(DISALLOWED_STATUS_CHARS, "");
}
function sanitizeStatusCode(statusCode, defaultStatusCode = 200) {
	if (!statusCode) return defaultStatusCode;
	if (typeof statusCode === "string") statusCode = +statusCode;
	if (statusCode < 100 || statusCode > 599) return defaultStatusCode;
	return statusCode;
}
var HTTPError = class HTTPError extends Error {
	get name() {
		return "HTTPError";
	}
	status;
	statusText;
	headers;
	cause;
	data;
	body;
	unhandled;
	static isError(input) {
		return input instanceof Error && input?.name === "HTTPError";
	}
	static status(status, statusText, details) {
		return new HTTPError({
			...details,
			statusText,
			status
		});
	}
	constructor(arg1, arg2) {
		let messageInput;
		let details;
		if (typeof arg1 === "string") {
			messageInput = arg1;
			details = arg2;
		} else details = arg1;
		const status = sanitizeStatusCode(details?.status || details?.statusCode || (details?.cause)?.status || (details?.cause)?.statusCode, 500);
		const statusText = sanitizeStatusMessage(details?.statusText || details?.statusMessage || (details?.cause)?.statusText || (details?.cause)?.statusMessage);
		const message = messageInput || details?.message || (details?.cause)?.message || details?.statusText || details?.statusMessage || [
			"HTTPError",
			status,
			statusText
		].filter(Boolean).join(" ");
		super(message, { cause: details });
		this.cause = details;
		this.status = status;
		this.statusText = statusText || void 0;
		const rawHeaders = details?.headers || (details?.cause)?.headers;
		this.headers = rawHeaders ? new Headers(rawHeaders) : void 0;
		this.unhandled = details?.unhandled ?? (details?.cause)?.unhandled ?? void 0;
		this.data = details?.data;
		this.body = details?.body;
	}
	get statusCode() {
		return this.status;
	}
	get statusMessage() {
		return this.statusText;
	}
	toJSON() {
		const unhandled = this.unhandled;
		return {
			status: this.status,
			statusText: this.statusText,
			unhandled,
			message: unhandled ? "HTTPError" : this.message,
			data: unhandled ? void 0 : this.data,
			...unhandled ? void 0 : this.body
		};
	}
};
function isJSONSerializable(value, _type) {
	if (value === null || value === void 0) return true;
	if (_type !== "object") return _type === "boolean" || _type === "number" || _type === "string";
	if (typeof value.toJSON === "function") return true;
	if (Array.isArray(value)) return true;
	if (typeof value.pipe === "function" || typeof value.pipeTo === "function") return false;
	if (value instanceof NullProtoObj) return true;
	const proto = Object.getPrototypeOf(value);
	return proto === Object.prototype || proto === null;
}
var kNotFound = /* @__PURE__ */ Symbol.for("h3.notFound");
var kHandled = /* @__PURE__ */ Symbol.for("h3.handled");
function toResponse(val, event, config = {}) {
	if (typeof val?.then === "function") return val.then((resolvedVal) => toResponse(resolvedVal, event, config), (r) => toResponse(typeof r === "number" ? new HTTPError({ status: r }) : r, event, config));
	const response = prepareResponse(val, event, config);
	if (typeof response?.then === "function") return toResponse(response, event, config);
	const { onResponse } = config;
	return onResponse ? Promise.resolve(onResponse(response, event)).then(() => response) : response;
}
var HTTPResponse = class {
	#headers;
	#init;
	body;
	constructor(body, init) {
		this.body = body;
		this.#init = init;
	}
	get status() {
		return this.#init?.status || 200;
	}
	get statusText() {
		return this.#init?.statusText || "OK";
	}
	get headers() {
		return this.#headers ||= new Headers(this.#init?.headers);
	}
};
function prepareResponse(val, event, config, nested) {
	if (val === kHandled) return new NodeResponse(null);
	if (val === kNotFound) val = new HTTPError({
		status: 404,
		message: `Cannot find any route matching [${event.req.method}] ${event.url}`
	});
	if (val && val instanceof Error) {
		const isHTTPError = HTTPError.isError(val);
		const error = isHTTPError ? val : new HTTPError(val);
		if (!isHTTPError) {
			error.unhandled = true;
			if (val?.stack) error.stack = val.stack;
		}
		if (error.unhandled && !config.silent) console.error(error);
		const { onError } = config;
		const errHeaders = event[kEventRes]?.[kEventResErrHeaders];
		return onError && !nested ? Promise.resolve(onError(error, event)).catch((error) => error).then((newVal) => prepareResponse(newVal ?? val, event, config, true)) : errorResponse(error, config.debug, errHeaders);
	}
	const preparedRes = event[kEventRes];
	const preparedHeaders = preparedRes?.[kEventResHeaders];
	event[kEventRes] = void 0;
	if (!(val instanceof Response)) {
		const res = prepareResponseBody(val, event, config);
		const status = res.status || preparedRes?.status;
		return new NodeResponse(nullBody(event.req.method, status) ? null : res.body, {
			status,
			statusText: res.statusText || preparedRes?.statusText,
			headers: res.headers && preparedHeaders ? mergeHeaders$1(res.headers, preparedHeaders) : res.headers || preparedHeaders
		});
	}
	if (!preparedHeaders || nested || !val.ok) return val;
	try {
		mergeHeaders$1(val.headers, preparedHeaders, val.headers);
		return val;
	} catch {
		return new NodeResponse(nullBody(event.req.method, val.status) ? null : val.body, {
			status: val.status,
			statusText: val.statusText,
			headers: mergeHeaders$1(val.headers, preparedHeaders)
		});
	}
}
function mergeHeaders$1(base, overrides, target = new Headers(base)) {
	for (const [name, value] of overrides) if (name === "set-cookie") target.append(name, value);
	else target.set(name, value);
	return target;
}
var frozen = (name) => (...args) => {
	throw new Error(`Headers are frozen (${name} ${args.join(", ")})`);
};
var FrozenHeaders = class extends Headers {
	set = frozen("set");
	append = frozen("append");
	delete = frozen("delete");
};
var emptyHeaders = /* @__PURE__ */ new FrozenHeaders({ "content-length": "0" });
var jsonHeaders = /* @__PURE__ */ new FrozenHeaders({ "content-type": "application/json;charset=UTF-8" });
function prepareResponseBody(val, event, config) {
	if (val === null || val === void 0) return {
		body: "",
		headers: emptyHeaders
	};
	const valType = typeof val;
	if (valType === "string") return { body: val };
	if (val instanceof Uint8Array) {
		event.res.headers.set("content-length", val.byteLength.toString());
		return { body: val };
	}
	if (val instanceof HTTPResponse || val?.constructor?.name === "HTTPResponse") return val;
	if (isJSONSerializable(val, valType)) return {
		body: JSON.stringify(val, void 0, config.debug ? 2 : void 0),
		headers: jsonHeaders
	};
	if (valType === "bigint") return {
		body: val.toString(),
		headers: jsonHeaders
	};
	if (val instanceof Blob) {
		const headers = new Headers({
			"content-type": val.type,
			"content-length": val.size.toString()
		});
		let filename = val.name;
		if (filename) {
			filename = encodeURIComponent(filename);
			headers.set("content-disposition", `filename="${filename}"; filename*=UTF-8''${filename}`);
		}
		return {
			body: val.stream(),
			headers
		};
	}
	if (valType === "symbol") return { body: val.toString() };
	if (valType === "function") return { body: `${val.name}()` };
	return { body: val };
}
function nullBody(method, status) {
	return method === "HEAD" || status === 100 || status === 101 || status === 102 || status === 204 || status === 205 || status === 304;
}
function errorResponse(error, debug, errHeaders) {
	let headers = error.headers ? mergeHeaders$1(jsonHeaders, error.headers) : new Headers(jsonHeaders);
	if (errHeaders) headers = mergeHeaders$1(headers, errHeaders);
	return new NodeResponse(JSON.stringify({
		...error.toJSON(),
		stack: debug && error.stack ? error.stack.split("\n").map((l) => l.trim()) : void 0
	}, void 0, debug ? 2 : void 0), {
		status: error.status,
		statusText: error.statusText,
		headers
	});
}
function callMiddleware(event, middleware, handler, index = 0) {
	if (index === middleware.length) return handler(event);
	const fn = middleware[index];
	let nextCalled;
	let nextResult;
	const next = () => {
		if (nextCalled) return nextResult;
		nextCalled = true;
		nextResult = callMiddleware(event, middleware, handler, index + 1);
		return nextResult;
	};
	const ret = fn(event, next);
	return isUnhandledResponse(ret) ? next() : typeof ret?.then === "function" ? ret.then((resolved) => isUnhandledResponse(resolved) ? next() : resolved) : ret;
}
function isUnhandledResponse(val) {
	return val === void 0 || val === kNotFound;
}
function toRequest(input, options) {
	if (typeof input === "string") {
		let url = input;
		if (url[0] === "/") {
			const headers = options?.headers ? new Headers(options.headers) : void 0;
			const host = headers?.get("host") || "localhost";
			url = `${headers?.get("x-forwarded-proto") === "https" ? "https" : "http"}://${host}${url}`;
		}
		return new Request(url, options);
	} else if (options || input instanceof URL) return new Request(input, options);
	return input;
}
function defineHandler(input) {
	if (typeof input === "function") return handlerWithFetch(input);
	const handler = input.handler || (input.fetch ? function _fetchHandler(event) {
		return input.fetch(event.req);
	} : NoHandler);
	return Object.assign(handlerWithFetch(input.middleware?.length ? function _handlerMiddleware(event) {
		return callMiddleware(event, input.middleware, handler);
	} : handler), input);
}
function handlerWithFetch(handler) {
	if ("fetch" in handler) return handler;
	return Object.assign(handler, { fetch: (req) => {
		if (typeof req === "string") req = new URL(req, "http://_");
		if (req instanceof URL) req = new Request(req);
		const event = new H3Event(req);
		try {
			return Promise.resolve(toResponse(handler(event), event));
		} catch (error) {
			return Promise.resolve(toResponse(error, event));
		}
	} });
}
function defineLazyEventHandler(loader) {
	let handler;
	let promise;
	return defineHandler(function lazyHandler(event) {
		return handler ? handler(event) : (promise ??= Promise.resolve(loader()).then(function resolveLazyHandler(r) {
			handler = toEventHandler(r) || toEventHandler(r.default);
			if (typeof handler !== "function") throw new TypeError("Invalid lazy handler", { cause: { resolved: r } });
			return handler;
		})).then((r) => r(event));
	});
}
function toEventHandler(handler) {
	if (typeof handler === "function") return handler;
	if (typeof handler?.handler === "function" && handler.constructor?.["~h3"]) return handler.handler;
	if (typeof handler?.fetch === "function") return function _fetchHandler(event) {
		return handler.fetch(event.req);
	};
}
var NoHandler = () => kNotFound;
var H3Core = class {
	static "~h3" = true;
	config;
	"~middleware";
	"~routes" = [];
	constructor(config = {}) {
		this["~middleware"] = [];
		this.config = config;
		this.fetch = this.fetch.bind(this);
		this.handler = this.handler.bind(this);
	}
	fetch(request) {
		return this["~request"](request);
	}
	handler(event) {
		const route = this["~findRoute"](event);
		if (route) {
			event.context.params = route.params;
			event.context.matchedRoute = route.data;
		}
		const routeHandler = route?.data.handler || NoHandler;
		const middleware = this["~getMiddleware"](event, route);
		return middleware.length > 0 ? callMiddleware(event, middleware, routeHandler) : routeHandler(event);
	}
	"~request"(request, context) {
		const event = new H3Event(request, context, this);
		let handlerRes;
		try {
			if (this.config.onRequest) {
				const hookRes = this.config.onRequest(event);
				handlerRes = typeof hookRes?.then === "function" ? hookRes.then(() => this.handler(event)) : this.handler(event);
			} else handlerRes = this.handler(event);
		} catch (error) {
			handlerRes = Promise.reject(error);
		}
		return toResponse(handlerRes, event, this.config);
	}
	"~findRoute"(_event) {}
	"~addRoute"(_route) {
		this["~routes"].push(_route);
	}
	"~getMiddleware"(_event, route) {
		const routeMiddleware = route?.data.middleware;
		const globalMiddleware = this["~middleware"];
		return routeMiddleware ? [...globalMiddleware, ...routeMiddleware] : globalMiddleware;
	}
};
//#endregion
export { NodeResponse as a, toRequest as i, HTTPError as n, FastURL as o, defineLazyEventHandler as r, H3Core as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_libs/h3-v2+rou3.mjs`
````mjs
import { a as NodeResponse, o as FastURL } from "./h3+rou3+srvx.mjs";
//#region node_modules/h3-v2/node_modules/rou3/dist/index.mjs
var NullProtoObj = /* @__PURE__ */ (() => {
	const e = function() {};
	return e.prototype = Object.create(null), Object.freeze(e.prototype), e;
})();
//#endregion
//#region node_modules/h3-v2/dist/h3-Bz4OPZv_.mjs
function decodePathname(pathname) {
	return decodeURI(pathname.includes("%25") ? pathname.replace(/%25/g, "%2525") : pathname);
}
var kEventNS = "h3.internal.event.";
var kEventRes = /* @__PURE__ */ Symbol.for(`${kEventNS}res`);
var kEventResHeaders = /* @__PURE__ */ Symbol.for(`${kEventNS}res.headers`);
var kEventResErrHeaders = /* @__PURE__ */ Symbol.for(`${kEventNS}res.err.headers`);
var H3Event = class {
	app;
	req;
	url;
	context;
	static __is_event__ = true;
	constructor(req, context, app) {
		this.context = context || req.context || new NullProtoObj();
		this.req = req;
		this.app = app;
		const _url = req._url;
		const url = _url && _url instanceof URL ? _url : new FastURL(req.url);
		if (url.pathname.includes("%")) url.pathname = decodePathname(url.pathname);
		this.url = url;
	}
	get res() {
		return this[kEventRes] ||= new H3EventResponse();
	}
	get runtime() {
		return this.req.runtime;
	}
	waitUntil(promise) {
		this.req.waitUntil?.(promise);
	}
	toString() {
		return `[${this.req.method}] ${this.req.url}`;
	}
	toJSON() {
		return this.toString();
	}
	get node() {
		return this.req.runtime?.node;
	}
	get headers() {
		return this.req.headers;
	}
	get path() {
		return this.url.pathname + this.url.search;
	}
	get method() {
		return this.req.method;
	}
};
var H3EventResponse = class {
	status;
	statusText;
	get headers() {
		return this[kEventResHeaders] ||= new Headers();
	}
	get errHeaders() {
		return this[kEventResErrHeaders] ||= new Headers();
	}
};
var DISALLOWED_STATUS_CHARS = /[^\u0009\u0020-\u007E]/g;
function sanitizeStatusMessage(statusMessage = "") {
	return statusMessage.replace(DISALLOWED_STATUS_CHARS, "");
}
function sanitizeStatusCode(statusCode, defaultStatusCode = 200) {
	if (!statusCode) return defaultStatusCode;
	if (typeof statusCode === "string") statusCode = +statusCode;
	if (statusCode < 100 || statusCode > 599) return defaultStatusCode;
	return statusCode;
}
var HTTPError = class HTTPError extends Error {
	get name() {
		return "HTTPError";
	}
	status;
	statusText;
	headers;
	cause;
	data;
	body;
	unhandled;
	static isError(input) {
		return input instanceof Error && input?.name === "HTTPError";
	}
	static status(status, statusText, details) {
		return new HTTPError({
			...details,
			statusText,
			status
		});
	}
	constructor(arg1, arg2) {
		let messageInput;
		let details;
		if (typeof arg1 === "string") {
			messageInput = arg1;
			details = arg2;
		} else details = arg1;
		const status = sanitizeStatusCode(details?.status || details?.statusCode || (details?.cause)?.status || (details?.cause)?.statusCode, 500);
		const statusText = sanitizeStatusMessage(details?.statusText || details?.statusMessage || (details?.cause)?.statusText || (details?.cause)?.statusMessage);
		const message = messageInput || details?.message || (details?.cause)?.message || details?.statusText || details?.statusMessage || [
			"HTTPError",
			status,
			statusText
		].filter(Boolean).join(" ");
		super(message, { cause: details });
		this.cause = details;
		this.status = status;
		this.statusText = statusText || void 0;
		const rawHeaders = details?.headers || (details?.cause)?.headers;
		this.headers = rawHeaders ? new Headers(rawHeaders) : void 0;
		this.unhandled = details?.unhandled ?? (details?.cause)?.unhandled ?? void 0;
		this.data = details?.data;
		this.body = details?.body;
	}
	get statusCode() {
		return this.status;
	}
	get statusMessage() {
		return this.statusText;
	}
	toJSON() {
		const unhandled = this.unhandled;
		return {
			status: this.status,
			statusText: this.statusText,
			unhandled,
			message: unhandled ? "HTTPError" : this.message,
			data: unhandled ? void 0 : this.data,
			...unhandled ? void 0 : this.body
		};
	}
};
function isJSONSerializable(value, _type) {
	if (value === null || value === void 0) return true;
	if (_type !== "object") return _type === "boolean" || _type === "number" || _type === "string";
	if (typeof value.toJSON === "function") return true;
	if (Array.isArray(value)) return true;
	if (typeof value.pipe === "function" || typeof value.pipeTo === "function") return false;
	if (value instanceof NullProtoObj) return true;
	const proto = Object.getPrototypeOf(value);
	return proto === Object.prototype || proto === null;
}
var kNotFound = /* @__PURE__ */ Symbol.for("h3.notFound");
var kHandled = /* @__PURE__ */ Symbol.for("h3.handled");
function toResponse(val, event, config = {}) {
	if (typeof val?.then === "function") return (val.catch?.((error) => error) || Promise.resolve(val)).then((resolvedVal) => toResponse(resolvedVal, event, config));
	const response = prepareResponse(val, event, config);
	if (typeof response?.then === "function") return toResponse(response, event, config);
	const { onResponse } = config;
	return onResponse ? Promise.resolve(onResponse(response, event)).then(() => response) : response;
}
var HTTPResponse = class {
	#headers;
	#init;
	body;
	constructor(body, init) {
		this.body = body;
		this.#init = init;
	}
	get status() {
		return this.#init?.status || 200;
	}
	get statusText() {
		return this.#init?.statusText || "OK";
	}
	get headers() {
		return this.#headers ||= new Headers(this.#init?.headers);
	}
};
function prepareResponse(val, event, config, nested) {
	if (val === kHandled) return new NodeResponse(null);
	if (val === kNotFound) val = new HTTPError({
		status: 404,
		message: `Cannot find any route matching [${event.req.method}] ${event.url}`
	});
	if (val && val instanceof Error) {
		const isHTTPError = HTTPError.isError(val);
		const error = isHTTPError ? val : new HTTPError(val);
		if (!isHTTPError) {
			error.unhandled = true;
			if (val?.stack) error.stack = val.stack;
		}
		if (error.unhandled && !config.silent) console.error(error);
		const { onError } = config;
		const errHeaders = event[kEventRes]?.[kEventResErrHeaders];
		return onError && !nested ? Promise.resolve(onError(error, event)).catch((error) => error).then((newVal) => prepareResponse(newVal ?? val, event, config, true)) : errorResponse(error, config.debug, errHeaders);
	}
	const preparedRes = event[kEventRes];
	const preparedHeaders = preparedRes?.[kEventResHeaders];
	event[kEventRes] = void 0;
	if (!(val instanceof Response)) {
		const res = prepareResponseBody(val, event, config);
		const status = res.status || preparedRes?.status;
		return new NodeResponse(nullBody(event.req.method, status) ? null : res.body, {
			status,
			statusText: res.statusText || preparedRes?.statusText,
			headers: res.headers && preparedHeaders ? mergeHeaders$1(res.headers, preparedHeaders) : res.headers || preparedHeaders
		});
	}
	if (!preparedHeaders || nested || !val.ok) return val;
	try {
		mergeHeaders$1(val.headers, preparedHeaders, val.headers);
		return val;
	} catch {
		return new NodeResponse(nullBody(event.req.method, val.status) ? null : val.body, {
			status: val.status,
			statusText: val.statusText,
			headers: mergeHeaders$1(val.headers, preparedHeaders)
		});
	}
}
function mergeHeaders$1(base, overrides, target = new Headers(base)) {
	for (const [name, value] of overrides) if (name === "set-cookie") target.append(name, value);
	else target.set(name, value);
	return target;
}
var frozen = (name) => (...args) => {
	throw new Error(`Headers are frozen (${name} ${args.join(", ")})`);
};
var FrozenHeaders = class extends Headers {
	set = frozen("set");
	append = frozen("append");
	delete = frozen("delete");
};
var emptyHeaders = /* @__PURE__ */ new FrozenHeaders({ "content-length": "0" });
var jsonHeaders = /* @__PURE__ */ new FrozenHeaders({ "content-type": "application/json;charset=UTF-8" });
function prepareResponseBody(val, event, config) {
	if (val === null || val === void 0) return {
		body: "",
		headers: emptyHeaders
	};
	const valType = typeof val;
	if (valType === "string") return { body: val };
	if (val instanceof Uint8Array) {
		event.res.headers.set("content-length", val.byteLength.toString());
		return { body: val };
	}
	if (val instanceof HTTPResponse || val?.constructor?.name === "HTTPResponse") return val;
	if (isJSONSerializable(val, valType)) return {
		body: JSON.stringify(val, void 0, config.debug ? 2 : void 0),
		headers: jsonHeaders
	};
	if (valType === "bigint") return {
		body: val.toString(),
		headers: jsonHeaders
	};
	if (val instanceof Blob) {
		const headers = new Headers({
			"content-type": val.type,
			"content-length": val.size.toString()
		});
		let filename = val.name;
		if (filename) {
			filename = encodeURIComponent(filename);
			headers.set("content-disposition", `filename="${filename}"; filename*=UTF-8''${filename}`);
		}
		return {
			body: val.stream(),
			headers
		};
	}
	if (valType === "symbol") return { body: val.toString() };
	if (valType === "function") return { body: `${val.name}()` };
	return { body: val };
}
function nullBody(method, status) {
	return method === "HEAD" || status === 100 || status === 101 || status === 102 || status === 204 || status === 205 || status === 304;
}
function errorResponse(error, debug, errHeaders) {
	let headers = error.headers ? mergeHeaders$1(jsonHeaders, error.headers) : new Headers(jsonHeaders);
	if (errHeaders) headers = mergeHeaders$1(headers, errHeaders);
	return new NodeResponse(JSON.stringify({
		...error.toJSON(),
		stack: debug && error.stack ? error.stack.split("\n").map((l) => l.trim()) : void 0
	}, void 0, debug ? 2 : void 0), {
		status: error.status,
		statusText: error.statusText,
		headers
	});
}
//#endregion
export { toResponse as n, H3Event as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_libs/lucide-react.mjs`
````mjs
import { i as __toESM } from "../_runtime.mjs";
import { K as require_react } from "./@tanstack/react-router+[...].mjs";
//#region node_modules/lucide-react/dist/esm/shared/src/utils.js
var import_react = /* @__PURE__ */ __toESM(require_react());
/**
* @license lucide-react v0.510.0 - ISC
*
* This source code is licensed under the ISC license.
* See the LICENSE file in the root directory of this source tree.
*/
var toKebabCase = (string) => string.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
var toCamelCase = (string) => string.replace(/^([A-Z])|[\s-_]+(\w)/g, (match, p1, p2) => p2 ? p2.toUpperCase() : p1.toLowerCase());
var toPascalCase = (string) => {
	const camelCase = toCamelCase(string);
	return camelCase.charAt(0).toUpperCase() + camelCase.slice(1);
};
var mergeClasses = (...classes) => classes.filter((className, index, array) => {
	return Boolean(className) && className.trim() !== "" && array.indexOf(className) === index;
}).join(" ").trim();
var hasA11yProp = (props) => {
	for (const prop in props) if (prop.startsWith("aria-") || prop === "role" || prop === "title") return true;
};
//#endregion
//#region node_modules/lucide-react/dist/esm/defaultAttributes.js
/**
* @license lucide-react v0.510.0 - ISC
*
* This source code is licensed under the ISC license.
* See the LICENSE file in the root directory of this source tree.
*/
var defaultAttributes = {
	xmlns: "http://www.w3.org/2000/svg",
	width: 24,
	height: 24,
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	strokeWidth: 2,
	strokeLinecap: "round",
	strokeLinejoin: "round"
};
//#endregion
//#region node_modules/lucide-react/dist/esm/Icon.js
/**
* @license lucide-react v0.510.0 - ISC
*
* This source code is licensed under the ISC license.
* See the LICENSE file in the root directory of this source tree.
*/
var Icon = (0, import_react.forwardRef)(({ color = "currentColor", size = 24, strokeWidth = 2, absoluteStrokeWidth, className = "", children, iconNode, ...rest }, ref) => (0, import_react.createElement)("svg", {
	ref,
	...defaultAttributes,
	width: size,
	height: size,
	stroke: color,
	strokeWidth: absoluteStrokeWidth ? Number(strokeWidth) * 24 / Number(size) : strokeWidth,
	className: mergeClasses("lucide", className),
	...!children && !hasA11yProp(rest) && { "aria-hidden": "true" },
	...rest
}, [...iconNode.map(([tag, attrs]) => (0, import_react.createElement)(tag, attrs)), ...Array.isArray(children) ? children : [children]]));
//#endregion
//#region node_modules/lucide-react/dist/esm/createLucideIcon.js
/**
* @license lucide-react v0.510.0 - ISC
*
* This source code is licensed under the ISC license.
* See the LICENSE file in the root directory of this source tree.
*/
var createLucideIcon = (iconName, iconNode) => {
	const Component = (0, import_react.forwardRef)(({ className, ...props }, ref) => (0, import_react.createElement)(Icon, {
		ref,
		iconNode,
		className: mergeClasses(`lucide-${toKebabCase(toPascalCase(iconName))}`, `lucide-${iconName}`, className),
		...props
	}));
	Component.displayName = toPascalCase(iconName);
	return Component;
};
/**
* @license lucide-react v0.510.0 - ISC
*
* This source code is licensed under the ISC license.
* See the LICENSE file in the root directory of this source tree.
*/
var TriangleAlert = createLucideIcon("triangle-alert", [
	["path", {
		d: "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",
		key: "wmoenq"
	}],
	["path", {
		d: "M12 9v4",
		key: "juzpu7"
	}],
	["path", {
		d: "M12 17h.01",
		key: "p32p05"
	}]
]);
//#endregion
export { TriangleAlert as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_libs/tanstack__history.mjs`
````mjs
//#region node_modules/@tanstack/history/dist/esm/index.js
var stateIndexKey = "__TSR_index";
var popStateEvent = "popstate";
var beforeUnloadEvent = "beforeunload";
/**
* Turn protocol-relative inputs such as "//evil.example" into paths
* such as "/evil.example", keeping navigation on the current origin.
*
* For HTTP(S) URLs, WHATWG parsing ignores leading C0 controls and spaces,
* removes tabs/newlines, and treats backslashes as slashes, so inputs like
* "/\evil.example" also need normalization. This only allocates when those
* rules would make the input protocol-relative.
*/
var protocolRelativePrefix = /^[\x00-\x20]*(?:[\\/][\t\n\r]*){2,}/;
function normalizeProtocolRelative(url) {
	const match = protocolRelativePrefix.exec(url);
	return match ? "/" + url.slice(match[0].length) : url;
}
function normalizeHref(href) {
	if (/[\x00-\x1f\x7f]/.test(href)) href = href.replace(/[\x00-\x1f\x7f]/g, (character) => "	\n\r".includes(character) ? "" : encodeURIComponent(character));
	return normalizeProtocolRelative(href);
}
function createHistory(opts) {
	let location = opts.getLocation();
	const subscribers = /* @__PURE__ */ new Set();
	const notify = (action) => {
		location = opts.getLocation();
		subscribers.forEach((subscriber) => subscriber({
			location,
			action
		}));
	};
	const handleIndexChange = (action) => {
		if (opts.notifyOnIndexChange ?? true) notify(action);
		else location = opts.getLocation();
	};
	const tryNavigation = async ({ task, navigateOpts, ...actionInfo }) => {
		if (navigateOpts?.ignoreBlocker ?? false) {
			task();
			return;
		}
		const blockers = opts.getBlockers?.() ?? [];
		const isPushOrReplace = actionInfo.type === "PUSH" || actionInfo.type === "REPLACE";
		if (typeof document !== "undefined" && blockers.length && isPushOrReplace) for (const blocker of blockers) {
			const nextLocation = parseHref(actionInfo.path, actionInfo.state);
			if (await blocker.blockerFn({
				currentLocation: location,
				nextLocation,
				action: actionInfo.type
			})) {
				opts.onBlocked?.();
				return;
			}
		}
		task();
	};
	return {
		get location() {
			return location;
		},
		get length() {
			return opts.getLength();
		},
		subscribers,
		subscribe: (cb) => {
			subscribers.add(cb);
			return () => {
				subscribers.delete(cb);
			};
		},
		push: (path, state, navigateOpts) => {
			const currentIndex = location.state[stateIndexKey];
			state = assignKeyAndIndex(currentIndex + 1, state);
			tryNavigation({
				task: () => {
					opts.pushState(path, state);
					notify({ type: "PUSH" });
				},
				navigateOpts,
				type: "PUSH",
				path,
				state
			});
		},
		replace: (path, state, navigateOpts) => {
			const currentIndex = location.state[stateIndexKey];
			state = assignKeyAndIndex(currentIndex, state);
			tryNavigation({
				task: () => {
					opts.replaceState(path, state);
					notify({ type: "REPLACE" });
				},
				navigateOpts,
				type: "REPLACE",
				path,
				state
			});
		},
		go: (index, navigateOpts) => {
			tryNavigation({
				task: () => {
					opts.go(index, navigateOpts?.ignoreBlocker ?? false);
					handleIndexChange({
						type: "GO",
						index
					});
				},
				navigateOpts,
				type: "GO"
			});
		},
		back: (navigateOpts) => {
			tryNavigation({
				task: () => {
					opts.back(navigateOpts?.ignoreBlocker ?? false);
					handleIndexChange({ type: "BACK" });
				},
				navigateOpts,
				type: "BACK"
			});
		},
		forward: (navigateOpts) => {
			tryNavigation({
				task: () => {
					opts.forward(navigateOpts?.ignoreBlocker ?? false);
					handleIndexChange({ type: "FORWARD" });
				},
				navigateOpts,
				type: "FORWARD"
			});
		},
		canGoBack: () => location.state[stateIndexKey] !== 0,
		createHref: (str) => opts.createHref(str),
		block: (blocker) => {
			if (!opts.setBlockers) return () => {};
			const blockers = opts.getBlockers?.() ?? [];
			opts.setBlockers([...blockers, blocker]);
			return () => {
				const blockers = opts.getBlockers?.() ?? [];
				opts.setBlockers?.(blockers.filter((b) => b !== blocker));
			};
		},
		flush: () => opts.flush?.(),
		destroy: () => opts.destroy?.(),
		notify,
		_getBlockers: () => opts.getBlockers?.() ?? []
	};
}
function assignKeyAndIndex(index, state) {
	const key = createRandomKey();
	return {
		...state,
		key,
		__TSR_key: key,
		[stateIndexKey]: index
	};
}
/**
* Creates a history object that can be used to interact with the browser's
* navigation. This is a lightweight API wrapping the browser's native methods.
* It is designed to work with TanStack Router, but could be used as a standalone API as well.
* IMPORTANT: This API implements history throttling via a microtask to prevent
* excessive calls to the history API. In some browsers, calling history.pushState or
* history.replaceState in quick succession can cause the browser to ignore subsequent
* calls. This API smooths out those differences and ensures that your application
* state will *eventually* match the browser state. In most cases, this is not a problem,
* but if you need to ensure that the browser state is up to date, you can use the
* `history.flush` method to immediately flush all pending state changes to the browser URL.
* @param opts
* @param opts.getHref A function that returns the current href (path + search + hash)
* @param opts.createHref A function that takes a path and returns a href (path + search + hash)
* @returns A history instance
*/
function createBrowserHistory(opts) {
	const win = opts?.window ?? (typeof document !== "undefined" ? window : void 0);
	const originalPushState = win.history.pushState;
	const originalReplaceState = win.history.replaceState;
	let blockers = [];
	const _getBlockers = () => blockers;
	const _setBlockers = (newBlockers) => blockers = newBlockers;
	const createHref = (path) => normalizeHref(opts?.createHref ? opts.createHref(path) : path);
	const parseLocation = opts?.parseLocation ?? (() => parseHref(`${win.location.pathname}${win.location.search}${win.location.hash}`, win.history.state));
	if (!win.history.state?.__TSR_key && !win.history.state?.key) {
		const addedKey = createRandomKey();
		win.history.replaceState({
			[stateIndexKey]: 0,
			key: addedKey,
			__TSR_key: addedKey
		}, "");
	}
	let currentLocation = parseLocation();
	let rollbackLocation;
	let nextPopIsGo = false;
	let ignoreNextPop = false;
	let skipBlockerNextPop = false;
	let ignoreNextBeforeUnload = false;
	const getLocation = () => currentLocation;
	let next;
	const flush = () => {
		if (!next) return;
		history._ignoreSubscribers = true;
		(next[2] ? win.history.pushState : win.history.replaceState)(next[1], "", next[0]);
		history._ignoreSubscribers = false;
		next = void 0;
		rollbackLocation = void 0;
	};
	const queueHistoryAction = (isPush, destHref, state) => {
		const href = opts?.createHref ? createHref(destHref) : void 0;
		const hasPendingAction = !!next;
		if (!hasPendingAction) rollbackLocation = currentLocation;
		currentLocation = parseHref(destHref, state);
		next = [
			href ?? currentLocation.href,
			state,
			next?.[2] || isPush
		];
		if (!hasPendingAction) queueMicrotask(() => flush());
	};
	const onPushPop = (type) => {
		currentLocation = parseLocation();
		history.notify({ type });
	};
	const onPushPopEvent = async () => {
		ignoreNextBeforeUnload = false;
		if (ignoreNextPop) {
			ignoreNextPop = false;
			return;
		}
		const nextLocation = parseLocation();
		const delta = nextLocation.state[stateIndexKey] - currentLocation.state[stateIndexKey];
		const isForward = delta === 1;
		const isBack = delta === -1;
		const isGo = !isForward && !isBack || nextPopIsGo;
		nextPopIsGo = false;
		const action = isGo ? "GO" : isBack ? "BACK" : "FORWARD";
		const notify = isGo ? {
			type: "GO",
			index: delta
		} : { type: isBack ? "BACK" : "FORWARD" };
		if (skipBlockerNextPop) skipBlockerNextPop = false;
		else {
			const blockers = _getBlockers();
			if (typeof document !== "undefined" && blockers.length) {
				for (const blocker of blockers) if (await blocker.blockerFn({
					currentLocation,
					nextLocation,
					action
				})) {
					ignoreNextPop = true;
					win.history.go(-delta);
					history.notify(notify);
					return;
				}
			}
		}
		currentLocation = parseLocation();
		history.notify(notify);
	};
	const onBeforeUnload = (e) => {
		if (ignoreNextBeforeUnload) {
			ignoreNextBeforeUnload = false;
			return;
		}
		let shouldBlock = false;
		const blockers = _getBlockers();
		if (typeof document !== "undefined" && blockers.length) for (const blocker of blockers) {
			const shouldHaveBeforeUnload = blocker.enableBeforeUnload ?? true;
			if (shouldHaveBeforeUnload === true) {
				shouldBlock = true;
				break;
			}
			if (typeof shouldHaveBeforeUnload === "function" && shouldHaveBeforeUnload() === true) {
				shouldBlock = true;
				break;
			}
		}
		if (shouldBlock) {
			e.preventDefault();
			return e.returnValue = "";
		}
	};
	const history = createHistory({
		getLocation,
		getLength: () => win.history.length,
		pushState: (href, state) => queueHistoryAction(true, href, state),
		replaceState: (href, state) => queueHistoryAction(false, href, state),
		back: (ignoreBlocker) => {
			if (ignoreBlocker) {
				skipBlockerNextPop = true;
				ignoreNextBeforeUnload = true;
			}
			return win.history.back();
		},
		forward: (ignoreBlocker) => {
			if (ignoreBlocker) {
				skipBlockerNextPop = true;
				ignoreNextBeforeUnload = true;
			}
			win.history.forward();
		},
		go: (n, ignoreBlocker) => {
			nextPopIsGo = true;
			if (ignoreBlocker) {
				skipBlockerNextPop = true;
				ignoreNextBeforeUnload = true;
			}
			win.history.go(n);
		},
		createHref: (href) => createHref(href),
		flush,
		destroy: () => {
			win.history.pushState = originalPushState;
			win.history.replaceState = originalReplaceState;
			win.removeEventListener(beforeUnloadEvent, onBeforeUnload, { capture: true });
			win.removeEventListener(popStateEvent, onPushPopEvent);
		},
		onBlocked: () => {
			if (rollbackLocation && currentLocation !== rollbackLocation) currentLocation = rollbackLocation;
		},
		getBlockers: _getBlockers,
		setBlockers: _setBlockers,
		notifyOnIndexChange: false
	});
	history._ignoreNextBeforeUnload = (href) => {
		ignoreNextBeforeUnload = false;
		try {
			href = new URL(href, win.document.baseURI).href;
			ignoreNextBeforeUnload = /^https?:/.test(href) && (!href.includes("#") || href.split("#")[0] !== win.location.href.split("#")[0]);
		} catch {}
	};
	win.addEventListener(beforeUnloadEvent, onBeforeUnload, { capture: true });
	win.addEventListener(popStateEvent, onPushPopEvent);
	win.history.pushState = function(...args) {
		const res = originalPushState.apply(win.history, args);
		if (!history._ignoreSubscribers) onPushPop("PUSH");
		return res;
	};
	win.history.replaceState = function(...args) {
		const res = originalReplaceState.apply(win.history, args);
		if (!history._ignoreSubscribers) onPushPop("REPLACE");
		return res;
	};
	return history;
}
var noop = () => {};
var ServerHistory = class {
	constructor(location) {
		this.location = location;
	}
	get length() {
		return 1;
	}
	get subscribers() {
		return this._subscribers ??= /* @__PURE__ */ new Set();
	}
	subscribe() {
		return noop;
	}
	push() {}
	replace() {}
	go() {}
	back() {}
	forward() {}
	canGoBack() {
		return false;
	}
	createHref(href) {
		return normalizeHref(href);
	}
	block() {
		return noop;
	}
	flush() {}
	destroy() {}
	notify() {}
	_getBlockers() {
		return [];
	}
};
/** A fixed request location; server navigation is a no-op. */
function createServerHistory(href) {
	return new ServerHistory(parseHref(href, void 0));
}
function parseHref(href, state) {
	const sanitizedHref = normalizeHref(href);
	const hashIndex = sanitizedHref.indexOf("#");
	const searchIndex = sanitizedHref.indexOf("?");
	if (!state) {
		const key = createRandomKey();
		state = {
			[stateIndexKey]: 0,
			key,
			__TSR_key: key
		};
	}
	return {
		href: sanitizedHref,
		pathname: sanitizedHref.substring(0, hashIndex > 0 ? searchIndex > 0 ? Math.min(hashIndex, searchIndex) : hashIndex : searchIndex > 0 ? searchIndex : sanitizedHref.length),
		hash: hashIndex > -1 ? sanitizedHref.substring(hashIndex) : "",
		search: searchIndex > -1 ? sanitizedHref.slice(searchIndex, hashIndex === -1 ? void 0 : hashIndex) : "",
		state
	};
}
function createRandomKey() {
	return (Math.random() + 1).toString(36).substring(7);
}
//#endregion
export { parseHref as i, createServerHistory as n, normalizeProtocolRelative as r, createBrowserHistory as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_runtime.mjs`
````mjs
import { createRequire } from "node:module";
//#region \0rolldown/runtime.js
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __commonJSMin = (cb, mod) => () => (mod || (cb((mod = { exports: {} }).exports, mod), cb = null), mod.exports);
var __exportAll = (all, no_symbols) => {
	let target = {};
	for (var name in all) __defProp(target, name, {
		get: all[name],
		enumerable: true
	});
	if (!no_symbols) __defProp(target, Symbol.toStringTag, { value: "Module" });
	return target;
};
var __copyProps = (to, from, except, desc) => {
	if (from && typeof from === "object" || typeof from === "function") for (var keys = __getOwnPropNames(from), i = 0, n = keys.length, key; i < n; i++) {
		key = keys[i];
		if (!__hasOwnProp.call(to, key) && key !== except) __defProp(to, key, {
			get: ((k) => from[k]).bind(null, key),
			enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
		});
	}
	return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(isNodeMode || !mod || !mod.__esModule || !__hasOwnProp.call(mod, "default") ? __defProp(target, "default", {
	value: mod,
	enumerable: true
}) : target, mod));
var __require = /* #__PURE__ */ (() => createRequire(import.meta.url))();
//#endregion
export { __toESM as i, __exportAll as n, __require as r, __commonJSMin as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_ssr/draft-rfi-BCcg_iVe.mjs`
````mjs
import { n as TSS_SERVER_FUNCTION, t as createServerFn } from "./ssr.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/draft-rfi-BCcg_iVe.js
var createServerRpc = (serverFnMeta, splitImportFn) => {
	const url = "/_serverFn/" + serverFnMeta.id;
	return Object.assign(splitImportFn, {
		url,
		serverFnMeta,
		[TSS_SERVER_FUNCTION]: true
	});
};
var sharpenRfi_createServerFn_handler = createServerRpc({
	id: "f9146104ae1489df47f2adbe50d0ec594fa07218b0e2bf146360d54c815e8193",
	name: "sharpenRfi",
	filename: "src/lib/draft-rfi.ts"
}, (opts) => sharpenRfi.__executeServer(opts));
var sharpenRfi = createServerFn({ method: "POST" }).validator((input) => input).handler(sharpenRfi_createServerFn_handler, async ({ data }) => {
	const apiKey = process.env.XAI_API_KEY;
	if (!apiKey) return {
		ok: false,
		error: "AI is not available in this environment"
	};
	const res = await fetch("https://api.x.ai/v1/chat/completions", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${apiKey}`
		},
		body: JSON.stringify({
			model: "grok-4.5",
			temperature: .2,
			max_tokens: 280,
			messages: [{
				role: "system",
				content: "You write one short Bieterfrage for a German construction tender, in formal German, citing VOB/A only if it fits. No price. No preamble. One paragraph the estimator can paste into a letter."
			}, {
				role: "user",
				content: `Position ${data.oz}: ${data.title}\n${data.longText}\nWhy it is risky: ${data.rationale}\nCurrent draft: ${data.draft}`
			}]
		})
	});
	if (!res.ok) return {
		ok: false,
		error: `Model error ${res.status}`
	};
	const text = (await res.json()).choices?.[0]?.message?.content?.trim() ?? "";
	if (!text) return {
		ok: false,
		error: "Empty answer"
	};
	return {
		ok: true,
		text
	};
});
//#endregion
export { sharpenRfi_createServerFn_handler };

````

## `frontend_demo/.vercel/output/functions/__server.func/_ssr/empty-plugin-adapters-D9UWiqvJ.mjs`
````mjs
//#region node_modules/.nitro/vite/services/ssr/assets/empty-plugin-adapters-D9UWiqvJ.js
var pluginSerializationAdapters = [];
var hasPluginAdapters = false;
//#endregion
export { hasPluginAdapters, pluginSerializationAdapters };

````

## `frontend_demo/.vercel/output/functions/__server.func/_ssr/router-Cdp50kSt.mjs`
````mjs
import { _ as createFileRoute, d as Scripts, f as HeadContent, g as lazyRouteComponent, h as Outlet, m as createRouter, v as createRootRoute, y as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { t as TriangleAlert } from "../_libs/lucide-react.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/router-Cdp50kSt.js
var import_jsx_runtime = require_jsx_runtime();
var FALLBACK_MESSAGE = "An unexpected error occurred. Try reloading the page.";
function errorMessage(error) {
	if (error instanceof Error && error.message) return error.message;
	if (typeof error === "string" && error) return error;
	return FALLBACK_MESSAGE;
}
function AppErrorComponent({ error }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", {
		className: "flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
				className: "text-red-500",
				"aria-hidden": "true",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TriangleAlert, {
					className: "size-10",
					strokeWidth: 2
				})
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
				className: "text-lg font-semibold",
				children: "Something went wrong"
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "max-w-md text-sm break-words text-zinc-500 dark:text-zinc-400",
				children: errorMessage(error)
			})
		]
	});
}
/**
* App-wide client provider mounted once near the root (in `src/routes/__root.tsx`):
*
*   <AuthProvider><Outlet /></AuthProvider>
*
* Better Auth's React client (`@/lib/auth/client`) needs NO context provider —
* its `useSession()` works standalone — so this is a passthrough today. It's
* kept as the single, stable mount point for any future client-side providers
* (e.g. a toast or theme provider) without churning the root shell.
*/
function AuthProvider({ children }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(import_jsx_runtime.Fragment, { children });
}
var styles_default = "/assets/styles-CMHoM8DC.css";
var Route$1 = createRootRoute({
	head: () => ({
		meta: [
			{ charSet: "utf-8" },
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1"
			},
			{ title: "Bid & Risk Assistant" },
			{
				name: "theme-color",
				content: "#1c1915"
			}
		],
		links: [
			{
				rel: "icon",
				type: "image/svg+xml",
				href: "/favicon.svg"
			},
			{
				rel: "stylesheet",
				href: styles_default
			},
			{
				rel: "preconnect",
				href: "https://fonts.googleapis.com"
			},
			{
				rel: "preconnect",
				href: "https://fonts.gstatic.com",
				crossOrigin: "anonymous"
			},
			{
				rel: "stylesheet",
				href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
			}
		]
	}),
	component: () => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("html", {
		lang: "en",
		suppressHydrationWarning: true,
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("head", { children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(HeadContent, {}) }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("body", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(AuthProvider, { children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Outlet, {}) }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Scripts, {})] })]
	})
});
var $$splitComponentImporter = () => import("./routes-DvTkTdoK.mjs");
var rootRouteChildren = { IndexRoute: createFileRoute("/")({ component: lazyRouteComponent($$splitComponentImporter, "component") }).update({
	id: "/",
	path: "/",
	getParentRoute: () => Route$1
}) };
var routeTree = Route$1._addFileChildren(rootRouteChildren)._addFileTypes();
function getRouter() {
	return createRouter({
		routeTree,
		defaultErrorComponent: AppErrorComponent
	});
}
//#endregion
export { getRouter };

````

## `frontend_demo/.vercel/output/functions/__server.func/_ssr/routes-DvTkTdoK.mjs`
````mjs
import { i as __toESM } from "../_runtime.mjs";
import { K as require_react, y as require_jsx_runtime } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as TSS_SERVER_FUNCTION, r as getServerFnById, t as createServerFn } from "./ssr.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/routes-DvTkTdoK.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function naturalOzCompare(a, b) {
	const aa = String(a).split(".");
	const bb = String(b).split(".");
	const length = Math.max(aa.length, bb.length);
	for (let index = 0; index < length; index += 1) {
		const left = aa[index] ?? "";
		const right = bb[index] ?? "";
		const leftNumber = /^\d+$/.test(left);
		const rightNumber = /^\d+$/.test(right);
		if (leftNumber && rightNumber) {
			const difference = Number(left) - Number(right);
			if (difference !== 0) return difference;
		} else {
			const difference = left.localeCompare(right, "de");
			if (difference !== 0) return difference;
		}
	}
	return 0;
}
/** Real submitted total on StBALV23040.D86 — the reveal number. */
var REVEAL_BID = 897305.45;
var SAMPLE_NAME = "NUMMER_001 · blank BoQ (248 positions)";
var ITEMS = [
	{
		oz: "01.01.0010",
		title: "Baugrube ausheben, Bodenklasse 3–5",
		longText: "Aushub einschließlich Laden und Abfuhr bis 15 km. Böschungen nach statischer Vorgabe.",
		qty: 1840,
		unit: "m³",
		benchmark: 18.4,
		laborShare: .35,
		hoursPerUnit: .08,
		materialPerUnit: 4.2,
		kind: null,
		rationale: "Unit price sits inside the reference band for excavation (median €18.40/m³ across priced sewer jobs).",
		rfi: ""
	},
	{
		oz: "01.02.0140",
		title: "Rohrgraben DN 300, einschließlich Verbau",
		longText: "Graben für Steinzeugrohr DN 300, Verbau nach Wahl des AN, Sohle plan.",
		qty: 620,
		unit: "m",
		benchmark: 86,
		laborShare: .55,
		hoursPerUnit: .55,
		materialPerUnit: 22,
		kind: "vague",
		rationale: "“Verbau nach Wahl des AN” leaves shoring method and groundwater unspecified. In  the priced twin this line alone moves five-figure money.",
		rfi: "Bitte die geforderte Verbauart (Verbaubox / Trägerbohlwand / geböscht) und den Bemessungswasserstand verbindlich vorgeben, damit die Position ohne Nachtrag kalkulierbar ist."
	},
	{
		oz: "01.02.0210",
		title: "Steinzeugrohr DN 300 liefern und verlegen",
		longText: "Kanalrohr Steinzeug DN 300, Verbindungssystem F, einschließlich Dichtung.",
		qty: 610,
		unit: "m",
		benchmark: 142,
		laborShare: .28,
		hoursPerUnit: .22,
		materialPerUnit: 96,
		kind: "qty",
		rationale: "Pipe length is 10 m shorter than the trench (620 m). A missing connection or a typo — either way the join does not close.",
		rfi: "Die Rohrleitung (610 m) ist kürzer als der zugehörige Graben (620 m). Bitte die maßgebende Länge bestätigen."
	},
	{
		oz: "01.03.0040",
		title: "Schacht DN 1000, Tiefe bis 3,00 m",
		longText: "Fertigteilschacht einschließlich Schachtabdeckung Klasse D 400.",
		qty: 14,
		unit: "St",
		benchmark: 2480,
		laborShare: .4,
		hoursPerUnit: 6.5,
		materialPerUnit: 1450,
		kind: null,
		rationale: "Comparable shafts in the priced set cluster tightly around €2,480.",
		rfi: ""
	},
	{
		oz: "01.04.0080",
		title: "Heizungswartung Baustelle, wöchentlich",
		longText: "Bereitstellung und wöchentliche Wartung der Baustellenheizung für die Wintermonate.",
		qty: 28,
		unit: "Wo",
		benchmark: .2,
		laborShare: .9,
		hoursPerUnit: 1.2,
		materialPerUnit: 35,
		kind: "outlier",
		rationale: "A real competitor priced this at €0.20/week (total €5.60). Same-trade medians for site heating sit two orders of magnitude higher. Classic speculative underprice on a line that will be measured.",
		rfi: "Die Position ist mit €0,20/Woche nicht auskömmlich. Bitte Leistungsumfang (Gerätetyp, Brennstoff, Betriebsstunden) festlegen, damit ein marktüblicher Einheitspreis angeboten werden kann."
	},
	{
		oz: "02.01.0030",
		title: "Tragschicht 0/32, d = 20 cm",
		longText: "Frostschutzschicht liefern, einbauen und verdichten.",
		qty: 2400,
		unit: "m²",
		benchmark: 11.6,
		laborShare: .32,
		hoursPerUnit: .04,
		materialPerUnit: 6.8,
		kind: null,
		rationale: "Inside the reference band for unbound base.",
		rfi: ""
	},
	{
		oz: "02.01.0110",
		title: "Asphaltdeckschicht AC 11, d = 4 cm",
		longText: "Deckschicht nach ZTV Asphalt, Einbauort nach Vorgabe AG.",
		qty: 2380,
		unit: "m²",
		benchmark: 22.5,
		laborShare: .25,
		hoursPerUnit: .03,
		materialPerUnit: 16.4,
		kind: "vague",
		rationale: "“Einbauort nach Vorgabe AG” with no stationing. Area is 20 m² under the base course — small, but the clause is a change-order door.",
		rfi: "Bitte den Einbauort und die Verkehrsfreigabe (Belastungsklasse) vor Angebotsabgabe verbindlich angeben."
	},
	{
		oz: "02.03.0020",
		title: "Bordstein hoch 15/25 setzen",
		longText: "Bordstein aus Beton, einschließlich Fundament und Rückenstütze.",
		qty: 480,
		unit: "m",
		benchmark: 38,
		laborShare: .5,
		hoursPerUnit: .22,
		materialPerUnit: 14,
		kind: null,
		rationale: "Matches priced kerb lines within a few percent.",
		rfi: ""
	},
	{
		oz: "03.01.0010",
		title: "Bedarfsposition: Kampfmittelräumung",
		longText: "Eventualposition. Sondierung und Bergung nach Bedarf, Abrechnung nach Aufwand.",
		qty: 1,
		unit: "psch",
		benchmark: 4500,
		laborShare: .7,
		hoursPerUnit: 40,
		materialPerUnit: 800,
		kind: "gap",
		rationale: "Provisional lump sum with no quantity driver. High chance it is either never called or explodes. Price it tactically, not as a firm cost.",
		rfi: "Bitte den Erwartungswert (Sondierungsfläche, Fundwahrscheinlichkeit) angeben oder die Position als Bedarfsposition ohne Wertung kennzeichnen."
	},
	{
		oz: "03.02.0060",
		title: "Wasserhaltung, offene Haltung",
		longText: "Wasserhaltung für die Bauzeit, Pumpen und Ableitung, nach Abstimmung mit dem AG.",
		qty: 12,
		unit: "Wo",
		benchmark: null,
		laborShare: .6,
		hoursPerUnit: 8,
		materialPerUnit: 220,
		kind: "vague",
		rationale: "No comparable in the 720 priced same-trade items (kein Vergleichswert). Scope (“nach Abstimmung”) cannot be priced firmly.",
		rfi: "Bitte den Bemessungszufluss, die Ableitstelle und die maximale Betriebsdauer festlegen."
	},
	{
		oz: "03.04.0020",
		title: "Verkehrssicherung nach RSA",
		longText: "Aufstellen, Vorhalten und Abbauen der Verkehrszeichen und Absperrungen.",
		qty: 16,
		unit: "Wo",
		benchmark: 640,
		laborShare: .45,
		hoursPerUnit: 3.2,
		materialPerUnit: 180,
		kind: null,
		rationale: "Weekly traffic management sits near the reference median.",
		rfi: ""
	},
	{
		oz: "04.01.0100",
		title: "Hausanschluss DN 150 anbinden",
		longText: "Anbindung bestehender Hausanschlüsse, Lage nach örtlichem Aufmaß.",
		qty: 2,
		unit: "St",
		benchmark: 890,
		laborShare: .65,
		hoursPerUnit: 6,
		materialPerUnit: 210,
		kind: "qty",
		rationale: "Only 2 connections are billed. Street length and shaft count imply closer to 18–22. If the count is wrong, a high unit price captures the overrun.",
		rfi: "Im LV sind 2 Hausanschlüsse ausgeschrieben. Nach Schachtanzahl und Straßenlänge erwarten wir eine deutlich höhere Stückzahl. Bitte die vollständige Anschlusszählung beifügen."
	}
];
var DEFAULT_RATES = {
	earth: 46,
	pipe: 52,
	pave: 49,
	fitter: 58,
	machine: 95,
	material: 1,
	agk: 12,
	wg: 8
};
function crewOf(oz) {
	if (oz.startsWith("02.")) return "pave";
	if (oz.startsWith("04.") || oz.startsWith("01.02") || oz.startsWith("01.03")) return "pipe";
	if (oz.startsWith("01.04") || oz.startsWith("03.02") || oz.startsWith("03.04")) return "fitter";
	return "earth";
}
var CREW_LABEL = {
	earth: "Earthworks crew",
	pipe: "Pipe crew",
	pave: "Paving crew",
	fitter: "Fitter"
};
function crewLabel(oz) {
	return CREW_LABEL[crewOf(oz)];
}
function overhead(r) {
	return (1 + r.agk / 100) * (1 + r.wg / 100);
}
var BASE_OH = 1.12 * 1.08;
/** Unit price from the observed bid, moved by the crew that actually does the work. */
function unitPrice(item, r, tactic = 1) {
	const oh = overhead(r);
	const crewW = r[crewOf(item.oz)];
	const wageFactor = 1 + (crewW / 48 - 1) * 1.6;
	const machFactor = 1 + (r.machine / 95 - 1) * 1.2;
	if (item.benchmark != null && item.kind !== "outlier") {
		const labor = item.laborShare;
		const machineInsideLabor = crewOf(item.oz) === "earth" || crewOf(item.oz) === "pave" ? .45 : .2;
		return {
			ep: item.benchmark * ((1 - labor) * (.55 + .45 * r.material) + labor * ((1 - machineInsideLabor) * wageFactor + machineInsideLabor * machFactor)) * (oh / BASE_OH) * tactic,
			source: "benchmark"
		};
	}
	const machineShare = crewOf(item.oz) === "fitter" ? .65 : .3;
	return {
		ep: (item.hoursPerUnit * (1 - machineShare) * crewW + item.hoursPerUnit * machineShare * r.machine + item.materialPerUnit * r.material) * oh * tactic,
		source: "built-up"
	};
}
var BILL_SCALE = 2.72;
function lineTotal(item, r, fix) {
	const qty = fix?.qty ?? item.qty;
	return unitPrice(item, r, fix?.tactic ?? 1).ep * qty * BILL_SCALE;
}
function estimateTotal(items, r, fixes = {}) {
	return items.reduce((s, it) => s + lineTotal(it, r, fixes[it.oz]), 0);
}
function findings(items, r, fixes = {}) {
	return items.filter((it) => it.kind).map((item) => {
		const fix = fixes[item.oz];
		const tactic = fix?.tactic ?? 1;
		const qty = fix?.qty ?? item.qty;
		const { ep, source } = unitPrice(item, r, tactic);
		const total = ep * qty * BILL_SCALE;
		const exposure = item.kind === "qty" ? Math.abs(item.qty - qty) * ep * BILL_SCALE + total * .12 : total * .18;
		return {
			item,
			ep,
			total,
			leverage: item.kind === "outlier" ? Math.max(total, 12e3) : Math.max(exposure, 4e3),
			source
		};
	}).sort((a, b) => b.leverage - a.leverage);
}
function euro(n) {
	return new Intl.NumberFormat("de-DE", {
		style: "currency",
		currency: "EUR",
		maximumFractionDigits: 2
	}).format(n);
}
function num(n, d = 2) {
	return new Intl.NumberFormat("de-DE", {
		maximumFractionDigits: d,
		minimumFractionDigits: d
	}).format(n);
}
var createSsrRpc = (functionId) => {
	const url = "/_serverFn/" + functionId;
	const serverFnMeta = { id: functionId };
	const fn = async (...args) => {
		return (await getServerFnById(functionId, { origin: "server" }))(...args);
	};
	return Object.assign(fn, {
		url,
		serverFnMeta,
		[TSS_SERVER_FUNCTION]: true
	});
};
var sharpenRfi = createServerFn({ method: "POST" }).validator((input) => input).handler(createSsrRpc("f9146104ae1489df47f2adbe50d0ec594fa07218b0e2bf146360d54c815e8193"));
var KIND = {
	outlier: "Speculative price",
	vague: "Vague scope",
	qty: "Quantity clash",
	gap: "Provisional"
};
function Home() {
	const [rates, setRates] = (0, import_react.useState)(DEFAULT_RATES);
	const [fixes, setFixes] = (0, import_react.useState)({});
	const [letters, setLetters] = (0, import_react.useState)({});
	const [busy, setBusy] = (0, import_react.useState)(null);
	const [aiNote, setAiNote] = (0, import_react.useState)(null);
	const [open, setOpen] = (0, import_react.useState)("01.04.0080");
	const [revealed, setRevealed] = (0, import_react.useState)(true);
	const [analysisRunning, setAnalysisRunning] = (0, import_react.useState)(false);
	const [analysisProgress, setAnalysisProgress] = (0, import_react.useState)(0);
	const [analysisStatus, setAnalysisStatus] = (0, import_react.useState)("Bereit zur Bereichsanalyse");
	const [analysisError, setAnalysisError] = (0, import_react.useState)(null);
	const sortedItems = (0, import_react.useMemo)(() => [...ITEMS].sort((a, b) => naturalOzCompare(a.oz, b.oz)), []);
	const total = (0, import_react.useMemo)(() => estimateTotal(ITEMS, rates, fixes), [rates, fixes]);
	const rows = (0, import_react.useMemo)(() => findings(ITEMS, rates, fixes), [rates, fixes]);
	const delta = total - REVEAL_BID;
	const pct = delta / REVEAL_BID * 100;
	function setRate(key, value) {
		setRates((r) => ({
			...r,
			[key]: value
		}));
	}
	function patch(oz, qty, tactic) {
		setFixes((f) => ({
			...f,
			[oz]: {
				qty,
				tactic
			}
		}));
	}
	async function runBatchDemo() {
		setAnalysisRunning(true);
		setAnalysisError(null);
		setAnalysisProgress(0);
		const batchSize = 20;
		const batchCount = Math.ceil(sortedItems.length / batchSize);
		try {
			for (let batchIndex = 0; batchIndex < batchCount; batchIndex += 1) {
				const from = batchIndex * batchSize + 1;
				const to = Math.min(sortedItems.length, (batchIndex + 1) * batchSize);
				const section = (sortedItems[batchIndex * batchSize]?.oz ?? "").split(".")[0] || "01";
				setAnalysisStatus(`Analysiere Bereich ${section} – Positionen ${from}–${to} von ${sortedItems.length}…`);
				await new Promise((resolve) => window.setTimeout(resolve, 220));
				setAnalysisProgress(Math.round((batchIndex + 1) / batchCount * 100));
			}
			setAnalysisStatus("Bereichsanalyse abgeschlossen");
		} catch {
			setAnalysisError("Netzwerkabbruch oder Timeout. Bitte die Analyse erneut starten.");
		} finally {
			setAnalysisRunning(false);
		}
	}
	function exportRfi() {
		const lines = [
			"Bieterfragen-Katalog",
			SAMPLE_NAME,
			"",
			"Nach VOB/A bitten wir um Klarstellung der folgenden Positionen vor Submission.",
			""
		];
		rows.forEach((f, i) => {
			const text = letters[f.item.oz] || f.item.rfi;
			if (!text) return;
			lines.push(`${i + 1}. Pos. ${f.item.oz} — ${f.item.title}`);
			lines.push(text);
			lines.push("");
		});
		const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
		const a = document.createElement("a");
		a.href = URL.createObjectURL(blob);
		a.download = "Bieterfragen-Katalog.txt";
		a.click();
		URL.revokeObjectURL(a.href);
	}
	async function sharpen(oz, title, longText, rationale, draft) {
		setBusy(oz);
		setAiNote(null);
		try {
			const res = await sharpenRfi({ data: {
				oz,
				title,
				longText,
				rationale,
				draft
			} });
			if (!res.ok) setAiNote(res.error);
			else setLetters((m) => ({
				...m,
				[oz]: res.text
			}));
		} catch {
			setAiNote("Could not reach the model. The drafted question stays as written.");
		} finally {
			setBusy(null);
		}
	}
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("main", {
		className: "mx-auto max-w-6xl px-4 py-8 sm:px-6",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("header", {
				className: "mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "font-mono text-xs tracking-widest text-muted uppercase",
						children: "Estimator desk"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
						className: "mt-1 text-3xl font-medium tracking-tight",
						children: "Bid & Risk"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-2 max-w-xl text-muted",
						children: "It reads a construction tender, finds the lines that will cost the contractor money, and drafts the clarification letter."
					})
				] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
					type: "button",
					onClick: exportRfi,
					className: "h-11 rounded-full bg-accent px-5 text-sm font-medium text-surface",
					children: "Export Bieterfragen"
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "mb-6 rounded-xl border border-line bg-surface px-4 py-3",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mb-2 flex items-center justify-between gap-3",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "min-w-0",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
								className: "font-mono text-xs tracking-widest text-muted uppercase",
								children: "KI-Batch-Fortschritt"
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
								className: "mt-1 text-sm overflow-wrap-anywhere",
								children: analysisStatus
							})]
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
							type: "button",
							className: "shrink-0 h-9 rounded-lg border border-line px-3 text-sm",
							disabled: analysisRunning,
							onClick: runBatchDemo,
							children: analysisRunning ? "Analysiert…" : "Analyse starten / Retry"
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "h-2 overflow-hidden rounded-full bg-line",
						role: "progressbar",
						"aria-valuemin": 0,
						"aria-valuemax": 100,
						"aria-valuenow": analysisProgress,
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "h-full bg-accent transition-[width]",
							style: { width: `${analysisProgress}%` }
						})
					}),
					analysisError && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-2 rounded-lg bg-accent-soft px-3 py-2 text-sm text-warn overflow-wrap-anywhere",
						children: analysisError
					})
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "mb-6 grid gap-3 sm:grid-cols-3",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
						label: "Our estimate",
						value: euro(total),
						hint: "Scaled from the worked slice to the 248-item twin"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
						label: "Submitted bid",
						value: revealed ? euro(REVEAL_BID) : "—",
						hint: "StBALV23040 · same bill"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
						label: "Gap",
						value: revealed ? `${pct >= 0 ? "+" : ""}${num(pct, 1)} %` : "—",
						hint: revealed ? euro(delta) : "Reveal to compare"
					})
				]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "mb-6 grid gap-4 lg:grid-cols-[280px_1fr]",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("aside", {
					className: "rounded-xl border border-line bg-surface p-4",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mb-3 font-mono text-xs tracking-widest text-muted uppercase",
							children: "Crew & plant"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Earthworks €/h",
							min: 32,
							max: 78,
							step: 1,
							value: rates.earth,
							onChange: (n) => setRate("earth", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Pipe crew €/h",
							min: 32,
							max: 78,
							step: 1,
							value: rates.pipe,
							onChange: (n) => setRate("pipe", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Paving €/h",
							min: 32,
							max: 78,
							step: 1,
							value: rates.pave,
							onChange: (n) => setRate("pave", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Fitter €/h",
							min: 32,
							max: 86,
							step: 1,
							value: rates.fitter,
							onChange: (n) => setRate("fitter", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Excavator €/h",
							min: 55,
							max: 160,
							step: 1,
							value: rates.machine,
							onChange: (n) => setRate("machine", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Material index",
							min: .8,
							max: 1.4,
							step: .05,
							value: rates.material,
							onChange: (n) => setRate("material", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "AGK %",
							min: 6,
							max: 22,
							step: 1,
							value: rates.agk,
							onChange: (n) => setRate("agk", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Slider, {
							label: "Wagnis & Gewinn %",
							min: 2,
							max: 16,
							step: 1,
							value: rates.wg,
							onChange: (n) => setRate("wg", n)
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
							type: "button",
							className: "mt-1 h-10 w-full rounded-lg border border-line text-sm",
							onClick: () => setRevealed((v) => !v),
							children: revealed ? "Hide real bid" : "Reveal real bid"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "mt-3 text-xs leading-relaxed text-muted",
							children: "A pipe layer is not an excavator operator, and the machine is not the wage. Move only the crew that does the work."
						})
					]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "overflow-hidden rounded-xl border border-line bg-surface",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-baseline justify-between border-b border-line px-4 py-3",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "text-sm font-medium",
							children: "Findings by euro leverage"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
							className: "font-mono text-xs text-muted",
							children: [rows.length, " flagged"]
						})]
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("ul", { children: rows.map((f) => {
						const isOpen = open === f.item.oz;
						return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
							className: "border-b border-line last:border-b-0",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
								type: "button",
								className: "flex w-full items-start gap-3 px-4 py-3 text-left",
								onClick: () => setOpen(isOpen ? null : f.item.oz),
								children: [
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
										className: "mt-0.5 shrink-0 rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent",
										children: KIND[f.item.kind ?? "gap"]
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
										className: "min-w-0 flex-1",
										children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
											className: "block font-medium",
											children: [
												f.item.oz,
												" · ",
												f.item.title
											]
										}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
											className: "block text-sm text-muted overflow-wrap-anywhere",
											children: f.item.rationale
										})]
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
										className: "shrink-0 text-right font-mono text-sm",
										children: f.source === "benchmark" ? euro(f.total) : "kein Vergleichswert"
									})
								]
							}), isOpen && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: "space-y-2 px-4 pb-4 text-sm",
								children: [
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
										className: "text-muted overflow-wrap-anywhere",
										children: f.item.longText
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
										className: "text-muted",
										children: crewLabel(f.item.oz)
									}),
									f.item.preambles && f.item.preambles.length > 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextAccordion, {
										title: "Vorbemerkungen",
										items: f.item.preambles
									}),
									f.item.remarks && f.item.remarks.length > 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(TextAccordion, {
										title: "Bereichs-Remarks",
										items: f.item.remarks
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
										className: "flex flex-wrap items-end gap-3",
										children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
											className: "text-xs text-muted",
											children: ["Qty used", /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
												className: "mt-1 block h-10 w-28 rounded-lg border border-line bg-bg px-2 font-mono text-sm text-ink",
												type: "number",
												min: 0,
												value: fixes[f.item.oz]?.qty ?? f.item.qty,
												onChange: (e) => patch(f.item.oz, Number(e.target.value), fixes[f.item.oz]?.tactic ?? 1)
											})]
										}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
											className: "text-xs text-muted",
											children: ["Tactic", /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("select", {
												className: "mt-1 block h-10 rounded-lg border border-line bg-bg px-2 text-sm text-ink",
												value: fixes[f.item.oz]?.tactic ?? 1,
												onChange: (e) => patch(f.item.oz, fixes[f.item.oz]?.qty ?? f.item.qty, Number(e.target.value)),
												children: [
													/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
														value: .7,
														children: "Low — may not be called"
													}),
													/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
														value: 1,
														children: "As calculated"
													}),
													/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
														value: 1.25,
														children: "High — quantity will grow"
													})
												]
											})]
										})]
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", { children: [
										"Billed ",
										num(f.item.qty, 0),
										" ",
										f.item.unit,
										f.item.benchmark != null ? ` · observed ${euro(f.item.benchmark)}` : " · kein Vergleichswert",
										" · ",
										"now ",
										euro(f.ep),
										"/",
										f.item.unit
									] }),
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
										className: "rounded-lg bg-bg px-3 py-2 text-ink",
										children: letters[f.item.oz] || f.item.rfi
									}),
									f.item.rfi && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
										type: "button",
										className: "h-10 rounded-lg border border-line px-3 text-sm",
										disabled: busy === f.item.oz,
										onClick: () => sharpen(f.item.oz, f.item.title, f.item.longText, f.item.rationale, letters[f.item.oz] || f.item.rfi),
										children: busy === f.item.oz ? "Writing…" : "Sharpen this question"
									}),
									aiNote && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
										className: "text-xs text-warn",
										children: aiNote
									})
								]
							})]
						}, f.item.oz);
					}) })]
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("section", {
				className: "overflow-x-auto rounded-xl border border-line bg-surface",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("table", {
					className: "w-full min-w-[640px] text-left text-sm",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("thead", {
						className: "border-b border-line font-mono text-xs tracking-wide text-muted uppercase",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", { children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-2 font-medium",
								children: "OZ"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-2 font-medium",
								children: "Position"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-2 font-medium",
								children: "Qty"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-2 font-medium",
								children: "EP"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-2 font-medium",
								children: "Source"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-2 text-right font-medium",
								children: "Total"
							})
						] })
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tbody", { children: sortedItems.map((it) => {
						const fix = fixes[it.oz];
						const priced = unitPrice(it, rates, fix?.tactic ?? 1);
						return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", {
							className: "border-b border-line last:border-b-0",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-2 font-mono text-xs",
									children: it.oz
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-2",
									children: it.title
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
									className: "px-4 py-2 font-mono text-xs",
									children: [
										num(fix?.qty ?? it.qty, 0),
										" ",
										it.unit
									]
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-2 font-mono text-xs",
									children: euro(priced.ep)
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
									className: "px-4 py-2 text-muted",
									children: [
										priced.source === "benchmark" ? "observed" : "built-up",
										" · ",
										crewLabel(it.oz)
									]
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-2 text-right font-mono text-xs",
									children: euro(lineTotal(it, rates, fix))
								})
							]
						}, it.oz);
					}) })]
				})
			})
		]
	});
}
function TextAccordion({ title, items }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("details", {
		className: "rounded-lg border border-line bg-bg px-3 py-2",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("summary", {
			className: "cursor-pointer text-sm font-medium",
			children: title
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "mt-2 space-y-2",
			children: items.map((text, index) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "text-xs leading-relaxed text-muted overflow-wrap-anywhere",
				children: text
			}, `${title}-${index}`))
		})]
	});
}
function Kpi({ label, value, hint }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "rounded-xl border border-line bg-surface px-4 py-3",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "font-mono text-xs tracking-widest text-muted uppercase",
				children: label
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "mt-1 text-2xl font-medium tracking-tight",
				children: value
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "mt-1 text-xs text-muted overflow-wrap-anywhere",
				children: hint
			})
		]
	});
}
function Slider({ label, min, max, step, value, onChange }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
		className: "mb-3 block text-sm",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
			className: "mb-1 flex justify-between",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: label }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
				className: "font-mono",
				children: Number(value.toFixed(2))
			})]
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
			className: "w-full accent-accent",
			type: "range",
			min,
			max,
			step,
			value,
			onChange: (e) => onChange(Number(e.target.value))
		})]
	});
}
//#endregion
export { Home as component };

````

## `frontend_demo/.vercel/output/functions/__server.func/_ssr/ssr.mjs`
````mjs
import { n as __exportAll } from "../_runtime.mjs";
import { A as getStylesheetHref, B as isPromise, C as fromJSON, E as toCrossJSONStream, F as executeRewriteInput, G as isNotFound, H as isRedirect, I as invariant, K as require_react, M as resolveManifestCssLink, N as waitForReason, P as _getRenderedMatches, T as toCrossJSONAsync, U as parseRedirect, W as rootRouteId, a as isSsrResponse, c as stripSsrResponseBody, i as disposeSsrResponse, j as resolveManifestAssetLink, k as getScriptPreloadAttrs, n as bindSsrResponseToRequest, o as normalizeSsrResponse, p as RouterProvider, r as defineHandlerCallback, s as replaceSsrResponse, t as renderRouterToStream, y as require_jsx_runtime, z as isDangerousProtocol } from "../_libs/@tanstack/react-router+[...].mjs";
import { n as createServerHistory } from "../_libs/tanstack__history.mjs";
import { a as defaultSerovalDeserializerPlugins, i as createRawStreamRPCPlugin, n as attachRouterServerSsrUtils, o as makeSerovalPlugin, r as getNormalizedURL, s as createSerializationAdapter, t as mergeHeaders } from "../_libs/@tanstack/router-core+[...].mjs";
import { n as toResponse, t as H3Event } from "../_libs/h3-v2+rou3.mjs";
import { AsyncLocalStorage } from "node:async_hooks";
//#region node_modules/.nitro/vite/services/ssr/index.js
var ssr_exports = /* @__PURE__ */ __exportAll({
	createServerEntry: () => createServerEntry,
	default: () => server_default,
	n: () => TSS_SERVER_FUNCTION,
	r: () => getServerFnById,
	t: () => createServerFn
});
require_react();
var import_jsx_runtime = require_jsx_runtime();
function StartServer(props) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(RouterProvider, { router: props.router });
}
var defaultStreamHandler = defineHandlerCallback(({ request, router, responseHeaders }) => renderRouterToStream({
	request,
	router,
	responseHeaders,
	children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StartServer, { router })
}));
var GLOBAL_EVENT_STORAGE_KEY = Symbol.for("tanstack-start:event-storage");
var globalObj$1 = globalThis;
if (!globalObj$1[GLOBAL_EVENT_STORAGE_KEY]) globalObj$1[GLOBAL_EVENT_STORAGE_KEY] = new AsyncLocalStorage();
var eventStorage = globalObj$1[GLOBAL_EVENT_STORAGE_KEY];
function isPromiseLike(value) {
	return (typeof value === "object" || typeof value === "function") && value !== null && typeof value.then === "function";
}
function getSetCookieValues(headers) {
	const headersWithSetCookie = headers;
	if (typeof headersWithSetCookie.getSetCookie === "function") return headersWithSetCookie.getSetCookie();
	const value = headers.get("set-cookie");
	return value ? [value] : [];
}
function mergeEventResponseHeaders(response, event) {
	if (response.ok) return;
	const eventSetCookies = getSetCookieValues(event.res.headers);
	if (eventSetCookies.length === 0) return;
	const responseSetCookies = getSetCookieValues(response.headers);
	response.headers.delete("set-cookie");
	for (const cookie of responseSetCookies) response.headers.append("set-cookie", cookie);
	for (const cookie of eventSetCookies) response.headers.append("set-cookie", cookie);
}
function finalizeResponse(value, event) {
	const response = ensureResponse(value);
	mergeEventResponseHeaders(response, event);
	return response;
}
function finalizeMaybeResponse(value, event) {
	if (isPromiseLike(value)) return Promise.resolve(value).then((resolved) => finalizeResponse(resolved, event), (error) => finalizeResponse(handleResponseError(error), event));
	return finalizeResponse(value, event);
}
function ensureResponse(value) {
	if (value instanceof Response) return value;
	return new Response("Internal Server Error", { status: 500 });
}
function handleResponseError(error) {
	if (error instanceof Response) return error;
	if (error instanceof Error) throw error;
	return new Response("Internal Server Error", { status: 500 });
}
function requestHandler(handler) {
	return (request, requestOpts) => {
		let h3Event;
		try {
			h3Event = new H3Event(request);
		} catch (error) {
			if (error instanceof URIError) return new Response(null, {
				status: 400,
				statusText: "Bad Request"
			});
			throw error;
		}
		let response;
		try {
			response = eventStorage.run({ h3Event }, () => handler(request, requestOpts));
		} catch (error) {
			response = handleResponseError(error);
		}
		return toResponse(finalizeMaybeResponse(response, h3Event), h3Event);
	};
}
function getH3Event() {
	const event = eventStorage.getStore();
	if (!event) throw new Error(`No StartEvent found in AsyncLocalStorage. Make sure you are using the function within the server runtime.`);
	return event.h3Event;
}
function getResponse() {
	return getH3Event().res;
}
var HEADERS = { TSS_SHELL: "X-TSS_SHELL" };
/**
* @description Returns the router manifest data that should be sent to the client.
* This includes only the assets and preloads for the current route and any
* special assets that are needed for the client. It does not include relationships
* between routes or any other data that is not needed for the client.
*
* @param matchedRoutes - In dev mode, the matched routes are used to build
* the dev styles URL for route-scoped CSS collection.
*/
async function getStartManifest(matchedRoutes) {
	const { tsrStartManifest } = await import("../_tanstack-start-manifest_v-C1wz4kaJ.mjs");
	const startManifest = tsrStartManifest();
	let routes = startManifest.routes;
	routes[rootRouteId];
	const manifestRoutes = {};
	for (const k in routes) {
		const v = routes[k];
		const result = {};
		if (v.preloads && v.preloads.length > 0) result.preloads = v.preloads;
		if (v.scripts && v.scripts.length > 0) result.scripts = v.scripts;
		if (v.css?.length) result.css = v.css;
		if (result.preloads || result.scripts || result.css) manifestRoutes[k] = result;
	}
	return {
		...startManifest.scriptFormat ? { scriptFormat: startManifest.scriptFormat } : {},
		...startManifest.inlineCss ? { inlineCss: startManifest.inlineCss } : {},
		routes: manifestRoutes
	};
}
var manifest = { "f9146104ae1489df47f2adbe50d0ec594fa07218b0e2bf146360d54c815e8193": {
	functionName: "sharpenRfi_createServerFn_handler",
	importer: () => import("./draft-rfi-BCcg_iVe.mjs")
} };
async function getServerFnById(id, access) {
	const serverFnInfo = manifest[id];
	if (!serverFnInfo) throw new Error("Server function info not found for " + id);
	const fnModule = serverFnInfo.module ??= await serverFnInfo.importer();
	if (!fnModule) throw new Error("Server function module not resolved for " + id);
	const action = fnModule[serverFnInfo.functionName];
	if (!action) throw new Error("Server function module export not resolved for serverFn ID: " + id);
	return action;
}
var TSS_FORMDATA_CONTEXT = "__TSS_CONTEXT";
var TSS_SERVER_FUNCTION = Symbol.for("TSS_SERVER_FUNCTION");
var TSS_SERVER_FUNCTION_FACTORY = Symbol.for("TSS_SERVER_FUNCTION_FACTORY");
var X_TSS_SERIALIZED = "x-tss-serialized";
var X_TSS_RAW_RESPONSE = "x-tss-raw";
/** Content-Type for multiplexed framed responses (RawStream support) */
var TSS_CONTENT_TYPE_FRAMED = "application/x-tss-framed";
/** Largest payload accepted by one framed-protocol record. */
var MAX_FRAME_PAYLOAD_SIZE = 16777216;
/** Largest number of raw streams accepted in one framed response. */
var MAX_FRAMED_STREAMS = 1024;
/** Full Content-Type header value with version parameter */
var TSS_CONTENT_TYPE_FRAMED_VERSIONED = `${TSS_CONTENT_TYPE_FRAMED}; v=1`;
var GLOBAL_STORAGE_KEY = Symbol.for("tanstack-start:start-storage-context");
var globalObj = globalThis;
if (!globalObj[GLOBAL_STORAGE_KEY]) globalObj[GLOBAL_STORAGE_KEY] = new AsyncLocalStorage();
var startStorage = globalObj[GLOBAL_STORAGE_KEY];
async function runWithStartContext(context, fn) {
	return startStorage.run(context, fn);
}
function getStartContext(opts) {
	const context = startStorage.getStore();
	if (!context && opts?.throwIfNotFound !== false) throw new Error(`No Start context found in AsyncLocalStorage. Make sure you are using the function within the server runtime.`);
	return context;
}
var getStartOptions = () => getStartContext().startOptions;
/** Start's serialization adapters followed by `routerPlugins`. */
function getSerovalPlugins(routerPlugins) {
	return [...(getStartOptions()?.serializationAdapters)?.map(makeSerovalPlugin) ?? [], ...routerPlugins];
}
/**
* Binary frame protocol for multiplexing JSON and raw streams over HTTP.
*
* Frame format: [type:1][streamId:4][length:4][payload:length]
* - type: 1 byte - frame type (JSON, CHUNK, END, ERROR)
* - streamId: 4 bytes big-endian uint32 - stream identifier
* - length: 4 bytes big-endian uint32 - payload length
* - payload: variable length bytes
*/
/** Cached TextEncoder for frame encoding */
var textEncoder$1 = new TextEncoder();
/** Shared empty payload for END frames - avoids allocation per call */
var EMPTY_PAYLOAD = /* @__PURE__ */ new Uint8Array(0);
var MAX_ERROR_MESSAGE_CODE_UNITS = 4096;
/**
* Encodes a single frame with header and payload.
*/
function encodeFrame(type, streamId, payload) {
	if (payload.byteLength > 16777216) throw new RangeError(`Frame payload exceeds ${MAX_FRAME_PAYLOAD_SIZE} bytes`);
	const frame = new Uint8Array(9 + payload.length);
	frame[0] = type;
	frame[1] = streamId >>> 24 & 255;
	frame[2] = streamId >>> 16 & 255;
	frame[3] = streamId >>> 8 & 255;
	frame[4] = streamId & 255;
	frame[5] = payload.length >>> 24 & 255;
	frame[6] = payload.length >>> 16 & 255;
	frame[7] = payload.length >>> 8 & 255;
	frame[8] = payload.length & 255;
	frame.set(payload, 9);
	return frame;
}
/** Encodes an error message payload, truncated to a bounded length. */
function encodeErrorPayload(error) {
	const originalMessage = error instanceof Error ? error.message : String(error ?? "Unknown error");
	const message = originalMessage.length > MAX_ERROR_MESSAGE_CODE_UNITS ? `${originalMessage.slice(0, MAX_ERROR_MESSAGE_CODE_UNITS)}…` : originalMessage;
	return textEncoder$1.encode(message);
}
/**
* Creates a multiplexed ReadableStream from serialized response records.
*
* A record's JSON frame is admitted before any raw stream referenced by that
* record starts. Raw streams from admitted records are pumped concurrently.
* The caller bounds the stream count before records reach this function.
*/
function createMultiplexedStream(recordStream, options = {}) {
	let controller;
	let stopped = false;
	let activePumps = 0;
	let wakeDemand;
	let admission;
	const readers = /* @__PURE__ */ new Set();
	const pendingRawStreams = /* @__PURE__ */ new Set();
	const abortOutput = () => errorOutput(options.signal?.reason);
	const wakeAdmission = () => {
		const wake = wakeDemand;
		wakeDemand = void 0;
		wake?.();
	};
	const cancelReader = (reader, reason) => {
		reader.cancel(reason).catch(() => {});
	};
	const cancelStream = (stream, reason) => {
		stream.cancel(reason).catch(() => {});
	};
	const stop = (reason) => {
		if (stopped) return false;
		stopped = [reason];
		options.signal?.removeEventListener("abort", abortOutput);
		wakeAdmission();
		for (const reader of readers) cancelReader(reader, reason);
		for (const stream of pendingRawStreams) cancelStream(stream, reason);
		pendingRawStreams.clear();
		return true;
	};
	const errorOutput = (error) => {
		if (!stop(error)) return;
		try {
			controller.error(error);
		} catch {}
	};
	const waitForDemand = async () => {
		while (!stopped && (controller.desiredSize ?? 0) <= 0) await new Promise((resolve) => {
			wakeDemand = resolve;
		});
		return !stopped;
	};
	const admitFrame = (type, streamId, payload) => {
		if (stopped) return false;
		if (!admission && (controller.desiredSize ?? 0) > 0) {
			controller.enqueue(encodeFrame(type, streamId, payload));
			return true;
		}
		const runAdmission = async () => {
			if (!await waitForDemand()) return false;
			controller.enqueue(encodeFrame(type, streamId, payload));
			return true;
		};
		const result = admission ? admission.then(runAdmission) : runAdmission();
		const clearAdmission = () => {
			if (admission === tail) admission = void 0;
		};
		const tail = result.then(clearAdmission, clearAdmission);
		admission = tail;
		return result;
	};
	const maybeClose = () => {
		if (activePumps !== 0 || !stop()) return;
		try {
			controller.close();
		} catch {}
	};
	const startPump = (pump) => {
		activePumps++;
		pump().then(() => {
			activePumps--;
			maybeClose();
		}, (error) => {
			activePumps--;
			errorOutput(error);
		});
	};
	async function pumpRawStream(streamId, stream) {
		const reader = stream.getReader();
		readers.add(reader);
		try {
			while (!stopped) {
				const { done, value } = await reader.read();
				if (stopped) return;
				if (done) {
					const frameAdmission = admitFrame(2, streamId, EMPTY_PAYLOAD);
					if (frameAdmission !== true) await frameAdmission;
					return;
				}
				if (!(value instanceof Uint8Array)) throw new TypeError("RawStream chunks must be Uint8Array");
				let offset = 0;
				do {
					const frameAdmission = admitFrame(1, streamId, value.byteLength <= 16777216 ? value : value.subarray(offset, offset + MAX_FRAME_PAYLOAD_SIZE));
					if (frameAdmission !== true && (frameAdmission === false || !await frameAdmission)) return;
					offset += MAX_FRAME_PAYLOAD_SIZE;
				} while (offset < value.byteLength);
			}
		} catch (error) {
			if (!stopped) {
				const frameAdmission = admitFrame(3, streamId, encodeErrorPayload(error));
				if (frameAdmission !== true) await frameAdmission;
			}
		} finally {
			readers.delete(reader);
			reader.releaseLock();
		}
	}
	async function pumpRecords() {
		const reader = recordStream.getReader();
		readers.add(reader);
		try {
			while (!stopped) {
				const { done, value } = await reader.read();
				if (stopped) {
					if (!done) for (const registration of value.rawStreams) cancelStream(registration.stream, stopped[0]);
					return;
				}
				if (done) return;
				for (const registration of value.rawStreams) pendingRawStreams.add(registration.stream);
				const frameAdmission = admitFrame(0, 0, value.json);
				if (frameAdmission !== true && (frameAdmission === false || !await frameAdmission)) return;
				for (const registration of value.rawStreams) {
					pendingRawStreams.delete(registration.stream);
					startPump(pumpRawStream.bind(void 0, registration.id, registration.stream));
				}
			}
		} catch (error) {
			if (!stopped) errorOutput(error);
		} finally {
			readers.delete(reader);
			reader.releaseLock();
		}
	}
	return new ReadableStream({
		start(ctrl) {
			controller = ctrl;
			if (options.signal?.aborted) {
				cancelStream(recordStream, options.signal.reason);
				errorOutput(options.signal.reason);
				return;
			}
			options.signal?.addEventListener("abort", abortOutput, { once: true });
			startPump(pumpRecords);
		},
		pull() {
			wakeAdmission();
		},
		cancel(reason) {
			if (stop(reason)) options.onCancel?.(reason);
		}
	});
}
function isSafeKey(key) {
	return key !== "__proto__" && key !== "constructor" && key !== "prototype";
}
/**
* Merge target and source into a new null-proto object, filtering dangerous keys.
*/
function safeObjectMerge(target, source) {
	const result = Object.create(null);
	if (target) {
		for (const key of Object.keys(target)) if (isSafeKey(key)) result[key] = target[key];
	}
	if (source && typeof source === "object") {
		for (const key of Object.keys(source)) if (isSafeKey(key)) result[key] = source[key];
	}
	return result;
}
/**
* Create a null-prototype object, optionally copying from source.
*/
function createNullProtoObject(source) {
	if (!source) return Object.create(null);
	const obj = Object.create(null);
	for (const key of Object.keys(source)) if (isSafeKey(key)) obj[key] = source[key];
	return obj;
}
var getStartContextServerOnly = getStartContext;
var createServerFn = (options, __opts) => {
	const resolvedOptions = __opts || options || {};
	if (typeof resolvedOptions.method === "undefined") resolvedOptions.method = "GET";
	const setValidator = (validator) => {
		return createServerFn(void 0, {
			...resolvedOptions,
			validator,
			inputValidator: validator
		});
	};
	const res = {
		options: resolvedOptions,
		middleware: (middleware) => {
			const newMiddleware = [...resolvedOptions.middleware || []];
			middleware.forEach((item) => {
				if (TSS_SERVER_FUNCTION_FACTORY in item) {
					if (item.options.middleware) newMiddleware.push(...item.options.middleware);
				} else newMiddleware.push(item);
			});
			const res = createServerFn(void 0, {
				...resolvedOptions,
				middleware: newMiddleware
			});
			res[TSS_SERVER_FUNCTION_FACTORY] = true;
			return res;
		},
		validator: setValidator,
		inputValidator: setValidator,
		handler: (...args) => {
			const [extractedFn, serverFn] = args;
			const newOptions = {
				...resolvedOptions,
				extractedFn,
				serverFn
			};
			const resolvedMiddleware = [...newOptions.middleware || [], serverFnBaseToMiddleware(newOptions)];
			extractedFn.method = resolvedOptions.method;
			return Object.assign(async (opts) => {
				const result = await executeMiddleware$1(resolvedMiddleware, "client", {
					...extractedFn,
					...newOptions,
					data: opts?.data,
					headers: opts?.headers,
					signal: opts?.signal,
					fetch: opts?.fetch,
					context: createNullProtoObject()
				});
				const redirect = parseRedirect(result.error);
				if (redirect) throw redirect;
				if (result.error) throw result.error;
				return result.result;
			}, {
				...extractedFn,
				method: resolvedOptions.method,
				__executeServer: async (opts) => {
					const startContext = getStartContextServerOnly();
					const serverContextAfterGlobalMiddlewares = startContext.contextAfterGlobalMiddlewares;
					return await executeMiddleware$1(resolvedMiddleware, "server", {
						...extractedFn,
						data: opts.data,
						method: opts.method ?? resolvedOptions.method,
						serverFnMeta: extractedFn.serverFnMeta,
						context: safeObjectMerge(opts.context, serverContextAfterGlobalMiddlewares),
						request: startContext.request
					}).then((d) => ({
						result: d.result,
						error: d.error,
						context: d.sendContext
					}));
				}
			});
		}
	};
	const fun = (options) => {
		return createServerFn(void 0, {
			...resolvedOptions,
			...options
		});
	};
	return Object.assign(fun, res);
};
async function executeMiddleware$1(middlewares, env, opts) {
	let flattenedMiddlewares = flattenMiddlewares([...getStartOptions()?.functionMiddleware || [], ...middlewares]);
	if (env === "server") {
		const startContext = getStartContextServerOnly({ throwIfNotFound: false });
		if (startContext?.executedRequestMiddlewares) flattenedMiddlewares = flattenedMiddlewares.filter((m) => !startContext.executedRequestMiddlewares.has(m));
	}
	const callNextMiddleware = async (ctx) => {
		const nextMiddleware = flattenedMiddlewares.shift();
		if (!nextMiddleware) return ctx;
		try {
			let validator = "validator" in nextMiddleware.options ? nextMiddleware.options.validator : void 0;
			if (!validator && "inputValidator" in nextMiddleware.options) validator = nextMiddleware.options.inputValidator;
			if (validator && env === "server") ctx.data = await execValidator(validator, ctx.data);
			let middlewareFn = void 0;
			if (env === "client") {
				if ("client" in nextMiddleware.options) middlewareFn = nextMiddleware.options.client;
			} else if ("server" in nextMiddleware.options) middlewareFn = nextMiddleware.options.server;
			if (middlewareFn) {
				const userNext = async (userCtx = {}) => {
					const result = await callNextMiddleware({
						...ctx,
						...userCtx,
						context: safeObjectMerge(ctx.context, userCtx.context),
						sendContext: safeObjectMerge(ctx.sendContext, userCtx.sendContext),
						headers: mergeHeaders(ctx.headers, userCtx.headers),
						_callSiteFetch: ctx._callSiteFetch,
						fetch: ctx._callSiteFetch ?? userCtx.fetch ?? ctx.fetch,
						result: userCtx.result !== void 0 ? userCtx.result : userCtx instanceof Response ? userCtx : ctx.result,
						error: userCtx.error ?? ctx.error
					});
					if (result.error) throw result.error;
					return result;
				};
				const result = await middlewareFn({
					...ctx,
					next: userNext
				});
				if (isRedirect(result)) return {
					...ctx,
					error: result
				};
				if (result instanceof Response) return {
					...ctx,
					result
				};
				if (!result) throw new Error("User middleware returned undefined. You must call next() or return a result in your middlewares.");
				return result;
			}
			return callNextMiddleware(ctx);
		} catch (error) {
			return {
				...ctx,
				error
			};
		}
	};
	return callNextMiddleware({
		...opts,
		headers: opts.headers || {},
		sendContext: opts.sendContext || {},
		context: opts.context || createNullProtoObject(),
		_callSiteFetch: opts.fetch
	});
}
function flattenMiddlewares(middlewares, maxDepth = 100) {
	const seen = /* @__PURE__ */ new Set();
	const flattened = [];
	const recurse = (middleware, depth) => {
		if (depth > maxDepth) throw new Error(`Middleware nesting depth exceeded maximum of ${maxDepth}. Check for circular references.`);
		middleware.forEach((m) => {
			if (m.options.middleware) recurse(m.options.middleware, depth + 1);
			if (!seen.has(m)) {
				seen.add(m);
				flattened.push(m);
			}
		});
	};
	recurse(middlewares, 0);
	return flattened;
}
async function execValidator(validator, input) {
	if (validator == null) return {};
	if ("~standard" in validator) {
		const result = await validator["~standard"].validate(input);
		if (result.issues) throw new Error(JSON.stringify(result.issues, void 0, 2));
		return result.value;
	}
	if ("parse" in validator) return validator.parse(input);
	if (typeof validator === "function") return validator(input);
	throw new Error("Invalid validator type!");
}
function serverFnBaseToMiddleware(options) {
	return {
		"~types": void 0,
		options: {
			inputValidator: options.validator ?? options.inputValidator,
			client: async ({ next, sendContext, fetch, ...ctx }) => {
				const payload = {
					...ctx,
					context: sendContext,
					fetch
				};
				return next(await options.extractedFn?.(payload));
			},
			server: async ({ next, ...ctx }) => {
				const result = await options.serverFn?.(ctx);
				return next({
					...ctx,
					result
				});
			}
		}
	};
}
var createMiddleware = (options, __opts) => {
	const resolvedOptions = {
		type: "request",
		...__opts || options
	};
	const setValidator = (validator) => {
		return createMiddleware({}, Object.assign(resolvedOptions, {
			validator,
			inputValidator: validator
		}));
	};
	return {
		options: resolvedOptions,
		middleware: (middleware) => {
			return createMiddleware({}, Object.assign(resolvedOptions, { middleware }));
		},
		validator: setValidator,
		inputValidator: setValidator,
		client: (client) => {
			return createMiddleware({}, Object.assign(resolvedOptions, { client }));
		},
		server: (server) => {
			return createMiddleware({}, Object.assign(resolvedOptions, { server }));
		}
	};
};
var innerCreateCsrfMiddleware = (opts = {}) => {
	return createMiddleware().server(async (ctx) => {
		const csrfCtx = ctx;
		if (opts.filter && !await opts.filter(csrfCtx)) return ctx.next();
		if (await isCsrfRequestAllowed(opts, csrfCtx)) return ctx.next();
		return getFailureResponse(opts, csrfCtx);
	});
};
var createCsrfMiddleware = innerCreateCsrfMiddleware;
async function isCsrfRequestAllowed(opts, ctx) {
	const result = await getCsrfRequestValidationResult(opts, ctx);
	return result === true || result === void 0 && opts.allowRequestsWithoutOriginCheck === true;
}
async function getCsrfRequestValidationResult(opts, ctx) {
	const fetchSite = ctx.request.headers.get("Sec-Fetch-Site");
	if (fetchSite !== null) return matchValue(opts.secFetchSite ?? "same-origin", fetchSite, ctx);
	const origin = ctx.request.headers.get("Origin");
	if (origin !== null) {
		if (opts.origin) return matchValue(opts.origin, origin, ctx);
		return origin === new URL(ctx.request.url).origin;
	}
	const referer = ctx.request.headers.get("Referer");
	if (referer === null || opts.referer === false) return;
	if (typeof opts.referer === "function") return opts.referer(referer, ctx);
	if (opts.origin) {
		const refererOrigin = getOriginFromUrl(referer);
		return refererOrigin !== void 0 && matchValue(opts.origin, refererOrigin, ctx);
	}
	return isRefererSameOrigin(referer, new URL(ctx.request.url).origin);
}
async function matchValue(matcher, value, ctx) {
	if (typeof matcher === "function") return matcher(value, ctx);
	if (Array.isArray(matcher)) return matcher.includes(value);
	return value === matcher;
}
function getOriginFromUrl(url) {
	try {
		return new URL(url).origin;
	} catch {
		return;
	}
}
function isRefererSameOrigin(referer, requestOrigin) {
	if (referer === requestOrigin) return true;
	if (!referer.startsWith(requestOrigin)) return false;
	if (referer.length === requestOrigin.length) return true;
	const code = referer.charCodeAt(requestOrigin.length);
	return code === 47 || code === 63 || code === 35;
}
async function getFailureResponse(opts, ctx) {
	if (typeof opts.failureResponse === "function") return opts.failureResponse(ctx);
	return opts.failureResponse?.clone() ?? new Response("Forbidden", { status: 403 });
}
var serovalPlugins = void 0;
var FORM_DATA_CONTENT_TYPES = ["multipart/form-data", "application/x-www-form-urlencoded"];
var MAX_PAYLOAD_SIZE = 1e6;
var MAX_PENDING_SERIALIZATION_RECORDS = 1024;
var MAX_PENDING_SERIALIZATION_BYTES = 33554432;
var textEncoder = new TextEncoder();
function encodeSerializationRecord(value) {
	return textEncoder.encode(JSON.stringify(value));
}
function exceedsPendingSerializationLimit(record, recordCount, pendingBytes) {
	return recordCount >= MAX_PENDING_SERIALIZATION_RECORDS || pendingBytes + record.byteLength > MAX_PENDING_SERIALIZATION_BYTES;
}
function runSerializationCleanup(dispose) {
	try {
		dispose();
	} catch {}
}
function cancelRawStream(stream, reason) {
	stream.cancel(reason).catch(() => {});
}
var handleServerAction = async ({ request, context, serverFnId }) => {
	const methodUpper = request.method.toUpperCase();
	const url = new URL(request.url);
	const action = await getServerFnById(serverFnId, { origin: "client" });
	if (action.method && methodUpper !== action.method) return new Response(`expected ${action.method} method. Got ${methodUpper}`, {
		status: 405,
		headers: { Allow: action.method }
	});
	const isServerFn = request.headers.get("x-tsr-serverFn") === "true";
	serovalPlugins ??= getSerovalPlugins(defaultSerovalDeserializerPlugins);
	const contentType = request.headers.get("Content-Type");
	try {
		let res;
		if (FORM_DATA_CONTENT_TYPES.some((type) => contentType && contentType.includes(type))) {
			if (methodUpper === "GET") invariant();
			const formData = await request.formData();
			const serializedContext = formData.get(TSS_FORMDATA_CONTEXT);
			formData.delete(TSS_FORMDATA_CONTEXT);
			const params = {
				context,
				data: formData,
				method: methodUpper
			};
			if (typeof serializedContext === "string") try {
				const deserializedContext = fromJSON(JSON.parse(serializedContext), { plugins: serovalPlugins });
				if (typeof deserializedContext === "object" && deserializedContext) params.context = safeObjectMerge(deserializedContext, context);
			} catch (e) {}
			res = await action(params);
		} else if (methodUpper === "GET") {
			const payloadParam = url.searchParams.get("payload");
			if (payloadParam && payloadParam.length > MAX_PAYLOAD_SIZE) throw new Error("Payload too large");
			const payload = payloadParam ? fromJSON(JSON.parse(payloadParam), { plugins: serovalPlugins }) : void 0;
			res = await action({
				data: payload?.data,
				context: safeObjectMerge(payload?.context, context),
				method: methodUpper
			});
		} else {
			const payload = contentType?.includes("application/json") ? fromJSON(await request.json(), { plugins: serovalPlugins }) : void 0;
			res = await action({
				data: payload?.data,
				context: safeObjectMerge(payload?.context, context),
				method: methodUpper
			});
		}
		const unwrapped = res.error !== void 0 ? res.error : res.result;
		if (isNotFound(res)) res = isNotFoundResponse(res);
		if (!isServerFn && (unwrapped instanceof Response || unwrapped === null || typeof unwrapped !== "object")) return unwrapped;
		if (unwrapped instanceof Response) {
			if (isRedirect(unwrapped)) return unwrapped;
			unwrapped.headers.set(X_TSS_RAW_RESPONSE, "true");
			return unwrapped;
		}
		return serializeResult(res, request.signal, serovalPlugins);
	} catch (error) {
		if (error instanceof Response) return error;
		if (isNotFound(error)) return isNotFoundResponse(error);
		console.error("Server Fn Error!", error);
		const serializedError = JSON.stringify(await toCrossJSONAsync(error, {
			refs: /* @__PURE__ */ new Map(),
			plugins: serovalPlugins
		}));
		const response = getResponse();
		const headers = {
			"Content-Type": "application/json",
			[X_TSS_SERIALIZED]: "true"
		};
		try {
			return new Response(serializedError, {
				status: response.status ?? 500,
				statusText: response.statusText,
				headers
			});
		} catch {
			return new Response(serializedError, {
				status: 500,
				statusText: "",
				headers
			});
		}
	}
};
/**
* Serializes a server-function result. A result that Seroval completes
* synchronously without RawStreams becomes plain JSON; everything else is a
* framed response whose records and raw streams are multiplexed in order.
*/
function serializeResult(res, signal, plugins) {
	const alsResponse = getResponse();
	const initialRecords = [];
	let initialBytes = 0;
	const pendingRawStreams = [];
	let done = false;
	let initialParsed = false;
	let serializationFailure;
	let disposeSerialization;
	let onParse = (value, initial) => {
		if (serializationFailure) return;
		initialParsed ||= initial;
		const record = encodeSerializationRecord(value);
		if (exceedsPendingSerializationLimit(record, initialRecords.length, initialBytes)) {
			serializationFailure = [/* @__PURE__ */ new Error("Server function serialization exceeded its pending output limit")];
			return;
		}
		initialRecords.push(record);
		initialBytes += record.byteLength;
	};
	let onDone = () => {
		if (initialParsed) done = true;
	};
	let onError = (error) => {
		serializationFailure ??= [error];
	};
	const rawStreamPlugin = createRawStreamRPCPlugin((id, stream) => {
		if (serializationFailure) {
			cancelRawStream(stream, serializationFailure[0]);
			return;
		}
		if (id > 1024) {
			const error = /* @__PURE__ */ new Error(`Too many raw streams in framed response (max ${MAX_FRAMED_STREAMS})`);
			cancelRawStream(stream, error);
			onError(error);
			return;
		}
		pendingRawStreams.push({
			id,
			stream
		});
	});
	const dispose = toCrossJSONStream(res, {
		refs: /* @__PURE__ */ new Map(),
		plugins: [rawStreamPlugin, ...plugins],
		onParse(value, initial) {
			onParse(value, initial);
		},
		onDone() {
			onDone();
		},
		onError: (error) => {
			onError(error);
		}
	});
	if (serializationFailure) {
		runSerializationCleanup(dispose);
		for (const registration of pendingRawStreams) cancelRawStream(registration.stream, serializationFailure[0]);
		throw serializationFailure[0];
	}
	if (!done) disposeSerialization = dispose;
	if (done && pendingRawStreams.length === 0 && initialRecords.length === 1) return new Response(initialRecords[0], {
		status: alsResponse.status,
		statusText: alsResponse.statusText,
		headers: {
			"Content-Type": "application/json",
			[X_TSS_SERIALIZED]: "true"
		}
	});
	if (done && initialRecords.length === 1) {
		const json = initialRecords[0];
		if (json.byteLength > 16777216) {
			const error = /* @__PURE__ */ new Error("Server function serialization exceeded its pending output limit");
			for (const registration of pendingRawStreams) cancelRawStream(registration.stream, error);
			throw error;
		}
		const rawStreams = pendingRawStreams.splice(0);
		initialRecords.length = 0;
		return createFramedResponse(new ReadableStream({
			start(controller) {
				controller.enqueue({
					json,
					rawStreams
				});
				controller.close();
			},
			cancel(reason) {
				for (const registration of rawStreams) cancelRawStream(registration.stream, reason);
			}
		}), { signal });
	}
	const { readable, writable } = new TransformStream();
	const writer = writable.getWriter();
	const recordAbortController = new AbortController();
	let pendingBytes = 0;
	const pendingRecords = /* @__PURE__ */ new Set();
	const abortRecordStream = (error) => {
		if (serializationFailure) return;
		serializationFailure = [error];
		const disposeCurrentSerialization = disposeSerialization;
		disposeSerialization = void 0;
		for (const registration of pendingRawStreams.splice(0)) cancelRawStream(registration.stream, error);
		for (const record of pendingRecords) for (const registration of record.rawStreams) cancelRawStream(registration.stream, error);
		pendingRecords.clear();
		recordAbortController.abort(error);
		writer.abort(error).catch(() => {});
		if (disposeCurrentSerialization) runSerializationCleanup(disposeCurrentSerialization);
	};
	const writeRecord = (json, rawStreams) => {
		if (serializationFailure) {
			for (const registration of rawStreams) cancelRawStream(registration.stream, serializationFailure[0]);
			return false;
		}
		if (json.byteLength > 16777216 || exceedsPendingSerializationLimit(json, pendingRecords.size, pendingBytes)) {
			const error = /* @__PURE__ */ new Error("Server function serialization exceeded its pending output limit");
			for (const registration of rawStreams) cancelRawStream(registration.stream, error);
			onError(error);
			return false;
		}
		pendingBytes += json.byteLength;
		const record = {
			json,
			rawStreams
		};
		pendingRecords.add(record);
		writer.write(record).then(() => {
			pendingRecords.delete(record);
			pendingBytes -= json.byteLength;
		}, (error) => {
			const stillOwned = pendingRecords.delete(record);
			pendingBytes -= json.byteLength;
			if (stillOwned) for (const registration of rawStreams) cancelRawStream(registration.stream, error);
		});
		return true;
	};
	onParse = (value) => {
		if (serializationFailure) return;
		writeRecord(encodeSerializationRecord(value), pendingRawStreams.splice(0));
	};
	onDone = () => {
		if (serializationFailure) return;
		disposeSerialization = void 0;
		writer.close().catch(() => {});
	};
	onError = (error) => {
		abortRecordStream(error);
	};
	const initialRawStreams = pendingRawStreams.splice(0);
	for (let index = 0; index < initialRecords.length; index++) {
		const isLast = index === initialRecords.length - 1;
		if (!writeRecord(initialRecords[index], isLast ? initialRawStreams : [])) {
			if (!isLast) for (const registration of initialRawStreams) cancelRawStream(registration.stream, serializationFailure[0]);
			initialRecords.length = 0;
			throw serializationFailure[0];
		}
	}
	initialRecords.length = 0;
	if (done) onDone();
	writer.closed.catch((error) => {
		abortRecordStream(error);
	});
	return createFramedResponse(readable, {
		signal: AbortSignal.any([recordAbortController.signal, signal]),
		onCancel: abortRecordStream
	});
	function createFramedResponse(records, options) {
		const multiplexedStream = createMultiplexedStream(records, options);
		try {
			return new Response(multiplexedStream, {
				status: alsResponse.status,
				statusText: alsResponse.statusText,
				headers: {
					"Content-Type": TSS_CONTENT_TYPE_FRAMED_VERSIONED,
					[X_TSS_SERIALIZED]: "true"
				}
			});
		} catch (error) {
			cancelRawStream(multiplexedStream, error);
			throw error;
		}
	}
}
function isNotFoundResponse(error) {
	const { headers, ...rest } = error;
	const response = new Response(JSON.stringify(rest), {
		status: 404,
		headers
	});
	response.headers.set("Content-Type", "application/json");
	return response;
}
var LINK_PARAM_TOKEN_RE = /^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/;
var PRELOAD_AS_VALUES = /* @__PURE__ */ new Set([
	"fetch",
	"font",
	"image",
	"script",
	"style",
	"track"
]);
function buildLinkParam(name, value) {
	if (value === void 0) return name;
	if (LINK_PARAM_TOKEN_RE.test(value)) return `${name}=${value}`;
	return `${name}=${JSON.stringify(value)}`;
}
function serializeEarlyHint(hint) {
	const parts = [`<${hint.href}>`, buildLinkParam("rel", hint.rel)];
	if (hint.as) parts.push(buildLinkParam("as", hint.as));
	if (hint.crossOrigin !== void 0) parts.push(buildLinkParam("crossorigin", hint.crossOrigin || void 0));
	if (hint.type) parts.push(buildLinkParam("type", hint.type));
	if (hint.integrity) parts.push(buildLinkParam("integrity", hint.integrity));
	if (hint.referrerPolicy) parts.push(buildLinkParam("referrerpolicy", hint.referrerPolicy));
	if (hint.fetchPriority) parts.push(buildLinkParam("fetchpriority", hint.fetchPriority));
	return parts.join("; ");
}
function getStringAttr(attrs, name, fallbackName) {
	const value = attrs?.[name] ?? (fallbackName ? attrs?.[fallbackName] : void 0);
	return typeof value === "string" ? value : void 0;
}
function getPreloadAs(attrs) {
	const as = getStringAttr(attrs, "as");
	return as && PRELOAD_AS_VALUES.has(as) ? as : void 0;
}
function addEarlyHintFetchAttrs(hint, attrs) {
	const crossOrigin = getStringAttr(attrs, "crossOrigin", "crossorigin");
	const type = getStringAttr(attrs, "type");
	const integrity = getStringAttr(attrs, "integrity");
	const referrerPolicy = getStringAttr(attrs, "referrerPolicy", "referrerpolicy");
	const fetchPriority = getStringAttr(attrs, "fetchPriority", "fetchpriority");
	if (crossOrigin !== void 0) hint.crossOrigin = crossOrigin;
	if (type) hint.type = type;
	if (integrity) hint.integrity = integrity;
	if (referrerPolicy) hint.referrerPolicy = referrerPolicy;
	if (fetchPriority) hint.fetchPriority = fetchPriority;
}
function linkAttrsToEarlyHint(attrs) {
	const href = getStringAttr(attrs, "href");
	const rel = getStringAttr(attrs, "rel");
	if (!href || !rel) return void 0;
	const relTokens = rel.split(/\s+/);
	let hintRel;
	let hintAs;
	if (relTokens.includes("modulepreload")) {
		hintRel = "modulepreload";
		hintAs = "script";
	} else if (relTokens.includes("stylesheet")) {
		hintRel = "preload";
		hintAs = "style";
	} else if (relTokens.includes("preload")) {
		hintAs = getPreloadAs(attrs);
		if (!hintAs) return void 0;
		hintRel = "preload";
	} else if (relTokens.includes("preconnect")) {
		hintRel = "preconnect";
		hintAs = void 0;
	} else if (relTokens.includes("dns-prefetch")) {
		hintRel = "dns-prefetch";
		hintAs = void 0;
	}
	if (!hintRel) return void 0;
	const hint = {
		href,
		rel: hintRel
	};
	if (hintAs) hint.as = hintAs;
	addEarlyHintFetchAttrs(hint, attrs);
	return hint;
}
function collectStaticHintsFromManifest(manifest, matchedRoutes) {
	const hints = [];
	for (const route of matchedRoutes) {
		const routeManifest = manifest.routes[route.id];
		if (!routeManifest) continue;
		for (const link of routeManifest.preloads ?? []) {
			const attrs = getScriptPreloadAttrs(manifest, link);
			const hint = {
				href: attrs.href,
				rel: attrs.rel,
				as: "script"
			};
			if (attrs.crossOrigin !== void 0) hint.crossOrigin = attrs.crossOrigin;
			hints.push(hint);
		}
		for (const link of routeManifest.css ?? []) {
			const stylesheetHref = getStylesheetHref(link);
			if (manifest.inlineCss?.styles[stylesheetHref] !== void 0) continue;
			const resolvedLink = resolveManifestCssLink(link);
			const hint = {
				href: stylesheetHref,
				rel: "preload",
				as: "style"
			};
			if (resolvedLink.crossOrigin !== void 0) hint.crossOrigin = resolvedLink.crossOrigin;
			hints.push(hint);
		}
	}
	return hints;
}
function collectDynamicHintsFromMatches(matches) {
	const hints = [];
	for (const match of matches) {
		const links = match.links;
		if (!Array.isArray(links)) continue;
		for (const link of links) {
			const hint = linkAttrsToEarlyHint(link);
			if (hint) hints.push(hint);
		}
	}
	return hints;
}
function createEarlyHintsEvent(opts) {
	const nextHints = [];
	const nextLinks = [];
	for (const hint of opts.hints) {
		const link = serializeEarlyHint(hint);
		if (opts.sentLinks.has(link)) continue;
		opts.sentLinks.add(link);
		opts.sentHints.push(hint);
		nextHints.push(hint);
		nextLinks.push(link);
	}
	if (!nextHints.length && opts.phase !== "dynamic") return void 0;
	return {
		phase: opts.phase,
		hints: nextHints,
		links: nextLinks,
		allHints: opts.sentHints.slice(),
		allLinks: Array.from(opts.sentLinks)
	};
}
function createResponseLinkHeaderEntries(opts) {
	for (const hint of opts.hints) {
		const link = serializeEarlyHint(hint);
		if (opts.sentLinks.has(link)) continue;
		opts.sentLinks.add(link);
		opts.entries.push({
			phase: opts.phase,
			hint,
			link
		});
	}
}
function getResponseLinkHeaderEntries(opts) {
	if (!opts.filter) return opts.entries.map((entry) => entry.link);
	try {
		const links = [];
		for (const entry of opts.entries) if (opts.filter(entry)) links.push(entry.link);
		return links;
	} catch (err) {
		console.error("Error filtering response Link headers:", err);
		return [];
	}
}
function notifyEarlyHints(phase, event, onEarlyHints) {
	try {
		const result = onEarlyHints(event);
		if (result) Promise.resolve(result).catch((err) => {
			console.error(`Error sending ${phase} early hints:`, err);
		});
	} catch (err) {
		console.error(`Error sending ${phase} early hints:`, err);
	}
}
function getResponseLinkHeaderFilter(responseLinkHeader) {
	if (typeof responseLinkHeader !== "object") return;
	return responseLinkHeader.filter;
}
function appendResponseLinkHeaders(opts) {
	for (const link of getResponseLinkHeaderEntries(opts)) opts.responseHeaders.append("Link", link);
}
function collectResponseLinkHeaderEntries(opts) {
	for (let index = 0; index < opts.event.hints.length; index++) opts.entries.push({
		phase: opts.phase,
		hint: opts.event.hints[index],
		link: opts.event.links[index]
	});
}
function collectEarlyHintsPhase(opts) {
	const event = opts.onEarlyHints ? createEarlyHintsEvent({
		phase: opts.phase,
		hints: opts.hints,
		sentLinks: opts.sentLinks,
		sentHints: opts.sentHints
	}) : void 0;
	if (event) notifyEarlyHints(opts.phase, event, opts.onEarlyHints);
	if (!opts.responseLinkHeaderEntries) return;
	if (event) {
		collectResponseLinkHeaderEntries({
			phase: opts.phase,
			event,
			entries: opts.responseLinkHeaderEntries
		});
		return;
	}
	createResponseLinkHeaderEntries({
		phase: opts.phase,
		hints: opts.hints,
		sentLinks: opts.sentLinks,
		entries: opts.responseLinkHeaderEntries
	});
}
function createEarlyHintsCollector(opts) {
	if (!opts?.onEarlyHints && !opts?.responseLinkHeader) return;
	const sentLinks = /* @__PURE__ */ new Set();
	const sentHints = opts.onEarlyHints ? new Array() : void 0;
	const responseLinkHeaderEntries = opts.responseLinkHeader ? new Array() : void 0;
	const responseLinkHeaderFilter = getResponseLinkHeaderFilter(opts.responseLinkHeader);
	return {
		collectStatic: ({ manifest, matchedRoutes }) => {
			if (!matchedRoutes?.length) return;
			collectEarlyHintsPhase({
				phase: "static",
				hints: collectStaticHintsFromManifest(manifest, matchedRoutes),
				sentLinks,
				sentHints,
				onEarlyHints: opts.onEarlyHints,
				responseLinkHeaderEntries
			});
		},
		collectDynamic: (matches) => {
			collectEarlyHintsPhase({
				phase: "dynamic",
				hints: collectDynamicHintsFromMatches(matches),
				sentLinks,
				sentHints,
				onEarlyHints: opts.onEarlyHints,
				responseLinkHeaderEntries
			});
		},
		appendResponseHeaders: (headers) => {
			if (!responseLinkHeaderEntries?.length) return;
			appendResponseLinkHeaders({
				responseHeaders: headers,
				entries: responseLinkHeaderEntries,
				filter: responseLinkHeaderFilter
			});
		}
	};
}
function normalizeTransformAssetResult(result) {
	if (typeof result === "string") return { href: result };
	return result;
}
function escapeCssString(value) {
	return value.replace(/\\/g, "\\\\").replace(/"/g, "\\\"").replace(/\n/g, "\\a ").replace(/\r/g, "\\d ").replace(/\f/g, "\\c ");
}
async function transformInlineCssTemplate(options) {
	const { strings, urls } = options.template;
	if (strings.length !== urls.length + 1) throw new Error(`TanStack Start inlineCss template for ${options.stylesheetHref} is invalid`);
	let css = strings[0];
	for (let index = 0; index < urls.length; index++) {
		const transformed = normalizeTransformAssetResult(await options.transformFn({
			kind: "css-url",
			url: urls[index],
			stylesheetHref: options.stylesheetHref
		}));
		css += escapeCssString(transformed.href) + strings[index + 1];
	}
	return css;
}
async function transformInlineCssStyles(inlineCss, transformFn) {
	const transformedStyles = {};
	const transformedEntries = await Promise.all(Object.entries(inlineCss.styles).map(async ([stylesheetHref, css]) => {
		const template = inlineCss.templates?.[stylesheetHref];
		return [stylesheetHref, template ? await transformInlineCssTemplate({
			stylesheetHref,
			template,
			transformFn
		}) : css];
	}));
	for (const [stylesheetHref, css] of transformedEntries) transformedStyles[stylesheetHref] = css;
	return {
		styles: transformedStyles,
		...inlineCss.templates ? { templates: inlineCss.templates } : {}
	};
}
function resolveTransformAssetsCrossOrigin(config, kind) {
	if (!config) return void 0;
	if (typeof config === "string") return config;
	return config[kind];
}
function isObjectShorthand(transform) {
	return "prefix" in transform;
}
function resolveTransformAssetsConfig(transform) {
	if (typeof transform === "string") {
		const prefix = transform;
		return {
			type: "transform",
			transformFn: ({ url }) => ({ href: `${prefix}${url}` }),
			cache: true
		};
	}
	if (typeof transform === "function") return {
		type: "transform",
		transformFn: transform,
		cache: true
	};
	if (isObjectShorthand(transform)) {
		const { prefix, crossOrigin } = transform;
		return {
			type: "transform",
			transformFn: ({ url, kind }) => {
				const href = `${prefix}${url}`;
				if (kind === "css-url") return { href };
				const co = resolveTransformAssetsCrossOrigin(crossOrigin, kind);
				return co ? {
					href,
					crossOrigin: co
				} : { href };
			},
			cache: true
		};
	}
	if ("createTransform" in transform && transform.createTransform) return {
		type: "createTransform",
		createTransform: transform.createTransform,
		cache: transform.cache !== false
	};
	return {
		type: "transform",
		transformFn: typeof transform.transform === "string" ? (({ url }) => ({ href: `${transform.transform}${url}` })) : transform.transform,
		cache: transform.cache !== false
	};
}
function assignManifestLink(link, next) {
	if (typeof link === "string") return next.crossOrigin ? next : next.href;
	const nextLink = {
		...link,
		href: next.href
	};
	if (next.crossOrigin) nextLink.crossOrigin = next.crossOrigin;
	else delete nextLink.crossOrigin;
	return nextLink;
}
async function transformManifestAssets(source, transformFn, _opts) {
	const manifest = structuredClone(source);
	const inlineCssEnabled = _opts?.inlineCss !== false;
	const scriptTransforms = /* @__PURE__ */ new Map();
	const transformScript = (url) => {
		const cached = scriptTransforms.get(url);
		if (cached) return cached;
		const transformed = Promise.resolve(transformFn({
			url,
			kind: "script"
		})).then(normalizeTransformAssetResult);
		scriptTransforms.set(url, transformed);
		return transformed;
	};
	if (!inlineCssEnabled) delete manifest.inlineCss;
	else if (manifest.inlineCss) manifest.inlineCss = await transformInlineCssStyles(manifest.inlineCss, transformFn);
	for (const route of Object.values(manifest.routes)) {
		if (route.preloads?.length) route.preloads = await Promise.all(route.preloads.map(async (link) => {
			const result = await transformScript(resolveManifestAssetLink(link).href);
			return assignManifestLink(link, {
				href: result.href,
				crossOrigin: result.crossOrigin
			});
		}));
		if (route.css?.length && !manifest.inlineCss) route.css = await Promise.all(route.css.map(async (link) => {
			const result = normalizeTransformAssetResult(await transformFn({
				url: resolveManifestCssLink(link).href,
				kind: "stylesheet"
			}));
			return assignManifestLink(link, {
				href: result.href,
				crossOrigin: result.crossOrigin
			});
		}));
		if (route.scripts?.length) for (const script of route.scripts) {
			const src = script.attrs?.src;
			if (typeof src !== "string") continue;
			const result = await transformScript(src);
			script.attrs = {
				...script.attrs,
				src: result.href
			};
			if (result.crossOrigin) script.attrs.crossOrigin = result.crossOrigin;
			else delete script.attrs.crossOrigin;
		}
	}
	return manifest;
}
/**
* Builds a final ServerManifest without URL transforms. Used when no
* transformAssets option is provided.
*
* Returns a new manifest object so the cached base manifest is never mutated.
*/
function buildManifest(source, opts) {
	return {
		...source.scriptFormat ? { scriptFormat: source.scriptFormat } : {},
		...opts?.inlineCss !== false && source.inlineCss ? { inlineCss: structuredClone(source.inlineCss) } : {},
		routes: { ...source.routes }
	};
}
function getStaticHandlerInlineCssDefault(handlerInlineCss) {
	if (typeof handlerInlineCss === "function") return;
	return handlerInlineCss ?? true;
}
async function resolveInlineCssForRequest(opts) {
	if (opts.requestInlineCss !== void 0) return opts.requestInlineCss;
	if (typeof opts.handlerInlineCss === "function") return await opts.handlerInlineCss({ request: opts.request });
	return opts.handlerInlineCss ?? true;
}
function createCachedBaseManifestLoader(loadBaseManifest) {
	let baseManifestPromise;
	return () => {
		if (!baseManifestPromise) baseManifestPromise = loadBaseManifest().catch((error) => {
			baseManifestPromise = void 0;
			throw error;
		});
		return baseManifestPromise;
	};
}
function createFinalManifestTransformResolver(transformAssets, opts) {
	const transformConfig = transformAssets !== void 0 ? resolveTransformAssetsConfig(transformAssets) : void 0;
	const cache = transformConfig ? transformConfig.cache : true;
	const warmup = !!transformAssets && typeof transformAssets === "object" && "warmup" in transformAssets && transformAssets.warmup === true;
	let cachedCreateTransformPromise;
	const clearCachedCreateTransform = () => {
		cachedCreateTransformPromise = void 0;
	};
	return {
		cache,
		warmup,
		clearCachedCreateTransform,
		getTransformFn: async (ctx) => {
			if (!transformConfig) return void 0;
			if (transformConfig.type !== "createTransform") return transformConfig.transformFn;
			if (!cache || !opts.cacheCreateTransform) return transformConfig.createTransform(ctx);
			if (!cachedCreateTransformPromise) cachedCreateTransformPromise = Promise.resolve(transformConfig.createTransform(ctx)).catch((error) => {
				clearCachedCreateTransform();
				throw error;
			});
			return cachedCreateTransformPromise;
		}
	};
}
function createFinalManifestResolver(opts) {
	const finalManifestCache = /* @__PURE__ */ new Map();
	const transformResolver = createFinalManifestTransformResolver(opts.transformAssets, { cacheCreateTransform: opts.cacheCreateTransform });
	const handlerDefaultInlineCss = getStaticHandlerInlineCssDefault(opts.inlineCss);
	const getRequestManifestOptions = async (requestOpts) => {
		const transformFn = await transformResolver.getTransformFn({
			warmup: false,
			request: requestOpts.request
		});
		const inlineCss = await resolveInlineCssForRequest({
			request: requestOpts.request,
			handlerInlineCss: opts.inlineCss,
			requestInlineCss: requestOpts.requestInlineCss
		});
		return {
			getBaseManifest: requestOpts.getBaseManifest,
			transformFn,
			cache: transformResolver.cache,
			inlineCss
		};
	};
	const resolveRequest = async (requestOpts, cache) => {
		return resolveFinalManifest({
			...await getRequestManifestOptions(requestOpts),
			finalManifestCache: cache
		});
	};
	return {
		warmup: ({ getBaseManifest }) => warmupFinalManifest({
			enabled: transformResolver.warmup,
			handlerDefaultInlineCss,
			cache: transformResolver.cache,
			finalManifestCache,
			getBaseManifest,
			getTransformFn: () => transformResolver.getTransformFn({ warmup: true }),
			onError: transformResolver.clearCachedCreateTransform
		}),
		resolveCached: (requestOpts) => resolveRequest(requestOpts, finalManifestCache),
		resolveUncached: (requestOpts) => resolveRequest(requestOpts, void 0)
	};
}
function getFinalManifestCacheKey(inlineCss) {
	return inlineCss ? "inline-css" : "linked-css";
}
function cacheFinalManifestPromise(cachedFinalManifestPromises, cacheKey, promise) {
	const cachedFinalManifestPromise = promise.catch((error) => {
		if (cachedFinalManifestPromises.get(cacheKey) === cachedFinalManifestPromise) cachedFinalManifestPromises.delete(cacheKey);
		throw error;
	});
	cachedFinalManifestPromises.set(cacheKey, cachedFinalManifestPromise);
	return cachedFinalManifestPromise;
}
function getOrCreateCachedFinalManifestPromise(cachedFinalManifestPromises, cacheKey, computeFinalManifest) {
	const cachedFinalManifestPromise = cachedFinalManifestPromises.get(cacheKey);
	if (cachedFinalManifestPromise) return cachedFinalManifestPromise;
	return cacheFinalManifestPromise(cachedFinalManifestPromises, cacheKey, Promise.resolve().then(computeFinalManifest));
}
async function buildFinalManifest(opts) {
	return opts.transformFn ? await transformManifestAssets(opts.base, opts.transformFn, { inlineCss: opts.inlineCss }) : buildManifest(opts.base, { inlineCss: opts.inlineCss });
}
async function resolveFinalManifest(opts) {
	const computeFinalManifest = async () => {
		return buildFinalManifest({
			base: await opts.getBaseManifest(),
			transformFn: opts.transformFn,
			inlineCss: opts.inlineCss
		});
	};
	if (opts.finalManifestCache && (!opts.transformFn || opts.cache)) return getOrCreateCachedFinalManifestPromise(opts.finalManifestCache, getFinalManifestCacheKey(opts.inlineCss), computeFinalManifest);
	return computeFinalManifest();
}
function warmupFinalManifest(opts) {
	if (!opts.enabled || opts.handlerDefaultInlineCss === void 0 || !opts.cache) return;
	const inlineCss = opts.handlerDefaultInlineCss;
	const warmupPromise = getOrCreateCachedFinalManifestPromise(opts.finalManifestCache, getFinalManifestCacheKey(inlineCss), async () => {
		const [base, transformFn] = await Promise.all([opts.getBaseManifest(), opts.getTransformFn()]);
		return buildFinalManifest({
			base,
			transformFn,
			inlineCss
		});
	});
	if (opts.onError) warmupPromise.catch(opts.onError);
	return warmupPromise;
}
var ServerFunctionSerializationAdapter = createSerializationAdapter({
	key: "$TSS/serverfn",
	test: (v) => {
		if (typeof v !== "function") return false;
		if (!(TSS_SERVER_FUNCTION in v)) return false;
		return !!v[TSS_SERVER_FUNCTION];
	},
	toSerializable: ({ serverFnMeta }) => ({ functionId: serverFnMeta.id }),
	fromSerializable: ({ functionId }) => {
		const fn = async (opts, signal) => {
			const serverFn = await getServerFnById(functionId, { origin: "client" });
			const result = await serverFn({
				data: opts?.data,
				context: opts?.context,
				method: serverFn.method ?? "GET"
			}, signal);
			if (result.error !== void 0) throw result.error;
			return result.result;
		};
		return fn;
	}
});
function getStartResponseHeaders(opts) {
	return mergeHeaders({ "Content-Type": "text/html; charset=utf-8" }, ..._getRenderedMatches(opts.router.stores.matches.get()).map((match) => {
		return match.headers;
	}));
}
var entriesPromise;
var defaultCsrfMiddleware = createCsrfMiddleware({ filter: (ctx) => ctx.handlerType === "serverFn" });
var getCachedBaseManifest = createCachedBaseManifestLoader(() => getStartManifest());
var getProdBaseManifest = () => getCachedBaseManifest();
var getBaseManifest = getProdBaseManifest;
var createEarlyHintsForRequest = createEarlyHintsCollector;
async function loadEntries() {
	const [routerEntry, startEntry, pluginAdapters] = await Promise.all([
		import("./router-Cdp50kSt.mjs"),
		import("./start-5Z2QO8AU.mjs"),
		import("./empty-plugin-adapters-D9UWiqvJ.mjs")
	]);
	return {
		routerEntry,
		startEntry,
		pluginAdapters
	};
}
function getEntries() {
	if (!entriesPromise) entriesPromise = loadEntries();
	return entriesPromise;
}
var ROUTER_BASEPATH = "/";
var SERVER_FN_BASE = "/_serverFn/";
var IS_PRERENDERING = process.env.TSS_PRERENDERING === "true";
var IS_SHELL_ENV = process.env.TSS_SHELL === "true";
var IS_DEV = false;
var ERR_NO_RESPONSE = IS_DEV ? `It looks like you forgot to return a response from your server route handler. If you want to defer to the app router, make sure to have a component set in this route.` : "Internal Server Error";
var ERR_NO_DEFER = IS_DEV ? `You cannot defer to the app router if there is no component defined on this route.` : "Internal Server Error";
function throwRouteHandlerError() {
	throw new Error(ERR_NO_RESPONSE);
}
function throwIfMayNotDefer() {
	throw new Error(ERR_NO_DEFER);
}
function getResponseFromResult(result) {
	return isSsrResponse(result) || result instanceof Response ? result : result?.response;
}
var responseBodySources = /* @__PURE__ */ new WeakMap();
function disposeResponseResult(result, reason) {
	const response = getResponseFromResult(result);
	if (isSsrResponse(response) || response instanceof Response) disposeSsrResponse(response, reason);
}
function hasResponseBody(value) {
	return value instanceof Response && value.body !== null;
}
function inheritsResponseOwnership(ownership, candidate) {
	return hasResponseBody(candidate) && (candidate.body === ownership.response.body || responseBodySources.get(candidate) === ownership.response);
}
function disposeResponseOwnership(ownership, reason) {
	const { response, sourceBody, streamResponse } = ownership;
	streamResponse?.dispose(reason);
	if (!streamResponse || response.body !== sourceBody) response.body.cancel(reason).catch(() => {});
}
function getOwnedResponse(ownership) {
	const { response, sourceBody, streamResponse } = ownership;
	if (!streamResponse) return response;
	if (streamResponse.response === response && response.body === sourceBody) return streamResponse;
	if (response.body === sourceBody) return {
		...streamResponse,
		response
	};
	return {
		...streamResponse,
		response,
		dispose(reason) {
			disposeResponseOwnership(ownership, reason);
		}
	};
}
function createLateResponseDisposer(signal) {
	return (result) => disposeResponseResult(result, signal.reason);
}
/**
* Compose middleware around a terminal response handler. With no middleware
* the terminal runs directly.
*/
async function executeMiddleware(middlewares, terminal, ctx, signal, terminalNext) {
	let index = -1;
	let responseOwnership;
	let settled = false;
	const disposeAbandonedResult = createLateResponseDisposer(signal);
	const setResponse = (response) => {
		const ssrResponse = isSsrResponse(response) ? response : void 0;
		const streamResponse = ssrResponse?.serverSsrCleanup === "stream" ? ssrResponse : void 0;
		const exposed = ssrResponse ? ssrResponse.response : response;
		const current = responseOwnership;
		if (settled) {
			if (exposed !== ctx.response) disposeResponseResult(response, "late middleware response");
			return;
		}
		if (current && current.response === exposed) current.streamResponse ??= streamResponse;
		else if (current && inheritsResponseOwnership(current, exposed)) {
			current.response = exposed;
			current.streamResponse ??= streamResponse;
		} else {
			if (current) disposeResponseOwnership(current, "middleware response replaced");
			if (hasResponseBody(exposed)) responseOwnership = {
				response: exposed,
				sourceBody: exposed.body,
				streamResponse
			};
			else responseOwnership = void 0;
		}
		ctx.response = exposed;
	};
	const reconcileCtxResponse = () => {
		if (ctx.response !== responseOwnership?.response) setResponse(ctx.response);
	};
	let nextPromise;
	function next(nextCtx) {
		const result = runNext(nextCtx);
		nextPromise = result;
		return result;
	}
	async function runNext(nextCtx) {
		signal.throwIfAborted();
		if (nextCtx) {
			if (nextCtx.context) ctx.context = safeObjectMerge(ctx.context, nextCtx.context);
			for (const key of Object.keys(nextCtx)) if (key === "response") setResponse(nextCtx.response);
			else if (key !== "context") ctx[key] = nextCtx[key];
		}
		index++;
		const isTerminal = index === middlewares.length;
		const middleware = index < middlewares.length ? middlewares[index] : isTerminal ? terminal : void 0;
		const middlewareNext = isTerminal && terminalNext ? terminalNext : next;
		if (!middleware) return ctx;
		let result;
		try {
			const pending = middleware({
				...ctx,
				next: middlewareNext
			});
			if (nextPromise && pending === nextPromise) {
				nextPromise = void 0;
				await pending;
				if (signal.aborted) throw signal.reason;
				return ctx;
			} else if (!isPromise(pending)) {
				result = pending;
				signal.throwIfAborted();
			} else result = await waitForReason(pending, signal, disposeAbandonedResult, disposeAbandonedResult);
		} catch (err) {
			reconcileCtxResponse();
			if (signal.aborted) {
				if (result !== void 0) disposeAbandonedResult(result);
				if (err !== signal.reason) disposeAbandonedResult(err);
				throw signal.reason;
			}
			if (err instanceof Response) {
				setResponse(err);
				return ctx;
			}
			throw err;
		}
		if (isTerminal && terminalNext && !result) throwRouteHandlerError();
		reconcileCtxResponse();
		if (result && result !== ctx) {
			const response = getResponseFromResult(result);
			if (response !== void 0 && response !== ctx.response) setResponse(response);
			if (response !== result && result.context && result.context !== ctx.context) ctx.context = safeObjectMerge(ctx.context, result.context);
		}
		return ctx;
	}
	try {
		await runNext();
		const response = ctx.response;
		if (!response) throwRouteHandlerError();
		reconcileCtxResponse();
		if (signal.aborted) throw signal.reason;
		settled = true;
		return responseOwnership ? getOwnedResponse(responseOwnership) : response;
	} catch (err) {
		settled = true;
		if (responseOwnership) disposeResponseOwnership(responseOwnership, signal.aborted ? signal.reason : err);
		throw err;
	}
}
/**
* Creates the TanStack Start request handler.
*
* @example Backwards-compatible usage (handler callback only):
* ```ts
* export default createStartHandler(defaultStreamHandler)
* ```
*
* @example With CDN URL rewriting:
* ```ts
* export default createStartHandler({
*   handler: defaultStreamHandler,
*   transformAssets: 'https://cdn.example.com',
* })
* ```
*
* @example With per-request URL rewriting:
* ```ts
* export default createStartHandler({
*   handler: defaultStreamHandler,
*   transformAssets: {
*     transform: ({ url }) => {
*       const cdnBase = getRequest().headers.get('x-cdn-base') || ''
*       return { href: `${cdnBase}${url}` }
*     },
*     cache: false,
*   },
* })
* ```
*/
function createStartHandler(cbOrOptions) {
	const handlerOptions = typeof cbOrOptions === "function" ? {} : cbOrOptions;
	const cb = typeof cbOrOptions === "function" ? cbOrOptions : cbOrOptions.handler;
	const finalManifestResolver = createFinalManifestResolver({
		...handlerOptions,
		cacheCreateTransform: true
	});
	const resolveManifestForRequest = finalManifestResolver.resolveCached;
	finalManifestResolver.warmup({ getBaseManifest: () => getBaseManifest(void 0) });
	const startRequestResolver = async (request, requestOpts) => {
		const signal = request.signal;
		let router;
		let routerPromise;
		let responseOwnsCleanup = false;
		try {
			signal.throwIfAborted();
			const { url, handledProtocolRelativeURL } = getNormalizedURL(request.url);
			const href = url.pathname + url.search + url.hash;
			const origin = url.origin;
			if (handledProtocolRelativeURL) return Response.redirect(url, 308);
			const entries = await waitForReason(getEntries(), signal);
			const isServerFnRequest = !!SERVER_FN_BASE && url.pathname.startsWith(SERVER_FN_BASE);
			const startInstance = entries.startEntry.startInstance;
			let startOptions;
			if (startInstance) {
				const pendingStartOptions = startInstance.getOptions();
				startOptions = isPromise(pendingStartOptions) ? await waitForReason(pendingStartOptions, signal) : pendingStartOptions;
				signal.throwIfAborted();
			} else startOptions = {};
			const { hasPluginAdapters, pluginSerializationAdapters } = entries.pluginAdapters;
			const serializationAdapters = [
				...startOptions.serializationAdapters || [],
				...hasPluginAdapters ? pluginSerializationAdapters : [],
				ServerFunctionSerializationAdapter
			];
			const requestStartOptions = {
				...startOptions,
				requestMiddleware: startInstance ? startOptions.requestMiddleware : isServerFnRequest ? [defaultCsrfMiddleware] : void 0,
				serializationAdapters
			};
			const flattenedRequestMiddlewares = requestStartOptions.requestMiddleware ? flattenMiddlewares(requestStartOptions.requestMiddleware) : [];
			const executedRequestMiddlewares = new Set(flattenedRequestMiddlewares);
			const getRouter = () => {
				routerPromise ??= (async () => {
					signal.throwIfAborted();
					const requestRouter = await waitForReason(entries.routerEntry.getRouter(), signal);
					let isShell = IS_SHELL_ENV;
					if (IS_PRERENDERING && !isShell) isShell = request.headers.get(HEADERS.TSS_SHELL) === "true";
					const history = createServerHistory(href);
					requestRouter.update({
						history,
						isShell,
						isPrerendering: IS_PRERENDERING,
						origin: requestRouter.options.origin ?? origin,
						defaultSsr: requestStartOptions.defaultSsr,
						serializationAdapters: [...requestStartOptions.serializationAdapters, ...requestRouter.options.serializationAdapters || []],
						basepath: ROUTER_BASEPATH
					});
					router = requestRouter;
					return requestRouter;
				})();
				return routerPromise;
			};
			const handlerType = isServerFnRequest ? "serverFn" : "router";
			const startContext = {
				getRouter,
				startOptions: requestStartOptions,
				request,
				executedRequestMiddlewares,
				handlerType
			};
			let terminal;
			if (isServerFnRequest) {
				const serverFnId = url.pathname.slice(SERVER_FN_BASE.length).split("/")[0];
				if (!serverFnId) throw new Error("Invalid server action param for serverFnId");
				terminal = ({ context }) => runWithStartContext({
					...startContext,
					contextAfterGlobalMiddlewares: context
				}, () => handleServerAction({
					request,
					context: requestOpts?.context,
					serverFnId
				}));
			} else {
				const executeRouter = async (serverContext, matchedRoutes) => {
					if (!/(^|,)\s*(\*\/\*|text\/html)/.test(request.headers.get("Accept") || "*/*")) return normalizeSsrResponse(Response.json({ error: "Only HTML requests are supported here" }, { status: 406 }));
					const manifest = await waitForReason(resolveManifestForRequest({
						request,
						requestInlineCss: requestOpts?.inlineCss,
						getBaseManifest: () => getBaseManifest(matchedRoutes)
					}), signal);
					const earlyHints = createEarlyHintsForRequest({
						onEarlyHints: requestOpts?.onEarlyHints,
						responseLinkHeader: requestOpts?.responseLinkHeader
					});
					earlyHints?.collectStatic({
						manifest,
						matchedRoutes
					});
					const routerInstance = await getRouter();
					attachRouterServerSsrUtils({
						router: routerInstance,
						manifest,
						getRequestAssets: () => getStartContext({ throwIfNotFound: false })?.requestAssets
					});
					routerInstance.options.additionalContext = { serverContext };
					await routerInstance.load({ _signal: signal });
					signal.throwIfAborted();
					if (routerInstance._serverResult?.type === "redirect") return normalizeSsrResponse(routerInstance._serverResult.redirect);
					earlyHints?.collectDynamic(_getRenderedMatches(routerInstance.stores.matches.get()));
					const ctx = getStartContext({ throwIfNotFound: false });
					await routerInstance.serverSsr.dehydrate({
						requestAssets: ctx?.requestAssets,
						signal
					});
					signal.throwIfAborted();
					const responseHeaders = getStartResponseHeaders({ router: routerInstance });
					earlyHints?.appendResponseHeaders(responseHeaders);
					signal.throwIfAborted();
					const disposeLate = createLateResponseDisposer(signal);
					return normalizeSsrResponse(await waitForReason(cb({
						request,
						router: routerInstance,
						responseHeaders
					}), signal, disposeLate, disposeLate));
				};
				terminal = ({ context }) => runWithStartContext({
					...startContext,
					contextAfterGlobalMiddlewares: context
				}, () => handleServerRoutes({
					getRouter,
					request,
					url,
					executeRouter,
					context,
					executedRequestMiddlewares
				}));
			}
			const middlewareResponse = await executeMiddleware(flattenedRequestMiddlewares.map((d) => d.options.server), terminal, {
				request,
				pathname: url.pathname,
				handlerType,
				context: createNullProtoObject(requestOpts?.context)
			}, signal);
			let result;
			try {
				result = await handleRedirectResponse(middlewareResponse, getRouter, signal, isServerFnRequest && request.headers.get("x-tsr-serverFn") === "true");
				if (request.method === "HEAD") result = stripSsrResponseBody(result, "HEAD body stripped");
			} catch (error) {
				disposeResponseResult(middlewareResponse, signal.aborted ? signal.reason : error);
				throw error;
			}
			bindSsrResponseToRequest(router, result, signal);
			signal.throwIfAborted();
			responseOwnsCleanup = result.serverSsrCleanup === "stream";
			return result.response;
		} finally {
			if (router?.serverSsr && !responseOwnsCleanup) router.serverSsr.cleanup();
		}
	};
	return requestHandler(startRequestResolver);
}
var relativeRedirectProtocols = /* @__PURE__ */ new Set();
async function handleRedirectResponse(response, getRouter, signal, serializeRedirect) {
	signal.throwIfAborted();
	const ssrResponse = normalizeSsrResponse(response);
	const redirect = ssrResponse.response;
	if (!isRedirect(redirect)) return ssrResponse;
	const opts = redirect.options;
	const href = redirect.headers.get("Location") || opts.href;
	if (!href && opts.to && typeof opts.to === "string" && !opts.to.startsWith("/")) throw new Error(`Server side redirects must use absolute paths via the 'href' or 'to' options. The redirect() method's "to" property accepts an internal path only. Use the "href" property to provide an external URL. Received: ${JSON.stringify(opts)}`);
	if (!href && [
		"params",
		"search",
		"hash"
	].some((d) => typeof opts[d] === "function")) throw new Error(`Server side redirects must use static search, params, and hash values and do not support functional values. Received functional values for: ${Object.keys(opts).filter((d) => typeof opts[d] === "function").map((d) => `"${d}"`).join(", ")}`);
	signal.throwIfAborted();
	if (href && !isDangerousProtocol(href, relativeRedirectProtocols)) {
		opts.href = href;
		redirect.headers.set("Location", href);
	} else {
		const router = await getRouter();
		signal.throwIfAborted();
		router.resolveRedirect(redirect);
	}
	if (serializeRedirect) {
		const redirectOptions = { ...opts };
		delete redirectOptions.headers;
		const responseHeaders = new Headers(redirect.headers);
		responseHeaders.set("content-type", "application/json");
		return replaceSsrResponse(ssrResponse, Response.json({
			...redirectOptions,
			isSerializedRedirect: true
		}, { headers: responseHeaders }), "redirect response replaced");
	}
	return ssrResponse;
}
function withParsedParams(handler, matchedRoutes) {
	if (!matchedRoutes.some((route) => route.options.params?.parse ?? route.options.parseParams)) return handler;
	return (ctx) => {
		const params = Object.assign(Object.create(null), ctx.params);
		for (const route of matchedRoutes) {
			const parse = route.options.params?.parse ?? route.options.parseParams;
			if (parse) Object.assign(params, parse(params));
		}
		return handler({
			...ctx,
			params
		});
	};
}
async function handleServerRoutes({ getRouter, request, url, executeRouter, context, executedRequestMiddlewares }) {
	const router = await getRouter();
	const pathname = executeRewriteInput(router.rewrite, url).pathname;
	const [matchedRoutes, rawParams, foundRoute] = router.getMatchedRoutes(pathname);
	const isExactMatch = foundRoute && rawParams["**"] === void 0;
	const routeMiddlewares = [];
	let terminalHandler = (ctx) => executeRouter(ctx.context, matchedRoutes);
	let terminalNext;
	for (const route of matchedRoutes) {
		const serverMiddleware = route.options.server?.middleware;
		if (serverMiddleware) {
			const flattened = flattenMiddlewares(serverMiddleware);
			for (const m of flattened) if (!executedRequestMiddlewares.has(m)) routeMiddlewares.push(m.options.server);
		}
	}
	const server = foundRoute?.options.server;
	if (server?.handlers && isExactMatch) {
		const handlers = typeof server.handlers === "function" ? server.handlers({ createHandlers: (d) => d }) : server.handlers;
		const requestMethod = request.method.toUpperCase();
		const handler = requestMethod === "HEAD" ? handlers["HEAD"] ?? handlers["GET"] ?? handlers["ANY"] : handlers[requestMethod] ?? handlers["ANY"];
		if (handler) {
			const mayDefer = !!foundRoute.options.component;
			if (typeof handler !== "function") {
				if (handler.middleware?.length) {
					const handlerMiddlewares = flattenMiddlewares(handler.middleware);
					for (const m of handlerMiddlewares) routeMiddlewares.push(m.options.server);
				}
			}
			const routeHandler = typeof handler === "function" ? handler : handler.handler;
			if (routeHandler) {
				const parsedHandler = withParsedParams(routeHandler, matchedRoutes);
				if (!mayDefer) {
					terminalHandler = parsedHandler;
					terminalNext = throwIfMayNotDefer;
				} else routeMiddlewares.push(parsedHandler);
			}
		}
	}
	return normalizeSsrResponse(await executeMiddleware(routeMiddlewares, terminalHandler, {
		request,
		context,
		params: rawParams,
		pathname,
		handlerType: "router"
	}, request.signal, terminalNext));
}
var fetch = createStartHandler(defaultStreamHandler);
function createServerEntry(entry) {
	return { async fetch(...args) {
		return await entry.fetch(...args);
	} };
}
var server_default = createServerEntry({ fetch });
//#endregion
export { createServerEntry, server_default as default, ssr_exports as i, TSS_SERVER_FUNCTION as n, getServerFnById as r, createServerFn as t };

````

## `frontend_demo/.vercel/output/functions/__server.func/_ssr/start-5Z2QO8AU.mjs`
````mjs
//#region node_modules/.nitro/vite/services/ssr/assets/start-5Z2QO8AU.js
var startInstance = void 0;
//#endregion
export { startInstance };

````

## `frontend_demo/.vercel/output/functions/__server.func/_tanstack-start-manifest_v-C1wz4kaJ.mjs`
````mjs
//#region node_modules/.nitro/vite/services/ssr/assets/_tanstack-start-manifest_v-C1wz4kaJ.js
var tsrStartManifest = () => ({ routes: {
	__root__: {
		filePath: "C:/Users/hans3/Desktop/Code and more/temp/frontend_demo/src/routes/__root.tsx",
		children: ["/"],
		preloads: ["/assets/index-BcgHBPiW.js"],
		scripts: [{ attrs: {
			type: "module",
			async: !0,
			src: "/assets/index-BcgHBPiW.js"
		} }]
	},
	"/": {
		filePath: "C:/Users/hans3/Desktop/Code and more/temp/frontend_demo/src/routes/index.tsx",
		children: void 0,
		preloads: ["/assets/routes-iHJqnnMA.js"]
	}
} });
//#endregion
export { tsrStartManifest };

````

## `frontend_demo/.vercel/output/functions/__server.func/index.mjs`
````mjs
globalThis.__nitro_main__ = import.meta.url;
import { a as NodeResponse, n as HTTPError, r as defineLazyEventHandler, t as H3Core } from "./_libs/h3+rou3+srvx.mjs";
//#region node_modules/nitro/dist/runtime/internal/route-rules.mjs
var headers = ((m) => function headersRouteRule(event) {
	for (const [key, value] of Object.entries(m.options || {})) event.res.headers.set(key, value);
});
//#endregion
//#region #nitro/virtual/routing
var findRouteRules = /* @__PURE__ */ (() => {
	const $0 = [{
		name: "headers",
		route: "/assets/**",
		handler: headers,
		options: { "cache-control": "public, max-age=31536000, immutable" }
	}];
	return (m, p) => {
		let r = [];
		if (p.charCodeAt(p.length - 1) === 47) p = p.slice(0, -1) || "/";
		let s = p.split("/");
		if (s.length > 1) {
			if (s[1] === "assets") r.unshift({
				data: $0,
				params: { "_": s.slice(2).join("/") }
			});
		}
		return r;
	};
})();
var _lazy_SjIjPi = defineLazyEventHandler(() => import("./_chunks/ssr-renderer.mjs"));
var findRoute = /* @__PURE__ */ (() => {
	const data = {
		route: "/**",
		handler: _lazy_SjIjPi
	};
	return ((_m, p) => {
		return {
			data,
			params: { "_": p.slice(1) }
		};
	});
})();
[].filter(Boolean);
//#endregion
//#region node_modules/nitro/dist/runtime/internal/error/prod.mjs
var errorHandler = (error, event) => {
	const res = defaultHandler(error, event);
	return new NodeResponse(typeof res.body === "string" ? res.body : JSON.stringify(res.body, null, 2), res);
};
function defaultHandler(error, event) {
	const unhandled = error.unhandled ?? !HTTPError.isError(error);
	const { status = 500, statusText = "" } = unhandled ? {} : error;
	if (status === 404) {
		const url = event.url || new URL(event.req.url);
		const baseURL = "/";
		if (/^\/[^/]/.test(baseURL) && !url.pathname.startsWith(baseURL)) return {
			status: 302,
			headers: new Headers({ location: `${baseURL}${url.pathname.slice(1)}${url.search}` })
		};
	}
	const headers = new Headers(unhandled ? {} : error.headers);
	headers.set("content-type", "application/json; charset=utf-8");
	return {
		status,
		statusText,
		headers,
		body: {
			error: true,
			...unhandled ? {
				status,
				unhandled: true
			} : typeof error.toJSON === "function" ? error.toJSON() : {
				status,
				statusText,
				message: error.message
			}
		}
	};
}
//#endregion
//#region #nitro/virtual/error-handler
var errorHandlers = [errorHandler];
async function error_handler_default(error, event) {
	for (const handler of errorHandlers) try {
		const response = await handler(error, event, { defaultHandler });
		if (response) return response;
	} catch (error) {
		console.error(error);
	}
}
//#endregion
//#region #nitro/virtual/app
function createNitroApp() {
	const captureError = (error, errorCtx) => {
		if (errorCtx?.event) {
			const errors = errorCtx.event.req.context?.nitro?.errors;
			if (errors) errors.push({
				error,
				context: errorCtx
			});
		}
	};
	const h3App = createH3App({ onError(error, event) {
		return error_handler_default(error, event);
	} });
	let appHandler = (req) => {
		req.context ||= {};
		req.context.nitro = req.context.nitro || { errors: [] };
		return h3App.fetch(req);
	};
	return {
		fetch: appHandler,
		h3: h3App,
		hooks: void 0,
		captureError
	};
}
function createH3App(config) {
	const h3App = new H3Core(config);
	h3App["~findRoute"] = (event) => findRoute(event.req.method, event.url.pathname);
	h3App["~getMiddleware"] = (event, route) => {
		const pathname = event.url.pathname;
		const method = event.req.method;
		const middleware = [];
		const routeRules = getRouteRules(method, pathname);
		event.context.routeRules = routeRules?.routeRules;
		if (routeRules?.routeRuleMiddleware.length) middleware.push(...routeRules.routeRuleMiddleware);
		if (route?.data?.middleware?.length) middleware.push(...route.data.middleware);
		return middleware;
	};
	return h3App;
}
//#endregion
//#region node_modules/nitro/dist/runtime/internal/app.mjs
var APP_ID = "default";
function useNitroApp() {
	let instance = useNitroApp._instance;
	if (instance) return instance;
	instance = useNitroApp._instance = createNitroApp();
	globalThis.__nitro__ = globalThis.__nitro__ || {};
	globalThis.__nitro__[APP_ID] = instance;
	return instance;
}
function getRouteRules(method, pathname) {
	const m = findRouteRules(method, pathname);
	if (!m?.length) return { routeRuleMiddleware: [] };
	const routeRules = {};
	for (const layer of m) for (const rule of layer.data) {
		const currentRule = routeRules[rule.name];
		if (currentRule) {
			if (rule.options === false) {
				delete routeRules[rule.name];
				continue;
			}
			if (typeof currentRule.options === "object" && typeof rule.options === "object") currentRule.options = {
				...currentRule.options,
				...rule.options
			};
			else currentRule.options = rule.options;
			currentRule.route = rule.route;
			currentRule.params = {
				...currentRule.params,
				...layer.params
			};
		} else if (rule.options !== false) routeRules[rule.name] = {
			...rule,
			params: layer.params
		};
	}
	const middleware = [];
	const orderedRules = Object.values(routeRules).sort((a, b) => (a.handler?.order || 0) - (b.handler?.order || 0));
	for (const rule of orderedRules) {
		if (rule.options === false || !rule.handler) continue;
		middleware.push(rule.handler(rule));
	}
	return {
		routeRules,
		routeRuleMiddleware: middleware
	};
}
//#endregion
//#region node_modules/nitro/dist/presets/vercel/runtime/isr.mjs
var ISR_URL_PARAM = "__isr_route";
function isrRouteRewrite(reqUrl, xNowRouteMatches) {
	if (xNowRouteMatches) {
		const isrURL = new URLSearchParams(xNowRouteMatches).get(ISR_URL_PARAM);
		if (isrURL) return [decodeURIComponent(isrURL), ""];
	} else {
		const queryIndex = reqUrl.indexOf("?");
		if (queryIndex !== -1) {
			const params = new URLSearchParams(reqUrl.slice(queryIndex + 1));
			const isrURL = params.get(ISR_URL_PARAM);
			if (isrURL) {
				params.delete(ISR_URL_PARAM);
				return [decodeURIComponent(isrURL), params.toString()];
			}
		}
	}
}
//#endregion
//#region node_modules/nitro/dist/presets/vercel/runtime/vercel.web.mjs
var nitroApp = useNitroApp();
var vercel_web_default = { async fetch(req, context) {
	const isrURL = isrRouteRewrite(req.url, req.headers.get("x-now-route-matches"));
	if (isrURL) {
		const { routeRules } = getRouteRules("", isrURL[0]);
		if (routeRules?.isr) req = new Request(new URL(isrURL[0] + (isrURL[1] ? `?${isrURL[1]}` : ""), req.url).href, req);
	}
	req.runtime ??= { name: "vercel" };
	req.runtime.vercel = { context };
	let ip;
	Object.defineProperty(req, "ip", { get() {
		const h = req.headers.get("x-forwarded-for");
		return ip ??= h?.split(",").shift()?.trim();
	} });
	req.waitUntil = context?.waitUntil;
	return nitroApp.fetch(req);
} };
//#endregion
export { vercel_web_default as default };

````

## `frontend_demo/.vercel/output/nitro.json`
````json
{
  "date": "2026-11-21T08:25:17.260Z",
  "preset": "vercel",
  "framework": {
    "name": "nitro",
    "version": "3.0.260610-beta"
  },
  "versions": {
    "nitro": "3.0.260610-beta"
  },
  "serverEntry": "functions/__server.func/index.mjs",
  "publicDir": "static",
  "commands": {
    "preview": "npx srvx --static ../../static ./functions/__server.func/index.mjs",
    "deploy": "npx vercel deploy --prebuilt"
  },
  "config": {
    "vercel": {
      "skewProtection": false,
      "cronHandlerRoute": "/_vercel/cron",
      "functions": {
        "runtime": "nodejs24.x"
      }
    }
  }
}
````

## `frontend_demo/.vercel/output/static/assets/index-BcgHBPiW.js`
*(?bersprungen: Datei gr??er als 200 KB)*

## `frontend_demo/.vercel/output/static/assets/routes-iHJqnnMA.js`
````js
import{a as e,c as t,i as n,n as r,o as i,r as a,s as o,t as s}from"./index-BcgHBPiW.js";function c(e){if(Array.isArray(e))return e.flatMap(e=>c(e));if(typeof e!=`string`)return[];let t=[],n=0,r,i,a,o,s,l=()=>{for(;n<e.length&&/\s/.test(e.charAt(n));)n+=1;return n<e.length},u=()=>(i=e.charAt(n),i!==`=`&&i!==`;`&&i!==`,`);for(;n<e.length;){for(r=n,s=!1;l();)if(i=e.charAt(n),i===`,`){for(a=n,n+=1,l(),o=n;n<e.length&&u();)n+=1;n<e.length&&e.charAt(n)===`=`?(s=!0,n=o,t.push(e.slice(r,a)),r=n):n=a+1}else n+=1;(!s||n>=e.length)&&t.push(e.slice(r))}return t}function l(e){return e instanceof Headers?e:Array.isArray(e)||typeof e==`object`?new Headers(e):null}function u(...e){return e.reduce((e,t)=>{let n=l(t);if(!n)return e;for(let[t,r]of n.entries())t===`set-cookie`?c(r).forEach(t=>e.append(`set-cookie`,t)):e.set(t,r);return e},new Headers)}var d=t(o());function f(e,t){let n=String(e).split(`.`),r=String(t).split(`.`),i=Math.max(n.length,r.length);for(let e=0;e<i;e+=1){let t=n[e]??``,i=r[e]??``,a=/^\d+$/.test(t),o=/^\d+$/.test(i);if(a&&o){let e=Number(t)-Number(i);if(e!==0)return e}else{let e=t.localeCompare(i,`de`);if(e!==0)return e}}return 0}var p=897305.45,m=`NUMMER_001 · blank BoQ (248 positions)`,h=[{oz:`01.01.0010`,title:`Baugrube ausheben, Bodenklasse 3–5`,longText:`Aushub einschließlich Laden und Abfuhr bis 15 km. Böschungen nach statischer Vorgabe.`,qty:1840,unit:`m³`,benchmark:18.4,laborShare:.35,hoursPerUnit:.08,materialPerUnit:4.2,kind:null,rationale:`Unit price sits inside the reference band for excavation (median €18.40/m³ across priced sewer jobs).`,rfi:``},{oz:`01.02.0140`,title:`Rohrgraben DN 300, einschließlich Verbau`,longText:`Graben für Steinzeugrohr DN 300, Verbau nach Wahl des AN, Sohle plan.`,qty:620,unit:`m`,benchmark:86,laborShare:.55,hoursPerUnit:.55,materialPerUnit:22,kind:`vague`,rationale:`“Verbau nach Wahl des AN” leaves shoring method and groundwater unspecified. In  the priced twin this line alone moves five-figure money.`,rfi:`Bitte die geforderte Verbauart (Verbaubox / Trägerbohlwand / geböscht) und den Bemessungswasserstand verbindlich vorgeben, damit die Position ohne Nachtrag kalkulierbar ist.`},{oz:`01.02.0210`,title:`Steinzeugrohr DN 300 liefern und verlegen`,longText:`Kanalrohr Steinzeug DN 300, Verbindungssystem F, einschließlich Dichtung.`,qty:610,unit:`m`,benchmark:142,laborShare:.28,hoursPerUnit:.22,materialPerUnit:96,kind:`qty`,rationale:`Pipe length is 10 m shorter than the trench (620 m). A missing connection or a typo — either way the join does not close.`,rfi:`Die Rohrleitung (610 m) ist kürzer als der zugehörige Graben (620 m). Bitte die maßgebende Länge bestätigen.`},{oz:`01.03.0040`,title:`Schacht DN 1000, Tiefe bis 3,00 m`,longText:`Fertigteilschacht einschließlich Schachtabdeckung Klasse D 400.`,qty:14,unit:`St`,benchmark:2480,laborShare:.4,hoursPerUnit:6.5,materialPerUnit:1450,kind:null,rationale:`Comparable shafts in the priced set cluster tightly around €2,480.`,rfi:``},{oz:`01.04.0080`,title:`Heizungswartung Baustelle, wöchentlich`,longText:`Bereitstellung und wöchentliche Wartung der Baustellenheizung für die Wintermonate.`,qty:28,unit:`Wo`,benchmark:.2,laborShare:.9,hoursPerUnit:1.2,materialPerUnit:35,kind:`outlier`,rationale:`A real competitor priced this at €0.20/week (total €5.60). Same-trade medians for site heating sit two orders of magnitude higher. Classic speculative underprice on a line that will be measured.`,rfi:`Die Position ist mit €0,20/Woche nicht auskömmlich. Bitte Leistungsumfang (Gerätetyp, Brennstoff, Betriebsstunden) festlegen, damit ein marktüblicher Einheitspreis angeboten werden kann.`},{oz:`02.01.0030`,title:`Tragschicht 0/32, d = 20 cm`,longText:`Frostschutzschicht liefern, einbauen und verdichten.`,qty:2400,unit:`m²`,benchmark:11.6,laborShare:.32,hoursPerUnit:.04,materialPerUnit:6.8,kind:null,rationale:`Inside the reference band for unbound base.`,rfi:``},{oz:`02.01.0110`,title:`Asphaltdeckschicht AC 11, d = 4 cm`,longText:`Deckschicht nach ZTV Asphalt, Einbauort nach Vorgabe AG.`,qty:2380,unit:`m²`,benchmark:22.5,laborShare:.25,hoursPerUnit:.03,materialPerUnit:16.4,kind:`vague`,rationale:`“Einbauort nach Vorgabe AG” with no stationing. Area is 20 m² under the base course — small, but the clause is a change-order door.`,rfi:`Bitte den Einbauort und die Verkehrsfreigabe (Belastungsklasse) vor Angebotsabgabe verbindlich angeben.`},{oz:`02.03.0020`,title:`Bordstein hoch 15/25 setzen`,longText:`Bordstein aus Beton, einschließlich Fundament und Rückenstütze.`,qty:480,unit:`m`,benchmark:38,laborShare:.5,hoursPerUnit:.22,materialPerUnit:14,kind:null,rationale:`Matches priced kerb lines within a few percent.`,rfi:``},{oz:`03.01.0010`,title:`Bedarfsposition: Kampfmittelräumung`,longText:`Eventualposition. Sondierung und Bergung nach Bedarf, Abrechnung nach Aufwand.`,qty:1,unit:`psch`,benchmark:4500,laborShare:.7,hoursPerUnit:40,materialPerUnit:800,kind:`gap`,rationale:`Provisional lump sum with no quantity driver. High chance it is either never called or explodes. Price it tactically, not as a firm cost.`,rfi:`Bitte den Erwartungswert (Sondierungsfläche, Fundwahrscheinlichkeit) angeben oder die Position als Bedarfsposition ohne Wertung kennzeichnen.`},{oz:`03.02.0060`,title:`Wasserhaltung, offene Haltung`,longText:`Wasserhaltung für die Bauzeit, Pumpen und Ableitung, nach Abstimmung mit dem AG.`,qty:12,unit:`Wo`,benchmark:null,laborShare:.6,hoursPerUnit:8,materialPerUnit:220,kind:`vague`,rationale:`No comparable in the 720 priced same-trade items (kein Vergleichswert). Scope (“nach Abstimmung”) cannot be priced firmly.`,rfi:`Bitte den Bemessungszufluss, die Ableitstelle und die maximale Betriebsdauer festlegen.`},{oz:`03.04.0020`,title:`Verkehrssicherung nach RSA`,longText:`Aufstellen, Vorhalten und Abbauen der Verkehrszeichen und Absperrungen.`,qty:16,unit:`Wo`,benchmark:640,laborShare:.45,hoursPerUnit:3.2,materialPerUnit:180,kind:null,rationale:`Weekly traffic management sits near the reference median.`,rfi:``},{oz:`04.01.0100`,title:`Hausanschluss DN 150 anbinden`,longText:`Anbindung bestehender Hausanschlüsse, Lage nach örtlichem Aufmaß.`,qty:2,unit:`St`,benchmark:890,laborShare:.65,hoursPerUnit:6,materialPerUnit:210,kind:`qty`,rationale:`Only 2 connections are billed. Street length and shaft count imply closer to 18–22. If the count is wrong, a high unit price captures the overrun.`,rfi:`Im LV sind 2 Hausanschlüsse ausgeschrieben. Nach Schachtanzahl und Straßenlänge erwarten wir eine deutlich höhere Stückzahl. Bitte die vollständige Anschlusszählung beifügen.`}],g={earth:46,pipe:52,pave:49,fitter:58,machine:95,material:1,agk:12,wg:8};function _(e){return e.startsWith(`02.`)?`pave`:e.startsWith(`04.`)||e.startsWith(`01.02`)||e.startsWith(`01.03`)?`pipe`:e.startsWith(`01.04`)||e.startsWith(`03.02`)||e.startsWith(`03.04`)?`fitter`:`earth`}var v={earth:`Earthworks crew`,pipe:`Pipe crew`,pave:`Paving crew`,fitter:`Fitter`};function y(e){return v[_(e)]}function b(e){return(1+e.agk/100)*(1+e.wg/100)}var x=1.12*1.08;function S(e,t,n=1){let r=b(t),i=t[_(e.oz)],a=1+(i/48-1)*1.6,o=1+(t.machine/95-1)*1.2;if(e.benchmark!=null&&e.kind!==`outlier`){let i=e.laborShare,s=_(e.oz)===`earth`||_(e.oz)===`pave`?.45:.2;return{ep:e.benchmark*((1-i)*(.55+.45*t.material)+i*((1-s)*a+s*o))*(r/x)*n,source:`benchmark`}}let s=_(e.oz)===`fitter`?.65:.3;return{ep:(e.hoursPerUnit*(1-s)*i+e.hoursPerUnit*s*t.machine+e.materialPerUnit*t.material)*r*n,source:`built-up`}}var C=2.72;function w(e,t,n){let r=n?.qty??e.qty;return S(e,t,n?.tactic??1).ep*r*C}function T(e,t,n={}){return e.reduce((e,r)=>e+w(r,t,n[r.oz]),0)}function E(e,t,n={}){return e.filter(e=>e.kind).map(e=>{let r=n[e.oz],i=r?.tactic??1,a=r?.qty??e.qty,{ep:o,source:s}=S(e,t,i),c=o*a*C,l=e.kind===`qty`?Math.abs(e.qty-a)*o*C+c*.12:c*.18;return{item:e,ep:o,total:c,leverage:e.kind===`outlier`?Math.max(c,12e3):Math.max(l,4e3),source:s}}).sort((e,t)=>t.leverage-e.leverage)}function D(e){return new Intl.NumberFormat(`de-DE`,{style:`currency`,currency:`EUR`,maximumFractionDigits:2}).format(e)}function O(e,t=2){return new Intl.NumberFormat(`de-DE`,{maximumFractionDigits:t,minimumFractionDigits:t}).format(e)}function k(e){return e!==`__proto__`&&e!==`constructor`&&e!==`prototype`}function A(e,t){let n=Object.create(null);if(e)for(let t of Object.keys(e))k(t)&&(n[t]=e[t]);if(t&&typeof t==`object`)for(let e of Object.keys(t))k(e)&&(n[e]=t[e]);return n}function j(e){if(!e)return Object.create(null);let t=Object.create(null);for(let n of Object.keys(e))k(n)&&(t[n]=e[n]);return t}var M=()=>{throw Error(`createServerOnlyFn() functions can only be called on the server!`)},N=(e,t)=>{let r=t||e||{};r.method===void 0&&(r.method=`GET`);let a=e=>N(void 0,{...r,validator:e,inputValidator:e});return Object.assign(e=>N(void 0,{...r,...e}),{options:r,middleware:e=>{let t=[...r.middleware||[]];e.forEach(e=>{i in e?e.options.middleware&&t.push(...e.options.middleware):t.push(e)});let n=N(void 0,{...r,middleware:t});return n[i]=!0,n},validator:a,inputValidator:a,handler:(...e)=>{let[t,i]=e,a={...r,extractedFn:t,serverFn:i},o=[...a.middleware||[],L(a)];return t.method=r.method,Object.assign(async e=>{let r=await P(o,`client`,{...t,...a,data:e?.data,headers:e?.headers,signal:e?.signal,fetch:e?.fetch,context:j()}),i=n(r.error);if(i)throw i;if(r.error)throw r.error;return r.result},{...t,method:r.method,__executeServer:async e=>{let n=M(),i=n.contextAfterGlobalMiddlewares;return await P(o,`server`,{...t,data:e.data,method:e.method??r.method,serverFnMeta:t.serverFnMeta,context:A(e.context,i),request:n.request}).then(e=>({result:e.result,error:e.error,context:e.sendContext}))}})}})};async function P(t,n,r){let i=F([...e()?.functionMiddleware||[],...t]);if(n===`server`){let e=M({throwIfNotFound:!1});e?.executedRequestMiddlewares&&(i=i.filter(t=>!e.executedRequestMiddlewares.has(t)))}let o=async e=>{let t=i.shift();if(!t)return e;try{let r=`validator`in t.options?t.options.validator:void 0;!r&&`inputValidator`in t.options&&(r=t.options.inputValidator),r&&n===`server`&&(e.data=await I(r,e.data));let i;if(n===`client`?`client`in t.options&&(i=t.options.client):`server`in t.options&&(i=t.options.server),i){let t=async(t={})=>{let n=await o({...e,...t,context:A(e.context,t.context),sendContext:A(e.sendContext,t.sendContext),headers:u(e.headers,t.headers),_callSiteFetch:e._callSiteFetch,fetch:e._callSiteFetch??t.fetch??e.fetch,result:t.result===void 0?t instanceof Response?t:e.result:t.result,error:t.error??e.error});if(n.error)throw n.error;return n},n=await i({...e,next:t});if(a(n))return{...e,error:n};if(n instanceof Response)return{...e,result:n};if(!n)throw Error(`User middleware returned undefined. You must call next() or return a result in your middlewares.`);return n}return o(e)}catch(t){return{...e,error:t}}};return o({...r,headers:r.headers||{},sendContext:r.sendContext||{},context:r.context||j(),_callSiteFetch:r.fetch})}function F(e,t=100){let n=new Set,r=[],i=(e,a)=>{if(a>t)throw Error(`Middleware nesting depth exceeded maximum of ${t}. Check for circular references.`);e.forEach(e=>{e.options.middleware&&i(e.options.middleware,a+1),n.has(e)||(n.add(e),r.push(e))})};return i(e,0),r}async function I(e,t){if(e==null)return{};if(`~standard`in e){let n=await e[`~standard`].validate(t);if(n.issues)throw Error(JSON.stringify(n.issues,void 0,2));return n.value}if(`parse`in e)return e.parse(t);if(typeof e==`function`)return e(t);throw Error(`Invalid validator type!`)}function L(e){return{"~types":void 0,options:{inputValidator:e.validator??e.inputValidator,client:async({next:t,sendContext:n,fetch:r,...i})=>{let a={...i,context:n,fetch:r};return t(await e.extractedFn?.(a))},server:async({next:t,...n})=>{let r=await e.serverFn?.(n);return t({...n,result:r})}}}}var R=N({method:`POST`}).handler(r(`f9146104ae1489df47f2adbe50d0ec594fa07218b0e2bf146360d54c815e8193`)),z=s(),B={outlier:`Speculative price`,vague:`Vague scope`,qty:`Quantity clash`,gap:`Provisional`};function V(){let[e,t]=(0,d.useState)(g),[n,r]=(0,d.useState)({}),[i,a]=(0,d.useState)({}),[o,s]=(0,d.useState)(null),[c,l]=(0,d.useState)(null),[u,_]=(0,d.useState)(`01.04.0080`),[v,b]=(0,d.useState)(!0),[x,C]=(0,d.useState)(!1),[k,A]=(0,d.useState)(0),[j,M]=(0,d.useState)(`Bereit zur Bereichsanalyse`),[N,P]=(0,d.useState)(null),F=(0,d.useMemo)(()=>[...h].sort((e,t)=>f(e.oz,t.oz)),[]),I=(0,d.useMemo)(()=>T(h,e,n),[e,n]),L=(0,d.useMemo)(()=>E(h,e,n),[e,n]),V=I-p,G=V/p*100;function K(e,n){t(t=>({...t,[e]:n}))}function q(e,t,n){r(r=>({...r,[e]:{qty:t,tactic:n}}))}async function J(){C(!0),P(null),A(0);let e=Math.ceil(F.length/20);try{for(let t=0;t<e;t+=1){let n=t*20+1,r=Math.min(F.length,(t+1)*20),i=(F[t*20]?.oz??``).split(`.`)[0]||`01`;M(`Analysiere Bereich ${i} – Positionen ${n}–${r} von ${F.length}…`),await new Promise(e=>window.setTimeout(e,220)),A(Math.round((t+1)/e*100))}M(`Bereichsanalyse abgeschlossen`)}catch{P(`Netzwerkabbruch oder Timeout. Bitte die Analyse erneut starten.`)}finally{C(!1)}}function Y(){let e=[`Bieterfragen-Katalog`,m,``,`Nach VOB/A bitten wir um Klarstellung der folgenden Positionen vor Submission.`,``];L.forEach((t,n)=>{let r=i[t.item.oz]||t.item.rfi;r&&(e.push(`${n+1}. Pos. ${t.item.oz} — ${t.item.title}`),e.push(r),e.push(``))});let t=new Blob([e.join(`
`)],{type:`text/plain;charset=utf-8`}),n=document.createElement(`a`);n.href=URL.createObjectURL(t),n.download=`Bieterfragen-Katalog.txt`,n.click(),URL.revokeObjectURL(n.href)}async function X(e,t,n,r,i){s(e),l(null);try{let o=await R({data:{oz:e,title:t,longText:n,rationale:r,draft:i}});o.ok?a(t=>({...t,[e]:o.text})):l(o.error)}catch{l(`Could not reach the model. The drafted question stays as written.`)}finally{s(null)}}return(0,z.jsxs)(`main`,{className:`mx-auto max-w-6xl px-4 py-8 sm:px-6`,children:[(0,z.jsxs)(`header`,{className:`mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between`,children:[(0,z.jsxs)(`div`,{children:[(0,z.jsx)(`p`,{className:`font-mono text-xs tracking-widest text-muted uppercase`,children:`Estimator desk`}),(0,z.jsx)(`h1`,{className:`mt-1 text-3xl font-medium tracking-tight`,children:`Bid & Risk`}),(0,z.jsx)(`p`,{className:`mt-2 max-w-xl text-muted`,children:`It reads a construction tender, finds the lines that will cost the contractor money, and drafts the clarification letter.`})]}),(0,z.jsx)(`button`,{type:`button`,onClick:Y,className:`h-11 rounded-full bg-accent px-5 text-sm font-medium text-surface`,children:`Export Bieterfragen`})]}),(0,z.jsxs)(`section`,{className:`mb-6 rounded-xl border border-line bg-surface px-4 py-3`,children:[(0,z.jsxs)(`div`,{className:`mb-2 flex items-center justify-between gap-3`,children:[(0,z.jsxs)(`div`,{className:`min-w-0`,children:[(0,z.jsx)(`p`,{className:`font-mono text-xs tracking-widest text-muted uppercase`,children:`KI-Batch-Fortschritt`}),(0,z.jsx)(`p`,{className:`mt-1 text-sm overflow-wrap-anywhere`,children:j})]}),(0,z.jsx)(`button`,{type:`button`,className:`shrink-0 h-9 rounded-lg border border-line px-3 text-sm`,disabled:x,onClick:J,children:x?`Analysiert…`:`Analyse starten / Retry`})]}),(0,z.jsx)(`div`,{className:`h-2 overflow-hidden rounded-full bg-line`,role:`progressbar`,"aria-valuemin":0,"aria-valuemax":100,"aria-valuenow":k,children:(0,z.jsx)(`div`,{className:`h-full bg-accent transition-[width]`,style:{width:`${k}%`}})}),N&&(0,z.jsx)(`p`,{className:`mt-2 rounded-lg bg-accent-soft px-3 py-2 text-sm text-warn overflow-wrap-anywhere`,children:N})]}),(0,z.jsxs)(`section`,{className:`mb-6 grid gap-3 sm:grid-cols-3`,children:[(0,z.jsx)(U,{label:`Our estimate`,value:D(I),hint:`Scaled from the worked slice to the 248-item twin`}),(0,z.jsx)(U,{label:`Submitted bid`,value:v?D(p):`—`,hint:`StBALV23040 · same bill`}),(0,z.jsx)(U,{label:`Gap`,value:v?`${G>=0?`+`:``}${O(G,1)} %`:`—`,hint:v?D(V):`Reveal to compare`})]}),(0,z.jsxs)(`section`,{className:`mb-6 grid gap-4 lg:grid-cols-[280px_1fr]`,children:[(0,z.jsxs)(`aside`,{className:`rounded-xl border border-line bg-surface p-4`,children:[(0,z.jsx)(`p`,{className:`mb-3 font-mono text-xs tracking-widest text-muted uppercase`,children:`Crew & plant`}),(0,z.jsx)(W,{label:`Earthworks €/h`,min:32,max:78,step:1,value:e.earth,onChange:e=>K(`earth`,e)}),(0,z.jsx)(W,{label:`Pipe crew €/h`,min:32,max:78,step:1,value:e.pipe,onChange:e=>K(`pipe`,e)}),(0,z.jsx)(W,{label:`Paving €/h`,min:32,max:78,step:1,value:e.pave,onChange:e=>K(`pave`,e)}),(0,z.jsx)(W,{label:`Fitter €/h`,min:32,max:86,step:1,value:e.fitter,onChange:e=>K(`fitter`,e)}),(0,z.jsx)(W,{label:`Excavator €/h`,min:55,max:160,step:1,value:e.machine,onChange:e=>K(`machine`,e)}),(0,z.jsx)(W,{label:`Material index`,min:.8,max:1.4,step:.05,value:e.material,onChange:e=>K(`material`,e)}),(0,z.jsx)(W,{label:`AGK %`,min:6,max:22,step:1,value:e.agk,onChange:e=>K(`agk`,e)}),(0,z.jsx)(W,{label:`Wagnis & Gewinn %`,min:2,max:16,step:1,value:e.wg,onChange:e=>K(`wg`,e)}),(0,z.jsx)(`button`,{type:`button`,className:`mt-1 h-10 w-full rounded-lg border border-line text-sm`,onClick:()=>b(e=>!e),children:v?`Hide real bid`:`Reveal real bid`}),(0,z.jsx)(`p`,{className:`mt-3 text-xs leading-relaxed text-muted`,children:`A pipe layer is not an excavator operator, and the machine is not the wage. Move only the crew that does the work.`})]}),(0,z.jsxs)(`div`,{className:`overflow-hidden rounded-xl border border-line bg-surface`,children:[(0,z.jsxs)(`div`,{className:`flex items-baseline justify-between border-b border-line px-4 py-3`,children:[(0,z.jsx)(`h2`,{className:`text-sm font-medium`,children:`Findings by euro leverage`}),(0,z.jsxs)(`span`,{className:`font-mono text-xs text-muted`,children:[L.length,` flagged`]})]}),(0,z.jsx)(`ul`,{children:L.map(e=>{let t=u===e.item.oz;return(0,z.jsxs)(`li`,{className:`border-b border-line last:border-b-0`,children:[(0,z.jsxs)(`button`,{type:`button`,className:`flex w-full items-start gap-3 px-4 py-3 text-left`,onClick:()=>_(t?null:e.item.oz),children:[(0,z.jsx)(`span`,{className:`mt-0.5 shrink-0 rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent`,children:B[e.item.kind??`gap`]}),(0,z.jsxs)(`span`,{className:`min-w-0 flex-1`,children:[(0,z.jsxs)(`span`,{className:`block font-medium`,children:[e.item.oz,` · `,e.item.title]}),(0,z.jsx)(`span`,{className:`block text-sm text-muted overflow-wrap-anywhere`,children:e.item.rationale})]}),(0,z.jsx)(`span`,{className:`shrink-0 text-right font-mono text-sm`,children:e.source===`benchmark`?D(e.total):`kein Vergleichswert`})]}),t&&(0,z.jsxs)(`div`,{className:`space-y-2 px-4 pb-4 text-sm`,children:[(0,z.jsx)(`p`,{className:`text-muted overflow-wrap-anywhere`,children:e.item.longText}),(0,z.jsx)(`p`,{className:`text-muted`,children:y(e.item.oz)}),e.item.preambles&&e.item.preambles.length>0&&(0,z.jsx)(H,{title:`Vorbemerkungen`,items:e.item.preambles}),e.item.remarks&&e.item.remarks.length>0&&(0,z.jsx)(H,{title:`Bereichs-Remarks`,items:e.item.remarks}),(0,z.jsxs)(`div`,{className:`flex flex-wrap items-end gap-3`,children:[(0,z.jsxs)(`label`,{className:`text-xs text-muted`,children:[`Qty used`,(0,z.jsx)(`input`,{className:`mt-1 block h-10 w-28 rounded-lg border border-line bg-bg px-2 font-mono text-sm text-ink`,type:`number`,min:0,value:n[e.item.oz]?.qty??e.item.qty,onChange:t=>q(e.item.oz,Number(t.target.value),n[e.item.oz]?.tactic??1)})]}),(0,z.jsxs)(`label`,{className:`text-xs text-muted`,children:[`Tactic`,(0,z.jsxs)(`select`,{className:`mt-1 block h-10 rounded-lg border border-line bg-bg px-2 text-sm text-ink`,value:n[e.item.oz]?.tactic??1,onChange:t=>q(e.item.oz,n[e.item.oz]?.qty??e.item.qty,Number(t.target.value)),children:[(0,z.jsx)(`option`,{value:.7,children:`Low — may not be called`}),(0,z.jsx)(`option`,{value:1,children:`As calculated`}),(0,z.jsx)(`option`,{value:1.25,children:`High — quantity will grow`})]})]})]}),(0,z.jsxs)(`p`,{children:[`Billed `,O(e.item.qty,0),` `,e.item.unit,e.item.benchmark==null?` · kein Vergleichswert`:` · observed ${D(e.item.benchmark)}`,` · `,`now `,D(e.ep),`/`,e.item.unit]}),(0,z.jsx)(`p`,{className:`rounded-lg bg-bg px-3 py-2 text-ink`,children:i[e.item.oz]||e.item.rfi}),e.item.rfi&&(0,z.jsx)(`button`,{type:`button`,className:`h-10 rounded-lg border border-line px-3 text-sm`,disabled:o===e.item.oz,onClick:()=>X(e.item.oz,e.item.title,e.item.longText,e.item.rationale,i[e.item.oz]||e.item.rfi),children:o===e.item.oz?`Writing…`:`Sharpen this question`}),c&&(0,z.jsx)(`p`,{className:`text-xs text-warn`,children:c})]})]},e.item.oz)})})]})]}),(0,z.jsx)(`section`,{className:`overflow-x-auto rounded-xl border border-line bg-surface`,children:(0,z.jsxs)(`table`,{className:`w-full min-w-[640px] text-left text-sm`,children:[(0,z.jsx)(`thead`,{className:`border-b border-line font-mono text-xs tracking-wide text-muted uppercase`,children:(0,z.jsxs)(`tr`,{children:[(0,z.jsx)(`th`,{className:`px-4 py-2 font-medium`,children:`OZ`}),(0,z.jsx)(`th`,{className:`px-4 py-2 font-medium`,children:`Position`}),(0,z.jsx)(`th`,{className:`px-4 py-2 font-medium`,children:`Qty`}),(0,z.jsx)(`th`,{className:`px-4 py-2 font-medium`,children:`EP`}),(0,z.jsx)(`th`,{className:`px-4 py-2 font-medium`,children:`Source`}),(0,z.jsx)(`th`,{className:`px-4 py-2 text-right font-medium`,children:`Total`})]})}),(0,z.jsx)(`tbody`,{children:F.map(t=>{let r=n[t.oz],i=S(t,e,r?.tactic??1);return(0,z.jsxs)(`tr`,{className:`border-b border-line last:border-b-0`,children:[(0,z.jsx)(`td`,{className:`px-4 py-2 font-mono text-xs`,children:t.oz}),(0,z.jsx)(`td`,{className:`px-4 py-2`,children:t.title}),(0,z.jsxs)(`td`,{className:`px-4 py-2 font-mono text-xs`,children:[O(r?.qty??t.qty,0),` `,t.unit]}),(0,z.jsx)(`td`,{className:`px-4 py-2 font-mono text-xs`,children:D(i.ep)}),(0,z.jsxs)(`td`,{className:`px-4 py-2 text-muted`,children:[i.source===`benchmark`?`observed`:`built-up`,` · `,y(t.oz)]}),(0,z.jsx)(`td`,{className:`px-4 py-2 text-right font-mono text-xs`,children:D(w(t,e,r))})]},t.oz)})})]})})]})}function H({title:e,items:t}){return(0,z.jsxs)(`details`,{className:`rounded-lg border border-line bg-bg px-3 py-2`,children:[(0,z.jsx)(`summary`,{className:`cursor-pointer text-sm font-medium`,children:e}),(0,z.jsx)(`div`,{className:`mt-2 space-y-2`,children:t.map((t,n)=>(0,z.jsx)(`p`,{className:`text-xs leading-relaxed text-muted overflow-wrap-anywhere`,children:t},`${e}-${n}`))})]})}function U({label:e,value:t,hint:n}){return(0,z.jsxs)(`div`,{className:`rounded-xl border border-line bg-surface px-4 py-3`,children:[(0,z.jsx)(`p`,{className:`font-mono text-xs tracking-widest text-muted uppercase`,children:e}),(0,z.jsx)(`p`,{className:`mt-1 text-2xl font-medium tracking-tight`,children:t}),(0,z.jsx)(`p`,{className:`mt-1 text-xs text-muted overflow-wrap-anywhere`,children:n})]})}function W({label:e,min:t,max:n,step:r,value:i,onChange:a}){return(0,z.jsxs)(`label`,{className:`mb-3 block text-sm`,children:[(0,z.jsxs)(`span`,{className:`mb-1 flex justify-between`,children:[(0,z.jsx)(`span`,{children:e}),(0,z.jsx)(`span`,{className:`font-mono`,children:Number(i.toFixed(2))})]}),(0,z.jsx)(`input`,{className:`w-full accent-accent`,type:`range`,min:t,max:n,step:r,value:i,onChange:e=>a(Number(e.target.value))})]})}export{V as component};
````

## `frontend_demo/.vercel/output/static/assets/styles-CMHoM8DC.css`
````css
/*! tailwindcss v4.3.3 | MIT License | https://tailwindcss.com */
@layer properties{@supports (((-webkit-hyphens:none)) and (not (margin-trim:inline))) or ((-moz-orient:inline) and (not (color:rgb(from red r g b)))){*,:before,:after,::backdrop{--tw-space-y-reverse:0;--tw-border-style:solid;--tw-leading:initial;--tw-font-weight:initial;--tw-tracking:initial}}}@layer theme{:root,:host{--font-sans:"IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;--font-mono:"IBM Plex Mono", ui-monospace, monospace;--color-red-500:oklch(63.7% .237 25.331);--color-zinc-50:oklch(98.5% 0 none);--color-zinc-400:oklch(70.5% .015 286.067);--color-zinc-500:oklch(55.2% .016 285.938);--color-zinc-900:oklch(21% .006 285.885);--color-zinc-950:oklch(14.1% .005 285.823);--color-neutral-100:oklch(97% 0 none);--color-neutral-300:oklch(87% 0 none);--color-neutral-700:oklch(37.1% 0 none);--color-neutral-900:oklch(20.5% 0 none);--color-black:#000;--color-white:#fff;--spacing:.25rem;--container-sm:24rem;--container-md:28rem;--container-xl:36rem;--container-6xl:72rem;--text-xs:.75rem;--text-xs--line-height:calc(1 / .75);--text-sm:.875rem;--text-sm--line-height:calc(1.25 / .875);--text-lg:1.125rem;--text-lg--line-height:calc(1.75 / 1.125);--text-2xl:1.5rem;--text-2xl--line-height:calc(2 / 1.5);--text-3xl:1.875rem;--text-3xl--line-height:calc(2.25 / 1.875);--font-weight-medium:500;--font-weight-semibold:600;--tracking-tight:-.025em;--tracking-wide:.025em;--tracking-widest:.1em;--leading-relaxed:1.625;--radius-md:.375rem;--radius-lg:.5rem;--radius-xl:.75rem;--default-transition-duration:.15s;--default-transition-timing-function:cubic-bezier(.4, 0, .2, 1);--default-font-family:var(--font-sans);--default-mono-font-family:var(--font-mono);--color-bg:#f3efe6;--color-surface:#fffcf7;--color-ink:#1c1915;--color-muted:#6e675e;--color-line:#e3d9cc;--color-accent:#9a3412;--color-accent-soft:#f3e4d6;--color-warn:#92400e}}@layer base{*,:after,:before,::backdrop{box-sizing:border-box;border:0 solid;margin:0;padding:0}::file-selector-button{box-sizing:border-box;border:0 solid;margin:0;padding:0}html,:host{-webkit-text-size-adjust:100%;tab-size:4;line-height:1.5;font-family:var(--default-font-family,-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji");font-feature-settings:var(--default-font-feature-settings,normal);font-variation-settings:var(--default-font-variation-settings,normal);-webkit-tap-highlight-color:transparent}hr{height:0;color:inherit;border-top-width:1px}abbr:where([title]){-webkit-text-decoration:underline dotted;text-decoration:underline dotted}h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}a{color:inherit;-webkit-text-decoration:inherit;-webkit-text-decoration:inherit;-webkit-text-decoration:inherit;-webkit-text-decoration:inherit;text-decoration:inherit}b,strong{font-weight:bolder}code,kbd,samp,pre{font-family:var(--default-mono-font-family,ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);font-feature-settings:var(--default-mono-font-feature-settings,normal);font-variation-settings:var(--default-mono-font-variation-settings,normal);font-size:1em}small{font-size:80%}sub,sup{vertical-align:baseline;font-size:75%;line-height:0;position:relative}sub{bottom:-.25em}sup{top:-.5em}table{text-indent:0;border-color:inherit;border-collapse:collapse}:-moz-focusring:where(:not(iframe)){outline:auto}progress{vertical-align:baseline}summary{display:list-item}ol,ul,menu{list-style:none}img,svg,video,canvas,audio,iframe,embed,object{vertical-align:middle;display:block}img,video{max-width:100%;height:auto}button,input,select,optgroup,textarea{font:inherit;font-feature-settings:inherit;font-variation-settings:inherit;letter-spacing:inherit;color:inherit;opacity:1;background-color:#0000;border-radius:0}::file-selector-button{font:inherit;font-feature-settings:inherit;font-variation-settings:inherit;letter-spacing:inherit;color:inherit;opacity:1;background-color:#0000;border-radius:0}:where(select:is([multiple],[size])) optgroup{font-weight:bolder}:where(select:is([multiple],[size])) optgroup option{padding-inline-start:20px}::file-selector-button{margin-inline-end:4px}::placeholder{opacity:1}@supports (not ((-webkit-appearance:-apple-pay-button))) or (contain-intrinsic-size:1px){::placeholder{color:currentColor}@supports (color:color-mix(in lab, red, red)){::placeholder{color:color-mix(in oklab, currentcolor 50%, transparent)}}}textarea{resize:vertical}::-webkit-search-decoration{-webkit-appearance:none}::-webkit-date-and-time-value{min-height:1lh;text-align:inherit}::-webkit-datetime-edit{display:inline-flex}::-webkit-datetime-edit-fields-wrapper{padding:0}::-webkit-datetime-edit{padding-block:0}::-webkit-datetime-edit-year-field{padding-block:0}::-webkit-datetime-edit-month-field{padding-block:0}::-webkit-datetime-edit-day-field{padding-block:0}::-webkit-datetime-edit-hour-field{padding-block:0}::-webkit-datetime-edit-minute-field{padding-block:0}::-webkit-datetime-edit-second-field{padding-block:0}::-webkit-datetime-edit-millisecond-field{padding-block:0}::-webkit-datetime-edit-meridiem-field{padding-block:0}::-webkit-calendar-picker-indicator{line-height:1}:-moz-ui-invalid{box-shadow:none}button,input:where([type=button],[type=reset],[type=submit]){appearance:button}::file-selector-button{appearance:button}::-webkit-inner-spin-button{height:auto}::-webkit-outer-spin-button{height:auto}[hidden]:where(:not([hidden=until-found])){display:none!important}html,body{background:var(--color-bg);color:var(--color-ink)}button:not(:disabled),[role=button]:not(:disabled){cursor:pointer}body{font-family:var(--font-sans);line-height:1.5}p,span,td,th,li,details,summary{overflow-wrap:break-word;word-break:normal}.overflow-wrap-anywhere{overflow-wrap:anywhere}}@layer components;@layer utilities{.visible{visibility:visible}.absolute{position:absolute}.fixed{position:fixed}.relative{position:relative}.static{position:static}.mx-auto{margin-inline:auto}.mt-0\.5{margin-top:calc(var(--spacing) * .5)}.mt-1{margin-top:var(--spacing)}.mt-2{margin-top:calc(var(--spacing) * 2)}.mt-3{margin-top:calc(var(--spacing) * 3)}.mb-1{margin-bottom:var(--spacing)}.mb-2{margin-bottom:calc(var(--spacing) * 2)}.mb-3{margin-bottom:calc(var(--spacing) * 3)}.mb-6{margin-bottom:calc(var(--spacing) * 6)}.mb-8{margin-bottom:calc(var(--spacing) * 8)}.block{display:block}.flex{display:flex}.grid{display:grid}.inline{display:inline}.table{display:table}.size-10{width:calc(var(--spacing) * 10);height:calc(var(--spacing) * 10)}.h-2{height:calc(var(--spacing) * 2)}.h-8{height:calc(var(--spacing) * 8)}.h-9{height:calc(var(--spacing) * 9)}.h-10{height:calc(var(--spacing) * 10)}.h-11{height:calc(var(--spacing) * 11)}.h-full{height:100%}.min-h-screen{min-height:100vh}.w-8{width:calc(var(--spacing) * 8)}.w-28{width:calc(var(--spacing) * 28)}.w-full{width:100%}.max-w-6xl{max-width:var(--container-6xl)}.max-w-md{max-width:var(--container-md)}.max-w-sm{max-width:var(--container-sm)}.max-w-xl{max-width:var(--container-xl)}.min-w-0{min-width:0}.min-w-\[640px\]{min-width:640px}.flex-1{flex:1}.shrink-0{flex-shrink:0}.grow{flex-grow:1}.cursor-pointer{cursor:pointer}.flex-col{flex-direction:column}.flex-wrap{flex-wrap:wrap}.place-items-center{place-items:center}.items-baseline{align-items:baseline}.items-center{align-items:center}.items-end{align-items:flex-end}.items-start{align-items:flex-start}.justify-between{justify-content:space-between}.justify-center{justify-content:center}.gap-2{gap:calc(var(--spacing) * 2)}.gap-3{gap:calc(var(--spacing) * 3)}.gap-4{gap:calc(var(--spacing) * 4)}:where(.space-y-2>:not(:last-child)){--tw-space-y-reverse:0;margin-block-start:calc(calc(var(--spacing) * 2) * var(--tw-space-y-reverse));margin-block-end:calc(calc(var(--spacing) * 2) * calc(1 - var(--tw-space-y-reverse)))}.overflow-hidden{overflow:hidden}.overflow-x-auto{overflow-x:auto}.rounded-full{border-radius:2147483647px}.rounded-lg{border-radius:var(--radius-lg)}.rounded-md{border-radius:var(--radius-md)}.rounded-xl{border-radius:var(--radius-xl)}.border{border-style:var(--tw-border-style);border-width:1px}.border-b{border-bottom-style:var(--tw-border-style);border-bottom-width:1px}.border-line{border-color:var(--color-line)}.border-neutral-300{border-color:var(--color-neutral-300)}.bg-accent{background-color:var(--color-accent)}.bg-accent-soft{background-color:var(--color-accent-soft)}.bg-bg{background-color:var(--color-bg)}.bg-black\/10{background-color:#0000001a}@supports (color:color-mix(in lab, red, red)){.bg-black\/10{background-color:color-mix(in oklab, var(--color-black) 10%, transparent)}}.bg-line{background-color:var(--color-line)}.bg-surface{background-color:var(--color-surface)}.bg-zinc-50{background-color:var(--color-zinc-50)}.object-cover{object-fit:cover}.p-4{padding:calc(var(--spacing) * 4)}.px-2{padding-inline:calc(var(--spacing) * 2)}.px-3{padding-inline:calc(var(--spacing) * 3)}.px-4{padding-inline:calc(var(--spacing) * 4)}.px-5{padding-inline:calc(var(--spacing) * 5)}.px-6{padding-inline:calc(var(--spacing) * 6)}.py-0\.5{padding-block:calc(var(--spacing) * .5)}.py-2{padding-block:calc(var(--spacing) * 2)}.py-3{padding-block:calc(var(--spacing) * 3)}.py-8{padding-block:calc(var(--spacing) * 8)}.pb-4{padding-bottom:calc(var(--spacing) * 4)}.text-center{text-align:center}.text-left{text-align:left}.text-right{text-align:right}.font-mono{font-family:var(--font-mono)}.text-2xl{font-size:var(--text-2xl);line-height:var(--tw-leading,var(--text-2xl--line-height))}.text-3xl{font-size:var(--text-3xl);line-height:var(--tw-leading,var(--text-3xl--line-height))}.text-lg{font-size:var(--text-lg);line-height:var(--tw-leading,var(--text-lg--line-height))}.text-sm{font-size:var(--text-sm);line-height:var(--tw-leading,var(--text-sm--line-height))}.text-xs{font-size:var(--text-xs);line-height:var(--tw-leading,var(--text-xs--line-height))}.leading-relaxed{--tw-leading:var(--leading-relaxed);line-height:var(--leading-relaxed)}.font-medium{--tw-font-weight:var(--font-weight-medium);font-weight:var(--font-weight-medium)}.font-semibold{--tw-font-weight:var(--font-weight-semibold);font-weight:var(--font-weight-semibold)}.tracking-tight{--tw-tracking:var(--tracking-tight);letter-spacing:var(--tracking-tight)}.tracking-wide{--tw-tracking:var(--tracking-wide);letter-spacing:var(--tracking-wide)}.tracking-widest{--tw-tracking:var(--tracking-widest);letter-spacing:var(--tracking-widest)}.break-words{overflow-wrap:break-word}.text-accent{color:var(--color-accent)}.text-ink{color:var(--color-ink)}.text-muted{color:var(--color-muted)}.text-red-500{color:var(--color-red-500)}.text-surface{color:var(--color-surface)}.text-warn{color:var(--color-warn)}.text-zinc-500{color:var(--color-zinc-500)}.text-zinc-900{color:var(--color-zinc-900)}.uppercase{text-transform:uppercase}.underline-offset-4{text-underline-offset:4px}.accent-accent{accent-color:var(--color-accent)}.opacity-70{opacity:.7}.transition-\[width\]{transition-property:width;transition-timing-function:var(--tw-ease,var(--default-transition-timing-function));transition-duration:var(--tw-duration,var(--default-transition-duration))}.last\:border-b-0:last-child{border-bottom-style:var(--tw-border-style);border-bottom-width:0}@media (hover:hover){.hover\:bg-neutral-100:hover{background-color:var(--color-neutral-100)}.hover\:underline:hover{text-decoration-line:underline}}.disabled\:cursor-wait:disabled{cursor:wait}.disabled\:no-underline:disabled{text-decoration-line:none}@media (width>=40rem){.sm\:grid-cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}.sm\:flex-row{flex-direction:row}.sm\:items-end{align-items:flex-end}.sm\:justify-between{justify-content:space-between}.sm\:px-6{padding-inline:calc(var(--spacing) * 6)}}@media (width>=64rem){.lg\:grid-cols-\[280px_1fr\]{grid-template-columns:280px 1fr}}@media (prefers-color-scheme:dark){.dark\:border-neutral-700{border-color:var(--color-neutral-700)}.dark\:bg-white\/20{background-color:#fff3}@supports (color:color-mix(in lab, red, red)){.dark\:bg-white\/20{background-color:color-mix(in oklab, var(--color-white) 20%, transparent)}}.dark\:bg-zinc-950{background-color:var(--color-zinc-950)}.dark\:text-zinc-50{color:var(--color-zinc-50)}.dark\:text-zinc-400{color:var(--color-zinc-400)}@media (hover:hover){.dark\:hover\:bg-neutral-900:hover{background-color:var(--color-neutral-900)}}}}@property --tw-space-y-reverse{syntax:"*";inherits:false;initial-value:0}@property --tw-border-style{syntax:"*";inherits:false;initial-value:solid}@property --tw-leading{syntax:"*";inherits:false}@property --tw-font-weight{syntax:"*";inherits:false}@property --tw-tracking{syntax:"*";inherits:false}

````

## `frontend_demo/.vercel/output/static/favicon.svg`
````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#1c1915"/>
  <path d="M8 22V10h3.2l4.8 7.4L20.8 10H24v12h-2.6v-7.2L17.2 22h-2.4l-4.2-7.2V22H8z" fill="#f3efe6"/>
</svg>

````

## `frontend_demo/eslint.config.mjs`
````mjs
import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

/** Flat ESLint config for the TanStack Start app-builder template. */
export default tseslint.config(
  {
    ignores: [
      "dist/**",
      ".output/**",
      ".vercel/**",
      ".nitro/**",
      "node_modules/**",
      "src/routeTree.gen.ts",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  // Disable rules that conflict with Prettier formatting.
  prettier,
);

````

## `frontend_demo/migrations/auth/0001_auth.sql`
````sql
-- Better Auth schema (identity + sessions for "Sign in with Grok").
--
-- Generated by the Better Auth CLI for its Postgres adapter — DO NOT EDIT by
-- hand. `@/lib/auth/server` runs Better Auth against these tables when
-- DATABASE_URL is set. The columns are camelCase and MUST stay double-quoted so
-- Postgres preserves the case Better Auth queries by.
--
-- Migrations in this folder are the single source of truth for your schema. They
-- apply to Neon during the Vercel build (`npm run build`) and to the local
-- PGLite fallback automatically on startup, so dev matches production. Applied
-- files are recorded by name in `_migrations` and NEVER run again.
--
-- Put YOUR app's schema in NEW ordered files (0002_*.sql, 0003_*.sql, …), never
-- in this one. For app tables, prefer snake_case and give per-user tables a
-- `user_id TEXT NOT NULL` column (TEXT, not UUID — the preview dev user id is
-- the string 'dev-user'), then scope every query to the authenticated user
-- server-side (see the `neon` + `auth` skills and src/lib/auth/verify.server.ts).

create table if not exists "user" (
  "id" text not null primary key,
  "name" text not null,
  "email" text not null unique,
  "emailVerified" boolean not null,
  "image" text,
  "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
  "updatedAt" timestamptz default CURRENT_TIMESTAMP not null
);

create table if not exists "session" (
  "id" text not null primary key,
  "expiresAt" timestamptz not null,
  "token" text not null unique,
  "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
  "updatedAt" timestamptz not null,
  "ipAddress" text,
  "userAgent" text,
  "userId" text not null references "user" ("id") on delete cascade
);

create table if not exists "account" (
  "id" text not null primary key,
  "accountId" text not null,
  "providerId" text not null,
  "userId" text not null references "user" ("id") on delete cascade,
  "accessToken" text,
  "refreshToken" text,
  "idToken" text,
  "accessTokenExpiresAt" timestamptz,
  "refreshTokenExpiresAt" timestamptz,
  "scope" text,
  "password" text,
  "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
  "updatedAt" timestamptz not null
);

create table if not exists "verification" (
  "id" text not null primary key,
  "identifier" text not null,
  "value" text not null,
  "expiresAt" timestamptz not null,
  "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
  "updatedAt" timestamptz default CURRENT_TIMESTAMP not null
);

create index if not exists "session_userId_idx" on "session" ("userId");
create index if not exists "account_userId_idx" on "account" ("userId");
create index if not exists "verification_identifier_idx" on "verification" ("identifier");

````

## `frontend_demo/package.json`
````json
{
  "name": "app-builder-workspace",
  "private": true,
  "sideEffects": false,
  "type": "module",
  "overrides": {
    "nf3": "0.3.17"
  },
  "scripts": {
    "dev": "vite dev --host 127.0.0.1 --port 3000",
    "build": "vite build",
    "db:migrate": "node scripts/migrate.mjs",
    "build:dev": "vite build --mode development",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "lint": "eslint .",
    "format": "prettier --write ."
  },
  "dependencies": {
    "@electric-sql/pglite": "^0.5.4",
    "@hookform/resolvers": "^5.7.0",
    "@radix-ui/react-accordion": "^1.2.12",
    "@radix-ui/react-alert-dialog": "^1.1.15",
    "@radix-ui/react-avatar": "^1.1.11",
    "@radix-ui/react-checkbox": "^1.3.3",
    "@radix-ui/react-collapsible": "^1.1.12",
    "@radix-ui/react-dialog": "^1.1.15",
    "@radix-ui/react-dropdown-menu": "^2.1.16",
    "@radix-ui/react-label": "^2.1.8",
    "@radix-ui/react-popover": "^1.1.15",
    "@radix-ui/react-progress": "^1.1.8",
    "@radix-ui/react-radio-group": "^1.3.8",
    "@radix-ui/react-scroll-area": "^1.2.10",
    "@radix-ui/react-select": "^2.2.6",
    "@radix-ui/react-separator": "^1.1.8",
    "@radix-ui/react-slider": "^1.3.6",
    "@radix-ui/react-slot": "^1.2.4",
    "@radix-ui/react-switch": "^1.2.6",
    "@radix-ui/react-tabs": "^1.1.13",
    "@radix-ui/react-toggle": "^1.1.10",
    "@radix-ui/react-toggle-group": "^1.1.11",
    "@radix-ui/react-tooltip": "^1.2.8",
    "@tailwindcss/vite": "^4.3.0",
    "@tanstack/react-query": "^5.101.0",
    "@tanstack/react-router": "^1.170.0",
    "@tanstack/react-start": "^1.168.60",
    "@tanstack/react-table": "^8.21.0",
    "@tanstack/router-plugin": "^1.168.0",
    "@vitejs/plugin-react": "^5.2.0",
    "better-auth": "~1.6.30",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "cmdk": "^1.1.1",
    "date-fns": "^4.0.0",
    "jose": "6.2.9",
    "kysely": "^0.28.5",
    "lightningcss": "^1.28.0",
    "lucide-react": "^0.510.0",
    "nitro": "3.0.260610-beta",
    "pg": "^8.16.3",
    "react": "^19.2.0",
    "react-day-picker": "^9.14.0",
    "react-dom": "^19.2.0",
    "react-hook-form": "^7.54.0",
    "react-resizable-panels": "^4.6.5",
    "recharts": "^2.13.0",
    "sonner": "^2.0.7",
    "tailwind-merge": "^3.5.0",
    "tailwindcss": "^4.3.0",
    "tw-animate-css": "^1.3.4",
    "typescript": "^5.7.0",
    "vaul": "^1.1.2",
    "vite": "^8.2.0",
    "zod": "^4.4.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.20.0",
    "@types/node": "^22.16.5",
    "@types/pg": "^8.11.10",
    "@types/react": "^19.2.0",
    "@types/react-dom": "^19.2.0",
    "eslint": "^9.20.0",
    "eslint-config-prettier": "^10.1.1",
    "eslint-plugin-prettier": "^5.2.6",
    "eslint-plugin-react-hooks": "^5.2.0",
    "eslint-plugin-react-refresh": "^0.4.20",
    "globals": "^15.15.0",
    "playwright": "^1.62.0",
    "prettier": "^3.4.0",
    "typescript-eslint": "^8.56.1"
  }
}

````

## `frontend_demo/public/favicon.svg`
````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#1c1915"/>
  <path d="M8 22V10h3.2l4.8 7.4L20.8 10H24v12h-2.6v-7.2L17.2 22h-2.4l-4.2-7.2V22H8z" fill="#f3efe6"/>
</svg>

````

## `frontend_demo/scripts/install-page.html`
````html
<!DOCTYPE html>
<html lang="en" class="device-desktop">
  <head>
    <meta charset="utf-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1, viewport-fit=cover"
    />
    <meta name="color-scheme" content="dark" />
    <meta name="theme-color" content="#000000" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black" />
    <meta name="apple-mobile-web-app-title" content="{{APP_NAME}}" />
    <title>Add {{APP_NAME}} to your Home Screen</title>
    <link rel="manifest" href="/__grok/manifest.webmanifest" />
    <link rel="apple-touch-icon" href="/__grok/icon-180.png" />
    <link rel="stylesheet" href="/__grok/install/styles.css" />
    <script>
      (function () {
        var ua = navigator.userAgent || "";
        var touch = navigator.maxTouchPoints || 0;
        var isiPad = /iPad/.test(ua) || (/Macintosh/.test(ua) && touch > 1);
        var isiPhone = /iPhone|iPod/.test(ua);
        var isIOS = isiPhone || isiPad;
        var isAndroid = /Android/i.test(ua);
        var isAndroidPhone = isAndroid && /Mobile/i.test(ua);
        var isAndroidTablet = isAndroid && !/Mobile/i.test(ua);
        var minSide = Math.min(screen.width || 0, screen.height || 0);
        var maxSide = Math.max(screen.width || 0, screen.height || 0);

        var type = "desktop";
        if (isiPhone) type = "phone";
        else if (isiPad || isAndroidTablet) type = "tablet";
        else if (isAndroidPhone) type = "phone";
        else if (touch > 0 && minSide > 0 && minSide <= 500) type = "phone";
        else if (touch > 0 && minSide > 500 && maxSide <= 1400) type = "tablet";

        var iosMajor = null;
        var osToken = null;
        var safariToken = null;
        var iphoneOs = ua.match(/iPhone OS (\d+)[._]/);
        var ipadOs = ua.match(/CPU OS (\d+)[._](\d+) like Mac OS X/);
        var safariVer = ua.match(/Version\/(\d+)[._]/);
        if (iphoneOs) osToken = parseInt(iphoneOs[1], 10);
        else if (ipadOs) osToken = parseInt(ipadOs[1], 10);
        if (isIOS && safariVer) safariToken = parseInt(safariVer[1], 10);
        if (osToken != null || safariToken != null) {
          iosMajor = Math.max(osToken || 0, safariToken || 0);
        }

        var root = document.documentElement;
        var classes = ["device-" + type];
        if (iosMajor != null) {
          root.dataset.ios = String(iosMajor);
          classes.push(iosMajor >= 27 ? "ios-27-plus" : "ios-below-27");
        }
        root.className = classes.join(" ");
      })();
    </script>
  </head>
  <body>
    <div class="page">
      <header class="powered" aria-label="Powered by Grok">
        <span class="powered-by">Powered by</span>
        <span class="powered-brand">
          <img
            class="grok-logo"
            src="/__grok/install/assets/homescreen/logo-grok.svg"
            width="14"
            height="14"
            alt=""
          />
          <span class="powered-grok">Grok</span>
        </span>
      </header>

      <main class="content">
        <div class="ob" aria-hidden="true">
          <img
            class="ob-img ob-phone"
            src="/__grok/install/assets/homescreen/ob-phone.png"
            width="338"
            height="294"
            alt=""
          />
          <img
            class="ob-img ob-ipad"
            src="/__grok/install/assets/homescreen/ob-ipad.png"
            width="634"
            height="294"
            alt=""
          />
        </div>

        <section class="copy">
          <h1>Add {{APP_NAME}} to your&nbsp;Home&nbsp;Screen</h1>

          <div class="steps">
            <p class="step step-tap step-ios27">
              <span class="muted">Tap</span>
              <span class="glass glass--icon" aria-hidden="true">
                <img src="/__grok/install/assets/homescreen/glass-puzzle.svg" width="24" height="24" alt="" />
              </span>
              <span class="muted loc loc-phone">in the bottom bar, then</span>
              <span class="muted loc loc-ipad">in the tool bar, then</span>
              <span class="glass glass--icon" aria-hidden="true">
                <img src="/__grok/install/assets/homescreen/glass-share.svg" width="24" height="24" alt="" />
              </span>
            </p>

            <p class="step step-tap step-ios-legacy">
              <span class="muted">Tap</span>
              <span class="glass glass--icon" aria-hidden="true">
                <img src="/__grok/install/assets/homescreen/glass-share.svg" width="24" height="24" alt="" />
              </span>
              <span class="muted loc loc-phone">in the bottom bar</span>
              <span class="muted loc loc-ipad">in the tool bar</span>
            </p>

            <p class="step step-select">
              <span class="muted">Select</span>
              <span class="add-label">
                <img
                  class="plus-icon"
                  src="/__grok/install/assets/homescreen/plus.svg"
                  width="16"
                  height="16"
                  alt=""
                />
                <span class="add-text">Add to Home Screen</span>
              </span>
            </p>
          </div>
        </section>
      </main>

      <main class="content content-desktop">
        <section class="copy">
          <h1>Open this link on your iPhone&nbsp;or&nbsp;iPad</h1>
          <p class="desktop-note">
            This page shows how to add {{APP_NAME}} to an iOS Home Screen.
          </p>
          <a class="desktop-open" href="{{APP_URL}}">Open {{APP_NAME}}</a>
        </section>
      </main>
    </div>
  </body>
</html>

````

## `frontend_demo/scripts/migrate.mjs`
````mjs
#!/usr/bin/env node
/**
 * Deploy-time database migrator (node-postgres, `pg`).
 *
 * Runs during `npm run build` — on every Vercel deploy — applying pending files
 * in ../migrations to DATABASE_URL. Each file is applied in one transaction and
 * recorded in a `_migrations` table, so it runs once and is safe to re-run.
 *
 * The read is non-recursive, so the opt-in auth schema under migrations/auth/
 * is not applied to an app that never asked for sign-in.
 *
 * No DATABASE_URL (local / preview builds) -> skip; the PGLite fallback applies
 * the same files at startup instead (see src/lib/db.ts).
 */
import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import pg from "pg";
import { pendingMigrations } from "./migration-plan.mjs";

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  console.log(
    "[migrate] DATABASE_URL not set — skipping (the PGLite fallback migrates itself).",
  );
  process.exit(0);
}

const migrationsDir = join(dirname(fileURLToPath(import.meta.url)), "..", "migrations");

async function main() {
  let entries;
  try {
    entries = await readdir(migrationsDir);
  } catch {
    console.log("[migrate] no migrations/ directory — nothing to do.");
    return;
  }
  // An app with no schema of its own must not pay for a database connection.
  if (pendingMigrations(entries, []).length === 0) {
    console.log("[migrate] no migrations — nothing to do.");
    return;
  }

  const pool = new pg.Pool({ connectionString: databaseUrl, max: 1 });
  const client = await pool.connect();
  try {
    await client.query(
      "CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())",
    );
    const applied = (await client.query("SELECT name FROM _migrations")).rows.map(
      (r) => r.name,
    );

    let count = 0;
    for (const { name } of pendingMigrations(entries, applied)) {
      const text = await readFile(join(migrationsDir, name), "utf8");
      try {
        await client.query("BEGIN");
        // pg's simple-query protocol runs a whole multi-statement file at once.
        await client.query(text);
        await client.query("INSERT INTO _migrations (name) VALUES ($1)", [name]);
        await client.query("COMMIT");
      } catch (err) {
        console.error(`[migrate] error applying ${name}`);
        try {
          await client.query("ROLLBACK");
        } catch {
          // ROLLBACK fails when the connection died — keep the original error.
        }
        throw err;
      }
      console.log(`[migrate] applied ${name}`);
      count += 1;
    }
    console.log(count ? `[migrate] done — ${count} migration(s) applied.` : "[migrate] up to date.");
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((err) => {
  console.error("[migrate] failed:", err?.message || err);
  // pg errors carry the context needed to debug a bad SQL file.
  for (const key of ["code", "detail", "hint", "position", "where"]) {
    if (err?.[key] != null) console.error(`[migrate]   ${key}: ${err[key]}`);
  }
  process.exit(1);
});

````

## `frontend_demo/scripts/migration-plan.mjs`
````mjs
// @ts-check
/**
 * Migration bookkeeping shared by the two appliers — `scripts/migrate.mjs`
 * (deploy, `readdir`) and `src/lib/db.ts` (PGLite preview, `import.meta.glob`).
 *
 * Applied files are keyed by BASENAME, so the same file applies once no matter
 * which directory it is globbed from. That is what makes the auth schema safe to
 * copy from `migrations/auth/` into `migrations/` when an app turns sign-in on:
 * a database that already has `0001_auth.sql` will not re-run it.
 *
 * Neither applier descends into subdirectories, so `migrations/auth/*.sql` is
 * out of scope for both until it is copied up.
 */

/**
 * The `_migrations` key for a migration path (or bare filename).
 * @param {string} path
 * @returns {string}
 */
export function migrationName(path) {
  return path.split("/").pop() ?? path;
}

/**
 * @param {string} path
 * @returns {boolean}
 */
export function isMigrationFile(path) {
  return path.endsWith(".sql");
}

/**
 * Migrations in `paths` that are not yet in `applied`, in apply order.
 * Non-`.sql` entries (a `readdir` also yields `migrations/auth/`) are dropped.
 * @param {Iterable<string>} paths
 * @param {Iterable<string>} applied
 * @returns {Array<{ name: string, path: string }>}
 */
export function pendingMigrations(paths, applied) {
  const done = new Set(applied);
  return [...paths]
    .filter(isMigrationFile)
    .map((path) => ({ name: migrationName(path), path }))
    .sort((a, b) => a.name.localeCompare(b.name))
    .filter(({ name }) => !done.has(name));
}

````

## `frontend_demo/scripts/migration-plan.test.mjs`
````mjs
import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { isMigrationFile, migrationName, pendingMigrations } from "./migration-plan.mjs";
import { projectRoot } from "./with-app-env.mjs";

const AUTH_MIGRATION = "0001_auth.sql";

/**
 * The auth-on copy of the Better Auth schema and its source, or null when the
 * app has not turned sign-in on (the shipped state).
 */
function authSchemaCopy(root) {
  const copy = join(root, "migrations", AUTH_MIGRATION);
  const source = join(root, "migrations/auth", AUTH_MIGRATION);
  if (!existsSync(copy) || !existsSync(source)) return null;
  return { copy: readFileSync(copy, "utf8"), source: readFileSync(source, "utf8") };
}

test("_migrations keys on basename, not path", () => {
  assert.equal(migrationName("/migrations/0002_todos.sql"), "0002_todos.sql");
  assert.equal(migrationName("migrations/auth/0001_auth.sql"), "0001_auth.sql");
  assert.equal(migrationName("0001_auth.sql"), "0001_auth.sql");
});

test("a file already applied from another directory does not re-apply", () => {
  // The auth-on path copies migrations/auth/0001_auth.sql into the globbed
  // directory; a database that already has it must not run it twice.
  assert.deepEqual(pendingMigrations(["/migrations/0001_auth.sql"], ["0001_auth.sql"]), []);
});

test("pending migrations are returned in name order", () => {
  assert.deepEqual(
    pendingMigrations(
      ["/migrations/0003_c.sql", "/migrations/0001_a.sql", "/migrations/0002_b.sql"],
      ["0001_a.sql"],
    ),
    [
      { name: "0002_b.sql", path: "/migrations/0002_b.sql" },
      { name: "0003_c.sql", path: "/migrations/0003_c.sql" },
    ],
  );
});

test("non-.sql entries are dropped (readdir also yields the auth/ directory)", () => {
  assert.equal(isMigrationFile("auth"), false);
  assert.deepEqual(pendingMigrations(["auth", "README.md"], []), []);
});

test("the auth schema ships outside the globbed directory", () => {
  const migrationsDir = join(projectRoot(), "migrations");
  assert.deepEqual(pendingMigrations(readdirSync(migrationsDir), []), []);
  assert.ok(readdirSync(join(migrationsDir, "auth")).includes("0001_auth.sql"));
});

test("this workspace's auth schema copy is byte-identical to its source", () => {
  // An edited copy diverges silently: basename keying skips it on a database
  // that already ran the original, and applies it on a fresh PGLite preview.
  const pair = authSchemaCopy(projectRoot());
  if (pair === null) return; // sign-in off — nothing has been copied up
  assert.equal(
    pair.copy,
    pair.source,
    "migrations/0001_auth.sql has been edited — it must stay a verbatim copy of migrations/auth/0001_auth.sql",
  );
});

test("the copy check reads both files and catches an edit", () => {
  const root = mkdtempSync(join(tmpdir(), "auth-schema-"));
  mkdirSync(join(root, "migrations/auth"), { recursive: true });
  writeFileSync(join(root, "migrations/auth", AUTH_MIGRATION), "create table t ();\n");
  assert.equal(authSchemaCopy(root), null);

  writeFileSync(join(root, "migrations", AUTH_MIGRATION), "create table t ();\n");
  const same = authSchemaCopy(root);
  assert.equal(same.copy, same.source);

  writeFileSync(join(root, "migrations", AUTH_MIGRATION), "create table t (x int);\n");
  const drifted = authSchemaCopy(root);
  assert.notEqual(drifted.copy, drifted.source);
});

````

## `frontend_demo/scripts/sign-out-plan.mjs`
````mjs
// @ts-check
/**
 * The sign-out sequence used by `src/lib/auth/client.ts`, kept here as a pure
 * module so its effects can be unit-tested (`node --test` only covers
 * `scripts/`), the same split `migration-plan.mjs` uses for the two appliers.
 *
 * The two environments authenticate differently, so they need different
 * answers to "the server did not reply":
 *
 * - **Live preview** — a partitioned iframe with no readable session cookie;
 *   the session rides the bearer token in `sessionStorage`. Dropping that token
 *   IS being signed out, so the server call is best effort and a wedged request
 *   must never strand the button. This is where the hang actually happens.
 * - **Deployed** — the session rides an HttpOnly `__Host-` cookie that JS
 *   cannot delete. ONLY a completed sign-out response clears it, and
 *   `server.ts` enables `session.cookieCache` (maxAge 300), so `/get-session`
 *   would keep answering from the cached cookie for minutes afterwards.
 *   Redirecting on a timeout would show the visitor "signed out" while their
 *   session is still live — so here we fail loudly instead of pretending.
 */

/**
 * Live preview: aggressive, because the local clear is what signs the user out.
 * The same-origin POST normally answers in tens of ms; lower would start
 * abandoning slow-but-working sign-outs for no gain.
 */
export const PREVIEW_SIGN_OUT_TIMEOUT_MS = 1500;

/**
 * Deployed: generous, because only the server can end this session — but still
 * bounded, so a wedged request reports failure the visitor can retry instead of
 * spinning forever. A sign-out still unanswered at 10s is not going to land.
 */
export const DEPLOYED_SIGN_OUT_TIMEOUT_MS = 10_000;

/**
 * How long to wait for a sign-out in this environment. Every sign-out network
 * call picks its bound here, so the preview/deployed split cannot drift apart
 * between callers.
 * @param {boolean} livePreview
 * @returns {number}
 */
export function signOutTimeoutMs(livePreview) {
  return livePreview ? PREVIEW_SIGN_OUT_TIMEOUT_MS : DEPLOYED_SIGN_OUT_TIMEOUT_MS;
}

/**
 * Run `start()` but give up after `timeoutMs`, reporting which happened. Never
 * rejects — callers decide what a failure means, and a `try/catch` around an
 * `await` does nothing for a promise that never settles.
 * @param {() => unknown} start
 * @param {number} timeoutMs
 * @returns {Promise<"ok" | "failed" | "timeout">}
 */
export function settleWithin(start, timeoutMs) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve("timeout"), timeoutMs);
    /** @param {"ok" | "failed"} outcome */
    const done = (outcome) => {
      clearTimeout(timer);
      resolve(outcome);
    };
    try {
      Promise.resolve(start()).then(
        () => done("ok"),
        () => done("failed"),
      );
    } catch {
      done("failed");
    }
  });
}

/**
 * @typedef {object} SignOutSteps
 * @property {boolean} livePreview Whether the app is the sandbox preview iframe.
 * @property {boolean} hasBearer Whether a preview bearer token is stored.
 * @property {() => unknown} requestSignOut Ask the server to end the session; must reject on a failed response.
 * @property {() => void} clearToken Drop the stored bearer token.
 * @property {() => void} redirect Leave the page.
 * @property {number} [timeoutMs]
 */

/**
 * End the session, then clear the local token and redirect.
 *
 * In the live preview those last two always run. When deployed they run only if
 * the server confirmed, because nothing else can clear the cookie — a failed or
 * timed-out sign-out throws rather than reporting a sign-out that did not
 * happen.
 * @param {SignOutSteps} steps
 * @returns {Promise<void>}
 */
export async function runSignOut({
  livePreview,
  hasBearer,
  requestSignOut,
  clearToken,
  redirect,
  timeoutMs,
}) {
  if (livePreview) {
    // No bearer means a partitioned iframe with nothing to invalidate; with one,
    // still invalidate it server-side, just don't block on the answer.
    if (hasBearer) {
      await settleWithin(requestSignOut, timeoutMs ?? signOutTimeoutMs(livePreview));
    }
    clearToken();
    redirect();
    return;
  }

  const outcome = await settleWithin(requestSignOut, timeoutMs ?? signOutTimeoutMs(livePreview));
  if (outcome !== "ok") {
    throw new Error(
      outcome === "timeout"
        ? "Sign-out timed out — you are still signed in. Please try again."
        : "Sign-out failed — you are still signed in. Please try again.",
    );
  }
  clearToken();
  redirect();
}

/**
 * @typedef {object} PreSignInSteps
 * @property {boolean} livePreview Whether the app is the sandbox preview iframe.
 * @property {boolean} hasBearer Whether a preview bearer token is stored.
 * @property {() => unknown} requestSignOut Ask the server to end any prior session.
 * @property {() => void} clearToken Drop the stored bearer token.
 * @property {number} [timeoutMs]
 */

/**
 * Drop any prior session before a new sign-in starts, so switching providers
 * actually switches identity.
 *
 * Deliberately BEST EFFORT — unlike `runSignOut` this never throws. It also
 * runs when there is no prior session at all, so treating a failure as fatal
 * would block first-time sign-in on a transport hiccup, for a visitor with no
 * session to protect. The subsequent OAuth flow issues a fresh session either
 * way. Only the wait is bounded, and by the same per-environment rule as
 * `runSignOut`: a deployed session dies server-side, so it gets the full
 * window rather than the preview's aggressive one.
 * @param {PreSignInSteps} steps
 * @returns {Promise<void>}
 */
export async function runPreSignInSignOut({
  livePreview,
  hasBearer,
  requestSignOut,
  clearToken,
  timeoutMs,
}) {
  // In the preview a missing bearer means there is nothing to clear.
  if (hasBearer || !livePreview) {
    await settleWithin(requestSignOut, timeoutMs ?? signOutTimeoutMs(livePreview));
  }
  clearToken();
}

````

## `frontend_demo/scripts/sign-out-plan.test.mjs`
````mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  DEPLOYED_SIGN_OUT_TIMEOUT_MS,
  PREVIEW_SIGN_OUT_TIMEOUT_MS,
  runPreSignInSignOut,
  runSignOut,
  settleWithin,
  signOutTimeoutMs,
} from "./sign-out-plan.mjs";

const TEST_TIMEOUT_MS = 20;

const hangs = () => new Promise(() => {});
const rejects = () => Promise.reject(new Error("network down"));

/**
 * Drain pending microtasks without advancing mocked time, so "has it finished
 * yet?" is answered by the mocked clock rather than by wall-clock luck.
 * `setImmediate` stays real — only `setTimeout` is mocked.
 */
const flush = () => new Promise((resolve) => setImmediate(resolve));

/**
 * A `runSignOut` call with the browser effects replaced by recorders, so each
 * test asserts on what actually happened rather than on how it was written.
 */
function harness(overrides = {}) {
  /** @type {string[]} */
  const order = [];
  let requests = 0;
  const steps = {
    livePreview: false,
    hasBearer: true,
    requestSignOut: () => {
      requests += 1;
      return Promise.resolve();
    },
    clearToken: () => order.push("clear"),
    redirect: () => order.push("redirect"),
    timeoutMs: TEST_TIMEOUT_MS,
    ...overrides,
  };
  return {
    order,
    get requests() {
      return requests;
    },
    run: () => runSignOut(steps),
  };
}

/** Live preview: the bearer is the session, so the local clear always wins. */
const preview = (overrides = {}) => harness({ livePreview: true, ...overrides });

/** Deployed: only the server can clear the `__Host-` cookie. */
const deployed = (overrides = {}) => harness({ livePreview: false, ...overrides });

// ── Live preview ─────────────────────────────────────────────────────────────

test("preview: a successful sign-out clears the token, then redirects", async () => {
  const h = preview();
  await h.run();
  assert.equal(h.requests, 1);
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

test("preview: a rejected sign-out still clears the token and redirects", async () => {
  const h = preview({ requestSignOut: rejects });
  await h.run();
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

test("preview: a sign-out that throws synchronously still clears and redirects", async () => {
  const h = preview({
    requestSignOut: () => {
      throw new Error("no fetch");
    },
  });
  await h.run();
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

test("preview: a sign-out that never settles clears and redirects once the wait expires", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = preview({ requestSignOut: hangs });
  const done = h.run();

  t.mock.timers.tick(TEST_TIMEOUT_MS - 1);
  await flush();
  assert.deepEqual(h.order, [], "the server still has its window — do not give up early");

  t.mock.timers.tick(1);
  await done;
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

test("preview: no bearer means nothing to invalidate, so no request is made", async () => {
  const h = preview({ hasBearer: false });
  await h.run();
  assert.equal(h.requests, 0);
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

test("preview: a stored bearer is still invalidated server-side", async () => {
  const h = preview({ hasBearer: true });
  await h.run();
  assert.equal(h.requests, 1);
});

// ── Deployed ─────────────────────────────────────────────────────────────────
// JS cannot delete the HttpOnly `__Host-` cookie and `cookieCache` keeps
// serving the cached session, so an unconfirmed sign-out must NOT look like one.

test("deployed: a confirmed sign-out clears the token, then redirects", async () => {
  const h = deployed();
  await h.run();
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

test("deployed: a sign-out that never settles throws and does NOT redirect", async () => {
  const h = deployed({ requestSignOut: hangs });
  await assert.rejects(h.run(), /still signed in/);
  assert.deepEqual(h.order, [], "no redirect may claim a sign-out the server never made");
});

test("deployed: a rejected sign-out throws and does NOT redirect", async () => {
  const h = deployed({ requestSignOut: rejects });
  await assert.rejects(h.run(), /still signed in/);
  assert.deepEqual(h.order, []);
});

test("deployed: the timeout is distinguishable from a rejection", async () => {
  await assert.rejects(deployed({ requestSignOut: hangs }).run(), /timed out/);
  await assert.rejects(deployed({ requestSignOut: rejects }).run(), /Sign-out failed/);
});

// ── Bounded wait (also used by `signIn`'s pre-sign-in session clear) ──────────

test("settleWithin reports the outcome and never rejects", async () => {
  assert.equal(await settleWithin(() => Promise.resolve(), TEST_TIMEOUT_MS), "ok");
  assert.equal(await settleWithin(rejects, TEST_TIMEOUT_MS), "failed");
  assert.equal(await settleWithin(hangs, TEST_TIMEOUT_MS), "timeout");
});

test("settleWithin waits its full window, then gives up rather than hanging", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let outcome = null;
  const done = settleWithin(hangs, TEST_TIMEOUT_MS).then((o) => (outcome = o));

  t.mock.timers.tick(TEST_TIMEOUT_MS - 1);
  await flush();
  assert.equal(outcome, null, "the request still has time left");

  t.mock.timers.tick(1);
  await done;
  assert.equal(outcome, "timeout", "the caller is never left waiting on a wedged request");
});

// ── Pre-sign-in session clear (`signIn`) ─────────────────────────────────────
// Same per-environment bound as sign-out, but best effort: it also runs when
// there is no prior session, so a failure must never block sign-in.

/** A pre-sign-in clear whose request never settles. */
function preSignIn(livePreview, overrides = {}) {
  let cleared = 0;
  const done = runPreSignInSignOut({
    livePreview,
    hasBearer: true,
    requestSignOut: hangs,
    clearToken: () => (cleared += 1),
    ...overrides,
  });
  return {
    done,
    get cleared() {
      return cleared;
    },
  };
}

test("pre-sign-in: the preview clear gives up at the preview bound", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = preSignIn(true);

  t.mock.timers.tick(PREVIEW_SIGN_OUT_TIMEOUT_MS - 1);
  await flush();
  assert.equal(h.cleared, 0);

  t.mock.timers.tick(1);
  await h.done;
  assert.equal(h.cleared, 1);
});

test("pre-sign-in: a deployed session gets the deployed window, not the preview one", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = preSignIn(false);

  t.mock.timers.tick(PREVIEW_SIGN_OUT_TIMEOUT_MS);
  await flush();
  assert.equal(
    h.cleared,
    0,
    "only the server can end a deployed session — do not start OAuth while it is still live",
  );

  t.mock.timers.tick(DEPLOYED_SIGN_OUT_TIMEOUT_MS - PREVIEW_SIGN_OUT_TIMEOUT_MS);
  await h.done;
  assert.equal(h.cleared, 1);
});

test("pre-sign-in: a failed clear never blocks sign-in", async () => {
  // Best effort by design: this also runs with no prior session to clear.
  await preSignIn(false, { requestSignOut: rejects, timeoutMs: TEST_TIMEOUT_MS }).done;
  await preSignIn(true, { requestSignOut: rejects, timeoutMs: TEST_TIMEOUT_MS }).done;
});

test("pre-sign-in: the preview skips the request when there is no bearer", async () => {
  let requests = 0;
  const h = preSignIn(true, {
    hasBearer: false,
    requestSignOut: () => {
      requests += 1;
      return hangs();
    },
  });
  await h.done;
  assert.equal(requests, 0);
  assert.equal(h.cleared, 1);
});

test("every sign-out bound comes from one rule", () => {
  assert.equal(signOutTimeoutMs(true), PREVIEW_SIGN_OUT_TIMEOUT_MS);
  assert.equal(signOutTimeoutMs(false), DEPLOYED_SIGN_OUT_TIMEOUT_MS);
});

test("the defaults are bounded, and deployed waits longer than preview", async (t) => {
  assert.ok(PREVIEW_SIGN_OUT_TIMEOUT_MS > 0 && PREVIEW_SIGN_OUT_TIMEOUT_MS <= 2000);
  assert.ok(DEPLOYED_SIGN_OUT_TIMEOUT_MS > PREVIEW_SIGN_OUT_TIMEOUT_MS);
  assert.ok(DEPLOYED_SIGN_OUT_TIMEOUT_MS <= 30_000);

  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = preview({ requestSignOut: hangs, timeoutMs: undefined });
  const done = h.run();
  t.mock.timers.tick(PREVIEW_SIGN_OUT_TIMEOUT_MS);
  await done;
  assert.deepEqual(h.order, ["clear", "redirect"]);
});

````

## `frontend_demo/scripts/write-atomic.mjs`
````mjs
#!/usr/bin/env node
/**
 * Hand a staged file over to a path another agent reads, in one step.
 *
 *   node scripts/write-atomic.mjs /workspace/.grok/og.jpg.tmp public/og.jpg
 *
 * The brand-asset task writes public/og.jpg and src/lib/og/site.json while the
 * parent may be mid-`npm run build`, so an in-place write can be read
 * half-finished. rename(2) is atomic within one filesystem: a reader sees the
 * old bytes or the new ones. /workspace is one filesystem, so a staged file
 * from anywhere else (/tmp is a separate mount) is refused rather than copied:
 * copying would have to land its temp in the target's directory, which is the
 * one thing a staged path is not allowed to do.
 */
import { existsSync, mkdirSync, renameSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

export function parseWriteAtomicArgs(argv) {
  const [staged, target, ...rest] = argv;
  if (!staged || !target) {
    return { error: "usage: node scripts/write-atomic.mjs <staged-file> <target>" };
  }
  if (rest.length > 0) return { error: `unexpected argument: ${rest[0]}` };
  return { staged, target };
}

function isInside(dir, file) {
  const rel = relative(dir, file);
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
}

/**
 * Why a staged path can be refused: `vite build` copies public/ verbatim into
 * the deployed app, so a temp that lands there ships (and an interrupted run
 * leaves it behind).
 */
export function stagingError({ staged, target, publicDir }) {
  if (staged === target) return `staged file and target are the same path: ${target}`;
  if (isInside(publicDir, staged)) {
    return `stage outside ${publicDir} (vite build ships that directory verbatim): ${staged}`;
  }
  return null;
}

/**
 * Moves `staged` onto `target`, leaving `target` untouched if anything fails.
 * `rename` is injectable because EXDEV — the refusal the "stage under
 * /workspace/.grok/" contract rests on — cannot be provoked portably.
 */
export function handOver(staged, target, { rename = renameSync } = {}) {
  if (!existsSync(staged)) {
    throw Object.assign(new Error(`staged file is missing: ${staged}`), { code: "ENOENT" });
  }
  mkdirSync(dirname(target), { recursive: true });
  try {
    rename(staged, target);
  } catch (err) {
    if (err?.code === "EXDEV") {
      throw new Error(
        `${staged} is on another filesystem than ${target}, so the hand-over cannot be a `
          + "rename — stage under /workspace/.grok/ instead",
      );
    }
    throw err;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = parseWriteAtomicArgs(process.argv.slice(2));
  if (args.error) {
    console.error(`[write-atomic] ${args.error}`);
    process.exit(1);
  }
  // Relative paths follow this script's root, not the caller's cwd: the brand
  // pass runs from wherever its sub-shell left it, and the public/ refusal
  // below is defined against that same root.
  const staged = resolve(ROOT, args.staged);
  const target = resolve(ROOT, args.target);
  const problem = stagingError({ staged, target, publicDir: join(ROOT, "public") });
  if (problem) {
    console.error(`[write-atomic] ${problem}`);
    process.exit(1);
  }
  try {
    handOver(staged, target);
  } catch (err) {
    console.error(`[write-atomic] ${staged} → ${target} failed: ${err?.message || err}`);
    process.exit(1);
  }
  console.log(`[write-atomic] wrote ${target}`);
}

````

## `frontend_demo/scripts/write-atomic.test.mjs`
````mjs
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { handOver, parseWriteAtomicArgs, stagingError } from "./write-atomic.mjs";

const TEMPLATE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCRIPT = join(TEMPLATE_ROOT, "scripts/write-atomic.mjs");

function makeWorkspace() {
  const root = mkdtempSync(join(tmpdir(), "write-atomic-"));
  mkdirSync(join(root, "public"), { recursive: true });
  mkdirSync(join(root, ".grok"), { recursive: true });
  return root;
}

test("parseWriteAtomicArgs needs exactly a staged file and a target", () => {
  assert.deepEqual(parseWriteAtomicArgs([".grok/og.tmp", "public/og.jpg"]), {
    staged: ".grok/og.tmp",
    target: "public/og.jpg",
  });
  assert.match(parseWriteAtomicArgs([]).error, /usage:/);
  assert.match(parseWriteAtomicArgs([".grok/og.tmp"]).error, /usage:/);
  assert.match(parseWriteAtomicArgs(["a", "b", "c"]).error, /unexpected argument: c/);
});

test("stagingError refuses a temp inside public/ and a no-op move", () => {
  const publicDir = "/workspace/public";
  assert.equal(
    stagingError({
      staged: "/workspace/.grok/og.jpg.tmp",
      target: "/workspace/public/og.jpg",
      publicDir,
    }),
    null,
  );
  assert.match(
    stagingError({
      staged: "/workspace/public/og.jpg.tmp",
      target: "/workspace/public/og.jpg",
      publicDir,
    }),
    /vite build ships that directory verbatim/,
  );
  assert.match(
    stagingError({
      staged: "/workspace/public/og.jpg",
      target: "/workspace/public/og.jpg",
      publicDir,
    }),
    /same path/,
  );
});

test("handOver replaces the target and clears the staged file", () => {
  const root = makeWorkspace();
  const staged = join(root, ".grok/og.jpg.tmp");
  const target = join(root, "public/og.jpg");
  writeFileSync(target, "old card");
  writeFileSync(staged, "new card");

  handOver(staged, target);

  assert.equal(readFileSync(target, "utf8"), "new card");
  assert.equal(existsSync(staged), false);
});

test("handOver creates a missing target directory", () => {
  const root = makeWorkspace();
  const staged = join(root, ".grok/site.json.tmp");
  writeFileSync(staged, '{"title":"Sky Strike"}');

  handOver(staged, join(root, "src/lib/og/site.json"));

  assert.equal(readFileSync(join(root, "src/lib/og/site.json"), "utf8"), '{"title":"Sky Strike"}');
});

test("an interrupted pass leaves the target on its old bytes, temp-free", () => {
  const root = makeWorkspace();
  const target = join(root, "public/og.jpg");
  writeFileSync(target, "old card");
  // The staged file a killed ffmpeg leaves behind: never handed over.
  writeFileSync(join(root, ".grok/og.jpg.tmp"), "half a JPEG");

  assert.equal(readFileSync(target, "utf8"), "old card");
  assert.throws(() => handOver(join(root, ".grok/absent.tmp"), target), { code: "ENOENT" });
  assert.equal(readFileSync(target, "utf8"), "old card");
  assert.equal(existsSync(`${target}.tmp-${process.pid}`), false);
});

test("a failed hand-over creates no directory for the target it never wrote", () => {
  const root = makeWorkspace();
  const missing = join(root, ".grok/absent.tmp");
  assert.throws(() => handOver(missing, join(root, "src/lib/og/site.json")), { code: "ENOENT" });
  assert.equal(existsSync(join(root, "src")), false);
});

test("a staged file on another filesystem is refused, not copied", () => {
  const root = makeWorkspace();
  const staged = join(root, ".grok/og.jpg.tmp");
  const target = join(root, "public/og.jpg");
  writeFileSync(staged, "new card");
  writeFileSync(target, "old card");
  const crossDevice = () => {
    throw Object.assign(new Error("EXDEV"), { code: "EXDEV" });
  };

  assert.throws(() => handOver(staged, target, { rename: crossDevice }), {
    message: /stage under \/workspace\/\.grok\//,
  });
  // Copying would have had to stage its own temp inside public/, which is the
  // one place stagingError refuses.
  assert.deepEqual(readdirSync(join(root, "public")), ["og.jpg"]);
  assert.equal(readFileSync(target, "utf8"), "old card");
});

test("cli: hands the file over, and refuses a temp staged in public/", () => {
  const root = makeWorkspace();
  writeFileSync(join(root, ".grok/og.jpg.tmp"), "new card");
  const ok = spawnSync(
    process.execPath,
    [SCRIPT, join(root, ".grok/og.jpg.tmp"), join(root, "public/og.jpg")],
    { encoding: "utf8" },
  );
  assert.equal(ok.status, 0, ok.stdout + ok.stderr);
  assert.equal(readFileSync(join(root, "public/og.jpg"), "utf8"), "new card");

  // publicDir comes from the script's own root, so refusal is checked there.
  const templateRoot = join(dirname(SCRIPT), "..");
  const staged = join(templateRoot, "public/og.jpg.tmp");
  const refused = spawnSync(
    process.execPath,
    [SCRIPT, staged, join(templateRoot, "public/og.jpg")],
    { encoding: "utf8" },
  );
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /stage outside/);
  assert.equal(existsSync(staged), false);
});

test("cli: relative paths follow the script's root, not the caller's cwd", () => {
  // Same relative pair the skill documents, run from a workspace that has its
  // own public/: resolving against cwd would take the staged temp out of the
  // directory the refusal is defined against and move it.
  const root = makeWorkspace();
  writeFileSync(join(root, "public/og.jpg.tmp"), "half a JPEG");
  const run = spawnSync(process.execPath, [SCRIPT, "public/og.jpg.tmp", "public/og.jpg"], {
    cwd: root,
    encoding: "utf8",
  });
  assert.equal(run.status, 1, run.stdout + run.stderr);
  assert.match(run.stderr, /stage outside/);
  assert.equal(readFileSync(join(root, "public/og.jpg.tmp"), "utf8"), "half a JPEG");
  assert.equal(existsSync(join(root, "public/og.jpg")), false);
});

test("every hand-over the og skill prints is one this script accepts", () => {
  // The card and banner recipes live in the skill's references/, not SKILL.md.
  const skillDir = join(TEMPLATE_ROOT, ".grok/skills/og");
  const docs = [
    join(skillDir, "SKILL.md"),
    ...readdirSync(join(skillDir, "references")).map((f) => join(skillDir, "references", f)),
  ];
  const invocations = docs.flatMap(
    (path) => readFileSync(path, "utf8").match(/node scripts\/write-atomic\.mjs[^\n`]*/g) ?? [],
  );
  assert.ok(invocations.length >= 3, "og.jpg, x-banner.jpg and site.json each hand over");
  for (const line of invocations) {
    const argv = line.replace("node scripts/write-atomic.mjs", "").trim().split(/\s+/);
    const args = parseWriteAtomicArgs(argv);
    assert.equal(args.error, undefined, line);
    assert.equal(
      stagingError({ staged: args.staged, target: args.target, publicDir: "/workspace/public" }),
      null,
      line,
    );
  }
});

test("cli: a missing staged file fails without touching the target", () => {
  const root = makeWorkspace();
  writeFileSync(join(root, "public/og.jpg"), "old card");
  const run = spawnSync(
    process.execPath,
    [SCRIPT, join(root, ".grok/absent.tmp"), join(root, "public/og.jpg")],
    { encoding: "utf8" },
  );
  assert.equal(run.status, 1);
  assert.match(run.stderr, /\[write-atomic\]/);
  assert.equal(readFileSync(join(root, "public/og.jpg"), "utf8"), "old card");
});

````

## `frontend_demo/src/lib/app-data/app-data.test.ts`
````ts
import { afterEach, beforeEach, describe, it, mock } from "node:test";
import assert from "node:assert/strict";
import {
  callTool,
  failureMemoSize,
  isConnectorTokenReady,
} from "./client.server.ts";
import { ConnectorType, GoogleCalendarTools } from "./types.ts";
import type { ToolArgs } from "./types.ts";
import { isLoginRequired, redirectToLoginIfRequired } from "./login.ts";
import { classifyCallToolError } from "./errors.ts";
import type { CallToolResult } from "./types.ts";

type WindowStub = {
  location: { assign: (url: string) => void; href: string };
  self?: unknown;
  top?: unknown;
  open?: (url: string, target: string) => unknown;
};

function withWindow<T>(stub: WindowStub, fn: () => T): T {
  (globalThis as { window?: unknown }).window = stub;
  try {
    return fn();
  } finally {
    delete (globalThis as { window?: unknown }).window;
  }
}

function fakeJwt(claims: Record<string, unknown>): string {
  const encode = (value: unknown) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(claims)}.sig`;
}

async function withStubbedGate(
  status: number,
  body: Record<string, unknown>,
  run: (calls: () => number) => Promise<void>,
): Promise<void> {
  process.env.GROK_CONNECTORS_URL = "https://connectors.invalid.example";
  const realFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response(JSON.stringify(body), { status });
  }) as typeof fetch;
  try {
    await run(() => calls);
  } finally {
    globalThis.fetch = realFetch;
    delete process.env.GROK_CONNECTORS_URL;
  }
}

describe("callTool failure memo", () => {
  it("replays an identical failure within the memo window without refetching", async () => {
    await withStubbedGate(500, { ok: false, errorMessage: "boom" }, async (calls) => {
      const options = {
        connectorType: ConnectorType.GoogleDrive,
        token: fakeJwt({ sub: "memo-user-1", iat: 1000, exp: 2000 }),
      };
      const first = await callTool("google_drive_search", { q: "memo" }, options);
      const second = await callTool("google_drive_search", { q: "memo" }, options);
      assert.equal(first.ok, false);
      assert.equal(first.errorMessage, "boom");
      assert.deepEqual(second, first);
      assert.equal(calls(), 1);
    });
  });

  it("keys by token identity so a reminted token shares the memo entry", async () => {
    await withStubbedGate(500, { ok: false, errorMessage: "boom" }, async (calls) => {
      const first = await callTool(
        "google_drive_search",
        { q: "remint" },
        {
          connectorType: ConnectorType.GoogleDrive,
          token: fakeJwt({ sub: "memo-user-2", iat: 1000, exp: 2000 }),
        },
      );
      const second = await callTool(
        "google_drive_search",
        { q: "remint" },
        {
          connectorType: ConnectorType.GoogleDrive,
          token: fakeJwt({ sub: "memo-user-2", iat: 1001, exp: 2001 }),
        },
      );
      assert.equal(first.ok, false);
      assert.deepEqual(second, first);
      assert.equal(calls(), 1);

      const other = await callTool(
        "google_drive_search",
        { q: "remint" },
        {
          connectorType: ConnectorType.GoogleDrive,
          token: fakeJwt({ sub: "memo-user-3", iat: 1000, exp: 2000 }),
        },
      );
      assert.equal(other.ok, false);
      assert.equal(calls(), 2);
    });
  });

  it("sweeps expired entries on write so unique keys do not accumulate", async () => {
    await withStubbedGate(500, { ok: false, errorMessage: "boom" }, async () => {
      mock.timers.enable({ apis: ["Date"], now: 1_000_000 });
      try {
        const sizeBefore = failureMemoSize();
        const options = {
          connectorType: ConnectorType.GoogleDrive,
          token: fakeJwt({ sub: "memo-user-5", iat: 1000, exp: 2000 }),
        };
        await callTool("google_drive_search", { q: "sweep-a" }, options);
        await callTool("google_drive_search", { q: "sweep-b" }, options);
        assert.equal(failureMemoSize(), sizeBefore + 2);

        mock.timers.setTime(1_000_000 + 5_001);
        await callTool("google_drive_search", { q: "sweep-c" }, options);
        assert.equal(
          failureMemoSize(),
          sizeBefore + 1,
          "expired sweep-a/sweep-b entries must be removed on the sweep-c write",
        );
      } finally {
        mock.timers.reset();
      }
    });
  });

  it("never memoizes login-required 401s", async () => {
    process.env.GROK_PROJECT_ID = "proj-1";
    try {
      await withStubbedGate(401, { errorMessage: "login required" }, async (calls) => {
        const options = {
          connectorType: ConnectorType.GoogleDrive,
          token: fakeJwt({ sub: "memo-user-4", iat: 1000, exp: 2000 }),
        };
        const first = await callTool("google_drive_search", { q: "auth" }, options);
        const second = await callTool("google_drive_search", { q: "auth" }, options);
        assert.equal(first.ok, false);
        assert.equal(first.loginRequired, true);
        assert.equal(second.loginRequired, true);
        assert.equal(calls(), 2);
      });
    } finally {
      delete process.env.GROK_PROJECT_ID;
    }
  });
});

describe("callTool in the workspace preview vs deployed", () => {
  const options = { connectorType: ConnectorType.GoogleDrive };
  const savedEnvToken = process.env.GROK_CONNECTOR_ACCESS_TOKEN;

  beforeEach(() => {
    delete process.env.GROK_CONNECTOR_ACCESS_TOKEN;
    delete process.env.GROK_PROJECT_ID;
  });
  afterEach(() => {
    if (savedEnvToken === undefined) {
      delete process.env.GROK_CONNECTOR_ACCESS_TOKEN;
    } else {
      process.env.GROK_CONNECTOR_ACCESS_TOKEN = savedEnvToken;
    }
    delete process.env.GROK_PROJECT_ID;
  });

  it("returns pending (no loginRequired) when the preview has no token yet", async () => {
    const result = await callTool("google_drive_search", {}, options);
    assert.equal(result.ok, false);
    assert.equal(result.pending, true);
    assert.equal(result.loginRequired, undefined);
    assert.match(result.errorMessage ?? "", /^connector_token_pending/);
  });

  it("returns a plain error (no sign-in CTA) when a deployed app has no token", async () => {
    process.env.GROK_PROJECT_ID = "proj-1";
    const result = await callTool("google_drive_search", {}, options);
    assert.equal(result.ok, false);
    assert.equal(result.loginRequired, undefined);
    assert.equal(result.loginUrl, undefined);
    assert.equal(result.pending, undefined);
    assert.match(result.errorMessage ?? "", /^missing_connector_token/);
  });

  it("treats a gate 401 in the preview as pending and parks the rejected token", async () => {
    await withStubbedGate(401, { errorMessage: "login required" }, async (calls) => {
      process.env.GROK_CONNECTOR_ACCESS_TOKEN = fakeJwt({ sub: "p", iat: 1, exp: 2 });
      assert.equal(isConnectorTokenReady(), true);

      const result = await callTool("google_drive_search", {}, options);
      assert.equal(result.pending, true);
      assert.equal(result.loginRequired, undefined);
      assert.match(result.errorMessage ?? "", /^connector_token_pending/);
      assert.equal(calls(), 1);
      assert.equal(isConnectorTokenReady(), false);

      process.env.GROK_CONNECTOR_ACCESS_TOKEN = fakeJwt({ sub: "p", iat: 3, exp: 4 });
      assert.equal(isConnectorTokenReady(), true);
    });
  });

  it("keeps loginRequired for a gate 401 on a deployed app", async () => {
    process.env.GROK_PROJECT_ID = "proj-1";
    await withStubbedGate(401, { errorMessage: "login required" }, async () => {
      const result = await callTool("google_drive_search", {}, {
        ...options,
        token: fakeJwt({ sub: "d", iat: 1, exp: 2 }),
      });
      assert.equal(result.loginRequired, true);
      assert.equal(result.pending, undefined);
    });
  });
});

describe("callTool", () => {
  it("resolves ok:false for non-serializable args instead of rejecting", async () => {
    process.env.GROK_CONNECTORS_URL = "https://connectors.invalid.example";
    try {
      const circular: Record<string, unknown> = {};
      circular.self = circular;
      const result = await callTool(
        "google_drive_search",
        circular as ToolArgs,
        {
          connectorType: ConnectorType.GoogleDrive,
          token: "opaque-token",
        },
      );
      assert.equal(result.ok, false);
      assert.match(result.errorMessage ?? "", /circular/i);
    } finally {
      delete process.env.GROK_CONNECTORS_URL;
    }
  });
});

describe("isLoginRequired", () => {
  it("is true only for login-required failures", () => {
    assert.equal(
      isLoginRequired({ ok: false, data: null, loginRequired: true }),
      true,
    );
    assert.equal(isLoginRequired({ ok: false, data: null }), false);
    assert.equal(
      isLoginRequired({ ok: false, data: null, errorMessage: "access_denied" }),
      false,
    );
    assert.equal(
      isLoginRequired({
        ok: true,
        data: {},
        loginRequired: true,
      } as CallToolResult),
      false,
    );
  });
});

describe("redirectToLoginIfRequired", () => {
  it("no-ops when login is not required", () => {
    let target = "";
    const did = withWindow(
      {
        location: {
          assign: (u) => {
            target = u;
          },
          href: "https://my-app.grok.me/current",
        },
      },
      () =>
        redirectToLoginIfRequired({
          ok: false,
          data: null,
          errorMessage: "tool error",
        }),
    );
    assert.equal(did, false);
    assert.equal(target, "");
  });

  it("navigates to the server-built loginUrl in the browser", () => {
    let target = "";
    const did = withWindow(
      {
        location: {
          assign: (u) => {
            target = u;
          },
          href: "https://my-app.grok.me/current",
        },
      },
      () =>
        redirectToLoginIfRequired({
          ok: false,
          data: null,
          loginRequired: true,
          loginUrl: "https://gate.grok.me/__gate/signin?return_to=x",
        }),
    );
    assert.equal(did, true);
    assert.equal(target, "https://gate.grok.me/__gate/signin?return_to=x");
  });

  it("opens a new tab instead of navigating when framed", () => {
    let assigned = "";
    let opened = "";
    const openedTab: { opener?: unknown } = { opener: "parent" };
    const did = withWindow(
      {
        self: "frame",
        top: "host",
        open: (url) => {
          opened = url;
          return openedTab;
        },
        location: {
          assign: (u) => {
            assigned = u;
          },
          href: "https://my-app.grok.me/current",
        },
      },
      () =>
        redirectToLoginIfRequired({
          ok: false,
          data: null,
          loginRequired: true,
          loginUrl: "https://gate.grok.me/__gate/signin?return_to=x",
        }),
    );
    assert.equal(did, true);
    assert.equal(opened, "https://gate.grok.me/__gate/signin?return_to=x");
    assert.equal(openedTab.opener, null);
    assert.equal(assigned, "");
  });

  it("falls back to navigation when framed and the popup is blocked", () => {
    let assigned = "";
    const did = withWindow(
      {
        self: "frame",
        top: "host",
        open: () => null,
        location: {
          assign: (u) => {
            assigned = u;
          },
          href: "https://my-app.grok.me/current",
        },
      },
      () =>
        redirectToLoginIfRequired({
          ok: false,
          data: null,
          loginRequired: true,
          loginUrl: "https://gate.grok.me/__gate/signin?return_to=x",
        }),
    );
    assert.equal(did, true);
    assert.equal(assigned, "https://gate.grok.me/__gate/signin?return_to=x");
  });

  it("returns false when the result has no loginUrl", () => {
    let target = "";
    const did = withWindow(
      {
        location: {
          assign: (u) => {
            target = u;
          },
          href: "https://my-app.grok.me/current",
        },
      },
      () =>
        redirectToLoginIfRequired({ ok: false, data: null, loginRequired: true }),
    );
    assert.equal(did, false);
    assert.equal(target, "");
  });

  it("returns false on the server (no window)", () => {
    const did = redirectToLoginIfRequired({
      ok: false,
      data: null,
      loginRequired: true,
      loginUrl: "https://gate.grok.me/__gate/signin?return_to=x",
    });
    assert.equal(did, false);
  });
});

describe("GoogleCalendarTools", () => {
  it("does not expose a list_events name", () => {
    assert.equal(GoogleCalendarTools.search, "google_calendar_search");
    assert.equal(GoogleCalendarTools.listCalendars, "google_calendar_list_calendars");
    const toolNames: readonly string[] = Object.values(GoogleCalendarTools);
    assert.equal(toolNames.includes("google_calendar_list_events"), false);
  });
});

describe("classifyCallToolError", () => {
  it("returns null for successful results", () => {
    assert.equal(classifyCallToolError({ ok: true, data: {} }), null);
  });

  it("classifies a pending preview token as pending before any other kind", () => {
    const state = classifyCallToolError({
      ok: false,
      data: null,
      pending: true,
      errorMessage: "connector_token_pending: the preview has not received the connector token yet",
    });
    assert.equal(state?.kind, "pending");
    assert.match(state?.message ?? "", /Connecting/);
    assert.match(state?.detail ?? "", /connector_token_pending/);
  });

  it("classifies a deployed missing token as error, not a login CTA", () => {
    const state = classifyCallToolError({
      ok: false,
      data: null,
      errorMessage: "missing_connector_token: open this app through the edge gate",
    });
    assert.equal(state?.kind, "error");
    assert.match(state?.detail ?? "", /missing_connector_token/);
  });

  it("classifies gate loginRequired without a missing-token message as login", () => {
    const state = classifyCallToolError({
      ok: false,
      data: null,
      loginRequired: true,
      errorMessage: "login required",
    });
    assert.equal(state?.kind, "login");
    assert.equal(state?.detail, "login required");
  });

  it("classifies not_connected and failed_precondition", () => {
    assert.equal(
      classifyCallToolError({
        ok: false,
        data: null,
        errorMessage: "connector_not_connected: Notion",
      })?.kind,
      "not_connected",
    );
    assert.equal(
      classifyCallToolError({
        ok: false,
        data: null,
        errorMessage: "FAILED_PRECONDITION: no connector",
      })?.kind,
      "not_connected",
    );
  });

  it("classifies scope_denied without claiming a missing grant", () => {
    const state = classifyCallToolError({
      ok: false,
      data: null,
      errorMessage: "scope_denied: tool notion-list-recent-pages not in grant scopes",
    });
    assert.equal(state?.kind, "scope_denied");
    assert.match(state?.message ?? "", /tool outside its grant/);
    assert.match(state?.detail ?? "", /notion-list-recent-pages/);
  });

  it("classifies access_denied", () => {
    assert.equal(
      classifyCallToolError({
        ok: false,
        data: null,
        errorMessage: "access_denied",
      })?.kind,
      "access_denied",
    );
  });

  it("falls back to a generic error with the raw message", () => {
    const state = classifyCallToolError({
      ok: false,
      data: null,
      errorMessage: "boom",
    });
    assert.equal(state?.kind, "error");
    assert.equal(state?.message, "boom");
    const empty = classifyCallToolError({ ok: false, data: null });
    assert.equal(empty?.kind, "error");
    assert.equal(empty?.message, "Something went wrong. Try again.");
    assert.equal(empty?.detail, undefined);
  });
});

````

## `frontend_demo/src/lib/app-data/client.server.ts`
````ts
import { createHash } from "node:crypto";
import { getRequest } from "@tanstack/react-start/server";
import {
  assertSameSiteRequest,
  CrossSiteRequestError,
} from "../auth/isolation.server.ts";
import { env, isWorkspacePreview } from "../env.server.ts";
import { assertAppDataServerOnly } from "./server-only.ts";
import {
  CONNECTOR_TOKEN_HEADER,
  CONNECTOR_TOKEN_PENDING_CODE,
  ConnectorType,
  type CallToolOptions,
  type CallToolResult,
  type ToolArgs,
} from "./types.ts";

assertAppDataServerOnly("app-data/client.server");

export const CONNECTORS_HOST_STAGING = "connectors.app-builder-testing.com";
export const CONNECTORS_HOST_PROD = "connectors.grok.me";

function isLoopbackHost(host: string): boolean {
  return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
}

type InboundContext = {
  token: string | null;
  publicHost: string | null;
  connectorsBase: string | null;
};

function connectorsBaseFor(publicHost: string | null): string | null {
  const explicit = env("GROK_CONNECTORS_URL");
  if (explicit) return explicit.replace(/\/+$/, "");

  const host = publicHost?.toLowerCase();
  if (!host || isLoopbackHost(host)) return null;
  if (
    host === "app-builder-testing.com" ||
    host.endsWith(".app-builder-testing.com")
  ) {
    return `https://${CONNECTORS_HOST_STAGING}`;
  }
  if (host === "grok.me" || host.endsWith(".grok.me")) {
    return `https://${CONNECTORS_HOST_PROD}`;
  }
  return null;
}

function tryGetRequest(): Request | null {
  try {
    return getRequest() ?? null;
  } catch {
    return null;
  }
}

function inboundContext(): InboundContext {
  const req = tryGetRequest();
  const xf = req?.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const publicHost =
    (xf || req?.headers.get("host") || "").split(":")[0]?.trim() || null;
  const headerToken = req?.headers.get(CONNECTOR_TOKEN_HEADER)?.trim() || null;
  const envToken =
    process.env.NODE_ENV === "production"
      ? null
      : (env("GROK_CONNECTOR_ACCESS_TOKEN") ?? null);
  return {
    token: headerToken ?? envToken,
    publicHost,
    connectorsBase: connectorsBaseFor(publicHost),
  };
}

export function resolveGateAppDataBase(): string | null {
  return inboundContext().connectorsBase;
}

export function getConnectorAccessToken(): string | null {
  return inboundContext().token;
}

export { isWorkspacePreview } from "../env.server.ts";

// Digest of the last preview token the gate answered 401 for. The readiness
// probe reports "not ready" while that exact token is still the one on the
// request, so the client waits for the preview panel to push a fresh token
// instead of re-calling the gate with a token already known to be rejected.
let rejectedTokenDigest: string | null = null;

function tokenDigest(token: string): string {
  return createHash("sha256").update(token).digest("base64url");
}

function noteTokenRejected(token: string): void {
  rejectedTokenDigest = tokenDigest(token);
}

function noteTokenAccepted(token: string): void {
  if (rejectedTokenDigest === tokenDigest(token)) rejectedTokenDigest = null;
}

/**
 * True when the inbound request carries a connector token the gate has not
 * rejected. This is what the preview readiness probe reports; it never calls
 * the gate.
 */
export function isConnectorTokenReady(): boolean {
  const token = inboundContext().token;
  return token !== null && tokenDigest(token) !== rejectedTokenDigest;
}

type GateJson = {
  ok?: boolean;
  data?: unknown;
  errorMessage?: string;
  loginUrl?: string;
};

async function gatePost(
  ctx: InboundContext,
  body: Record<string, unknown>,
  token: string,
): Promise<{ status: number; json: GateJson }> {
  const base = ctx.connectorsBase;
  if (!base) {
    throw new Error(
      "cannot resolve gate host (missing x-forwarded-host/host on the server request); " +
        "open the app through the gated public URL so the gate can proxy and inject credentials",
    );
  }

  if (!/^https?:\/\//i.test(base)) {
    throw new Error(
      `gate base must be absolute http(s) URL (got ${base}); refusing relative fetch`,
    );
  }

  const headers: Record<string, string> = {
    "content-type": "application/json",
    accept: "application/json",
    authorization: `Bearer ${token}`,
  };
  if (ctx.publicHost) {
    headers["x-forwarded-host"] = ctx.publicHost;
  }

  const res = await fetch(`${base}/call-tool`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    redirect: "manual",
  });

  let json: GateJson = {};
  const text = await res.text();
  if (text) {
    try {
      json = JSON.parse(text) as GateJson;
    } catch {
      json = {
        ok: false,
        errorMessage: `gate non-JSON response (HTTP ${res.status}): ${text.slice(0, 200)}`,
      };
    }
  }

  return { status: res.status, json };
}

function gateSigninUrl(ctx: InboundContext): string | undefined {
  const base = ctx.connectorsBase;
  if (!base) return undefined;
  try {
    const connectorsHost = new URL(base).host.toLowerCase();
    const gateHost = connectorsHost.replace(/^connectors\./, "gate.");
    if (gateHost === connectorsHost) return undefined;
    const publicHost = ctx.publicHost?.toLowerCase();
    const gated =
      publicHost && !isLoopbackHost(publicHost)
        ? `https://${publicHost}`
        : undefined;
    const signin = `https://${gateHost}/__gate/signin`;
    return gated
      ? `${signin}?return_to=${encodeURIComponent(gated)}`
      : signin;
  } catch {
    return undefined;
  }
}

const PENDING_TOKEN_MISSING =
  "the preview has not received the connector token yet; it arrives once " +
  "the connector grant is approved";
const PENDING_TOKEN_REJECTED =
  "the gate rejected the current preview token; the preview panel pushes a " +
  "fresh one on its own schedule";

function pendingTokenResult(reason: string): CallToolResult {
  return {
    ok: false,
    data: null,
    pending: true,
    errorMessage: `${CONNECTOR_TOKEN_PENDING_CODE}: ${reason}`,
  };
}

// Deployed apps only reach here when the request bypassed the gate (the gate
// injects the token on every proxied request), so a sign-in redirect cannot
// fix it: no loginRequired / loginUrl.
function missingAuthResult(): CallToolResult {
  if (isWorkspacePreview()) return pendingTokenResult(PENDING_TOKEN_MISSING);
  return {
    ok: false,
    data: null,
    errorMessage:
      "missing_connector_token: open this app through the edge gate " +
      "(the server must receive x-connector-access-token on the inbound request)",
  };
}

function unauthorizedResult(
  ctx: InboundContext,
  json: GateJson,
  token: string,
): CallToolResult {
  if (isWorkspacePreview()) {
    noteTokenRejected(token);
    return pendingTokenResult(PENDING_TOKEN_REJECTED);
  }
  const loginUrl =
    gateSigninUrl(ctx) ??
    (typeof json.loginUrl === "string" && json.loginUrl
      ? json.loginUrl
      : undefined);
  return {
    ok: false,
    data: null,
    loginRequired: true,
    errorMessage: json.errorMessage ?? "login required",
    ...(loginUrl ? { loginUrl } : {}),
  };
}

function crossSiteBlockedResult(): CallToolResult | null {
  try {
    assertSameSiteRequest();
    return null;
  } catch (e) {
    if (e instanceof CrossSiteRequestError) {
      return { ok: false, data: null, errorMessage: e.message };
    }
    return null;
  }
}

const FAILURE_MEMO_TTL_MS = 5_000;
const failureMemo = new Map<string, { at: number; result: CallToolResult }>();

function tokenIdentityKey(token: string): string {
  const payload = token.split(".")[1];
  if (payload) {
    try {
      const claims: unknown = JSON.parse(
        Buffer.from(payload, "base64url").toString("utf8"),
      );
      if (claims && typeof claims === "object" && !Array.isArray(claims)) {
        const { sub, team_id: teamId } = claims as {
          sub?: unknown;
          team_id?: unknown;
        };
        if (typeof sub === "string" && sub) {
          return createHash("sha256")
            .update(
              JSON.stringify([sub, typeof teamId === "string" ? teamId : null]),
            )
            .digest("base64url");
        }
      }
    } catch {}
  }
  return createHash("sha256").update(token).digest("base64url");
}

function memoizedFailure(key: string | null): CallToolResult | null {
  if (!key) return null;
  const hit = failureMemo.get(key);
  if (!hit) return null;
  if (Date.now() - hit.at > FAILURE_MEMO_TTL_MS) {
    failureMemo.delete(key);
    return null;
  }
  return hit.result;
}

function memoizeFailure(
  key: string | null,
  result: CallToolResult,
): CallToolResult {
  if (!key) return result;
  const now = Date.now();
  for (const [staleKey, entry] of failureMemo) {
    if (now - entry.at > FAILURE_MEMO_TTL_MS) failureMemo.delete(staleKey);
  }
  failureMemo.set(key, { at: now, result });
  return result;
}

export function failureMemoSize(): number {
  return failureMemo.size;
}

function safeMemoKey(parts: unknown[]): string | null {
  try {
    return JSON.stringify(parts);
  } catch {
    return null;
  }
}

function nonPostBlockedResult(): CallToolResult | null {
  const req = tryGetRequest();
  if (!req || req.method === "POST") return null;
  return {
    ok: false,
    data: null,
    errorMessage:
      `blocked ${req.method} inbound request: connector calls must run inside ` +
      'a createServerFn({ method: "POST" }) handler',
  };
}

export async function callTool(
  toolName: string,
  args: ToolArgs,
  options: CallToolOptions,
): Promise<CallToolResult> {
  const blocked = crossSiteBlockedResult() ?? nonPostBlockedResult();
  if (blocked) return blocked;

  const ctx = inboundContext();
  const token = options.token ?? ctx.token;
  if (!token) {
    return missingAuthResult();
  }

  const connectorType = options.connectorType;
  if (!connectorType) {
    return {
      ok: false,
      data: null,
      errorMessage:
        "connectorType is required: pass the connector type granted to this app " +
        "(e.g. { connectorType: ConnectorType.GoogleDrive })",
    };
  }

  const memoKey = safeMemoKey([
    toolName,
    args,
    connectorType,
    options?.connectorCatalogId ?? null,
    tokenIdentityKey(token),
  ]);
  const memoized = memoizedFailure(memoKey);
  if (memoized) {
    return memoized;
  }
  const fail = (errorMessage: string): CallToolResult =>
    memoizeFailure(memoKey, { ok: false, data: null, errorMessage });
  if (connectorType === ConnectorType.Mcp && !options?.connectorCatalogId) {
    return {
      ok: false,
      data: null,
      errorMessage: "connectorCatalogId is required when connectorType is Mcp",
    };
  }

  try {
    const { status, json } = await gatePost(
      ctx,
      {
        host: ctx.publicHost ?? undefined,
        connector_type: connectorType,
        tool_name: toolName,
        arguments: args,
        connector_catalog_id: options.connectorCatalogId,
      },
      token,
    );

    if (status === 401) {
      return unauthorizedResult(ctx, json, token);
    }
    noteTokenAccepted(token);
    if (status === 403) {
      return fail(json.errorMessage ?? "access_denied");
    }
    if (json.errorMessage && json.ok === false) {
      return fail(json.errorMessage);
    }
    if (status >= 400 && json.ok !== true) {
      return fail(json.errorMessage ?? `HTTP ${status}`);
    }
    if (json.ok === false) {
      return fail(json.errorMessage ?? "tool error");
    }
    return { ok: true, data: json.data ?? null };
  } catch (e) {
    return fail(e instanceof Error ? e.message : String(e));
  }
}

export {
  ConnectorType,
  GoogleCalendarTools,
  GoogleDriveTools,
  CONNECTOR_TOKEN_HEADER,
} from "./types.ts";
export type {
  CallToolResult,
  CallToolOptions,
  ToolArgs,
  ConnectorTypeName,
} from "./types.ts";
export { isLoginRequired, redirectToLoginIfRequired } from "./login.ts";

````

## `frontend_demo/src/lib/app-data/errors.ts`
````ts
import type { CallToolResult } from "./types.ts";
import { isConnectorPending, isLoginRequired } from "./login.ts";

export type CallToolErrorKind =
  | "pending"
  | "login"
  | "not_connected"
  | "scope_denied"
  | "access_denied"
  | "error";

export type CallToolErrorState = {
  kind: CallToolErrorKind;
  message: string;
  detail?: string;
};

type MessageRule = {
  needles: readonly string[];
  kind: CallToolErrorKind;
  message: string;
};

const MESSAGE_RULES: readonly MessageRule[] = [
  {
    needles: ["not_connected", "failed_precondition"],
    kind: "not_connected",
    message: "Connect this connector in Grok to load your data.",
  },
  {
    needles: ["scope_denied"],
    kind: "scope_denied",
    message: "This view isn't available — the app requested a tool outside its grant.",
  },
  {
    needles: ["access_denied"],
    kind: "access_denied",
    message: "You don't have access to this data.",
  },
];

function matchMessageRule(raw: string): MessageRule | undefined {
  return MESSAGE_RULES.find((rule) =>
    rule.needles.some((needle) => raw.includes(needle)),
  );
}

export function classifyCallToolError(
  result: CallToolResult,
): CallToolErrorState | null {
  if (result.ok) return null;
  const detail = result.errorMessage || undefined;
  const raw = (result.errorMessage ?? "").toLowerCase();
  if (isConnectorPending(result)) {
    return { kind: "pending", message: "Connecting to your data…", detail };
  }
  if (raw.includes("missing_connector_token")) {
    return {
      kind: "error",
      message: "Open this app from Grok to load your data.",
      detail,
    };
  }
  if (isLoginRequired(result)) {
    return {
      kind: "login",
      message: "Continue with Grok to load your data.",
      detail,
    };
  }
  const rule = matchMessageRule(raw);
  if (rule) return { kind: rule.kind, message: rule.message, detail };
  return {
    kind: "error",
    message: detail ?? "Something went wrong. Try again.",
    detail,
  };
}

````

## `frontend_demo/src/lib/app-data/index.ts`
````ts
export {
  CONNECTOR_TOKEN_HEADER,
  ConnectorType,
  GoogleCalendarTools,
  GoogleDriveTools,
} from "./types.ts";
export type {
  CallToolOptions,
  CallToolResult,
  ConnectorTypeName,
  ToolArgs,
} from "./types.ts";
export {
  isConnectorPending,
  isLoginRequired,
  redirectToLoginIfRequired,
} from "./login.ts";
export { classifyCallToolError } from "./errors.ts";
export type { CallToolErrorKind, CallToolErrorState } from "./errors.ts";
export { useRefetchWhenConnectorReady } from "./use-connector-readiness.ts";
export type { ConnectorWaitStatus } from "./use-connector-readiness.ts";

````

## `frontend_demo/src/lib/app-data/login.ts`
````ts
import type { CallToolResult } from "./types.ts";

export function isLoginRequired(result: CallToolResult): boolean {
  return result.ok === false && result.loginRequired === true;
}

export function isConnectorPending(result: CallToolResult): boolean {
  return result.ok === false && result.pending === true;
}

export function isFramed(): boolean {
  try {
    return window.self !== window.top;
  } catch {
    return true;
  }
}

export function redirectToLoginIfRequired(result: CallToolResult): boolean {
  if (!isLoginRequired(result)) return false;
  const url = result.loginUrl;
  if (!url) return false;
  if (typeof window === "undefined") return false;
  if (isFramed()) {
    const opened = window.open(url, "_blank");
    if (opened) {
      opened.opener = null;
      return true;
    }
  }
  window.location.assign(url);
  return true;
}

````

## `frontend_demo/src/lib/app-data/readiness-schedule.test.ts`
````ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  READINESS_PROBE_DELAYS_MS,
  READINESS_PROBE_MAX_TOTAL_MS,
  readinessProbeDelayMs,
  readinessProbeExhausted,
} from "./readiness-schedule.ts";

describe("readinessProbeDelayMs", () => {
  it("backs off through the schedule and then holds the last delay", () => {
    const last = READINESS_PROBE_DELAYS_MS[READINESS_PROBE_DELAYS_MS.length - 1];
    assert.deepEqual(
      [0, 1, 2, 3, 4, 50].map(readinessProbeDelayMs),
      [...READINESS_PROBE_DELAYS_MS, last, last],
    );
  });

  it("clamps a negative attempt to the first delay", () => {
    assert.equal(readinessProbeDelayMs(-3), READINESS_PROBE_DELAYS_MS[0]);
  });
});

describe("readinessProbeExhausted", () => {
  it("gives up only once the total wait budget has elapsed", () => {
    assert.equal(readinessProbeExhausted(1_000, 1_000), false);
    assert.equal(
      readinessProbeExhausted(1_000, 1_000 + READINESS_PROBE_MAX_TOTAL_MS - 1),
      false,
    );
    assert.equal(
      readinessProbeExhausted(1_000, 1_000 + READINESS_PROBE_MAX_TOTAL_MS),
      true,
    );
  });
});

````

## `frontend_demo/src/lib/app-data/readiness-schedule.ts`
````ts
export const READINESS_PROBE_DELAYS_MS = [1_000, 2_000, 3_000, 5_000] as const;

export const READINESS_PROBE_MAX_TOTAL_MS = 3 * 60_000;

export function readinessProbeDelayMs(attempt: number): number {
  const index = Math.min(
    Math.max(attempt, 0),
    READINESS_PROBE_DELAYS_MS.length - 1,
  );
  return READINESS_PROBE_DELAYS_MS[index];
}

export function readinessProbeExhausted(
  startedAtMs: number,
  nowMs: number,
): boolean {
  return nowMs - startedAtMs >= READINESS_PROBE_MAX_TOTAL_MS;
}

````

## `frontend_demo/src/lib/app-data/readiness.ts`
````ts
import { createServerFn } from "@tanstack/react-start";

export type ConnectorReadiness = { ready: boolean };

export const getConnectorReadiness = createServerFn({ method: "POST" }).handler(
  async (): Promise<ConnectorReadiness> => {
    const { isConnectorTokenReady } = await import("./client.server.ts");
    return { ready: isConnectorTokenReady() };
  },
);

````

## `frontend_demo/src/lib/app-data/server-only.ts`
````ts
export function assertAppDataServerOnly(
  context = "app-data/client.server",
): void {
  if (typeof window !== "undefined") {
    throw new Error(
      `@/lib/${context} is server-only. Call connector tools from a createServerFn handler (dynamic import of @/lib/app-data/client.server), never from a React component, useEffect, or browser fetch. Types and login helpers are client-safe via @/lib/app-data.`,
    );
  }
}

assertAppDataServerOnly("app-data/client.server");

````

## `frontend_demo/src/lib/app-data/types.ts`
````ts
export const CONNECTOR_TOKEN_HEADER = "x-connector-access-token";

export const CONNECTOR_TOKEN_PENDING_CODE = "connector_token_pending";

export const CONNECTOR_TOKEN_READY_EVENT = "grok:connector-token-ready";

export const ConnectorType = {
  GoogleDrive: "GoogleDrive",
  Gmail: "Gmail",
  GoogleCalendar: "GoogleCalendar",
  Outlook: "Outlook",
  OutlookCalendar: "OutlookCalendar",
  MicrosoftTeams: "MicrosoftTeams",
  Mcp: "Mcp",
} as const;

export type ConnectorTypeName =
  (typeof ConnectorType)[keyof typeof ConnectorType];

export const GoogleDriveTools = {
  search: "google_drive_search",
  readFile: "google_drive_read_file",
  listFolder: "google_drive_list_folder",
  createFolder: "google_drive_create_folder",
  trashFile: "google_drive_trash_file",
} as const;

export const GoogleCalendarTools = {
  listCalendars: "google_calendar_list_calendars",
  search: "google_calendar_search",
  getEvent: "google_calendar_get_event",
  availability: "google_calendar_availability",
} as const;

export type CallToolResult<T = unknown> = {
  ok: boolean;
  data: T | null;
  errorMessage?: string;
  loginRequired?: boolean;
  loginUrl?: string;
  pending?: boolean;
};

export type CallToolOptions = {
  connectorType: ConnectorTypeName;
  connectorCatalogId?: string;
  token?: string | null;
};

export type ToolArgs = Record<string, unknown>;

````

## `frontend_demo/src/lib/app-data/use-connector-readiness.ts`
````ts
import { useEffect, useRef, useState } from "react";
import { isFramed } from "./login.ts";
import { getConnectorReadiness } from "./readiness.ts";
import {
  READINESS_PROBE_MAX_TOTAL_MS,
  readinessProbeDelayMs,
  readinessProbeExhausted,
} from "./readiness-schedule.ts";
import { CONNECTOR_TOKEN_READY_EVENT } from "./types.ts";

export type ConnectorWaitStatus =
  | "idle"
  | "waiting"
  | "timed_out"
  | "not_embedded";

export const READINESS_PROBE_TIMEOUT_MS = 10_000;

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | null> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), ms);
    const settle = (value: T | null) => {
      clearTimeout(timer);
      resolve(value);
    };
    promise.then(settle, () => settle(null));
  });
}

async function isConnectorReady(): Promise<boolean> {
  const result = await withTimeout(
    getConnectorReadiness(),
    READINESS_PROBE_TIMEOUT_MS,
  );
  return result?.ready === true;
}

/**
 * While `waiting` is true (a connector call returned `pending`), probes the
 * server for the connector token and calls `refetch` once it is present. The
 * probe is a header check on the app's own server — it never reaches the gate.
 * A `connector-token-ready` bridge event from the Grok preview chrome triggers
 * `refetch` immediately. A top-level page (download/export, local dev, the
 * sandbox's own `npm run preview`) is not framed by any preview, so no token
 * can ever arrive: the hook reports `not_embedded` without probing. Any framed
 * page probes, even when the parent origin cannot be resolved (empty referrer,
 * no `ancestorOrigins`): the token comes through the preview proxy, and the
 * bridge event is only the faster signal.
 */
export function useRefetchWhenConnectorReady(
  waiting: boolean,
  refetch: () => unknown,
): ConnectorWaitStatus {
  const refetchRef = useRef(refetch);
  const [timedOut, setTimedOut] = useState(false);
  const [notEmbedded, setNotEmbedded] = useState(false);

  useEffect(() => {
    refetchRef.current = refetch;
  }, [refetch]);

  useEffect(() => {
    if (!waiting) return;
    if (!isFramed()) {
      setNotEmbedded(true);
      return () => setNotEmbedded(false);
    }
    let cancelled = false;
    let refetching = false;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();

    const runRefetch = async () => {
      if (refetching) return;
      refetching = true;
      try {
        await refetchRef.current();
      } catch {
        // The query owns its own error state; a failed refetch must not stop
        // the probe loop.
      } finally {
        refetching = false;
      }
    };
    const schedule = () => {
      timer = setTimeout(probe, readinessProbeDelayMs(attempt));
      attempt += 1;
    };
    const probe = async () => {
      if (cancelled || readinessProbeExhausted(startedAt, Date.now())) return;
      const ready = await isConnectorReady();
      if (cancelled) return;
      if (ready) await runRefetch();
      if (!cancelled) schedule();
    };
    const onTokenReady = () => {
      void runRefetch();
    };
    // Time-based terminal state: a probe that never settles or a refetch that
    // throws cannot leave the UI on "waiting" forever.
    const deadline = setTimeout(() => {
      if (!cancelled) setTimedOut(true);
    }, READINESS_PROBE_MAX_TOTAL_MS);

    window.addEventListener(CONNECTOR_TOKEN_READY_EVENT, onTokenReady);
    schedule();
    return () => {
      cancelled = true;
      clearTimeout(deadline);
      if (timer !== undefined) clearTimeout(timer);
      window.removeEventListener(CONNECTOR_TOKEN_READY_EVENT, onTokenReady);
      setTimedOut(false);
    };
  }, [waiting]);

  if (!waiting) return "idle";
  if (notEmbedded) return "not_embedded";
  return timedOut ? "timed_out" : "waiting";
}

````

## `frontend_demo/src/lib/auth/client.ts`
````ts
import { genericOAuthClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";
import { runPreSignInSignOut, runSignOut } from "../../../scripts/sign-out-plan.mjs";
import { GROK_PROVIDERS } from "./providers";

/**
 * Better Auth client for this React SPA (browser-side).
 *
 * Talks to this app's OWN Better Auth at same-origin `/api/auth/*`. In the live
 * preview the app is an embedded iframe with PARTITIONED cookies, so after a
 * popup sign-in it can't read the session cookie — it authenticates with a
 * bearer token instead (captured from the popup, see `signIn`). The `onRequest`
 * hook attaches that token when present; when deployed (cookie auth) no token
 * is stored, so nothing changes.
 *
 * To sign out call `signOut()` below, NOT `authClient.signOut()`: the raw call
 * leaves the bearer token in place, and `onRequest` keeps re-attaching it, so
 * the visitor stays signed in.
 */
export const authClient = createAuthClient({
  plugins: [genericOAuthClient()],
  fetchOptions: {
    onRequest(ctx) {
      const token = getBearerToken();
      if (token) ctx.headers.set("Authorization", `Bearer ${token}`);
      return ctx;
    },
  },
});

/**
 * True when sign-in UI should be shown — i.e. whenever `VITE_AUTH_ENABLED` is
 * not `"false"`. The shipped template sets it to `"false"`
 * (`.grok/app-env.json`), which selects the dev user (see `use-current-user`);
 * with the key removed, sign-in is real in preview (baked preview client) and
 * when deployed (injected per-app client).
 */
export const authEnabled = import.meta.env.VITE_AUTH_ENABLED !== "false";

/** The upstream providers to render sign-in buttons for. */
export { GROK_PROVIDERS };

// ── Live-preview bearer token ────────────────────────────────────────────────
// The embedded preview iframe has partitioned cookies, so we keep the session's
// bearer token in sessionStorage and attach it to every Better Auth request (and
// to server functions, via `@/lib/auth/middleware`). Empty everywhere except the
// preview after a popup sign-in, so the cookie path is untouched elsewhere.
const BEARER_KEY = "grok-auth.bearer-token";

/** The stored preview bearer token, or null. */
export function getBearerToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(BEARER_KEY);
  } catch {
    return null;
  }
}

function setBearerToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) window.sessionStorage.setItem(BEARER_KEY, token);
    else window.sessionStorage.removeItem(BEARER_KEY);
  } catch {
    /* storage unavailable — ignore */
  }
}

/**
 * The sandbox live preview runs this app inside an iframe on a `*.grok-sandbox.com`
 * host, where a full-page redirect to the broker can't work — so sign-in uses a
 * popup there and a normal redirect everywhere else.
 */
function inLivePreview(): boolean {
  return (
    typeof window !== "undefined" &&
    window.location.hostname.endsWith(".grok-sandbox.com")
  );
}

/** Message the popup posts back to the opener once sign-in completes. */
type PopupMessage = { source: "grok-auth-popup"; token: string | null; error?: string };

/**
 * Start sign-in with one upstream provider (`providerId` from `GROK_PROVIDERS`),
 * federating through the Grok auth broker.
 *
 * - **Live preview** (`*.grok-sandbox.com` iframe): opens a POPUP to
 *   `/auth/popup`, served by the template Vite plugin (see `vite.config.ts` +
 *   `popup.server.ts`) — 302s to the broker/upstream login (no app chrome) and,
 *   on return, posts the session bearer token back. We store it and refresh the
 *   session; no top-level navigation of the iframe to the broker.
 * - **Deployed** (and local non-iframe): a normal full-page redirect into the broker.
 *
 * Either way it clears any existing local session FIRST so switching providers
 * actually switches identity.
 */
export async function signIn(
  providerId: string,
  opts: { callbackURL?: string; errorCallbackURL?: string } = {},
): Promise<void> {
  const callbackURL = opts.callbackURL ?? "/";
  const errorCallbackURL = opts.errorCallbackURL ?? "/";

  // Open the popup SYNCHRONOUSLY on the user gesture — before any await
  // (including signOut). Awaiting first drops user-gesture privilege in some
  // browsers when the opener is a cross-origin live-preview iframe.
  const popup = inLivePreview() ? openSignInPopup(providerId) : null;

  // Clear any prior session so switching providers actually switches identity.
  // Bounded because the popup is already open — a request that never settles
  // would leave it hanging — but bounded PER ENVIRONMENT: only the server can
  // end a deployed session, so cutting it short at the preview's 1.5s would
  // start OAuth with the old session still live.
  await runPreSignInSignOut({
    livePreview: inLivePreview(),
    hasBearer: Boolean(getBearerToken()),
    requestSignOut: () => authClient.signOut(),
    clearToken: () => setBearerToken(null),
  });

  if (inLivePreview()) {
    if (!popup) throw new Error("Pop-up blocked — allow pop-ups for sign-in");
    const token = await waitForPopupToken(popup);
    if (!token) throw new Error("Sign-in was cancelled or failed");
    setBearerToken(token);
    // Refresh the client session store with the bearer attached (onRequest).
    // Avoid a full iframe reload when we're already on the destination — that
    // reload was the slow "still loading after the popup closed" feeling.
    try {
      await authClient.getSession();
    } catch {
      /* session store will recover on next useSession fetch */
    }
    if (typeof window !== "undefined") {
      const dest = new URL(callbackURL, window.location.origin);
      const here = window.location;
      if (dest.origin !== here.origin || dest.pathname !== here.pathname || dest.search !== here.search) {
        window.location.href = callbackURL;
      }
    }
    return;
  }

  const { data, error } = await authClient.signIn.oauth2({
    providerId,
    callbackURL,
    errorCallbackURL,
  });
  if (error) throw new Error(error.message ?? "Sign-in failed");
  if (data?.url) window.location.href = data.url;
}

/**
 * Open `/auth/popup` in a new window. Must run synchronously inside the click
 * handler (no await before this). The path is served by the template Vite
 * plugin (`authPopupPlugin` in vite.config.ts) — NOT by a React route.
 *
 * Opens the real URL directly (not about:blank → assign). From a cross-origin
 * iframe the about:blank dance often fails on the first click and the window
 * ends up showing the app shell.
 */
function openSignInPopup(providerId: string): Window | null {
  const origin = window.location.origin;
  const url = `${origin}/auth/popup?providerId=${encodeURIComponent(providerId)}`;
  // Unique name per attempt so a prior attempt stuck on the SPA is not reused.
  const name = `grok-signin-${Date.now()}`;
  return window.open(url, name, "popup,width=500,height=650");
}

/**
 * Wait for the popup's completion page to postMessage the session bearer (or
 * for the user to dismiss the popup).
 */
function waitForPopupToken(popup: Window): Promise<string | null> {
  return new Promise((resolve) => {
    const origin = window.location.origin;
    let settled = false;
    let closeTimer: number | undefined;
    const settle = (token: string | null) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(token);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== origin) return;
      const data = event.data as PopupMessage | undefined;
      if (!data || data.source !== "grok-auth-popup") return;
      settle(data.token ?? null);
    };
    // Fallback when the user dismisses the popup. Grace period lets the
    // completion page's postMessage win over a racing `popup.closed`.
    const pollTimer = window.setInterval(() => {
      if (!popup.closed) return;
      window.clearInterval(pollTimer);
      closeTimer = window.setTimeout(() => settle(null), 400);
    }, 300);
    function cleanup() {
      window.clearInterval(pollTimer);
      if (closeTimer !== undefined) window.clearTimeout(closeTimer);
      window.removeEventListener("message", onMessage);
    }
    window.addEventListener("message", onMessage);
  });
}

/**
 * Sign out of THIS app's local session, clear the preview token, then redirect.
 *
 * Use this, never `authClient.signOut()` — see the note on `authClient`.
 * Sequencing lives in `scripts/sign-out-plan.mjs` so it can be unit-tested.
 *
 * **Rejects when deployed if the server never confirms.** There the session is
 * an HttpOnly cookie only the server can clear, so redirecting anyway would
 * report a sign-out that did not happen. `<UserButton />` handles that for you;
 * a hand-rolled control must catch it and let the visitor retry. In the live
 * preview the local clear is sufficient, so it always resolves.
 */
export async function signOut(redirectTo = "/"): Promise<void> {
  await runSignOut({
    livePreview: inLivePreview(),
    hasBearer: Boolean(getBearerToken()),
    // Better Auth resolves with `{ error }` instead of rejecting, so surface a
    // failed response as a rejection for the sequence to act on.
    requestSignOut: async () => {
      const { error } = await authClient.signOut();
      if (error) throw new Error(error.message ?? "Sign-out failed");
    },
    clearToken: () => setBearerToken(null),
    redirect: () => {
      window.location.href = redirectTo;
    },
  });
}

````

## `frontend_demo/src/lib/auth/email-password.ts`
````ts
/**
 * Local email/password sign-in (this app's Better Auth DB — not the broker).
 *
 * Off by default. To enable: set `emailAndPasswordEnabled` to `true` below,
 * then build sign-up / sign-in forms with `authClient.signUp.email` /
 * `authClient.signIn.email` from `@/lib/auth/client` (see the auth skill).
 *
 * Do NOT edit `server.ts` for this — that file is frozen pre-wired config.
 */
export const emailAndPasswordEnabled = false;

````

## `frontend_demo/src/lib/auth/gate-identity.server.ts`
````ts
import {
  importJWK,
  jwtVerify,
  type JWK,
  type JWTVerifyGetKey,
} from "jose";
import { env, isWorkspacePreview } from "../env.server.ts";

export const GATE_IDENTITY_HEADER = "x-grok-identity";
export const GATE_JWKS_PATH = "/__gate/identity-key";

const JWKS_CACHE_TTL_MS = 300_000;
const PREVIEW_AUDIENCE = "preview";
export const PREVIEW_GATE_ORIGIN = "http://127.0.0.1:6014";
const FALLBACK_EMAIL_DOMAIN = "viewer.grok.invalid";
const FALLBACK_NAME = "Grok user";

export type GateIdentity = {
  sub: string;
  email: string | null;
  name: string | null;
  teamId: string | null;
};

export type GateJwks = { keys: JWK[] };

export type JwksFetch = (url: string) => Promise<GateJwks | null>;

export function gateIdentityEnabled(): boolean {
  return env("VITE_AUTH_ENABLED") !== "false";
}

export function gateTokenAudience(): string {
  if (isWorkspacePreview()) return PREVIEW_AUDIENCE;
  return `app:${env("GROK_PROJECT_ID")}`;
}

async function defaultJwksFetch(url: string): Promise<GateJwks | null> {
  try {
    const res = await fetch(url, {
      headers: { accept: "application/json" },
      redirect: "manual",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as GateJwks;
    return Array.isArray(body?.keys) ? body : null;
  } catch {
    return null;
  }
}

const jwksCache = new Map<string, { jwks: GateJwks; fetchedAt: number }>();

export function gateKeyResolver(
  url: string,
  jwksFetch: JwksFetch = defaultJwksFetch,
): JWTVerifyGetKey {
  return async (protectedHeader) => {
    const kid =
      typeof protectedHeader.kid === "string" ? protectedHeader.kid : undefined;
    const findKey = (jwks: GateJwks): JWK | undefined =>
      jwks.keys.find(
        (k) =>
          k.kty === "OKP" && k.crv === "Ed25519" && (!kid || k.kid === kid),
      );

    let entry = jwksCache.get(url);
    if (!entry || Date.now() - entry.fetchedAt > JWKS_CACHE_TTL_MS) {
      const jwks = await jwksFetch(url);
      if (jwks) {
        entry = { jwks, fetchedAt: Date.now() };
        jwksCache.set(url, entry);
      }
    }

    let key = entry ? findKey(entry.jwks) : undefined;
    if (!key) {
      const jwks = await jwksFetch(url);
      if (jwks) {
        entry = { jwks, fetchedAt: Date.now() };
        jwksCache.set(url, entry);
        key = findKey(jwks);
      }
    }
    if (!key) {
      throw new Error("no gate identity key matches the token kid");
    }
    return importJWK(key, "EdDSA");
  };
}

export type VerifyGateIdentityTokenOptions = {
  issuer: string;
  audience: string;
  getKey: JWTVerifyGetKey;
};

export async function verifyGateIdentityToken(
  token: string,
  options: VerifyGateIdentityTokenOptions,
): Promise<GateIdentity | null> {
  try {
    const { payload } = await jwtVerify(token, options.getKey, {
      algorithms: ["EdDSA"],
      issuer: options.issuer,
      audience: options.audience,
      requiredClaims: ["sub", "iat", "exp"],
      maxTokenAge: "10 minutes",
    });
    const sub = typeof payload.sub === "string" ? payload.sub.trim() : "";
    if (!sub) return null;
    return {
      sub,
      email: typeof payload.email === "string" ? payload.email : null,
      name: typeof payload.name === "string" ? payload.name : null,
      teamId: typeof payload.team_id === "string" ? payload.team_id : null,
    };
  } catch {
    return null;
  }
}

type GateEndpoints = { issuer: string; jwksUrl: string };

export function resolveGateEndpoints(headers: Headers): GateEndpoints | null {
  const explicit = env("GROK_GATE_ORIGIN");
  if (explicit) {
    const origin = explicit.replace(/\/+$/, "");
    return { issuer: origin, jwksUrl: `${origin}${GATE_JWKS_PATH}` };
  }

  if (isWorkspacePreview()) {
    return {
      issuer: PREVIEW_GATE_ORIGIN,
      jwksUrl: `${PREVIEW_GATE_ORIGIN}${GATE_JWKS_PATH}`,
    };
  }

  const xf = headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = (xf || headers.get("host") || "")
    .split(":")[0]
    ?.trim()
    .toLowerCase();
  if (!host) return null;

  let issuer: string | null = null;
  if (
    host === "app-builder-testing.com" ||
    host.endsWith(".app-builder-testing.com")
  ) {
    issuer = "https://gate.app-builder-testing.com";
  } else if (host === "grok.me" || host.endsWith(".grok.me")) {
    issuer = "https://gate.grok.me";
  }
  if (!issuer) return null;

  return { issuer, jwksUrl: `${issuer}${GATE_JWKS_PATH}` };
}

export type GateLinkedAccount = { providerId: string; accountId: string };

export function sessionBoundToGateIdentity(
  accounts: readonly GateLinkedAccount[],
  identitySub: string,
  gateProviderId: string,
): boolean {
  return accounts.some(
    (account) =>
      account.providerId === gateProviderId &&
      account.accountId === identitySub,
  );
}

export async function gateIdentityFromHeaders(
  headers: Headers,
  jwksFetch?: JwksFetch,
): Promise<GateIdentity | null> {
  if (!gateIdentityEnabled()) return null;
  const token = headers.get(GATE_IDENTITY_HEADER)?.trim();
  if (!token) return null;
  const endpoints = resolveGateEndpoints(headers);
  if (!endpoints) return null;
  return verifyGateIdentityToken(token, {
    issuer: endpoints.issuer,
    audience: gateTokenAudience(),
    getKey: gateKeyResolver(endpoints.jwksUrl, jwksFetch),
  });
}

export type GateUserInfo = {
  id: string;
  email: string;
  emailVerified: boolean;
  name: string;
};

export function gateIdentityUserInfo(identity: GateIdentity): GateUserInfo {
  return {
    id: identity.sub,
    email: (
      identity.email ?? `${identity.sub}@${FALLBACK_EMAIL_DOMAIN}`
    ).toLowerCase(),
    emailVerified: Boolean(identity.email),
    name: identity.name ?? FALLBACK_NAME,
  };
}

````

## `frontend_demo/src/lib/auth/gate-identity.test.ts`
````ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, type KeyObject } from "node:crypto";
import { SignJWT, exportJWK, type JWK } from "jose";
import {
  gateIdentityEnabled,
  gateIdentityFromHeaders,
  gateIdentityUserInfo,
  gateKeyResolver,
  gateTokenAudience,
  sessionBoundToGateIdentity,
  verifyGateIdentityToken,
  type GateJwks,
} from "./gate-identity.server.ts";

const ISSUER = "https://gate.app-builder-testing.com";
const AUDIENCE = "app:proj-123";

type TestKey = { privateKey: KeyObject; jwk: JWK; kid: string };

async function makeKey(kid: string): Promise<TestKey> {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const jwk = await exportJWK(publicKey);
  return {
    privateKey,
    kid,
    jwk: { ...jwk, alg: "EdDSA", use: "sig", kid },
  };
}

type SignOptions = {
  issuer?: string;
  audience?: string;
  expiresIn?: number;
  issuedAt?: number;
  omitExp?: boolean;
};

async function signToken(
  key: TestKey,
  claims: Record<string, unknown>,
  options: SignOptions = {},
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const jwt = new SignJWT(claims)
    .setProtectedHeader({ alg: "EdDSA", kid: key.kid })
    .setIssuer(options.issuer ?? ISSUER)
    .setAudience(options.audience ?? AUDIENCE)
    .setIssuedAt(options.issuedAt ?? now);
  if (!options.omitExp) {
    jwt.setExpirationTime((options.issuedAt ?? now) + (options.expiresIn ?? 300));
  }
  return jwt.sign(key.privateKey);
}

function staticJwks(keys: JWK[]): {
  fetchImpl: (url: string) => Promise<GateJwks | null>;
  calls: () => number;
} {
  let count = 0;
  return {
    fetchImpl: async () => {
      count += 1;
      return { keys };
    },
    calls: () => count,
  };
}

let urlCounter = 0;
function uniqueUrl(): string {
  urlCounter += 1;
  return `https://test-${urlCounter}.invalid/__gate/identity-key`;
}

describe("verifyGateIdentityToken", () => {
  it("returns the identity for a valid token", async () => {
    const key = await makeKey("k1");
    const token = await signToken(key, {
      sub: "user-1",
      email: "viewer@example.com",
      name: "Viewer",
      team_id: "team-9",
      jti: "j1",
    });
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([key.jwk]).fetchImpl),
    });
    assert.deepEqual(identity, {
      sub: "user-1",
      email: "viewer@example.com",
      name: "Viewer",
      teamId: "team-9",
    });
  });

  it("omits optional claims as nulls", async () => {
    const key = await makeKey("k1");
    const token = await signToken(key, { sub: "user-2", jti: "j2" });
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([key.jwk]).fetchImpl),
    });
    assert.deepEqual(identity, {
      sub: "user-2",
      email: null,
      name: null,
      teamId: null,
    });
  });

  it("rejects a wrong audience", async () => {
    const key = await makeKey("k1");
    const token = await signToken(
      key,
      { sub: "user-1" },
      { audience: "app:other-project" },
    );
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([key.jwk]).fetchImpl),
    });
    assert.equal(identity, null);
  });

  it("rejects a wrong issuer", async () => {
    const key = await makeKey("k1");
    const token = await signToken(
      key,
      { sub: "user-1" },
      { issuer: "https://evil.example.com" },
    );
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([key.jwk]).fetchImpl),
    });
    assert.equal(identity, null);
  });

  it("rejects an expired token", async () => {
    const key = await makeKey("k1");
    const past = Math.floor(Date.now() / 1000) - 3600;
    const token = await signToken(
      key,
      { sub: "user-1" },
      { issuedAt: past, expiresIn: 300 },
    );
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([key.jwk]).fetchImpl),
    });
    assert.equal(identity, null);
  });

  it("rejects a token without exp", async () => {
    const key = await makeKey("k1");
    const token = await signToken(key, { sub: "user-1" }, { omitExp: true });
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([key.jwk]).fetchImpl),
    });
    assert.equal(identity, null);
  });

  it("rejects a token signed by a different key with the same kid", async () => {
    const trusted = await makeKey("k1");
    const attacker = await makeKey("k1");
    const token = await signToken(attacker, { sub: "user-1" });
    const identity = await verifyGateIdentityToken(token, {
      issuer: ISSUER,
      audience: AUDIENCE,
      getKey: gateKeyResolver(uniqueUrl(), staticJwks([trusted.jwk]).fetchImpl),
    });
    assert.equal(identity, null);
  });

  it("refetches the JWKS when the kid rotates", async () => {
    const oldKey = await makeKey("k-old");
    const newKey = await makeKey("k-new");
    const url = uniqueUrl();
    let calls = 0;
    let published: JWK[] = [oldKey.jwk];
    const fetchImpl = async (): Promise<GateJwks> => {
      calls += 1;
      return { keys: published };
    };
    const getKey = gateKeyResolver(url, fetchImpl);

    const first = await verifyGateIdentityToken(
      await signToken(oldKey, { sub: "user-1" }),
      { issuer: ISSUER, audience: AUDIENCE, getKey },
    );
    assert.equal(first?.sub, "user-1");
    assert.equal(calls, 1);

    published = [newKey.jwk];
    const second = await verifyGateIdentityToken(
      await signToken(newKey, { sub: "user-1" }),
      { issuer: ISSUER, audience: AUDIENCE, getKey },
    );
    assert.equal(second?.sub, "user-1");
    assert.equal(calls, 2);
  });
});

describe("gateIdentityFromHeaders", () => {
  it("verifies the header token end to end and fails closed without it", async () => {
    const key = await makeKey("k1");
    const { fetchImpl } = staticJwks([key.jwk]);
    process.env.GROK_PROJECT_ID = "proj-123";
    process.env.GROK_GATE_ORIGIN = ISSUER;
    try {
      const token = await signToken(key, {
        sub: "user-1",
        email: "viewer@example.com",
      });
      const withToken = await gateIdentityFromHeaders(
        new Headers({ "x-grok-identity": token }),
        fetchImpl,
      );
      assert.equal(withToken?.sub, "user-1");

      const withoutToken = await gateIdentityFromHeaders(
        new Headers(),
        fetchImpl,
      );
      assert.equal(withoutToken, null);
    } finally {
      delete process.env.GROK_PROJECT_ID;
      delete process.env.GROK_GATE_ORIGIN;
    }
  });

  it("activates on a deployed-shaped request without GROK_GATE_ORIGIN", async () => {
    const key = await makeKey("k-deployed");
    const fetchedFrom: string[] = [];
    const fetchImpl = async (url: string): Promise<GateJwks> => {
      fetchedFrom.push(url);
      return { keys: [key.jwk] };
    };
    process.env.GROK_PROJECT_ID = "proj-123";
    delete process.env.GROK_GATE_ORIGIN;
    try {
      const token = await signToken(key, {
        sub: "user-1",
        email: "viewer@example.com",
      });
      const identity = await gateIdentityFromHeaders(
        new Headers({
          host: "my-app.app-builder-testing.com",
          "x-grok-identity": token,
        }),
        fetchImpl,
      );
      assert.equal(identity?.sub, "user-1");
      assert.equal(
        fetchedFrom[0],
        "https://gate.app-builder-testing.com/__gate/identity-key",
      );
    } finally {
      delete process.env.GROK_PROJECT_ID;
    }
  });

  it("verifies a preview-audience token with no gate env vars via the loopback default", async () => {
    const key = await makeKey("k-preview");
    const fetchedFrom: string[] = [];
    const fetchImpl = async (url: string): Promise<GateJwks> => {
      fetchedFrom.push(url);
      return { keys: [key.jwk] };
    };
    delete process.env.GROK_PROJECT_ID;
    delete process.env.GROK_GATE_ORIGIN;
    const token = await signToken(
      key,
      { sub: "user-1" },
      { issuer: "http://127.0.0.1:6014", audience: "preview" },
    );
    const identity = await gateIdentityFromHeaders(
      new Headers({
        host: "my-session.grok-sandbox.com",
        "x-grok-identity": token,
      }),
      fetchImpl,
    );
    assert.equal(identity?.sub, "user-1");
    assert.equal(fetchedFrom[0], "http://127.0.0.1:6014/__gate/identity-key");
  });

  it("rejects a wrong-issuer token in the loopback default mode", async () => {
    const key = await makeKey("k-preview-iss");
    const { fetchImpl } = staticJwks([key.jwk]);
    delete process.env.GROK_PROJECT_ID;
    delete process.env.GROK_GATE_ORIGIN;
    const token = await signToken(
      key,
      { sub: "user-1" },
      { issuer: ISSUER, audience: "preview" },
    );
    const identity = await gateIdentityFromHeaders(
      new Headers({ "x-grok-identity": token }),
      fetchImpl,
    );
    assert.equal(identity, null);
  });

  it("verifies a preview-audience token when only GROK_GATE_ORIGIN is set", async () => {
    const key = await makeKey("k1");
    const { fetchImpl } = staticJwks([key.jwk]);
    delete process.env.GROK_PROJECT_ID;
    process.env.GROK_GATE_ORIGIN = ISSUER;
    try {
      const token = await signToken(
        key,
        { sub: "user-1" },
        { audience: "preview" },
      );
      const identity = await gateIdentityFromHeaders(
        new Headers({ "x-grok-identity": token }),
        fetchImpl,
      );
      assert.deepEqual(identity, {
        sub: "user-1",
        email: null,
        name: null,
        teamId: null,
      });
    } finally {
      delete process.env.GROK_GATE_ORIGIN;
    }
  });

  it("rejects a preview-audience token when GROK_PROJECT_ID is set", async () => {
    const key = await makeKey("k1");
    const { fetchImpl } = staticJwks([key.jwk]);
    process.env.GROK_PROJECT_ID = "proj-123";
    process.env.GROK_GATE_ORIGIN = ISSUER;
    try {
      const token = await signToken(
        key,
        { sub: "user-1" },
        { audience: "preview" },
      );
      const identity = await gateIdentityFromHeaders(
        new Headers({ "x-grok-identity": token }),
        fetchImpl,
      );
      assert.equal(identity, null);
    } finally {
      delete process.env.GROK_PROJECT_ID;
      delete process.env.GROK_GATE_ORIGIN;
    }
  });

  it("rejects an app-audience token in preview mode", async () => {
    const key = await makeKey("k1");
    const { fetchImpl } = staticJwks([key.jwk]);
    delete process.env.GROK_PROJECT_ID;
    process.env.GROK_GATE_ORIGIN = ISSUER;
    try {
      const token = await signToken(key, { sub: "user-1" });
      const identity = await gateIdentityFromHeaders(
        new Headers({ "x-grok-identity": token }),
        fetchImpl,
      );
      assert.equal(identity, null);
    } finally {
      delete process.env.GROK_GATE_ORIGIN;
    }
  });
});

describe("gateIdentityEnabled", () => {
  it("is enabled by default with no gate env vars", () => {
    delete process.env.GROK_PROJECT_ID;
    delete process.env.GROK_GATE_ORIGIN;
    assert.equal(gateIdentityEnabled(), true);
  });

  it("is disabled when VITE_AUTH_ENABLED is false", () => {
    process.env.VITE_AUTH_ENABLED = "false";
    try {
      assert.equal(gateIdentityEnabled(), false);
    } finally {
      delete process.env.VITE_AUTH_ENABLED;
    }
  });
});

describe("gateTokenAudience", () => {
  it("pins app:<id> when GROK_PROJECT_ID is set, even alongside GROK_GATE_ORIGIN", () => {
    process.env.GROK_PROJECT_ID = "proj-123";
    process.env.GROK_GATE_ORIGIN = ISSUER;
    try {
      assert.equal(gateTokenAudience(), "app:proj-123");
    } finally {
      delete process.env.GROK_PROJECT_ID;
      delete process.env.GROK_GATE_ORIGIN;
    }
  });

  it("pins preview when GROK_PROJECT_ID is unset", () => {
    delete process.env.GROK_PROJECT_ID;
    process.env.GROK_GATE_ORIGIN = ISSUER;
    try {
      assert.equal(gateTokenAudience(), "preview");
    } finally {
      delete process.env.GROK_GATE_ORIGIN;
    }
  });
});

describe("gateIdentityUserInfo", () => {
  it("falls back to a synthetic email and name for sub-only claims", () => {
    assert.deepEqual(
      gateIdentityUserInfo({
        sub: "User-1",
        email: null,
        name: null,
        teamId: null,
      }),
      {
        id: "User-1",
        email: "user-1@viewer.grok.invalid",
        emailVerified: false,
        name: "Grok user",
      },
    );
  });

  it("keeps real claims, lowercasing the email and marking it verified", () => {
    assert.deepEqual(
      gateIdentityUserInfo({
        sub: "user-1",
        email: "Viewer@Example.com",
        name: "Viewer",
        teamId: "team-9",
      }),
      {
        id: "user-1",
        email: "viewer@example.com",
        emailVerified: true,
        name: "Viewer",
      },
    );
  });
});

describe("sessionBoundToGateIdentity", () => {
  const provider = "grok-gate";

  it("keeps the session when it is bound to the same gate sub", () => {
    assert.equal(
      sessionBoundToGateIdentity(
        [
          { providerId: "google", accountId: "g-1" },
          { providerId: provider, accountId: "user-1" },
        ],
        "user-1",
        provider,
      ),
      true,
    );
  });

  it("rotates when the session belongs to a different gate sub", () => {
    assert.equal(
      sessionBoundToGateIdentity(
        [{ providerId: provider, accountId: "user-1" }],
        "user-2",
        provider,
      ),
      false,
    );
  });

  it("rotates when the session user has no gate-bound account", () => {
    assert.equal(
      sessionBoundToGateIdentity(
        [{ providerId: "google", accountId: "user-1" }],
        "user-1",
        provider,
      ),
      false,
    );
    assert.equal(sessionBoundToGateIdentity([], "user-1", provider), false);
  });
});

````

## `frontend_demo/src/lib/auth/gate-session-marker.ts`
````ts
/**
 * Client-readable marker for gate-materialized sessions ("Sign in with Grok"
 * zero-click sessions minted by `gate-session.server.ts`). Signing out of a
 * gate session is a no-op — the next request re-materializes it from
 * `x-grok-identity` — so `UserButton` uses this to hide its sign-out control.
 * `__Host-` prefixed like the other auth cookies: browsers reject a `__Host-`
 * cookie carrying a `Domain`, so an untrusted sibling `*.grok.me` app cannot
 * plant a parent-domain copy that the host-only clear could never expire.
 * Client-safe: no server imports.
 */
export const GATE_SESSION_MARKER_COOKIE = "__Host-grok_gate_session";

export function hasGateSessionMarker(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie
    .split(";")
    .some((pair) => pair.trim().startsWith(`${GATE_SESSION_MARKER_COOKIE}=`));
}

````

## `frontend_demo/src/lib/auth/gate-session.server.ts`
````ts
import type { BetterAuthPlugin } from "better-auth";
import { createAuthMiddleware, getSessionFromCtx } from "better-auth/api";
import {
  parseSetCookieHeader,
  setRequestCookie,
  setSessionCookie,
} from "better-auth/cookies";
import { handleOAuthUserInfo } from "better-auth/oauth2";
import {
  GATE_IDENTITY_HEADER,
  gateIdentityEnabled,
  gateIdentityFromHeaders,
  gateIdentityUserInfo,
  sessionBoundToGateIdentity,
} from "./gate-identity.server";
import { GATE_SESSION_MARKER_COOKIE } from "./gate-session-marker";

export const GATE_PROVIDER_ID = "grok-gate";
const GATE_ACCOUNT_ISSUER = "https://grok.com";
const LOG = "[gate-identity]";

type GateAccount = Parameters<typeof handleOAuthUserInfo>[1]["account"];

/**
 * Emit the signed session cookie so the browser actually receives it.
 *
 * `setSessionCookie` writes into the Better Auth middleware header bag, but on
 * TanStack Start that bag is not always copied onto the final HTTP response
 * (the response can end up with no `Set-Cookie`). Sign the token ourselves and
 * push it through TanStack's `setCookie` + `responseHeaders` so both the
 * framework cookie store and any after-hooks see it.
 */
async function emitSessionCookie(
  ctx: Parameters<Parameters<typeof createAuthMiddleware>[0]>[0],
  sessionTokenName: string,
  sessionToken: string,
): Promise<string | null> {
  const attributes = ctx.context.authCookies.sessionToken.attributes;
  const maxAge = ctx.context.sessionConfig.expiresIn;
  const cookieOptions = {
    ...attributes,
    maxAge,
  };

  let signedCookie: string;
  try {
    signedCookie = await ctx.setSignedCookie(
      sessionTokenName,
      sessionToken,
      ctx.context.secret,
      cookieOptions,
    );
  } catch (err) {
    console.error(`${LOG} setSignedCookie failed`, err);
    return null;
  }

  const sessionValue = parseSetCookieHeader(signedCookie).get(
    sessionTokenName,
  )?.value;
  if (!sessionValue) {
    console.error(`${LOG} signed Set-Cookie missing session token value`, {
      cookiePreview: signedCookie.slice(0, 120),
    });
    return null;
  }

  // Primary path: TanStack Start's response cookie store (reaches the browser).
  try {
    const { setCookie } = await import("@tanstack/react-start/server");
    setCookie(sessionTokenName, sessionValue, {
      path: cookieOptions.path ?? "/",
      httpOnly: cookieOptions.httpOnly ?? true,
      secure: cookieOptions.secure ?? true,
      sameSite: (cookieOptions.sameSite as "lax" | "strict" | "none") ?? "lax",
      maxAge: typeof maxAge === "number" ? maxAge : undefined,
      domain: cookieOptions.domain,
    });
  } catch (err) {
    console.error(`${LOG} TanStack setCookie failed`, err);
  }

  // Also stash on Better Auth responseHeaders so after-hooks (tanstackStartCookies)
  // can forward it if they run.
  try {
    const responseHeaders = ctx.context.responseHeaders;
    if (responseHeaders) {
      responseHeaders.append("set-cookie", signedCookie);
    } else {
      console.error(`${LOG} ctx.context.responseHeaders is missing`);
    }
  } catch (err) {
    console.error(`${LOG} responseHeaders.append(set-cookie) failed`, err);
  }

  return sessionValue;
}

/**
 * Expire the previous user's `session_data` cookie cache after an identity
 * swap. The cache is signed against the old session and outlives it (5-min
 * TTL), so without this `/get-session` keeps serving the replaced user.
 * Mirrors `emitSessionCookie`'s dual-path delivery: TanStack's response
 * cookie store plus Better Auth's `responseHeaders` bag.
 */
async function expireSessionDataCookie(
  ctx: Parameters<Parameters<typeof createAuthMiddleware>[0]>[0],
  cookie: { name: string; attributes: { path?: string; secure?: boolean } },
): Promise<void> {
  const path = cookie.attributes.path ?? "/";
  const secure = cookie.attributes.secure ?? true;
  try {
    const { setCookie } = await import("@tanstack/react-start/server");
    setCookie(cookie.name, "", {
      path,
      httpOnly: true,
      secure,
      sameSite: "lax",
      maxAge: 0,
    });
  } catch (err) {
    console.error(`${LOG} TanStack setCookie (expire session_data) failed`, err);
  }
  try {
    ctx.context.responseHeaders?.append(
      "set-cookie",
      `${cookie.name}=; Path=${path}; HttpOnly; ` +
        `${secure ? "Secure; " : ""}SameSite=Lax; Max-Age=0`,
    );
  } catch (err) {
    console.error(
      `${LOG} responseHeaders.append (expire session_data) failed`,
      err,
    );
  }
}

/**
 * Write or clear the client-readable gate-session marker
 * (`gate-session-marker.ts`), through the same dual-path delivery as
 * `emitSessionCookie`. Not HttpOnly by design: `UserButton` reads it to hide
 * sign-out for gate sessions (signing out would re-materialize instantly).
 */
async function writeGateMarkerCookie(
  ctx: Parameters<Parameters<typeof createAuthMiddleware>[0]>[0],
  clear: boolean,
): Promise<void> {
  const sessionMaxAge = ctx.context.sessionConfig.expiresIn;
  const maxAge = clear
    ? 0
    : typeof sessionMaxAge === "number"
      ? sessionMaxAge
      : undefined;
  const value = clear ? "" : "1";
  try {
    const { setCookie } = await import("@tanstack/react-start/server");
    setCookie(GATE_SESSION_MARKER_COOKIE, value, {
      path: "/",
      httpOnly: false,
      secure: true,
      sameSite: "lax",
      maxAge,
    });
  } catch (err) {
    console.error(`${LOG} TanStack setCookie (gate marker) failed`, err);
  }
  try {
    ctx.context.responseHeaders?.append(
      "set-cookie",
      `${GATE_SESSION_MARKER_COOKIE}=${value}; Path=/; Secure; SameSite=Lax` +
        (maxAge === undefined ? "" : `; Max-Age=${maxAge}`),
    );
  } catch (err) {
    console.error(`${LOG} responseHeaders.append (gate marker) failed`, err);
  }
}

/**
 * Clear a stale marker when a `/get-session` arrives without `x-grok-identity`:
 * the browser is no longer behind a gate viewer (returned anonymously, or the
 * session is a broker one), so sign-out must not stay hidden. Emits the
 * Max-Age=0 clear only when the marker is actually on the request.
 */
async function clearGateMarkerIfPresent(
  ctx: Parameters<Parameters<typeof createAuthMiddleware>[0]>[0],
  inbound: Headers,
): Promise<void> {
  const cookieHeader = inbound.get("cookie") ?? "";
  if (!cookieHeader.includes(`${GATE_SESSION_MARKER_COOKIE}=`)) return;
  await writeGateMarkerCookie(ctx, true);
}

/** Drop a cookie from the request `Cookie` header (inverse of `setRequestCookie`). */
function removeRequestCookie(headers: Headers, name: string): void {
  const cookieHeader = headers.get("cookie");
  if (!cookieHeader) return;
  const kept = cookieHeader
    .split(";")
    .map((pair) => pair.trim())
    .filter((pair) => pair && !pair.startsWith(`${name}=`));
  if (kept.length > 0) {
    headers.set("cookie", kept.join("; "));
  } else {
    headers.delete("cookie");
  }
}

export function gateIdentitySessions() {
  return {
    id: "grok-gate-identity",
    hooks: {
      before: [
        {
          matcher: (ctx: { path?: string }) => ctx.path === "/get-session",
          handler: createAuthMiddleware(async (ctx) => {
            if (!gateIdentityEnabled()) return;
            const inbound = ctx.request?.headers ?? ctx.headers;
            if (!inbound) {
              console.error(`${LOG} no request headers on /get-session`);
              return;
            }
            // Bearer auth (live-preview popup) already carries a session — leave it alone.
            if (inbound.get("authorization")) return;
            if (!inbound.get(GATE_IDENTITY_HEADER)) {
              await clearGateMarkerIfPresent(ctx, inbound);
              return;
            }

            const identity = await gateIdentityFromHeaders(inbound);
            if (!identity) {
              console.error(
                `${LOG} ${GATE_IDENTITY_HEADER} present but verification failed`,
              );
              return;
            }

            const sessionCookieName = ctx.context.authCookies.sessionToken.name;
            const cookieHeader = inbound.get("cookie") ?? "";
            if (cookieHeader.includes(`${sessionCookieName}=`)) {
              const existing = await getSessionFromCtx(ctx).catch((err) => {
                console.error(`${LOG} getSessionFromCtx failed`, err);
                return null;
              });
              if (existing?.session && existing.user) {
                const accounts = await ctx.context.internalAdapter
                  .findAccounts(existing.user.id)
                  .catch((err) => {
                    console.error(`${LOG} findAccounts failed`, err);
                    return null;
                  });
                if (!accounts) {
                  console.error(
                    `${LOG} could not load accounts for existing session user`,
                    { userId: existing.user.id },
                  );
                  return;
                }
                if (
                  sessionBoundToGateIdentity(
                    accounts,
                    identity.sub,
                    GATE_PROVIDER_ID,
                  )
                ) {
                  await writeGateMarkerCookie(ctx, false);
                  return;
                }
                await ctx.context.internalAdapter
                  .deleteSession(existing.session.token)
                  .catch((err) => {
                    console.error(
                      `${LOG} deleteSession (stale non-gate session) failed`,
                      err,
                    );
                    return null;
                  });
              }
            }

            try {
              const result = await handleOAuthUserInfo(ctx, {
                userInfo: gateIdentityUserInfo(identity),
                account: {
                  providerId: GATE_PROVIDER_ID,
                  issuer: GATE_ACCOUNT_ISSUER,
                  accountId: identity.sub,
                } as GateAccount,
              });
              if (result.error || !result.data) {
                console.error(`${LOG} handleOAuthUserInfo failed`, {
                  error: result.error,
                  hasData: Boolean(result.data),
                  sub: identity.sub,
                });
                return;
              }

              // Persist session rows + internal newSession state.
              await setSessionCookie(ctx, result.data);

              // Explicitly sign the token and emit Set-Cookie — do NOT rely on
              // reading it back from ctx.context.responseHeaders (often empty
              // here, which previously caused a silent signed-out render).
              const sessionValue = await emitSessionCookie(
                ctx,
                sessionCookieName,
                result.data.session.token,
              );
              if (!sessionValue) {
                console.error(
                  `${LOG} session created in DB but cookie was not emitted`,
                  { userId: result.data.user.id },
                );
                return;
              }

              await writeGateMarkerCookie(ctx, false);

              const sessionDataCookie = ctx.context.authCookies.sessionData;
              await expireSessionDataCookie(ctx, sessionDataCookie);

              // Inject the cookie into this request so the rest of /get-session
              // resolves the newly created session in the same round-trip.
              const headers = new Headers(
                Object.fromEntries(inbound.entries()),
              );
              setRequestCookie(headers, sessionCookieName, sessionValue);
              removeRequestCookie(headers, sessionDataCookie.name);
              return { context: { headers } };
            } catch (err) {
              console.error(`${LOG} gate identity session hook threw`, err);
              return;
            }
          }),
        },
      ],
    },
  } satisfies BetterAuthPlugin;
}

````

## `frontend_demo/src/lib/auth/gates.tsx`
````tsx
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { Navigate } from "@tanstack/react-router";
import { GROK_PROVIDERS, authEnabled, signIn, signOut } from "./client";
import { hasGateSessionMarker } from "./gate-session-marker";
import { resolveSignInGateState } from "./sign-in-gate";
import { useCurrentUser, useCurrentUserState } from "./use-current-user";

const subscribeToNothing = () => () => {};
const noGateSessionOnServer = () => false;

/**
 * Auth state components — plain wrappers around `useCurrentUserState()`.
 *
 * With auth on, visitors are signed out until they authenticate — in the sandbox
 * live preview too, which does real sign-in. The shared dev user appears only
 * when auth is disabled (`VITE_AUTH_ENABLED=false`, the shipped default).
 * While the session is still resolving, gates that care about signed-out state
 * render nothing so there's no signed-out flash on hard reload.
 */

/** Where `RedirectToSignIn` sends signed-out visitors. Create this route. */
export const SIGN_IN_PATH = "/login";

/** Render children only when a user is present (real session, or the disabled-auth dev user). */
export function SignedIn({ children }: { children: ReactNode }) {
  const { user } = useCurrentUserState();
  return user ? <>{children}</> : null;
}

/**
 * Render children only once we KNOW the visitor is signed out (`isPending` has
 * cleared and there is no user). Hidden while the session is still loading.
 */
export function SignedOut({ children }: { children: ReactNode }) {
  const { user, isPending } = useCurrentUserState();
  if (isPending || user) return null;
  return <>{children}</>;
}

/**
 * Client-side redirect to the sign-in route (TanStack `<Navigate>` — NOT a full
 * `window.location` reload). A hard navigation re-bootstraps the SPA and re-runs
 * session loading, which feels like a second "Loading…" on /login.
 *
 * Guard routes by waiting out `isPending` first (see `use-current-user`), then
 * render this.
 */
export function RedirectToSignIn({ to = SIGN_IN_PATH }: { to?: string }) {
  return <Navigate to={to} />;
}

export function SignInGate({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { user, isPending } = useCurrentUserState();
  const state = resolveSignInGateState({ isPending, hasUser: user !== null });
  if (state === "pending") return null;
  if (state === "signed_in") return <>{children}</>;
  return <>{fallback ?? <SignInButtons />}</>;
}

export function SignInButtons() {
  return (
    <div className="flex w-full max-w-sm flex-col gap-2">
      {GROK_PROVIDERS.map((p) => (
        <button
          key={p.providerId}
          type="button"
          onClick={() => signIn(p.providerId, { callbackURL: "/" })}
          className="w-full cursor-pointer rounded-md border border-neutral-300 px-4 py-2 hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-900"
        >
          Continue with {p.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Minimal signed-in identity chip + sign-out. Restyle freely (see the
 * `design-ui` skill). Sign-out is only shown when auth is enabled (the
 * disabled-auth dev user has nothing to sign out of) and the session is not
 * gate-materialized — behind the gate the next request signs the viewer
 * straight back in, so a sign-out control there is a broken loop.
 */
export function UserButton() {
  const user = useCurrentUser();
  // Sign-out can take a moment (and can fail when deployed), so the control
  // shows it is working and cannot be fired twice.
  const [signingOut, setSigningOut] = useState(false);
  const gateSession = useSyncExternalStore(
    subscribeToNothing,
    hasGateSessionMarker,
    noGateSessionOnServer,
  );
  if (!user) return null;
  const label = user.displayName ?? user.primaryEmail ?? "Account";
  return (
    <div className="flex items-center gap-2">
      {user.profileImageUrl ? (
        <img
          src={user.profileImageUrl}
          alt=""
          className="h-8 w-8 rounded-full object-cover"
        />
      ) : (
        <span className="grid h-8 w-8 place-items-center rounded-full bg-black/10 text-sm font-medium dark:bg-white/20">
          {label.charAt(0).toUpperCase()}
        </span>
      )}
      <span className="text-sm font-medium">{label}</span>
      {authEnabled && !gateSession && (
        <button
          type="button"
          disabled={signingOut}
          onClick={() => {
            setSigningOut(true);
            // Success navigates away; on failure re-enable so it can be retried.
            void signOut().catch(() => setSigningOut(false));
          }}
          className="cursor-pointer text-sm underline-offset-4 opacity-70 hover:underline disabled:cursor-wait disabled:no-underline"
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      )}
    </div>
  );
}

````

## `frontend_demo/src/lib/auth/isolation.server.ts`
````ts
import { getRequest } from "@tanstack/react-start/server";

/**
 * Fetch-Metadata sibling isolation — **server-only** (`.server.ts` suffix).
 *
 * MUST keep the `.server` suffix: this file imports `@tanstack/react-start/server`
 * (`getRequest` → Node `AsyncLocalStorage`). If it is imported from a dual
 * client/server module under a non-`.server` name, Vite ships it to the browser
 * and the app dies with: `AsyncLocalStorage is not a constructor`.
 *
 * Apps deployed on `*.grok.me` are "same-site" to each other but MUTUALLY
 * UNTRUSTED, and a `SameSite=Lax` session cookie IS sent on same-site
 * subrequests — so without this, a malicious sibling could make a SCRIPTED
 * (fetch/XHR/form-POST) request to this app's server functions and ride this
 * app's session cookie.
 *
 * We allow only: same-origin requests (this app's own client), non-browser
 * requests (SSR / server-to-server, which send no `Sec-Fetch-Site`), and
 * top-level GET navigations (how the OAuth callback and normal page loads
 * arrive). Every cross-site / same-site *scripted* request is rejected.
 * Together with `__Host-` cookies and Better Auth's `trustedOrigins`, this
 * closes the sibling-tenant attack surface. Enforced at the `authMiddleware`
 * chokepoint (see `middleware.ts`).
 */
export class CrossSiteRequestError extends Error {
  readonly status = 403;
  constructor() {
    super("Forbidden: cross-site request blocked");
    this.name = "CrossSiteRequestError";
  }
}

/** Throw `CrossSiteRequestError` for a scripted cross-site/sibling request. */
export function assertSameSiteRequest(): void {
  const request = getRequest();
  if (!request) return; // no request context (e.g. build) — nothing to guard
  const h = request.headers;
  const site = h.get("sec-fetch-site");
  // Non-browser client (no header), the app's own origin, or a direct
  // (address-bar/bookmark) load are all fine.
  if (!site || site === "same-origin" || site === "none") return;
  // A top-level GET navigation (e.g. the broker's OAuth callback redirect) is
  // fine even when it's cross-site; scripted requests never set navigate mode.
  const dest = h.get("sec-fetch-dest");
  const isTopLevelGet =
    h.get("sec-fetch-mode") === "navigate" &&
    request.method === "GET" &&
    dest !== "object" &&
    dest !== "embed";
  if (isTopLevelGet) return;
  throw new CrossSiteRequestError();
}

````

## `frontend_demo/src/lib/auth/middleware.ts`
````ts
import { createMiddleware } from "@tanstack/react-start";

/**
 * Auth middleware for server functions — the standard way to get the caller's
 * verified user id. When deployed the session cookie is same-origin and rides
 * along automatically. In the live preview the client also forwards the bearer
 * token (partitioned cookies) via the `.client` hook below — call sites do not
 * thread it themselves.
 *
 *   import { createServerFn } from "@tanstack/react-start";
 *   import { getSql } from "@/lib/db";
 *   import { authMiddleware } from "@/lib/auth/middleware";
 *
 *   export const listTodos = createServerFn({ method: "GET" })
 *     .middleware([authMiddleware])
 *     .handler(async ({ context }) => {
 *       const sql = await getSql();
 *       return sql`select * from todos where user_id = ${context.userId}`;
 *     });
 *
 * Signed out with auth on (live preview included) -> throws `UnauthorizedError`
 * (see `verify.server.ts`). With auth disabled (`VITE_AUTH_ENABLED=false`, the
 * shipped default) it resolves the shared dev user — but throws instead when a
 * `DATABASE_URL` is also set, so an app without sign-in must not use this at
 * all. On the auth-on path, use it on every server function that touches
 * per-user data and scope every query by `context.userId`.
 */
export const authMiddleware = createMiddleware({ type: "function" })
  .client(async ({ next }) => {
    // Live preview (partitioned iframe): the session rides a bearer token, not a
    // cookie, so forward it to the server. Null when deployed (cookie auth), so
    // this is a no-op there.
    const { getBearerToken } = await import("./client");
    return next({ sendContext: { bearerToken: getBearerToken() ?? undefined } });
  })
  .server(async ({ next, context }) => {
    // ONLY import `*.server` modules here. This file is dual client/server
    // (bearer hook on the client). A plain `./isolation` path was renamed to
    // `isolation.server.ts` — keep this import in sync so image `tsc` resolves
    // it, and so Vite does not ship `@tanstack/react-start/server` to the browser.
    const { assertSameSiteRequest } = await import("./isolation.server");
    const { requireUserId } = await import("./verify.server");
    // Reject scripted cross-site/sibling requests before touching per-user data.
    assertSameSiteRequest();
    const userId = await requireUserId(context.bearerToken);
    return next({ context: { userId } });
  });

````

## `frontend_demo/src/lib/auth/pglite-dialect.ts`
````ts
/**
 * Kysely dialect for Better Auth over the app's embedded PGLite instance.
 * Lazy: resolves `getClient` on first connection so migrations can finish first.
 */
import type { PGlite } from "@electric-sql/pglite";
import {
  CompiledQuery,
  type DatabaseConnection,
  type DatabaseIntrospector,
  type Dialect,
  type Driver,
  type Kysely,
  PostgresAdapter,
  PostgresIntrospector,
  PostgresQueryCompiler,
  type QueryCompiler,
  type QueryResult,
  type TransactionSettings,
} from "kysely";

type Client = PGlite;

/** Factory used by `auth/server.ts`: `pgliteDialect(() => getPglite())`. */
export function pgliteDialect(
  getClient: () => Promise<Client> | Client,
): Dialect {
  return {
    createAdapter: () => new PostgresAdapter(),
    createDriver: () => new LazyPGliteDriver(getClient),
    createQueryCompiler: (): QueryCompiler => new PostgresQueryCompiler(),
    createIntrospector: (db: Kysely<unknown>): DatabaseIntrospector =>
      new PostgresIntrospector(db),
  };
}

class LazyPGliteDriver implements Driver {
  private client: Client | undefined;
  private connection: PGliteConnection | undefined;
  private queue: Array<(con: PGliteConnection) => void> = [];

  constructor(private readonly getClient: () => Promise<Client> | Client) {}

  async init(): Promise<void> {
    this.client = await this.getClient();
  }

  async acquireConnection(): Promise<DatabaseConnection> {
    if (this.client === undefined) {
      this.client = await this.getClient();
    }
    if (this.connection !== undefined) {
      return new Promise((resolve) => {
        this.queue.push(resolve);
      });
    }
    this.connection = new PGliteConnection(this.client);
    return this.connection;
  }

  async releaseConnection(connection: DatabaseConnection): Promise<void> {
    if (connection !== this.connection) {
      throw new Error("Invalid connection");
    }
    const next = this.queue.shift();
    if (next === undefined) {
      this.connection = undefined;
      return;
    }
    next(this.connection);
  }

  async beginTransaction(
    conn: DatabaseConnection,
    settings: TransactionSettings,
  ): Promise<void> {
    const c = conn as PGliteConnection;
    if (settings.isolationLevel) {
      await c.executeQuery(
        CompiledQuery.raw(
          `start transaction isolation level ${settings.isolationLevel}`,
        ),
      );
    } else {
      await c.executeQuery(CompiledQuery.raw("begin"));
    }
  }

  async commitTransaction(conn: DatabaseConnection): Promise<void> {
    await (conn as PGliteConnection).executeQuery(CompiledQuery.raw("commit"));
  }

  async rollbackTransaction(conn: DatabaseConnection): Promise<void> {
    await (conn as PGliteConnection).executeQuery(
      CompiledQuery.raw("rollback"),
    );
  }

  async destroy(): Promise<void> {
    // Do not close the client: it is the shared getPglite() singleton used by
    // app SQL (getSql). Only drop our local handle so auth teardown cannot
    // poison the rest of the process.
    this.client = undefined;
    this.connection = undefined;
    this.queue = [];
  }
}

class PGliteConnection implements DatabaseConnection {
  constructor(private readonly client: Client) {}

  async executeQuery<O>(compiledQuery: CompiledQuery): Promise<QueryResult<O>> {
    const result = await this.client.query(compiledQuery.sql, [
      ...compiledQuery.parameters,
    ]);
    if (result.affectedRows) {
      return {
        numAffectedRows: BigInt(result.affectedRows),
        rows: result.rows as O[],
      };
    }
    return { rows: result.rows as O[] };
  }

  async *streamQuery<O>(
    compiledQuery: CompiledQuery,
    chunkSize: number,
  ): AsyncIterableIterator<QueryResult<O>> {
    if (!Number.isInteger(chunkSize) || chunkSize <= 0) {
      throw new Error("chunkSize must be a positive integer");
    }
    const result = await this.client.query(compiledQuery.sql, [
      ...compiledQuery.parameters,
    ]);
    for (let i = 0; i < result.rows.length; i += chunkSize) {
      yield { rows: result.rows.slice(i, i + chunkSize) as O[] };
    }
  }
}

````

## `frontend_demo/src/lib/auth/popup.server.ts`
````ts
/**
 * Live-preview sign-in popup — server-only (NEVER import from the client).
 *
 * The sandbox preview runs the app in a partitioned iframe, so OAuth must happen
 * in a top-level popup (first-party cookies). This handler is the ENTIRE popup
 * document — no React shell:
 *
 *   Phase 1 (`?providerId=…`): start OAuth server-side and 302 straight to the
 *     broker / upstream login page. The popup never paints the app.
 *   Phase 2 (`?done=1`): after the broker round-trip, emit a tiny HTML page that
 *     posts the session token to the opener and closes. No SPA hydrate, no
 *     server-fn round-trip.
 *
 * Wired automatically by the Vite `authPopupPlugin` in `vite.config.ts` during
 * `npm run dev` (live preview). Do NOT create `src/routes/auth/popup.tsx` — a
 * React route here paints the full app shell in the popup. The opener lives in
 * `client.ts` (`signIn` → `openSignInPopup`).
 */
import { auth, SESSION_TOKEN_COOKIE } from "./server";

/** Message shape the popup posts to the opener (must match `client.ts`). */
type PopupMessage = {
  source: "grok-auth-popup";
  token: string | null;
  error?: string;
};

/**
 * Handle `GET /auth/popup`. Invoked by the Vite `authPopupPlugin` (dev / live
 * preview). Do not re-export this from a React route file.
 */
export async function handleAuthPopupRequest(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const done = url.searchParams.get("done") === "1";

  if (done) {
    const errored = url.searchParams.has("error");
    const token = errored ? null : readCookie(request, SESSION_TOKEN_COOKIE);
    const message: PopupMessage = {
      source: "grok-auth-popup",
      token,
      ...(errored ? { error: url.searchParams.get("error") ?? "sign_in_failed" } : {}),
    };
    return new Response(completionHtml(message), {
      status: 200,
      headers: {
        "content-type": "text/html; charset=utf-8",
        // Never cache a page that embeds a session token.
        "cache-control": "no-store",
      },
    });
  }

  const providerId = url.searchParams.get("providerId")?.trim();
  if (!providerId) {
    return new Response("Missing providerId", {
      status: 400,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  // Stay first-party for the callback so the session cookie lands in THIS popup.
  const back = `${url.origin}/auth/popup?done=1`;
  try {
    const apiRes = await auth.api.signInWithOAuth2({
      body: {
        providerId,
        callbackURL: back,
        errorCallbackURL: `${back}&error=1`,
      },
      // Forward the preview host so Better Auth derives the correct baseURL /
      // redirect_uri for the dynamic `*.grok-sandbox.com` origin.
      headers: request.headers,
      asResponse: true,
    });

    if (!apiRes.ok) {
      const detail = await apiRes.text().catch(() => "");
      return completionResponse({
        source: "grok-auth-popup",
        token: null,
        error: detail || `oauth_init_failed_${apiRes.status}`,
      });
    }

    const body = (await apiRes.json().catch(() => null)) as {
      url?: string;
    } | null;
    const location = body?.url;
    if (!location) {
      return completionResponse({
        source: "grok-auth-popup",
        token: null,
        error: "oauth_init_missing_url",
      });
    }

    // 302 to the broker (which headlessly forwards to Google/X). Forward any
    // Set-Cookie (OAuth state / PKCE) so the callback can complete in this popup.
    const headers = new Headers({ location, "cache-control": "no-store" });
    for (const cookie of apiRes.headers.getSetCookie()) {
      headers.append("set-cookie", cookie);
    }
    return new Response(null, { status: 302, headers });
  } catch (err) {
    const message = err instanceof Error ? err.message : "oauth_init_threw";
    return completionResponse({
      source: "grok-auth-popup",
      token: null,
      error: message,
    });
  }
}

function completionResponse(message: PopupMessage): Response {
  return new Response(completionHtml(message), {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

/** Minimal HTML: postMessage the token to the opener and close. No React. */
function completionHtml(message: PopupMessage): string {
  // JSON is safe inside a <script type="application/json"> block; the inline
  // script only reads it. Avoids escaping pitfalls of embedding in JS source.
  const payload = JSON.stringify(message).replace(/</g, "\\u003c");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Signing in…</title>
<style>
  html,body{margin:0;min-height:100%;background:#0b0b0c;color:#a1a1aa;
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  main{min-height:100vh;display:grid;place-items:center;padding:1.5rem;text-align:center}
</style>
</head>
<body>
<main><p>Signing you in…</p></main>
<script type="application/json" id="grok-auth-popup-msg">${payload}</script>
<script>
(function () {
  var el = document.getElementById("grok-auth-popup-msg");
  var msg = { source: "grok-auth-popup", token: null };
  try { if (el && el.textContent) msg = JSON.parse(el.textContent); } catch (e) {}
  try {
    if (window.opener) window.opener.postMessage(msg, window.location.origin);
  } catch (e) {}
  try { window.close(); } catch (e) {}
})();
</script>
</body>
</html>`;
}

/** Read a single cookie value from the request (handles `=` inside values). */
function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get("cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    if (trimmed.slice(0, eq) !== name) continue;
    const raw = trimmed.slice(eq + 1);
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }
  return null;
}

````

## `frontend_demo/src/lib/auth/preview.ts`
````ts
/**
 * Shared LIVE-PREVIEW OAuth client (server-only — NEVER import from the client).
 *
 * The sandbox serves each live preview on a dynamic `https://*.grok-sandbox.com`
 * URL, which can't be pre-registered per app. The broker instead exposes ONE
 * shared "preview" client that accepts any
 * `https://*.grok-sandbox.com/api/auth/oauth2/callback/*`
 * (broker: `app-builder-deployer/auth/src/preview-oauth.ts`). Baking it here lets
 * the live preview do REAL sign-in — no demo/mock users — with no platform
 * injection. When deployed the deployer injects a per-app
 * `GROK_AUTH_*` that overrides these (see `server.ts`).
 *
 * These MUST equal the broker's `GROK_PREVIEW_CLIENT_ID` /
 * `GROK_PREVIEW_CLIENT_SECRET` (set in the broker's Vercel env; the broker stores
 * only the secret's `base64url(SHA-256)` hash). This is a dedicated, low-privilege
 * client (preview-only, `*.grok-sandbox.com`) — rotate it by regenerating the
 * broker env var and this constant together.
 */
export const PREVIEW_CLIENT_ID = "grok_preview";
export const PREVIEW_CLIENT_SECRET =
  "8bcdb7fc5a33874ad933ca568918d5790388a0795e44c4d1dea691f801b17ec5";

/** The shared auth broker issuer (OIDC discovery lives under it). */
export const GROK_ISSUER_DEFAULT = "https://auth.grok.me";

/**
 * Host patterns whose callbacks the preview client accepts. Better Auth derives
 * the live preview's real origin from the request host and validates it against
 * this list (wildcard-matched), so the OAuth `redirect_uri` becomes the concrete
 * `https://<preview-host>/api/auth/oauth2/callback/...` the broker allows.
 */
export const PREVIEW_ALLOWED_HOSTS = ["*.grok-sandbox.com"] as const;

````

## `frontend_demo/src/lib/auth/provider.tsx`
````tsx
import type { ReactNode } from "react";

/**
 * App-wide client provider mounted once near the root (in `src/routes/__root.tsx`):
 *
 *   <AuthProvider><Outlet /></AuthProvider>
 *
 * Better Auth's React client (`@/lib/auth/client`) needs NO context provider —
 * its `useSession()` works standalone — so this is a passthrough today. It's
 * kept as the single, stable mount point for any future client-side providers
 * (e.g. a toast or theme provider) without churning the root shell.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

````

## `frontend_demo/src/lib/auth/providers.ts`
````ts
/**
 * The upstream identity providers this app offers for sign-in (via the broker).
 *
 * Source of truth for BOTH the server (`server.ts`, one `genericOAuth` provider
 * per entry) and the client (`client.ts` / sign-in buttons). Kept in its own
 * dependency-free module so the client can import it without pulling the
 * server-only Better Auth instance (and `pg`) into the browser bundle.
 *
 * Each app federates to the shared **auth broker** (`GROK_AUTH_ISSUER`), which
 * holds the real Google/X secrets. The app never sees them — it only knows its
 * own per-app client id/secret and which upstream to ask the broker for (`idp`).
 *
 * To add an upstream (e.g. GitHub) once the broker supports it: add one entry
 * here (`{ providerId: "grok-github", idp: "github", label: "GitHub" }`). The
 * `providerId` is this app's local id and the OAuth callback path segment
 * (`/api/auth/oauth2/callback/<providerId>`); `idp` is the hint the broker reads
 * to pick the upstream (Better Auth's id for X is still `twitter`).
 */
export type GrokProvider = {
  /** This app's local provider id; also the callback path segment. */
  providerId: string;
  /** Upstream hint the broker forwards to (Better Auth social id). */
  idp: string;
  /** Human label for the sign-in button. */
  label: string;
};

export const GROK_PROVIDERS: readonly GrokProvider[] = [
  { providerId: "grok-google", idp: "google", label: "Google" },
  { providerId: "grok-x", idp: "twitter", label: "X" },
];

````

## `frontend_demo/src/lib/auth/server.ts`
````ts
/**
 * Self-hosted Better Auth for THIS app (server-only).
 *
 * Pre-wired for live preview + deploy — do not rewrite this file. To enable
 * local email/password, flip the flag in `./email-password` only (see auth skill).
 *
 * The app runs its own Better Auth at `/api/auth/*`, so the session cookie stays
 * on this app's own origin. Sign-in federates to the shared **Grok auth broker**
 * (`GROK_AUTH_ISSUER`) via the `genericOAuth` plugin — the broker brokers the
 * upstream sign-in methods (Google, X, …) and holds their shared secrets; this
 * app only holds its own client id/secret and names the upstream it wants via
 * each provider's `idp` hint.
 *
 * Tri-mode:
 *   - Deployed: the deployer injects a per-app `GROK_AUTH_*` + `BETTER_AUTH_URL`
 *     + `DATABASE_URL`, so real federated auth is persisted in Postgres.
 *   - Sandbox live preview: no injection -> falls back to the shared **preview
 *     client** (`./preview`) and derives the preview's `https://*.grok-sandbox.com`
 *     origin from the request, so real sign-in works (no demo users). Sessions
 *     and identities persist in the embedded PGLite DB (same DB as app data);
 *     the process restart wipes both. Live-preview iframe clients use a bearer
 *     token (partitioned cookies) — see `client.ts`.
 *   - Off (`VITE_AUTH_ENABLED=false`, the shipped default): no providers;
 *     `requireUserId` resolves a dev user with no database configured, and
 *     throws fail-closed once `DATABASE_URL` is set (see `verify.server.ts`).
 *
 * NEVER import this from client code — it pulls in `pg` + the preview secret +
 * server-only Better Auth internals. The client uses `@/lib/auth/client`;
 * components read the user via `@/lib/auth/use-current-user`; server functions get
 * a verified id via `@/lib/auth/middleware`.
 */
import { betterAuth } from "better-auth";
import { bearer, genericOAuth } from "better-auth/plugins";
import { tanstackStartCookies } from "better-auth/tanstack-start";
import { getCookie } from "@tanstack/react-start/server";
import { randomBytes } from "node:crypto";
import { Pool } from "pg";
import { ensureDbReady, getPglite } from "../db";
import { emailAndPasswordEnabled } from "./email-password";
import { GATE_PROVIDER_ID, gateIdentitySessions } from "./gate-session.server";
import { GROK_PROVIDERS } from "./providers";
import { pgliteDialect } from "./pglite-dialect";
import {
  GROK_ISSUER_DEFAULT,
  PREVIEW_ALLOWED_HOSTS,
  PREVIEW_CLIENT_ID,
  PREVIEW_CLIENT_SECRET,
} from "./preview";

// Kick (and share) PGLite bootstrap as soon as the auth server module loads.
void ensureDbReady();

/**
 * Preview secret must outlive module reloads: PGLite (and its session rows) is
 * stored on `globalThis`, so an HMR re-eval of this file must NOT mint a new
 * signing secret or every existing session becomes invalid mid-dev. Process
 * restart clears both the secret and PGLite together.
 */
const globalAuthRef = globalThis as typeof globalThis & {
  __grokAuthPreviewSecret__?: string;
};
function previewAuthSecret(): string {
  globalAuthRef.__grokAuthPreviewSecret__ ??= randomBytes(32).toString("hex");
  return globalAuthRef.__grokAuthPreviewSecret__;
}

/** Read an env var, treating empty/whitespace as unset. */
const env = (key: string): string | undefined => {
  const value = process.env[key]?.trim();
  return value ? value : undefined;
};

// Explicit off-switch. The deployer sets `VITE_AUTH_ENABLED=true` when it
// provisions auth; set it to "false" to force auth off everywhere (dev user).
const authDisabled = env("VITE_AUTH_ENABLED") === "false";

// Broker federation creds: the deployer injects a per-app client when deployed;
// otherwise fall back to the shared live-preview client, which the broker accepts
// for any `*.grok-sandbox.com` callback (see `./preview`).
const grokIssuer = env("GROK_AUTH_ISSUER") ?? GROK_ISSUER_DEFAULT;
const grokClientId = env("GROK_AUTH_CLIENT_ID") ?? PREVIEW_CLIENT_ID;
const grokClientSecret = env("GROK_AUTH_CLIENT_SECRET") ?? PREVIEW_CLIENT_SECRET;

/** True when federated sign-in is active (real auth is enforced). */
export const authConfigured =
  !authDisabled && Boolean(grokClientId && grokClientSecret);

// This app's own Better Auth origin. When deployed the deployer injects the
// public URL. In the sandbox live preview there's no fixed URL (each preview gets
// a dynamic `*.grok-sandbox.com` host), so we hand Better Auth a dynamic baseURL:
// it derives the origin per-request from the (proxied) host, validated against the
// preview allowlist, which makes the OAuth `redirect_uri` the concrete preview URL
// the broker's preview client accepts.
const explicitBaseURL = env("BETTER_AUTH_URL");
// Explicit `string[]` (not a readonly tuple) — Better Auth's DynamicBaseURLConfig
// requires a mutable `allowedHosts: string[]`.
const previewAllowedHosts: string[] = [...PREVIEW_ALLOWED_HOSTS];
// Local `npm run dev` (port 8080 contract). Browsers may send Origin as any of
// these for the same server — trusting only `localhost` rejects `127.0.0.1` and
// breaks email/password with "Invalid origin".
const LOCAL_DEV_ORIGINS: string[] = [
  "http://localhost:8080",
  "http://127.0.0.1:8080",
  "http://[::1]:8080",
];
const baseURL = explicitBaseURL ?? {
  // Include loopback hosts so dynamic baseURL resolves for local email/password
  // (not only the preview wildcard).
  allowedHosts: [...previewAllowedHosts, "localhost", "127.0.0.1", "[::1]"],
  // `auto` → trust both http:// and https:// expansions of allowedHosts
  // (preview is https; local dev is http).
  protocol: "auto" as const,
  fallback: "http://localhost:8080",
};

// Origins Better Auth accepts on credentialed POSTs (sign-up/sign-in, etc.).
// Missing entries here surface as FORBIDDEN "Invalid origin".
const trustedOrigins: string[] = explicitBaseURL
  ? [explicitBaseURL, ...LOCAL_DEV_ORIGINS]
  : [
      // Host wildcards (matched against Origin's host)
      ...previewAllowedHosts,
      // Full-origin wildcards (matched against Origin)
      ...previewAllowedHosts.flatMap((host) => [`https://${host}`, `http://${host}`]),
      ...LOCAL_DEV_ORIGINS,
    ];

const databaseUrl = env("DATABASE_URL");

// Static broker OAuth endpoints (skip OIDC discovery on every sign-in / callback).
// Discovery would cost an extra network hop to the broker before the popup can
// even redirect to Google/X — the live-preview popup felt stuck on the app for
// that whole round-trip. These paths match the broker's discovery document.
const issuerBase = grokIssuer.replace(/\/+$/, "");
const grokAuthorizationUrl = `${issuerBase}/api/auth/oauth2/authorize`;
const grokTokenUrl = `${issuerBase}/api/auth/oauth2/token`;
const grokUserInfoUrl = `${issuerBase}/api/auth/oauth2/userinfo`;

// Real Postgres when `DATABASE_URL` is set (deployed apps), else the app's
// embedded PGLite (preview) via a Kysely dialect — so Better Auth persists to the
// SAME DB as app data, including email/password users. Both use the Better Auth
// schema from `migrations/auth/0001_auth.sql`, copied into `migrations/` when
// the app turns sign-in on.
const database = databaseUrl
  ? new Pool({ connectionString: databaseUrl })
  : { dialect: pgliteDialect(() => getPglite()), type: "postgres" as const };

/** Session token cookie name — also read by the live-preview popup completion page. */
export const SESSION_TOKEN_COOKIE = "__Host-grok-auth.session_token";

// Built separately so the `betterAuth({...})` call stays easy to edit without
// breaking brackets (models often trip on the conditional plugin spread).
const grokOAuthPlugin = authConfigured
  ? genericOAuth({
      config: GROK_PROVIDERS.map(({ providerId, idp }) => ({
        providerId,
        clientId: grokClientId as string,
        clientSecret: grokClientSecret as string,
        // Prefer static endpoints over `discoveryUrl` so initiating (and
        // completing) OAuth does not wait on a broker discovery fetch.
        authorizationUrl: grokAuthorizationUrl,
        tokenUrl: grokTokenUrl,
        userInfoUrl: grokUserInfoUrl,
        scopes: ["openid", "profile", "email"],
        // `prompt: "login"` forces the broker to re-authenticate against the
        // upstream on every sign-in instead of silently reusing an existing
        // broker session. Combined with the broker sending Google
        // `prompt=select_account`, the user always gets the account chooser
        // and can pick (or switch) which account to sign in with.
        authorizationUrlParams: { idp, prompt: "login" },
      })),
    })
  : null;

export const auth = betterAuth({
  baseURL,
  // Deployed apps inject BETTER_AUTH_SECRET. Preview: process-stable secret on
  // globalThis so HMR doesn't invalidate PGLite-backed sessions (see above).
  secret: env("BETTER_AUTH_SECRET") ?? previewAuthSecret(),
  database,

  // CSRF / origin check for credentialed auth POSTs (email sign-up/sign-in, …).
  // See `trustedOrigins` construction above — must cover live preview hosts AND
  // local loopback variants, or clients get "Invalid origin".
  trustedOrigins,

  // Encrypt broker-issued OAuth tokens at rest, and treat the broker's upstreams
  // as trusted first-party identities. The broker owns identity and X emails are
  // synthetic/unverified, so WITHOUT this a login can fail with
  // `account_not_linked` (Better Auth refuses to attach an untrusted, unverified
  // identity to an existing user). Google and X carry DISTINCT emails, so this
  // never merges them into one user — they stay separate identities.
  account: {
    encryptOAuthTokens: true,
    accountLinking: {
      enabled: true,
      trustedProviders: [
        ...GROK_PROVIDERS.map((p) => p.providerId),
        GATE_PROVIDER_ID,
      ],
      // X's synthetic email is never "verified", so don't gate linking on the
      // local user's email-verified state.
      requireLocalEmailVerified: false,
    },
  },

  // Cache the session in the short-lived signed `session_data` cookie so reads
  // (incl. the client's `/get-session`) skip the DB — this shrinks the "loading"
  // window and reduces auth flicker. See the `auth` skill for the full
  // flicker-prevention guidance (gate on `isPending`; SSR the session).
  session: { cookieCache: { enabled: true, maxAge: 300 } },

  // Local email/password — toggled only via `./email-password` (not a plugin).
  ...(emailAndPasswordEnabled ? { emailAndPassword: { enabled: true } } : {}),

  // `__Host-` prefixed cookies: the browser REFUSES any same-named cookie that
  // carries a `Domain` attribute, so a sibling `*.grok.me` app cannot "toss" a
  // `Domain=.grok.me` session cookie onto this app. `__Host-` requires Secure +
  // Path=/ + no Domain; Better Auth otherwise uses `__Secure-` (which permits
  // Domain), so we drop its auto prefix (`useSecureCookies: false`) and set
  // Secure + the names ourselves. (Browsers allow Secure cookies on
  // `http://localhost`, so local dev still works.)
  advanced: {
    useSecureCookies: false,
    defaultCookieAttributes: { secure: true, sameSite: "lax", path: "/" },
    cookies: {
      session_token: { name: SESSION_TOKEN_COOKIE },
      session_data: { name: "__Host-grok-auth.session_data" },
      account_data: { name: "__Host-grok-auth.account_data" },
      dont_remember: { name: "__Host-grok-auth.dont_remember" },
    },
  },

  plugins: [
    gateIdentitySessions(),

    // One genericOAuth provider per upstream (when auth is on), all federating
    // to the broker with the SAME client and differing only by the `idp` hint.
    ...(grokOAuthPlugin ? [grokOAuthPlugin] : []),

    // Accept `Authorization: Bearer <session-token>` as an alternative to the
    // cookie. Needed for the LIVE PREVIEW: the app runs in an embedded iframe
    // where cookies are partitioned, so after popup sign-in it authenticates with
    // a bearer token instead (see `client.ts` / the `auth` skill). The hook only
    // fires when an Authorization header is present, so the cookie path
    // (deployed apps) is unaffected.
    bearer(),

    // Bridges Better Auth's Set-Cookie into TanStack Start responses. MUST be
    // last so it runs after every other plugin's hooks.
    tanstackStartCookies(),
  ],
});

export function readSessionToken(): string | null {
  return getCookie(SESSION_TOKEN_COOKIE) ?? null;
}

// Re-exported for convenience; the array lives in the dependency-free
// `providers.ts` so the client can import it too.
export { GROK_PROVIDERS } from "./providers";

````

## `frontend_demo/src/lib/auth/sign-in-gate.test.ts`
````ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { resolveSignInGateState } from "./sign-in-gate.ts";

describe("resolveSignInGateState", () => {
  it("is pending while the session check is in flight, user or not", () => {
    assert.equal(
      resolveSignInGateState({ isPending: true, hasUser: false }),
      "pending",
    );
    assert.equal(
      resolveSignInGateState({ isPending: true, hasUser: true }),
      "pending",
    );
  });

  it("is signed_in once a user is present", () => {
    assert.equal(
      resolveSignInGateState({ isPending: false, hasUser: true }),
      "signed_in",
    );
  });

  it("is signed_out only after the check resolved with no user", () => {
    assert.equal(
      resolveSignInGateState({ isPending: false, hasUser: false }),
      "signed_out",
    );
  });
});

````

## `frontend_demo/src/lib/auth/sign-in-gate.ts`
````ts
export type SignInGateState = "pending" | "signed_in" | "signed_out";

export type SignInGateInput = {
  isPending: boolean;
  hasUser: boolean;
};

export function resolveSignInGateState(
  input: SignInGateInput,
): SignInGateState {
  if (input.isPending) return "pending";
  return input.hasUser ? "signed_in" : "signed_out";
}

````

## `frontend_demo/src/lib/auth/use-current-user.ts`
````ts
import { useMemo } from "react";
import { authClient, authEnabled } from "./client";

/** Normalized user shape used across the app, auth on or off. */
export type AppUser = {
  id: string;
  displayName: string | null;
  primaryEmail: string | null;
  profileImageUrl: string | null;
  /** True when this is the sandbox/dev fallback (auth not configured). */
  isDevFallback: boolean;
};

/**
 * Stable fallback user, used ONLY when auth is disabled
 * (`VITE_AUTH_ENABLED=false`, the shipped default). With auth on, the sandbox
 * live preview does real sign-in via the baked preview client. Its id is
 * `"dev-user"` — the SAME id `verify.server.ts` returns server-side — so per-user
 * rows written in that mode belong to one consistent owner.
 */
export const DEV_USER: AppUser = {
  id: "dev-user",
  displayName: "Dev User",
  primaryEmail: "dev@example.com",
  profileImageUrl: null,
  isDevFallback: true,
};

/** `useCurrentUserState()` result: the user plus the session-loading flag. */
export type CurrentUserState = {
  /** The user — `null` BOTH while the session loads and when signed out. */
  user: AppUser | null;
  /** True while the session is still resolving — don't treat `user: null` as signed out yet. */
  isPending: boolean;
};

const DEV_STATE: CurrentUserState = { user: DEV_USER, isPending: false };

/**
 * Current user + loading state. Same behavior in live preview and when deployed:
 *   - Auth enabled -> the real signed-in user; `user` is `null` while
 *                            the session resolves (`isPending: true`) and when
 *                            signed out (`isPending: false`). Session comes from
 *                            Better Auth `useSession()` → `/api/auth/get-session`
 *                            (cookie when deployed; bearer in live preview).
 *   - Auth disabled (`VITE_AUTH_ENABLED=false`) -> `DEV_USER`, never pending.
 *
 * Protect a route by waiting out `isPending` before acting on `user` —
 * redirecting on `user: null` alone bounces signed-in visitors to sign-in on
 * every hard reload:
 *
 *   import { RedirectToSignIn } from "@/lib/auth/gates";
 *   const { user, isPending } = useCurrentUserState();
 *   if (isPending) return null;              // still resolving — don't redirect yet
 *   if (!user) return <RedirectToSignIn />;  // definitely signed out
 *
 * `authEnabled` is a module-level constant fixed at load, so the guarded hook
 * call keeps a stable hook order across every render of a given component.
 */
export function useCurrentUserState(): CurrentUserState {
  if (!authEnabled) return DEV_STATE;
  // eslint-disable-next-line react-hooks/rules-of-hooks -- authEnabled is constant for the app's lifetime
  return useSessionUserState();
}

function useSessionUserState(): CurrentUserState {
  const { data, isPending } = authClient.useSession();
  const id = data?.user.id;
  const displayName = data?.user.name ?? null;
  const primaryEmail = data?.user.email ?? null;
  const profileImageUrl = data?.user.image ?? null;
  const user = useMemo<AppUser | null>(
    () => (id ? { id, displayName, primaryEmail, profileImageUrl, isDevFallback: false } : null),
    [id, displayName, primaryEmail, profileImageUrl],
  );
  return useMemo(() => ({ user, isPending }), [user, isPending]);
}

/**
 * Convenience view of `useCurrentUserState().user` for display (e.g.
 * `user?.displayName ?? "Guest"`). NOTE: `null` means *loading OR signed out* —
 * for redirects/guards use `useCurrentUserState()` and check `isPending`.
 */
export function useCurrentUser(): AppUser | null {
  return useCurrentUserState().user;
}

````

## `frontend_demo/src/lib/auth/verify.server.ts`
````ts
import { getRequest } from "@tanstack/react-start/server";
import { gateIdentityEnabled } from "./gate-identity.server";
import { auth, authConfigured } from "./server";

/**
 * Server-side session resolution (server-only).
 *
 * Because this app runs its OWN Better Auth at same-origin `/api/auth/*`, the
 * session cookie is sent with every request to this app — server functions AND
 * SSR loaders included. So we resolve the user straight from the request cookies
 * via `auth.api.getSession` (no client-minted JWT needed). Never trust a
 * client-supplied user id — only the result of this verification.
 */

/** True when a real database is configured server-side. */
const databaseConfigured = Boolean(process.env.DATABASE_URL?.trim());

/** Re-export so callers can branch on it without importing `server.ts`. */
export { authConfigured };

if (databaseConfigured && !authConfigured) {
  console.error(
    "[auth] DATABASE_URL is set but auth is disabled (VITE_AUTH_ENABLED=false) " +
      "— requireUserId() will reject every request (fail closed) rather than " +
      "share one dev user on a real database.",
  );
}

/** Dev fallback user id, used only when auth is disabled (VITE_AUTH_ENABLED=false). */
export const DEV_USER_ID = "dev-user";

/**
 * Thrown by `requireUserId` when the caller has no valid session. Carries
 * `status: 401`; the message is a stable contract — match
 * `err.message === "Unauthorized"` client-side to send the visitor to sign-in.
 */
export class UnauthorizedError extends Error {
  readonly status = 401;
  constructor() {
    super("Unauthorized");
    this.name = "UnauthorizedError";
  }
}

export type VerifiedUser = { id: string; email: string | null };

/**
 * Resolve the signed-in user from the current request, or `null` when auth isn't
 * configured / nobody is signed in. Safe to call from server functions and SSR
 * loaders.
 *
 * `bearerToken` is for the LIVE PREVIEW: the app runs in a partitioned iframe
 * whose cookies don't reach the server, so `authMiddleware` forwards the session
 * as a bearer token, which we present as `Authorization: Bearer …` (the `bearer`
 * plugin resolves it). When deployed no token is passed and the cookie is used.
 */
export async function getSessionUser(
  bearerToken?: string,
): Promise<VerifiedUser | null> {
  if (!authConfigured && !gateIdentityEnabled()) return null;
  const request = getRequest();
  if (!request) return null;
  let headers = request.headers;
  if (bearerToken) {
    headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${bearerToken}`);
  }
  const session = await auth.api.getSession({ headers });
  if (!session?.user) return null;
  return { id: session.user.id, email: session.user.email ?? null };
}

/**
 * Resolve the current user id for a server function, or throw when unauthorized.
 * Prefer `authMiddleware` (`./middleware`), which calls this for you.
 * - Auth enabled -> the verified session user id; throws
 *   `UnauthorizedError` when signed out. Works in the sandbox preview too (real
 *   sign-in via the baked preview client).
 * - Auth disabled (`VITE_AUTH_ENABLED=false`) + `DATABASE_URL` set -> throw (fail
 *   closed): one shared dev user on a real database would let every visitor
 *   read/write everyone's rows.
 * - Auth disabled + no database -> the shared dev user id.
 */
export async function requireUserId(bearerToken?: string): Promise<string> {
  if (!authConfigured && !gateIdentityEnabled()) {
    if (databaseConfigured) {
      throw new Error(
        "Auth is disabled (VITE_AUTH_ENABLED=false) but DATABASE_URL is set — " +
          "refusing to fall back to the shared dev user against a real database.",
      );
    }
    return DEV_USER_ID;
  }
  const user = await getSessionUser(bearerToken);
  if (!user) throw new UnauthorizedError();
  return user.id;
}

````

## `frontend_demo/src/lib/boq.ts`
````ts
export type FindingKind = "outlier" | "vague" | "qty" | "gap";

export type BoqItem = {
  oz: string;
  title: string;
  longText: string;
  qty: number;
  unit: string;
  /** Observed median unit price from same-trade bids (€). null = no comparable. */
  benchmark: number | null;
  /** Share of the benchmark that moves with the wage slider (0–1). */
  laborShare: number;
  hoursPerUnit: number;
  materialPerUnit: number;
  kind: FindingKind | null;
  rationale: string;
  rfi: string;
  remarks?: string[];
  preambles?: string[];
};

export function naturalOzCompare(a: string, b: string): number {
  const aa = String(a).split(".");
  const bb = String(b).split(".");
  const length = Math.max(aa.length, bb.length);
  for (let index = 0; index < length; index += 1) {
    const left = aa[index] ?? "";
    const right = bb[index] ?? "";
    const leftNumber = /^\d+$/.test(left);
    const rightNumber = /^\d+$/.test(right);
    if (leftNumber && rightNumber) {
      const difference = Number(left) - Number(right);
      if (difference !== 0) return difference;
    } else {
      const difference = left.localeCompare(right, "de");
      if (difference !== 0) return difference;
    }
  }
  return 0;
}

/** Real submitted total on StBALV23040.D86 — the reveal number. */
export const REVEAL_BID = 897_305.45;

export const SAMPLE_NAME = "NUMMER_001 · blank BoQ (248 positions)";

export const ITEMS: BoqItem[] = [
  {
    oz: "01.01.0010",
    title: "Baugrube ausheben, Bodenklasse 3–5",
    longText: "Aushub einschließlich Laden und Abfuhr bis 15 km. Böschungen nach statischer Vorgabe.",
    qty: 1840,
    unit: "m³",
    benchmark: 18.4,
    laborShare: 0.35,
    hoursPerUnit: 0.08,
    materialPerUnit: 4.2,
    kind: null,
    rationale: "Unit price sits inside the reference band for excavation (median €18.40/m³ across priced sewer jobs).",
    rfi: "",
  },
  {
    oz: "01.02.0140",
    title: "Rohrgraben DN 300, einschließlich Verbau",
    longText: "Graben für Steinzeugrohr DN 300, Verbau nach Wahl des AN, Sohle plan.",
    qty: 620,
    unit: "m",
    benchmark: 86,
    laborShare: 0.55,
    hoursPerUnit: 0.55,
    materialPerUnit: 22,
    kind: "vague",
    rationale: "“Verbau nach Wahl des AN” leaves shoring method and groundwater unspecified. In  the priced twin this line alone moves five-figure money.",
    rfi: "Bitte die geforderte Verbauart (Verbaubox / Trägerbohlwand / geböscht) und den Bemessungswasserstand verbindlich vorgeben, damit die Position ohne Nachtrag kalkulierbar ist.",
  },
  {
    oz: "01.02.0210",
    title: "Steinzeugrohr DN 300 liefern und verlegen",
    longText: "Kanalrohr Steinzeug DN 300, Verbindungssystem F, einschließlich Dichtung.",
    qty: 610,
    unit: "m",
    benchmark: 142,
    laborShare: 0.28,
    hoursPerUnit: 0.22,
    materialPerUnit: 96,
    kind: "qty",
    rationale: "Pipe length is 10 m shorter than the trench (620 m). A missing connection or a typo — either way the join does not close.",
    rfi: "Die Rohrleitung (610 m) ist kürzer als der zugehörige Graben (620 m). Bitte die maßgebende Länge bestätigen.",
  },
  {
    oz: "01.03.0040",
    title: "Schacht DN 1000, Tiefe bis 3,00 m",
    longText: "Fertigteilschacht einschließlich Schachtabdeckung Klasse D 400.",
    qty: 14,
    unit: "St",
    benchmark: 2480,
    laborShare: 0.4,
    hoursPerUnit: 6.5,
    materialPerUnit: 1450,
    kind: null,
    rationale: "Comparable shafts in the priced set cluster tightly around €2,480.",
    rfi: "",
  },
  {
    oz: "01.04.0080",
    title: "Heizungswartung Baustelle, wöchentlich",
    longText: "Bereitstellung und wöchentliche Wartung der Baustellenheizung für die Wintermonate.",
    qty: 28,
    unit: "Wo",
    benchmark: 0.2,
    laborShare: 0.9,
    hoursPerUnit: 1.2,
    materialPerUnit: 35,
    kind: "outlier",
    rationale: "A real competitor priced this at €0.20/week (total €5.60). Same-trade medians for site heating sit two orders of magnitude higher. Classic speculative underprice on a line that will be measured.",
    rfi: "Die Position ist mit €0,20/Woche nicht auskömmlich. Bitte Leistungsumfang (Gerätetyp, Brennstoff, Betriebsstunden) festlegen, damit ein marktüblicher Einheitspreis angeboten werden kann.",
  },
  {
    oz: "02.01.0030",
    title: "Tragschicht 0/32, d = 20 cm",
    longText: "Frostschutzschicht liefern, einbauen und verdichten.",
    qty: 2400,
    unit: "m²",
    benchmark: 11.6,
    laborShare: 0.32,
    hoursPerUnit: 0.04,
    materialPerUnit: 6.8,
    kind: null,
    rationale: "Inside the reference band for unbound base.",
    rfi: "",
  },
  {
    oz: "02.01.0110",
    title: "Asphaltdeckschicht AC 11, d = 4 cm",
    longText: "Deckschicht nach ZTV Asphalt, Einbauort nach Vorgabe AG.",
    qty: 2380,
    unit: "m²",
    benchmark: 22.5,
    laborShare: 0.25,
    hoursPerUnit: 0.03,
    materialPerUnit: 16.4,
    kind: "vague",
    rationale: "“Einbauort nach Vorgabe AG” with no stationing. Area is 20 m² under the base course — small, but the clause is a change-order door.",
    rfi: "Bitte den Einbauort und die Verkehrsfreigabe (Belastungsklasse) vor Angebotsabgabe verbindlich angeben.",
  },
  {
    oz: "02.03.0020",
    title: "Bordstein hoch 15/25 setzen",
    longText: "Bordstein aus Beton, einschließlich Fundament und Rückenstütze.",
    qty: 480,
    unit: "m",
    benchmark: 38,
    laborShare: 0.5,
    hoursPerUnit: 0.22,
    materialPerUnit: 14,
    kind: null,
    rationale: "Matches priced kerb lines within a few percent.",
    rfi: "",
  },
  {
    oz: "03.01.0010",
    title: "Bedarfsposition: Kampfmittelräumung",
    longText: "Eventualposition. Sondierung und Bergung nach Bedarf, Abrechnung nach Aufwand.",
    qty: 1,
    unit: "psch",
    benchmark: 4500,
    laborShare: 0.7,
    hoursPerUnit: 40,
    materialPerUnit: 800,
    kind: "gap",
    rationale: "Provisional lump sum with no quantity driver. High chance it is either never called or explodes. Price it tactically, not as a firm cost.",
    rfi: "Bitte den Erwartungswert (Sondierungsfläche, Fundwahrscheinlichkeit) angeben oder die Position als Bedarfsposition ohne Wertung kennzeichnen.",
  },
  {
    oz: "03.02.0060",
    title: "Wasserhaltung, offene Haltung",
    longText: "Wasserhaltung für die Bauzeit, Pumpen und Ableitung, nach Abstimmung mit dem AG.",
    qty: 12,
    unit: "Wo",
    benchmark: null,
    laborShare: 0.6,
    hoursPerUnit: 8,
    materialPerUnit: 220,
    kind: "vague",
    rationale: "No comparable in the 720 priced same-trade items (kein Vergleichswert). Scope (“nach Abstimmung”) cannot be priced firmly.",
    rfi: "Bitte den Bemessungszufluss, die Ableitstelle und die maximale Betriebsdauer festlegen.",
  },
  {
    oz: "03.04.0020",
    title: "Verkehrssicherung nach RSA",
    longText: "Aufstellen, Vorhalten und Abbauen der Verkehrszeichen und Absperrungen.",
    qty: 16,
    unit: "Wo",
    benchmark: 640,
    laborShare: 0.45,
    hoursPerUnit: 3.2,
    materialPerUnit: 180,
    kind: null,
    rationale: "Weekly traffic management sits near the reference median.",
    rfi: "",
  },
  {
    oz: "04.01.0100",
    title: "Hausanschluss DN 150 anbinden",
    longText: "Anbindung bestehender Hausanschlüsse, Lage nach örtlichem Aufmaß.",
    qty: 2,
    unit: "St",
    benchmark: 890,
    laborShare: 0.65,
    hoursPerUnit: 6,
    materialPerUnit: 210,
    kind: "qty",
    rationale: "Only 2 connections are billed. Street length and shaft count imply closer to 18–22. If the count is wrong, a high unit price captures the overrun.",
    rfi: "Im LV sind 2 Hausanschlüsse ausgeschrieben. Nach Schachtanzahl und Straßenlänge erwarten wir eine deutlich höhere Stückzahl. Bitte die vollständige Anschlusszählung beifügen.",
  },
];

export type Rates = {
  earth: number;
  pipe: number;
  pave: number;
  fitter: number;
  machine: number;
  material: number;
  agk: number;
  wg: number;
};

export type LineFix = { qty: number; tactic: number };

export const BASE_WAGE = 48;
export const BASE_MACHINE = 95;
export const DEFAULT_RATES: Rates = {
  earth: 46,
  pipe: 52,
  pave: 49,
  fitter: 58,
  machine: 95,
  material: 1,
  agk: 12,
  wg: 8,
};

export type Crew = "earth" | "pipe" | "pave" | "fitter";

export function crewOf(oz: string): Crew {
  if (oz.startsWith("02.")) return "pave";
  if (oz.startsWith("04.") || oz.startsWith("01.02") || oz.startsWith("01.03")) return "pipe";
  if (oz.startsWith("01.04") || oz.startsWith("03.02") || oz.startsWith("03.04")) return "fitter";
  return "earth";
}

const CREW_LABEL: Record<Crew, string> = {
  earth: "Earthworks crew",
  pipe: "Pipe crew",
  pave: "Paving crew",
  fitter: "Fitter",
};

export function crewLabel(oz: string) {
  return CREW_LABEL[crewOf(oz)];
}

function overhead(r: Rates) {
  return (1 + r.agk / 100) * (1 + r.wg / 100);
}

const BASE_OH = (1 + 0.12) * (1 + 0.08);

/** Unit price from the observed bid, moved by the crew that actually does the work. */
export function unitPrice(item: BoqItem, r: Rates, tactic = 1): { ep: number; source: "benchmark" | "built-up" } {
  const oh = overhead(r);
  const crewW = r[crewOf(item.oz)];
  const wageFactor = 1 + (crewW / BASE_WAGE - 1) * 1.6;
  const machFactor = 1 + (r.machine / BASE_MACHINE - 1) * 1.2;
  if (item.benchmark != null && item.kind !== "outlier") {
    const labor = item.laborShare;
    const machineInsideLabor = crewOf(item.oz) === "earth" || crewOf(item.oz) === "pave" ? 0.45 : 0.2;
    const scaled =
      item.benchmark *
      ((1 - labor) * (0.55 + 0.45 * r.material) +
        labor * ((1 - machineInsideLabor) * wageFactor + machineInsideLabor * machFactor));
    return { ep: scaled * (oh / BASE_OH) * tactic, source: "benchmark" };
  }
  const machineShare = crewOf(item.oz) === "fitter" ? 0.65 : 0.3;
  const ekt =
    item.hoursPerUnit * (1 - machineShare) * crewW +
    item.hoursPerUnit * machineShare * r.machine +
    item.materialPerUnit * r.material;
  return { ep: ekt * oh * tactic, source: "built-up" };
}

export const BILL_SCALE = 2.72;

export function lineTotal(item: BoqItem, r: Rates, fix?: LineFix) {
  const qty = fix?.qty ?? item.qty;
  const tactic = fix?.tactic ?? 1;
  return unitPrice(item, r, tactic).ep * qty * BILL_SCALE;
}

export function estimateTotal(items: BoqItem[], r: Rates, fixes: Record<string, LineFix> = {}) {
  return items.reduce((s, it) => s + lineTotal(it, r, fixes[it.oz]), 0);
}

/** Scale the visible sample so the default slider lands near a known gap vs the real bid.
 *  The sample is a slice; we report it as the modeled share of the 248-item bill.
 */
export const SAMPLE_WEIGHT = 1;

export type Finding = {
  item: BoqItem;
  ep: number;
  total: number;
  leverage: number;
  source: "benchmark" | "built-up";
};

export function findings(items: BoqItem[], r: Rates, fixes: Record<string, LineFix> = {}): Finding[] {
  return items
    .filter((it) => it.kind)
    .map((item) => {
      const fix = fixes[item.oz];
      const tactic = fix?.tactic ?? 1;
      const qty = fix?.qty ?? item.qty;
      const { ep, source } = unitPrice(item, r, tactic);
      const total = ep * qty * BILL_SCALE;
      const exposure = item.kind === "qty" ? Math.abs(item.qty - qty) * ep * BILL_SCALE + total * 0.12 : total * 0.18;
      const leverage = item.kind === "outlier" ? Math.max(total, 12000) : Math.max(exposure, 4000);
      return { item, ep, total, leverage, source };
    })
    .sort((a, b) => b.leverage - a.leverage);
}

export function euro(n: number) {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(n);
}

export function num(n: number, d = 2) {
  return new Intl.NumberFormat("de-DE", { maximumFractionDigits: d, minimumFractionDigits: d }).format(n);
}

````

## `frontend_demo/src/lib/db.ts`
````ts
import { pendingMigrations } from "../../scripts/migration-plan.mjs";

/** Which database backend is active. */
export type DbSource = "neon" | "pglite";

// An empty/whitespace DATABASE_URL (an easy misconfig in deploy UIs) must mean
// "unset" — otherwise production would silently run on the PGLite fallback.
const rawDatabaseUrl =
  typeof process !== "undefined" ? process.env.DATABASE_URL : undefined;
const databaseUrl =
  rawDatabaseUrl && rawDatabaseUrl.trim() ? rawDatabaseUrl : undefined;

/**
 * Active backend: real **Neon** when `DATABASE_URL` is set (deployed / configured
 * sandbox), otherwise a local embedded **PGLite** (Postgres compiled to WASM) so
 * the app has a working database even with nothing configured — the live preview
 * included. Swap in Neon later by just setting `DATABASE_URL`; no code changes.
 */
export const dbSource: DbSource = databaseUrl ? "neon" : "pglite";

/**
 * Minimal shared SQL surface, satisfied by both Neon and PGLite. Both the
 * tagged-template and `.query()` forms resolve to an array of row objects:
 *
 *   const sql = await getSql();
 *   const rows = await sql`select * from todos where id = ${id}`; // parameterized
 *   const rows2 = await sql.query("select * from todos where id = $1", [id]);
 */
export interface Sql {
  <T = Record<string, unknown>>(
    strings: TemplateStringsArray,
    ...values: unknown[]
  ): Promise<T[]>;
  query<T = Record<string, unknown>>(
    text: string,
    params?: unknown[],
  ): Promise<T[]>;
}

/**
 * Init state lives on globalThis as promises: dev HMR creates new instances of
 * this module, and two instances racing module-level state would open a second
 * pool or run two concurrent PGLite migration passes (whose duplicate
 * `_migrations` insert rejects — and would get memoized, poisoning every later
 * `getSql()`). A failed init clears its slot so the next call retries.
 */
const globalRef = globalThis as typeof globalThis & {
  __pgSqlPromise__?: Promise<Sql>;
  __pgliteInstance__?: Promise<import("@electric-sql/pglite").PGlite>;
  __pgliteMigrateChain__?: Promise<void>;
};

/**
 * Result-type parity: Postgres sends every value as text plus a type OID — the
 * JS value is the DRIVER's parsing choice, and pg and PGLite disagree (pg:
 * int8 -> string, date -> local-midnight Date; PGLite: int8 -> BigInt, which
 * JSON.stringify rejects, date -> UTC Date). Normalize both so preview and
 * production return identical, JSON-safe shapes:
 *   int8/bigint (incl. count(*)) -> number (past 2^53 loses precision — cast
 *                                   `::text` if you ever need huge integers)
 *   date                         -> 'YYYY-MM-DD' string
 *   interval                     -> Postgres interval text
 * numeric already comes back as a string on both (arbitrary precision).
 */
const OID_INT8 = 20;
const OID_DATE = 1082;
const OID_INTERVAL = 1186;
const identity = (v: string) => v;

type Run = <T>(text: string, params: unknown[]) => Promise<T[]>;

/** Wrap a query runner in the tagged-template + `.query()` `Sql` surface. */
function toSql(run: Run): Sql {
  const sql = (async <T = Record<string, unknown>>(
    strings: TemplateStringsArray,
    ...values: unknown[]
  ): Promise<T[]> => {
    // Rebuild with $1, $2, … placeholders so values stay parameterized.
    let text = strings[0];
    for (let i = 0; i < values.length; i += 1) text += `$${i + 1}${strings[i + 1]}`;
    return run<T>(text, values);
  }) as unknown as Sql;
  sql.query = <T = Record<string, unknown>>(text: string, params: unknown[] = []) =>
    run<T>(text, params);
  return sql;
}

function createNeonSql(): Promise<Sql> {
  globalRef.__pgSqlPromise__ ??= (async () => {
    // Regular Postgres driver: node-postgres (`pg`) — works directly with Neon's
    // pooled endpoint. One pool per process; warm serverless instances reuse it.
    const { Pool, types } = await import("pg");
    types.setTypeParser(OID_INT8, Number);
    types.setTypeParser(OID_DATE, identity);
    types.setTypeParser(OID_INTERVAL, identity);
    const pool = new Pool({ connectionString: databaseUrl });
    return toSql(async <T>(text: string, params: unknown[]) => {
      const res = await pool.query(text, params);
      return res.rows as T[];
    });
  })().catch((err) => {
    globalRef.__pgSqlPromise__ = undefined;
    throw err;
  });
  return globalRef.__pgSqlPromise__;
}

async function createPgliteSql(): Promise<Sql> {
  // Embedded Postgres, imported on demand so it never loads on the Neon path.
  // One in-memory instance per process, shared across HMR module instances, so
  // data survives source edits (it resets on dev-server restart).
  globalRef.__pgliteInstance__ ??= (async () => {
    const { PGlite } = await import("@electric-sql/pglite");
    const pg = new PGlite({
      parsers: {
        [OID_INT8]: Number,
        [OID_DATE]: identity,
        [OID_INTERVAL]: identity,
      },
    });
    await pg.waitReady;
    await pg.exec(
      "create table if not exists _migrations (name text primary key, applied_at timestamptz not null default now())",
    );
    return pg;
  })().catch((err) => {
    globalRef.__pgliteInstance__ = undefined;
    throw err;
  });
  const pg = await globalRef.__pgliteInstance__;

  // Apply migrations/ (the single schema source) so preview matches production.
  // SQL is inlined by the bundler via import.meta.glob (no runtime fs); applied
  // files are tracked in _migrations. The glob does not descend, so the opt-in
  // auth schema under migrations/auth/ stays out. Runs once per module instance
  // — so an HMR reload after adding a migration file applies it live — with
  // passes serialized on a global chain so concurrent callers never
  // double-apply.
  const migrate = async (): Promise<void> => {
    const migrations = import.meta.glob("/migrations/*.sql", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;
    const doneRows = await pg.query<{ name: string }>(
      "select name from _migrations",
    );
    const done = doneRows.rows.map((r) => r.name);
    for (const { name, path } of pendingMigrations(Object.keys(migrations), done)) {
      // Apply + record atomically (parity with scripts/migrate.mjs) so a failed
      // statement can't leave a file half-applied but untracked.
      await pg.transaction(async (tx) => {
        await tx.exec(migrations[path]);
        await tx.query("insert into _migrations (name) values ($1)", [name]);
      });
    }
  };
  const pass = (globalRef.__pgliteMigrateChain__ ?? Promise.resolve())
    .catch(() => undefined) // an earlier failed pass must not wedge the chain
    .then(migrate);
  globalRef.__pgliteMigrateChain__ = pass;
  await pass;

  return toSql(async <T>(text: string, params: unknown[]) => {
    const result = await pg.query<T>(text, params);
    return result.rows;
  });
}

let sqlPromise: Promise<Sql> | null = null;

async function createSql(): Promise<Sql> {
  if (typeof window !== "undefined") {
    throw new Error(
      "@/lib/db is server-only — call getSql() from a createServerFn handler " +
        "or a server route loader, never from client code.",
    );
  }
  return dbSource === "neon" ? createNeonSql() : createPgliteSql();
}

/**
 * Get the shared, **server-only** SQL client. Neon when `DATABASE_URL` is set,
 * otherwise the local PGLite fallback. Memoized — safe to call per request.
 *
 * Schema comes from `migrations/*.sql`, auto-applied before the first query on
 * both backends — define tables there, never inline in server functions.
 */
export function getSql(): Promise<Sql> {
  sqlPromise ??= createSql().catch((err) => {
    sqlPromise = null; // don't memoize failures — let the next call retry
    throw err;
  });
  return sqlPromise;
}

/**
 * The shared PGLite instance (preview only), with `migrations/*.sql` applied.
 * Lets Better Auth persist to the SAME embedded DB as app data in preview (via a
 * Kysely dialect). Throws when `DATABASE_URL` is set (that path uses Neon).
 */
export async function getPglite(): Promise<import("@electric-sql/pglite").PGlite> {
  if (dbSource !== "pglite") {
    throw new Error("getPglite() is only available on the PGLite fallback (no DATABASE_URL)");
  }
  await getSql();
  const pg = await globalRef.__pgliteInstance__;
  if (!pg) throw new Error("PGLite instance failed to initialize");
  return pg;
}

/**
 * Finish DB bootstrap before the server handles traffic.
 *
 * - **PGLite** (preview / no `DATABASE_URL`): open the in-memory DB and apply
 *   `migrations/*.sql`. Idempotent — concurrent callers share one promise.
 * - **Neon**: no-op (pool is created lazily on first query).
 *
 * Vite `configureServer` awaits this at dev startup; production imports of this
 * module kick it off immediately (see bottom of file).
 */
export function ensureDbReady(): Promise<void> {
  if (dbSource !== "pglite") return Promise.resolve();
  return getSql().then(() => undefined);
}

// Server-only eager start: kick PGLite bootstrap as soon as this module loads in
// Node. Client bundles never hit this path (`getSql` throws in the browser).
const globalBoot = globalThis as typeof globalThis & {
  __pgBootstrapPromise__?: Promise<void>;
};
if (typeof window === "undefined" && dbSource === "pglite") {
  globalBoot.__pgBootstrapPromise__ ??= ensureDbReady().catch((err) => {
    globalBoot.__pgBootstrapPromise__ = undefined;
    console.error("[db] PGLite bootstrap failed:", err);
    throw err;
  });
}

````

## `frontend_demo/src/lib/draft-rfi.ts`
````ts
import { createServerFn } from "@tanstack/react-start";

export type DraftInput = {
  oz: string;
  title: string;
  longText: string;
  rationale: string;
  draft: string;
};

export const sharpenRfi = createServerFn({ method: "POST" })
  .validator((input: DraftInput) => input)
  .handler(async ({ data }) => {
    const apiKey = process.env.XAI_API_KEY;
    if (!apiKey) return { ok: false as const, error: "AI is not available in this environment" };

    const res = await fetch("https://api.x.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "grok-4.5",
        temperature: 0.2,
        max_tokens: 280,
        messages: [
          {
            role: "system",
            content:
              "You write one short Bieterfrage for a German construction tender, in formal German, citing VOB/A only if it fits. No price. No preamble. One paragraph the estimator can paste into a letter.",
          },
          {
            role: "user",
            content: `Position ${data.oz}: ${data.title}\n${data.longText}\nWhy it is risky: ${data.rationale}\nCurrent draft: ${data.draft}`,
          },
        ],
      }),
    });
    if (!res.ok) return { ok: false as const, error: `Model error ${res.status}` };
    const body = (await res.json()) as { choices?: { message?: { content?: string } }[] };
    const text = body.choices?.[0]?.message?.content?.trim() ?? "";
    if (!text) return { ok: false as const, error: "Empty answer" };
    return { ok: true as const, text };
  });

````

## `frontend_demo/src/lib/env.server.ts`
````ts
export function env(key: string): string | undefined {
  const v = process.env[key]?.trim();
  return v || undefined;
}

/**
 * Workspace preview vs deployed app. The deployer writes GROK_PROJECT_ID on
 * every publish; the sandbox preview never has it. Single source of truth for
 * the split — gate audience, gate endpoints and connector-token semantics all
 * key off this predicate.
 */
export function isWorkspacePreview(): boolean {
  return !env("GROK_PROJECT_ID");
}

````

## `frontend_demo/src/lib/error-component.tsx`
````tsx
import type { ErrorComponentProps } from "@tanstack/react-router";
import { TriangleAlert } from "lucide-react";

const FALLBACK_MESSAGE = "An unexpected error occurred. Try reloading the page.";

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string" && error) return error;
  return FALLBACK_MESSAGE;
}

export function AppErrorComponent({ error }: ErrorComponentProps) {
  return (
    <main
      className={
        "flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center " +
        "bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50"
      }
    >
      <span className="text-red-500" aria-hidden="true">
        <TriangleAlert className="size-10" strokeWidth={2} />
      </span>
      <h1 className="text-lg font-semibold">Something went wrong</h1>
      <p className="max-w-md text-sm break-words text-zinc-500 dark:text-zinc-400">
        {errorMessage(error)}
      </p>
    </main>
  );
}

````

## `frontend_demo/src/router.tsx`
````tsx
import { createRouter } from "@tanstack/react-router";
import { AppErrorComponent } from "@/lib/error-component";
import { routeTree } from "./routeTree.gen";

export function getRouter() {
  return createRouter({
    routeTree,
    defaultErrorComponent: AppErrorComponent,
  });
}

````

## `frontend_demo/src/routes/__root.tsx`
````tsx
import { createRootRoute, HeadContent, Outlet, Scripts } from "@tanstack/react-router";
import { AuthProvider } from "@/lib/auth/provider";
import appCss from "../styles.css?url";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Bid & Risk Assistant" },
      { name: "theme-color", content: "#1c1915" },
    ],
    links: [
      { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
      { rel: "stylesheet", href: appCss },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap",
      },
    ],
  }),
  component: () => (
    <html lang="en" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body>
        <AuthProvider>
          <Outlet />
        </AuthProvider>
        <Scripts />
      </body>
    </html>
  ),
});

````

## `frontend_demo/src/routes/index.tsx`
````tsx
import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  DEFAULT_RATES,
  ITEMS,
  REVEAL_BID,
  SAMPLE_NAME,
  crewLabel,
  estimateTotal,
  euro,
  findings,
  lineTotal,
  naturalOzCompare,
  num,
  unitPrice,
  type LineFix,
  type Rates,
} from "@/lib/boq";
import { sharpenRfi } from "@/lib/draft-rfi";

export const Route = createFileRoute("/")({ component: Home });

const KIND: Record<string, string> = {
  outlier: "Speculative price",
  vague: "Vague scope",
  qty: "Quantity clash",
  gap: "Provisional",
};

function Home() {
  const [rates, setRates] = useState<Rates>(DEFAULT_RATES);
  const [fixes, setFixes] = useState<Record<string, LineFix>>({});
  const [letters, setLetters] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>("01.04.0080");
  const [revealed, setRevealed] = useState(true);
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStatus, setAnalysisStatus] = useState(
    "Bereit zur Bereichsanalyse",
  );
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const sortedItems = useMemo(
    () => [...ITEMS].sort((a, b) => naturalOzCompare(a.oz, b.oz)),
    [],
  );

  const total = useMemo(() => estimateTotal(ITEMS, rates, fixes), [rates, fixes]);
  const rows = useMemo(() => findings(ITEMS, rates, fixes), [rates, fixes]);
  const delta = total - REVEAL_BID;
  const pct = (delta / REVEAL_BID) * 100;

  function setRate<K extends keyof Rates>(key: K, value: number) {
    setRates((r) => ({ ...r, [key]: value }));
  }

  function patch(oz: string, qty: number, tactic: number) {
    setFixes((f) => ({ ...f, [oz]: { qty, tactic } }));
  }

  async function runBatchDemo() {
    setAnalysisRunning(true);
    setAnalysisError(null);
    setAnalysisProgress(0);
    const batchSize = 20;
    const batchCount = Math.ceil(sortedItems.length / batchSize);
    try {
      for (let batchIndex = 0; batchIndex < batchCount; batchIndex += 1) {
        const from = batchIndex * batchSize + 1;
        const to = Math.min(sortedItems.length, (batchIndex + 1) * batchSize);
        const firstOz = sortedItems[batchIndex * batchSize]?.oz ?? "";
        const section = firstOz.split(".")[0] || "01";
        setAnalysisStatus(
          `Analysiere Bereich ${section} – Positionen ${from}–${to} von ${sortedItems.length}…`,
        );
        await new Promise((resolve) => window.setTimeout(resolve, 220));
        setAnalysisProgress(Math.round(((batchIndex + 1) / batchCount) * 100));
      }
      setAnalysisStatus("Bereichsanalyse abgeschlossen");
    } catch {
      setAnalysisError("Netzwerkabbruch oder Timeout. Bitte die Analyse erneut starten.");
    } finally {
      setAnalysisRunning(false);
    }
  }

  function exportRfi() {
    const lines = [
      "Bieterfragen-Katalog",
      SAMPLE_NAME,
      "",
      "Nach VOB/A bitten wir um Klarstellung der folgenden Positionen vor Submission.",
      "",
    ];
    rows.forEach((f, i) => {
      const text = letters[f.item.oz] || f.item.rfi;
      if (!text) return;
      lines.push(`${i + 1}. Pos. ${f.item.oz} — ${f.item.title}`);
      lines.push(text);
      lines.push("");
    });
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "Bieterfragen-Katalog.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function sharpen(oz: string, title: string, longText: string, rationale: string, draft: string) {
    setBusy(oz);
    setAiNote(null);
    try {
      const res = await sharpenRfi({ data: { oz, title, longText, rationale, draft } });
      if (!res.ok) setAiNote(res.error);
      else setLetters((m) => ({ ...m, [oz]: res.text }));
    } catch {
      setAiNote("Could not reach the model. The drafted question stays as written.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs tracking-widest text-muted uppercase">Estimator desk</p>
          <h1 className="mt-1 text-3xl font-medium tracking-tight">Bid & Risk</h1>
          <p className="mt-2 max-w-xl text-muted">
            It reads a construction tender, finds the lines that will cost the contractor money, and drafts the clarification letter.
          </p>
        </div>
        <button
          type="button"
          onClick={exportRfi}
          className="h-11 rounded-full bg-accent px-5 text-sm font-medium text-surface"
        >
          Export Bieterfragen
        </button>
      </header>

      <section className="mb-6 rounded-xl border border-line bg-surface px-4 py-3">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-xs tracking-widest text-muted uppercase">
              KI-Batch-Fortschritt
            </p>
            <p className="mt-1 text-sm overflow-wrap-anywhere">{analysisStatus}</p>
          </div>
          <button
            type="button"
            className="shrink-0 h-9 rounded-lg border border-line px-3 text-sm"
            disabled={analysisRunning}
            onClick={runBatchDemo}
          >
            {analysisRunning ? "Analysiert…" : "Analyse starten / Retry"}
          </button>
        </div>
        <div
          className="h-2 overflow-hidden rounded-full bg-line"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={analysisProgress}
        >
          <div
            className="h-full bg-accent transition-[width]"
            style={{ width: `${analysisProgress}%` }}
          />
        </div>
        {analysisError && (
          <p className="mt-2 rounded-lg bg-accent-soft px-3 py-2 text-sm text-warn overflow-wrap-anywhere">
            {analysisError}
          </p>
        )}
      </section>

      <section className="mb-6 grid gap-3 sm:grid-cols-3">
        <Kpi label="Our estimate" value={euro(total)} hint="Scaled from the worked slice to the 248-item twin" />
        <Kpi
          label="Submitted bid"
          value={revealed ? euro(REVEAL_BID) : "—"}
          hint="StBALV23040 · same bill"
        />
        <Kpi
          label="Gap"
          value={revealed ? `${pct >= 0 ? "+" : ""}${num(pct, 1)} %` : "—"}
          hint={revealed ? euro(delta) : "Reveal to compare"}
        />
      </section>

      <section className="mb-6 grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-xl border border-line bg-surface p-4">
          <p className="mb-3 font-mono text-xs tracking-widest text-muted uppercase">Crew & plant</p>
          <Slider label="Earthworks €/h" min={32} max={78} step={1} value={rates.earth} onChange={(n) => setRate("earth", n)} />
          <Slider label="Pipe crew €/h" min={32} max={78} step={1} value={rates.pipe} onChange={(n) => setRate("pipe", n)} />
          <Slider label="Paving €/h" min={32} max={78} step={1} value={rates.pave} onChange={(n) => setRate("pave", n)} />
          <Slider label="Fitter €/h" min={32} max={86} step={1} value={rates.fitter} onChange={(n) => setRate("fitter", n)} />
          <Slider label="Excavator €/h" min={55} max={160} step={1} value={rates.machine} onChange={(n) => setRate("machine", n)} />
          <Slider label="Material index" min={0.8} max={1.4} step={0.05} value={rates.material} onChange={(n) => setRate("material", n)} />
          <Slider label="AGK %" min={6} max={22} step={1} value={rates.agk} onChange={(n) => setRate("agk", n)} />
          <Slider label="Wagnis & Gewinn %" min={2} max={16} step={1} value={rates.wg} onChange={(n) => setRate("wg", n)} />
          <button
            type="button"
            className="mt-1 h-10 w-full rounded-lg border border-line text-sm"
            onClick={() => setRevealed((v) => !v)}
          >
            {revealed ? "Hide real bid" : "Reveal real bid"}
          </button>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            A pipe layer is not an excavator operator, and the machine is not the wage. Move only the crew that does the work.
          </p>
        </aside>

        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <div className="flex items-baseline justify-between border-b border-line px-4 py-3">
            <h2 className="text-sm font-medium">Findings by euro leverage</h2>
            <span className="font-mono text-xs text-muted">{rows.length} flagged</span>
          </div>
          <ul>
            {rows.map((f) => {
              const isOpen = open === f.item.oz;
              return (
                <li key={f.item.oz} className="border-b border-line last:border-b-0">
                  <button
                    type="button"
                    className="flex w-full items-start gap-3 px-4 py-3 text-left"
                    onClick={() => setOpen(isOpen ? null : f.item.oz)}
                  >
                    <span className="mt-0.5 shrink-0 rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent">
                      {KIND[f.item.kind ?? "gap"]}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">
                        {f.item.oz} · {f.item.title}
                      </span>
                      <span className="block text-sm text-muted overflow-wrap-anywhere">
                        {f.item.rationale}
                      </span>
                    </span>
                    <span className="shrink-0 text-right font-mono text-sm">
                      {f.source === "benchmark" ? euro(f.total) : "kein Vergleichswert"}
                    </span>
                  </button>
                  {isOpen && (
                    <div className="space-y-2 px-4 pb-4 text-sm">
                      <p className="text-muted overflow-wrap-anywhere">{f.item.longText}</p>
                      <p className="text-muted">{crewLabel(f.item.oz)}</p>
                      {f.item.preambles && f.item.preambles.length > 0 && (
                        <TextAccordion
                          title="Vorbemerkungen"
                          items={f.item.preambles}
                        />
                      )}
                      {f.item.remarks && f.item.remarks.length > 0 && (
                        <TextAccordion
                          title="Bereichs-Remarks"
                          items={f.item.remarks}
                        />
                      )}
                      <div className="flex flex-wrap items-end gap-3">
                        <label className="text-xs text-muted">
                          Qty used
                          <input
                            className="mt-1 block h-10 w-28 rounded-lg border border-line bg-bg px-2 font-mono text-sm text-ink"
                            type="number"
                            min={0}
                            value={fixes[f.item.oz]?.qty ?? f.item.qty}
                            onChange={(e) =>
                              patch(f.item.oz, Number(e.target.value), fixes[f.item.oz]?.tactic ?? 1)
                            }
                          />
                        </label>
                        <label className="text-xs text-muted">
                          Tactic
                          <select
                            className="mt-1 block h-10 rounded-lg border border-line bg-bg px-2 text-sm text-ink"
                            value={fixes[f.item.oz]?.tactic ?? 1}
                            onChange={(e) =>
                              patch(f.item.oz, fixes[f.item.oz]?.qty ?? f.item.qty, Number(e.target.value))
                            }
                          >
                            <option value={0.7}>Low — may not be called</option>
                            <option value={1}>As calculated</option>
                            <option value={1.25}>High — quantity will grow</option>
                          </select>
                        </label>
                      </div>
                      <p>
                        Billed {num(f.item.qty, 0)} {f.item.unit}
                        {f.item.benchmark != null ? ` · observed ${euro(f.item.benchmark)}` : " · kein Vergleichswert"}
                        {" · "}now {euro(f.ep)}/{f.item.unit}
                      </p>
                      <p className="rounded-lg bg-bg px-3 py-2 text-ink">{letters[f.item.oz] || f.item.rfi}</p>
                      {f.item.rfi && (
                        <button
                          type="button"
                          className="h-10 rounded-lg border border-line px-3 text-sm"
                          disabled={busy === f.item.oz}
                          onClick={() =>
                            sharpen(
                              f.item.oz,
                              f.item.title,
                              f.item.longText,
                              f.item.rationale,
                              letters[f.item.oz] || f.item.rfi,
                            )
                          }
                        >
                          {busy === f.item.oz ? "Writing…" : "Sharpen this question"}
                        </button>
                      )}
                      {aiNote && <p className="text-xs text-warn">{aiNote}</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      <section className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line font-mono text-xs tracking-wide text-muted uppercase">
            <tr>
              <th className="px-4 py-2 font-medium">OZ</th>
              <th className="px-4 py-2 font-medium">Position</th>
              <th className="px-4 py-2 font-medium">Qty</th>
              <th className="px-4 py-2 font-medium">EP</th>
              <th className="px-4 py-2 font-medium">Source</th>
              <th className="px-4 py-2 text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {sortedItems.map((it) => {
              const fix = fixes[it.oz];
              const priced = unitPrice(it, rates, fix?.tactic ?? 1);
              return (
                <tr key={it.oz} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-2 font-mono text-xs">{it.oz}</td>
                  <td className="px-4 py-2">{it.title}</td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {num(fix?.qty ?? it.qty, 0)} {it.unit}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">{euro(priced.ep)}</td>
                  <td className="px-4 py-2 text-muted">
                    {priced.source === "benchmark" ? "observed" : "built-up"} · {crewLabel(it.oz)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-xs">{euro(lineTotal(it, rates, fix))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </main>
  );
}

function TextAccordion({ title, items }: { title: string; items: string[] }) {
  return (
    <details className="rounded-lg border border-line bg-bg px-3 py-2">
      <summary className="cursor-pointer text-sm font-medium">{title}</summary>
      <div className="mt-2 space-y-2">
        {items.map((text, index) => (
          <p
            key={`${title}-${index}`}
            className="text-xs leading-relaxed text-muted overflow-wrap-anywhere"
          >
            {text}
          </p>
        ))}
      </div>
    </details>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3">
      <p className="font-mono text-xs tracking-widest text-muted uppercase">{label}</p>
      <p className="mt-1 text-2xl font-medium tracking-tight">{value}</p>
      <p className="mt-1 text-xs text-muted overflow-wrap-anywhere">{hint}</p>
    </div>
  );
}

function Slider({
  label,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="mb-3 block text-sm">
      <span className="mb-1 flex justify-between">
        <span>{label}</span>
        <span className="font-mono">{Number(value.toFixed(2))}</span>
      </span>
      <input
        className="w-full accent-accent"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

````

## `frontend_demo/src/routeTree.gen.ts`
````ts
/* eslint-disable */

// @ts-nocheck

// noinspection JSUnusedGlobalSymbols

// This file was automatically generated by TanStack Router.
// You should NOT make any changes in this file as it will be overwritten.
// Additionally, you should also exclude this file from your linter and/or formatter to prevent it from being checked or modified.

import { Route as rootRouteImport } from './routes/__root'
import { Route as IndexRouteImport } from './routes/index'

const IndexRoute = IndexRouteImport.update({
  id: '/',
  path: '/',
  getParentRoute: () => rootRouteImport,
} as any)

export interface FileRoutesByFullPath {
  '/': typeof IndexRoute
}
export interface FileRoutesByTo {
  '/': typeof IndexRoute
}
export interface FileRoutesById {
  __root__: typeof rootRouteImport
  '/': typeof IndexRoute
}
export interface FileRouteTypes {
  fileRoutesByFullPath: FileRoutesByFullPath
  fullPaths: '/'
  fileRoutesByTo: FileRoutesByTo
  to: '/'
  id: '__root__' | '/'
  fileRoutesById: FileRoutesById
}
export interface RootRouteChildren {
  IndexRoute: typeof IndexRoute
}

declare module '@tanstack/react-router' {
  interface FileRoutesByPath {
    '/': {
      id: '/'
      path: '/'
      fullPath: '/'
      preLoaderRoute: typeof IndexRouteImport
      parentRoute: typeof rootRouteImport
    }
  }
}

const rootRouteChildren: RootRouteChildren = {
  IndexRoute: IndexRoute,
}
export const routeTree = rootRouteImport
  ._addFileChildren(rootRouteChildren)
  ._addFileTypes<FileRouteTypes>()

import type { getRouter } from './router.tsx'
import type { createStart } from '@tanstack/react-start'
declare module '@tanstack/react-start' {
  interface Register {
    ssr: true
    router: Awaited<ReturnType<typeof getRouter>>
  }
}

````

## `frontend_demo/src/styles.css`
````css
@import "tailwindcss";

@theme {
  --color-bg: #f3efe6;
  --color-surface: #fffcf7;
  --color-ink: #1c1915;
  --color-muted: #6e675e;
  --color-line: #e3d9cc;
  --color-accent: #9a3412;
  --color-accent-soft: #f3e4d6;
  --color-warn: #92400e;
  --color-ok: #3f6212;
  --font-sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --radius: 0.75rem;
}

@layer base {
  html, body { background: var(--color-bg); color: var(--color-ink); }
  button:not(:disabled), [role="button"]:not(:disabled) { cursor: pointer; }
  body { font-family: var(--font-sans); line-height: 1.5; }
  p, span, td, th, li, details, summary {
    overflow-wrap: break-word;
    word-break: normal;
  }
  .overflow-wrap-anywhere {
    overflow-wrap: anywhere;
  }
}

````

## `frontend_demo/tsconfig.json`
````json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": [
      "ES2022",
      "DOM",
      "DOM.Iterable"
    ],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "allowJs": true,
    "checkJs": true,
    "noEmit": true,
    "types": [
      "vite/client",
      "node"
    ],
    "baseUrl": ".",
    "paths": {
      "@/*": [
        "./src/*"
      ]
    },
    "allowImportingTsExtensions": true
  },
  "include": [
    "src",
    "server"
  ]
}

````

## `frontend_demo/vercel.json`
````json
{
  "installCommand": "npm install --omit=dev --no-audit --no-fund"
}

````

## `frontend_demo/vite.config.ts`
````ts
import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { nitro } from "nitro/vite";

export default defineConfig(({ command, isPreview }) => ({
  server: {
    host: "127.0.0.1",
    port: 3000,
  },
  preview: {
    host: "127.0.0.1",
    port: 3001,
  },
  resolve: { tsconfigPaths: true },
  plugins: [
    tailwindcss(),
    tanstackStart(),
    ...(command === "build" || isPreview
      ? [nitro({ preset: "vercel" })]
      : []),
    viteReact(),
  ],
}));

````

## `ingest_benchmarks.py`
````py
import argparse
import json
import re
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List

from openpyxl import load_workbook

from models import BenchmarkItem
from parser import normalize_benchmark_unit, parse_fixed_width, parse_x83


ANONYMIZE = re.compile(r"\[(?:PERSON|ORT|FIRMA|PROJEKT|[A-Z]+)[^\]]*\]")
IGNORED_PDF_LINES = re.compile(
    r"(übertrag|summe|zusammenstellung|mehrwertsteuer|gesamtsumme)",
    re.IGNORECASE,
)
POSITION_RE = re.compile(r"^\s*(\d+(?:[._/-]\d+)*)")
GERMAN_PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)")
UNIT_RE = re.compile(
    r"(?<![A-Za-z])(?:psch|Mt|m\s*[³3]|m2|m²|m|Stk?|h|t|d)(?![A-Za-z])",
    re.IGNORECASE,
)


def decode_bytes(raw: bytes) -> str:
    for encoding in ("cp850", "cp1252", "utf-8-sig"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def german_price(value: str) -> float:
    if not value:
        return 0.0
    value = value.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return 0.0


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].split(":")[-1]


def parse_fixed_benchmark(path: Path, folder: Path) -> List[BenchmarkItem]:
    text = decode_bytes(path.read_bytes())
    prices = {}
    current_oz = ""
    section = ""
    has_full_text = False

    for line in text.splitlines():
        content = line[:74]
        if len(content) < 2:
            continue
        record = content[:2]
        if record == "11":
            no = content[2:11].strip()
            title = content[11:74].strip()
            section = " ".join(part for part in (no, title) if part).strip()
        elif record == "12":
            subsection = content[2:74].strip()
            section = " > ".join(part for part in (section, subsection) if part)
        elif record == "21":
            current_oz = content[2:11].strip()
        elif record == "23" and current_oz:
            try:
                prices[current_oz] = int(content[12:22].strip()) / 100.0
            except (TypeError, ValueError):
                pass
        elif record in ("25", "26") and content[2:74].strip():
            has_full_text = True

    items = parse_fixed_width(path)
    if not items and any(prices.values()):
        d83_candidates = list(folder.glob("*.d83")) + list(folder.glob("*.D83"))
        for d83 in d83_candidates:
            items = parse_fixed_width(d83)
            if items:
                break

    if not has_full_text and not items:
        print(f"Warning: {path.name} contains price-only 23 records; skipped.")
        return []

    result = []
    for item in items:
        price = prices.get(item.oz)
        if price is None or price <= 0:
            continue
        if not item.short_text.strip() and not item.long_text.strip():
            continue
        result.append(BenchmarkItem(
            oz=item.oz, section=item.hierarchy or section,
            short_text=item.short_text, long_text=item.long_text,
            unit=item.unit, quantity=item.qty, unit_price=price,
            source_file=path.name, price_type="contract",
        ))
    return result


def parse_x_benchmark(path: Path) -> List[BenchmarkItem]:
    items = parse_x83(path)
    tree = ET.parse(str(path))
    prices = {}
    for elem in tree.getroot().iter():
        if local_name(elem.tag).lower() not in ("boqitem", "boqline", "boqbodyitem", "item"):
            continue
        oz = ""
        price = 0.0
        for child in elem.iter():
            name = local_name(child.tag).lower()
            value = " ".join(child.itertext()).strip()
            if name in ("rnopart", "boqno", "id") and not oz:
                oz = value
            elif name in ("up", "unitprice", "ep"):
                price = german_price(value)
        if oz:
            prices[oz] = price

    return [
        BenchmarkItem(
            oz=item.oz, section=item.hierarchy,
            short_text=item.short_text, long_text=item.long_text,
            unit=item.unit, quantity=item.qty,
            unit_price=prices.get(item.oz, 0.0),
            source_file=path.name, price_type="contract",
        )
        for item in items
        if prices.get(item.oz, 0.0) > 0 and (item.short_text or item.long_text)
    ]


def parse_excel_benchmark(path: Path) -> List[BenchmarkItem]:
    wb = load_workbook(path, read_only=True, data_only=True)
    entries = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        try:
            headers = [str(v).strip().lower() if v is not None else "" for v in next(rows)]
        except StopIteration:
            continue
        aliases = {
            "oz": ("oz", "pos", "pos-nr", "positionsnr", "ordnungszahl"),
            "section": ("section", "bereich", "abschnitt", "titel"),
            "short": ("short_text", "kurztext", "bezeichnung", "description"),
            "long": ("long_text", "langtext", "beschreibung"),
            "unit": ("unit", "einheit", "me"),
            "qty": ("quantity", "qty", "menge"),
            "price": ("unit_price", "ep", "einheitspreis", "preis"),
        }
        def col_for(names):
            return next((i for i, h in enumerate(headers) if h in names), None)
        cols = {key: col_for(names) for key, names in aliases.items()}
        if cols["oz"] is None or cols["price"] is None:
            continue
        for row in rows:
            def value(key):
                index = cols[key]
                return row[index] if index is not None and index < len(row) else None
            oz = str(value("oz") or "").strip()
            price = german_price(str(value("price") or ""))
            short = str(value("short") or "").strip()
            long = str(value("long") or "").strip()
            unit = normalize_benchmark_unit(str(value("unit") or "").strip())
            if not oz or price <= 0 or not unit or not (short or long):
                continue
            try:
                quantity = float(str(value("qty") or "1").replace(",", "."))
            except ValueError:
                quantity = 1.0
            entries.append(BenchmarkItem(
                oz=oz, section=str(value("section") or "").strip(),
                short_text=short or long[:180], long_text=long or short,
                unit=unit, quantity=quantity, unit_price=price,
                source_file=path.name,
                price_type="contract" if ".x86" in path.suffix.lower() else "offer",
            ))
    return entries


def parse_pdf_benchmark(path: Path) -> List[BenchmarkItem]:
    import pdfplumber

    entries = []
    section = ""
    pending = None
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for raw_line in text.splitlines():
                line = ANONYMIZE.sub("", raw_line).strip()
                if not line or IGNORED_PDF_LINES.search(line):
                    continue
                lower = line.lower()
                if "bereich" in lower or "abschnitt" in lower:
                    section = re.sub(r"^\W+", "", line).strip()

                oz_match = POSITION_RE.match(line)
                if oz_match:
                    if pending:
                        entries.append(pending)
                    oz = oz_match.group(1)
                    rest = line[oz_match.end():].strip()
                    pending = _pdf_row_to_entry(path, oz, rest, section)
                elif pending:
                    pending.long_text = " ".join(filter(None, (pending.long_text, line))).strip()
                    pending.short_text = pending.long_text[:180]
                    refreshed = _pdf_row_to_entry(
                        path, pending.oz, pending.long_text, section,
                        existing=pending,
                    )
                    pending = refreshed
            if pending:
                entries.append(pending)
                pending = None
    return [e for e in entries if e.unit_price > 0 and e.short_text.strip()]


def _pdf_row_to_entry(path: Path, oz: str, rest: str, section: str,
                      existing=None) -> BenchmarkItem:
    price_match = GERMAN_PRICE_RE.findall(rest)
    unit_match = UNIT_RE.search(rest)
    unit = normalize_benchmark_unit(unit_match.group(0) if unit_match else "")
    unit_price = german_price(price_match[-1]) if price_match else 0.0
    quantity = 1.0
    if unit_match:
        left = rest[:unit_match.start()]
        quantities = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)", left)
        if quantities:
            try:
                quantity = float(quantities[-1].replace(".", "").replace(",", "."))
            except ValueError:
                pass
    description = GERMAN_PRICE_RE.sub("", rest)
    if unit_match:
        description = description.replace(unit_match.group(0), "", 1)
    description = re.sub(r"\s+", " ", description).strip(" \t.-")
    if existing:
        description = existing.long_text if not description else description
    return BenchmarkItem(
        oz=oz, section=section, short_text=description[:180],
        long_text=description, unit=unit, quantity=quantity,
        unit_price=unit_price, source_file=path.name,
        price_type="contract" if "auftrag" in path.name.lower() or "contract" in path.name.lower() or "order" in path.name.lower() else "offer",
    )


def apply_outlier_filter(entries: List[BenchmarkItem]) -> None:
    by_unit = {}
    for entry in entries:
        unit = normalize_benchmark_unit(entry.unit)
        by_unit.setdefault(unit, []).append(entry.unit_price)
    medians = {
        unit: statistics.median(prices)
        for unit, prices in by_unit.items()
        if prices
    }
    dummy_units = {"h", "d", "mt", "m3", "t", "psch", "st"}
    for entry in entries:
        unit = normalize_benchmark_unit(entry.unit)
        median = medians.get(unit)
        entry.is_outlier = (
            (unit in dummy_units and entry.unit_price < 1.50)
            or (median is not None and entry.unit_price < 0.15 * median)
        )


def is_excluded(path: Path, exclude_file: Iterable[str]) -> bool:
    return any(token.lower() in path.name.lower() for token in exclude_file)


def main():
    parser = argparse.ArgumentParser(description="Ingest historical benchmark sources.")
    parser.add_argument("--input-dir", default="data/raw_benchmarks")
    parser.add_argument("--output", default="data/benchmarks.json")
    parser.add_argument("--exclude-file", action="append", default=[],
                        help="Filename substring to exclude; repeatable.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if input_dir.exists():
        for path in sorted(input_dir.rglob("*")):
            if not path.is_file() or is_excluded(path, args.exclude_file):
                continue
            suffix = path.suffix.lower()
            try:
                if suffix in (".d84", ".d86"):
                    entries.extend(parse_fixed_benchmark(path, path.parent))
                elif suffix in (".x84", ".x86"):
                    entries.extend(parse_x_benchmark(path))
                elif suffix == ".xlsx":
                    entries.extend(parse_excel_benchmark(path))
                elif suffix == ".pdf":
                    entries.extend(parse_pdf_benchmark(path))
            except Exception as exc:
                print(f"Warning: could not ingest {path.name}: {exc}")

    apply_outlier_filter(entries)
    unique = {}
    for entry in entries:
        key = (entry.oz, normalize_benchmark_unit(entry.unit),
               entry.short_text.lower(), entry.source_file)
        unique[key] = entry
    payload = [{
        "oz": e.oz, "section": e.section,
        "short_text": e.short_text, "long_text": e.long_text,
        "unit": normalize_benchmark_unit(e.unit),
        "quantity": e.quantity, "unit_price": e.unit_price,
        "source_file": e.source_file,
        "is_outlier": e.is_outlier,
        "price_type": e.price_type,
    } for e in unique.values()]
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Stored {len(payload)} benchmark entries in {output}")


if __name__ == "__main__":
    main()

````

## `models.py`
````py
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NormalizedItem:
    """Full hierarchical order number, e.g. "02.0004" or "01.01.0001"."""
    oz: str
    hierarchy: str
    short_text: str
    long_text: str
    qty: float
    unit: str
    item_type: str = "Normal"
    source_file: str = ""
    reference_unit_price: Optional[float] = None
    data_defects: List[str] = field(default_factory=list)
    xml_id: str = ""
    context_from_previous_item: str = ""
    remarks: List[str] = field(default_factory=list)
    project_metadata: List[str] = field(default_factory=list)


@dataclass
class BenchmarkItem:
    oz: str
    short_text: str
    unit: str
    unit_price: float
    section: str = ""
    long_text: str = ""
    quantity: float = 0.0
    source_file: str = ""
    is_outlier: bool = False
    price_type: str = "offer"


@dataclass
class RiskFlag:
    code: str
    severity: str
    message: str
    related_oz: List[str] = field(default_factory=list)


@dataclass
class AIItemResult:
    oz: str
    crew_type: str = "general"
    labor_hours_per_unit: float = 0.0
    machine_hours_per_unit: float = 0.0
    base_material_cost_per_unit: float = 0.0
    material_or_subcontract_cost_per_unit: float = 0.0
    errors_and_risks: List[str] = field(default_factory=list)
    suggested_tactic: str = "STANDARD"
    is_specialist_or_unclear: bool = False
    tier_low: Optional[float] = None
    tier_mid: Optional[float] = None
    tier_high: Optional[float] = None
    tier_rationale: str = ""
    client_rfi_draft: str = ""
    subcontractor_rfq_draft: str = ""
    confidence: float = 0.5
    construction_phase: str = "Allgemein"
    change_order_potential: str = "niedrig"
    rfi_question: str = ""
    material_cost_estimate: Optional[float] = None
    risk_flags: List[RiskFlag] = field(default_factory=list)
    needs_llm: bool = False
    auto_accepted: bool = False


@dataclass
class PricedItem:
    oz: str
    hierarchy: str
    short_text: str
    long_text: str
    qty: float
    unit: str
    item_type: str
    crew_type: str
    labor_hours_per_unit: float
    machine_hours_per_unit: float
    base_material_cost_per_unit: float
    labor_hours: float
    machine_hours: float
    ekt: float
    ep_per_unit: float
    item_total: float
    tactic: str
    risks: List[str]
    needs_review: bool
    confirmed: bool
    selected_price_tier: str = ""
    benchmark_unit_price: Optional[float] = None
    benchmark_comparison: str = ""
    client_rfi_draft: str = ""
    subcontractor_rfq_draft: str = ""
    reference_unit_price: Optional[float] = None
    confidence: float = 0.5
    construction_phase: str = "Allgemein"
    change_order_potential: str = "mittel"
    xml_id: str = ""
    material_or_subcontract_cost_per_unit: float = 0.0
    rfi_question: str = ""

````

## `parser.py`
````py
import csv
import difflib
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List

import streamlit as st

from models import BenchmarkItem, NormalizedItem


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].split(":")[-1]


def _text(node: ET.Element) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _desc_text(node: ET.Element, names: Iterable[str]) -> str:
    wanted = {n.lower() for n in names}
    vals = []
    for child in node.iter():
        if _local(child.tag).lower() in wanted:
            text = _text(child)
            if text:
                vals.append(text)
    return " ".join(dict.fromkeys(vals)).strip()


def _category_label_text(ctgy_elem: ET.Element) -> str:
    """Liest ausschließlich den Titel des aktuellen <BoQCtgy>-Knotens, ohne in <BoQBody>/<Item> abzusteigen."""
    stop_tags = {"boqbody", "itemlist", "item", "boqitem", "boqline", "boqctgy"}
    title_tags = {"lbltx", "name", "outlinetext", "outltxt", "shorttext"}
    vals: List[str] = []

    def _walk_header(node: ET.Element):
        for child in list(node):
            tag = _local(child.tag).lower()
            if tag in stop_tags:
                continue
            if tag in title_tags:
                txt = clean_text(child)
                if txt:
                    vals.append(txt)
            else:
                _walk_header(child)

    _walk_header(ctgy_elem)
    return " ".join(dict.fromkeys(vals)).strip()


def _first_attr(node: ET.Element, names=("RNoPart", "RNo", "PartNo", "BoQNo", "BoQPart")) -> str:
    wanted = {n.lower() for n in names}
    for key, value in node.attrib.items():
        if _local(key).lower() in wanted:
            val = str(value).strip()
            if val:
                return val
    return ""


def _smart_truncate(text: str, max_len: int = 240) -> str:
    cleaned = " ".join((text or "").split()).strip()
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len]
    # Bevorzugt an Satzende schneiden, sonst an letzter Wortgrenze
    sentence_end = max(cut.rfind(". "), cut.rfind("; "))
    if sentence_end >= max_len // 2:
        return cut[: sentence_end + 1].strip()
    word_end = cut.rfind(" ")
    if word_end >= max_len // 2:
        return cut[:word_end].strip() + " …"
    return cut.strip() + " …"


def _parse_gaeb_number(value: str) -> float:
    if not value:
        return 0.0
    value = value.strip().replace("\xa0", "").replace(" ", "")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_x83(path: str | Path) -> List[NormalizedItem]:
    tree = ET.parse(str(path))
    root = tree.getroot()
    items: List[NormalizedItem] = []
    project_metadata: List[str] = []

    for elem in root.iter():
        if _local(elem.tag).lower() not in ("addtext", "remark", "preamble"):
            continue
        text = clean_text(elem)
        if text:
            project_metadata.append(text)

    def direct_text(parent: ET.Element, names: Iterable[str]) -> str:
        wanted = {name.lower() for name in names}
        for child in list(parent):
            if _local(child.tag).lower() in wanted:
                return " ".join(" ".join(child.itertext()).split())
        return ""

    def direct_element(parent: ET.Element, names: Iterable[str]) -> ET.Element | None:
        wanted = {name.lower() for name in names}
        for child in list(parent):
            if _local(child.tag).lower() in wanted:
                return child
        return None

    def find_descendant(parent: ET.Element, names: Iterable[str]) -> ET.Element | None:
        wanted = {name.lower() for name in names}
        for node in parent.iter():
            if node is parent:
                continue
            if _local(node.tag).lower() in wanted:
                return node
        return None

    def extract_item_texts(item_elem: ET.Element) -> tuple[str, str]:
        desc_node = direct_element(item_elem, ("Description",))
        search_root = desc_node if desc_node is not None else item_elem

        short_node = (
            direct_element(search_root, ("OutlineText", "OutlTxt", "ShortText"))
            or find_descendant(search_root, ("OutlineText", "OutlTxt", "ShortText"))
        )
        long_node = (
            direct_element(search_root, ("CompleteText", "DetailTxt", "Text"))
            or find_descendant(search_root, ("CompleteText", "DetailTxt", "Text"))
        )

        short = clean_text(short_node) if short_node is not None else ""
        long = clean_text(long_node) if long_node is not None else ""

        # Falls <Description> weder <OutlineText> noch <DetailTxt> nutzt, aber direkten Text hat
        if not short and not long and desc_node is not None:
            full_desc = clean_text(desc_node)
            lines = [clean_text(ln) for ln in full_desc.splitlines() if clean_text(ln)]
            if lines:
                short = _smart_truncate(lines[0], max_len=240)
                long = full_desc

        if not short and long:
            first_line = next((clean_text(ln) for ln in long.splitlines() if clean_text(ln)), long)
            short = _smart_truncate(first_line, max_len=240)
        if not long and short:
            long = short

        return deduplicate_text(short), deduplicate_text(long)

    def walk(elem: ET.Element, hierarchy: List[str], category_numbers: List[str]):
        local_name = _local(elem.tag).lower()
        next_hierarchy = list(hierarchy)
        next_category_numbers = list(category_numbers)

        if local_name == "boqctgy":
            category_no = (
                direct_text(elem, ("RNoPart", "RNo", "PartNo"))
                or _first_attr(elem, ("RNoPart", "RNo", "PartNo"))
            ).strip()
            category_idx = _first_attr(elem, ("RNoIndex",))
            if category_no and category_idx and not category_no.endswith(category_idx):
                category_no = f"{category_no}{category_idx}"

            category_label = _category_label_text(elem)
            category = " ".join(part for part in (category_no, category_label) if part).strip()
            if category:
                next_hierarchy.append(category)
            if category_no:
                next_category_numbers.append(category_no)

        if local_name in {"boqitem", "boqline", "boqbodyitem", "item"}:
            item_no = (
                direct_text(elem, ("RNoPart", "RNo", "BoQNo", "BoQPart", "ItemNo"))
                or _first_attr(elem, ("RNoPart", "RNo", "BoQNo", "BoQPart", "ItemNo"))
            ).strip()
            item_idx = _first_attr(elem, ("RNoIndex",))
            if item_no and item_idx and not item_no.endswith(item_idx):
                item_no = f"{item_no}{item_idx}"

            xml_id = next(
                (
                    str(value).strip()
                    for key, value in elem.attrib.items()
                    if _local(key).lower() == "id"
                ),
                "",
            )

            prefix = ".".join(part for part in next_category_numbers if part)
            if prefix and item_no:
                if item_no.startswith(f"{prefix}."):
                    oz = item_no
                else:
                    oz = f"{prefix}.{item_no}"
            else:
                oz = item_no or prefix or f"{len(items) + 1:04d}"

            short, long = extract_item_texts(elem)

            qty_node = direct_element(elem, ("Qty",))
            quantity_node = direct_element(elem, ("Quantity",))
            qty_text = ""
            if qty_node is not None:
                nested_quantity = direct_element(qty_node, ("Quantity",))
                qty_text = (
                    " ".join(" ".join(nested_quantity.itertext()).split())
                    if nested_quantity is not None
                    else " ".join(" ".join(qty_node.itertext()).split())
                )
            elif quantity_node is not None:
                qty_text = " ".join(" ".join(quantity_node.itertext()).split())
            unit_node = direct_element(elem, ("QU", "Unit"))
            unit = " ".join(" ".join(unit_node.itertext()).split()) if unit_node is not None else ""
            qty = _parse_gaeb_number(qty_text)

            # GAEB Item-Typ (Bedarfs-/Eventualpositionen sauber erkennen)
            item_type = "Normal"
            for attr_key, attr_val in elem.attrib.items():
                ak = _local(attr_key).lower()
                av = str(attr_val).lower()
                if ak in ("type", "itemtype", "provis", "provisional"):
                    if "provis" in av or "bedarf" in av or av in ("true", "1", "b"):
                        item_type = "Bedarf"
                    elif "alt" in av or "eventual" in av or av == "e":
                        item_type = "Eventual"
            if direct_element(elem, ("Provis", "Provisional")) is not None:
                item_type = "Bedarf"

            all_text = f"{short} {long}".lower()
            if item_type == "Normal":
                if "eventual" in all_text or "alternativposition" in all_text:
                    item_type = "Eventual"
                elif "bedarfsposition" in all_text or "bedarfspos" in all_text:
                    item_type = "Bedarf"

            if not oz and not short and not long:
                return

            reference_price = None
            for descendant in elem.iter():
                if _local(descendant.tag).lower() in ("up", "unitprice", "ep"):
                    reference_price = _parse_gaeb_number(_text(descendant))
                    break

            remark_nodes = [
                " ".join(" ".join(descendant.itertext()).split())
                for descendant in elem.iter()
                if _local(descendant.tag).lower() in ("remark", "remarks")
                and clean_text(descendant)
            ]
            items.append(
                NormalizedItem(
                    oz,
                    " > ".join(dict.fromkeys(next_hierarchy)),
                    short,
                    long,
                    qty,
                    unit,
                    item_type,
                    Path(path).name,
                    reference_unit_price=reference_price,
                    xml_id=xml_id,
                    remarks=list(dict.fromkeys(remark_nodes)),
                    project_metadata=list(dict.fromkeys(project_metadata)),
                )
            )
            return

        for child in elem:
            walk(child, next_hierarchy, next_category_numbers)

    walk(root, [], [])

    previous_by_section = {}
    for item in items:
        section_key = item.hierarchy
        source = f"{item.short_text} {item.long_text}".strip().lower()
        if source.startswith("wie vor") or "\nwie vor" in source:
            previous = previous_by_section.get(section_key)
            if previous is not None:
                core = clean_text(previous.short_text or previous.long_text)
                if core:
                    reference = f"[Bezug auf {previous.oz}: {core}] "
                    item.context_from_previous_item = (
                        f"{previous.oz}: {clean_text(previous.short_text)} "
                        f"{clean_text(previous.long_text)}"
                    ).strip()
                    item.long_text = deduplicate_text(reference + item.long_text)
                    item.short_text = deduplicate_text(item.short_text)
        previous_by_section[section_key] = item

    return finalize_defects(items)


def _ancestor_hierarchy(elem: ET.Element) -> str:
    text = _desc_text(elem, ("OutlTxt", "BoQText", "Name"))
    return _smart_truncate(text, max_len=250) if text else ""


def parse_fixed_width(path: str | Path) -> List[NormalizedItem]:
    raw = Path(path).read_bytes()
    text = ""
    for encoding in ("cp850", "cp1252", "utf-8-sig"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    items: List[NormalizedItem] = []
    hierarchy_parts: List[str] = []
    section_title = ""
    subsection_title = ""
    hierarchy_numbers: List[str] = []
    current = None

    for line in text.splitlines():
        content = line[:74]
        if len(content) < 2:
            continue
        record = content[:2]

        if record in ("00", "01", "02", "03", "08"):
            continue

        if record == "11":
            section_no = content[2:11].strip()
            title_text = content[11:74].strip()
            hierarchy_numbers = [section_no] if section_no else []
            if title_text:
                section_title = " ".join(part for part in (section_no, title_text) if part).strip()
            subsection_title = ""
            hierarchy_parts = [section_title] if section_title else []
            continue

        if record == "12":
            subsection_no = content[2:11].strip()
            if subsection_no.isdigit():
                hierarchy_numbers = hierarchy_numbers[:1] + [subsection_no]
            text_part = content[2:74].strip()
            if text_part:
                subsection_title = text_part
                hierarchy_parts = (
                    [section_title, subsection_title] if section_title else [subsection_title]
                )
            continue

        if record == "21":
            if current is not None:
                items.append(current)

            item_no = content[2:11].strip()
            oz_parts = hierarchy_numbers + ([item_no] if item_no else [])
            cleaned_parts = []
            for part in oz_parts:
                cleaned = re.sub(r"\s+", "", part).strip(".")
                if cleaned and cleaned not in cleaned_parts:
                    cleaned_parts.append(cleaned)
            if cleaned_parts:
                top = cleaned_parts[0]
                item_clean = cleaned_parts[-1]
                if len(cleaned_parts) > 1 and item_clean.startswith(top):
                    item_clean = item_clean[len(top) :]
                item_clean = re.sub(r"\D", "", item_clean)
                if item_clean:
                    item_clean = item_clean.zfill(4)
                    cleaned_parts = cleaned_parts[: len(hierarchy_numbers)]
                    if cleaned_parts:
                        cleaned_parts.append(item_clean)
                    else:
                        cleaned_parts = [item_clean]
            oz = ".".join(cleaned_parts) or item_no
            type_field = content[11:23]
            qty_raw = content[23:34].strip()
            unit = content[34:38].strip()
            try:
                qty = int(re.sub(r"\D", "", qty_raw)) / 1000.0 if qty_raw else 0.0
            except ValueError:
                qty = 0.0

            item_type = "Normal"
            if "B" in type_field.upper():
                item_type = "Bedarf"
            elif "E" in type_field.upper():
                item_type = "Eventual"

            if not oz:
                oz = str(len(items) + 1)
            current = NormalizedItem(
                oz=oz,
                hierarchy=" / ".join(dict.fromkeys(hierarchy_parts)),
                short_text="",
                long_text="",
                qty=qty,
                unit=unit,
                item_type=item_type,
                source_file=Path(path).name,
            )
            continue

        if record == "23" and current is not None:
            try:
                unit_price = int(content[12:22].strip()) / 100.0
                if unit_price > 0:
                    current.reference_unit_price = unit_price
            except (TypeError, ValueError):
                pass
            continue

        if record == "25" and current is not None:
            text_part = content[2:74].strip()
            if text_part:
                current.short_text = (current.short_text + " " + text_part).strip()
            continue

        if record == "26" and current is not None:
            text_part = content[2:74].strip()
            if text_part:
                current.long_text = (
                    (current.long_text + "\n" if current.long_text else "") + text_part
                )
            continue

    if current is not None:
        items.append(current)

    for item in items:
        if not item.short_text and item.long_text:
            item.short_text = _smart_truncate(item.long_text.split("\n", 1)[0], max_len=240)
        item.short_text = deduplicate_text(clean_text(item.short_text))
        item.long_text = deduplicate_text(clean_text(item.long_text))

    previous_by_section = {}
    for item in items:
        source = f"{item.short_text} {item.long_text}".strip().lower()
        if source.startswith("wie vor") or "\nwie vor" in source:
            previous = previous_by_section.get(item.hierarchy)
            if previous is not None:
                core = clean_text(previous.short_text or previous.long_text)
                item.long_text = deduplicate_text(
                    f"[Bezug auf {previous.oz}: {core}] {item.long_text}"
                )
        previous_by_section[item.hierarchy] = item
    return items


ANONYMIZE_RE = re.compile(r"\[(?:PERSON|ORT|FIRMA|PROJEKT|[A-Z]+)[^\]]*\]")
IGNORED_PDF_RE = re.compile(
    r"(übertrag|summe|zusammenstellung|mehrwertsteuer|gesamtsumme)",
    re.IGNORECASE,
)
PDF_UNIT_RE = re.compile(
    r"(?<![A-Za-z])(psch|Mt|m3|m²|m2|m|Stk?|h|t|d)(?![A-Za-z])",
    re.IGNORECASE,
)
PDF_PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)")
PDF_OZ_RE = re.compile(r"^\s*(\d+(?:[._/-]\d+)*)")


def clean_text(text: str) -> str:
    if text is None:
        return ""
    if isinstance(text, ET.Element):
        paragraphs = []
        for node in text.iter():
            node_name = _local(node.tag).lower()
            if node_name in ("p", "div", "li", "br"):
                body = " ".join(" ".join(node.itertext()).split())
                if body:
                    paragraphs.append(body)
        if paragraphs:
            text = "\n".join(dict.fromkeys(paragraphs))
        else:
            text = " ".join(" ".join(text.itertext()).split())
    else:
        text = str(text)
        try:
            fragment = ET.fromstring(f"<root>{text}</root>")
        except ET.ParseError:
            fragment = None
        if fragment is not None:
            paragraphs = []
            for node in fragment.iter():
                node_name = _local(node.tag).lower()
                if node_name in ("p", "div", "li", "br"):
                    body = " ".join(" ".join(node.itertext()).split())
                    if body:
                        paragraphs.append(body)
            text = (
                "\n".join(dict.fromkeys(paragraphs))
                if paragraphs
                else " ".join(" ".join(fragment.itertext()).split())
            )

    # Neutraler Platzhalter '[...]', damit zusammengesetzte Fachbegriffe ('Kies-[...]-Gemisch') lesbar bleiben
    value = re.sub(
        r"\[(?:PERSON|FIRMA|TELEFON|ORT|PROJEKT|[A-Z]+)_[^]]*\]",
        "[...]",
        str(text),
    )
    value = re.sub(r"\s+", " ", value).strip()
    return deduplicate_text(value)


def deduplicate_text(text: str) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    half = len(normalized) // 2
    if half > 20 and normalized[:half].strip() == normalized[half:].strip():
        return normalized[:half].strip()
    parts = []
    seen = set()
    for sentence in re.split(r"(?<=[.!?])\s+", normalized):
        key = re.sub(r"\W+", "", sentence.lower())
        if key and key not in seen:
            seen.add(key)
            parts.append(sentence)
    return " ".join(parts).strip()


def extract_project_quantities(path: str | Path) -> dict:
    try:
        tree = ET.parse(str(path))
    except Exception:
        return {"pipeline_m": None, "diameters": [], "structure_count": None}
    texts = []
    for elem in tree.getroot().iter():
        if _local(elem.tag).lower() in ("addtext", "remark", "preamble", "lbltx"):
            text = clean_text(_text(elem))
            if text:
                texts.append(text)
    combined = " ".join(texts).lower()

    pipeline_m = None
    length_patterns = (
        r"(?:gesamtlänge|leitungslänge|rohrleitungslänge|gesamte leitung)[^\d]{0,20}(\d+(?:[.,]\d+)?)\s*m",
        r"(?:pipeline|rohrleitung)[^\d]{0,30}(\d+(?:[.,]\d+)?)\s*m",
        r"(\d+(?:[.,]\d+)?)\s*m[^\n]{0,25}(?:rohrleitung|leitung)",
    )
    for pattern in length_patterns:
        match = re.search(pattern, combined)
        if match:
            pipeline_m = float(match.group(1).replace(",", "."))
            break

    diameters = sorted(
        set(int(value) for value in re.findall(r"\bdn\s*([0-9]{3,4})\b", combined))
    )
    german_numbers = {
        "ein": 1,
        "eins": 1,
        "einen": 1,
        "zwei": 2,
        "drei": 3,
        "vier": 4,
        "fünf": 5,
    }
    structure_count = None
    structure_match = re.search(
        r"(ein(?:en|e)?|eins|zwei|drei|vier|fünf|\d+)\s+"
        r"(?:tangential[\s-]*schächte?|schächte?|einlaufbauwerke?|schächte/einlaufbauwerke?)",
        combined,
    )
    if structure_match:
        token = structure_match.group(1).lower()
        structure_count = int(token) if token.isdigit() else german_numbers.get(token)
    return {
        "pipeline_m": pipeline_m,
        "diameters": diameters,
        "structure_count": structure_count,
    }


def extract_project_metadata(path: str | Path) -> List[str]:
    try:
        tree = ET.parse(str(path))
    except Exception:
        return []
    risks = []
    traps = (
        ("beweissicherung", "Beweissicherung ist als gesonderter Leistungsumfang zu prüfen"),
        ("grundstückseigentümer", "Grundstückseigentümer-Freigaben/Abnahmen sind abzuklären"),
        ("abnahme", "Abnahme durch Dritte oder Grundeigentümer ist vertraglich abzugrenzen"),
        ("sigeko", "SiGeKo-Kosten dürfen nicht ungeprüft auf Nachunternehmer übertragen werden"),
        ("nachunternehmer", "Nachunternehmer-Zusatzkosten und Schnittstellenverantwortung prüfen"),
        ("einzurechnen", "Unklare Kostentransferpflicht: Leistung soll möglicherweise uneingeschränkt eingerechnet werden"),
        ("eigentümer", "Eigentümer-/Grundstücksfreigaben und Abnahmeschnittstellen sind abzuklären"),
        ("bauseits", "Bauseitige Schnittstellenverantwortung und Übergabe sind abzugrenzen"),
    )
    for elem in tree.getroot().iter():
        if _local(elem.tag).lower() not in ("addtext", "remark", "preamble"):
            continue
        text = clean_text(_text(elem))
        if not text:
            continue
        lower = text.lower()
        is_hourly_preamble = (
            "vorbemerkung arbeitskräfte" in lower
            or "vorbemerkung geräte" in lower
            or "vorbemerkung fahrzeuge" in lower
        )
        if is_hourly_preamble and not any(
            trap in lower
            for trap in (
                "beweissicherung",
                "abnahme",
                "sigeko",
                "bauseits",
                "einzurechnen",
                "eigentümer",
            )
        ):
            continue
        matched = [risk for keyword, risk in traps if keyword in lower]
        if matched:
            risks.extend(matched)
        elif len(text) >= 20:
            risks.append(_smart_truncate(text, max_len=500))
    return list(dict.fromkeys(risks))


def header_index(headers):
    groups = {
        "oz": ("oz", "pos", "pos.", "pos-nr", "posnr", "positionsnr", "ordnungszahl", "ordnungs-nr"),
        "short": ("kurztext", "short_text", "bezeichnung", "position", "description", "leistung"),
        "long": ("langtext", "long_text", "beschreibung", "text", "leistungsbeschreibung"),
        "qty": ("menge", "qty", "quantity", "quantität", "quantitaet"),
        "unit": ("einheit", "unit", "me", "einheiten"),
        "price": ("ep", "ep netto", "einheitspreis", "einheitspreis netto", "unit_price", "preis"),
        "section": ("bereich", "abschnitt", "section", "titel", "los"),
    }
    normalized_headers = []
    for value in headers:
        header = clean_text(str(value or "")).lower().strip()
        header = re.sub(r"[\.\-_]+", "-", header)
        header = re.sub(r"\s+", " ", header).strip(" -")
        normalized_headers.append(header)
    result = {}
    for key, names in groups.items():
        result[key] = next(
            (i for i, header in enumerate(normalized_headers) if header in names),
            None,
        )
    return result


def spreadsheet_rows(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = path.read_bytes()
        text = None
        for encoding in ("cp850", "cp1252", "utf-8-sig"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        lines = text.splitlines() if text is not None else raw.decode("utf-8", "replace").splitlines()
        sample = "\n".join(lines[:20])
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t") if sample else csv.excel
        yield from csv.reader(lines, dialect)
        return

    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            yield row


def parse_table(path: str | Path) -> List[NormalizedItem]:
    path = Path(path)
    items = []
    header = None
    indices = None
    for row in spreadsheet_rows(path):
        if not row or not any(v not in (None, "") for v in row):
            continue
        if header is None:
            candidate = header_index(row)
            if candidate["oz"] is not None and candidate["qty"] is not None:
                header = row
                indices = candidate
                continue
            continue

        def get(key):
            index = indices[key]
            return row[index] if index is not None and index < len(row) else None

        oz = clean_text(str(get("oz") or "").strip())
        short = clean_text(str(get("short") or "").strip())
        long = clean_text(str(get("long") or "").strip())
        if not oz and not short:
            continue
        qty = _parse_gaeb_number(str(get("qty") or "0"))
        unit = clean_text(str(get("unit") or "").strip())
        section = clean_text(str(get("section") or "").strip())
        price_text = str(get("price") or "").strip()
        reference = _parse_gaeb_number(price_text) if price_text else None
        if not oz:
            oz = str(len(items) + 1)
        items.append(
            NormalizedItem(
                oz=oz,
                hierarchy=section,
                short_text=short or _smart_truncate(long, max_len=240),
                long_text=long or short,
                qty=qty,
                unit=unit,
                source_file=path.name,
                reference_unit_price=reference,
            )
        )
    return items


def parse_spreadsheet(path: str | Path) -> List[NormalizedItem]:
    return finalize_defects(parse_table(path))


def parse_csv(path: str | Path) -> List[NormalizedItem]:
    return finalize_defects(parse_table(path))


def parse_excel_boq(path: str | Path) -> List[NormalizedItem]:
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        return parse_spreadsheet(path)
    if suffix == ".csv":
        return parse_csv(path)
    raise ValueError(f"Unsupported tabular BoQ format: {suffix}")


def parse_pdf(path: str | Path) -> List[NormalizedItem]:
    import pdfplumber

    path = Path(path)
    items = []
    section = ""
    pending = None
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for raw_line in text.splitlines():
                line = clean_text(raw_line)
                if not line or IGNORED_PDF_RE.search(line):
                    continue
                if re.search(r"\b(seite|blatt|leistungsverzeichnis|stand vom|projekt-nr)\b", line.lower()):
                    continue
                lower = line.lower()
                if "bereich" in lower or "abschnitt" in lower:
                    section = line
                    continue

                oz_match = PDF_OZ_RE.match(line)
                if not oz_match:
                    if pending:
                        pending.long_text = " ".join((pending.long_text, line)).strip()
                        pending.short_text = _smart_truncate(pending.long_text, max_len=240)
                        price_match = PDF_PRICE_RE.findall(line)
                        unit_match = PDF_UNIT_RE.search(line)
                        if unit_match:
                            pending.unit = clean_text(unit_match.group(0))
                        if price_match:
                            pending.reference_unit_price = _parse_gaeb_number(price_match[-1])
                        if unit_match:
                            left = line[: unit_match.start()]
                            quantities = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)", left)
                            if quantities:
                                try:
                                    pending.qty = float(
                                        quantities[-1].replace(".", "").replace(",", ".")
                                    )
                                except ValueError:
                                    pass
                    continue

                if pending:
                    items.append(pending)
                oz = oz_match.group(1)
                rest = line[oz_match.end() :].strip()
                price_match = PDF_PRICE_RE.findall(rest)
                unit_match = PDF_UNIT_RE.search(rest)
                unit = clean_text(unit_match.group(0) if unit_match else "")
                qty = 1.0
                if unit_match:
                    left = rest[: unit_match.start()]
                    quantities = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)", left)
                    if quantities:
                        try:
                            qty = float(quantities[-1].replace(".", "").replace(",", "."))
                        except ValueError:
                            pass
                description = PDF_PRICE_RE.sub("", rest)
                if unit_match:
                    description = description.replace(unit_match.group(0), "", 1)
                description = clean_text(description)
                reference = _parse_gaeb_number(price_match[-1]) if price_match else None
                pending = NormalizedItem(
                    oz=oz,
                    hierarchy=section,
                    short_text=_smart_truncate(description, max_len=240),
                    long_text=description,
                    qty=qty,
                    unit=unit,
                    source_file=path.name,
                    reference_unit_price=reference,
                )
        if pending:
            items.append(pending)
    return finalize_defects(items)


def finalize_defects(items: List[NormalizedItem]) -> List[NormalizedItem]:
    seen = {}
    for item in items:
        defects = []
        if item.qty <= 0:
            defects.append("Missing or zero quantity")
        if not item.unit.strip():
            defects.append("Missing unit")
        item.data_defects = defects
        key = (item.hierarchy, item.oz)
        if key in seen:
            seen[key].append(item)
        else:
            seen[key] = [item]
    for duplicates in seen.values():
        if len(duplicates) > 1:
            for item in duplicates:
                item.data_defects.append("Duplicate OZ within same section")
    return items


def parse_pdf_boq(path: str | Path) -> List[NormalizedItem]:
    return finalize_defects(parse_pdf(path))


def parse_boq(path: str | Path) -> List[NormalizedItem]:
    suffix = Path(path).suffix.lower()
    if suffix in (".x83", ".x84"):
        return finalize_defects(parse_x83(path))
    if suffix in (".d83", ".d84", ".d86"):
        return finalize_defects(parse_fixed_width(path))
    if suffix == ".xlsx":
        return parse_excel_boq(path)
    if suffix == ".csv":
        return parse_excel_boq(path)
    if suffix == ".pdf":
        return parse_pdf_boq(path)
    raise ValueError(f"Unsupported tender format: {suffix}")


def normalize_benchmark_unit(unit: str) -> str:
    value = unicodedata.normalize("NFKC", (unit or "").strip()).lower()
    value = value.replace("²", "2").replace("³", "3").replace(".", "").strip()
    aliases = {
        "stück": "stk",
        "stueck": "stk",
        "st": "stk",
        "stk": "stk",
        "qm": "m2",
        "m2": "m2",
        "m^2": "m2",
        "cbm": "m3",
        "m3": "m3",
        "m^3": "m3",
        "lfm": "m",
        "laufmeter": "m",
        "m": "m",
        "pausch": "psch",
        "pauschal": "psch",
        "psch": "psch",
        "ls": "psch",
        "to": "to",
        "t": "to",
        "tonne": "to",
        "std": "h",
        "stds": "h",
        "stunde": "h",
        "stunden": "h",
        "h": "h",
        "hour": "h",
        "monate": "mt",
        "monat": "mt",
    }
    compact = re.sub(r"\s+", "", value)
    return aliases.get(compact, aliases.get(value, compact))


GERMAN_CONSTRUCTION_TERMS = {
    "baustelleneinrichtung": "site establishment",
    "baustelle": "site",
    "einbau": "installation",
    "montage": "installation",
    "lieferung": "supply",
    "ausschachten": "excavation",
    "aushub": "excavation",
    "rohrleitung": "pipe",
    "kanal": "sewer",
    "pflaster": "paving",
    "beton": "concrete",
    "entfernen": "removal",
    "rueckbau": "demolition",
    "ruckbau": "demolition",
}


def normalize_construction_text(text: str) -> str:
    text = re.sub(
        r"\[(?:PERSON|FIRMA|TELEFON|ORT|PROJEKT|[A-Z]+)_[^]]*\]",
        " ",
        text or "",
    )
    text = (text or "").replace("[...]", " ")
    value = unicodedata.normalize("NFKD", text).lower()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9%]+", " ", value)
    stopwords = {
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "und",
        "oder",
        "mit",
        "ohne",
        "nach",
        "gemass",
        "vorgabe",
        "position",
        "leistung",
        "leistungen",
        "lieferung",
        "einbau",
        "montage",
        "inkl",
        "einschl",
        "einschliesslich",
        "liefern",
        "verlegen",
        "herstellen",
        "fachgerecht",
    }
    tokens = [
        GERMAN_CONSTRUCTION_TERMS.get(token, token)
        for token in value.split()
        if token not in stopwords and len(token) > 1
    ]
    return " ".join(tokens)


def _extract_dn_set(text: str) -> set[int]:
    return {int(m) for m in re.findall(r"\bdn\s*([0-9]{2,4})\b", (text or "").lower())}


def load_benchmark_database(path: str | Path = "data/benchmarks.json") -> List[BenchmarkItem]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    result = []
    for row in rows if isinstance(rows, list) else []:
        try:
            result.append(
                BenchmarkItem(
                    oz=str(row.get("oz", "")),
                    short_text=str(row.get("short_text", "")),
                    unit=str(row.get("unit", "")),
                    unit_price=float(row.get("unit_price", 0) or 0),
                    section=str(row.get("section", "")),
                    long_text=str(row.get("long_text", "")),
                    quantity=float(row.get("quantity", 0) or 0),
                    source_file=str(row.get("source_file", "")),
                    is_outlier=bool(row.get("is_outlier", False)),
                    price_type=str(row.get("price_type", "offer")),
                )
            )
        except (TypeError, ValueError):
            continue
    return result


@st.cache_data(show_spinner=False)
def _cached_find_benchmark(
    short_text: str,
    long_text: str,
    canonical_unit: str,
    item_oz: str,
    benchmark_rows: tuple,
    threshold: float,
):
    benchmarks = [
        BenchmarkItem(
            oz=row[0],
            short_text=row[1],
            unit=row[2],
            unit_price=row[3],
            section=row[4],
            long_text=row[5],
            quantity=row[6],
            source_file=row[7],
            is_outlier=row[8],
            price_type=row[9],
        )
        for row in benchmark_rows
    ]
    item_unit = normalize_benchmark_unit(canonical_unit)
    item_short_norm = normalize_construction_text(short_text)
    item_full_norm = normalize_construction_text(f"{short_text} {long_text}".strip())
    item_tokens = {
        tok
        for tok in item_full_norm.split()
        if not re.fullmatch(r"(?:din|dn)?[0-9]+", tok)
    }
    item_dns = _extract_dn_set(f"{short_text} {long_text}")
    candidates = []

    domain_keywords = {
        "schachtabdeckung",
        "kanalrohr",
        "stahlbetonrohr",
        "uhpc",
        "asphalt",
        "asphalttragschicht",
        "asphaltdeckschicht",
        "frostschutz",
        "oberboden",
        "wasserhaltung",
        "bauzaun",
        "rohrgrabenaushub",
        "bodenaustausch",
        "tangentialschacht",
        "polier",
        "vorarbeiter",
        "facharbeiter",
        "minibagger",
        "bagger",
    }

    for benchmark in benchmarks:
        if benchmark.unit_price <= 0 or benchmark.is_outlier:
            continue
        benchmark_unit = normalize_benchmark_unit(benchmark.unit)
        if item_unit != benchmark_unit:
            continue

        bench_raw = f"{benchmark.short_text} {benchmark.long_text}".strip()
        bench_dns = _extract_dn_set(bench_raw)
        # Wenn beide eine DN-Nennweite haben, müssen sie kompatibel sein
        if item_dns and bench_dns and not (item_dns & bench_dns):
            continue

        bench_short_norm = normalize_construction_text(benchmark.short_text)
        bench_full_norm = normalize_construction_text(bench_raw)
        benchmark_tokens = {
            tok
            for tok in bench_full_norm.split()
            if not re.fullmatch(r"(?:din|dn)?[0-9]+", tok)
        }
        if not item_tokens or not benchmark_tokens:
            continue

        common = item_tokens & benchmark_tokens
        union = item_tokens | benchmark_tokens
        jaccard = len(common) / len(union) if union else 0.0
        # Containment-Recall: Kurzer Benchmark-Eintrag wird in langem GAEB-Langtext wiedergefunden
        containment = len(common) / max(1, min(len(item_tokens), len(benchmark_tokens)))
        short_seq = difflib.SequenceMatcher(None, item_short_norm, bench_short_norm).ratio()

        score = (0.45 * containment) + (0.25 * jaccard) + (0.30 * short_seq)
        shared_domains = common & domain_keywords
        score += 0.07 * len(shared_domains)
        if item_dns and bench_dns and (item_dns & bench_dns):
            score += 0.12

        if benchmark.oz and benchmark.oz == item_oz:
            score = max(score, 0.95)
        if score >= threshold:
            contract_bonus = 0.02 if benchmark.price_type == "contract" else 0.0
            candidates.append((score + contract_bonus, benchmark))

    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1], candidates[0][0]


def find_benchmark(
    item: NormalizedItem, benchmarks: List[BenchmarkItem], threshold: float = 0.42
):
    benchmark_rows = tuple(
        (
            benchmark.oz,
            benchmark.short_text,
            benchmark.unit,
            benchmark.unit_price,
            benchmark.section,
            benchmark.long_text,
            benchmark.quantity,
            benchmark.source_file,
            benchmark.is_outlier,
            benchmark.price_type,
        )
        for benchmark in benchmarks
    )
    return _cached_find_benchmark(
        item.short_text or "",
        item.long_text or "",
        normalize_benchmark_unit(item.unit),
        item.oz or "",
        benchmark_rows,
        threshold,
    )


@st.cache_data(show_spinner=False)
def parse_benchmarks(folder: str | Path) -> List[BenchmarkItem]:
    json_path = Path(folder).parent / "benchmarks.json"
    benchmarks = load_benchmark_database(json_path)
    if benchmarks:
        return benchmarks

    benchmarks = []
    folder = Path(folder)
    if not folder.exists():
        return benchmarks
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in (".d86", ".d84", ".x84", ".x86"):
            continue
        suffix = path.suffix.lower()
        if suffix in (".d86", ".d84"):
            items = parse_fixed_width(path)
            for item in items:
                benchmarks.append(BenchmarkItem(item.oz, item.short_text, item.unit, 0.0))
        else:
            try:
                for item in parse_x83(path):
                    benchmarks.append(BenchmarkItem(item.oz, item.short_text, item.unit, 0.0))
            except Exception:
                continue
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in (".d86", ".d84"):
            continue
        text = path.read_bytes().decode("cp850", errors="replace")
        current_oz = ""
        for line in text.splitlines():
            content = line[:74]
            if len(content) < 22:
                continue
            record = content[:2]
            if record == "21":
                current_oz = content[2:11].strip()
            elif record == "23" and current_oz:
                try:
                    unit_price = int(content[12:22].strip()) / 100.0
                except (ValueError, TypeError):
                    continue
                if not unit_price:
                    continue
                for i, benchmark in enumerate(benchmarks):
                    if benchmark.oz == current_oz and benchmark.unit_price == 0.0:
                        benchmarks[i] = BenchmarkItem(
                            benchmark.oz, benchmark.short_text, benchmark.unit, unit_price
                        )
                        break
    return benchmarks
````

## `README.md`
````md
# AI Estimation & Bidding Assistant

Challenge A is a standalone local Python application for estimating, reviewing, and
exporting German building Bills of Quantities (GAEB LV).

The Python core includes:

- `app.py` - Streamlit interface
- `parser.py` - GAEB `.X83`, `.D83`, `.D84`, and `.D86` parsing
- `ai_engine.py` - Morpheus/OpenAI-compatible analysis with rule-based fallback
- `calculator.py` - overhead, tactics, specialist prices, and time planning
- `exporter.py` - GAEB `.X84` and Excel exports
- `models.py` - normalized data structures

## Run the Python application

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

Install benchmark ingestion dependencies with the same requirements file, then run:

```powershell
python ingest_benchmarks.py --input-dir data/raw_benchmarks --output data/benchmarks.json
python ingest_benchmarks.py --exclude-file ground-truth
```

The app is available at `http://localhost:8501`.

Build or refresh the persistent benchmark database:

```powershell
python ingest_benchmarks.py
python ingest_benchmarks.py --exclude-source ground-truth
```

Upload an unpriced `.X83` or `.D83` file in the interface. Historical references may
be placed in `data/benchmarks/` as `.D84` or `.D86` files.

Morpheus is optional. To enable it, create a local `.env` file:

```text
MORPHEUS_API_KEY=your_key
MORPHEUS_BASE_URL=https://your-openai-compatible-endpoint/v1
MORPHEUS_MODEL=your_model
```

Without a key, the application runs the documented rule-based fallback.

## Frontend prototype

`frontend_demo/` contains the separate TanStack Start UI prototype used during the
hackathon. It is not the production entry point for Challenge A.

From the Python core, use the Streamlit command above. The prototype is not required
to parse or export BoQ data.

````

## `requirements.txt`
````txt
streamlit>=1.38
openai>=1.40
python-dotenv>=1.0
openpyxl>=3.1
pdfplumber>=0.11

````

## `risk_engine.py`
````py
from typing import Any, Dict, List, Set


SPECIALIST_KEYWORDS = (
    "bauseits",
    "nach vorgabe",
    "komplettanlage",
    "komplett",
    "raumsystem",
    "pauschal",
    "nach aufwand",
    "o.ä.",
    "ggf.",
    "wie angeordnet",
    "audio",
    "medientechnik",
    "sonderkonstruktion",
    "nach beigefügter zeichnung",
)


def _get(item: Any, *keys: str, default: Any = "") -> Any:
    for key in keys:
        if isinstance(item, dict) and key in item and item[key] is not None:
            return item[key]
        if hasattr(item, key) and getattr(item, key) is not None:
            return getattr(item, key)
    return default


def calculate_risk(item: Any, logic_result: Dict[str, Any]) -> Dict[str, Any]:
    """Phase 2: Risiko-Scoring & Routing für selektiven LLM-Einsatz."""
    severity = logic_result.get("severity", "low")
    flags = logic_result.get("flags", [])

    short_t = str(_get(item, "short_text", "description", default=""))
    long_t = str(_get(item, "long_text", default=""))
    desc = f"{short_t} {long_t}".lower()
    qty = float(_get(item, "qty", "quantity", default=0.0) or 0.0)
    unit = str(_get(item, "unit", default="")).strip().lower()

    matched_terms = [kw for kw in SPECIALIST_KEYWORDS if kw in desc]
    is_specialist = bool(matched_terms) or unit in ("psch", "pauschal", "ls")

    if severity == "high" or (is_specialist and (len(flags) > 0 or len(matched_terms) >= 2)):
        risk_score = "high"
    elif severity == "medium" or is_specialist:
        risk_score = "medium"
    else:
        risk_score = "low"

    # High-Severity-Fehler UND unklare Spezial-/Pauschalpositionen gehen ans LLM
    needs_llm = (risk_score == "high") or is_specialist

    # Prioritäts-Score für Top-N-Deckelung bei sehr großen LVs (z. B. 9.000 Positionen)
    priority_weight = (
        (100 if risk_score == "high" else (40 if risk_score == "medium" else 0))
        + len(flags) * 25
        + len(matched_terms) * 15
        + min(qty, 500.0) * 0.05
    )

    return {
        "risk_score": risk_score,
        "is_specialist": is_specialist,
        "needs_llm": needs_llm,
        "auto_accepted": not needs_llm,
        "priority_weight": round(priority_weight, 2),
    }


def select_top_llm_keys(
    items: List[Any], risk_results: List[Dict[str, Any]], max_llm_items: int = 100
) -> Set[str]:
    """Wählt die bis zu `max_llm_items` kritischsten Positionen anhand ihres globalen Index-Keys aus."""
    candidates = []
    for idx, (item, risk) in enumerate(zip(items, risk_results)):
        if risk.get("needs_llm"):
            oz = str(_get(item, "oz", "id", default=""))
            key = f"{idx}|{oz}"
            candidates.append((risk.get("priority_weight", 0.0), key))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return {key for _, key in candidates[:max_llm_items]}
````

## `rules_engine.py`
````py
from typing import Any, Dict, List


CATEGORY_MAP = {
    "concrete_m3": ["ortbeton", "stahlbeton", "beton c", "sauberkeitsschicht", "fundamentbeton"],
    "formwork_m2": ["schalung", "einschalen", "abschalung"],
    "rebar_t": ["bewehrung", "betonstahl", "baustahlmatte"],
    "pipe_m": ["rohr", "leitung", "kanal", "dn ", "dn2", "dn3", "dn4", "dn5", "dn6", "dn8"],
    "excavation_m3": ["aushub", "bagger", "graben", "ausheben", "bodenaushub"],
    "backfill_m3": ["verfüll", "verdicht", "auffüll", "humus", "wiederverfüll"],
    "floor_m2": ["estrich", "bodenbelag", "parkett", "fliese", "teppich", "bodenbeschichtung"],
    "floor_heating_m2": ["fußbodenheizung", "bodenheizung", "heizestrich"],
    "wall_m2": ["wand", "putz", "maler", "tapez", "anstrich", "mauerwerk"],
    "shaft_stk": ["schacht", "einlaufbauwerk", "kontrollschacht", "tangentialschacht"],
}


def _get(item: Any, *keys: str, default: Any = "") -> Any:
    for key in keys:
        if isinstance(item, dict) and key in item and item[key] is not None:
            return item[key]
        if hasattr(item, key) and getattr(item, key) is not None:
            return getattr(item, key)
    return default


def _full_text(item: Any) -> str:
    short_t = str(_get(item, "short_text", "description", default=""))
    long_t = str(_get(item, "long_text", default=""))
    return f"{short_t} {long_t}".strip().lower()


def tag_item(item: Any) -> List[str]:
    desc = _full_text(item)
    return [
        tag
        for tag, keywords in CATEGORY_MAP.items()
        if any(kw in desc for kw in keywords)
    ]


def compute_category_sums(items: List[Any]) -> Dict[str, float]:
    sums: Dict[str, float] = {}
    for item in items:
        qty = float(_get(item, "qty", "quantity", default=0.0) or 0.0)
        if qty <= 0:
            continue
        for tag in tag_item(item):
            sums[tag] = round(sums.get(tag, 0.0) + qty, 2)
    return sums


def run_logic_engine(items: List[Any]) -> List[Dict[str, Any]]:
    """Phase 1: Deterministische Regel- und Plausibilitätsprüfung."""
    results: List[Dict[str, Any]] = []
    item_tags: List[List[str]] = [tag_item(item) for item in items]
    category_sums = compute_category_sums(items)

    has_any_installation = any(
        any(w in _full_text(it) for w in ("montage", "einbau", "verlegen", "versetzen"))
        for it in items
    )

    for idx, item in enumerate(items):
        flags: List[str] = []
        severity = "low"

        oz = str(_get(item, "oz", "id", default=f"POS-{idx}"))
        short_text = str(_get(item, "short_text", "description", default=""))
        long_text = str(_get(item, "long_text", default=""))
        desc = f"{short_text} {long_text}".lower()
        qty = float(_get(item, "qty", "quantity", default=0.0) or 0.0)
        unit = str(_get(item, "unit", default="")).strip().lower()
        item_type = str(_get(item, "item_type", default="Normal"))
        tags = item_tags[idx]

        # 1. Meta-Widersprüche (High)
        if ("pauschal" in desc or unit in ("psch", "pauschal", "ls")) and qty not in (0.0, 1.0):
            flags.append(f"META_MISMATCH: Pauschale hat Menge {qty:g} statt 1")
            severity = "high"

        if qty <= 0 and item_type.lower() not in ("eventual", "bedarfsposition", "alternativ"):
            flags.append("ZERO_QTY: Normalposition ohne positive Menge")
            severity = "high"

        # 2. Mögliche Zahlendreher / Ausreißer (Medium)
        if unit in ("m²", "m2", "qm") and qty >= 1000:
            flags.append(f"QTY_OUTLIER: Sehr große Fläche ({qty:g} {unit}) – Zahlendreher prüfen")
            if severity == "low":
                severity = "medium"
        elif unit in ("stk", "stück", "st") and qty >= 500:
            flags.append(f"QTY_OUTLIER: Sehr hohe Stückzahl ({qty:g} {unit}) – Zahlendreher prüfen")
            if severity == "low":
                severity = "medium"

        # 3. Fehlender Langtext bei komplexer Position (Medium)
        if len(long_text.strip()) < 15 and any(
            kw in desc for kw in ("anlage", "system", "komplett", "sonder", "bauwerk", "schacht")
        ):
            flags.append("MISSING_SPEC: Komplexer Kurztext ohne ausreichenden Langtext")
            if severity == "low":
                severity = "medium"

        # 4. Lieferung ohne Einbau/Montage (Medium)
        if "lieferung" in desc and not any(
            w in desc for w in ("montage", "einbau", "verlegen", "versetzen", "inkl.")
        ):
            if not has_any_installation:
                flags.append("SCOPE_GAP: Reine Lieferung ohne erkennbare Montageposition im LV")
                if severity == "low":
                    severity = "medium"

        # 5. Projektweite Mengen- & Gewerk-Plausibilität
        if "floor_heating_m2" in tags and category_sums.get("floor_m2", 0) > 0:
            if category_sums["floor_heating_m2"] > category_sums["floor_m2"] * 1.05:
                flags.append("CATEGORY_MISMATCH: Fußbodenheizung > gesamte Bodenfläche")
                if severity == "low":
                    severity = "medium"

        if "excavation_m3" in tags and category_sums.get("excavation_m3", 0) > 0:
            if category_sums.get("backfill_m3", 0) < category_sums["excavation_m3"] * 0.3:
                flags.append("MISSING_FOLLOW_UP: Geringe Verfüllung im Verhältnis zum Aushub")
                if severity == "low":
                    severity = "medium"

        if "concrete_m3" in tags and category_sums.get("concrete_m3", 0) >= 10:
            if category_sums.get("formwork_m2", 0) == 0 and category_sums.get("rebar_t", 0) == 0:
                flags.append("MISSING_FOLLOW_UP: Betonpositionen ohne Schalung/Bewehrung im LV")
                if severity == "low":
                    severity = "medium"

        results.append(
            {
                "id": oz,
                "oz": oz,
                "flags": flags,
                "severity": severity,
                "tags": tags,
            }
        )

    return results
````

## `test_parser_gaeb.py`
````py
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from parser import parse_x83, clean_text


GAEB_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<GAEB xmlns="{namespace}">
  <Award><AddText><p>Vorbemerkung <span style="color:red">Beweissicherung</span></p></AddText></Award>
  <BoQ><BoQBody>
    <BoQCtgy><RNoPart>01</RNoPart><LblTx>Tiefbau</LblTx>
      <BoQCtgy><RNoPart>01</RNoPart><LblTx>Rohre</LblTx>
        <Item ID="id2232">
          <RNoPart>0004</RNoPart>
          <OutlineText><p>UHPC-Stahlbetonrohre liefern</p></OutlineText>
          <DetailTxt><p>Liefern <span style="font-weight:bold">und verlegen</span>.</p></DetailTxt>
          <Remark>Nach Vorgabe</Remark>
          <Qty><Quantity>10</Quantity></Qty><QU>m</QU>
        </Item>
        <Item ID="id2233">
          <RNoPart>0005</RNoPart>
          <OutlineText><p>wie vor, jedoch DN 900</p></OutlineText>
          <DetailTxt><p>wie vor, jedoch DN 900</p></DetailTxt>
          <Qty><Quantity>20</Quantity></Qty><QU>m</QU>
        </Item>
      </BoQCtgy>
    </BoQCtgy>
  </BoQBody></BoQ>
</GAEB>
"""


class GaebNamespaceParserTests(unittest.TestCase):
    def parse(self, namespace):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boq.X83"
            path.write_text(
                GAEB_TEMPLATE.format(namespace=namespace),
                encoding="utf-8",
            )
            return parse_x83(path)

    def test_gaeb_31_and_32_parse_identically(self):
        gaeb31 = self.parse("http://www.gaeb.de/GAEB_DA_XML/200407")
        gaeb32 = self.parse("DA83/3.2")
        fields31 = [(i.oz, i.short_text, i.long_text, i.qty, i.unit, i.xml_id) for i in gaeb31]
        fields32 = [(i.oz, i.short_text, i.long_text, i.qty, i.unit, i.xml_id) for i in gaeb32]
        self.assertEqual(fields31, fields32)

    def test_hierarchical_oz_and_previous_item_context(self):
        items = self.parse("http://www.gaeb.de/GAEB_DA_XML/200407")
        self.assertEqual(items[0].oz, "01.01.0004")
        self.assertEqual(items[1].oz, "01.01.0005")
        self.assertIn("UHPC-Stahlbetonrohre", items[1].context_from_previous_item)

    def test_clean_detail_text_removes_inline_styles(self):
        text = clean_text(
            "<p>Liefern <span style=\"font-weight:bold\">und verlegen</span>.</p>"
        )
        self.assertNotIn("<", text)
        self.assertIn("Liefern", text)
        self.assertIn("verlegen", text)


if __name__ == "__main__":
    unittest.main()

````
