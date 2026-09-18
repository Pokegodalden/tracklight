"""Author the Step 2 specification and extract cited sample rows. No solver."""
import csv
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/baselines/ps1-0dfd901f97bf579f"
OUT = ROOT / "specs/ps1/v0.1.0"
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))


def source(section, anchor, file="PS1/PS1_README.md"):
    text = (SNAPSHOT / file).read_text(encoding="utf-8-sig")
    assert anchor in text, (file, anchor)
    return {"file": file, "section": section, "anchor": anchor,
            "line": text[:text.index(anchor)].count("\n") + 1}


def rows(file):
    with (SNAPSHOT / file).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return [{"file": file, "line": reader.line_num, "row": row} for row in reader]


rules = []


def rule(id, title, status, sources, decision, policy, mode, enforcement, examples, question=None):
    rules.append(dict(id=id, title=title, status=status, sources=sources,
                      decision=decision, selected_policy=policy, enforcement_mode=mode,
                      enforcement_location=enforcement, examples=examples,
                      organiser_question=question,
                      organiser_response=None, official_rule_version=None))


rule("R01", "Complete workload and yield", "documented",
     [source("2.4 rule 1", "**Workload Conservation:**")],
     "All activities must reach at least their required workload. Standard=1 and ECLO=1.5 units; surplus caused by the final indivisible access is permitted by >=. No dropping work.",
     {"required_coverage": "all_activities", "unit_scale": 2, "standard_yield": 2, "eclo_yield": 3, "comparison": ">="},
     "enforce", "workload ledger / solver / checker", ["E01"])
rule("R02", "Earliest start week", "documented",
     [source("2.4 rule 2", "**Planned Start Date:**")],
     "Do not schedule before the planned-start week. Date-to-week conversion follows provisional R19; no intraweek start time is asserted.",
     {"release_constraint": "week >= planned_start_week", "calendar_rule": "R19"},
     "enforce", "calendar adapter / solver / checker", ["E06"])
rule("R03", "One access per activity per week", "documented",
     [source("2.4 rule 9", "Since an activity gets at most one access-night per week")],
     "Apply at most one activity access per week in all scenarios. The sentence appears in the C explanation but describes the activity granularity without a scenario qualifier.",
     {"max_accesses_per_activity_week": 1}, "enforce", "solver / checker", ["E05"])
rule("R04", "Working-span expansion", "provisional",
     [source("2.2", "A job that runs from one station to another must book every tunnel sector")],
     "For the supplied SEC endpoints, include every tunnel between them and all incident platforms on the same line/bound. Platform endpoints, reversed spans and disconnected/branching paths need explicit handling in Step 3; reject unsupported cases rather than invent a route.",
     {"sec_span": "inclusive_tunnels_and_incident_platforms", "unsupported_path": "input_error"},
     "enforce", "span expander / export checker", ["E09", "E24"], "Q03")
rule("R05", "Legal sharing composition", "documented",
     [source("2.4 rule 4", "**Possession Locations & Legal Mixes:**")],
     "Within one location/week/group: PM alone, one PC plus zero to three C, or one to four C. No PM+C, two PC, or fifth participant. Access type is independent of nature of works.",
     {"allowed": [{"PM": 1}, {"PC": 1, "C_max": 3}, {"C_max": 4}]},
     "enforce", "group builder / checker", ["E02"])
rule("R06", "Location capacity and excess accounting", "documented",
     [source("2.4 rule 5", "Same `(location_id, week, co_share_group)`"),
      source("2.7", "summed across location-weeks")],
     "Count distinct occupied groups per location/week, not activity rows. Excess is max(0, groups-supply), summed over location-weeks. A physical possession crossing three locations can therefore incur three excess units.",
     {"count": "distinct_group_per_location_week", "excess": "sum(max(0,groups-supply))"},
     "enforce", "capacity ledger / solver / checker", ["E03"])
rule("R07", "Contract-local allocation indices", "documented",
     [source("2.6", "accounting index per contract+type+week"), source("2.4 rule 6", "**Weekly Allocation:**")],
     "Use the supplied cap for (contract_number,activity_type,week). Indices are integers 1..cap. Equal indices in different contracts do not establish a common night.",
     {"scope": ["contract_number", "activity_type", "week"], "index_domain": "1..supplied_cap"},
     "enforce", "contract ledger / solver / checker", ["E04", "E08"])
rule("R08", "Local workfront limit", "documented",
     [source("2.4 rule 7", "**Workfronts:**")],
     "Count distinct activities per contract/type/week/access_night and enforce supplied workfronts. This check alone does not establish physical-night consistency (R10).",
     {"count": "distinct_activities_per_contract_type_week_access_night"},
     "enforce", "resource ledger / solver / checker", ["E04", "E08"])
rule("R09", "Sharing-label scope", "documented",
     [source("2.4 rule 5", "Same `(location_id, week, co_share_group)`"), source("2.6", "an arbitrary label like `b1`, `b2`")],
     "Labels are scoped to location and week. Never treat b1 as a globally named weekday or possession. Consistent renaming within each location/week leaves local accounting unchanged.",
     {"scope": ["location_id", "week", "co_share_group"], "global_label_identity": False},
     "enforce", "group model / checker", ["E07", "E26"])
