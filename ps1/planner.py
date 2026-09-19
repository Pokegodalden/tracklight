"""Explain checked plans without changing scheduling or protection semantics."""
from collections import defaultdict
import hashlib
import json

from .validator import (ACTIVITY_PRIORITY_WEIGHT, CONTRACT_PRIORITY_WEIGHT,
                        ECLO_ACCESS_TENTHS, EXCESS_SLOT_TENTHS)

VERSION = 'ps1-planner-0.1.0'
SCOPE = 'Planning review only. Full protection and official acceptance remain unverified; this is not track-entry authorisation.'
ZERO_MEANS = ('A score of 0 would mean every contract finishes on or before its planned date, '
              'with no week needing more track access than its nominal supply and no engineering '
              'hours used. It is the ideal, not a promise that any particular instance can reach it.')
UNVERIFIED_PROTECTION = ('Buffer distances, opposite-bound extent and interchange effects are not yet '
                         'configured (rules R12, R15, R17). An engineer must confirm protection before track entry.')


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


def score_components(view):
    """Split the checked score into the terms the active scenario actually charges."""
    m = ((view.get('validation') or {}).get('report') or {}).get('metrics') or {}
    scenario = view['scenario']
    delay, excess, eclo = (m.get('activity_weighted_delay_tenths'), m.get('excess_location_week_units'),
                           m.get('eclo_activity_accesses'))
    charged = [
        {'key': 'delay', 'label': 'Late completion',
         'tenths': delay if delay is not None else None, 'charged': scenario != 'B',
         'quantity': m.get('activity_delay_days'), 'unit': 'activity-days late',
         'explanation': 'Each late day is weighted by contract priority (priority 1 counts '
                        f"{CONTRACT_PRIORITY_WEIGHT[1]//CONTRACT_PRIORITY_WEIGHT[3]} times priority 3) "
                        'and again by activity priority.'},
        {'key': 'excess', 'label': 'Track access above nominal supply',
         'tenths': EXCESS_SLOT_TENTHS*excess if excess is not None else None, 'charged': scenario != 'A',
         'quantity': excess, 'unit': 'extra location-weeks',
         'explanation': f'Each location/week used beyond its nominal supply costs {EXCESS_SLOT_TENTHS/10:.1f}.'},
        {'key': 'eclo', 'label': 'Engineering hours (ECLO)',
         'tenths': ECLO_ACCESS_TENTHS*eclo if eclo is not None else None, 'charged': scenario != 'A',
         'quantity': eclo, 'unit': 'ECLO accesses',
         'explanation': f'Each ECLO access costs {ECLO_ACCESS_TENTHS/10:.1f}.'},
    ]
    total = m.get('score_tenths')
    for item in charged:
        counted = item['tenths'] if item['charged'] and item['tenths'] is not None else 0
        item['counted_tenths'] = counted
        item['value'] = counted/10
        item['share'] = counted/total if total else 0.0
        if not item['charged']:
            item['explanation'] = f'Scenario {scenario} does not charge this term. ' + item['explanation']
    return charged


def score_explanation(view):
    """Anchor the score against 0 and against the solver's proven floor for this instance."""
    m = ((view.get('validation') or {}).get('report') or {}).get('metrics') or {}
    optimisation = view.get('optimisation') or {}
    total, bound = m.get('score_tenths'), optimisation.get('best_bound_tenths')
    components = score_components(view)
    drivers = [c for c in components if c['counted_tenths'] > 0]
    drivers.sort(key=lambda c: -c['counted_tenths'])
    if total is None:
        headline = 'No score yet. A score is only calculated once every activity has its full workload scheduled.'
    elif not drivers:
        headline = 'This plan scores 0: nothing is late and no extra track access or engineering hours were needed.'
    else:
        headline = 'This plan scores {:.1f}, driven by {}.'.format(
            total/10, ' and '.join(c['label'].lower() for c in drivers))
    return {'total_tenths': total, 'total': total/10 if total is not None else None,
            'headline': headline, 'zero_means': ZERO_MEANS, 'components': components,
            'best_possible_tenths': bound, 'best_possible': bound/10 if bound is not None else None,
            'at_best_possible': bool(total is not None and bound is not None and total == bound),
            'zero_ruled_out': bool(bound is not None and bound > 0),
            'best_possible_note': (
                None if bound is None else
                'The solver proved that no plan for these inputs can score below {:.1f}, so 0 is not reachable here.'.format(bound/10)
                if bound > 0 else
                'The solver could not rule out a score of 0 for these inputs.'),
            'scenario_note': {
                'A': 'Scenario A charges lateness only. It forbids ECLO and allows no track access above nominal supply.',
                'B': 'Scenario B charges extra track access and engineering hours, and treats planned completion dates as hard requirements rather than scoring lateness.',
                'C': 'Scenario C charges lateness, extra track access and engineering hours together.',
            }[view['scenario']]}


