# PS1 small rule examples

Version 0.1.0; baseline `ps1-0dfd901f97bf579f`. No organiser response or official tool result is available.

These are isolated specifications with stipulated context, not complete eight-CSV submissions. PASS/FAIL applies only to the named rule/interpretation. None is an official validator verdict. Synthetic names such as a, b and L are placeholders, not missing baseline records.

Only the cited sample rows and selected arithmetic/logic observations are recomputed by the Step 2 checker. The remaining outcomes are authored expectations for later checker/solver tests.

<a id="e01"></a>

## E01 — Workload conservation

Rules: R01. Basis: documented rule; hand calculation.

Given:

- required_units: 3
- scenario: B
- placements: distinct eligible weeks; other constraints satisfied

Expected under each interpretation:

- **two_standard:** FAIL: 2 < 3
- **three_standard:** PASS: 3 >= 3
- **two_ECLO:** PASS: 3 >= 3
- **one_standard_one_ECLO:** FAIL: 2.5 < 3

Organiser question: None currently required. Official result: unknown.

<a id="e02"></a>

## E02 — Composition at one location/week/group

Rules: R05. Basis: documented composition only.

Given:

- nature: Non-live (Others)
- same_local_group: true

Expected under each interpretation:

- **PM:** PASS
- **PM+C:** FAIL
- **PC:** PASS
- **PC+3C:** PASS
- **4C:** PASS
- **2PC:** FAIL
- **5C:** FAIL

Organiser question: None currently required. Official result: unknown.

<a id="e03"></a>

## E03 — Capacity is groups, not participant rows

Rules: R06, R20, R22, R23, R24. Basis: documented group/excess arithmetic; other constraints excluded.

Given:

- location: L
- week: 10
- supply: 1

Expected under each interpretation:

- **one_group_PC_plus_3C:** groups=1, excess=0; capacity passes A/B/C
- **two_groups_C_each:** excess=1; A fails, B/C capacity passes with penalty 7
- **three_groups_C_each:** excess=2; A/C fail, B capacity passes with penalty 14
- **two_groups_at_each_of_three_locations:** total excess=3; B/C excess penalty=21 if each location has supply 1

Organiser question: None currently required. Official result: unknown.

<a id="e04"></a>

## E04 — Local budget and workfront

Rules: R07, R08. Basis: documented local checks.

Given:

- contract: K
- activity_type: Renewal
- week: 10
- cap: 3
- workfronts: 1
- activities: ["a", "b"]

Expected under each interpretation:

- **indices_1_and_1:** FAIL workfront: two activities on one index
- **indices_1_and_2:** PASS local budget/workfront
- **indices_1_and_4:** FAIL index domain even though only two indices used

Organiser question: None currently required. Official result: unknown.

<a id="e05"></a>

## E05 — Do not spend two accesses on one activity/week

Rules: R03. Basis: documented activity granularity.

Given:

- activity: a
- required_units: 2
- proposed_access_weeks: [10, 10]

Expected under each interpretation:

- **one_access_rule:** FAIL even with ample supply and workfronts

Organiser question: None currently required. Official result: unknown.

<a id="e06"></a>

## E06 — Start week and partial-week release

Rules: R02, R19. Basis: date conversion assumption.

Given:

- horizon_start: 2027-01-04
- planned_start: 2027-01-13

Expected under each interpretation:

- **provisional:** release week 2; week 1 FAIL, week 2 passes week-level release only; Monday/Wednesday physical timing not established

Organiser question: Q07. Official result: unknown.

<a id="e07"></a>

## E07 — Reference sample has contradictory night equalities

Rules: R09, R10. Basis: source observation plus conditional logical proof.

Given:

- week: 23
- activities: ["A001", "A011"]
- observed_groups: [{"activity_id": "A001", "week": "23", "location_id": "PLAT:BET:S15:EB", "co_share_group": "b2"}, {"activity_id": "A001", "week": "23", "location_id": "PLAT:BET:S16:EB", "co_share_group": "b2"}, {"activity_id": "A011", "week": "23", "location_id": "PLAT:BET:S15:EB", "co_share_group": "b1"}, {"activity_id": "A011", "week": "23", "location_id": "PLAT:BET:S16:EB", "co_share_group": "b2"}]

Expected under each interpretation:

- **local_group_interpretation:** These rows alone do not violate local group accounting
- **one_full_night_per_access:** IMPOSSIBLE: S16 requires night(A001)=night(A011), while S15 requires them unequal