rule("R10", "Common physical night", "provisional",
     [source("1", "a works controller could dispatch against"), source("2.4 rule 5", "separate possessions on separate nights")],
     "Use local weekly accounting for the provisional benchmark model. Separately diagnose one-full-night-per-access consistency. Do not impose an unconfirmed global-night constraint on the benchmark or call local success dispatch-ready.",
     {"benchmark": "local_weekly_accounting", "physical_night_check": "separate_diagnostic", "dispatch_ready": False},
     "diagnostic", "model adapter / future night diagnostic / UI", ["E07", "E08"], "Q01")
rule("R11", "Buffer class parameters", "documented",
     [source("buffer table", "nature_of_works,up_to_buffer_sectors", "PS1/01_data/05_BUFFER_LOCATION.csv")],
     "Read nature-of-works buffer counts from the supplied table: Live 2, Consist 1, Others 0; only Live requires opposite bound. These counts do not specify the whole expansion algorithm.",
     {"source_table": "05_BUFFER_LOCATION.csv", "join": "nature_of_activity -> nature_of_works"},
     "enforce", "rule input adapter", ["E09", "E10"])
rule("R12", "Buffer geometry and terminal treatment", "deferred",
     [source("2.4 rule 3", "**Closures and Buffers:**")],
     "No authoritative selection between tunnel-hop/platform-edge interpretations. Request exact affected-location sets, including terminals. Until configured, protection coverage is unverified, not passed; do not run an all-rules-feasible claim.",
     {"geometry": None, "terminal_policy": None, "missing_policy_result": "UNVERIFIED"},
     "unverified", "protection expander / checker readiness", ["E09"], "Q03")
rule("R13", "Live opposite-bound effect", "documented",
     [source("2.4 rule 3", "Live` mirrors closure to opposite bound")],
     "A Live closure affects the opposite bound. Whether and how the expanded buffer mirrors remains unconfigured with R12. Non-Live does not acquire this effect.",
     {"live_requires_opposite_bound": True, "extent_dependency": "R12"},
     "enforce", "protection expander", ["E10"])
rule("R14", "Independent interchange capacity", "provisional",
     [source("2.2", "physically two adjacent tunnels, not one shared track"),
      source("sector table", "SEC:ALP:H01_H02,ALP,H01,H02,5,0", "PS1/01_data/03_SECTORS.csv")],
     "Prefer detailed section 2.2 and the supplied is_shared=0 rows over the opening shared-track narrative. ALP/BET tunnel and platform capacity remain separate; Live protection can couple them. Do not map fictional hubs to real stations.",
     {"capacity": "separate_by_line_bound_location", "live_coupling": "protection_only"},
     "enforce", "network model / capacity ledger", ["E11"], "Q03")
rule("R15", "Live interchange trigger and footprint", "deferred",
     [source("2.2", "**The one exception — `Live`:**")],
     "Cross-line Live effects are required when applicable, but work-span versus buffer-contact triggering and exact propagation are unresolved. Require an explicit mapping before a complete protection check.",
     {"cross_line_live_effect_required": True, "trigger": None, "affected_locations": None, "missing_policy_result": "UNVERIFIED"},
     "unverified", "protection expander / ECLO affected-line resolver", ["E11"], "Q03")
rule("R16", "Sharing exemption extent", "provisional",
     [source("2.1 item 5", "PC` and `C` are already buffer-free against each other"),
      source("2.4 rule 5", "exempt from each other's closures")],
     "Provisionally recognise exemption only for the same group at the same location/week. Do not propagate A-B and B-C into A-C automatically or exempt every PC/C pair everywhere. Broader exemptions need confirmation; dependent protection checks remain unverified with R12/R17.",
     {"exemption_scope": "same_local_group", "transitive": False, "global_type_only_exemption": False},
     "enforce", "compatibility/protection checker", ["E12"], "Q04")
rule("R17", "Protection comparison time", "deferred",
     [source("2.4 rule 3", "no external activity may enter it that night")],
     "Neither overlapping weekly footprints nor matching local labels alone proves simultaneity. Keep potential intersections as candidates. A definite temporal protection verdict requires a confirmed night relation or official weekly rule.",
     {"comparison_time_model": None, "unmapped_overlap": "UNVERIFIED", "weekly_overlap_is_violation": False},
     "unverified", "protection conflict evaluator", ["E13"], "Q05")
rule("R18", "Predecessor ordering", "provisional",
     [source("activity schema", "predecessor_activity_id", "PS1/01_data/08_ACTIVITY_DETAILS.csv")],
     "For a nonblank predecessor, provisionally require its entire workload to finish in an earlier week. Treat unknown IDs/cycles as input errors; do not silently drop dependency edges. Same-week sequencing is not representable yet.",
     {"relation": "successor_first_week > predecessor_last_week", "unknown_or_cycle": "input_error"},
     "enforce", "dependency graph / solver / checker", ["E14"], "Q06")
