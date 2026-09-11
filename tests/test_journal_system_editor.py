from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from ui.pages.journal import JOURNAL_HTML
from ui.scripts import DASHBOARD_SCRIPT
from ui.styles import DASHBOARD_CSS


VALID = {
    'approved_models': ['OTE', 'ORB', 'POWELL_10AM'],
    'max_trades_per_day': 2,
    'daily_risk_pct': 1,
    'max_losses_per_day': 2,
    'live_sessions': ['NY_AM', 'NY_PM'],
    'prime_steps': ['Position', 'Relevant Level', 'Interaction', 'Market Confirmation', 'Execution'],
}


def test_system_editor_is_available_in_the_existing_card():
    assert 'id="jSystemEditBtn"' in JOURNAL_HTML
    assert 'Edit rules' in JOURNAL_HTML
    assert 'function editJournalSystem()' in DASHBOARD_SCRIPT
    assert "fetch('/journal/workspace/'+'system'" in DASHBOARD_SCRIPT
    assert '.jn-system-form{' in DASHBOARD_CSS


def test_system_update_validates_and_persists_all_fields():
    stored = {'plans': [], 'reflections': [], 'studies': [], 'goals': [], 'system': dict(VALID)}
    with patch.object(main, 'load_journal_workspace', return_value=stored), \
         patch.object(main, 'save_journal_workspace') as save:
        response = TestClient(main.app).post('/journal/workspace/system', json=VALID)
    assert response.status_code == 200
    assert response.json()['system']['approved_models'] == ['OTE', 'ORB', 'POWELL_10AM']
    save.assert_called_once()


def test_system_update_rejects_invalid_risk_without_writing():
    invalid = {**VALID, 'daily_risk_pct': 99}
    with patch.object(main, 'save_journal_workspace') as save:
        response = TestClient(main.app).post('/journal/workspace/system', json=invalid)
    assert response.status_code == 400
    assert 'Daily risk' in response.json()['detail']
    save.assert_not_called()


def test_system_update_rejects_unfunded_asia_session():
    invalid = {**VALID, 'live_sessions': ['NY_AM', 'ASIA']}
    with patch.object(main, 'save_journal_workspace') as save:
        response = TestClient(main.app).post('/journal/workspace/system', json=invalid)
    assert response.status_code == 400
    assert 'NY_AM or NY_PM' in response.json()['detail']
    save.assert_not_called()


def test_system_update_rejects_fractional_limits_and_non_finite_risk():
    client = TestClient(main.app)
    with patch.object(main, 'save_journal_workspace') as save:
        fractional = client.post('/journal/workspace/system', json={**VALID, 'max_trades_per_day': 2.5})
        non_finite = client.post('/journal/workspace/system', content='''{
          "approved_models":["OTE"],"max_trades_per_day":2,"daily_risk_pct":NaN,
          "max_losses_per_day":2,"live_sessions":["NY_AM"],"prime_steps":["Execution"]
        }''', headers={'content-type': 'application/json'})
    assert fractional.status_code == 400
    assert non_finite.status_code == 400
    save.assert_not_called()
