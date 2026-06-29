"""donna_signals.py — signal processing, verdict engine, alert history."""
from __future__ import annotations

import time

from core.config import (
    TELEGRAM_ALERT_MODE, safe_float, utc_now_iso, now_ny, session_label,
    send_telegram_message,
)
from core.state import load_risk_state, load_alert_history, save_alert_history
from engines.engines import (
    build_session_significance, build_market_driver_engine, build_morning_edge,
)

# Known setup types (used for routing and labelling)
_ELITE_SETUPS = {'ICT_ELITE', 'ICT_ELITE_SHORT', 'ICT_ELITE_LONG'}
_ICT_SETUPS   = {'ICT_BUY', 'ICT_SELL', 'HARVEY_BUY', 'HARVEY_SELL'}
_ORB_SETUPS   = {'ORB_MID_REJECT', 'ORB_LIQ_REJECT', 'ORB_EDGE_REJECT', 'ORB_LONG', 'ORB_SHORT'}
_PROS_SETUPS  = {'PROS_CONTINUATION'}


def normalize_payload(payload: dict) -> dict:
    setup_type = str(payload.get('setup_type', 'unknown')).upper()
    strategy_family = (
        'ORB'            if setup_type.startswith('ORB')  else
        'PROS'           if setup_type.startswith('PROS') else
        'ICT'            if setup_type.startswith('ICT')  else
        'FAILED_AUCTION' if setup_type == 'FAILED_AUCTION' else
        'MOMENTUM'       if setup_type == 'MOMENTUM_CONTINUATION' else
        'UNKNOWN'
    )
    ticker_raw = str(payload.get('ticker', 'UNKNOWN')).upper()
    signal_raw = str(payload.get('signal', 'NONE')).upper()
    signal_id  = f"{ticker_raw}_{signal_raw}_{int(time.time())}"

    return {
        # ── core fields ──────────────────────────────────────────
        'ticker':           ticker_raw,
        'price':            str(payload.get('price', '0')),
        'signal':           signal_raw,
        'timeframe':        str(payload.get('timeframe', 'unknown')),
        'session':          str(payload.get('session', session_label())),
        'setup_type':       setup_type,
        'strategy_family':  strategy_family,
        'signal_id':        signal_id,
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
        'instrument':       str(payload.get('instrument', 'unknown')).upper(),
        'tier':             str(payload.get('tier', '3')).upper(),
        'trap_risk':        str(payload.get('trap_risk', 'false')).lower(),
        'signal_reason':    str(payload.get('signal_reason', '')),
        'ict_step':         str(payload.get('ict_step', '')),
        'kill_zone':        str(payload.get('kill_zone', '')),
        'regime':           str(payload.get('regime', '')),
        'liq_state':        str(payload.get('liq_state', '')),
        'brain_state':      str(payload.get('brain_state', '')),
        'harvey_confidence': str(payload.get('confidence', '')),
    }


def _is_elite(data: dict) -> bool:
    return data.get('tier', '') in ('1', 'ELITE') or data.get('setup_type', '') in _ELITE_SETUPS


def _is_nq(data: dict) -> bool:
    instrument = data.get('instrument', '').upper()
    ticker     = data.get('ticker', '').upper()
    return 'NQ' in instrument or 'MNQ' in ticker or 'NQ' in ticker


def pre_verdict_engine(data: dict, risk=None) -> str:
    # ── trap risk: immediate SKIP ────────────────────────────
    if data.get('trap_risk') == 'true':
        return 'SKIP'

    state      = risk or load_risk_state()
    score      = safe_float(data['score'])
    tier       = data.get('tier', '3').upper()
    setup_type = data.get('setup_type', '').upper()

    # ── ORB on NQ → always CAUTION ───────────────────────────
    if setup_type in _ORB_SETUPS and _is_nq(data):
        return 'CAUTION'

    # ── tier / elite fast-path ───────────────────────────────
    if _is_elite(data):
        if score >= 55:
            return 'TAKE'
    elif tier == '2':
        if score >= 62:
            return 'TAKE'
    elif tier == '3':
        if score >= 70:
            return 'TAKE'

    # ── point system fallback ────────────────────────────────
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

    session = str(state.get('nova_session') or state.get('donna_session') or data.get('session') or '').upper()
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
    if sig['label'].startswith('MAJOR'):     points += 2
    elif sig['label'].startswith('NOTABLE'): points += 1

    return 'TAKE' if points >= 8 else 'CAUTION' if points >= 4 else 'SKIP'


