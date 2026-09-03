"""Regression checks for the approved News and Journal density layout."""

from ui.styles import DASHBOARD_CSS


def test_journal_period_layout_uses_full_three_column_row():
    assert "grid-template-columns:minmax(0,1.65fr) minmax(280px,.675fr) minmax(280px,.675fr)" in DASHBOARD_CSS
    assert ".jn-dashboard-side{display:contents}" in DASHBOARD_CSS
    assert ".jn-dashboard-side>section:first-child{grid-column:2}" in DASHBOARD_CSS
    assert ".jn-dashboard-side>section:last-child{grid-column:3}" in DASHBOARD_CSS
    assert ".jn-calendar-panel{grid-column:1;display:flex;flex-direction:column" in DASHBOARD_CSS
    assert "grid-auto-rows:minmax(86px,1fr);flex:1" in DASHBOARD_CSS


def test_news_driver_cards_fill_their_column_without_mobile_regression():
    assert ".mk-news-lower>.mk-news-section:first-child{display:grid;grid-template-rows:auto minmax(0,1fr) auto minmax(0,1fr);align-items:stretch}" in DASHBOARD_CSS
    assert ".mk-news-lower>.mk-news-section:first-child .mk-driver-box{height:calc(100% - 10px)}" in DASHBOARD_CSS
    assert ".mk-news-lower>.mk-news-section:first-child{display:block}" in DASHBOARD_CSS
    assert ".mk-news-lower>.mk-news-section:first-child .mk-driver-box{height:auto}" in DASHBOARD_CSS