rule("R19", "Calendar conversion and completion date", "provisional",
     [source("horizon parameters", "horizon_start,2027-01-04", "PS1/01_data/06_PARAMETERS.csv"),
      source("2.4 rule 2", "planned start week")],
     "Use seven-day buckets anchored at horizon_start. Release week=floor((date-start)/7)+1. Completion=start+7*last_week-1 days; this matches all 14 sample results but does not prove hidden-date semantics. Out-of-horizon cases follow R21.",
     {"week_days": 7, "release_rounding": "floor_plus_one", "completion": "last_day_of_last_week"},
     "enforce", "calendar adapter / metrics", ["E06", "E15"], "Q07")
rule("R20", "Static supply repeats within horizon", "provisional",
     [source("supply schema", "location_id,location_kind,line_code,bound,supply_capacity", "PS1/01_data/04_LOCATION_SUPPLY.csv")],
     "Repeat each supplied location capacity in each in-horizon week. Zero is a real capacity; an absent location is an input error, not unlimited supply. Weekly overrides will be explicit future changes, not invented input columns.",
     {"repeat_within_horizon": True, "missing_location": "input_error"},
     "enforce", "supply adapter / capacity ledger", ["E03", "E16"], "Q08")
rule("R21", "Horizon extension", "provisional",
     [source("horizon parameters", "horizon_weeks,30", "PS1/01_data/06_PARAMETERS.csv")],
     "Keep accesses in weeks 1..horizon_weeks until extension and its supply are authorised. Never invent extra weeks to hide infeasibility; report horizon-limited results as conditional.",
     {"min_week": 1, "max_week": "horizon_weeks", "extend": False},
     "enforce", "calendar validation / solver domain", ["E15", "E16"], "Q08")
rule("R22", "Scenario A policy", "documented",
     [source("2.5 A", "**Scenario A (Strict Supply, Flexible Schedule):**")],
     "No supply excess and no ECLO. Delay may occur; objective interpretation is R28. Never relax workload or protection to produce a result.",
     {"max_excess_per_location_week": 0, "eclo_allowed": False, "planned_date_hard": False},
     "enforce", "scenario adapter / solver / checker", ["E03", "E17"])
rule("R23", "Scenario B policy", "documented",
     [source("2.5 B", "**Scenario B (Strict Schedule, Flexible Supply):**")],
     "Planned completion is hard. Excess capacity is soft with no stated numeric ceiling. ECLO may occur in any week. Prose suggesting P3 slip in B conflicts with the explicit hard deadline; retain the hard deadline.",
     {"max_excess_per_location_week": None, "eclo_allowed": True, "planned_date_hard": True, "eclo_window_weeks": None},
     "enforce", "scenario adapter / solver / checker", ["E03", "E17"], "Q09")
rule("R24", "Scenario C capacity policy", "documented",
     [source("2.5 C", "up to 1 excess access-night per location-week")],
     "Allow at most one excess group per location/week above the supplied capacity, penalise every excess unit, permit delayed completion. Do not bake an additional supply increase into this allowance.",
     {"max_excess_per_location_week": 1, "eclo_allowed": True, "planned_date_hard": False},
     "enforce", "scenario adapter / solver / checker", ["E03", "E25"])
rule("R25", "Scenario C ECLO span and affected lines", "documented",
     [source("2.4 rule 9", "one continuous span of at most 2 calendar weeks")],
     "For each affected line, ECLO weeks must fit in at most two adjacent week buckets. Empty/single-week sets are allowed. Different lines choose independently; cross-line Live accesses must fit both. Determining affected lines depends on unresolved R15.",
     {"max_span_weeks": 2, "condition": "max_week-min_week <= 1", "line_windows_independent": True, "cross_line_live": "both_windows"},
     "enforce", "ECLO checker / solver", ["E18"])
rule("R26", "ECLO penalty unit", "provisional",
     [source("2.5 ECLO", "per ECLO-night used"), source("2.7 detail", "total access-nights across all activities")],
     "Provisionally charge 5 per eclo=1 activity-access row. Also expose the count separately; do not deduplicate by local groups across locations and call that physical nights. The alternative physical-possession price remains open.",
     {"unit": "activity_access", "penalty": 5}, "enforce", "score calculator", ["E19"], "Q10")
rule("R27", "Mixed ECLO flags within a shared group", "provisional",
     [source("2.4 rule 5", "one possession (one access-night slot)")],
     "Until clarified, require equal ECLO flags within a local sharing group. This is an explicitly stricter development choice, not a proven official constraint. Do not infer an extra ECLO award for a member flagged standard.",
     {"uniform_eclo_within_local_group": True}, "enforce", "group builder / checker", ["E20"], "Q10")
rule("R28", "Delay formula and metrics", "provisional",
     [source("2.5 formula", "\\text{Score}_{A}"), source("2.7", "summed per overrunning activity")],
     "Primary development score uses per-activity weighted planned-date lateness (100/10/1)*(1.3/1.2/1.0)*days. Separately report contract-day lateness and its contract-weighted total. A=delay, B=7*excess+5*ECLO, C=delay+7*excess+5*ECLO. Numeric scores remain provisional; unknown protection prevents a full-feasibility claim.",
     {"formula_id": "ps1-activity-delay-provisional-0.1.0", "contract_weights": {"1": 100, "2": 10, "3": 1}, "activity_multiplier_tenths": {"1": 13, "2": 12, "3": 10}, "delay_aggregation": "per_activity", "excess_weight": 7, "eclo_weight": 5, "official": False},
     "enforce", "score calculator / comparison UI", ["E21", "E22"], "Q09")
