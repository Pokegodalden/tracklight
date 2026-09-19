"""Bounded CP-SAT optimisation of the disclosed weekly/core-night model.

Protection remains unconfigured. A model solution is never a full-feasibility
claim, and model infeasibility is not an official PS1 infeasibility verdict.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from itertools import combinations
import math
from time import perf_counter

from .validator import check_schedule

VERSION = 'ps1-cpsat-0.2.0'
MODEL_ID = 'weekly-core-nights-0.1.0'
MAX_ASSIGNMENTS = 60000
MAX_LOCATION_MEMBERSHIPS = 300000


@dataclass(frozen=True)
class Scenario:
    code: str
    capacity_extra: int | None
    eclo_allowed: bool
    hard_deadline: bool
    delay_cost: bool
    eclo_window: bool


SCENARIOS = {
    'A': Scenario('A', 0, False, False, True, False),
    'B': Scenario('B', None, True, True, False, False),
    'C': Scenario('C', 1, True, False, True, True),
}
ASSUMPTIONS = [
    'One of seven abstract full nights per activity/week; dated availability is not supplied.',
    'One legal sharing group per location/abstract night, with uniform ECLO flags.',
    'Known Live opposite-bound working cores are separated; full buffers and interchange closure geometry remain unverified.',
    'Scenario C conservatively applies each Live ECLO access to every input line window; this is a stronger construction policy, not a confirmed affected-line map.',
    'The supplied eight-file instance is used for C; its official scenario applicability remains unconfirmed.',
    'Objective uses provisional weighted activity delay, 7 per excess location/week slot and 5 per ECLO activity access.',
]


def _accepted(report):
    return (report['metrics'] is not None and report['metrics']['all_work_complete']
            and not any(f['severity'] in ('violation', 'error') for f in report['findings'])
            and report['physical_night_diagnostic']['status'] == 'ASSIGNED_FOR_MODELLED_RELATIONS')


def objective_gap(score, bound):
    # Do not turn a contradictory or non-finite bound into an apparent zero gap.
    if not math.isfinite(bound) or bound > score + 1e-6:
        raise RuntimeError('Solver bound contradicts the checked objective; candidate withheld.')
    return max(0, (score-bound) / max(1, abs(score)))


def window_check(model, tables):
    """Independently reconstruct the conservative C window check from CSV decisions."""
    activities = {a['activity_id']: a for a in model['activities']}
    locations = {l['location_id']: l for l in model['locations']}
    lines = sorted(l['line_code'] for l in model['lines'])
    used = defaultdict(set)
    for row in tables['SCHEDULE_ACCESS.csv']:
        if row['eclo']:
            a = activities[row['activity_id']]
            affected = lines if a['nature_of_works'] == 'Live' else [locations[a['start_location_id']]['line_code']]
            for line in affected:
                used[line].add(row['week'])
    return {'policy': 'all_input_lines_for_Live', 'weeks': {l: sorted(w) for l,w in sorted(used.items())},
            'passed': all(max(w)-min(w) <= 1 for w in used.values()), 'official_affected_lines_verified': False}


def _incumbent(model, tables, scenario):
    if tables is None:
        return None, 'No incumbent supplied.'
    report = check_schedule(model, tables, scenario, search_budget=5000)
    if not _accepted(report):
        return None, 'Parent is preserved, but it is incomplete, violates a checked rule, or lacks a verified conditional night assignment.'
    if scenario == 'C' and not window_check(model, tables)['passed']:
        return None, 'Parent does not meet the disclosed conservative C window policy.'
    nights = { (a, w['week']): n for w in report['physical_night_diagnostic']['weeks']
              for a,n in w['assignment'].items() }
    return {'tables': tables, 'report': report, 'nights': nights}, 'Complete model-compatible incumbent retained as a fallback.'


def optimise(model, scenario, *, seconds=30, workers=1, seed=0, incumbent=None, replanning=None):
    if scenario not in SCENARIOS:
        raise ValueError('Choose scenario A, B or C.')
    if isinstance(seconds, bool) or not isinstance(seconds, (int,float)) or not math.isfinite(seconds) or not 0 < seconds <= 300:
        raise ValueError('Solver time limit must be greater than zero and at most 300 seconds.')
    if type(workers) is not int or not 1 <= workers <= 8 or type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError('Use 1..8 workers and a nonnegative 32-bit random seed.')
    try:
        from ortools.sat.python import cp_model
        import ortools
    except ImportError as exc:
        raise ValueError('OR-Tools is required. Start the app with the project .venv interpreter after installing requirements.txt.') from exc
    started = perf_counter()
    config = SCENARIOS[scenario]
    activities = {a['activity_id']: a for a in model['activities']}
    projects = {(p['contract_number'],p['activity_type']): p for p in model['project_types']}
    locations = {l['location_id']: l for l in model['locations']}
    horizon = model['calendar']['weeks']
    start = date.fromisoformat(model['calendar']['start'])
    # Use the importer's working spans. The checker independently reconstructs
    # them from topology, so a modelling/export error cannot validate itself.
    spans = {a: set(row['working_span']['location_ids']) for a,row in activities.items()}
    lines = sorted(l['line_code'] for l in model['lines'])
    allowed, early_failures = {}, []
    for a,row in activities.items():
        p = projects[tuple(row['project_key'])]
        last = min(horizon, ((date.fromisoformat(p['planned_completion_date'])-start).days+1)//7) if config.hard_deadline else horizon
        first = max(1, (date.fromisoformat(row['planned_start_date'])-start).days//7+1)
        allowed[a] = list(range(first,last+1))
        max_yield = len(allowed[a]) * (3 if config.eclo_allowed else 2)
        if row['workload_units_scaled'] > max_yield:
            early_failures.append({'activity_id':a, 'required_scaled':row['workload_units_scaled'],
                                   'maximum_scaled_before_resource_constraints':max_yield,
                                   'reason':'Insufficient released weeks before the deadline/horizon, even ignoring resource competition.'})
        if p['number_of_workfronts'] == 0 or p['number_of_maximum_access_per_week'] == 0:
            early_failures.append({'activity_id':a, 'reason':'Positive workload with zero contract access or workfront resources.'})
    if sum(map(len,allowed.values()))*7 > MAX_ASSIGNMENTS:
        raise ValueError('Instance exceeds the local solver limit of 60,000 activity/week/night choices.')
    if sum(len(allowed[a])*7*len(spans[a]) for a in activities) > MAX_LOCATION_MEMBERSHIPS:
        raise ValueError('Instance exceeds the local solver limit of 300,000 location/assignment memberships.')
    meta = {'version':VERSION, 'model_id':MODEL_ID, 'scenario':scenario, 'scenario_config':asdict(config),
            'ortools_version':ortools.__version__, 'settings':{'time_limit_seconds':seconds,'workers':workers,'seed':seed},
            'assumptions':ASSUMPTIONS, 'status':'NOT_SOLVED', 'solver_status':None,
            'full_feasibility_established':False, 'official_validation':'NOT_RUN', 'submission_ready':False,
            'objective_tenths':None, 'best_bound_tenths':None, 'relative_gap':None,
            'optimality_scope':'Only '+MODEL_ID+' with the stated assumptions; not the full PS1 problem.',
            'model_optimality_proven':False, 'infeasibility_evidence':early_failures}
    if early_failures:
        meta.update(status='INFEASIBLE_MODEL', solver_status='PRECHECK_INFEASIBLE', elapsed_seconds=perf_counter()-started)
        return {'tables':None,'optimisation':meta}
    prior, prior_reason = _incumbent(model,incumbent,scenario)
    if prior and replanning:
        from .replan import audit
        candidate_view = dict(replanning['parent'], model=model, tables=prior['tables'])
        if not audit(replanning['parent'], candidate_view, replanning['context'])['passed']:
            prior = None
            prior_reason = 'Parent is not compatible with the requested completed work and locks.'
    meta['incumbent_policy'] = prior_reason
    cp = cp_model.CpModel()
    x, used, eclo, finish = {}, {}, {}, {}
    at_location, at_project = defaultdict(list), defaultdict(list)
    for a,row in activities.items():
        for w in allowed[a]:
            used[a,w] = cp.new_bool_var(f'use:{a}:{w}')
            eclo[a,w] = cp.new_bool_var(f'eclo:{a}:{w}')
            cp.add(eclo[a,w] <= used[a,w])
            if not config.eclo_allowed:
                cp.add(eclo[a,w] == 0)
            for n in range(1,8):
                x[a,w,n] = cp.new_bool_var(f'x:{a}:{w}:{n}')
                for l in sorted(spans[a]):
                    at_location[l,w,n].append(a)
                at_project[(*row['project_key'],w,n)].append(a)
            cp.add(sum(x[a,w,n] for n in range(1,8)) == used[a,w])
        cp.add(sum(2*used[a,w]+eclo[a,w] for w in allowed[a]) >= row['workload_units_scaled'])
        finish[a] = cp.new_int_var(1,horizon,f'finish:{a}')
        cp.add_max_equality(finish[a], [w*used[a,w] for w in allowed[a]])
    for a,row in activities.items():
        pred = row['predecessor_activity_id']
        if pred:
            for w in allowed[a]:
                cp.add(finish[pred] < w).only_enforce_if(used[a,w])
    project_nights = defaultdict(list)
    for (c,t,w,n), jobs in at_project.items():
        values = [x[a,w,n] for a in jobs]
        on = cp.new_bool_var(f'project:{c}:{t}:{w}:{n}')
        cp.add_max_equality(on,values)
        cp.add(sum(values) <= projects[c,t]['number_of_workfronts'])
        project_nights[c,t,w].append(on)
    for (c,t,w), values in project_nights.items():
        cp.add(sum(values) <= projects[c,t]['number_of_maximum_access_per_week'])
    local_nights = defaultdict(list)
    for (l,w,n), jobs in at_location.items():
        values = [x[a,w,n] for a in jobs]
        on = cp.new_bool_var(f'location:{l}:{w}:{n}')
        cp.add_max_equality(on,values)
        pc = sum(x[a,w,n] for a in jobs if activities[a]['access_type']=='PC')
        pm = sum(x[a,w,n] for a in jobs if activities[a]['access_type']=='PM')
        cp.add(pc <= 1)
        cp.add(sum(values) + 3*pm <= 4)
        if config.eclo_allowed:
            flag = cp.new_bool_var(f'location-eclo:{l}:{w}:{n}')
            for a in jobs:
                cp.add(eclo[a,w] == flag).only_enforce_if(x[a,w,n])
        local_nights[l,w].append(on)
    overrides = {(r['location_id'], r['week']):r['capacity'] for r in model.get('weekly_supply_overrides', [])}
    extras = []
    for (l,w), values in local_nights.items():
        cap = overrides.get((l,w), locations[l]['supply_capacity'])
        if config.capacity_extra is not None:
            cp.add(sum(values) <= cap+config.capacity_extra)
        extra = cp.new_int_var(0,7,f'extra:{l}:{w}')
        cp.add_max_equality(extra,[0,sum(values)-cap])
        extras.append(extra)
    # Minimum known mirror relation only. No unconfirmed buffer geometry is invented.
    pairs = set()
    for a,row in activities.items():
        if row['nature_of_works']=='Live':
            mirror = {l.rsplit(':',1)[0]+(':WB' if l.endswith(':EB') else ':EB') for l in spans[a]}
            for b in activities:
                if a!=b and mirror & spans[b]:
                    pairs.add(tuple(sorted((a,b))))
    for a,b in sorted(pairs):
        for w in sorted(set(allowed[a]) & set(allowed[b])):
            for n in range(1,8):
                cp.add(x[a,w,n]+x[b,w,n] <= 1)
    windows = {}
    if config.eclo_window:
        windows = {l:cp.new_int_var(1,horizon,f'window:{l}') for l in lines}
        for a,row in activities.items():
            affected = lines if row['nature_of_works']=='Live' else [locations[row['start_location_id']]['line_code']]
            for w in allowed[a]:
                for l in affected:
                    cp.add(windows[l] <= w).only_enforce_if(eclo[a,w])
                    cp.add(windows[l]+1 >= w).only_enforce_if(eclo[a,w])
    delays = []
    for a,row in activities.items():
        p = projects[tuple(row['project_key'])]
        target = (date.fromisoformat(p['planned_completion_date'])-start).days
        late = cp.new_int_var(0,max(0,7*horizon-1-target),f'late:{a}')
        cp.add_max_equality(late,[0,7*finish[a]-1-target])
        delays.append(late*{1:100,2:10,3:1}[p['contract_priority']]*{1:13,2:12,3:10}[row['activity_priority']])
    objective = (sum(delays) if config.delay_cost else 0) + (70*sum(extras)+50*sum(eclo.values()) if config.eclo_allowed else 0)
    weight = 1
    churn = 0
    if replanning:
        from .replan import constrain
        churn = constrain(cp, model, used, eclo, x, replanning)
        weight = len(activities)+1
        meta['replanning_objective'] = {'order':['provisional_scenario_score', 'changed_activity_count'], 'weight':weight,
            'scope':'Exact lexicographic order. Changes include weeks, ECLO and sharing relationships. Optimality only if the combined model is proven optimal.'}
    cp.minimize(objective*weight+churn)
    if replanning and not prior:
        parent = replanning['parent']
        known_nights = {(a, w['week']):n for w in parent['validation']['report']['physical_night_diagnostic']['weeks']
                        for a,n in w['assignment'].items()}
        known_rows = {(r['activity_id'],r['week']):r for r in parent['tables']['SCHEDULE_ACCESS.csv']}
        for (a,w,n),v in x.items():
            cp.add_hint(v, int(known_nights.get((a,w)) == n))
        for key,v in eclo.items():
            cp.add_hint(v, known_rows[key]['eclo'] if key in known_rows else 0)
    if prior:
        known = {(r['activity_id'],r['week']):r for r in prior['tables']['SCHEDULE_ACCESS.csv']}
        for (a,w,n),v in x.items():
            cp.add_hint(v,int(prior['nights'].get((a,w))==n))
        for key,v in eclo.items():
            cp.add_hint(v,known[key]['eclo'] if key in known else 0)
        cp.add(objective <= prior['report']['metrics']['score_tenths'])
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    meta['build_seconds'] = perf_counter()-started
    status = solver.solve(cp)
    bound = solver.best_objective_bound if status in (cp_model.OPTIMAL,cp_model.FEASIBLE,cp_model.UNKNOWN) else None
    if bound is not None and not math.isfinite(bound):
        raise RuntimeError('Solver returned a non-finite objective bound; result withheld.')
    if replanning and bound is not None:
        meta['combined_best_bound'] = bound
        bound = math.floor(bound/weight)
    meta.update(solver_status=solver.status_name(status), solver_seconds=solver.wall_time,
                best_bound_tenths=max(0,bound) if bound is not None else None,
                variables=len(cp.proto.variables), constraints=len(cp.proto.constraints), branches=solver.num_branches,
                conflicts=solver.num_conflicts)
    tables = None
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        rows = [(a,w,n,int(solver.value(eclo[a,w]))) for (a,w,n),v in x.items() if solver.value(v)]
        tables = _tables(model,scenario,rows,spans)
        report = check_schedule(model,tables,scenario,search_budget=5000)
        raw_objective = int(solver.value(objective))
        if replanning:
            meta['changed_activity_count'] = int(solver.value(churn))
            meta['churn_optimality_proven'] = status == cp_model.OPTIMAL
        if not _accepted(report) or report['metrics']['score_tenths'] != raw_objective or (scenario=='C' and not window_check(model,tables)['passed']):
            raise RuntimeError('Optimiser output failed the independent checker or objective reconciliation; candidate withheld.')
        # Standard accesses can have zero marginal objective cost. Remove redundant
        # ones without dropping required yield, then independently check again.
        retained = []
        for a,row in activities.items():
            selected = sorted((r for r in rows if r[0]==a),key=lambda r:r[1],reverse=True)
            total = sum(3 if r[3] else 2 for r in selected)
            for r in selected:
                amount = 3 if r[3] else 2
                if total-amount >= row['workload_units_scaled']:
                    total -= amount
                else:
                    retained.append(r)
        meta.update(raw_solver_objective_tenths=raw_objective, removed_redundant_accesses=len(rows)-len(retained))
        if replanning:
            retained = rows  # Post-solve pruning could break locks or worsen the secondary objective.
            meta['removed_redundant_accesses'] = 0
        rows = retained
        tables = _tables(model,scenario,rows,spans)
        report = check_schedule(model,tables,scenario,search_budget=5000)
        objective_value = report['metrics']['score_tenths']
        if not _accepted(report) or objective_value > raw_objective or (status==cp_model.OPTIMAL and objective_value!=raw_objective):
            raise RuntimeError('Redundant-access removal failed verification; candidate withheld.')
        meta.update(status='OPTIMAL_MODEL_UNVERIFIED' if status==cp_model.OPTIMAL else 'FEASIBLE_MODEL_UNVERIFIED',
                    model_optimality_proven=status==cp_model.OPTIMAL, objective_tenths=objective_value,
                    selected_from='solver', abstract_nights=[{'activity_id':a,'week':w,'night':n} for a,w,n,e in rows])
    elif prior and status==cp_model.UNKNOWN:
        tables,report = prior['tables'],prior['report']
        meta.update(status='RETAINED_INCUMBENT_UNVERIFIED', objective_tenths=report['metrics']['score_tenths'], selected_from='incumbent',
                    abstract_nights=[{'activity_id':a, 'week':w, 'night':n} for (a,w),n in sorted(prior['nights'].items())])
    elif status==cp_model.INFEASIBLE:
        if prior:
            raise RuntimeError('Solver contradicted a checked model-compatible incumbent; result withheld.')
        meta.update(status='INFEASIBLE_MODEL', infeasibility_evidence=[{'reason':'CP-SAT exhausted the stated model; no minimal conflict set was computed.'}])
    elif status==cp_model.UNKNOWN:
        meta['status']='NO_SOLUTION_WITHIN_LIMIT'
    else:
        raise RuntimeError('CP-SAT rejected the model: '+solver.solution_info())
    if tables is not None and replanning:
        from .replan import audit
        from .planner import allocation_details
        candidate_view = dict(replanning['parent'], model=model, tables=tables)
        meta['lock_audit'] = audit(replanning['parent'], candidate_view, replanning['context'])
        if not meta['lock_audit']['passed']:
            raise RuntimeError('Independent completed-work/lock audit failed; candidate withheld.')
        old, new = allocation_details(replanning['parent']), allocation_details(candidate_view)
        changes = sum(old.get(a) != new.get(a) for a in set(old)|set(new))
        if meta.get('changed_activity_count', changes) != changes:
            raise RuntimeError('Solver churn differs from independent allocation comparison; candidate withheld.')
        meta['changed_activity_count'] = changes
        meta.setdefault('churn_optimality_proven', False)
    if tables is not None:
        meta['metrics'] = report['metrics']
        meta['conditional_night_status'] = report['physical_night_diagnostic']['status']
        meta['c_window_check'] = window_check(model,tables) if scenario=='C' else None
        bound,score = meta['best_bound_tenths'],meta['objective_tenths']
        meta['relative_gap'] = objective_gap(score, bound)
    meta['elapsed_seconds']=perf_counter()-started
    return {'tables':tables,'optimisation':meta}


def _tables(model, scenario, placements, spans):
    activities={a['activity_id']:a for a in model['activities']}
    projects={tuple((p['contract_number'],p['activity_type'])):p for p in model['project_types']}
    nights=defaultdict(set)
    for a,w,n,e in placements:
        nights[(*activities[a]['project_key'],w)].add(n)
    indices={key:{n:i+1 for i,n in enumerate(sorted(values))} for key,values in nights.items()}
    access,occupancy=[],[]
    sequence=Counter()
    finishes=defaultdict(int)
    for a,w,n,e in sorted(placements):
        sequence[a]+=1
        access.append(dict(activity_id=a,access_seq=sequence[a],week=w,eclo=e,access_night=indices[(*activities[a]['project_key'],w)][n]))
        occupancy.extend(dict(activity_id=a,week=w,location_id=l,co_share_group=f'n{n}') for l in sorted(spans[a]))
        finishes[activities[a]['contract_number']]=max(finishes[activities[a]['contract_number']],w)
    start=date.fromisoformat(model['calendar']['start'])
    results=[]
    for c,w in sorted(finishes.items()):
        p=next(p for p in projects.values() if p['contract_number']==c)
        finish=start+timedelta(days=7*w-1)
        results.append(dict(scenario=scenario,contract_number=c,simulated_completion_date=finish.isoformat(),overrun_days=max(0,(finish-date.fromisoformat(p['planned_completion_date'])).days)))
    return {'SCHEDULE_ACCESS.csv':access,'SCHEDULE_OCCUPANCY.csv':occupancy,'RESULTS.csv':results}
