from fastapi.testclient import TestClient

import main
from ui.scripts import DASHBOARD_SCRIPT
from ui.styles import DASHBOARD_CSS


def test_reset_endpoint_clears_every_trade_population(monkeypatch):
    trades = [
        {'ticker': 'NQ', 'trade_mode': 'LIVE', 'realized_pnl': 500},
        {'ticker': 'MNQ', 'trade_mode': 'PAPER', 'realized_pnl': -100},
        {'ticker': 'NQ', 'origin': 'legacy_system', 'realized_pnl': 25},
    ]
    saved = []
    monkeypatch.setattr(main, 'load_journal', lambda: trades)
    monkeypatch.setattr(main, 'save_journal', lambda value: saved.append(value))

    response = TestClient(main.app).post('/journal/reset', json={
        'confirmation': 'RESET_ALL_TRADES',
    })

    assert response.status_code == 200
    assert response.json()['removed'] == 3
    assert response.json()['stats']['total'] == 0
    assert saved == [[]]


def test_reset_endpoint_requires_exact_confirmation_without_writing(monkeypatch):
    saved = []
    monkeypatch.setattr(main, 'save_journal', lambda value: saved.append(value))

    response = TestClient(main.app).post('/journal/reset', json={'confirmation': 'RESET'})

    assert response.status_code == 400
    assert saved == []


def test_dashboard_exposes_guarded_all_history_reset():
    assert 'Reset all trades' in DASHBOARD_SCRIPT
    assert "prompt('Final confirmation: type RESET" in DASHBOARD_SCRIPT
    assert "fetch('/journal/reset'" in DASHBOARD_SCRIPT
    assert "confirmation:'RESET_ALL_TRADES'" in DASHBOARD_SCRIPT
    assert '.jn-reset-trades{' in DASHBOARD_CSS
