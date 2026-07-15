from pribilka.collectors.macro_collector import (
    parse_eurostat_hicp_json,
    parse_nbp_reference_rates_xml,
)


def test_parse_nbp_nested_stopa_layout():
    xml = """<?xml version="1.0" encoding="ISO-8859-2"?>
    <archiwum>
      <pozycja obowiazuje_od="2024-10-17">
        <stopa id="ref" nazwa="Referencyjna" oprocentowanie="5.75"/>
        <stopa id="lom" nazwa="Lombardowa" oprocentowanie="6.25"/>
      </pozycja>
      <pozycja obowiazuje_od="2025-05-08">
        <stopa id="ref" oprocentowanie="5.25"/>
      </pozycja>
    </archiwum>
    """
    rows = parse_nbp_reference_rates_xml(xml)
    assert len(rows) == 2
    assert rows[0]["as_of_date"].isoformat() == "2024-10-17"
    assert rows[0]["value"] == 5.75
    assert rows[1]["value"] == 5.25
    assert rows[1]["kind"].value == "nbp_reference_rate"


def test_parse_nbp_compact_attribute_layout():
    xml = """
    <table>
      <pozycja obowiazuje_od="2023-09-07" ref="6.00" lombard="6.50"/>
    </table>
    """
    rows = parse_nbp_reference_rates_xml(xml)
    assert len(rows) == 1
    assert rows[0]["value"] == 6.0


def test_parse_eurostat_hicp_json():
    payload = {
        "value": {"0": 3.8, "1": 4.1, "2": 3.9},
        "dimension": {
            "time": {
                "category": {
                    "index": {"2025-01": 0, "2025-02": 1, "2025-03": 2},
                }
            }
        },
    }
    rows = parse_eurostat_hicp_json(payload)
    assert len(rows) == 3
    assert rows[0]["as_of_date"].isoformat() == "2025-01-31"
    assert rows[0]["value"] == 3.8
    assert rows[2]["as_of_date"].isoformat() == "2025-03-31"
    assert rows[2]["kind"].value == "cpi_yoy"
