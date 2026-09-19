"""Explain checked plans without changing scheduling or protection semantics."""
from collections import defaultdict
import hashlib
import json

VERSION = 'ps1-planner-0.1.0'
SCOPE = 'Planning review only. Full protection and official acceptance remain unverified; this is not track-entry authorisation.'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def snapshot(view, files):
    names = ('RESULTS.csv', 'SCHEDULE_ACCESS.csv', 'SCHEDULE_OCCUPANCY.csv')
    identity = {'input_data_sha256': view['input_identity'], 'scenario': view['scenario'],
                'rule_profile': view['rule_profile'], 'source_sha256': view['source_sha256'],
                'schedule_sha256': {n: hashlib.sha256(files[n]).hexdigest() for n in names if n in files}}
    if view.get('planning_context'):
        identity['planning_context'] = view['planning_context']
    return {'version': digest(identity), **identity}


def summary(view):
    report = (view.get('validation') or {}).get('report') or {}
    m = report.get('metrics') or {}
    diag = report.get('physical_night_diagnostic') or {}
    violations = sum(f['severity'] in ('error', 'violation') for f in report.get('findings', []))
    assigned = diag.get('status') == 'ASSIGNED_FOR_MODELLED_RELATIONS'
    c_check = None
    if view['scenario'] == 'C' and m and not violations:
        from .optimizer import window_check
        c_check = window_check(view['model'], view['tables'])
    ready = bool(m.get('all_work_complete') and not violations and assigned
                 and (view['scenario'] != 'C' or (c_check and c_check['passed'])))
    workload = m.get('workload')
    return {'status': 'CHECKED_MODEL_PLAN' if ready else 'REVIEW_REQUIRED' if view['tables'] is not None else 'NO_SCHEDULE',
            'checked_model_plan': ready, 'full_feasibility_established': False,
            'official_validation': 'NOT_RUN', 'operational_authorisation': False,
            'required_activities': len(view['model']['activities']),
            'complete_activities': sum(w['complete'] for w in workload) if workload is not None else None,
            'covered_units': sum(min(w['required_scaled'], w['delivered_scaled']) for w in workload)/2 if workload is not None else None,
            'required_units': sum(a['workload_units_scaled'] for a in view['model']['activities'])/2,
            'activity_delay_days': m.get('activity_delay_days'), 'contract_delay_days': m.get('contract_delay_days'),
            'weighted_delay': m['activity_weighted_delay_tenths']/10 if m.get('activity_weighted_delay_tenths') is not None else None,
            'eclo_accesses': m.get('eclo_activity_accesses'), 'excess_slots': m.get('excess_location_week_units'),
            'score': m['score_tenths']/10 if m.get('score_tenths') is not None else None,
            'weekly_violations': violations if report else None,
            'night_conflict_weeks': sum(w['status'] == 'INCONSISTENT_UNDER_ASSUMPTIONS' for w in diag.get('weeks', [])) if diag else None,
            'night_status': diag.get('status', 'NOT_EVALUATED'), 'c_window_check': c_check,
            'completion_date': max((w['completion_date'] for w in workload), default=None) if m.get('all_work_complete') else None}