def _compute_signal_confidence(data: dict, risk: dict, sig: dict) -> float:
    session     = str(risk.get('nova_session') or risk.get('donna_session') or '').upper()
    macro       = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()

    # ── HARVEY's own score takes full precedence ──────────────
    harvey_raw = str(data.get('harvey_confidence', '')).strip()
    if harvey_raw:
        try:
            val = float(harvey_raw.replace('%', '').strip())
            if val > 0:
                if str(data.get('kill_zone', '')).upper() == 'OFF KZ':
                    val *= 0.85
                return round(max(20.0, min(97.0, val)), 1)
        except (ValueError, TypeError):
            pass

    # ── Tier-based base confidence ────────────────────────────
    tier       = data.get('tier', '3').upper()
    setup_type = data.get('setup_type', '').upper()

    if _is_elite(data):
        base = 85.0
    elif tier == '2':
        base = 72.0
    else:
        base = 58.0

    # ── Percentage reductions ─────────────────────────────────
    if macro == 'high':
        base *= 0.80                                 # −20 % macro risk
    if event_phase in ('LIVE', 'IMMINENT'):
        base *= 0.85                                 # −15 % event active
    if session != 'NEW_YORK_CASH':
        base *= 0.90                                 # −10 % off-session

    # ── Kill zone penalty ─────────────────────────────────────
    if str(data.get('kill_zone', '')).upper() == 'OFF KZ':
        base *= 0.85

    # ── NQ/NASDAQ momentum nudge (minor) ─────────────────────
    snap    = risk.get('market_snapshot', {})
    nas_pct = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    signal  = str(data.get('signal', '')).upper()
    if signal in ('LONG', 'BUY'):
        if nas_pct > 0.5:    base = min(97.0, base + 5)
        elif nas_pct < -0.5: base = max(20.0, base - 8)
    elif signal in ('SHORT', 'SELL'):
        if nas_pct < -0.5:   base = min(97.0, base + 5)
        elif nas_pct > 0.5:  base = max(20.0, base - 8)

    return round(max(20.0, min(97.0, base)), 1)


