from unittest.mock import MagicMock, patch

from pribilka.collectors.pl.deposits.parse_result import ParseStatus, ParserResult
from pribilka.services.collector_alerts import report_deposit_parse_results


@patch("pribilka.services.collector_alerts.get_redis")
@patch("pribilka.services.collector_alerts._send_telegram")
def test_alert_sent_on_parser_error(mock_telegram, mock_get_redis):
    mock_get_redis.return_value = MagicMock(get=MagicMock(return_value=None))
    mock_telegram.return_value = True

    results = [
        ParserResult(
            offers=[],
            parser_name="IngDepositParser",
            institution_name="ING Bank Śląski",
            status=ParseStatus.ERROR,
            error_message="HTTP 503",
        )
    ]

    report_deposit_parse_results(results, total_records=0)

    mock_telegram.assert_called_once()
    assert "ING Bank Śląski" in mock_telegram.call_args[0][0]


@patch("pribilka.services.collector_alerts.get_redis")
@patch("pribilka.services.collector_alerts._send_telegram")
def test_alert_suppressed_by_cooldown(mock_telegram, mock_get_redis):
    mock_get_redis.return_value = MagicMock(get=MagicMock(return_value="1"))

    results = [
        ParserResult(
            offers=[],
            parser_name="PkoDepositParser",
            institution_name="PKO Bank Polski",
            status=ParseStatus.EMPTY,
        )
    ]

    report_deposit_parse_results(results, total_records=0)

    mock_telegram.assert_not_called()


@patch("pribilka.services.collector_alerts.get_redis")
@patch("pribilka.services.collector_alerts._send_telegram")
def test_no_alert_for_supplementary_empty_parser(mock_telegram, mock_get_redis):
    mock_get_redis.return_value = MagicMock(get=MagicMock(return_value=None))

    results = [
        ParserResult(
            offers=[],
            parser_name="BankierDepositParser",
            institution_name="Bankier.pl (ranking)",
            status=ParseStatus.EMPTY,
            alert_on_empty=False,
        ),
        ParserResult(
            offers=[object()],
            parser_name="PkoDepositParser",
            institution_name="PKO Bank Polski",
            status=ParseStatus.OK,
        ),
    ]

    report_deposit_parse_results(results, total_records=3)

    mock_telegram.assert_not_called()


@patch("pribilka.services.collector_alerts.get_redis")
@patch("pribilka.services.collector_alerts._send_telegram")
def test_no_alert_when_all_ok(mock_telegram, mock_get_redis):
    mock_get_redis.return_value = MagicMock(get=MagicMock(return_value=None))

    results = [
        ParserResult(
            offers=[],
            parser_name="IngDepositParser",
            institution_name="ING",
            status=ParseStatus.OK,
        )
    ]

    report_deposit_parse_results(results, total_records=5)

    mock_telegram.assert_not_called()
