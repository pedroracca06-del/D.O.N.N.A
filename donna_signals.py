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


def normalize_payload(payload: dict) -> dict:
    # trap_risk may arrive as bool or string
    trap_raw  = payload.get('trap_risk', False)
    trap_risk = trap_raw if isinstance(trap_raw, bool) else str(trap_raw).lower() in ('true', '1', 'yes')

    return {
        # ── original fields ──────────────────────────────────────
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
        # ── HARVEY V4 fields ─────────────────────────────────────
        'tier':             str(payload.get('tier', '')).upper(),
        'signal_reason':    str(payload.get('signal_reason', '')),
        'ict_step':         str(payload.get('ict_step', '')),
        'trap_risk':        trap_risk,
        'kill_zone':        str(payload.get('kill_zone', '')),
        'regime':           str(payload.get('regime', '')),
        'liq_state':        str(payload.get('liq_state', '')),
        'brain_state':      str(payload.get('brain_state', '')),
        'harvey_confidence': str(payload.get('confidence', '')),  # HARVEY's 100-pt score
    }


def pre_verdict_engine(data: dict, risk=None) -> str:
    # ── trap risk is an immediate veto ──────────────────────────
    if data.get('trap_risk'):
        return 'WAIT'

    state = risk or load_risk_state()
    score = safe_float(data['score'])
    tier  = data.get('tier', '').upper()

    # ── tier-based fast path ────────────────────────────────────
    if tier in ('1', 'ELITE'):
        if score >= 55:
            return 'TAKE'
    elif tier == '2':
        if score >= 62:
            return 'TAKE'
    elif tier == '3':
        if score >= 70:
            return 'TAKE'

    # ── existing point system (no tier, or tier threshold not met) ──
    quality        = data['quality']
    context        = data['context_strength'].lower()
    score_provided = score > 0
    points         = 0

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
        if nas_pct > 0.5:    points += 2
        elif nas_pct > 0.2:  points += 1
        elif nas_pct < -0.5: points -= 2
    elif signal in ('SHORT', 'SELL'):
        if nas_pct < -0.5:   points += 2
        elif nas_pct < -0.2: points += 1
        elif nas_pct > 0.5:  points -= 2

    sig = build_session_significance(state)
    if sig['label'].startswith('MAJOR'):    points += 2
    elif sig['label'].startswith('NOTABLE'): points += 1

    return 'TAKE' if points >= 8 else 'CAUTION' if points >= 4 else 'SKIP'


def _compute_signal_confidence(data: dict, risk: dict, sig: dict) -> float:
    # ── HARVEY's own confidence takes full precedence ─────────
    harvey_raw = str(data.get('harvey_confidence', '')).strip()
    if harvey_raw:
        try:
            base = float(harvey_raw.replace('%', '').strip())
            if base > 0:
                if str(data.get('kill_zone', '')).upper() == 'OFF KZ':
                    base *= 0.85
                return round(max(20.0, min(97.0, base)), 1)
        except (ValueError, TypeError):
            pass

    # ── Fallback: DONNA's own scoring model ───────────────────
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

    if sig['label'].startswith('MAJOR'):    adj += 8
    elif sig['label'].startswith('NOTABLE'): adj += 4

    if vix_pct >= 5:    adj -= 8
    elif vix_pct >= 2:  adj -= 4
    elif vix_pct <= -3: adj += 3

    # Kill zone penalty on DONNA's fallback path too
    if str(data.get('kill_zone', '')).upper() == 'OFF KZ':
        adj -= (base + adj) * 0.15

    return round(max(20.0, min(97.0, base + adj)), 1)