rule("R29", "Weighted priority versus strict precedence", "provisional",
     [source("2.5", "Contract tier decides which band you're in"), source("2.5 formula", "\\text{Score}_{C}")],
     "Minimise the scalar penalty; do not silently impose lexicographic contract priorities or a fixed ECLO-before-capacity heuristic. Aggregate weighted trade-offs can contradict prose saying never delay higher tiers. Compare alternatives under the chosen formula, not the prose's incomparable batch-cost ratios.",
     {"priority_mode": "weighted_sum", "lexicographic_priority": False, "fixed_lever_order": False},
     "enforce", "objective adapter / alternative ranking", ["E23"], "Q09")
rule("R30", "Occupancy export versus protection", "provisional",
     [source("2.6", "**`SCHEDULE_OCCUPANCY.csv`**")],
     "Export work-span rows only as the sample does. Keep buffers/mirrors/cross-line effects in separate derived records; do not count them as extra submitted working rows without expander confirmation.",
     {"export": "working_span_only", "protection": "separate_derived_records"},
     "enforce", "exporter / export checker", ["E24"], "Q03")
rule("R31", "Results aggregation and target date", "provisional",
     [source("2.6", "**`RESULTS.csv`**"), source("2.3", "planned_completion_date` (target)")],
     "One result per scenario/contract; complete at the maximum finishing week across its activities/types, using R19. Overrun=max(0, completion-planned_completion_date); keep contractual dates separate. Multiple project rows with conflicting planned dates require clarification rather than an arbitrary first match.",
     {"completion": "max_activity_finish_per_contract", "overrun_target": "planned_completion_date", "negative_overrun": 0, "ambiguous_contract_dates": "input_error"},
     "enforce", "results exporter / metrics", ["E15", "E21", "E22"], "Q07")
rule("R32", "Scenario input identity", "provisional",
     [source("2.5 C", "a Scenario C instance generated with amended, higher local supply")],
     "Develop A/B/C against the same frozen eight CSVs until another manifest is supplied. Label C input applicability provisional. Never edit the baseline or fabricate the amended C capacities.",
     {"development_inputs": "same_frozen_eight_files", "C_input_applicability": "unconfirmed", "invent_amended_supply": False},
     "enforce", "run configuration / provenance", ["E25"], "Q11")
rule("R33", "Output contract and unsupported instances", "documented",
     [source("2.6", "three scenario answer keys"), source("4", "hidden test instance (the 8 CSV instance files)")],
     "Three CSVs per scenario, exact documented columns. The eventual importer must accept supported unseen IDs/counts, not just the sample. Endpoint/category variations and solve-time limits still need organiser confirmation; reject unsupported structures clearly.",
     {"scenarios": ["A", "B", "C"], "files_per_scenario": 3, "hardcoded_sample_ids": False},
     "enforce", "import contract / exporter / hosted UI", ["E26"], "Q12")
rule("R34", "No fabricated success under congestion", "provisional",
     [source("1", "**Keep Scheduling Under Congestion**"), source("1", "**Feasibility First**")],
     "Persist in searching permitted alternatives, but distinguish timeout from proven infeasibility under selected assumptions. The brief's request not to declare impossibility cannot authorise dropping work, exceeding hard scenario limits or claiming an unchecked feasible result.",
     {"safety_relaxation": False, "drop_workload": False, "outcomes": ["feasible_under_profile", "optimal_under_profile", "infeasible_under_profile", "no_solution_within_limit", "unverified_rules"]},
     "enforce", "run-status reporting", ["E17", "E25"], "Q12")

cases = []


def case(id, title, rule_ids, given, expected, basis, question=None, evidence=None):
    cases.append(dict(id=id, title=title, rule_ids=rule_ids, given=given,
                      expected_by_interpretation=expected, expectation_basis=basis,
                      question=question, evidence=evidence or [], official_result=None,
                      scope="Isolated rule example, not a complete eight-CSV instance or full feasibility verdict"))


case("E01", "Workload conservation", ["R01"], {"required_units": 3, "scenario": "B", "placements": "distinct eligible weeks; other constraints satisfied"},
     {"two_standard": "FAIL: 2 < 3", "three_standard": "PASS: 3 >= 3", "two_ECLO": "PASS: 3 >= 3", "one_standard_one_ECLO": "FAIL: 2.5 < 3"}, "documented rule; hand calculation")
case("E02", "Composition at one location/week/group", ["R05"], {"nature": "Non-live (Others)", "same_local_group": True},
     {"PM": "PASS", "PM+C": "FAIL", "PC": "PASS", "PC+3C": "PASS", "4C": "PASS", "2PC": "FAIL", "5C": "FAIL"}, "documented composition only")
