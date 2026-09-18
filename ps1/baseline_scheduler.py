"""Deterministic Scenario A construction, not optimisation or feasibility proof."""
from collections import Counter, defaultdict
from datetime import date, timedelta


VERSION = "ps1-greedy-a-0.1.0"


def construct(model):
    projects = {(p["contract_number"], p["activity_type"]): p for p in model["project_types"]}
    activities = {a["activity_id"]: a for a in model["activities"]}
    supply = {l["location_id"]: l["supply_capacity"] for l in model["locations"]}
    spans = {a: set(row["working_span"]["location_ids"]) for a, row in activities.items()}
    mirrors = {a: {l.rsplit(":", 1)[0]+(":WB" if l.endswith(":EB") else ":EB") for l in spans[a]}
               if row["nature_of_works"] == "Live" else set() for a, row in activities.items()}
    remaining = {a: row["workload_units_scaled"] for a, row in activities.items()}
    finished, sequence, reasons = {}, Counter(), defaultdict(Counter)
    accesses, occupancy, placements = [], [], []
    order = sorted(activities, key=lambda a: (projects[tuple(activities[a]["project_key"])]["contract_priority"],
                                             projects[tuple(activities[a]["project_key"])]["planned_completion_date"],
                                             activities[a]["activity_priority"], a))
    for week in range(1, model["calendar"]["weeks"]+1):
        used = Counter()
        nights, contract_nights, fronts = defaultdict(list), defaultdict(dict), Counter()
        for id in order:
            if remaining[id] <= 0:
                continue
            a = activities[id]
            key = tuple(a["project_key"])
            p = projects[key]
            pred = a["predecessor_activity_id"]
            if week < a["earliest_in_horizon_week"]:
                reasons[id]["before_release"] += 1
                continue
            if pred and (pred not in finished or finished[pred] >= week):
                reasons[id]["predecessor_not_finished_in_earlier_week"] += 1
                continue
            if any(used[l] >= supply[l] for l in spans[id]):
                reasons[id]["location_capacity_used_or_zero"] += 1
                continue
            if not p["number_of_workfronts"] or not p["number_of_maximum_access_per_week"]:
                reasons[id]["zero_contract_resources"] += 1
                continue
            selected, index = None, None
            for night in range(1, 8):
                if night not in contract_nights[key] and len(contract_nights[key]) >= p["number_of_maximum_access_per_week"]:
                    continue
                if fronts[(key, night)] >= p["number_of_workfronts"]:
                    continue
                if any(spans[id] & spans[other] or mirrors[id] & spans[other] or spans[id] & mirrors[other] for other in nights[night]):
                    continue
                selected = night
                index = contract_nights[key].setdefault(night, len(contract_nights[key])+1)
                break
            if selected is None:
                reasons[id]["no_slot_under_greedy_no_sharing_policy"] += 1
                continue
            nights[selected].append(id)
            fronts[(key, selected)] += 1
            used.update(spans[id])
            sequence[id] += 1
            accesses.append(dict(activity_id=id, access_seq=sequence[id], week=week, eclo=0, access_night=index))
            group = f"g{len(accesses)}"
            occupancy.extend(dict(activity_id=id, week=week, location_id=l, co_share_group=group) for l in sorted(spans[id]))
            placements.append({"activity_id": id, "week": week, "abstract_night": selected,
                               "reason": "First available slot after release and predecessor completion, within location and contract resources; no sharing or ECLO."})
            remaining[id] -= 2
            if remaining[id] <= 0:
                finished[id] = week
    start = date.fromisoformat(model["calendar"]["start"])
    results = []
    for contract in sorted({p["contract_number"] for p in model["project_types"]}):
        jobs = [id for id, a in activities.items() if a["contract_number"] == contract]
        if jobs and all(id in finished for id in jobs):
            finish = start + timedelta(days=max(finished[id] for id in jobs)*7-1)
            p = projects[tuple(activities[jobs[0]]["project_key"])]
            results.append(dict(scenario="A", contract_number=contract, simulated_completion_date=finish.isoformat(),
                                overrun_days=max(0, (finish-date.fromisoformat(p["planned_completion_date"])).days)))
    unfinished = [{"activity_id": id, "remaining_scaled_units": max(0, left),
                   "deferred_weeks_by_reason": dict(reasons[id]),
                   "conclusion": "Not placed by this heuristic within the horizon; not a proof of infeasibility."}
                  for id, left in sorted(remaining.items()) if left > 0]
    return {"tables": {"SCHEDULE_ACCESS.csv": accesses, "SCHEDULE_OCCUPANCY.csv": occupancy, "RESULTS.csv": results},
            "construction": {"version": VERSION, "scenario": "A", "status": "PARTIAL_DRAFT" if unfinished else "COMPLETE_WORKLOAD_DRAFT",
                             "optimality_proven": False, "feasibility_proven": False,
                             "limitations": ["No sharing and no backtracking; this may leave avoidable unused capacity.",
                                             "Seven abstract nights and known working-core separation are construction choices, not extra benchmark constraints.",
                                             "Buffer and interchange protection remain unverified."],
                             "unfinished": unfinished, "placements": placements,
                             "remaining_scaled_units": sum(max(0, n) for n in remaining.values())}}
