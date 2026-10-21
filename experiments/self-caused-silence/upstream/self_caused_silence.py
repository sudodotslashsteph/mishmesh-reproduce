#!/usr/bin/env python3
"""
Self-caused silence: a minimal, exact, standard-library model.

A monitor watches for proof-of-life responses. Missing responses are counted as
evidence ("debt"). At enough debt it performs an irreversible action ("release").
Separately, at lower debt it may take a protective intervention ("lock") that
can obstruct the very channel it is watching.

Part A  Opportunity, not uptime.  Exhaustive enumeration, independent
        re-implementation of quorum-review/causal-recovery/silence_experiment.py.
Part B  Self-confirming suspicion.  Exact dynamic programming over a Markov chain,
        comparing accounting rules when an intervention can block the channel.

Everything is exact (no sampling). Run:  python3 self_caused_silence.py
Writes results.json next to this file. Python 3.8+, no dependencies.
"""
from itertools import product
import json, os

# ----------------------------------------------------------------------------
# Part A: opportunity, not uptime
# ----------------------------------------------------------------------------
# Two routes A and B. Each tick, the set of open routes is {A}, {B} or {A,B}
# (some route is ALWAYS open). A challenge window lasts W=4 ticks. A living,
# always-ready endpoint answers iff some ANNOUNCED route is open for R=2
# consecutive ticks inside the window (interruption discards progress).
# A dead endpoint never answers. Two consecutive windows; release iff both are
# unanswered AND both are credited by the accounting policy.

W, R = 4, 2
SYMBOLS = ({'A'}, {'B'}, {'A', 'B'})
ANNOUNCEMENTS = ({'A'}, {'A', 'B'})

def usable(window, announced):
    """True iff some announced route has an uninterrupted run of R ticks."""
    for route in announced:
        run = 0
        for open_set in window:
            run = run + 1 if route in open_set else 0
            if run >= R:
                return True
    return False

POLICIES = {
    # credit an unanswered window when ...
    'timeout':               lambda w, ann: True,
    'any_route_open_at_end': lambda w, ann: len(w[-1]) > 0,
    'announced_open_at_end': lambda w, ann: bool(w[-1] & ann),
    'certified_opportunity': lambda w, ann: usable(w, ann),
}

def part_a():
    out = {}
    windows = list(product(SYMBOLS, repeat=W))
    for name, credit in POLICIES.items():
        living_rel = dead_rel = unearned = 0
        for ann in ANNOUNCEMENTS:
            for w1 in windows:
                for w2 in windows:
                    # living endpoint
                    answered = [usable(w, ann) for w in (w1, w2)]
                    credits = [(not a) and credit(w, ann) for a, w in zip(answered, (w1, w2))]
                    unearned += sum(credits)          # every living credit is unearned
                    if all(credits):
                        living_rel += 1
                    # dead endpoint: never answers
                    if credit(w1, ann) and credit(w2, ann):
                        dead_rel += 1
        n = len(ANNOUNCEMENTS) * len(windows) ** 2
        out[name] = dict(cases=n, living_releases=living_rel,
                         unearned_credits=unearned, dead_releases=dead_rel)
    # the AABB vs ABAB pair: equal per-route uptime, different usability
    A, B = {'A'}, {'B'}
    out['_pair'] = {
        'AABB': dict(uptime_A=2, uptime_B=2, usable=usable((A, A, B, B), {'A', 'B'})),
        'ABAB': dict(uptime_A=2, uptime_B=2, usable=usable((A, B, A, B), {'A', 'B'})),
    }
    return out

# ----------------------------------------------------------------------------
# Part B: self-confirming suspicion
# ----------------------------------------------------------------------------
# Discrete check-in windows (think: days). Each window the subject gets one
# chance to respond.
#
# Exogenous unreachability: a two-state Markov chain (reachable / unreachable).
#   enter = P(reachable -> unreachable), stay = P(unreachable -> unreachable).
#   stay == enter gives independent windows; stay > enter gives bursts
#   (trips, illness, outages) with mean length 1/(1-stay).
#
# Monitor state: debt c (credited misses this episode), lock (windows left),
# locked_once (has this episode already locked?).
#   - A response resets the episode: c = 0, lock lifted.
#   - When c reaches K_LOCK, the monitor locks the ordinary response channel for
#     ELL windows (edge-triggered: once per episode; ELL = None means "until
#     the subject responds").
#   - While locked, the subject can still recover through an alternate path
#     with probability RHO per window (if exogenously reachable).
#   - Release (irreversible) when c reaches M.
#
# Accounting rules for a missed window:
#   naive       credit every miss.
#   censored    do not credit a miss in a window the monitor's OWN lock
#               obstructed (the monitor knows its own actions). Exogenous misses
#               are still credited: the monitor cannot tell them from death.
#   reserved    the lock never obstructs proof-of-life (a "half-open" slot is
#               kept each window); every miss is an ordinary miss.
# 'nolock' is the baseline monitor with no intervention at all.

POLICY_NAMES = ('nolock', 'naive', 'censored', 'reserved')