def _generate_signal_summary(data: dict, risk: dict, sig: dict, driver: dict) -> str:
    ticker      = data['ticker']
    signal      = str(data['signal']).upper()
    price       = data['price']
    timeframe   = data['timeframe']
    setup_type  = data.get('setup_type', '').upper()
    instrument  = data.get('instrument', ticker).upper()
    tier        = data.get('tier', '3')
    regime      = str(data.get('regime', '') or driver.get('market_regime', 'Neutral'))
    liq_state   = str(data.get('liq_state', ''))
    brain_state = str(data.get('brain_state', ''))
    kill_zone   = str(data.get('kill_zone', ''))
    session_raw = str(risk.get('nova_session') or risk.get('donna_session') or data.get('session') or '').upper()
    macro       = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()
    next_event  = risk.get('next_event', 'no major event scheduled')
    snap        = risk.get('market_snapshot', {})
    nas_pct     = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    ny_mins     = now_ny().hour * 60 + now_ny().minute
    is_prime    = session_raw == 'NEW_YORK_CASH' and (
        (9 * 60 + 30 <= ny_mins <= 11 * 60) or (14 * 60 <= ny_mins <= 15 * 60 + 30)
    )
    session_name = {'NEW_YORK_CASH': 'NY cash', 'LONDON': 'London', 'ASIA': 'Asia'}.get(
        session_raw, session_raw.lower().replace('_', ' ')
    )

    # ── context suffix (always appended) ─────────────────────
    ctx_parts = []
    if regime:      ctx_parts.append(f'Regime: {regime}')
    if liq_state:   ctx_parts.append(f'Liq: {liq_state}')
    if brain_state: ctx_parts.append(f'Brain: {brain_state}')
    ctx = ' | '.join(ctx_parts)

    def _with_ctx(s: str) -> str:
        return f'{s} [{ctx}]' if ctx else s

    # ── setup_type-specific templates ────────────────────────
    if setup_type in _ELITE_SETUPS:
        body = (f'ELITE ICT setup on {instrument}. '
                f'Tier 1 — highest conviction HARVEY signal. {regime} regime.')

    elif setup_type in _ICT_SETUPS:
        direction = 'long' if signal in ('LONG', 'BUY') else 'short'
        body = (f'HARVEY Tier {tier} {direction} on {instrument}. '
                f'ICT structure confirmed in {session_name} session.')

    elif setup_type in _ORB_SETUPS:
        entry_type = setup_type.replace('ORB_', '').replace('_', ' ')
        body = (f'ORB {entry_type} on {instrument}. '
                f'Respect event timing if macro risk is active.')

    elif setup_type in _PROS_SETUPS:
        direction = 'long' if signal in ('LONG', 'BUY') else 'short'
        body = (f'PROS continuation {direction} on {instrument}. '
                f'Displacement → retracement → continuation confirmed. {regime} regime.')

    else:
        # ── fallback: directional + macro ─────────────────────
        if signal in ('LONG', 'BUY'):
            if nas_pct > 0.5:    dir_note = f'NQ up {nas_pct:.1f}% — momentum aligned.'
            elif nas_pct > 0.1:  dir_note = f'NQ +{nas_pct:.1f}% — bias leans long.'
            elif nas_pct < -0.5: dir_note = f'NQ down {nas_pct:.1f}% — counter-trend long.'
            else:                 dir_note = 'NQ near flat — structural support required.'
        elif signal in ('SHORT', 'SELL'):
            if nas_pct < -0.5:   dir_note = f'NQ down {nas_pct:.1f}% — momentum aligned.'
            elif nas_pct < -0.1: dir_note = f'NQ {nas_pct:.1f}% — bias leans short.'
            elif nas_pct > 0.5:  dir_note = f'NQ +{nas_pct:.1f}% — counter-trend short.'
            else:                 dir_note = 'NQ near flat — structural breakdown required.'
        else:
            dir_note = f'NQ at {nas_pct:+.1f}%.'

        if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
            body = (f'{ticker} {signal} at {price} — macro event LIVE ({next_event}). '
                    f'{dir_note} Wait for clean confirmation.')
        elif is_prime:
            body = f'{ticker} {signal} at {price} during prime {session_name}. {dir_note} Macro: {macro}. {sig["summary"]}'
        else:
            body = (f'{ticker} {signal} at {price}. {dir_note} Macro: {macro}. '
                    f'{driver.get("market_summary", "No strong driver detected.")}')

    summary = _with_ctx(body)

    # ── conditional risk warnings (appended to all templates) ─
    warnings: list[str] = []
    if macro == 'high':
        warnings.append('⚠️ Macro risk HIGH — reduce size, respect reaction risk.')
    if event_phase in ('LIVE', 'IMMINENT'):
        warnings.append(f'⚠️ Event is {event_phase} — WAIT for clean price action.')

    if warnings:
        summary = summary + ' ' + ' '.join(warnings)

    return summary


def should_send_trade_to_telegram(parsed: dict) -> bool:
    mode = (TELEGRAM_ALERT_MODE or 'critical').lower()
    if mode == 'off': return False
    if mode == 'all': return True
    verdict = str(parsed.get('verdict', '')).upper()
    try:
        confidence = float(str(parsed.get('confidence', '0')).replace('%', '').strip())
    except Exception:
        confidence = 0.0
    return verdict == 'TAKE' or confidence >= 80