case("E03", "Capacity is groups, not participant rows", ["R06", "R20", "R22", "R23", "R24"], {"location": "L", "week": 10, "supply": 1},
     {"one_group_PC_plus_3C": "groups=1, excess=0; capacity passes A/B/C", "two_groups_C_each": "excess=1; A fails, B/C capacity passes with penalty 7", "three_groups_C_each": "excess=2; A/C fail, B capacity passes with penalty 14", "two_groups_at_each_of_three_locations": "total excess=3; B/C excess penalty=21 if each location has supply 1"}, "documented group/excess arithmetic; other constraints excluded")
case("E04", "Local budget and workfront", ["R07", "R08"], {"contract": "K", "activity_type": "Renewal", "week": 10, "cap": 3, "workfronts": 1, "activities": ["a", "b"]},
     {"indices_1_and_1": "FAIL workfront: two activities on one index", "indices_1_and_2": "PASS local budget/workfront", "indices_1_and_4": "FAIL index domain even though only two indices used"}, "documented local checks")
case("E05", "Do not spend two accesses on one activity/week", ["R03"], {"activity": "a", "required_units": 2, "proposed_access_weeks": [10, 10]}, {"one_access_rule": "FAIL even with ample supply and workfronts"}, "documented activity granularity")
case("E06", "Start week and partial-week release", ["R02", "R19"], {"horizon_start": "2027-01-04", "planned_start": "2027-01-13"}, {"provisional": "release week 2; week 1 FAIL, week 2 passes week-level release only; Monday/Wednesday physical timing not established"}, "date conversion assumption", "Q07")

occupancy = rows("PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv")
access = rows("PS1/03_submission_sample/SCHEDULE_ACCESS.csv")
projects = rows("PS1/01_data/07_PROJECT_DETAILS.csv")
activities = rows("PS1/01_data/08_ACTIVITY_DETAILS.csv")
results = rows("PS1/03_submission_sample/RESULTS.csv")
sample7 = [r for r in occupancy if r["row"]["activity_id"] in ("A001", "A011") and r["row"]["week"] == "23" and r["row"]["location_id"] in ("PLAT:BET:S15:EB", "PLAT:BET:S16:EB")]
assert len(sample7) == 4
case("E07", "Reference sample has contradictory night equalities", ["R09", "R10"], {"week": 23, "activities": ["A001", "A011"], "observed_groups": [r["row"] for r in sample7]},
     {"local_group_interpretation": "These rows alone do not violate local group accounting", "one_full_night_per_access": "IMPOSSIBLE: S16 requires night(A001)=night(A011), while S15 requires them unequal"},
     "source observation plus conditional logical proof", "Q01", sample7)
sample8 = [r for r in occupancy if r["row"]["activity_id"] in ("A040", "A042") and r["row"]["week"] == "25" and r["row"]["location_id"] == "SEC:BET:S15_S16:EB"]
sample8 += [r for r in access if r["row"]["activity_id"] in ("A040", "A042") and r["row"]["week"] == "25"]
sample8 += [r for r in projects if r["row"]["contract_number"] == "C007"]
sample8 += [r for r in activities if r["row"]["activity_id"] in ("A040", "A042")]
assert len(sample8) == 7
case("E08", "One workfront but a shared physical night", ["R07", "R08", "R10"], {"week": 25, "contract": "C007", "activities": ["A040", "A042"], "workfronts": 1, "local_indices": [3, 1], "shared_group": "b4 at SEC:BET:S15_S16:EB"},
     {"local_indices": "No mutual workfront breach from this pair; indices differ", "simultaneous_shared_night": "FAIL: two simultaneous activities exceed the same contract/type's one workfront"},
     "source observation; physical interpretation conditional", "Q02", sample8)
case("E09", "Exact buffer locations and terminal", ["R04", "R11", "R12"], {"line_order": ["S01", "S02", "S03", "S04"], "activity": "Non-live (Consist) at SEC:ALP:S02_S03:EB", "work_locations": ["SEC:ALP:S02_S03:EB", "PLAT:ALP:S02:EB", "PLAT:ALP:S03:EB"], "buffer_count": 1},
     {"candidate_tunnel_hop_with_outer_platforms": ["SEC:ALP:S01_S02:EB", "PLAT:ALP:S01:EB", "SEC:ALP:S03_S04:EB", "PLAT:ALP:S04:EB"], "candidate_tunnels_only": ["SEC:ALP:S01_S02:EB", "SEC:ALP:S03_S04:EB"], "selected_geometry": "UNVERIFIED; neither candidate adopted", "terminal_variant": "Move work to S01-S02; confirm truncate-versus-reject when no upstream sector exists"}, "alternative candidate extra-buffer sets; not authoritative footprints", "Q03")
case("E10", "How much of a Live footprint mirrors?", ["R11", "R13"], {"work": "SEC:ALP:S01_S02:EB", "nature": "Live", "candidate_same_bound_protected_station_range": "S01 through S04 after two downstream tunnel hops"},
     {"required_effect": "Opposite-bound closure is required", "work_only_mirror_candidate": ["SEC:ALP:S01_S02:WB", "PLAT:ALP:S01:WB", "PLAT:ALP:S02:WB"], "full_footprint_mirror_candidate": "Also mirror S02-S03, S03-S04 and S03/S04 platforms WB", "selected_extent": "UNVERIFIED pending exact mapping"}, "opposite-bound principle documented; extent unresolved", "Q03")
