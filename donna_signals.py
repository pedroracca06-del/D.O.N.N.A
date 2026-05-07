"""donna_signals.py — signal processing, verdict engine, alert history."""
from __future__ import annotations

from donna_config import (
    TELEGRAM_ALERT_MODE, safe_float, utc_now_iso, now_ny, session_label,
    send_telegram_message,
)
from donna_state import load_risk_state, load_alert_history, save_alert_history
from donna_engines import (
    build_session_significance, build_market_driver_engine, build_morning_edge,
)


def normalize_payload(payload):
    return {
        'ticker':           str(payload.get('ticker', 'UNKNOWN')),
        'price':            str(payload.get('price', '0')),
        'signal':           str(payload.get('signal', 'NONE')).upper(),
        'timeframe':        str(payload.get('timeframe', 'unknown')),
        'session':          str(payload.get('session', session_label())),
        'setup_type':       str(payload.get('setup_type', 'unknown')),
        'signal_priority':  str(payload.get('signal_priority', 'unknown')),
        'context_strength': str(payload.get('context_strength', 'moderate')),
        'market_state':     str(payload.get('market_state', 'neutral')),
        'scenario':         str(payload.get('scenario', 'none')),
        'fib_zone':         str(payload.get('fib_zone', 'none')),
        'liquidity':        str(payload.get('liquidity', 'unknown')),
        'bias':             str(payload.get('bias', 'neutral')),
        'score':            str(payload.get('score', '0')),
        'quality':          str(payload.get('quality', 'B')).upper(),
    }


def pre_verdict_engine(data, risk=None):
    state         = risk or load_risk_state()
    score         = safe_float(data['score'])
    quality       = data['quality']
    context       = data['context_strength'].lower()
    score_provided = score > 0
    points        = 0

    if score_provided:
        if score >= 80:   points += 4
        elif score >= 70: points += 3
        elif score >= 60: points += 2
        elif score >= 50: points += 1
        else:             points -= 1

    if quality == 'A':   points += 3
    elif quality == 'B': points += (2 if score_provided else 1)
    elif quality == 'D': points -= 1

    if context == 'strong':                        points += 3
    elif context == 'moderate' and score_provided: points += 1
    elif context not in ('strong', 'moderate'):    points -= 1

    session = str(state.get('donna_session', data.get('session', ''))).upper()
    ny      = now_ny()
    ny_mins = ny.hour * 60 + ny.minute
    if session == 'NEW_YORK_CASH':
        if (9 * 60 + 30 <= ny_mins <= 11 * 60) or (14 * 60 <= ny_mins <= 15 * 60 + 30):
            points += 3
        else:
            points += 1
    elif session == 'LONDON': points += 1
    elif session == 'ASIA':   points -= 1

    macro       = str(state.get('macro_risk', 'medium')).lower()
    event_phase = str(state.get('event_phase', '')).upper()
    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'): points -= 3
    elif macro == 'high':  points -= 1
    elif macro == 'low':   points += 1

    signal  = str(data.get('signal', '')).upper()
    snap    = state.get('market_snapshot', {})
    nas_pct = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    if signal in ('LONG', 'BUY'):
        if nas_pct > 0.5:   points += 2
        elif nas_pct > 0.2: points += 1
        elif nas_pct < -0.5: points -= 2
    elif signal in ('SHORT', 'SELL'):
        if nas_pct < -0.5:   points += 2
        elif nas_pct < -0.2: points += 1
        elif nas_pct > 0.5:  points -= 2

    sig = build_session_significance(state)
    if sig['label'].startswith('MAJOR'):   points += 2
    elif sig['label'].startswith('NOTABLE'): points += 1

    return 'TAKE' if points >= 8 else 'CAUTION' if points >= 4 else 'SKIP'


