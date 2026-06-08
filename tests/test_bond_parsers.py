from pathlib import Path

from pribilka.collectors.pl.bonds.obligacje_skarbowe import ObligacjeSkarboweParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_obligacje_skarbowe_parser_extracts_inline_html():
    html = (FIXTURES / "obligacje_skarbowe.html").read_text()
    records = ObligacjeSkarboweParser()._parse_html(html)

    assert len(records) == 4
    series = {r["bond_series"] for r in records}
    assert series == {"OTS", "ROR", "COI", "EDO"}

    ots = next(r for r in records if r["bond_series"] == "OTS")
    assert ots["coupon_rate"] == 2.0
    assert ots["is_government"] is True
    assert ots["external_id"] == "pl-gov-ots"

    edo = next(r for r in records if r["bond_series"] == "EDO")
    assert edo["coupon_rate"] == 5.35


def test_obligacje_skarbowe_parser_extracts_product_cards():
    """Live site splits rate and (symbol: XYZ) into separate HTML nodes."""
    html = (FIXTURES / "obligacje_skarbowe_live.html").read_text()
    records = ObligacjeSkarboweParser()._parse_html(html)

    assert len(records) == 4
    assert {r["bond_series"] for r in records} == {"OTS", "ROR", "EDO", "ROD"}