def conflicts(view):
    report = (view.get('validation') or {}).get('report') or {}
    result = []
    for f in report.get('findings', []):
        actionable = f['severity'] in ('violation', 'error')
        result.append({'id': 'weekly-'+digest(f)[:16], 'kind': 'weekly', 'rule': f['rule_id'],
                       'title': f['code'].replace('_', ' ').capitalize(), 'explanation': f['message'],
                       'week': f.get('week'), 'activities': f.get('activities', []),
                       'location_id': f.get('location_id'), 'observed': f.get('observed'), 'expected': f.get('expected'),
                       'actionable': actionable, 'evidence': f,
                       'proposal': 'Reschedule and regroup the complete plan under the same scenario, then check every activity and location.' if actionable else
                       'Clarification or further evidence is required. A replacement schedule cannot certify this unresolved rule.'})
    for w in (report.get('physical_night_diagnostic') or {}).get('weeks', []):
        for c in w['conflicts']:
            kind = c['kind']
            if kind == 'equal_and_different_night':
                links = c.get('equality_path', [])
                chain = ' â†’ '.join(e.get('location_id') or f"{e.get('contract')} local index {e.get('access_night')}" for e in links)
                reason = c['inequality']
                different = reason.get('location_id') or reason.get('contract') or reason['basis'].replace('_', ' ')
                explanation = f"{' and '.join(c['activities'])} must share one night through {chain}, but must also use different nights at {different}. Both requirements cannot hold together under the full-night assumption."
            elif kind == 'simultaneous_workfront_excess':
                explanation = f"{c['contract']} has {c['observed']} activities linked to one night, but only {c['limit']} workfronts. Split their night assignments or move some work to another week."
            else:
                explanation = c.get('explanation', 'These modelled relations do not fit the available abstract night labels.')
            result.append({'id': 'night-'+digest([w['week'], c])[:16], 'kind': 'night', 'rule': 'R10',
                           'title': kind.replace('_', ' ').capitalize(), 'explanation': explanation,
                           'week': w['week'], 'activities': c.get('activities', []), 'evidence': c,
                           'actionable': True,
                           'proposal': 'Search for consistent sharing groups and weeks across the whole plan. Other allocations may change; no minimum-change guarantee is made.'})
        if w['status'] in ('UNKNOWN_SEARCH_LIMIT', 'INTERNAL_ERROR'):
            result.append({'id': f"night-status-{w['week']}", 'kind': 'night', 'rule': 'R10',
                           'title': 'Night assignment not established', 'explanation': 'The diagnostic did not establish a night assignment; this is not proof of a conflict.',
                           'week': w['week'], 'activities': [], 'actionable': True, 'evidence': {'status': w['status']},
                           'proposal': 'Search for a complete replacement and check its night assignment independently.'})
    c_check = summary(view)['c_window_check'] if view['scenario'] == 'C' else None
    if c_check and not c_check['passed']:
        result.append({'id': 'model-c-window', 'kind': 'construction_policy', 'rule': 'MODEL_C_WINDOW',
                       'title': 'Conservative C line-window policy', 'week': None,
                       'activities': sorted({r['activity_id'] for r in view['tables']['SCHEDULE_ACCESS.csv'] if r['eclo']}),
                       'explanation': 'The local working-line checks pass, but the disclosed C model applies each Live ECLO access to every input line. These weeks do not fit that stronger two-week policy. This is not an organiser-confirmed affected-line map.',
                       'actionable': True, 'evidence': c_check,
                       'proposal': 'Search under the unchanged conservative C construction policy and show the actual allocation and cost changes.'})
    # Repeated witnesses need not create repeated actions.
    return list({c['id']: c for c in result}.values())


def allocation_details(view):
    """Compare relations, not arbitrary CSV group names or local night labels."""
    tables = view['tables'] or {}
    groups, indices = defaultdict(set), defaultdict(set)
    activities = {a['activity_id']: a for a in view['model']['activities']}
    for r in tables.get('SCHEDULE_OCCUPANCY.csv', []):
        groups[r['week'], r['location_id'], r['co_share_group']].add(r['activity_id'])
    for r in tables.get('SCHEDULE_ACCESS.csv', []):
        a = activities.get(r['activity_id'])
        if a:
            indices[(*a['project_key'], r['week'], r['access_night'])].add(r['activity_id'])
    details = {a: {'accesses': [], 'sharing': [], 'same_project_night': []} for a in activities}
    for r in tables.get('SCHEDULE_ACCESS.csv', []):
        d = details.setdefault(r['activity_id'], {'accesses': [], 'sharing': [], 'same_project_night': []})
        d['accesses'].append({'week': r['week'], 'eclo': r['eclo']})
    for (week, location, _), members in groups.items():
        for a in members:
            if a in details:
                details[a]['sharing'].append({'week': week, 'location_id': location, 'partners': sorted(members-{a})})
    for (_, _, week, _), members in indices.items():
        for a in members:
            details[a]['same_project_night'].append({'week': week, 'partners': sorted(members-{a})})
    for d in details.values():
        for key in d:
            d[key].sort(key=lambda r: (r['week'], json.dumps(r, sort_keys=True)))
    return details


