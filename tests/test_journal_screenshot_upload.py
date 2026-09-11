import base64

from fastapi.testclient import TestClient

import main


def test_journal_screenshot_upload_attaches_to_exact_trade(monkeypatch, tmp_path):
    trades = [
        {'ticker': 'MNQ', 'outcome': 'WIN', 'realized_pnl': 25},
        {'ticker': 'MES', 'outcome': 'LOSS', 'realized_pnl': -10},
    ]
    saved = {}

    monkeypatch.setattr(main, 'load_journal', lambda: trades)
    monkeypatch.setattr(main, 'save_journal', lambda value: saved.setdefault('trades', value))
    monkeypatch.setattr(main, '__file__', str(tmp_path / 'main.py'))

    png = b'\x89PNG\r\n\x1a\nNOVA'
    response = TestClient(main.app).post('/journal/screenshot/upload', json={
        'index': 1,
        'filename': 'chart.png',
        'mime_type': 'image/png',
        'data_base64': base64.b64encode(png).decode('ascii'),
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['index'] == 1
    assert 'chart_snapshot' not in saved['trades'][0]
    assert saved['trades'][1]['chart_snapshot'] == payload['url']
    filename = saved['trades'][1]['screenshot_filename']
    assert filename.startswith('journal_') and filename.endswith('.png')
    assert (tmp_path / 'mcp' / 'tradingview' / 'screenshots' / filename).read_bytes() == png


def test_journal_screenshot_upload_rejects_mismatched_contents(monkeypatch):
    monkeypatch.setattr(main, 'load_journal', lambda: [{'ticker': 'MNQ'}])
    response = TestClient(main.app).post('/journal/screenshot/upload', json={
        'index': 0,
        'filename': 'not-really-a-chart.png',
        'mime_type': 'image/png',
        'data_base64': base64.b64encode(b'not an image').decode('ascii'),
    })
    assert response.status_code == 400
    assert 'do not match' in response.json()['detail']


def test_journal_add_returns_index_for_followup_attachment(monkeypatch):
    trades = []
    monkeypatch.setattr(main, 'load_journal', lambda: trades)
    monkeypatch.setattr(main, 'save_journal', lambda value: None)
    monkeypatch.setattr(main, 'load_risk_state', lambda: {})
    monkeypatch.setattr(main, 'build_harvey_payload', lambda: {})
    monkeypatch.setattr(main, 'compute_journal_stats', lambda value: {'total': len(value)})

    response = TestClient(main.app).post('/journal/add', json={
        'ticker': 'MNQ', 'direction': 'LONG', 'outcome': 'WIN', 'realized_pnl': 50,
    })
    assert response.status_code == 200
    assert response.json()['index'] == 0
    assert trades[0]['trade_mode'] == 'LIVE'


def test_journal_add_stores_paper_studies_separately(monkeypatch):
    trades = []
    monkeypatch.setattr(main, 'load_journal', lambda: trades)
    monkeypatch.setattr(main, 'save_journal', lambda value: None)
    monkeypatch.setattr(main, 'load_risk_state', lambda: {})
    monkeypatch.setattr(main, 'build_harvey_payload', lambda: {})
    monkeypatch.setattr(main, 'compute_journal_stats', lambda value: {'total': len(value)})

    response = TestClient(main.app).post('/journal/add', json={
        'ticker': 'MNQ', 'direction': 'LONG', 'outcome': 'LOSS',
        'realized_pnl': 25, 'trade_mode': 'PAPER',
    })
    assert response.status_code == 200
    assert trades[0]['trade_mode'] == 'PAPER'
    assert trades[0]['realized_pnl'] == -25


def test_journal_add_rejects_unknown_trade_mode(monkeypatch):
    monkeypatch.setattr(main, 'load_journal', lambda: [])
    response = TestClient(main.app).post('/journal/add', json={
        'ticker': 'MNQ', 'direction': 'LONG', 'outcome': 'WIN',
        'realized_pnl': 50, 'trade_mode': 'SIM-ish',
    })
    assert response.status_code == 400
    assert response.json()['detail'] == 'trade_mode must be LIVE or PAPER'


def test_journal_delete_removes_the_exact_selected_record(monkeypatch):
    trades = [
        {'ticker': 'MNQ', 'trade_mode': 'LIVE', 'realized_pnl': 100},
        {'ticker': 'NQ', 'trade_mode': 'PAPER', 'realized_pnl': -25},
    ]
    saved = {}
    monkeypatch.setattr(main, 'load_journal', lambda: trades)
    monkeypatch.setattr(main, 'save_journal', lambda value: saved.setdefault('trades', list(value)))
    monkeypatch.setattr(main, 'compute_journal_stats', lambda value: {'total': len(value)})

    response = TestClient(main.app).post('/journal/delete', json={'index': 1})

    assert response.status_code == 200
    assert response.json()['stats']['total'] == 1
    assert saved['trades'] == [{'ticker': 'MNQ', 'trade_mode': 'LIVE', 'realized_pnl': 100}]


def _workspace():
    return {
        'plans': [], 'reflections': [], 'studies': [], 'goals': [],
        'system': {
            'approved_models': ['KLR', 'OTE', 'ORB', 'POWELL_10AM'],
            'max_trades_per_day': 2, 'daily_risk_pct': 1,
            'max_losses_per_day': 2, 'live_sessions': ['NY_AM', 'NY_PM'],
            'prime_steps': ['Prepare', 'Risk', 'Identify', 'Manage', 'Evaluate'],
        },
    }


def test_workspace_records_are_server_saved_and_deletable(monkeypatch):
    workspace = _workspace()
    saved = {}
    monkeypatch.setattr(main, 'load_journal_workspace', lambda: workspace)
    monkeypatch.setattr(main, 'save_journal_workspace', lambda value: saved.update(value))
    client = TestClient(main.app)

    created = client.post('/journal/workspace/plans', json={
        'date': '2026-09-03', 'bias': 'BULLISH', 'book': 'LIVE',
        'game_plan': 'Buy only after confirmation.',
    })
    assert created.status_code == 200
    record = created.json()['record']
    assert record['book'] == 'LIVE'
    assert workspace['plans'][0]['game_plan'] == 'Buy only after confirmation.'

    deleted = client.post('/journal/workspace/plans/delete', json={'id': record['id']})
    assert deleted.status_code == 200
    assert workspace['plans'] == []
    assert saved['plans'] == []


def test_workspace_screenshot_attaches_to_exact_study(monkeypatch, tmp_path):
    workspace = _workspace()
    workspace['studies'] = [{'id': 'study-1', 'book': 'PAPER', 'title': 'Asia study'}]
    monkeypatch.setattr(main, 'load_journal_workspace', lambda: workspace)
    monkeypatch.setattr(main, 'save_journal_workspace', lambda value: None)
    monkeypatch.setattr(main, '__file__', str(tmp_path / 'main.py'))

    png = b'\x89PNG\r\n\x1a\nNOVA-STUDY'
    response = TestClient(main.app).post('/journal/workspace/screenshot/upload', json={
        'section': 'studies', 'id': 'study-1', 'mime_type': 'image/png',
        'data_base64': base64.b64encode(png).decode('ascii'),
    })
    assert response.status_code == 200
    filename = workspace['studies'][0]['screenshot_filename']
    assert workspace['studies'][0]['chart_snapshot'].endswith(filename)
    assert (tmp_path / 'mcp' / 'tradingview' / 'screenshots' / filename).read_bytes() == png


def test_trade_update_preserves_book_and_normalizes_loss(monkeypatch):
    trades = [{'ticker': 'MNQ', 'trade_mode': 'PAPER', 'setup_type': 'EXPERIMENTAL',
               'outcome': 'WIN', 'realized_pnl': 25, 'trade_date': '2026-09-03'}]
    saved = {}
    monkeypatch.setattr(main, 'load_journal', lambda: trades)
    monkeypatch.setattr(main, 'save_journal', lambda value: saved.setdefault('trades', list(value)))
    monkeypatch.setattr(main, 'compute_journal_stats', lambda value: {'total': len(value)})

    response = TestClient(main.app).post('/journal/trade/update', json={
        'index': 0, 'trade_mode': 'PAPER', 'outcome': 'LOSS',
        'realized_pnl': 40, 'notes': 'Paper-only study.',
    })
    assert response.status_code == 200
    assert saved['trades'][0]['trade_mode'] == 'PAPER'
    assert saved['trades'][0]['setup_type'] == 'EXPERIMENTAL'
    assert saved['trades'][0]['realized_pnl'] == -40
    assert saved['trades'][0]['outcome'] == 'LOSS'


def test_live_trade_rejects_unapproved_model(monkeypatch):
    monkeypatch.setattr(main, 'load_journal', lambda: [])
    response = TestClient(main.app).post('/journal/add', json={
        'ticker': 'MNQ', 'direction': 'LONG', 'outcome': 'WIN',
        'realized_pnl': 50, 'trade_mode': 'LIVE', 'setup_type': 'EXPERIMENTAL',
    })
    assert response.status_code == 400
    assert 'Live model must be' in response.json()['detail']