case("E11", "Interchange coupling is not shared capacity", ["R14", "R15"], {"variant_1": "Non-live jobs on ALP and BET H01-H02", "variant_2": "Live work directly on ALP H01-H02 EB", "variant_3": "Live work outside hub; only its candidate buffer reaches H01"},
     {"variant_1": "Separate capacity ledgers under selected detailed-section interpretation", "variant_2": "Cross-line protection required; request exact Beta tunnel/platform/bound set and whether buffers extend beyond hubs", "variant_3": "Trigger UNVERIFIED; do not infer from geographic contact alone"}, "mixed documented principle and unconfigured geometry", "Q03")
case("E12", "Sharing is not automatically transitive", ["R16"], {"same_week": 10, "A_B": "share group at X", "B_C": "share group at Y", "A_C": "protected footprints intersect at Z; no common local group at Z"},
     {"selected_local_exemption": "No A-C exemption at Z; actual violation still depends on timing/geometry", "global_component_exemption": "Would exempt A-C if an organiser-defined shared-possession component rule permits it", "official": "UNKNOWN"}, "alternative interpretation test", "Q04")
case("E13", "A weekly footprint overlap is insufficient", ["R17"], {"two_activities": "incompatible protected footprints overlap", "week": 10},
     {"explicit_same_night": "Conflict under full-night model", "explicit_different_nights": "No simultaneous protection conflict from this pair", "only_week_and_local_labels": "UNVERIFIED; retain a candidate intersection, not a confirmed breach"}, "conditional temporal reasoning, not an official checker", "Q05")
case("E14", "Predecessor finishing week", ["R18"], {"predecessor": "P", "successor": "S", "P_full_workload_finish_week": 2},
     {"selected_S_week_2": "FAIL", "selected_S_week_3": "PASS dependency only", "alternative_intraweek_model": "S in week 2 could pass if P finishes before S starts; missing timestamps prevent proving it", "unknown_predecessor_or_cycle": "INPUT ERROR under selected policy"}, "provisional strict-next-week ordering", "Q06")
case("E15", "Week boundaries and contract completion", ["R19", "R21", "R31"], {"horizon_start": "2027-01-04", "weeks": 30, "two_activity_last_weeks": [1, 2]},
     {"week_1_end": "2027-01-10", "week_30_end": "2027-08-01", "contract_finish": "2027-01-17 under last-week-end convention", "week_31": "Outside selected horizon; hypothetical week end 2027-08-08 is not permission to schedule there", "non_Sunday_deadline": "May create partial-week lateness under selected convention; request official date convention"}, "provisional calendar arithmetic", "Q07")
case("E16", "No invented capacity", ["R20", "R21"], {"capacity_at_L": 0, "location_M": "absent", "request_week": 31, "horizon_weeks": 30},
     {"L_one_group_in_A": "FAIL capacity", "M": "INPUT ERROR, not capacity 0 or infinity", "week_31": "FAIL selected horizon; an extended model requires confirmed supply and calendar rules"}, "explicit development assumptions", "Q08")
case("E17", "Hard scenario limits override heuristic advice", ["R22", "R23", "R34"], {"case_A": "One ECLO access", "case_B": "Priority-3 contract finishes seven days after planned date"},
     {"A": "FAIL even if it reduces delay", "B": "FAIL even if the delay would have a low penalty", "no_feasible_result": "Report outcome honestly; do not convert either hard rule to a soft penalty"}, "explicit scenario definitions preferred over inconsistent heuristic prose", "Q09")
case("E18", "C ECLO calendar span", ["R25"], {"scenario": "C", "affected_lines": "explicitly provided for this isolated test; geometry is not inferred"},
     {"same_line_weeks_10_11": "PASS", "same_line_weeks_10_12": "FAIL", "same_line_week_10_only": "PASS", "no_ECLO": "PASS window check", "ALP_10_BET_12_without_cross_line": "PASS independent windows", "add_cross_line_week_12": "FAIL ALP becomes {10,12}", "scenario_B_weeks_10_12": "No C-window restriction"}, "documented span check with stipulated affected lines")
case("E19", "One shared possession, two ECLO activities", ["R26"], {"scenario": "B", "activities": ["a", "b"], "required_each": 1.5, "eclo_each": 1, "locations": ["L"], "same_local_group": True, "excess": 0, "access_type_each": "C"},
     {"selected_per_activity": "2 ECLO accesses; penalty 10; 1.5 units credited to each", "per_physical_possession": "1 physical ECLO night; penalty 5 if that is the official accounting unit", "official": "UNKNOWN"}, "provisional penalty-counting comparison", "Q10")
case("E20", "Mixed ECLO flags in one group", ["R27"], {"activities": ["a", "b"], "same_local_group": True, "eclo_flags": [0, 1]},
     {"selected_uniform_policy": "FAIL profile-specific rule, not a confirmed official violation", "alternative_individual_duration_policy": "Could allow mixed flags with credits 1 and 1.5; must be confirmed"}, "stricter provisional development choice", "Q10")
