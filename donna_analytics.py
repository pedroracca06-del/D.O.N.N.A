from donna_state import load_journal
from datetime import datetime


def validate_trade(trade: dict) -> dict:
    """Re-derive outcome and pnl mathematically. Flag any inconsistencies."""
    try:
        direction      = str(trade.get('direction', '')).upper()
        entry          = float(trade.get('entry_price') or 0)
        exit_          = float(trade.get('exit_price') or 0)
        size           = float(trade.get('size') or 1)
        stored_pnl     = float(trade.get('realized_pnl') or trade.get('pnl') or 0)
        stored_outcome = str(trade.get('outcome', ''))

        if not direction or not entry or not exit_:
            return {'valid': False, 'reason': 'missing_fields'}

        if direction == 'LONG':
            correct_pnl = round((exit_ - entry) * size, 2)
        elif direction == 'SHORT':
            correct_pnl = round((entry - exit_) * size, 2)
        else:
            return {'valid': False, 'reason': 'unknown_direction'}

        correct_outcome = 'WIN' if correct_pnl > 0 else ('LOSS' if correct_pnl < 0 else 'BREAKEVEN')

        pnl_mismatch     = abs(correct_pnl - stored_pnl) > 0.01
        outcome_mismatch = correct_outcome != stored_outcome

        return {
            'valid':            not pnl_mismatch and not outcome_mismatch,
            'correct_pnl':      correct_pnl,
            'stored_pnl':       stored_pnl,
            'correct_outcome':  correct_outcome,
            'stored_outcome':   stored_outcome,
            'pnl_mismatch':     pnl_mismatch,
            'outcome_mismatch': outcome_mismatch,
        }
    except Exception as e:
        return {'valid': False, 'reason': str(e)}


def compute_analytics() -> dict:
    """Full analytics over closed trades only. Only valid trades enter analytics buckets."""
    closed = [t for t in load_journal() if t.get('outcome') in ('WIN', 'LOSS', 'BREAKEVEN')]

    if not closed:
        return {'status': 'no_closed_trades', 'trade_count': 0}

    valid_trades   = []
    invalid_trades = []
    for t in closed:
        result = validate_trade(t)
        if result.get('valid'):
            valid_trades.append(t)
        else:
            invalid_trades.append({
                'signal_id': t.get('signal_id', ''),
                'ticker':    t.get('ticker', ''),
                'trade_date': t.get('trade_date', ''),
                'reason':    result.get('reason', ''),
                'pnl_mismatch':     result.get('pnl_mismatch'),
                'outcome_mismatch': result.get('outcome_mismatch'),
                'stored_pnl':       result.get('stored_pnl'),
                'correct_pnl':      result.get('correct_pnl'),
                'stored_outcome':   result.get('stored_outcome'),
                'correct_outcome':  result.get('correct_outcome'),
            })

    integrity_report = {
        'total_closed':   len(closed),
        'valid':          len(valid_trades),
        'invalid':        len(invalid_trades),
        'invalid_trades': invalid_trades,
    }

    trades = valid_trades

    if not trades:
        return {'status': 'no_valid_trades', 'trade_count': 0, 'integrity_report': integrity_report}

    def bucket(trades_list, key_fn, label):
        buckets = {}
        for t in trades_list:
            k = key_fn(t) or 'UNKNOWN'
            if k not in buckets:
                buckets[k] = {'wins': 0, 'losses': 0, 'breakevens': 0, 'pnl': 0.0, 'trades': 0}
            b = buckets[k]
            b['trades'] += 1
            outcome = t.get('outcome', '')
            pnl = float(t.get('realized_pnl') or t.get('pnl') or 0)
            b['pnl'] = round(b['pnl'] + pnl, 2)
            if outcome == 'WIN':
                b['wins'] += 1
            elif outcome == 'LOSS':
                b['losses'] += 1
            else:
                b['breakevens'] += 1
        for b in buckets.values():
            t_ = b['wins'] + b['losses'] + b['breakevens']
            b['win_rate'] = round(b['wins'] / t_ * 100, 1) if t_ else 0.0
            b['avg_pnl'] = round(b['pnl'] / t_, 2) if t_ else 0.0
        return buckets

    def conf_bucket(t):
        try:
            c = float(t.get('confidence') or t.get('harvey_confidence') or 0)
            if c >= 90: return '90+'
            if c >= 80: return '80-89'
            if c >= 70: return '70-79'
            if c >= 60: return '60-69'
            return '<60'
        except Exception:
            return 'UNKNOWN'

    total      = len(trades)
    wins       = sum(1 for t in trades if t.get('outcome') == 'WIN')
    losses     = sum(1 for t in trades if t.get('outcome') == 'LOSS')
    breakevens = sum(1 for t in trades if t.get('outcome') == 'BREAKEVEN')
    total_pnl  = round(sum(float(t.get('realized_pnl') or t.get('pnl') or 0) for t in trades), 2)
    win_rate   = round(wins / total * 100, 1) if total else 0.0

    win_pnls  = [float(t.get('realized_pnl') or t.get('pnl') or 0) for t in trades if t.get('outcome') == 'WIN']
    loss_pnls = [float(t.get('realized_pnl') or t.get('pnl') or 0) for t in trades if t.get('outcome') == 'LOSS']
    avg_win   = round(sum(win_pnls)  / len(win_pnls),  2) if win_pnls  else 0.0
    avg_loss  = round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0.0
    expectancy = round((win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss), 2)

    return {
        'status':             'ok',
        'trade_count':        total,
        'wins':               wins,
        'losses':             losses,
        'breakevens':         breakevens,
        'win_rate':           win_rate,
        'total_pnl':          total_pnl,
        'avg_win':            avg_win,
        'avg_loss':           avg_loss,
        'expectancy':         expectancy,
        'by_strategy_family': bucket(trades, lambda t: t.get('strategy_family'), 'strategy_family'),
        'by_setup_type':      bucket(trades, lambda t: t.get('setup_type'), 'setup_type'),
        'by_session':         bucket(trades, lambda t: t.get('session'), 'session'),
        'by_regime':          bucket(trades, lambda t: t.get('active_regime') or t.get('regime'), 'regime'),
        'by_direction':       bucket(trades, lambda t: t.get('direction'), 'direction'),
        'by_confidence':      bucket(trades, conf_bucket, 'confidence'),
        'by_ticker':          bucket(trades, lambda t: t.get('ticker'), 'ticker'),
        'orchestration_stats': {
            'total_blocked': 0,
            'note': 'blocked_signals_today in state engine — resets daily',
        },
        'integrity_report': integrity_report,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
    }