def contract_delays(view):
    """Per-contract lateness with the activities responsible for it."""
    m = ((view.get('validation') or {}).get('report') or {}).get('metrics') or {}
    priority = {p['contract_number']: p['contract_priority'] for p in view['model']['project_types']}
    target = {p['contract_number']: p['planned_completion_date'] for p in view['model']['project_types']}
    finished = {w['activity_id']: w for w in (m.get('workload') or [])}
    owner = defaultdict(list)
    for a in view['model']['activities']:
        owner[a['contract_number']].append(a)
    result = []
    for row in (m.get('contracts') or []):
        contract = row['contract_number']
        due = target.get(contract)
        late = []
        for a in sorted(owner[contract], key=lambda a: a['activity_id']):
            done = finished.get(a['activity_id']) or {}
            if done.get('completion_date') and due and done['completion_date'] > due:
                late.append({'activity_id': a['activity_id'], 'completion_date': done['completion_date'],
                             'activity_priority': a['activity_priority']})
        result.append({'contract_number': contract, 'completion_date': row['completion_date'],
                       'overrun_days': row['overrun_days'], 'planned_completion_date': due,
                       'contract_priority': priority.get(contract),
                       'priority_weight': CONTRACT_PRIORITY_WEIGHT.get(priority.get(contract)),
                       'activity_count': len(owner[contract]), 'late_activities': late,
                       'on_time': row['overrun_days'] == 0})
    result.sort(key=lambda r: (-(r['overrun_days'] or 0), r['contract_priority'] or 9, r['contract_number']))
    return result


def bottlenecks(view, limit=12):
    """Rank the location/weeks under the most access pressure, with who is there.

    With no excess anywhere the binding constraint is how often a location sits at
    full nominal supply, so locations are ranked on that before raw utilisation.
    """
    m = ((view.get('validation') or {}).get('report') or {}).get('metrics') or {}
    occupancy = (view.get('tables') or {}).get('SCHEDULE_OCCUPANCY.csv') or []
    members = defaultdict(set)
    for r in occupancy:
        members[(r['location_id'], r['week'])].add(r['activity_id'])
    rows = m.get('capacity') or []
    points, totals = [], defaultdict(lambda: {'excess': 0, 'weeks_over': 0, 'weeks_at_capacity': 0,
                                              'weeks_used': 0, 'peak_utilisation': 0.0, 'no_nominal_supply': False})
    for r in rows:
        starved = not r['supply'] and r['groups'] > 0
        utilisation = r['groups']/r['supply'] if r['supply'] else None
        points.append({'location_id': r['location_id'], 'week': r['week'], 'groups': r['groups'],
                       'supply': r['supply'], 'excess': r['excess'], 'utilisation': utilisation,
                       'no_nominal_supply': starved,
                       'activities': sorted(members[(r['location_id'], r['week'])])})
        seen = totals[r['location_id']]
        seen['excess'] += r['excess']
        seen['weeks_over'] += int(r['excess'] > 0)
        seen['weeks_at_capacity'] += int(starved or (r['supply'] and r['groups'] >= r['supply']))
        seen['weeks_used'] += 1
        seen['no_nominal_supply'] = seen['no_nominal_supply'] or starved
        seen['peak_utilisation'] = max(seen['peak_utilisation'], utilisation or 0)
    # Rank a starved cell above any finite utilisation without using a non-JSON infinity.
    points.sort(key=lambda r: (-r['excess'], -int(r['no_nominal_supply']), -(r['utilisation'] or 0),
                               -r['groups'], r['location_id'], r['week']))
    locations = [{'location_id': id, **values} for id, values in totals.items()]
    locations.sort(key=lambda r: (-r['excess'], -int(r['no_nominal_supply']), -r['weeks_at_capacity'],
                                  -r['peak_utilisation'], r['location_id']))
    total_excess = sum(r['excess'] for r in rows)
    if not rows:
        headline = 'No track occupancy to analyse yet.'
    elif total_excess:
        headline = (f'{total_excess} location-week{"s" if total_excess != 1 else ""} need more access than '
                    f'nominal supply allows, across {sum(1 for r in rows if r["excess"])} week slot(s).')
    elif locations:
        busiest = locations[0]
        headline = (f'No location exceeds its nominal supply. The tightest is {busiest["location_id"]}, '
                    f'at full capacity in {busiest["weeks_at_capacity"]} of {busiest["weeks_used"]} weeks it is used.')
    else:
        headline = 'No location exceeds its nominal supply.'
    return {'headline': headline, 'pressure_points': points[:limit], 'locations': locations[:limit],
            'total_excess': total_excess, 'evaluated_location_weeks': len(rows),
            'scope': 'Counts distinct sharing groups against nominal weekly supply for occupied locations only.'}


