"""Price options and ready-to-send mails for a single risky position.

Two things an estimator does with a flagged position: he decides what to put
in the price, and he asks someone a question. This module produces both as
text he can act on without retyping anything.

The three price options are not invented — they are the calculation's own
`h_min` / `h_mittel` / `h_max` band, relabelled for the decision being made:

    aggressiv    the fast time. Use when the quantity is certain and you want
                 the job.
    realistisch  the standard time. The default.
    abgesichert  the slow time. Use when the scope is open, because that is
                 the case you will actually be building.

Where a position carries Nachtragspotenzial — the quantity is likely to grow
after award — the recommendation flips: price it low to win, because the
money comes from the Mehrmenge under VOB/B § 2 Abs. 3. That is the
speculation play, and it is a deliberate commercial decision, so it is
labelled as one rather than applied silently.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Optional

MAILTO_LIMIT = 1800   # browsers truncate long mailto URLs; keep a copy fallback


@dataclass
class Preisoption:
    label: str
    ep: float
    gp: float
    begruendung: str
    empfohlen: bool = False


def preisoptionen(calculated, nachtragspotenzial: float = 0.0) -> list[Preisoption]:
    """Three priceable options for one position, cheapest first."""
    if calculated is None or not calculated.priced:
        return []

    quantity = calculated.item.quantity or 0.0
    speculative = nachtragspotenzial >= 0.70

    options = [
        Preisoption(
            "aggressiv", calculated.ep_low, (calculated.ep_low or 0.0) * quantity,
            "Schnellster Ansatz der Richtwerte. Nur bei sicherer Menge und "
            "bekanntem Baugrund.",
        ),
        Preisoption(
            "realistisch", calculated.ep_mid, (calculated.ep_mid or 0.0) * quantity,
            "Mittlerer Richtwert. Standardansatz ohne besondere Annahmen.",
        ),
        Preisoption(
            "abgesichert", calculated.ep_high, (calculated.ep_high or 0.0) * quantity,
            "Langsamster Ansatz. Deckt offenen Leistungsumfang und "
            "Erschwernisse ab.",
        ),
    ]

    if speculative:
        options[0].empfohlen = True
        options[0].begruendung = (
            "Empfohlen: Die Menge wird voraussichtlich steigen. Niedriger "
            "Einheitspreis sichert den Zuschlag, die Marge kommt über die "
            "Mehrmenge (VOB/B § 2 Abs. 3)."
        )
    else:
        options[1].empfohlen = True

    return options


def _position_block(item, calculated) -> str:
    lines = [
        f"OZ {getattr(item, 'display_oz', item.oz)}",
        f"Kurztext: {item.short_text or '—'}",
        f"Menge: {item.quantity:,.3f} {item.unit or '—'}".replace(",", "X")
        .replace(".", ",").replace("X", "."),
    ]
    if calculated is not None and calculated.leistung is not None:
        lines.append(f"Zugeordnete Leistung: {calculated.leistung.label()}")
    return "\n".join(lines)


def rfi_mail(item, calculated, gruende: list[str], projekt: str = "") -> dict:
    """A clarification question to the client. Short, VOB-appropriate."""
    oz = getattr(item, "display_oz", item.oz)
    betreff = f"Bieterfrage zu Position {oz}" + (f" – {projekt}" if projekt else "")
    grund_text = "\n".join(f"- {g}" for g in gruende if g) or \
        "- Der Leistungsumfang ist aus der Position nicht eindeutig ableitbar."

    body = f"""Sehr geehrte Damen und Herren,

im Rahmen der Angebotsbearbeitung ergibt sich zu nachstehender Position eine
Rückfrage:

{_position_block(item, calculated)}

Anlass der Rückfrage:
{grund_text}

Wir bitten um Klarstellung, damit die Position eindeutig und vergleichbar
kalkuliert werden kann. Sofern die Leistung wie beschrieben gewollt ist,
bitten wir um kurze Bestätigung.

Mit freundlichen Grüßen
"""
    return {"betreff": betreff, "body": body, "empfaenger": ""}


def rfq_mail(item, calculated, gruende: list[str], projekt: str = "") -> dict:
    """A quotation request to a subcontractor. Deliberately fuller than the RFI.

    A subcontractor cannot price from the OZ alone: he needs the full
    specification text, the quantity, the site constraints and a deadline.
    Leaving any of it out produces a quote with a caveat instead of a price.
    """
    oz = getattr(item, "display_oz", item.oz)
    betreff = f"Angebotsanfrage Nachunternehmerleistung – Position {oz}" + \
        (f" – {projekt}" if projekt else "")
    langtext = (item.long_text or "").strip() or "— kein Langtext im LV —"
    hinweise = "\n".join(f"- {g}" for g in gruende if g) or "- keine"

    body = f"""Sehr geehrte Damen und Herren,

für das nachfolgende Bauvorhaben bitten wir um ein Angebot über die unten
beschriebene Nachunternehmerleistung.

{_position_block(item, calculated)}

Leistungsbeschreibung laut Leistungsverzeichnis:
{langtext}

Für die Kalkulation relevante Hinweise:
{hinweise}

Bitte geben Sie an:
- Einheitspreis und Gesamtpreis netto
- enthaltene Nebenleistungen sowie ausdrücklich nicht enthaltene Leistungen
- benötigte Vorleistungen und Bauseitsleistungen
- Ausführungsdauer und früheste Verfügbarkeit
- Gültigkeitsdauer des Angebots

Sollten Angaben für eine belastbare Kalkulation fehlen, teilen Sie uns dies
bitte mit, anstatt Annahmen zu treffen.

Mit freundlichen Grüßen
"""
    return {"betreff": betreff, "body": body, "empfaenger": ""}


def mailto_link(mail: dict) -> Optional[str]:
    """`mailto:` URL, or None when the body is too long for a browser.

    Long URLs get silently truncated by some mail clients, which would send a
    half-finished enquiry. Returning None lets the caller offer the copy
    button instead of a link that quietly loses the end of the message.
    """
    query = urllib.parse.urlencode(
        {"subject": mail["betreff"], "body": mail["body"]},
        quote_via=urllib.parse.quote,
    )
    url = f"mailto:{mail.get('empfaenger', '')}?{query}"
    return url if len(url) <= MAILTO_LIMIT else None
