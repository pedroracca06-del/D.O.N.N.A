import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from services import headlines


NY = ZoneInfo("America/New_York")


def test_forex_factory_feed_keeps_low_impact_and_all_day_context():
    payload = [
        {
            "title": "FOMC Member Hammack Speaks",
            "country": "USD",
            "date": "2026-10-14T12:10:00-04:00",
            "time": "12:10pm",
            "impact": "Low",
        },
        {
            "title": "IMF Meetings",
            "country": "All",
            "date": "Oct 12, 2026",
            "time": "All Day",
            "impact": "Holiday",
        },
    ]

    with patch.object(headlines, "_safe_get", return_value=payload), patch.object(
        headlines, "_now_ny", return_value=datetime(2026, 10, 14, 9, tzinfo=NY)
    ):
        events = headlines._fetch_ff_json_calendar()

    assert len(events) == 2
    speaker = next(event for event in events if event["title"] == "FOMC Member Hammack Speaks")
    meeting = next(event for event in events if event["title"] == "IMF Meetings")
    assert speaker["importance"] == "low"
    assert speaker["currency"] == "USD"
    assert speaker["time_et"] == "12:10"
    assert meeting["importance"] == "low"
    assert meeting["currency"] == "ALL"
    assert meeting["display_time"] == "All Day"
    assert meeting["time_et"] == ""
    assert not headlines._is_financial(speaker)


def test_red_folder_week_detects_cpi_ppi_and_retail_sales_in_schedule(tmp_path):
    macro_path = tmp_path / "macro.json"
    risk_path = tmp_path / "risk.json"
    macro_path.write_text(
        json.dumps(
            {
                "events": [
                    {"date": "2026-10-14", "title": "Core CPI m/m", "importance": "high"},
                    {"date": "2026-10-15", "title": "Core PPI m/m", "importance": "high"},
                    {"date": "2026-10-15", "title": "Retail Sales m/m", "importance": "high"},
                    {"date": "2026-10-16", "title": "FOMC Member Speaks", "importance": "low"},
                ]
            }
        ),
        encoding="utf-8",
    )
    risk_path.write_text("{}", encoding="utf-8")
    now = datetime(2026, 10, 14, 9, 0, tzinfo=NY)

    with patch.object(headlines, "MACRO_EVENTS_FILE", macro_path), patch.object(
        headlines, "RISK_STATE_FILE", risk_path
    ), patch.object(headlines, "_now_ny", return_value=now):
        assert headlines.is_red_folder_week() is True

    assert json.loads(risk_path.read_text(encoding="utf-8"))["red_folder_week"] is True



def test_calendar_bounds_match_sunday_through_saturday_around_midweek():
    wednesday = datetime(2026, 10, 14, 9, tzinfo=NY)
    with patch.object(headlines, "_now_ny", return_value=wednesday):
        assert headlines._calendar_bounds() == ("2026-10-11", "2026-10-17")


def test_calendar_bounds_roll_forward_on_saturday_and_sunday():
    saturday = datetime(2026, 10, 10, 9, tzinfo=NY)
    sunday = datetime(2026, 10, 11, 9, tzinfo=NY)
    with patch.object(headlines, "_now_ny", return_value=saturday):
        assert headlines._calendar_bounds() == ("2026-10-11", "2026-10-17")
    with patch.object(headlines, "_now_ny", return_value=sunday):
        assert headlines._calendar_bounds() == ("2026-10-11", "2026-10-17")



def test_cycle_persists_full_sunday_saturday_calendar_but_flags_weekday_risk(tmp_path):
    macro_path = tmp_path / "macro.json"
    risk_path = tmp_path / "risk.json"
    risk_path.write_text("{}", encoding="utf-8")
    now = datetime(2026, 10, 14, 9, 0, tzinfo=NY)
    feed = [
        {
            "date": "2026-10-11", "time_et": "", "display_time": "All Day",
            "title": "IMF Meetings", "importance": "low", "category": "macro", "currency": "ALL",
            "source": "ForexFactory",
        },
        {
            "date": "2026-10-14", "time_et": "08:30", "display_time": "08:30",
            "title": "Core CPI m/m", "importance": "high", "category": "inflation", "currency": "USD",
            "source": "ForexFactory",
        },
        {
            "date": "2026-10-17", "time_et": "", "display_time": "All Day",
            "title": "IMF Meetings", "importance": "low", "category": "macro", "currency": "ALL",
            "source": "ForexFactory",
        },
    ]

    from services import execution

    with patch.object(headlines, "MACRO_EVENTS_FILE", macro_path), patch.object(
        headlines, "RISK_STATE_FILE", risk_path
    ), patch.object(headlines, "_now_ny", return_value=now), patch.object(
        headlines, "_fetch_fmp_calendar", return_value=[]
    ), patch.object(
        headlines, "_fetch_ff_json_calendar", return_value=feed
    ), patch.object(headlines, "cache_delete"), patch.object(
        headlines._state, "set"
    ), patch.object(execution, "set_red_folder_lock"):
        headlines.process_headlines_cycle()

    saved = json.loads(macro_path.read_text(encoding="utf-8"))
    assert saved["calendar_start"] == "2026-10-11"
    assert saved["calendar_end"] == "2026-10-17"
    assert saved["data_status"] == "live"
    assert [event["date"] for event in saved["events"]] == [
        "2026-10-11", "2026-10-14", "2026-10-17"
    ]
    assert json.loads(risk_path.read_text(encoding="utf-8"))["red_folder_week"] is True


