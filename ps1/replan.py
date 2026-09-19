"""Explicit disruption proposals, model constraints and independent lock audit."""
from collections import defaultdict
from copy import deepcopy
import csv
from datetime import date, timedelta
import io

from . import planner
from .schema import SCHEMAS

VERSION = 'ps1-replan-0.1.0'


def supply_overrides(model, rows):
    """Validate the optional planning overlay; never alter the organiser schema."""
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError('Weekly supply must be a list of at most 2,000 overrides.')
    locations = {l['location_id'] for l in model['locations']}
    result = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'location_id', 'week', 'capacity'}:
            raise ValueError('Each weekly supply override needs location_id, week and capacity.')
        if row['location_id'] not in locations or type(row['week']) is not int or not 1 <= row['week'] <= model['calendar']['weeks']:
            raise ValueError('Weekly supply must identify an existing location and horizon week.')
        if type(row['capacity']) is not int or not 0 <= row['capacity'] <= 7:
            raise ValueError('Weekly nominal supply must be an integer from 0 to 7.')
        key = (row['location_id'], row['week'])
        if key in result:
            raise ValueError('Duplicate weekly supply override.')
        result[key] = row['capacity']
    return result


def prepare(parent, files, proposal):
    if not planner.summary(parent)['checked_model_plan']:
        raise ValueError('Controlled replanning requires a complete checked model plan. Optimise or repair this draft first.')
    if not isinstance(proposal, dict) or set(proposal) - {'completed_through_week', 'locked_activity_ids', 'changes'}:
        raise ValueError('Use completed_through_week, locked_activity_ids and changes.')
    previous = parent.get('planning_context') or {}
    cutoff = proposal.get('completed_through_week', previous.get('completed_through_week', 0))
    if type(cutoff) is not int or not previous.get('completed_through_week', 0) <= cutoff <= parent['model']['calendar']['weeks']:
        raise ValueError('Completed-through week must be within the horizon and cannot move backwards.')
    locks = proposal.get('locked_activity_ids', previous.get('locked_activity_ids', []))
    activities = {a['activity_id']: a for a in parent['model']['activities']}
    if not isinstance(locks, list) or any(not isinstance(a, str) or a not in activities for a in locks) or len(set(locks)) != len(locks):
        raise ValueError('Locks must be a unique list of existing activity IDs.')
    if not set(previous.get('locked_activity_ids', [])) <= set(locks):
        raise ValueError('Inherited locks cannot be silently removed. Return to the version before the lock and submit an explicit new proposal.')
    changes = proposal.get('changes', [])
    if not isinstance(changes, list) or len(changes) > 100:
        raise ValueError('Use at most 100 structured changes.')
    if not changes and not locks and cutoff == 0:
        raise ValueError('Specify a disruption, a completed week or an explicit lock.')
    rows = list(csv.DictReader(io.StringIO(files['08_ACTIVITY_DETAILS.csv'].decode('utf-8-sig'))))
    by_id = {r['activity_id']: r for r in rows}
    project_rows = list(csv.DictReader(io.StringIO(files['07_PROJECT_DETAILS.csv'].decode('utf-8-sig'))))
    overrides = supply_overrides(parent['model'], previous.get('weekly_supply', []))
    seen = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError('Each change must be a structured object.')
        kind = change.get('type')
        if kind == 'workload':
            if set(change) != {'type', 'activity_id', 'additional_units'} or change['activity_id'] not in activities:
                raise ValueError('Workload changes require an existing activity_id and additional_units.')
            a = change['activity_id']; value = change['additional_units']
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 104 or value*2 != int(value*2):
                raise ValueError('Additional workload must be positive half-unit increments, at most 104 units.')
            if max(r['week'] for r in parent['tables']['SCHEDULE_ACCESS.csv'] if r['activity_id'] == a) <= cutoff:
                raise ValueError('This activity is already completed. Add a separate follow-up activity instead of rewriting completed work.')
            by_id[a]['total_accesses'] = str(activities[a]['workload_units_scaled']/2 + value)
            key = (kind, a)
        elif kind == 'weekly_supply':
            if set(change) != {'type', 'location_id', 'week', 'capacity'}:
                raise ValueError('Weekly supply changes require location_id, week and capacity.')
            one = {k:v for k,v in change.items() if k != 'type'}
            entry = supply_overrides(parent['model'], [one])
            if change['week'] <= cutoff:
                raise ValueError('Supply changes cannot rewrite a completed week.')
            overrides.update(entry); key = (kind, change['location_id'], change['week'])
        elif kind == 'urgent_activity':
            if set(change) != {'type', 'activity'} or not isinstance(change['activity'], dict) or set(change['activity']) != set(SCHEMAS['08_ACTIVITY_DETAILS.csv']):
                raise ValueError('Urgent activity requires all documented 08_ACTIVITY_DETAILS.csv fields; it must use an existing project/type.')
            row = deepcopy(change['activity']); a = row['activity_id']
            if not isinstance(a, str) or a in by_id:
                raise ValueError('An urgent activity needs a new unique activity ID.')
            earliest = date.fromisoformat(parent['model']['calendar']['start']) + timedelta(weeks=cutoff)
            if date.fromisoformat(row['planned_start_date']) < earliest:
                raise ValueError('An urgent activity cannot start before the first uncompleted week.')
            rows.append(row); by_id[a] = row; key = (kind, a)
        elif kind == 'activity_priority':
            if set(change) != {'type', 'activity_id', 'priority'} or change['activity_id'] not in activities:
                raise ValueError('Activity priority changes require an existing activity_id and priority.')
            a = change['activity_id']; value = change['priority']
            if isinstance(value, bool) or type(value) is not int or value not in (1, 2, 3):
                raise ValueError('Priority must be the integer 1, 2 or 3.')
            if activities[a]['activity_priority'] == value:
                raise ValueError(f'Activity {a} already has priority {value}.')
            by_id[a]['activity_priority'] = str(value)
            key = (kind, a)
        elif kind == 'contract_priority':
            if set(change) != {'type', 'contract_number', 'priority'}:
                raise ValueError('Contract priority changes require contract_number and priority.')
            contract = change['contract_number']; value = change['priority']
            if isinstance(value, bool) or type(value) is not int or value not in (1, 2, 3):
                raise ValueError('Priority must be the integer 1, 2 or 3.')
            affected = [r for r in project_rows if r['contract_number'] == contract]
            if not affected:
                raise ValueError('Contract priority changes require an existing contract_number.')
            if all(r['contract_priority'] == str(value) for r in affected):
                raise ValueError(f'Contract {contract} already has priority {value}.')
            # The importer requires contract-level priority to agree across every
            # activity type, so every row for this contract moves together.
            for r in affected:
                r['contract_priority'] = str(value)
            key = (kind, contract)
        else:
            raise ValueError('Change type must be workload, weekly_supply, urgent_activity, activity_priority or contract_priority. Locks use locked_activity_ids.')
        if key in seen:
            raise ValueError('Duplicate change target. Combine it into one explicit change.')
        seen.add(key)
    revised = dict(files)
    for name, table, kinds in (('08_ACTIVITY_DETAILS.csv', rows, ('workload', 'urgent_activity', 'activity_priority')),
                               ('07_PROJECT_DETAILS.csv', project_rows, ('contract_priority',))):
        if any(c['type'] in kinds for c in changes):
            stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=list(SCHEMAS[name]), lineterminator='\r\n')
            writer.writeheader(); writer.writerows(table)
            revised[name] = stream.getvalue().encode()
    context = {'completed_through_week': cutoff, 'locked_activity_ids': sorted(locks),
               'weekly_supply': [{'location_id':l, 'week':w, 'capacity':c} for (l,w),c in sorted(overrides.items())],
               'scope': 'Planner-declared completed weeks as scheduled; nominal weekly supply overlay. Scenario B/C excess allowances still apply. No actual dates or operational authority.'}
    return revised, context