def add_alert_to_history(data: dict, parsed: dict):
    alerts = load_alert_history()
    alerts.insert(0, {
        'ticker':        data['ticker'],
        'signal':        data['signal'],
        'session':       data['session'],
        'timeframe':     data['timeframe'],
        'price':         data['price'],
        'verdict':       parsed['verdict'],
        'confidence':    parsed['confidence'],
        'summary':       parsed['summary'],
        'instrument':    data.get('instrument', ''),
        'tier':          data.get('tier', ''),
        'setup_type':    data.get('setup_type', ''),
        'signal_reason': data.get('signal_reason', ''),
        'brain_state':   data.get('brain_state', ''),
        'trap_risk':     data.get('trap_risk', 'false'),
        'timestamp':     utc_now_iso(),
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
    session     = str(risk.get('nova_session') or risk.get('donna_session') or '').upper()
    snap        = risk.get('market_snapshot', {})
    nas_pct     = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    signal      = str(data['signal']).upper()
    instrument  = data.get('instrument', data['ticker'])
    tier        = data.get('tier', '')
    setup_type  = data.get('setup_type', '')
    ict_step    = data.get('ict_step', '')
    brain_state = data.get('brain_state', '')
    trap_risk   = data.get('trap_risk') == 'true'

    # ── why ──────────────────────────────────────────────────
    if trap_risk:
        why = 'Trap risk flagged by HARVEY — signal forced to SKIP.'
    elif data.get('harvey_confidence'):
        kz_note = 'Kill zone penalty applied (OFF KZ).' if data.get('kill_zone', '').upper() == 'OFF KZ' else 'Kill zone active.'
        why = f"HARVEY confidence: {data['harvey_confidence']}. {kz_note}"
    elif macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
        why = f"Macro event LIVE ({risk.get('next_event', 'unknown')}). Confidence penalized — event-period noise is real."
    elif sig['label'].startswith('MAJOR'):
        why = 'Major NQ session expansion. Momentum conditions deserve respect.'
    elif signal in ('LONG', 'BUY') and nas_pct > 0.5:
        why = f'Long aligned with NQ +{nas_pct:.1f}% — directional context supports the trade.'
    elif signal in ('SHORT', 'SELL') and nas_pct < -0.5:
        why = f'Short aligned with NQ {nas_pct:.1f}% — momentum favors the direction.'
    elif session == 'NEW_YORK_CASH':
        why = 'NY cash session — signal quality elevated by timing.'
    else:
        why = f"Confidence reflects {macro} macro risk, Tier {tier}, {session.lower().replace('_', ' ')} session."

    # ── execution ─────────────────────────────────────────────
    if trap_risk:
        execution = 'Stand aside — HARVEY flagged a trap. Do not enter until trap_risk clears.'
    elif event_phase in ('LIVE', 'IMMINENT'):
        execution = 'Reduce size or stand aside until event resolves. Price confirmation required.'
    elif sig['label'].startswith('MAJOR'):
        execution = 'Respect leadership. Do not fade strength in a major session expansion.'
    elif macro == 'high':
        execution = 'Keep size controlled. Event risk can reverse moves quickly.'
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

    # ── execution trace: VERDICT stage ────────────────────────
    try:
        import services.execution_trace as _trace
        _trace.log_execution_event('VERDICT', data, {
            'verdict':    verdict,
            'confidence': confidence,
            'macro_risk': macro,
            'session':    session,
            'trap_risk':  data.get('trap_risk', 'false'),
            'tier':       data.get('tier', ''),
        })
    except Exception:
        pass

    if should_send_trade_to_telegram(parsed):
        header_lines = [
            f'Instrument: {instrument}' if instrument else '',
            f'Tier: {tier} | Setup: {setup_type}' if (tier or setup_type) else '',
            f'ICT Step: {ict_step}' if ict_step else '',
            f'Brain: {brain_state}'  if brain_state else '',
            'TRAP RISK: YES — SKIP forced' if trap_risk else '',
        ]
        header_block = '\n'.join(l for l in header_lines if l)

        send_telegram_message(
            f"NOVA // {data['ticker']} // {data['signal']}\n"
            f"{data['session']} | TF {data['timeframe']} | Price {data['price']}\n"
            + (f'{header_block}\n' if header_block else '') +
            f'\nVerdict: {parsed["verdict"]}\nConfidence: {parsed["confidence"]}\n'
            f'Why: {parsed["why"]}\nRisk: {parsed["risk"]}\n'
            f'Execution: {parsed["execution"]}\nSummary: {parsed["summary"]}'
        )

    return {'status': 'ok', 'data': data, 'parsed': parsed}