def _compute_signal_confidence(data, risk, sig):
    score  = safe_float(data['score'])
    base   = score if score > 0 else 62.0
    signal = str(data.get('signal', '')).upper()
    session = str(risk.get('donna_session', '')).upper()
    macro   = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()
    snap    = risk.get('market_snapshot', {})
    nas_pct = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    vix_pct = safe_float(snap.get('VIX', {}).get('pct', 0))
    ny_mins = now_ny().hour * 60 + now_ny().minute
    adj     = 0.0

    if session == 'NEW_YORK_CASH':
        if (9 * 60 + 30 <= ny_mins <= 11 * 60) or (14 * 60 <= ny_mins <= 15 * 60 + 30): adj += 10
        else: adj += 4
    elif session == 'LONDON': adj += 3
    elif session == 'ASIA':   adj -= 6

    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):   adj -= 15
    elif macro == 'high' and event_phase == 'APPROACHING':         adj -= 8
    elif macro == 'high':                                           adj -= 5
    elif macro == 'low':                                            adj += 5

    if signal in ('LONG', 'BUY'):
        if nas_pct > 0.5:    adj += 8
        elif nas_pct > 0.2:  adj += 4
        elif nas_pct < -0.5: adj -= 10
        elif nas_pct < -0.2: adj -= 5
    elif signal in ('SHORT', 'SELL'):
        if nas_pct < -0.5:   adj += 8
        elif nas_pct < -0.2: adj += 4
        elif nas_pct > 0.5:  adj -= 10
        elif nas_pct > 0.2:  adj -= 5

    if sig['label'].startswith('MAJOR'):   adj += 8
    elif sig['label'].startswith('NOTABLE'): adj += 4

    if vix_pct >= 5:    adj -= 8
    elif vix_pct >= 2:  adj -= 4
    elif vix_pct <= -3: adj += 3

    return round(max(20.0, min(97.0, base + adj)), 1)


def _generate_signal_summary(data, risk, sig, driver):
    ticker     = data['ticker']
    signal     = str(data['signal']).upper()
    price      = data['price']
    timeframe  = data['timeframe']
    session    = str(risk.get('donna_session', data.get('session', ''))).upper()
    macro      = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()
    next_event = risk.get('next_event', 'no major event scheduled')
    snap       = risk.get('market_snapshot', {})
    nas_pct    = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    ny_mins    = now_ny().hour * 60 + now_ny().minute
    is_prime   = session == 'NEW_YORK_CASH' and ((9 * 60 + 30 <= ny_mins <= 11 * 60) or (14 * 60 <= ny_mins <= 15 * 60 + 30))

    session_label_map = {'NEW_YORK_CASH': 'NY cash session', 'LONDON': 'London session', 'ASIA': 'Asia session', 'OFF_HOURS': 'off-hours'}
    session_phrase    = session_label_map.get(session, session.lower().replace('_', ' '))

    if signal in ('LONG', 'BUY'):
        if nas_pct > 0.5:    dir_note = f'NQ is up {nas_pct:.1f}% — momentum is aligned with the long.'
        elif nas_pct > 0.1:  dir_note = f'NQ is modestly positive (+{nas_pct:.1f}%) — bias leans long but lacks full conviction.'
        elif nas_pct < -0.5: dir_note = f'NQ is down {nas_pct:.1f}% — this long is counter-trend; require clean structure confirmation.'
        else:                 dir_note = 'NQ is near flat — long signal needs structural support to hold.'
    elif signal in ('SHORT', 'SELL'):
        if nas_pct < -0.5:   dir_note = f'NQ is down {nas_pct:.1f}% — momentum aligns with the short.'
        elif nas_pct < -0.1: dir_note = f'NQ is modestly negative ({nas_pct:.1f}%) — bias leans short but cautious.'
        elif nas_pct > 0.5:  dir_note = f'NQ is up +{nas_pct:.1f}% — this short is counter-trend; use tight management.'
        else:                 dir_note = 'NQ is near flat — short signal requires clear structural breakdown.'
    else:
        dir_note = f'NQ is at {nas_pct:+.1f}% — no clear directional alignment for this signal type.'

    if ticker == 'MNQ1!' and timeframe == '1':
        nq_pts = sig['nq_points']
        regime = driver.get('market_regime', 'Neutral')
        if sig['label'].startswith('MAJOR'):
            return (f"MNQ1! 1m signal at {price} inside a MAJOR NQ session expansion ({int(nq_pts)} pts). "
                    f"Regime: {regime}. {dir_note} "
                    f"This is a high-significance NQ window — momentum conditions are real, not noise.")
        elif sig['label'].startswith('NOTABLE'):
            return (f"MNQ1! 1m signal at {price}. NQ has expanded ~{int(nq_pts)} pts this session — notable, not routine. "
                    f"Regime: {regime}. {dir_note}")
        else:
            return (f"MNQ1! 1m signal at {price} in the {session_phrase}. "
                    f"NQ session move is routine ({int(nq_pts)} pts). {dir_note} Macro: {macro}.")

    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
        return (f"{ticker} {signal} at {price} — macro event is LIVE ({next_event}). "
                f"DONNA flags elevated risk. {dir_note} Treat as event-period noise until price confirms cleanly.")

    if macro == 'high' and event_phase == 'APPROACHING':
        return (f"{ticker} {signal} at {price} in {session_phrase}. {next_event} approaching — macro risk is elevated. "
                f"{dir_note} Do not add size into the event window.")

    if is_prime:
        return (f"{ticker} {signal} at {price} during prime {session_phrase}. "
                f"{dir_note} Macro: {macro}. {sig['summary']}")

    return (f"{ticker} {signal} at {price} in {session_phrase}. "
            f"{dir_note} Macro: {macro}. {driver.get('market_summary', 'No strong driver detected.')}")


