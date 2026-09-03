"""Regression checks for the approved News and Journal density layout."""

from ui.styles import DASHBOARD_CSS
from ui.scripts import DASHBOARD_SCRIPT


def test_journal_period_layout_uses_full_width_calendar_and_level_analytics():
    assert "grid-template-columns:minmax(0,1.65fr) minmax(360px,.95fr)" in DASHBOARD_CSS
    assert ".jn-calendar-panel{grid-column:1/3;display:flex;flex-direction:column" in DASHBOARD_CSS
    assert ".jn-dashboard-side{grid-column:1/3;display:grid;grid-template-columns:1fr 1fr" in DASHBOARD_CSS
    assert ".jn-dashboard-side>.jn-dash-panel{height:100%}" in DASHBOARD_CSS
    assert "grid-auto-rows:minmax(86px,1fr);flex:1" in DASHBOARD_CSS
    assert ".jn-cal-day.outside" in DASHBOARD_CSS
    assert "while (calDays.length < 42)" in DASHBOARD_SCRIPT
    assert "prevCount - leading + i + 1" in DASHBOARD_SCRIPT


def test_news_driver_cards_fill_their_column_without_mobile_regression():
    assert ".mk-news-lower>.mk-news-section:first-child{display:grid;grid-template-rows:auto minmax(0,1fr) auto minmax(0,1fr);align-items:stretch}" in DASHBOARD_CSS
    assert ".mk-news-lower>.mk-news-section:first-child .mk-driver-box{height:calc(100% - 10px)}" in DASHBOARD_CSS
    assert ".mk-news-lower>.mk-news-section:first-child{display:block}" in DASHBOARD_CSS
    assert ".mk-news-lower>.mk-news-section:first-child .mk-driver-box{height:auto}" in DASHBOARD_CSS