def _generate_signal_summary(data: dict, risk: dict, sig: dict, driver: dict) -> str:
    ticker        = data['ticker']
    signal        = str(data['signal']).upper()
    price         = data['price']
    timeframe     = data['timeframe']
    signal_reason = str(data.get('signal_reason', '')).upper()
    kill_zone     = str(data.get('kill_zone', ''))
    regime        = str(data.get('regime', '') or driver.get('market_regime', 'Neutral'))
    liq_state     = str(data.get('liq_state', ''))
    brain_state   = str(data.get('brain_state', ''))
    target        = str(data.get('scenario', '') or data.get('fib_zone', ''))
    session       = str(risk.get('donna_session', data.get('session', ''))).upper()
    macro         = str(risk.get('macro_risk', 'medium')).lower()
    event_phase   = str(risk.get('event_phase', '')).upper()
    next_event    = risk.get('next_event', 'no major event scheduled')
    snap          = risk.get('market_snapshot', {})
    nas_pct       = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    ny_mins       = now_ny().hour * 60 + now_ny().minute
    is_prime      = session == 'NEW_YORK_CASH' and (
        (9 * 60 + 30 <= ny_mins <= 11 * 60) or (14 * 60 <= ny_mins <= 15 * 60 + 30)
    )

    # ── always-present context suffix ────────────────────────
    ctx_parts = []
    if regime:      ctx_parts.append(f'Regime: {regime}')
    if liq_state:   ctx_parts.append(f'Liq: {liq_state}')
    if brain_state: ctx_parts.append(f'Brain: {brain_state}')
    ctx = ' | '.join(ctx_parts)

    def _with_ctx(s: str) -> str:
        return f'{s} [{ctx}]' if ctx else s

    # ── signal_reason-specific templates ─────────────────────
    if 'ICT' in signal_reason and 'ELITE' in signal_reason:
        kz        = kill_zone or 'current kill zone'
        direction = 'long' if 'LONG' in signal_reason else 'short'
        return _with_ctx(
            f'Elite ICT setup in {kz}. Full 6-step model confirmed. Highest conviction {direction}.'
        )

    if 'ORB' in signal_reason:
        direction     = 'long' if 'LONG' in signal_reason else 'short'
        breakout_type = 'breakout' if direction == 'long' else 'rejection'
        tgt_note      = f' Target: {target}.' if target and target not in ('none', '') else ''
        return _with_ctx(f'ORB {breakout_type} on {ticker}. {regime}.{tgt_note}')

    if 'LIQUIDITY' in signal_reason or signal_reason.startswith('LIQ'):
        liq = liq_state or 'key level'
        return _with_ctx(f'Liquidity sweep at {liq}. Reversal setup confirmed.')

    # ── fallback: existing directional + macro logic ──────────
    if signal in ('LONG', 'BUY'):
        if nas_pct > 0.5:    dir_note = f'NQ is up {nas_pct:.1f}% — momentum aligned with the long.'
        elif nas_pct > 0.1:  dir_note = f'NQ is modestly positive (+{nas_pct:.1f}%) — bias leans long.'
        elif nas_pct < -0.5: dir_note = f'NQ is down {nas_pct:.1f}% — counter-trend long; require clean structure.'
        else:                 dir_note = 'NQ near flat — long needs structural support.'
    elif signal in ('SHORT', 'SELL'):
        if nas_pct < -0.5:   dir_note = f'NQ is down {nas_pct:.1f}% — momentum aligned with the short.'
        elif nas_pct < -0.1: dir_note = f'NQ is modestly negative ({nas_pct:.1f}%) — bias leans short.'
        elif nas_pct > 0.5:  dir_note = f'NQ is up +{nas_pct:.1f}% — counter-trend short; use tight management.'
        else:                 dir_note = 'NQ near flat — short needs clear structural breakdown.'
    else:
        dir_note = f'NQ at {nas_pct:+.1f}% — no clear directional alignment.'

    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
        base = (f'{ticker} {signal} at {price} — macro event LIVE ({next_event}). '
                f'Elevated risk. {dir_note} Wait for clean confirmation.')
    elif macro == 'high' and event_phase == 'APPROACHING':
        base = (f'{ticker} {signal} at {price}. {next_event} approaching. '
                f'{dir_note} Do not add size into the event window.')
    elif is_prime:
        session_label_map = {'NEW_YORK_CASH': 'NY cash session', 'LONDON': 'London session', 'ASIA': 'Asia session'}
        sp = session_label_map.get(session, session.lower().replace('_', ' '))
        base = f'{ticker} {signal} at {price} during prime {sp}. {dir_note} Macro: {macro}. {sig["summary"]}'
    elif ticker == 'MNQ1!' and timeframe == '1':
        nq_pts = sig['nq_points']
        label  = sig['label']
        if label.startswith('MAJOR'):
            base = (f'MNQ1! 1m at {price} inside MAJOR NQ expansion ({int(nq_pts)} pts). '
                    f'{dir_note} This is a high-significance window.')
        else:
            base = f'MNQ1! 1m at {price}. NQ session move: {int(nq_pts)} pts. {dir_note}'
    else:
        base = (f'{ticker} {signal} at {price}. {dir_note} Macro: {macro}. '
                f'{driver.get("market_summary", "No strong driver detected.")}')

    return _with_ctx(base)


