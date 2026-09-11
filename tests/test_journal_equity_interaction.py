from ui.scripts import DASHBOARD_SCRIPT
from ui.styles import DASHBOARD_CSS


def test_equity_curve_exposes_hover_and_keyboard_details():
    assert 'function _jnBindEquityInteraction(host, points)' in DASHBOARD_SCRIPT
    assert "svg.addEventListener('pointermove'" in DASHBOARD_SCRIPT
    assert "dot.addEventListener('focus'" in DASHBOARD_SCRIPT
    assert 'data-eq-session' in DASHBOARD_SCRIPT
    assert 'data-eq-cumulative' in DASHBOARD_SCRIPT
    assert 'data-eq-trades' in DASHBOARD_SCRIPT
    assert 'tabindex="0" role="button"' in DASHBOARD_SCRIPT


def test_equity_tooltip_and_crosshair_have_visible_styles():
    assert '.jn-eq-guide{' in DASHBOARD_CSS
    assert '.jn-eq-tooltip{' in DASHBOARD_CSS
    assert '.jn-eq-dot.is-active{' in DASHBOARD_CSS
