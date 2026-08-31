from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.state import journal_record_origin
from services import headlines
from engines import engines


NY = ZoneInfo('America/New_York')


def test_weekend_calendar_rolls_to_coming_trading_week():
    sunday = datetime(2026, 8, 30, 12, tzinfo=NY)
    with patch.object(headlines, '_now_ny', return_value=sunday):
        assert headlines._week_bounds() == ('2026-08-31', '2026-09-04')


def test_weekday_calendar_keeps_current_trading_week():
    friday = datetime(2026, 8, 28, 12, tzinfo=NY)
    with patch.object(headlines, '_now_ny', return_value=friday):
        assert headlines._week_bounds() == ('2026-08-24', '2026-08-28')


def test_journal_provenance_requires_strong_legacy_marker():
    assert journal_record_origin({'notes': 'EOD forced close @ 716.35'}) == 'legacy_system'
    assert journal_record_origin({'notes': 'NOVA autonomous trade. ORB failure.'}) == 'legacy_system'
    assert journal_record_origin({'notes': 'Closed via NOVA_EXECUTION_TAB (reason=MANUAL)'}) == 'legacy_system'
    assert journal_record_origin({'notes': 'My manual EOD close after Powell spoke'}) == 'personal'
    assert journal_record_origin({'notes': ''}) == 'personal'


def test_live_news_carries_deterministic_impact_and_category():
    sample = [
        {'headline': 'Powell signals rates may stay higher', 'source': 'Reuters', 'url': 'https://example.test/fed'},
        {'headline': 'Missile attack lifts oil prices', 'source': 'Reuters', 'url': 'https://example.test/oil'},
        {'headline': 'Stocks finish mixed', 'source': 'Reuters', 'url': 'https://example.test/stocks'},
    ]
    with patch.object(engines, 'cache_get', return_value=None), \
         patch.object(engines, 'cache_set'), \
         patch.object(engines, 'fetch_finnhub_market_news', return_value=sample):
        rows = engines.get_live_news()
    assert [(r['severity'], r['category']) for r in rows] == [
        ('high', 'Fed & rates'),
        ('high', 'Geopolitics'),
        ('low', 'Markets'),
    ]