def audit(parent, child, context):
    """Compare exported semantic decisions, independently of solver variables."""
    old, new = planner.allocation_details(parent), planner.allocation_details(child)
    cutoff = context['completed_through_week']; errors = []
    for a in sorted(set(old) | set(new)):
        before = old.get(a, {'accesses':[], 'sharing':[], 'same_project_night':[]})
        after = new.get(a, {'accesses':[], 'sharing':[], 'same_project_night':[]})
        if {k:[r for r in v if r['week'] <= cutoff] for k,v in before.items()} != {k:[r for r in v if r['week'] <= cutoff] for k,v in after.items()}:
            errors.append({'activity_id':a, 'reason':'Completed-week allocations or sharing relationships changed.'})
        if a in context['locked_activity_ids'] and before != after:
            errors.append({'activity_id':a, 'reason':'Explicitly locked allocation or sharing relationship changed.'})
    return {'passed':not errors, 'completed_through_week':cutoff, 'locked_activity_ids':context['locked_activity_ids'], 'errors':errors,
            'scope':'Weeks, ECLO, occupancy and sharing relationships; arbitrary CSV group/index labels are not physical dates.'}


def constrain(cp, model, used, eclo, x, replanning):
    """Hard freeze/locks plus exact semantic changed-activity indicators."""
    parent, context = replanning['parent'], replanning['context']
    acts = {a['activity_id']:a for a in model['activities']}
    old = planner.allocation_details(parent)
    prior_rows = {(r['activity_id'],r['week']):r for r in parent['tables']['SCHEDULE_ACCESS.csv']}
    cutoff = context['completed_through_week']; locks = set(context['locked_activity_ids'])
    differences = defaultdict(list)
    # Complete vectors include absent decisions, so nothing can be added to history.
    for a in acts:
        for w in range(1, model['calendar']['weeks']+1):
            previous = prior_rows.get((a,w)); on = used.get((a,w),0); flag = eclo.get((a,w),0)
            differences[a].extend([1-on if previous else on, 1-flag if previous and previous['eclo'] else flag])
            if w <= cutoff or a in locks:
                cp.add(on == int(previous is not None)); cp.add(flag == (previous['eclo'] if previous else 0))
    spans = {a:set(r['working_span']['location_ids']) for a,r in acts.items()}
    ids = sorted(acts)
    pairs = [(a,b) for i,a in enumerate(ids) for b in ids[i+1:]
             if spans[a] & spans[b] or acts[a]['project_key'] == acts[b]['project_key']]
    if len(pairs)*model['calendar']['weeks'] > 20000:
        raise ValueError('Replanning exceeds the local limit of 20,000 interacting activity-pair/weeks.')
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            if not (spans[a] & spans[b] or acts[a]['project_key'] == acts[b]['project_key']):
                continue
            same_before = {r['week'] for key in ('sharing','same_project_night') for r in old.get(a,{}).get(key,[]) if b in r['partners']}
            for w in range(1, model['calendar']['weeks']+1):
                if (a,w) not in used or (b,w) not in used:
                    together = 0
                else:
                    both = []
                    for n in range(1,8):
                        v = cp.new_bool_var(f'together:{a}:{b}:{w}:{n}')
                        cp.add_min_equality(v,[x[a,w,n],x[b,w,n]]); both.append(v)
                    together = cp.new_bool_var(f'share:{a}:{b}:{w}')
                    cp.add(together == sum(both))
                diff = 1-together if w in same_before else together
                differences[a].append(diff); differences[b].append(diff)
                if w <= cutoff or a in locks or b in locks:
                    cp.add(together == int(w in same_before))
    changed = []
    for a in acts:
        v = cp.new_bool_var(f'changed:{a}')
        cp.add_max_equality(v,differences[a] or [int(a not in old)])
        changed.append(v)
    return sum(changed)


def comparison(parent, child, record):
    result = planner.compare(parent, child, disruption=True)
    result['disruption'] = {'proposal':record['proposal'], 'planning_context':child['planning_context'],
                            'base_input_identity':parent['input_identity'], 'revised_input_identity':child['input_identity']}
    return result