def step_living(dist, policy, p_enter, p_stay, K_LOCK, M, ELL, RHO):
    """One window of a living subject. dist maps state->prob; state =
    (unreachable, c, lock_left, locked_once). Returns (new_dist, p_released_now)."""
    new, released = {}, 0.0
    def add(s, pr):
        new[s] = new.get(s, 0.0) + pr
    for (u, c, lock, once), pr in dist.items():
        # exogenous state for this window
        p_u = p_stay if u else p_enter
        for unreach, pu in ((1, p_u), (0, 1 - p_u)):
            q = pr * pu
            if q == 0:
                continue
            locked = lock != 0 and policy != 'nolock'
            obstructs = locked and policy != 'reserved'
            # can the subject respond this window?
            if unreach:
                outcomes = ((False, 1.0),)
            elif not obstructs:
                outcomes = ((True, 1.0),)
            else:  # ordinary channel blocked by our own lock; alternate path?
                outcomes = ((True, RHO), (False, 1 - RHO))
            for responded, po in outcomes:
                qq = q * po
                if qq == 0:
                    continue
                if responded:
                    add((unreach, 0, 0, 0), qq)
                    continue
                credit = not (policy == 'censored' and obstructs)
                c2 = c + 1 if credit else c
                if c2 >= M:
                    released += qq
                    continue
                # lock bookkeeping
                lock2 = lock
                if lock2 not in (0, None) and lock2 > 0:
                    lock2 -= 1
                once2 = once
                if policy != 'nolock' and not once and c2 >= K_LOCK:
                    lock2, once2 = (-1 if ELL is None else ELL), 1
                add((unreach, c2, lock2, once2), qq)
    return new, released

def living_outcomes(policy, p_enter, p_stay, K_LOCK, M, ELL, RHO, H):
    """For a subject alive throughout H windows: P(released), P(still locked
    out at the end), and expected number of windows spent locked."""
    # stationary start for the exogenous chain
    pi_u = p_enter / (1 - p_stay + p_enter) if (1 - p_stay + p_enter) > 0 else 0
    dist = {(1, 0, 0, 0): pi_u, (0, 0, 0, 0): 1 - pi_u}
    total, locked_windows = 0.0, 0.0
    for _ in range(H):
        dist, r = step_living(dist, policy, p_enter, p_stay, K_LOCK, M, ELL, RHO)
        total += r
        if policy != 'nolock':
            locked_windows += sum(pr for (u, c, lock, once), pr in dist.items() if lock != 0)
    locked_end = sum(pr for (u, c, lock, once), pr in dist.items() if lock != 0) if policy != 'nolock' else 0.0
    return dict(released=total, locked_at_end=locked_end, mean_locked_windows=locked_windows)

def living_false_release(*args):
    return living_outcomes(*args)['released']

def dead_release_delay(policy, K_LOCK, M, ELL, horizon=10_000):
    """Windows from death (fresh episode) to release. Dead subjects never
    respond or recover, so this is deterministic. None = never released."""
    c, lock, once = 0, 0, False
    for t in range(1, horizon + 1):
        locked = lock != 0 and policy != 'nolock'
        obstructs = locked and policy != 'reserved'
        credit = not (policy == 'censored' and obstructs)
        if credit:
            c += 1
        if c >= M:
            return t
        if lock > 0:
            lock -= 1
        if policy != 'nolock' and not once and c >= K_LOCK:
            lock, once = (-1 if ELL is None else ELL), True
    return None

def dead_delay_level_triggered(K_LOCK, M, ELL, horizon=10_000):
    """Negative control: censored accounting with a LEVEL-triggered lock
    (re-lock whenever c >= K_LOCK and unlocked). Demonstrates a permanent stall."""
    c, lock = 0, 0
    for t in range(1, horizon + 1):
        obstructs = lock > 0
        if not obstructs:
            c += 1
        if c >= M:
            return t
        if lock > 0:
            lock -= 1
        if lock == 0 and c >= K_LOCK:
            lock = ELL
    return None

