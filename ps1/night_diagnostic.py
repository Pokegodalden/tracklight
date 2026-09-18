"""Conditional full-night consistency, separate from the weekly benchmark rules."""
from collections import Counter, defaultdict, deque
from itertools import combinations


def equality_path(start, end, adjacency):
    queue, seen = deque([start]), {start: None}
    while queue:
        node = queue.popleft()
        if node == end:
            break
        for other, reason in adjacency[node]:
            if other not in seen:
                seen[other] = (node, reason)
                queue.append(other)
    path = []
    while end != start:
        previous, reason = seen[end]
        path.append({"activities": [previous, end], **reason})
        end = previous
    return list(reversed(path))


def color_graph(adjacency, limit, budget):
    """DSATUR greedy, then bounded exact search. Exhaustion is never infeasibility."""
    if not adjacency:
        return "ASSIGNED", {}, 0

    def choose(colors):
        return max((n for n in adjacency if n not in colors),
                   key=lambda n: (len({colors[x] for x in adjacency[n] if x in colors}), len(adjacency[n]), n))

    colors = {}
    while len(colors) < len(adjacency):
        node = choose(colors)
        forbidden = {colors[n] for n in adjacency[node] if n in colors}
        available = [c for c in range(1, limit+1) if c not in forbidden]
        if not available:
            break
        colors[node] = available[0]
    if len(colors) == len(adjacency):
        return "ASSIGNED", colors, 0
    # Bound recursion independently of the search-node budget. Large greedy
    # failures remain unknown; they are not falsely called impossible.
    if len(adjacency) > 400:
        return "UNKNOWN_SEARCH_LIMIT", None, 0
    colors, visited, stopped = {}, 0, False

    def search():
        nonlocal visited, stopped
        if len(colors) == len(adjacency):
            return True
        if visited >= budget:
            stopped = True
            return False
        visited += 1
        node = choose(colors)
        forbidden = {colors[n] for n in adjacency[node] if n in colors}
        # Color labels are interchangeable; introduce at most one new label.
        for color in range(1, min(limit, max(colors.values(), default=0)+1)+1):
            if color not in forbidden:
                colors[node] = color
                if search():
                    return True
                del colors[node]
                if stopped:
                    return False
        return False

    found = search()
    return ("ASSIGNED", dict(colors), visited) if found else (
        "UNKNOWN_SEARCH_LIMIT" if stopped else "INCONSISTENT_UNDER_ASSUMPTIONS", None, visited)


def validate_options(night_limit, search_budget):
    if type(night_limit) is not int or not 1 <= night_limit <= 7:
        raise ValueError("Abstract night limit must be an integer from 1 to 7.")
    if type(search_budget) is not int or search_budget < 0:
        raise ValueError("Search budget must be a nonnegative integer.")


