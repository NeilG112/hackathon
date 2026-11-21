# RECOVERED FROM PROCESS MEMORY - fragments, longest first.
# Stitch by hand; the original was ~23,000 characters.

 Streamlit UI. Task 007.

    streamlit run app.py

> It reads a construction tender file, finds the line items that will cost the
> contractor money, and writes the clarification letter he'd otherwise spend
> four hours on.

Lead with that sentence. No vocabulary lesson, no file extensions.

Wired: upload -> parse -> item table -> company sliders -> priced totals ->
the reveal. Still stubbed, and owned by other people:

  * the findings panel lights up when `core/detectors.py` (task 004) lands
  * the export button lights up when `export_rfi.py` (task 006) lands

Both are guarded, so an unfinished module shows a note instead of a traceback.

Fallbacks, in order: live parse -> `data/golden/` fixture -> an honest
"format not supported" with the sample loaded on a button. Degrade visibly
rather than fabricating output.
"""

from __future__ import annotations

import os
import tempfile
import traceback

import pandas as pd
import streamlit as st

from core import (classify, constants, detectors, kalkulation, logic, objects,
                  parser_gaeb90, parser_x83, pricer, stammdaten)
from views import reveal

ONE_SENTENCE = (
    "It reads a construction tender file, finds the line items that will cost "
    "the contractor money, and writes the clarification letter he'd otherwise "
    "spend four hours on."
)

SAMPLE = constants.REVEAL["blank_boq"]
ANSWER_KEY = constants.REVEAL["answer_key"]

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
GAEB90_SUFFIXES = (".d83", ".d81", ".d84", ".d86")

st.set_page_config(page_title="Bid & Risk Assistant", layout="wide")


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


# --- sections --------------------------------------------------------------

def sidebar_kalkulation() -> stammdaten.Company:
    """The cost base the bottom-up calculation uses.

    These are the parameters the client said a contractor must bring himself:
    *"Maschinenstundens

# --------------------------------------------------------------------

-facing Streamlit UI."""

from __future__ import annotations

import os
import tempfile
import traceback

import pandas as pd
import streamlit as st

from core import (
    classify,
    constants,
    kalkulation,
    objects,
    parser_gaeb90,
    parser_x83,
    stammdaten,
)

PAGES = ("Tender", "Groups", "Logic", "Das Angebot", "Heikle Positionen")

SAMPLE = constants.REVEAL["blank_boq"]

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
GAEB90_SUFFIXES = (".d83", ".d81", ".d84", ".d86")

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


def rehydrate(dicts: list[dict]):
    from core.models import NormalizedItem
    return [NormalizedItem.from_dict(d) for d in dicts]


# --- sections --------------------------------------------------------------

def sidebar_kalkulation() -> stammdaten.Company:
    """The cost base the bottom-up calculation uses.

    These are the parameters the client said a contractor must bring himself:
    *"Maschinenstundens

# --------------------------------------------------------------------

 user-facing Streamlit UI."""

from __future__ import annotations

import os
import tempfile
import traceback

import pandas as pd
import streamlit as st

from core import (
    classify,
    constants,
    kalkulation,
    objects,
    parser_gaeb90,
    parser_x83,
    stammdaten,
)

PAGES = ("Tender", "Groups", "Logic", "Das Angebot", "Heikle Positionen")

SAMPLE = constants.REVEAL["blank_boq"]

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
GAEB90_SUFFIXES = (".d83", ".d81", ".d84", ".d86")

st.set_page_config(
    page_title="Bid & Risk Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- parsing ---------------------------------------------------------------

def parse_path(path: str):
    """Parse 

# --------------------------------------------------------------------

widtht tstrfile
len:7t traceback

import pandas as pd
import streamlit as st

from core import (
    classify,
    constants,
    kalkulation,
    objects,
    parser_gaeb90,
    parser_x83,
    stammdaten,
)

PAGES = ("Tender", "Groups", "Logic", "Das Angebot", "Heikle Positionen")

SAMPLE = constants.REVEAL["blank_boq"]

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
GAEB90_SUFFIXES = (".d83", ".d81", ".d84", ".d86")

st.set_page_config(
    page_title="Bid & Risk Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- parsing ---------------------------------Q

# --------------------------------------------------------------------

width,
 strinitilen:7debar_state="expanded",
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
 q

# --------------------------------------------------------------------

