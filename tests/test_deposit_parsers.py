from pathlib import Path
from unittest.mock import patch

from pribilka.collectors.deposit_collector import PolandDepositCollector
from pribilka.collectors.pl.deposits.bankier import BankierDepositParser
from pribilka.collectors.pl.deposits.ing import IngDepositParser
from pribilka.collectors.pl.deposits.mbank import MBankDepositParser
from pribilka.collectors.pl.deposits.pko import PkoDepositParser
from pribilka.collectors.pl.deposits.santander import SantanderDepositParser
from pribilka.collectors.pl.deposits.velobank import VeloBankDepositParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_ing_parser_extracts_pln_deposits():
    html = (FIXTURES / "ing_lokata.html").read_text()
    offers = IngDepositParser()._parse_pln_deposits(html)

    assert len(offers) == 5
    assert any(o.term_months == 3 and o.annual_interest_rate == 1.0 for o in offers)
    assert any(
        o.product_name == "Lokata terminowa 6M" and o.annual_interest_rate == 1.5 for o in offers
    )
    assert any(
        o.product_name == "Lokata terminowa Plus 6M" and o.annual_interest_rate == 3.25
        for o in offers
    )


def test_ing_parser_extracts_rates_pdf():
    pdf_text = (FIXTURES / "ing_rates_pdf.txt").read_text()
    offers = IngDepositParser()._parse_rates_pdf(pdf_text.encode("cp1250"))

    assert len(offers) == 5
    assert any(o.term_months == 12 and o.annual_interest_rate == 2.0 for o in offers)
    assert any(o.product_name == "Lokata terminowa Plus 12M" for o in offers)


def test_ing_parser_extracts_rates_pdf_2026_layout():
    pdf_text = (FIXTURES / "ing_rates_pdf_2026.txt").read_text()
    offers = IngDepositParser()._parse_rates_pdf(pdf_text.encode("utf-8"))

    assert len(offers) == 5
    assert any(o.term_months == 3 and o.annual_interest_rate == 1.0 for o in offers)
    assert any(
        o.product_name == "Lokata terminowa Plus 6M" and o.annual_interest_rate == 3.25
        for o in offers
    )


def test_ing_parser_extracts_rates_table():
    html = (FIXTURES / "ing_rates_table.html").read_text()
    offers = IngDepositParser()._parse_rates_table(html)

    assert len(offers) == 5
    assert any(o.term_months == 6 and o.annual_interest_rate == 1.5 for o in offers)


def test_bankier_parser_extracts_offer_cards():
    html = (FIXTURES / "bankier_lokaty.html").read_text()
    offers = BankierDepositParser()._parse_offer_cards(html)

    assert len(offers) == 2
    assert any(
        o.institution_name == "VeloBank"
        and o.term_months == 6
        and o.annual_interest_rate == 6.0
        for o in offers
    )
    assert any(o.term_months == 1 and o.annual_interest_rate == 5.5 for o in offers)


def test_pko_parser_extracts_term_deposits():
    html = (FIXTURES / "pko_lokata.html").read_text()
    offers = PkoDepositParser()._parse_standard_lokata(html)

    assert len(offers) == 3
    assert any(o.annual_interest_rate == 1.75 and o.term_months == 6 for o in offers)


def test_santander_parser():
    html = (FIXTURES / "santander_lokata.html").read_text()
    offers = SantanderDepositParser()._parse_html(html)
    assert len(offers) == 3
    assert any(o.term_months == 12 and o.annual_interest_rate == 1.5 for o in offers)


def test_velobank_parser():
    html = (FIXTURES / "velobank_lokata.html").read_text()
    offers = VeloBankDepositParser()._parse_nowe_srodki(html)
    assert len(offers) == 3
    assert any(o.term_months == 6 and o.annual_interest_rate == 3.4 for o in offers)


def test_mbank_promo_parser():
    html = """
    <html><body>
    <h1>lokata na nowe środki</h1>
    <div>3,40% w skali roku</div>
    <div>3,20% w skali roku</div>
    </body></html>
    """
    offers = MBankDepositParser()._parse_promo_html(html)
    assert len(offers) == 2
    assert max(o.annual_interest_rate for o in offers) == 3.4


@patch("pribilka.collectors.deposit_collector.report_deposit_parse_results")
@patch("pribilka.collectors.pl.deposits.bankier.fetch_text")
@patch("pribilka.collectors.pl.deposits.velobank.fetch_text")
@patch("pribilka.collectors.pl.deposits.santander.fetch_text")
@patch("pribilka.collectors.pl.deposits.pko.fetch_text")
@patch("pribilka.collectors.pl.deposits.ing.fetch_text")
@patch("pribilka.collectors.pl.deposits.mbank.fetch_text")
def test_poland_collector_aggregates_parsers(
    mock_mbank, mock_ing, mock_pko, mock_santander, mock_velo, mock_bankier, _mock_alerts
):
    mock_pko.side_effect = [
        (FIXTURES / "pko_lokata.html").read_text(),
        "",  # promo page — skip
    ]
    mock_ing.return_value = (FIXTURES / "ing_lokata.html").read_text()
    mock_mbank.side_effect = [
        Exception("skip promo"),
        Exception("skip fund"),
        Exception("skip overview"),
    ]
    mock_santander.return_value = (FIXTURES / "santander_lokata.html").read_text()
    mock_velo.side_effect = [
        (FIXTURES / "velobank_lokata.html").read_text(),
        Exception("skip velolokata"),
    ]
    mock_bankier.return_value = "<html></html>"

    records = PolandDepositCollector().collect()

    assert len(records) >= 9
    institutions = {r["institution_name"] for r in records}
    assert "PKO Bank Polski" in institutions
    assert "ING Bank Śląski" in institutions
