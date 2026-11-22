import unittest

from core import vergabe
from core.kalkulation import CalculatedItem, CostBreakdown, calculate_item
from core.models import NormalizedItem
from core.stammdaten import Company, Leistung, Stammdaten
from core.vergabe import GewerkEntscheidung, Modus

ERDBAU = Leistung("E1", "Erdbau", "Boden lösen", "m3", 0.1, 0.2, 0.3)
PRUEFUNG = Leistung("P1", "Prüfung", "TV-Inspektion", "m", 0.05, 0.1, 0.15)
DATA = Stammdaten({"E1": ERDBAU, "P1": PRUEFUNG}, {}, {})
COMPANY = Company(agk_pct=0.0, bgk_pct=0.0, wg_pct=10.0)


def _item(oz: str, qty: float = 1.0) -> NormalizedItem:
    return NormalizedItem(oz=oz, quantity=qty, unit="m3", short_text=oz)


def _calc(item: NormalizedItem, leistung, ekt: float) -> CalculatedItem:
    """A priced position whose direct cost per unit is `ekt`, +10 % W&G."""
    ep = ekt * 1.10
    return CalculatedItem(item=item, leistung=leistung, ep_low=ep, ep_mid=ep,
                          ep_high=ep, breakdown=CostBreakdown(labour_eur=ekt))


def _tender():
    """Erdbau 1 000 €, Prüfung 10 000 € (both incl. 10 % W&G), one unassigned."""
    e, p, x = _item("01"), _item("02"), _item("03")
    assignments = {"01": ("E1", 1.0), "02": ("P1", 1.0)}
    calculated = [
        _calc(e, ERDBAU, 1000 / 1.1),
        _calc(p, PRUEFUNG, 10000 / 1.1),
        CalculatedItem(item=x, leistung=None),
    ]
    return [e, p, x], assignments, calculated


def _run(entscheidungen=None):
    items, assignments, calculated = _tender()
    return vergabe.auswerten(items, assignments, DATA, calculated, COMPANY,
                             entscheidungen)


def _row(result, gewerk):
    return next(z for z in result.zeilen if z.gewerk == gewerk)


class DefaultTests(unittest.TestCase):
    def test_default_keeps_bid_unchanged(self):
        result = _run()
        self.assertAlmostEqual(result.angebotssumme, 11000.0, places=2)

    def test_unassigned_trade_starts_as_open_subcontract(self):
        result = _run()
        row = _row(result, vergabe.UNASSIGNED_TRADE)
        self.assertIs(row.entscheidung.modus, Modus.FREMD_OFFEN)
        self.assertEqual(result.offen, (vergabe.UNASSIGNED_TRADE,))

    def test_priced_trades_start_as_own_work(self):
        result = _run()
        self.assertIs(_row(result, "Erdbau").entscheidung.modus, Modus.SELBST)

    def test_typical_subcontract_trade_is_hint_only(self):
        row = _row(_run(), "Prüfung")
        self.assertTrue(row.oft_vergeben)
        self.assertIs(row.entscheidung.modus, Modus.SELBST)

    def test_own_profit_is_wg_share_of_direct_cost(self):
        self.assertAlmostEqual(_run().gewinn_eigen, 1000.0, places=2)


class QuoteTests(unittest.TestCase):
    def test_quote_replaces_own_calculation_instead_of_adding(self):
        quote = GewerkEntscheidung("Prüfung", Modus.FREMD_ANGEBOT, 8000.0, 10.0)
        result = _run({"Prüfung": quote})
        self.assertAlmostEqual(result.angebotssumme, 1000.0 + 8800.0, places=2)

    def test_quote_profit_counted_separately(self):
        quote = GewerkEntscheidung("Prüfung", Modus.FREMD_ANGEBOT, 8000.0, 10.0)
        result = _run({"Prüfung": quote})
        self.assertAlmostEqual(result.gewinn_vergabe, 800.0, places=2)
        self.assertAlmostEqual(result.gewinn_eigen, 1000 / 1.1 * 0.1, places=2)
        self.assertEqual((result.fremd_mit_angebot, result.fremd_gesamt), (1, 2))

    def test_open_subcontract_drops_out_of_bid(self):
        result = _run({"Prüfung": GewerkEntscheidung("Prüfung", Modus.FREMD_OFFEN)})
        self.assertAlmostEqual(result.angebotssumme, 1000.0, places=2)
        self.assertIn("Prüfung", result.offen)

    def test_quote_mode_without_amount_counts_as_open(self):
        empty = GewerkEntscheidung("Prüfung", Modus.FREMD_ANGEBOT, None)
        result = _run({"Prüfung": empty})
        self.assertIn("Prüfung", result.offen)
        self.assertIsNone(_row(result, "Prüfung").angebot_eur)

    def test_mit_entscheidung_does_not_mutate_input(self):
        before = {}
        after = vergabe.mit_entscheidung(
            before, GewerkEntscheidung("Erdbau", Modus.FREMD_OFFEN))
        self.assertEqual(before, {})
        self.assertIn("Erdbau", after)


class ZeroPriceGuardTests(unittest.TestCase):
    def test_leistung_without_rates_is_not_priced(self):
        empty = Leistung("X1", "Elektro", "Kabel ziehen", "m3", 0, 0, 0,
                         status="ohne_preis")
        result = calculate_item(_item("09"), empty, COMPANY, DATA)
        self.assertFalse(result.priced)
        self.assertIn("keine Aufwandswerte", result.note)

    def test_only_h_max_without_mid_is_not_priced(self):
        partial = Leistung("X2", "Elektro", "Kabel", "m3", 0, 0, 0.5)
        result = calculate_item(_item("09"), partial, COMPANY, DATA)
        self.assertFalse(result.priced)

    def test_only_h_min_without_mid_is_not_priced(self):
        partial = Leistung("X3", "Elektro", "Kabel", "m3", 0.5, 0, 0)
        result = calculate_item(_item("09"), partial, COMPANY, DATA)
        self.assertFalse(result.priced)

    def test_note_carries_catalogue_remark(self):
        b01 = Leistung("B01", "Baustelle", "BE", "m3", 0, 0, 0,
                       bemerkung="Kalkuliert als Anteil der Einzelkosten.")
        result = calculate_item(_item("09"), b01, COMPANY, DATA)
        self.assertFalse(result.priced)
        self.assertIn("Anteil der Einzelkosten", result.note)

    def test_leistung_with_rates_is_priced(self):
        result = calculate_item(_item("09"), ERDBAU, COMPANY, DATA)
        self.assertTrue(result.priced)
        self.assertGreater(result.ep_mid, 0)


if __name__ == "__main__":
    unittest.main()
