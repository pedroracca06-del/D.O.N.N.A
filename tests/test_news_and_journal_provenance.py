from datetime import datetime
import json
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


def test_calendar_cycle_retains_last_good_current_week_on_provider_dropout(tmp_path):
    macro_path = tmp_path / 'macro.json'
    risk_path = tmp_path / 'risk.json'
    existing = {
        'source': 'ForexFactory',
        'fetched_at': '2026-09-01T12:00:00+00:00',
        'week_start': '2026-08-31',
        'week_end': '2026-09-04',
        'events': [{
            'date': '2026-09-01', 'time_et': '10:00',
            'title': 'ISM Manufacturing PMI', 'importance': 'high',
            'category': 'macro',
        }],
    }
    macro_path.write_text(json.dumps(existing), encoding='utf-8')
    risk_path.write_text('{}', encoding='utf-8')
    before = macro_path.read_bytes()
    now = datetime(2026, 9, 1, 9, 0, tzinfo=NY)

    with patch.object(headlines, 'MACRO_EVENTS_FILE', macro_path), \
         patch.object(headlines, 'RISK_STATE_FILE', risk_path), \
         patch.object(headlines, '_now_ny', return_value=now), \
         patch.object(headlines, '_fetch_fmp_calendar', return_value=[]), \
         patch.object(headlines, '_fetch_ff_json_calendar', return_value=[]), \
         patch.object(headlines, 'cache_delete') as delete_cache:
        headlines.process_headlines_cycle()

    assert macro_path.read_bytes() == before
    delete_cache.assert_not_called()
    risk = json.loads(risk_path.read_text(encoding='utf-8'))
    assert risk['next_event'] == 'ISM Manufacturing PMI'


def test_calendar_cycle_replaces_payload_and_invalidates_cache_on_recovery(tmp_path):
    macro_path = tmp_path / 'macro.json'
    risk_path = tmp_path / 'risk.json'
    macro_path.write_text(json.dumps({
        'source': 'none', 'week_start': '2026-08-31',
        'week_end': '2026-09-04', 'events': [],
    }), encoding='utf-8')
    risk_path.write_text('{}', encoding='utf-8')
    now = datetime(2026, 9, 1, 9, 0, tzinfo=NY)
    recovered = [{
        'date': '2026-09-01', 'time_et': '10:00',
        'title': 'ISM Manufacturing PMI', 'importance': 'high',
        'category': 'growth', 'currency': 'USD', 'source': 'ForexFactory',
    }]

    with patch.object(headlines, 'MACRO_EVENTS_FILE', macro_path), \
         patch.object(headlines, 'RISK_STATE_FILE', risk_path), \
         patch.object(headlines, '_now_ny', return_value=now), \
         patch.object(headlines, '_fetch_fmp_calendar', return_value=[]), \
         patch.object(headlines, '_fetch_ff_json_calendar', return_value=recovered), \
         patch.object(headlines, 'cache_delete') as delete_cache:
        headlines.process_headlines_cycle()

    saved = json.loads(macro_path.read_text(encoding='utf-8'))
    assert saved['events'] == recovered
    assert saved['source'] == 'ForexFactory'
    delete_cache.assert_called_once_with('calendar')


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
        ('high', 'Geopolitics'),
        ('high', 'Fed & rates'),
        ('low', 'Markets'),
    ]


def test_live_news_rejects_non_market_publisher_traffic_and_keeps_timestamp():
    sample = [
        {'headline': 'Family shares a heartwarming travel story', 'source': 'CNBC', 'datetime': 100},
        {'headline': 'Iran missile attack lifts oil and rattles stock futures',
         'source': 'Reuters', 'datetime': 200, 'url': 'https://example.test/iran'},
    ]
    with patch.object(engines, 'cache_get', return_value=None), \
         patch.object(engines, 'cache_set'), \
         patch.object(engines, 'fetch_finnhub_market_news', return_value=sample):
        rows = engines.get_live_news()
    assert len(rows) == 1
    assert rows[0]['category'] == 'Geopolitics'
    assert rows[0]['published_at'] == 200
    assert rows[0]['market_score'] > 0
