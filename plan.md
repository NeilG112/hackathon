**1. Core Idea (Still Valid, Now Sharpened)**
We are not building a generic "BoQ Analyzer," but a **Bid & Risk Assistant** from the perspective of the estimator / construction company.
Target output after uploading a new BoQ:

- Realistic total bid price (adjustable live with company parameters)
- Top 15–25 critical line items, sorted by € leverage
- Each finding includes: rationale + estimated change order / risk volume in € + ready-to-use Request for Information (RFI) or tactical pricing recommendation
- Speculative pricing detection in already priced files

Everything else (what-if scenarios, extensive historical integration, compliance checks) will only be mentioned or shown as a "Next Step."

**2. Data Architecture – What We Build Upfront vs. What Is Used at Runtime**

| **Layer** | **What Exactly** | **When Built** | **File / Storage Location** | **Used For** |
| --- | --- | --- | --- | --- |
| **1. Master Rates** | Average wage rate, machine hourly rates, general overhead %, profit & risk %, standard productivity rates, guide prices for common materials | Once manually + AI-generated, fixed thereafter | `data/master_rates.json` | Pricing new line items + risk valuation in € |
| **2. Reference Prices** | All unit prices + quantities from the 2 priced files (`.D84` + `.D86`), normalized | Once during parsing | `data/reference_prices.json` | Benchmarking + speculative pricing detection |
| **3. Semantic Corpus** | Line items from the ~30 trade PDFs → assigned `semantic_category` + co-occurrence matrix (which categories co-occur and how often) | Once offline (Saturday) | `data/corpus_rules.json` | Missing-companion detector |
| **4. Rule & Signal Knowledge** | Vague-scope trigger words, unit inconsistencies, typical quantity ratios, provisional/optional item patterns | Manually + from analysis | `data/rules.json` + hardcoded in detectors | Vague scope, quantity plausibility, provisional item ratio |
| **5. Runtime Input** | Uploaded new BoQ (`.X83` / `.D84` / `.D86` / `PDF`) | At runtime | Temporarily in memory | Parsed into `List[NormalizedItem]` |
| **6. Company Parameters (UI)** | Live-adjustable sliders (average wage rate, machine hourly rate, overhead, profit & risk, tactical factor) | At runtime by user | Streamlit Session State | Influences total bid price and tactical pricing recommendations |

**Key Takeaway:**
Only layers 1–4 are built/trained upfront. For every new BoQ, all we need at runtime are the parser + the pre-built knowledge files + the company sliders. This keeps the app fast and stable.

**3. Recommended Project Structure**

```
boq-assistant/
├── app.py                      # Streamlit UI (main demo)
├── build_corpus.py             # Offline: PDFs → corpus_rules.json
├── build_reference_prices.py   # Offline: D84/D86 → reference_prices.json
├── data/
│   ├── master_rates.json
│   ├── reference_prices.json
│   ├── corpus_rules.json
│   └── rules.json
├── core/
│   ├── models.py               # NormalizedItem + Pydantic
│   ├── parser_x83.py
│   ├── parser_gaeb90.py
│   ├── parser_pdf.py           # only for corpus building
│   ├── detectors.py            # all 5 detectors
│   └── pricer.py               # markup calculation + € risk
├── utils/
│   ├── text_cleaning.py
│   └── semantic.py             # LLM wrapper for category + vague check
└── requirements.txt
```