case("E21", "Activity and contract delay are different", ["R28", "R31"], {"contract_priority": 3, "two_activities": [{"late_days": 7, "activity_priority": 1}, {"late_days": 14, "activity_priority": 3}], "excess_units": 2, "eclo_activity_accesses": 3},
     {"contract_late_days": 14, "raw_activity_late_days": 21, "selected_activity_weighted_delay": "23.1", "alternative_contract_weighted_delay": "14", "selected_C_score": "52.1", "alternative_C_score": "43", "B_component_score": "29 but this late schedule is infeasible in B"}, "hand arithmetic under clearly separated candidate formulas", "Q09")

project_by_id = {r["row"]["contract_number"]: r["row"] for r in projects}
activity_by_id = {r["row"]["activity_id"]: r["row"] for r in activities}
last_weeks = {}
for record in access:
    row = record["row"]
    last_weeks[row["activity_id"]] = max(last_weeks.get(row["activity_id"], 0), int(row["week"]))
start = date(2027, 1, 4)
late = []
for activity_id, week in sorted(last_weeks.items()):
    activity = activity_by_id[activity_id]
    project = project_by_id[activity["contract_number"]]
    days = max(0, (start + timedelta(days=7*week-1) - date.fromisoformat(project["planned_completion_date"])).days)
    if days:
        cost = Decimal(days) * {"1": 100, "2": 10, "3": 1}[project["contract_priority"]] * {"1": Decimal("1.3"), "2": Decimal("1.2"), "3": Decimal("1")}[activity["activity_priority"]]
        late.append({"activity_id": activity_id, "contract": activity["contract_number"], "late_days": days, "weighted": str(cost)})
assert sum(x["late_days"] for x in late) == 42
assert sum(Decimal(x["weighted"]) for x in late) == Decimal("48.3")
assert sum(int(r["row"]["overrun_days"]) for r in results) == 28
case("E22", "Reference sample score reconciliation", ["R28", "R31"], {"sample_scenario": "A", "late_activities": late, "calendar_assumption": "R19", "planned_date_assumption": "R31"},
     {"contract_days_from_RESULTS": 28, "activity_days": 42, "candidate_activity_weighted_score": "48.3", "candidate_contract_weighted_score": "28", "official_objective": "UNKNOWN; request validator JSON/formula version"}, "source counts plus conditional independent arithmetic", "Q09", results)
case("E23", "A scalar objective is not lexicographic priority", ["R29"], {"alternative_X": "one P1 activity 7 days late, activity priority 3", "alternative_Y": "one P2 activity 77 days late, activity priority 3", "other_penalties": 0, "scenario": "A or C"},
     {"weighted_sum": "X=700, Y=770, so X wins", "strict_priority_first": "Y wins because it avoids any P1 delay", "selected": "weighted_sum provisionally; organiser confirmation required"}, "mathematical counterexample to strict-priority prose", "Q09")
sample24 = [r for r in occupancy if r["row"]["activity_id"] == "A074" and r["row"]["week"] == "21"]
assert len(sample24) == 3
case("E24", "Export excludes derived protection in the sample", ["R04", "R30"], {"activity": "A074", "week": 21, "sample_working_rows": [r["row"] for r in sample24]},
     {"selected_export": "Three ALP EB working-location rows only", "internal_protection": "Keep opposite-bound/cross-line/buffer effects separately; actual expansion still unresolved", "official_expander": "UNKNOWN"}, "observed sample format, not complete protection proof", "Q03", sample24)
case("E25", "Do not fabricate Scenario C supply", ["R24", "R32", "R34"], {"C_nominal_supply": 1, "proposed_groups": 3},
     {"provided_supply": "FAIL: excess 2 exceeds C allowance 1", "invented_amended_supply_2": "Would pass capacity with excess 1, but that input change is unauthorised", "selected": "Use provided supply, label scenario-input applicability provisional, request official C manifest"}, "documented allowance plus provisional input applicability", "Q11")
case("E26", "Output sets and label renaming", ["R09", "R33"], {"scenarios": ["A", "B", "C"], "group_rename": "At one fixed location/week rename each distinct label bijectively"},
     {"output_files": "3 CSVs per scenario, 9 total; do not mix scenario labels within RESULTS", "renaming": "Local feasibility and score unchanged; never merge two labels or apply a numeric weekday meaning", "hidden_instances": "Different IDs/counts are not a reason for rejection; supported schema/domain governs"}, "documented output and label scope")