Exact source records:

- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 7](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A001", "week": "23", "location_id": "PLAT:BET:S15:EB", "co_share_group": "b2"}`
- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 8](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A001", "week": "23", "location_id": "PLAT:BET:S16:EB", "co_share_group": "b2"}`
- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 143](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A011", "week": "23", "location_id": "PLAT:BET:S15:EB", "co_share_group": "b1"}`
- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 144](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A011", "week": "23", "location_id": "PLAT:BET:S16:EB", "co_share_group": "b2"}`

Organiser question: Q01. Official result: unknown.

<a id="e08"></a>

## E08 — One workfront but a shared physical night

Rules: R07, R08, R10. Basis: source observation; physical interpretation conditional.

Given:

- week: 25
- contract: C007
- activities: ["A040", "A042"]
- workfronts: 1
- local_indices: [3, 1]
- shared_group: b4 at SEC:BET:S15_S16:EB

Expected under each interpretation:

- **local_indices:** No mutual workfront breach from this pair; indices differ
- **simultaneous_shared_night:** FAIL: two simultaneous activities exceed the same contract/type's one workfront

Exact source records:

- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 531](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A040", "week": "25", "location_id": "SEC:BET:S15_S16:EB", "co_share_group": "b4"}`
- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 556](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A042", "week": "25", "location_id": "SEC:BET:S15_S16:EB", "co_share_group": "b4"}`
- [PS1/03_submission_sample/SCHEDULE_ACCESS.csv — record, line 115](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_ACCESS.csv): `{"activity_id": "A040", "access_seq": "7", "week": "25", "eclo": "0", "access_night": "3"}`
- [PS1/03_submission_sample/SCHEDULE_ACCESS.csv — record, line 120](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_ACCESS.csv): `{"activity_id": "A042", "access_seq": "3", "week": "25", "eclo": "0", "access_night": "1"}`
- [PS1/01_data/07_PROJECT_DETAILS.csv — record, line 8](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/07_PROJECT_DETAILS.csv): `{"contract_number": "C007", "contract_description": "Renewal programme 7", "contract_award_date": "2026-01-13", "activity_type": "Renewal", "nature_of_activity": "Non-live (Consist)", "contract_priority": "1", "contract_completion_date": "2027-07-25", "planned_completion_date": "2027-07-11", "number_of_workfronts": "1", "access_type": "C", "number_of_maximum_access_per_week": "3"}`
- [PS1/01_data/08_ACTIVITY_DETAILS.csv — record, line 27](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/08_ACTIVITY_DETAILS.csv): `{"activity_id": "A040", "contract_number": "C007", "activity_type": "Renewal", "start_location_id": "SEC:BET:H01_H02:EB", "end_location_id": "SEC:BET:S15_S16:EB", "total_accesses": "7", "planned_start_date": "2027-03-29", "predecessor_activity_id": "", "activity_priority": "1"}`
- [PS1/01_data/08_ACTIVITY_DETAILS.csv — record, line 29](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/08_ACTIVITY_DETAILS.csv): `{"activity_id": "A042", "contract_number": "C007", "activity_type": "Renewal", "start_location_id": "SEC:BET:S15_S16:EB", "end_location_id": "SEC:BET:S17_S18:EB", "total_accesses": "3", "planned_start_date": "2027-06-07", "predecessor_activity_id": "", "activity_priority": "2"}`

Organiser question: Q02. Official result: unknown.

<a id="e09"></a>

## E09 — Exact buffer locations and terminal

Rules: R04, R11, R12. Basis: alternative candidate extra-buffer sets; not authoritative footprints.

Given:

- line_order: ["S01", "S02", "S03", "S04"]
- activity: Non-live (Consist) at SEC:ALP:S02_S03:EB
- work_locations: ["SEC:ALP:S02_S03:EB", "PLAT:ALP:S02:EB", "PLAT:ALP:S03:EB"]
- buffer_count: 1

Expected under each interpretation:

- **candidate_tunnel_hop_with_outer_platforms:** ["SEC:ALP:S01_S02:EB", "PLAT:ALP:S01:EB", "SEC:ALP:S03_S04:EB", "PLAT:ALP:S04:EB"]
- **candidate_tunnels_only:** ["SEC:ALP:S01_S02:EB", "SEC:ALP:S03_S04:EB"]
- **selected_geometry:** UNVERIFIED; neither candidate adopted
- **terminal_variant:** Move work to S01-S02; confirm truncate-versus-reject when no upstream sector exists

Organiser question: Q03. Official result: unknown.

<a id="e10"></a>

## E10 — How much of a Live footprint mirrors?

Rules: R11, R13. Basis: opposite-bound principle documented; extent unresolved.

Given:

- work: SEC:ALP:S01_S02:EB
- nature: Live
- candidate_same_bound_protected_station_range: S01 through S04 after two downstream tunnel hops

Expected under each interpretation:

- **required_effect:** Opposite-bound closure is required
- **work_only_mirror_candidate:** ["SEC:ALP:S01_S02:WB", "PLAT:ALP:S01:WB", "PLAT:ALP:S02:WB"]
- **full_footprint_mirror_candidate:** Also mirror S02-S03, S03-S04 and S03/S04 platforms WB
- **selected_extent:** UNVERIFIED pending exact mapping

Organiser question: Q03. Official result: unknown.

<a id="e11"></a>

## E11 — Interchange coupling is not shared capacity

Rules: R14, R15. Basis: mixed documented principle and unconfigured geometry.

Given:

- variant_1: Non-live jobs on ALP and BET H01-H02
- variant_2: Live work directly on ALP H01-H02 EB
- variant_3: Live work outside hub; only its candidate buffer reaches H01

Expected under each interpretation:

- **variant_1:** Separate capacity ledgers under selected detailed-section interpretation
- **variant_2:** Cross-line protection required; request exact Beta tunnel/platform/bound set and whether buffers extend beyond hubs
- **variant_3:** Trigger UNVERIFIED; do not infer from geographic contact alone

Organiser question: Q03. Official result: unknown.

<a id="e12"></a>

## E12 — Sharing is not automatically transitive

Rules: R16. Basis: alternative interpretation test.

Given:

- same_week: 10
- A_B: share group at X
- B_C: share group at Y
- A_C: protected footprints intersect at Z; no common local group at Z

Expected under each interpretation:

- **selected_local_exemption:** No A-C exemption at Z; actual violation still depends on timing/geometry
- **global_component_exemption:** Would exempt A-C if an organiser-defined shared-possession component rule permits it
- **official:** UNKNOWN

Organiser question: Q04. Official result: unknown.

<a id="e13"></a>

## E13 — A weekly footprint overlap is insufficient

Rules: R17. Basis: conditional temporal reasoning, not an official checker.

Given:

- two_activities: incompatible protected footprints overlap
- week: 10

Expected under each interpretation:

- **explicit_same_night:** Conflict under full-night model
- **explicit_different_nights:** No simultaneous protection conflict from this pair
- **only_week_and_local_labels:** UNVERIFIED; retain a candidate intersection, not a confirmed breach

Organiser question: Q05. Official result: unknown.

<a id="e14"></a>

## E14 — Predecessor finishing week

Rules: R18. Basis: provisional strict-next-week ordering.

Given:

- predecessor: P
- successor: S
- P_full_workload_finish_week: 2

Expected under each interpretation:

- **selected_S_week_2:** FAIL
- **selected_S_week_3:** PASS dependency only
- **alternative_intraweek_model:** S in week 2 could pass if P finishes before S starts; missing timestamps prevent proving it
- **unknown_predecessor_or_cycle:** INPUT ERROR under selected policy

Organiser question: Q06. Official result: unknown.

<a id="e15"></a>

## E15 — Week boundaries and contract completion

Rules: R19, R21, R31. Basis: provisional calendar arithmetic.

Given:

- horizon_start: 2027-01-04
- weeks: 30
- two_activity_last_weeks: [1, 2]

Expected under each interpretation:

- **week_1_end:** 2027-01-10
- **week_30_end:** 2027-08-01
- **contract_finish:** 2027-01-17 under last-week-end convention
- **week_31:** Outside selected horizon; hypothetical week end 2027-08-08 is not permission to schedule there
- **non_Sunday_deadline:** May create partial-week lateness under selected convention; request official date convention

Organiser question: Q07. Official result: unknown.

<a id="e16"></a>

## E16 — No invented capacity

Rules: R20, R21. Basis: explicit development assumptions.

Given:

- capacity_at_L: 0
- location_M: absent
- request_week: 31
- horizon_weeks: 30

Expected under each interpretation:

- **L_one_group_in_A:** FAIL capacity
- **M:** INPUT ERROR, not capacity 0 or infinity
- **week_31:** FAIL selected horizon; an extended model requires confirmed supply and calendar rules

Organiser question: Q08. Official result: unknown.

<a id="e17"></a>

## E17 — Hard scenario limits override heuristic advice

Rules: R22, R23, R34. Basis: explicit scenario definitions preferred over inconsistent heuristic prose.

Given:

- case_A: One ECLO access
- case_B: Priority-3 contract finishes seven days after planned date

Expected under each interpretation:

- **A:** FAIL even if it reduces delay
- **B:** FAIL even if the delay would have a low penalty
- **no_feasible_result:** Report outcome honestly; do not convert either hard rule to a soft penalty

Organiser question: Q09. Official result: unknown.

<a id="e18"></a>

## E18 — C ECLO calendar span

Rules: R25. Basis: documented span check with stipulated affected lines.

Given:

- scenario: C
- affected_lines: explicitly provided for this isolated test; geometry is not inferred

Expected under each interpretation:

- **same_line_weeks_10_11:** PASS
- **same_line_weeks_10_12:** FAIL
- **same_line_week_10_only:** PASS
- **no_ECLO:** PASS window check
- **ALP_10_BET_12_without_cross_line:** PASS independent windows
- **add_cross_line_week_12:** FAIL ALP becomes {10,12}
- **scenario_B_weeks_10_12:** No C-window restriction

Organiser question: None currently required. Official result: unknown.

<a id="e19"></a>

## E19 — One shared possession, two ECLO activities

Rules: R26. Basis: provisional penalty-counting comparison.

Given:

- scenario: B
- activities: ["a", "b"]
- required_each: 1.5
- eclo_each: 1
- locations: ["L"]
- same_local_group: true
- excess: 0
- access_type_each: C

Expected under each interpretation:

- **selected_per_activity:** 2 ECLO accesses; penalty 10; 1.5 units credited to each
- **per_physical_possession:** 1 physical ECLO night; penalty 5 if that is the official accounting unit
- **official:** UNKNOWN

Organiser question: Q10. Official result: unknown.

<a id="e20"></a>

## E20 — Mixed ECLO flags in one group

Rules: R27. Basis: stricter provisional development choice.

Given:

- activities: ["a", "b"]
- same_local_group: true
- eclo_flags: [0, 1]

Expected under each interpretation:

- **selected_uniform_policy:** FAIL profile-specific rule, not a confirmed official violation
- **alternative_individual_duration_policy:** Could allow mixed flags with credits 1 and 1.5; must be confirmed

Organiser question: Q10. Official result: unknown.

<a id="e21"></a>

## E21 — Activity and contract delay are different

Rules: R28, R31. Basis: hand arithmetic under clearly separated candidate formulas.

Given:

- contract_priority: 3
- two_activities: [{"late_days": 7, "activity_priority": 1}, {"late_days": 14, "activity_priority": 3}]
- excess_units: 2
- eclo_activity_accesses: 3

Expected under each interpretation:

- **contract_late_days:** 14
- **raw_activity_late_days:** 21
- **selected_activity_weighted_delay:** 23.1
- **alternative_contract_weighted_delay:** 14
- **selected_C_score:** 52.1
- **alternative_C_score:** 43
- **B_component_score:** 29 but this late schedule is infeasible in B

Organiser question: Q09. Official result: unknown.

<a id="e22"></a>

## E22 — Reference sample score reconciliation

Rules: R28, R31. Basis: source counts plus conditional independent arithmetic.

Given:

- sample_scenario: A
- late_activities: [{"activity_id": "A035", "contract": "C006", "late_days": 7, "weighted": "9.1"}, {"activity_id": "A036", "contract": "C006", "late_days": 14, "weighted": "18.2"}, {"activity_id": "A038", "contract": "C006", "late_days": 7, "weighted": "7"}, {"activity_id": "A059", "contract": "C010", "late_days": 7, "weighted": "7"}, {"activity_id": "A075", "contract": "C014", "late_days": 7, "weighted": "7"}]
- calendar_assumption: R19
- planned_date_assumption: R31

Expected under each interpretation:

- **contract_days_from_RESULTS:** 28
- **activity_days:** 42
- **candidate_activity_weighted_score:** 48.3
- **candidate_contract_weighted_score:** 28
- **official_objective:** UNKNOWN; request validator JSON/formula version

Exact source records:

- [PS1/03_submission_sample/RESULTS.csv — record, line 2](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C001", "simulated_completion_date": "2027-06-13", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 3](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C002", "simulated_completion_date": "2027-07-04", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 4](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C003", "simulated_completion_date": "2027-07-04", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 5](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C004", "simulated_completion_date": "2027-07-18", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 6](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C005", "simulated_completion_date": "2027-03-21", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 7](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C006", "simulated_completion_date": "2027-07-18", "overrun_days": "14"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 8](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C007", "simulated_completion_date": "2027-07-04", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 9](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C008", "simulated_completion_date": "2027-07-18", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 10](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C009", "simulated_completion_date": "2027-06-27", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 11](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C010", "simulated_completion_date": "2027-05-23", "overrun_days": "7"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 12](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C011", "simulated_completion_date": "2027-07-11", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 13](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C012", "simulated_completion_date": "2027-07-04", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 14](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C013", "simulated_completion_date": "2027-05-30", "overrun_days": "0"}`
- [PS1/03_submission_sample/RESULTS.csv — record, line 15](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/RESULTS.csv): `{"scenario": "A", "contract_number": "C014", "simulated_completion_date": "2027-07-25", "overrun_days": "7"}`

Organiser question: Q09. Official result: unknown.

<a id="e23"></a>

## E23 — A scalar objective is not lexicographic priority

Rules: R29. Basis: mathematical counterexample to strict-priority prose.

Given:

- alternative_X: one P1 activity 7 days late, activity priority 3
- alternative_Y: one P2 activity 77 days late, activity priority 3
- other_penalties: 0
- scenario: A or C

Expected under each interpretation:

- **weighted_sum:** X=700, Y=770, so X wins
- **strict_priority_first:** Y wins because it avoids any P1 delay
- **selected:** weighted_sum provisionally; organiser confirmation required

Organiser question: Q09. Official result: unknown.

<a id="e24"></a>

## E24 — Export excludes derived protection in the sample

Rules: R04, R30. Basis: observed sample format, not complete protection proof.

Given:

- activity: A074
- week: 21
- sample_working_rows: [{"activity_id": "A074", "week": "21", "location_id": "PLAT:ALP:H01:EB", "co_share_group": "b1"}, {"activity_id": "A074", "week": "21", "location_id": "PLAT:ALP:H02:EB", "co_share_group": "b1"}, {"activity_id": "A074", "week": "21", "location_id": "SEC:ALP:H01_H02:EB", "co_share_group": "b1"}]

Expected under each interpretation:

- **selected_export:** Three ALP EB working-location rows only
- **internal_protection:** Keep opposite-bound/cross-line/buffer effects separately; actual expansion still unresolved
- **official_expander:** UNKNOWN

Exact source records:

- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 924](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A074", "week": "21", "location_id": "PLAT:ALP:H01:EB", "co_share_group": "b1"}`
- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 925](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A074", "week": "21", "location_id": "PLAT:ALP:H02:EB", "co_share_group": "b1"}`
- [PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv — record, line 926](../../data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): `{"activity_id": "A074", "week": "21", "location_id": "SEC:ALP:H01_H02:EB", "co_share_group": "b1"}`

Organiser question: Q03. Official result: unknown.

<a id="e25"></a>

## E25 — Do not fabricate Scenario C supply

Rules: R24, R32, R34. Basis: documented allowance plus provisional input applicability.

Given:

- C_nominal_supply: 1
- proposed_groups: 3

Expected under each interpretation:

- **provided_supply:** FAIL: excess 2 exceeds C allowance 1
- **invented_amended_supply_2:** Would pass capacity with excess 1, but that input change is unauthorised
- **selected:** Use provided supply, label scenario-input applicability provisional, request official C manifest

Organiser question: Q11. Official result: unknown.

<a id="e26"></a>

## E26 — Output sets and label renaming

Rules: R09, R33. Basis: documented output and label scope.

Given:

- scenarios: ["A", "B", "C"]
- group_rename: At one fixed location/week rename each distinct label bijectively

Expected under each interpretation:

- **output_files:** 3 CSVs per scenario, 9 total; do not mix scenario labels within RESULTS
- **renaming:** Local feasibility and score unchanged; never merge two labels or apply a numeric weekday meaning
- **hidden_instances:** Different IDs/counts are not a reason for rejection; supported schema/domain governs

Organiser question: None currently required. Official result: unknown.