def should_send_trade_to_telegram(parsed: dict) -> bool:
    mode = (TELEGRAM_ALERT_MODE or 'critical').lower()
    if mode == 'off':  return False
    if mode == 'all':  return True
    verdict = str(parsed.get('verdict', '')).upper()
    try:
        confidence = float(str(parsed.get('confidence', '0')).replace('%', '').strip())
    except Exception:
        confidence = 0.0
    return verdict in ('TAKE', 'WAIT') or confidence >= 80


def add_alert_to_history(data: dict, parsed: dict):
    alerts = load_alert_history()
    alerts.insert(0, {
        'ticker':       data['ticker'],
        'signal':       data['signal'],
        'session':      data['session'],
        'timeframe':    data['timeframe'],
        'price':        data['price'],
        'verdict':      parsed['verdict'],
        'confidence':   parsed['confidence'],
        'summary':      parsed['summary'],
        'tier':         data.get('tier', ''),
        'signal_reason':data.get('signal_reason', ''),
        'brain_state':  data.get('brain_state', ''),
        'trap_risk':    data.get('trap_risk', False),
        'timestamp':    utc_now_iso(),
    })
    save_alert_history(alerts)


def process_signal(payload: dict) -> dict:
    data = normalize_payload(payload)
    if data['signal'] == 'NONE':
        return {'status': 'ignored', 'reason': 'signal NONE'}

    risk    = load_risk_state()
    sig     = build_session_significance(risk)
    driver  = build_market_driver_engine(risk)
    morning = build_morning_edge(risk)

    verdict        = pre_verdict_engine(data, risk)
    confidence_val = _compute_signal_confidence(data, risk, sig)
    confidence     = f'{confidence_val}%'
    summary        = _generate_signal_summary(data, risk, sig, driver)

    macro       = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()
    session     = str(risk.get('donna_session', '')).upper()
    snap        = risk.get('market_snapshot', {})
    nas_pct     = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    signal      = str(data['signal']).upper()
    tier        = data.get('tier', '')
    ict_step    = data.get('ict_step', '')
    brain_state = data.get('brain_state', '')
    trap_risk   = data.get('trap_risk', False)

    # why
    if trap_risk:
        why = 'Trap risk flagged by HARVEY — signal vetoed regardless of score.'
    elif data.get('harvey_confidence'):
        why = f"HARVEY confidence: {data['harvey_confidence']}. {'Kill zone penalty applied (OFF KZ).' if data.get('kill_zone', '').upper() == 'OFF KZ' else 'Kill zone confirmed.'}"
    elif macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
        why = f"Macro event is live ({risk.get('next_event', 'unknown')}). Confidence penalized — event-period noise is real."
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

    # execution
    if trap_risk:
        execution = 'Stand aside — HARVEY flagged a trap. Do not enter until trap_risk clears.'
    elif event_phase in ('LIVE', 'IMMINENT'):
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
        'verdict':    verdict,
        'confidence': confidence,
        'why':        why,
        'risk':       risk_text,
        'execution':  execution,
        'summary':    summary,
    }

    add_alert_to_history(data, parsed)

    if should_send_trade_to_telegram(parsed):
        tier_line   = f'Tier: {tier}' if tier else ''
        step_line   = f'ICT Step: {ict_step}' if ict_step else ''
        brain_line  = f'Brain: {brain_state}' if brain_state else ''
        trap_line   = 'TRAP RISK: YES — WAIT forced' if trap_risk else ''
        extra_lines = '\n'.join(l for l in [tier_line, step_line, brain_line, trap_line] if l)

        send_telegram_message(
            f"DONNA // {data['ticker']} // {data['signal']}\n"
            f"{data['session']} | TF {data['timeframe']} | Price {data['price']}\n"
            + (f'{extra_lines}\n' if extra_lines else '') +
            f'\nVerdict: {parsed["verdict"]}\nConfidence: {parsed["confidence"]}\n'
            f'Why: {parsed["why"]}\nRisk: {parsed["risk"]}\n'
            f'Execution: {parsed["execution"]}\nSummary: {parsed["summary"]}'
        )

    return {'status': 'ok', 'data': data, 'parsed': parsed}
