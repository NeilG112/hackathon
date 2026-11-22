"""Vergabe page — make-or-buy per trade, and what the company earns on it.

The seam with `app.py` is one function:

    from views import vergabe as vergabe_view
    vergabe_view.render(scope, auswerten)

`auswerten(entscheidungen) -> VergabeErgebnis` is `core.vergabe.auswerten`
with the tender already bound; this module only draws and collects decisions.

Streamlit cleans up widget state for widgets not drawn in a run, and not
uniformly: a radio key disappears, a number_input key is reset to None. So the
widget keys are never trusted across pages. The single source of truth is a
plain session key per tender (`scope`): every widget writes into it through an
`on_change` callback (callbacks run before the script), and every run copies it
back into the widget keys before the widgets are drawn.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional

import streamlit as st

from core import session_store
from core.vergabe import (DEFAULT_AUFSCHLAG_PCT, MODUS_LABEL,
                          GewerkEntscheidung, GewerkZeile, Modus,
                          VergabeErgebnis)

STORE_KEY = "vergabe_entscheidungen"
AUFSCHLAG_MIN, AUFSCHLAG_MAX, AUFSCHLAG_STEP = 0.0, 30.0, 1.0
# Plain strings in the widget, converted to Modus right after it.
MODI = tuple(m.value for m in (Modus.SELBST, Modus.FREMD_OFFEN, Modus.FREMD_ANGEBOT))

Auswerten = Callable[[Mapping[str, GewerkEntscheidung]], VergabeErgebnis]


def eur(value: Optional[float]) -> str:
    if value is None:
        return "–"
    return f"{value:,.0f} €".replace(",", ".")


def gespeicherte_entscheidungen(scope: str) -> dict[str, GewerkEntscheidung]:
    """Decisions stored for this tender. Used by other pages for the bid sum."""
    return dict(st.session_state.get(STORE_KEY, {}).get(scope, {}))


def _speichern(scope: str, entscheidungen: Mapping[str, GewerkEntscheidung]) -> None:
    store = st.session_state.get(STORE_KEY, {})
    st.session_state[STORE_KEY] = {**store, scope: dict(entscheidungen)}
    session_store.persist(st.session_state)


def _keys(scope: str, gewerk: str) -> tuple[str, str, str]:
    base = f"vg::{scope}::{gewerk}"
    return f"{base}::modus", f"{base}::einkauf", f"{base}::aufschlag"


def _widget_state_wiederherstellen(scope: str, zeile: GewerkZeile,
                                   gespeichert: Optional[GewerkEntscheidung]) -> None:
    e = gespeichert or zeile.entscheidung
    k_modus, k_einkauf, k_aufschlag = _keys(scope, zeile.gewerk)
    st.session_state[k_modus] = e.modus.value
    st.session_state[k_einkauf] = e.einkauf_eur
    st.session_state[k_aufschlag] = float(e.aufschlag_pct)


def _uebernehmen(scope: str, gewerk: str, default: Modus) -> None:
    """on_change callback: copy this trade's widget values into the store."""
    k_modus, k_einkauf, k_aufschlag = _keys(scope, gewerk)
    ss = st.session_state
    modus = Modus(ss[k_modus]) if ss.get(k_modus) else default
    einkauf = ss.get(k_einkauf)
    neu = GewerkEntscheidung(
        gewerk, modus,
        float(einkauf) if einkauf else None,
        float(ss.get(k_aufschlag, DEFAULT_AUFSCHLAG_PCT)),
    )
    _speichern(scope, {**gespeicherte_entscheidungen(scope), gewerk: neu})