questions = [
    ("Q01", "P0", ["E07"], "Must every activity access use one common physical night over its full span, or does the judged model check local location/week packing only?", "Return a physical-night assignment for Week 23 A001/A011, a corrected sample, or explicit confirmation of local-only validation. Equal at S16 and unequal at S15 cannot both hold under the full-night interpretation."),
    ("Q02", "P0", ["E08"], "Which field defines simultaneous work for a contract's workfront cap?", "Explain Week 25 A040/A042 (C007 workfront=1, local nights 3/1, shared b4). State whether shared groups override local indices and supply expected pass/fail."),
    ("Q03", "P0", ["E09", "E10", "E11", "E24"], "Please specify the complete protection-expansion algorithm and export scope.", "Return exact working/buffer/mirrored/cross-line location lists for E09-E11, including a terminal, a buffer touching an interchange, and direct hub work. Confirm platform inclusion, trigger, propagation limit, capacity treatment, and whether occupancy exports remain working-span-only as E24 shows. Confirm separate line capacities from section 2.2."),
    ("Q04", "P0", ["E12"], "Is the sharing exemption local to a group/location, pairwise across a possession, or transitive across linked groups?", "Give a verdict for A-B at X and B-C at Y with an A-C protected intersection at Z. Clarify the scope of the PC/C buffer-free prose."),
    ("Q05", "P0", ["E13"], "How does the validator determine whether two protected footprints overlap in time?", "Specify the comparison key or required night mapping. Give pass/fail for same night, different nights, and only weekly/group information. Do not rely on identical label strings across locations."),
    ("Q06", "P1", ["E14"], "Is predecessor_activity_id enforced, and may a successor start in the predecessor's finishing week?", "Return E14 outcomes and treatment of cycles, unknown IDs, full-workload completion and same-week sequencing."),
    ("Q07", "P1", ["E06", "E15", "E21", "E22"], "What are the exact date-to-week and completion conventions?", "Confirm partial-week planned starts, week-end completion, planned versus contractual overrun target, and contract aggregation across activity types. Supply a non-Monday start/non-Sunday deadline example."),
    ("Q08", "P1", ["E16"], "Does static supply repeat weekly, and may schedules extend beyond horizon_weeks?", "Specify capacity/calendar beyond the horizon, missing-location handling and whether any actual weekday availability is supplied. Confirm extension policy separately for A/B/C."),
    ("Q09", "P0", ["E17", "E21", "E22", "E23"], "Which formula and priority policy are authoritative?", "Return official sample metrics/objective and formula version: contract days 28 versus activity days 42 versus weighted activity 48.3. Resolve E21's 23.1 versus 14 delay score, E23's scalar versus lexicographic ranking, and the B hard deadline versus prose suggesting P3 slip. Confirm 7 per excess unit and 5 per ECLO unit; the heuristic table compares different batch quantities."),
    ("Q10", "P1", ["E19", "E20"], "How are ECLO yield, penalties and flags handled for co-sharing activities?", "For two activities in one ECLO possession, state penalty 10 or 5 (or another documented rule), each activity's credited workload, and whether mixed 0/1 flags are legal. Define possession identity if used for deduplication."),
    ("Q11", "P1", ["E25"], "Which input files belong to A, B and C?", "Provide authoritative scenario manifests/checksums or confirm all use the supplied eight files. If C has amended supply, provide that file; also provide B/C sample outputs if available."),
    ("Q12", "P0", ["E17", "E25", "E26"], "Please provide official tooling and the hidden-instance execution contract.", "Provide validator/expander package or repository, version/commit, exact commands, sample validator JSON, limits on solve time/memory/file sizes and allowed schema/category/path variations. Confirm how an infeasible or timed-out instance should be reported without weakening hard constraints."),
]
question_records = [dict(id=q[0], priority=q[1], examples=q[2], question=q[3], requested_response=q[4], sent=False, response=None) for q in questions]

common = {"version": "0.1.0", "snapshot_id": manifest["snapshot_id"], "pack_sha256": manifest["pack_sha256"], "input_data_sha256": manifest["input_data_sha256"]}
register = {**common, "status_definitions": {
    "documented": "Explicit in the frozen source, not independently confirmed by organiser or official executable.",
    "provisional": "Selected development interpretation, with alternatives/questions retained.",
    "deferred": "No authoritative operational choice. Explicit policy returns UNVERIFIED and blocks a full-feasibility claim."
}, "rules": rules, "questions": question_records}
examples = {**common, "description": "Isolated rule specifications, not runnable full submission fixtures or an official test suite.", "cases": cases}
profile = {**common, "profile_id": "ps1-provisional-0.1.0", "officially_confirmed": False,
           "readiness": {"step3_import_model": "ready_under_disclosed_assumptions", "complete_protection_validation": False, "official_score_equivalence": False, "physical_dispatch": False},
           "claim_policy": {"unverified_check_is_pass": False, "missing_rule_result": "UNVERIFIED", "full_feasibility_requires_all_required_checks": True, "official_validation_requires_actual_tool_result": True},
           "rules": {r["id"]: {"status": r["status"], "mode": r["enforcement_mode"], "policy": r["selected_policy"]} for r in rules},
           "unconfigured_rules": [r["id"] for r in rules if r["status"] == "deferred"]}
for name, data in (("rules.json", register), ("examples.json", examples), ("profile.json", profile)):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
profile["rules_sha256"] = hashlib.sha256((OUT / "rules.json").read_bytes()).hexdigest()
profile["examples_sha256"] = hashlib.sha256((OUT / "examples.json").read_bytes()).hexdigest()
(OUT / "profile.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"rules": len(rules), "cases": len(cases), "questions": len(questions), "unconfigured": profile["unconfigured_rules"]}))