def verdict(view):
    """One plain-language state, saying what was checked rather than claiming feasibility."""
    facts = summary(view)
    report = (view.get('validation') or {}).get('report') or {}
    blocking = []
    if view.get('tables') is None:
        state, headline = 'none', 'No schedule yet'
        detail = 'Load the supplied sample, import a schedule or optimise a scenario to begin.'
    else:
        complete, required = facts['complete_activities'], facts['required_activities']
        if not facts['checked_model_plan']:
            if complete is not None and complete < required:
                blocking.append(f'{required-complete} of {required} activities do not have their full workload scheduled.')
            if facts['weekly_violations']:
                blocking.append(f"{facts['weekly_violations']} scheduling rule{'s' if facts['weekly_violations'] != 1 else ''} are broken.")
            if facts['night_conflict_weeks']:
                blocking.append(f"{facts['night_conflict_weeks']} week(s) cannot be arranged into consistent nights.")
            c_check = facts.get('c_window_check')
            if c_check and not c_check['passed']:
                blocking.append('Engineering-hour access does not fit the two-week line window this scenario assumes.')
        state = 'checked' if facts['checked_model_plan'] else 'review'
        headline = 'Ready for planning review' if state == 'checked' else 'Needs attention'
        checks = sum(1 for status in report.get('rule_checks', {}).values() if status == 'PASS_UNDER_PROFILE')
        detail = (f'All {required} activities scheduled · {checks} automated checks passed'
                  if state == 'checked' else
                  (blocking[0] if blocking else 'Review the findings before using this plan.'))
    return {'state': state, 'headline': headline, 'detail': detail, 'blocking': blocking,
            'caveats': [UNVERIFIED_PROTECTION,
                        'This is planning support, not authority to enter the track.'],
            'checked_model_plan': facts['checked_model_plan']}


def explain(view):
    """Decision-support view derived only from checked inputs, outputs and findings."""
    return {'version': VERSION, 'verdict': verdict(view), 'score': score_explanation(view),
            'contracts': contract_delays(view), 'bottlenecks': bottlenecks(view), 'scope': SCOPE}


TRADEOFF_TERMS = (
    ('complete_activities', 'completed activities', True),
    ('activity_delay_days', 'days of activity lateness', False),
    ('contract_delay_days', 'days of contract lateness', False),
    ('eclo_accesses', 'engineering-hour accesses', False),
    ('excess_slots', 'location-weeks above nominal supply', False),
    ('weekly_violations', 'broken scheduling rules', False),
    ('night_conflict_weeks', 'weeks with night conflicts', False),
)


def tradeoffs(deltas, comparable, changed_activities=None):
    """Name what improved and what it cost, using only the measured differences."""
    improvements, costs = [], []
    for key, label, higher_better in TRADEOFF_TERMS:
        delta = deltas.get(key)
        if not delta:
            continue
        entry = {'key': key, 'label': label, 'delta': delta,
                 'text': f"{abs(delta):g} {'more' if delta > 0 else 'fewer'} {label}"}
        (improvements if (delta > 0) == higher_better else costs).append(entry)
    for group in (improvements, costs):
        group.sort(key=lambda e: -abs(e['delta']))
    def listed(entries):
        texts = [e['text'] for e in entries]
        return texts[0] if len(texts) == 1 else ', '.join(texts[:-1]) + ' and ' + texts[-1]

    if improvements and costs:
        summary_text = f'Gained {listed(improvements[:2])}, at the cost of {listed(costs[:2])}.'
    elif improvements:
        summary_text = f'Gained {listed(improvements[:3])}, with no measured cost.'
    elif costs:
        summary_text = f'No measured gain; this plan has {listed(costs[:3])}.'
    elif changed_activities:
        summary_text = (f'Every headline figure is unchanged, though {changed_activities} '
                        f'activit{"y was" if changed_activities == 1 else "ies were"} rescheduled.')
    elif changed_activities == 0:
        summary_text = 'Nothing changed: no activity moved and no headline figure differs.'
    else:
        summary_text = 'These two plans match on every headline figure.'
    score = deltas.get('score')
    if comparable and score:
        summary_text += ' Score {} by {:.1f}.'.format('rose' if score > 0 else 'fell', abs(score))
    return {'summary': summary_text, 'improvements': improvements, 'costs': costs,
            'score_delta': score if comparable else None, 'scores_comparable': comparable}


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
            'tradeoffs': tradeoffs(deltas, comparable, len(changes)),
            'changes': changes, 'before_contracts': bm.get('contracts'), 'after_contracts': am.get('contracts'), 'scope': SCOPE}