def activity_contexts(view):
    allocations = allocation_details(view)
    locations = {l['location_id'] for l in view['model']['locations']}
    result = {}
    for a in view['model']['activities']:
        mirrors = []
        if a['nature_of_works'] == 'Live':
            for loc in a['working_span']['location_ids']:
                stem, bound = loc.rsplit(':', 1)
                mirror = stem+(':WB' if bound == 'EB' else ':EB')
                if mirror in locations:
                    mirrors.append(mirror)
        result[a['activity_id']] = {'sharing': [r for r in allocations[a['activity_id']]['sharing'] if r['partners']],
                                   'known_live_mirror_core': sorted(set(mirrors)),
                                   'protection_status': 'UNVERIFIED',
                                   'protection_note': 'Known opposite-bound working-core separation only; complete buffers, mirror extent and interchange propagation are unresolved.'}
    return result


def compare(before, after, *, disruption=False):
    same_inputs = before['input_identity'] == after['input_identity']
    same_rules = before['rule_profile'] == after['rule_profile']
    same_code = before['source_sha256'] == after['source_sha256']
    same_context = before.get('planning_context') == after.get('planning_context')
    if not (same_rules and same_code and ((same_inputs and same_context) or disruption)):
        raise ValueError('Comparison requires identical input bytes, rule evidence and implementation fingerprints. Import both schedules in the same current session.')
    if before['tables'] is None or after['tables'] is None:
        raise ValueError('Comparison requires two schedules. A solver outcome without a schedule is not an alternative.')
    b, a = summary(before), summary(after)
    bm = ((before['validation'] or {}).get('report') or {}).get('metrics') or {}
    am = ((after['validation'] or {}).get('report') or {}).get('metrics') or {}
    completions = [{r['activity_id']: r for r in m.get('workload', [])} for m in (bm, am)]
    plans = [allocation_details(v) for v in (before, after)]
    changes = []
    for id in sorted(set(plans[0]) | set(plans[1])):
        old, new = plans[0].get(id), plans[1].get(id)
        if old != new:
            reasons = [key for key in ('accesses', 'sharing', 'same_project_night') if (old or {}).get(key) != (new or {}).get(key)]
            changes.append({'activity_id': id, 'changed': reasons, 'before': old, 'after': new,
                            'before_completion': completions[0].get(id, {}).get('completion_date'),
                            'after_completion': completions[1].get(id, {}).get('completion_date')})
    same_scenario = before['scenario'] == after['scenario']
    numbers = ('complete_activities', 'covered_units', 'activity_delay_days', 'contract_delay_days',
               'weighted_delay', 'eclo_accesses', 'excess_slots', 'weekly_violations', 'night_conflict_weeks')
    deltas = {key: a[key]-b[key] if a[key] is not None and b[key] is not None else None for key in numbers}
    # Subtract exact integer tenths before converting for display.
    for output, metric in (('weighted_delay', 'activity_weighted_delay_tenths'), ('score', 'score_tenths')):
        deltas[output] = (am[metric]-bm[metric])/10 if am.get(metric) is not None and bm.get(metric) is not None else None
    comparable = same_scenario and same_inputs and same_context
    if not comparable:
        deltas['score'] = None
    return {'version': VERSION, 'base_run_id': before['id'], 'candidate_run_id': after['id'],
            'base_snapshot': before['schedule_snapshot'], 'candidate_snapshot': after['schedule_snapshot'],
            'same_inputs': same_inputs, 'same_rules': same_rules, 'same_implementation': same_code,
            'same_scenario': same_scenario, 'same_planning_context':same_context, 'scores_comparable': comparable,
            'comparison_note': 'Changed requirements or planning constraints: component differences describe consequences, not a fair score improvement.' if disruption else 'Same scenario; scores are provisional arithmetic and do not establish full feasibility.' if same_scenario else
            'Different scenario policies: compare the components, not the aggregate scores. No score delta or ranking is meaningful across these objectives.',
            'before': b, 'after': a, 'deltas': deltas, 'changed_activity_count': len(changes),
            'changes': changes, 'before_contracts': bm.get('contracts'), 'after_contracts': am.get('contracts'), 'scope': SCOPE}