def should_send_trade_to_telegram(parsed):
    mode = (TELEGRAM_ALERT_MODE or 'critical').lower()
    if mode == 'off':  return False
    if mode == 'all':  return True
    verdict = str(parsed.get('verdict', '')).upper()
    try:
        confidence = float(str(parsed.get('confidence', '0')).replace('%', '').strip())
    except Exception:
        confidence = 0.0
    return verdict == 'TAKE' or confidence >= 80


def add_alert_to_history(data, parsed):
    alerts = load_alert_history()
    alerts.insert(0, {
        'ticker':     data['ticker'],
        'signal':     data['signal'],
        'session':    data['session'],
        'timeframe':  data['timeframe'],
        'price':      data['price'],
        'verdict':    parsed['verdict'],
        'confidence': parsed['confidence'],
        'summary':    parsed['summary'],
        'timestamp':  utc_now_iso(),
    })
    save_alert_history(alerts)


def process_signal(payload):
    data = normalize_payload(payload)
    if data['signal'] == 'NONE':
        return {'status': 'ignored', 'reason': 'signal NONE'}

    risk   = load_risk_state()
    sig    = build_session_significance(risk)
    driver = build_market_driver_engine(risk)
    morning = build_morning_edge(risk)

    verdict         = pre_verdict_engine(data, risk)
    confidence_val  = _compute_signal_confidence(data, risk, sig)
    confidence      = f'{confidence_val}%'
    summary         = _generate_signal_summary(data, risk, sig, driver)

    macro       = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()
    session     = str(risk.get('donna_session', '')).upper()
    snap        = risk.get('market_snapshot', {})
    nas_pct     = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    signal      = str(data['signal']).upper()

    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
        why = f"Macro event is live ({risk.get('next_event', 'unknown')}). Confidence penalized — event-period signals carry outsized noise."
    elif sig['label'].startswith('MAJOR'):
        why = 'Major NQ session expansion is the primary context. Momentum conditions deserve respect.'
    elif signal in ('LONG', 'BUY') and nas_pct > 0.5:
        why = f'Long signal aligned with NQ up {nas_pct:.1f}% — directional context supports the trade.'
    elif signal in ('SHORT', 'SELL') and nas_pct < -0.5:
        why = f'Short signal aligned with NQ down {nas_pct:.1f}% — momentum favors the direction.'
    elif session == 'NEW_YORK_CASH':
        why = 'NY cash session active — signal quality elevated by session timing.'
    else:
        why = f"Confidence reflects {macro} macro risk and {session.lower().replace('_', ' ')} session quality."

    if event_phase in ('LIVE', 'IMMINENT'):
        execution = 'Reduce size or stand aside until event resolves. Price confirmation required.'
    elif sig['label'].startswith('MAJOR'):
        execution = 'Respect leadership. Do not fade strength blindly in a major session expansion.'
    elif macro == 'high':
        execution = 'Keep size controlled. Event risk can reverse moves quickly without warning.'
    else:
        execution = morning.get('first_read', 'Use leadership and event timing as the final filter.')

    risk_text = (f"Macro: {macro.upper()} | Headline: {str(risk.get('headline_risk', 'medium')).upper()} "
                 f"| Event: {risk.get('next_event', 'none')} ({event_phase})")

    parsed = {
        'verdict': verdict, 'confidence': confidence, 'why': why,
        'risk': risk_text, 'execution': execution, 'summary': summary,
    }
    add_alert_to_history(data, parsed)
    if should_send_trade_to_telegram(parsed):
        send_telegram_message(
            f"DONNA // {data['ticker']} // {data['signal']}\n"
            f"{data['session']} | TF {data['timeframe']} | Price {data['price']}\n\n"
            f"Verdict: {parsed['verdict']}\nConfidence: {parsed['confidence']}\n"
            f"Why: {parsed['why']}\nRisk: {parsed['risk']}\n"
            f"Execution: {parsed['execution']}\nSummary: {parsed['summary']}"
        )
    return {'status': 'ok', 'data': data, 'parsed': parsed}