def _zeile_zeichnen(scope: str, zeile: GewerkZeile) -> GewerkEntscheidung:
    """Draw one trade row and return the decision the widgets now hold."""
    k_modus, k_einkauf, k_aufschlag = _keys(scope, zeile.gewerk)
    sync = {"on_change": _uebernehmen,
            "args": (scope, zeile.gewerk, zeile.entscheidung.modus)}
    name, pos, volumen, wahl = st.columns([3, 1, 2, 5], vertical_alignment="center")

    hinweis = "  \n:gray[oft vergeben]" if zeile.oft_vergeben else ""
    name.markdown(f"**{zeile.gewerk}**{hinweis}")
    pos.markdown(f"{len(zeile.positionen)} Pos.")
    if zeile.eigen_eur > 0:
        extra = f"  \n:orange[{zeile.unkalkuliert} ohne Preis]" if zeile.unkalkuliert else ""
        volumen.markdown(f"{eur(zeile.eigen_eur)}{extra}")
    else:
        volumen.markdown(":orange[? kein Preis]")

    gewaehlt = wahl.radio(
        "Wer macht's?", MODI, key=k_modus, horizontal=True,
        format_func=lambda m: MODUS_LABEL[Modus(m)],
        label_visibility="collapsed", **sync,
    )
    modus = Modus(gewaehlt) if gewaehlt else zeile.entscheidung.modus

    einkauf = st.session_state.get(k_einkauf)
    aufschlag = float(st.session_state.get(k_aufschlag, 0.0))
    if modus is Modus.SELBST:
        return GewerkEntscheidung(zeile.gewerk, modus, einkauf, aufschlag)

    _, body = st.columns([1, 10])
    with body:
        if modus is Modus.FREMD_OFFEN:
            st.warning(f"{len(zeile.positionen)} Positionen ohne Preis aus "
                       "Vergabe. Angebot einholen und eintragen.", icon="⚠️")
            return GewerkEntscheidung(zeile.gewerk, modus, einkauf, aufschlag)

        c_betrag, c_aufschlag, c_gewinn = st.columns([3, 4, 3])
        einkauf = c_betrag.number_input(
            "Einkauf (Angebot Nachunternehmer, netto €)", min_value=0.0,
            step=500.0, key=k_einkauf, placeholder="Betrag eintragen", **sync,
        )
        if not einkauf:
            c_aufschlag.info("Aufschlag erscheint, sobald ein Betrag da ist.")
            return GewerkEntscheidung(zeile.gewerk, modus, None, aufschlag)

        aufschlag = c_aufschlag.slider(
            "Aufschlag (%)", AUFSCHLAG_MIN, AUFSCHLAG_MAX, step=AUFSCHLAG_STEP,
            key=k_aufschlag, **sync,
        )
        gewinn = einkauf * aufschlag / 100.0
        c_gewinn.metric("Gewinn", eur(gewinn),
                        help="Ersetzt die eigene Kalkulation dieses Gewerks "
                             f"({eur(zeile.eigen_eur)}), kommt nicht dazu.")
        if zeile.eigen_eur > 0:
            c_gewinn.caption(f"ersetzt eigene Kalkulation {eur(zeile.eigen_eur)}")
        return GewerkEntscheidung(zeile.gewerk, modus, float(einkauf), float(aufschlag))


def _kopf(ziel, ergebnis: VergabeErgebnis, basis: VergabeErgebnis) -> None:
    a, b, c = ziel.columns(3)
    delta = ergebnis.angebotssumme - basis.angebotssumme
    a.metric("Angebotssumme", eur(ergebnis.angebotssumme),
             delta=eur(delta) if abs(delta) >= 1 else None)
    b.metric("Gewinn gesamt", eur(ergebnis.gewinn_gesamt))
    c.metric("Vergabe", f"{ergebnis.fremd_mit_angebot} von "
             f"{ergebnis.fremd_gesamt} Gewerken mit Angebot")


def _gewinn_block(ergebnis: VergabeErgebnis) -> None:
    st.divider()
    st.subheader("Gewinn")
    links, rechts = st.columns(2)
    links.metric("aus eigener Leistung", eur(ergebnis.gewinn_eigen),
                 help="Wagnis & Gewinn auf die Einzelkosten der selbst "
                      "ausgeführten Gewerke.")
    rechts.metric("aus Vergabe", eur(ergebnis.gewinn_vergabe),
                  help="Aufschlag auf die eingekauften Nachunternehmerleistungen.")
    st.metric("gesamt", eur(ergebnis.gewinn_gesamt))
    if ergebnis.offen:
        st.warning("Noch ohne Angebot und deshalb nicht in der Angebotssumme: "
                   + ", ".join(ergebnis.offen))
    st.caption("Ein Aufschlag je eingekauftem Gewerk. Ob Nachunternehmer"
               "leistungen zusätzlich AGK/BGK tragen, ist noch nicht geklärt.")


def render(scope: str, auswerten: Auswerten) -> VergabeErgebnis:
    """Draw the Vergabe page and return the result of the current decisions."""
    st.caption("Welche Gewerke führst du selbst aus, welche vergibst du — und "
               "was verdienst du daran? Ein Angebot ersetzt die eigene "
               "Kalkulation des Gewerks, es wird nicht addiert.")
    basis = auswerten({})
    gespeichert = gespeicherte_entscheidungen(scope)
    kopf = st.container()

    st.divider()
    entscheidungen: dict[str, GewerkEntscheidung] = {}
    for zeile in basis.zeilen:
        _widget_state_wiederherstellen(scope, zeile, gespeichert.get(zeile.gewerk))
        with st.container(border=True):
            entscheidungen = {**entscheidungen,
                              zeile.gewerk: _zeile_zeichnen(scope, zeile)}

    _speichern(scope, entscheidungen)
    ergebnis = auswerten(entscheidungen)
    _kopf(kopf, ergebnis, basis)
    _gewinn_block(ergebnis)
    return ergebnis
