import inspect

from services import news


def _item(label):
    return [{
        'headline': label,
        'summary': '',
        'source': 'test',
        'url': '',
        'ts': 0,
    }]


def test_news_sources_rotate_when_both_are_available(monkeypatch):
    calls = []
    monkeypatch.setattr(news, '_news_source_cursor', 0)
    monkeypatch.setattr(
        news, '_fetch_finnhub_news',
        lambda: calls.append('finnhub') or _item('Finnhub headline'),
    )
    monkeypatch.setattr(
        news, '_fetch_fmp_news',
        lambda: calls.append('fmp') or _item('FMP headline'),
    )

    assert news._fetch_rotating_news()[0]['headline'] == 'Finnhub headline'
    assert news._fetch_rotating_news()[0]['headline'] == 'FMP headline'
    assert calls == ['finnhub', 'fmp']


def test_news_rotation_falls_back_when_selected_source_is_empty(monkeypatch):
    calls = []
    monkeypatch.setattr(news, '_news_source_cursor', 0)
    monkeypatch.setattr(
        news, '_fetch_finnhub_news',
        lambda: calls.append('finnhub') or [],
    )
    monkeypatch.setattr(
        news, '_fetch_fmp_news',
        lambda: calls.append('fmp') or _item('Fallback headline'),
    )

    assert news._fetch_rotating_news()[0]['headline'] == 'Fallback headline'
    assert calls == ['finnhub', 'fmp']


def test_startup_schedules_external_warmup_instead_of_awaiting_it():
    import main

    source = inspect.getsource(main.startup)
    assert 'asyncio.create_task(_initial_data_warmup())' in source
    assert 'await _initial_data_warmup()' not in source
    assert 'await asyncio.to_thread(check_todays_breaking_events)' not in source
    assert 'await asyncio.to_thread(process_finnhub_cycle)' not in source


def test_periodic_market_refresh_does_not_duplicate_deploy_warmup():
    import main

    source = inspect.getsource(main.finnhub_loop)
    assert source.index('await asyncio.sleep(300)') < source.index('while True:')