def diagnose(model, accesses, occupancy, night_limit=7, search_budget=50000):
    validate_options(night_limit, search_budget)
    activities = {a["activity_id"]: a for a in model["activities"]}
    projects = {(p["contract_number"], p["activity_type"]): p for p in model["project_types"]}
    by_week, occ_week = defaultdict(list), defaultdict(list)
    for access in accesses:
        by_week[access["week"]].append(access)
    for row in occupancy:
        occ_week[row["week"]].append(row)
    weeks = []
    for week, rows in sorted(by_week.items()):
        ids = sorted(r["activity_id"] for r in rows)
        parent = {a: a for a in ids}
        equality = defaultdict(list)

        def root(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def join(a, b, reason):
            equality[a].append((b, reason))
            equality[b].append((a, reason))
            ra, rb = root(a), root(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        groups, local_indices, at_location = defaultdict(list), defaultdict(list), defaultdict(dict)
        for r in occ_week[week]:
            groups[(r["location_id"], r["co_share_group"])].append(r["activity_id"])
            at_location[r["location_id"]][r["activity_id"]] = r["co_share_group"]
        for r in rows:
            a = activities[r["activity_id"]]
            local_indices[(a["contract_number"], a["activity_type"], r["access_night"])].append(r["activity_id"])
        for (location, group), members in sorted(groups.items()):
            for member in sorted(members)[1:]:
                join(min(members), member, {"basis": "same_local_sharing_group", "location_id": location, "group": group})
        for (contract, kind, index), members in sorted(local_indices.items()):
            for member in sorted(members)[1:]:
                join(min(members), member, {"basis": "same_contract_local_index", "contract": contract, "activity_type": kind, "access_night": index})

        unequal = []
        for location, members in sorted(at_location.items()):
            for a, b in combinations(sorted(members), 2):
                if members[a] != members[b]:
                    unequal.append((a, b, {"basis": "different_groups_at_same_location", "location_id": location}))
        for (c1, t1, i1), (c2, t2, i2) in combinations(sorted(local_indices), 2):
            if (c1, t1) == (c2, t2) and i1 != i2:
                unequal.append((min(local_indices[(c1, t1, i1)]), min(local_indices[(c2, t2, i2)]),
                                {"basis": "different_indices_within_contract_type", "contract": c1, "activity_type": t1}))
        # Known minimum of R13: mirror the Live working core. Buffer expansion
        # and cross-line propagation remain unset; never invent their edges.
        mirror_edges = 0
        for a in ids:
            if activities[a]["nature_of_works"] != "Live":
                continue
            for location in activities[a]["working_span"]["location_ids"]:
                stem, bound = location.rsplit(":", 1)
                mirror = stem + (":WB" if bound == "EB" else ":EB")
                for b in sorted(at_location.get(mirror, {})):
                    if a != b:
                        unequal.append((a, b, {"basis": "live_opposite_bound_working_core", "location_id": mirror, "rule_id": "R13"}))
                        mirror_edges += 1

        members = defaultdict(list)
        for a in ids:
            members[root(a)].append(a)
        graph = {r: set() for r in members}
        edge_reasons = {}
        conflicts = []
        for a, b, reason in unequal:
            ra, rb = root(a), root(b)
            if ra == rb:
                conflicts.append({"kind": "equal_and_different_night", "activities": [a, b],
                                  "inequality": reason, "equality_path": equality_path(a, b, equality)})
            else:
                graph[ra].add(rb)
                graph[rb].add(ra)
                edge_reasons.setdefault(tuple(sorted((ra, rb))), {"activities": [a, b], **reason})
        for component in members.values():
            by_project = defaultdict(list)
            for a in component:
                by_project[tuple(activities[a]["project_key"])].append(a)
            for key, jobs in by_project.items():
                cap = projects[key]["number_of_workfronts"]
                if len(jobs) > cap:
                    witness = jobs[:cap+1]
                    conflicts.append({"kind": "simultaneous_workfront_excess", "activities": witness,
                                      "contract": key[0], "activity_type": key[1], "observed": len(jobs), "limit": cap,
                                      "equality_paths": [equality_path(witness[0], a, equality) for a in witness[1:]]})
        if conflicts:
            status, assignment, nodes = "INCONSISTENT_UNDER_ASSUMPTIONS", None, 0
        else:
            status, assignment, nodes = color_graph(graph, night_limit, search_budget)
            if status == "INCONSISTENT_UNDER_ASSUMPTIONS":
                conflicts.append({"kind": "night_limit_exceeded", "night_limit": night_limit,
                                  "activities": ids,
                                  "components": [{"component": r, "activities": jobs} for r, jobs in sorted(members.items())],
                                  "equality_edges": [{"activities": [a, b], **reason} for a in sorted(equality)
                                                     for b, reason in equality[a] if a < b],
                                  "separation_edges": [{"components": list(pair), "reason": reason}
                                                       for pair, reason in sorted(edge_reasons.items())],
                                  "explanation": "Exact search exhausted this constraint graph under the selected night limit. The witness is replayable, not minimised."})
        assigned, verification_errors = None, []
        if status == "ASSIGNED":
            if not isinstance(assignment, dict) or set(assignment) != set(members):
                verification_errors.append("Assignment must cover exactly the equality components.")
            elif any(type(n) is not int or not 1 <= n <= night_limit for n in assignment.values()):
                verification_errors.append("Assignment contains a noninteger or out-of-range night label.")
            else:
                candidate = {a: assignment[root(a)] for a in ids}
                if any(candidate[a] == candidate[b] for a, b, _ in unequal):
                    verification_errors.append("Assignment violates a required separation relation.")
                if any(candidate[a] != candidate[b] for a in equality for b, _ in equality[a]):
                    verification_errors.append("Assignment violates an equality relation.")
                counts = Counter((activities[a]["contract_number"], activities[a]["activity_type"], candidate[a]) for a in ids)
                if any(n > projects[(c, t)]["number_of_workfronts"] for (c, t, _), n in counts.items()):
                    verification_errors.append("Assignment exceeds a workfront limit.")
                if not verification_errors:
                    assigned = candidate
        elif status not in ("INCONSISTENT_UNDER_ASSUMPTIONS", "UNKNOWN_SEARCH_LIMIT") or assignment is not None:
            verification_errors.append("Unexpected search status or assignment payload.")
        if verification_errors:
            status = "INTERNAL_ERROR"
        weeks.append({"week": week, "status": status, "activity_count": len(ids),
                      "equality_components": len(members), "known_live_mirror_relations": mirror_edges,
                      "search_nodes": nodes, "assignment": assigned, "conflicts": conflicts,
                      "assignment_verification_errors": verification_errors,
                      "conflict_minimality_proven": False})
    statuses = {w["status"] for w in weeks}
    status = ("NO_ACCESSES" if not weeks else "INTERNAL_ERROR" if "INTERNAL_ERROR" in statuses else
              "INCONSISTENT_UNDER_ASSUMPTIONS" if "INCONSISTENT_UNDER_ASSUMPTIONS" in statuses else
              "UNKNOWN_SEARCH_LIMIT" if "UNKNOWN_SEARCH_LIMIT" in statuses else "ASSIGNED_FOR_MODELLED_RELATIONS")
    return {"status": status, "night_limit": night_limit, "search_budget_per_week": search_budget,
            "assumptions": ["One full physical night per activity access.",
                            "Local sharing and same contract/type index imply equal nights; different indices within that scope imply different nights.",
                            "Seven is a calendar upper bound, not supplied night availability. Lower limits are diagnostic what-if assumptions."],
            "checked_protection": "Working-core separation and Live opposite-bound working-core closures only.",
            "unverified_protection_rules": ["R12", "R15", "R16", "R17"],
            "physical_feasibility_established": False, "operational_authorisation": False, "weeks": weeks}
