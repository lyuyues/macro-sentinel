import json
import os
import numpy as np
import pytest
from quant.screener import discover_tickers, load_ticker_summary, filter_universe


def _make_meta(tmp_path, ticker, fair_value, sector="CONSUMER", currency="USD"):
    """Helper: create a minimal meta.json for a fake ticker."""
    ticker_dir = tmp_path / ticker
    ticker_dir.mkdir(exist_ok=True)
    meta = {
        "Sector": sector,
        "Fair Value / Share ": str(fair_value),
        "Currency": currency,
    }
    (ticker_dir / f"2026_dcf_{ticker}_meta.json").write_text(json.dumps(meta))
    return ticker_dir


class TestDiscoverTickers:
    def test_finds_tickers_with_meta(self, tmp_path):
        _make_meta(tmp_path, "AAA", "100.0")
        _make_meta(tmp_path, "BBB", "50.0")
        # Directory with no meta.json should be skipped
        (tmp_path / "CCC").mkdir()
        result = discover_tickers(str(tmp_path))
        assert result == ["AAA", "BBB"]

    def test_empty_dir(self, tmp_path):
        assert discover_tickers(str(tmp_path)) == []

    def test_nonexistent_dir(self):
        assert discover_tickers("/nonexistent/path") == []


class TestLoadTickerSummary:
    def test_loads_summary(self, tmp_path):
        _make_meta(tmp_path, "AAPL", "172.90", sector="CONSUMER", currency="USD")
        s = load_ticker_summary("AAPL", str(tmp_path))
        assert s["sector"] == "CONSUMER"
        assert s["fair_value"] == pytest.approx(172.90)
        assert s["currency"] == "USD"

    def test_negative_fair_value(self, tmp_path):
        _make_meta(tmp_path, "BAD", "-6.19")
        s = load_ticker_summary("BAD", str(tmp_path))
        assert s["fair_value"] == pytest.approx(-6.19)

    def test_missing_ticker(self, tmp_path):
        s = load_ticker_summary("MISSING", str(tmp_path))
        assert np.isnan(s["fair_value"])
        assert s["sector"] is None


class TestFilterUniverse:
    def test_filters_negative_fv(self, tmp_path):
        _make_meta(tmp_path, "GOOD", "100.0")
        _make_meta(tmp_path, "BAD", "-5.0")
        result = filter_universe(str(tmp_path))
        assert "GOOD" in result["qualified"]
        assert "BAD" in result["rejected"]
        assert "fair_value" in result["rejected"]["BAD"]

    def test_filters_bank_sector(self, tmp_path):
        _make_meta(tmp_path, "BANK1", "50.0", sector="BANK")
        _make_meta(tmp_path, "INS1", "80.0", sector="INSURANCE")
        _make_meta(tmp_path, "TECH1", "120.0", sector="TECH")
        result = filter_universe(str(tmp_path))
        assert "TECH1" in result["qualified"]
        assert "BANK1" in result["rejected"]
        assert "INS1" in result["rejected"]

    def test_filters_nan_fv(self, tmp_path):
        ticker_dir = tmp_path / "NANFV"
        ticker_dir.mkdir()
        meta = {"Sector": "TECH", "Fair Value / Share ": "N/A", "Currency": "USD"}
        (ticker_dir / "2026_dcf_NANFV_meta.json").write_text(json.dumps(meta))
        result = filter_universe(str(tmp_path))
        assert "NANFV" in result["rejected"]

    def test_filters_non_usd(self, tmp_path):
        _make_meta(tmp_path, "RUB1", "50.0", currency="RUB")
        result = filter_universe(str(tmp_path))
        assert "RUB1" in result["rejected"]
        assert "currency" in result["rejected"]["RUB1"]

    def test_require_usd_false(self, tmp_path):
        _make_meta(tmp_path, "RUB1", "50.0", currency="RUB")
        result = filter_universe(str(tmp_path), require_usd=False)
        assert "RUB1" in result["qualified"]

    def test_integration_real_output(self):
        """Test against real output/ directory if it exists."""
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "output"
        )
        if not os.path.isdir(output_dir):
            pytest.skip("No output/ directory")

        tickers = discover_tickers(output_dir)
        assert len(tickers) > 0

        result = filter_universe(output_dir)
        # AAPL should always qualify
        assert "AAPL" in result["qualified"]
        # NBIS has negative FV and non-USD currency
        if "NBIS" in result["rejected"]:
            assert result["rejected"]["NBIS"]  # has a reason
        # IREN has negative FV
        if "IREN" in result["rejected"]:
            assert "fair_value" in result["rejected"]["IREN"]