def part_b():
    H = 365
    out = {'horizon_windows': H}

    # S1: stylized threshold erasure. Lock at the FIRST credited miss, lasting
    # until the subject responds, no alternate path. Independent windows.
    K, M, ELL, RHO = 1, 3, None, 0.0
    ps = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1]
    s1 = {'K_LOCK': K, 'M': M, 'ELL': ELL, 'RHO': RHO, 'p': ps}
    for pol in POLICY_NAMES:
        o = [living_outcomes(pol, p, p, K, M, ELL, RHO, H) for p in ps]
        s1[pol] = {'released': [x['released'] for x in o],
                   'locked_at_end': [x['locked_at_end'] for x in o],
                   'mean_locked_windows': [x['mean_locked_windows'] for x in o]}
    s1['dead_release_delay'] = {pol: dead_release_delay(pol, K, M, ELL) for pol in POLICY_NAMES}
    s1['closed_form_check'] = {
        'naive_dp_p0.05': s1['naive']['released'][ps.index(0.05)],
        'naive_closed_form_p0.05': 1 - (1 - 0.05) ** (H - 2)}
    out['S1_threshold_erasure'] = s1

    # S2: daily check-ins with bursty unreachability (trips, illness, outages):
    # a burst starts with prob 0.01/day, mean length 5 days. Release after 30
    # credited missed days; lock after 7, lasting 30 days. Sweep how often the
    # alternate recovery path works while locked.
    K, M, ELL = 7, 30, 30
    pe, pst = 0.01, 0.8
    rhos = [0.0, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0]
    s2 = {'K_LOCK': K, 'M': M, 'ELL': ELL, 'p_enter': pe, 'p_stay': pst, 'rho': rhos}
    for pol in POLICY_NAMES:
        o = [living_outcomes(pol, pe, pst, K, M, ELL, r, H) for r in rhos]
        s2[pol] = {'released': [x['released'] for x in o],
                   'locked_at_end': [x['locked_at_end'] for x in o],
                   'mean_locked_windows': [x['mean_locked_windows'] for x in o]}
    s2['dead_release_delay'] = {pol: dead_release_delay(pol, K, M, ELL) for pol in POLICY_NAMES}
    out['S2_daily_bursty'] = s2

    # Property checks over a grid (independent windows): reserved == nolock,
    # censored <= nolock, naive >= nolock.
    viol = []
    for p in (0.01, 0.05, 0.2):
        for (K, M, ELL, RHO) in ((1, 3, None, 0.0), (2, 4, 3, 0.3), (3, 7, 14, 0.5), (1, 5, 2, 0.0)):
            v = {pol: living_false_release(pol, p, p, K, M, ELL, RHO, 200) for pol in POLICY_NAMES}
            if abs(v['reserved'] - v['nolock']) > 1e-12: viol.append(('reserved!=nolock', p, K, M, ELL, RHO, v))
            if v['censored'] > v['nolock'] + 1e-12: viol.append(('censored>nolock', p, K, M, ELL, RHO, v))
            if v['naive'] < v['nolock'] - 1e-12: viol.append(('naive<nolock', p, K, M, ELL, RHO, v))
    out['property_checks_independent_windows'] = {'cases': 12, 'violations': viol}

    # Negative control: censored accounting + LEVEL-triggered lock never
    # releases a dead subject.
    out['negative_control_level_triggered_censored_dead_delay'] = \
        dead_delay_level_triggered(K_LOCK=7, M=30, ELL=30)
    return out

# ----------------------------------------------------------------------------
if __name__ == '__main__':
    res = {'part_a': part_a(), 'part_b': part_b()}
    here = os.path.dirname(os.path.abspath(__file__))
    def tidy(x):  # 12 significant figures: stable across Python versions/platforms
        if isinstance(x, float): return float(f'{x:.12g}')
        if isinstance(x, dict): return {k: tidy(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [tidy(v) for v in x]
        return x
    with open(os.path.join(here, 'results.json'), 'w') as f:
        json.dump(tidy(res), f, indent=1)
    a = res['part_a']
    print('Part A  (13,122 living + 13,122 dead cases per policy)')
    for k in POLICIES:
        print(f"  {k:24s} living releases {a[k]['living_releases']:5d}   "
              f"unearned credits {a[k]['unearned_credits']:5d}   dead releases {a[k]['dead_releases']:5d}")
    print('  AABB usable:', a['_pair']['AABB']['usable'], '  ABAB usable:', a['_pair']['ABAB']['usable'])
    b = res['part_b']
    s1 = b['S1_threshold_erasure']
    print(f"\nPart B / S1  lock at first miss until response, M=3, independent windows, {b['horizon_windows']} windows")
    print('   p      ' + '  '.join(f'{pol:>10s}' for pol in POLICY_NAMES) + '   (P living released)')
    for i, p in enumerate(s1['p']):
        print(f'  {p:<7}' + '  '.join(f"{s1[pol]['released'][i]:10.2e}" for pol in POLICY_NAMES)
              + f"   censored: P(locked out at end)={s1['censored']['locked_at_end'][i]:.3f}")
    print('  dead delay:', s1['dead_release_delay'], ' closed-form check:', s1['closed_form_check'])
    s2 = b['S2_daily_bursty']
    print(f"\nPart B / S2  daily, bursts mean 5d, lock at 7 for 30d, release at 30")
    print('   rho    ' + '  '.join(f'{pol:>10s}' for pol in POLICY_NAMES) + '   | mean locked days: naive censored reserved')
    for i, r in enumerate(s2['rho']):
        print(f'  {r:<7}' + '  '.join(f"{s2[pol]['released'][i]:10.2e}" for pol in POLICY_NAMES)
              + '   | ' + '  '.join(f"{s2[pol]['mean_locked_windows'][i]:6.1f}" for pol in ('naive','censored','reserved')))
    print('  dead delay:', s2['dead_release_delay'])
    print('  property checks:', b['property_checks_independent_windows'])
    print('  negative control (level-triggered lock + censoring) dead delay:',
          b['negative_control_level_triggered_censored_dead_delay'])