def test_provider_outage_preserves_calendar_risk_and_red_folder_lock(tmp_path):
    macro_path = tmp_path / "macro.json"
    risk_path = tmp_path / "risk.json"
    previous_calendar = {
        "source": "ForexFactory",
        "fetched_at": "2026-10-13T12:00:00+00:00",
        "week_start": "2026-10-12",
        "week_end": "2026-10-16",
        "calendar_start": "2026-10-11",
        "calendar_end": "2026-10-17",
        "events": [{"date": "2026-10-14", "title": "Core CPI m/m", "importance": "high"}],
    }
    previous_risk = {
        "macro_risk": "medium",
        "red_folder_week": True,
        "next_event": "Core CPI m/m",
        "minutes_to_event": 45,
        "red_folder_lock": True,
    }
    macro_path.write_text(json.dumps(previous_calendar), encoding="utf-8")
    risk_path.write_text(json.dumps(previous_risk), encoding="utf-8")
    now = datetime(2026, 10, 14, 9, 0, tzinfo=NY)

    from services import execution

    with patch.object(headlines, "MACRO_EVENTS_FILE", macro_path), patch.object(
        headlines, "RISK_STATE_FILE", risk_path
    ), patch.object(headlines, "_now_ny", return_value=now), patch.object(
        headlines, "_fetch_fmp_calendar", return_value=[]
    ), patch.object(
        headlines, "_fetch_ff_json_calendar", return_value=[]
    ), patch.object(headlines, "cache_delete") as cache_delete, patch.object(
        headlines._state, "set"
    ) as state_set, patch.object(
        execution, "set_red_folder_lock"
    ) as set_lock:
        headlines.process_headlines_cycle()

    assert json.loads(macro_path.read_text(encoding="utf-8")) == previous_calendar
    assert json.loads(risk_path.read_text(encoding="utf-8")) == previous_risk
    cache_delete.assert_not_called()
    state_set.assert_not_called()
    set_lock.assert_not_called()


def test_speaker_classifier_flags_trump_and_fed_without_execution_governance():
    trump = headlines._classify_speaker_event("President Trump Speaks")
    fed = headlines._classify_speaker_event("FOMC Member Hammack Speaks")
    ordinary = headlines._classify_speaker_event("Initial Jobless Claims")

    assert trump == {
        "event_type": "speaker",
        "speaker_alert": True,
        "speaker_kind": "political",
        "speaker_name": "President Trump",
    }
    assert fed["event_type"] == "speaker"
    assert fed["speaker_alert"] is True
    assert fed["speaker_kind"] == "fed"
    assert "Hammack" in fed["speaker_name"]
    assert ordinary["speaker_alert"] is False
    assert not headlines._is_financial({
        "title": "FOMC Member Hammack Speaks",
        "importance": "low",
        **fed,
    })


def test_forex_factory_parser_attaches_speaker_alert_metadata():
    payload = [
        {
            "title": "President Trump Speaks",
            "country": "USD",
            "date": "2026-10-14T12:10:00-04:00",
            "time": "12:10pm",
            "impact": "Low",
        }
    ]
    with patch.object(
        headlines, "_safe_get", return_value=payload
    ), patch.object(
        headlines, "_now_ny", return_value=datetime(2026, 10, 14, 9, tzinfo=NY)
    ):
        events = headlines._fetch_ff_json_calendar()

    assert events[0]["speaker_alert"] is True
    assert events[0]["speaker_kind"] == "political"
    assert events[0]["display_time"] == "12:10"
