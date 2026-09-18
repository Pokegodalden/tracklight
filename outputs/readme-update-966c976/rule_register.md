# PS1 rule register

Version 0.2.0; baseline `ps1-0dfd901f97bf579f`. Published README commit `966c976` resolves predecessor semantics. No direct organiser reply or official tool result is available.

This is a specification, not implemented scheduling validation.

- **documented:** Explicit in the frozen source, not independently confirmed by organiser or official executable.
- **provisional:** Selected development interpretation, with alternatives/questions retained.
- **deferred:** No authoritative operational choice. Explicit policy returns UNVERIFIED and blocks a full-feasibility claim.

Deferred rules have an explicit UNVERIFIED handling policy; they are not resolved operational rules.

## R01 — Complete workload and yield

Status: **documented**. Planned enforcement: workload ledger / solver / checker.

All activities must reach at least their required workload. Standard=1 and ECLO=1.5 units; surplus caused by the final indivisible access is permitted by >=. No dropping work.

Sources: [PS1/PS1_README.md — 2.4 rule 1, line 85](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E01](examples.md#e01). Organiser question: None currently required. Published confirmation/version: none.

## R02 — Earliest start week

Status: **documented**. Planned enforcement: calendar adapter / solver / checker.

Do not schedule before the planned-start week. Date-to-week conversion follows provisional R19; no intraweek start time is asserted.

Sources: [PS1/PS1_README.md — 2.4 rule 2, line 86](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E06](examples.md#e06). Organiser question: None currently required. Published confirmation/version: none.

## R03 — One access per activity per week

Status: **documented**. Planned enforcement: solver / checker.

Apply at most one activity access per week in all scenarios. The sentence appears in the C explanation but describes the activity granularity without a scenario qualifier.

Sources: [PS1/PS1_README.md — 2.4 rule 9, line 93](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E05](examples.md#e05). Organiser question: None currently required. Published confirmation/version: none.

## R04 — Working-span expansion

Status: **provisional**. Planned enforcement: span expander / export checker.

For the supplied SEC endpoints, include every tunnel between them and all incident platforms on the same line/bound. Platform endpoints, reversed spans and disconnected/branching paths need explicit handling in Step 3; reject unsupported cases rather than invent a route.

Sources: [PS1/PS1_README.md — 2.2, line 56](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E09](examples.md#e09), [E24](examples.md#e24). Organiser question: Q03. Published confirmation/version: none.

## R05 — Legal sharing composition

Status: **documented**. Planned enforcement: group builder / checker.

Within one location/week/group: PM alone, one PC plus zero to three C, or one to four C. No PM+C, two PC, or fifth participant. Access type is independent of nature of works.

Sources: [PS1/PS1_README.md — 2.4 rule 4, line 88](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E02](examples.md#e02). Organiser question: None currently required. Published confirmation/version: none.

## R06 — Location capacity and excess accounting

Status: **documented**. Planned enforcement: capacity ledger / solver / checker.

Count distinct occupied groups per location/week, not activity rows. Excess is max(0, groups-supply), summed over location-weeks. A physical possession crossing three locations can therefore incur three excess units.

Sources: [PS1/PS1_README.md — 2.4 rule 5, line 89](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.7, line 195](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E03](examples.md#e03). Organiser question: None currently required. Published confirmation/version: none.

## R07 — Contract-local allocation indices

Status: **documented**. Planned enforcement: contract ledger / solver / checker.

Use the supplied cap for (contract_number,activity_type,week). Indices are integers 1..cap. Equal indices in different contracts do not establish a common night.

Sources: [PS1/PS1_README.md — 2.6, line 154](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.4 rule 6, line 90](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E04](examples.md#e04), [E08](examples.md#e08). Organiser question: None currently required. Published confirmation/version: none.

## R08 — Local workfront limit

Status: **documented**. Planned enforcement: resource ledger / solver / checker.

Count distinct activities per contract/type/week/access_night and enforce supplied workfronts. This check alone does not establish physical-night consistency (R10).

Sources: [PS1/PS1_README.md — 2.4 rule 7, line 91](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E04](examples.md#e04), [E08](examples.md#e08). Organiser question: None currently required. Published confirmation/version: none.

## R09 — Sharing-label scope

Status: **documented**. Planned enforcement: group model / checker.

Labels are scoped to location and week. Never treat b1 as a globally named weekday or possession. Consistent renaming within each location/week leaves local accounting unchanged.

Sources: [PS1/PS1_README.md — 2.4 rule 5, line 89](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.6, line 158](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E07](examples.md#e07), [E26](examples.md#e26). Organiser question: None currently required. Published confirmation/version: none.

## R10 — Common physical night

Status: **provisional**. Planned enforcement: model adapter / future night diagnostic / UI.

Use local weekly accounting for the provisional benchmark model. Separately diagnose one-full-night-per-access consistency. Do not impose an unconfirmed global-night constraint on the benchmark or call local success dispatch-ready.

Sources: [PS1/PS1_README.md — 1, line 20](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.4 rule 5, line 89](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E07](examples.md#e07), [E08](examples.md#e08). Organiser question: Q01. Published confirmation/version: none.

## R11 — Buffer class parameters

Status: **documented**. Planned enforcement: rule input adapter.

Read nature-of-works buffer counts from the supplied table: Live 2, Consist 1, Others 0; only Live requires opposite bound. These counts do not specify the whole expansion algorithm.

Sources: [PS1/01_data/05_BUFFER_LOCATION.csv — buffer table, line 1](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/05_BUFFER_LOCATION.csv).

Examples: [E09](examples.md#e09), [E10](examples.md#e10). Organiser question: None currently required. Published confirmation/version: none.

## R12 — Buffer geometry and terminal treatment

Status: **deferred**. Planned enforcement: protection expander / checker readiness.

No authoritative selection between tunnel-hop/platform-edge interpretations. Request exact affected-location sets, including terminals. Until configured, protection coverage is unverified, not passed; do not run an all-rules-feasible claim.

Sources: [PS1/PS1_README.md — 2.4 rule 3, line 87](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E09](examples.md#e09). Organiser question: Q03. Published confirmation/version: none.

## R13 — Live opposite-bound effect

Status: **documented**. Planned enforcement: protection expander.

A Live closure affects the opposite bound. Whether and how the expanded buffer mirrors remains unconfigured with R12. Non-Live does not acquire this effect.

Sources: [PS1/PS1_README.md — 2.4 rule 3, line 87](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E10](examples.md#e10). Organiser question: None currently required. Published confirmation/version: none.

## R14 — Independent interchange capacity

Status: **provisional**. Planned enforcement: network model / capacity ledger.

Prefer detailed section 2.2 and the supplied is_shared=0 rows over the opening shared-track narrative. ALP/BET tunnel and platform capacity remain separate; Live protection can couple them. Do not map fictional hubs to real stations.

Sources: [PS1/PS1_README.md — 2.2, line 58](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/01_data/03_SECTORS.csv — sector table, line 6](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/03_SECTORS.csv).

Examples: [E11](examples.md#e11). Organiser question: Q03. Published confirmation/version: none.

## R15 — Live interchange trigger and footprint

Status: **deferred**. Planned enforcement: protection expander / ECLO affected-line resolver.

Cross-line Live effects are required when applicable, but work-span versus buffer-contact triggering and exact propagation are unresolved. Require an explicit mapping before a complete protection check.

Sources: [PS1/PS1_README.md — 2.2, line 61](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E11](examples.md#e11). Organiser question: Q03. Published confirmation/version: none.

## R16 — Sharing exemption extent

Status: **provisional**. Planned enforcement: compatibility/protection checker.

Provisionally recognise exemption only for the same group at the same location/week. Do not propagate A-B and B-C into A-C automatically or exempt every PC/C pair everywhere. Broader exemptions need confirmation; dependent protection checks remain unverified with R12/R17.

Sources: [PS1/PS1_README.md — 2.1 item 5, line 41](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.4 rule 5, line 89](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E12](examples.md#e12). Organiser question: Q04. Published confirmation/version: none.

## R17 — Protection comparison time

Status: **deferred**. Planned enforcement: protection conflict evaluator.

Neither overlapping weekly footprints nor matching local labels alone proves simultaneity. Keep potential intersections as candidates. A definite temporal protection verdict requires a confirmed night relation or official weekly rule.

Sources: [PS1/PS1_README.md — 2.4 rule 3, line 87](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E13](examples.md#e13). Organiser question: Q05. Published confirmation/version: none.

## R18 — Predecessor ordering

Status: **documented**. Planned enforcement: dependency graph / solver / checker.

README section 2.4 rule 3 confirms strict later-week finish-to-start precedence, permits cross-contract links, and forbids cycles. Finished means the last scheduled predecessor access, including any additional scheduled accesses. Workload completeness remains a separate mandatory R01 gate. Unknown predecessor IDs remain rejected as referential input errors; the brief does not prescribe their error format.

Sources: [PS1/01_data/08_ACTIVITY_DETAILS.csv — activity schema, line 1](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/08_ACTIVITY_DETAILS.csv); [data/source_updates/966c976005db2e3e40a691cff268fdb8f396a5df/PS1_README.md — 2.4 rule 3, line 89](../../data/source_updates/966c976005db2e3e40a691cff268fdb8f396a5df/PS1_README.md).

Examples: [E14](examples.md#e14). Organiser question: None currently required. Published confirmation/version: 966c976005db2e3e40a691cff268fdb8f396a5df.

## R19 — Calendar conversion and completion date

Status: **provisional**. Planned enforcement: calendar adapter / metrics.

Use seven-day buckets anchored at horizon_start. Release week=floor((date-start)/7)+1. Completion=start+7*last_week-1 days; this matches all 14 sample results but does not prove hidden-date semantics. Out-of-horizon cases follow R21.

Sources: [PS1/01_data/06_PARAMETERS.csv — horizon parameters, line 2](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/06_PARAMETERS.csv); [PS1/PS1_README.md — 2.4 rule 2, line 86](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E06](examples.md#e06), [E15](examples.md#e15). Organiser question: Q07. Published confirmation/version: none.

## R20 — Static supply repeats within horizon

Status: **provisional**. Planned enforcement: supply adapter / capacity ledger.

Repeat each supplied location capacity in each in-horizon week. Zero is a real capacity; an absent location is an input error, not unlimited supply. Weekly overrides will be explicit future changes, not invented input columns.

Sources: [PS1/01_data/04_LOCATION_SUPPLY.csv — supply schema, line 1](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/04_LOCATION_SUPPLY.csv).

Examples: [E03](examples.md#e03), [E16](examples.md#e16). Organiser question: Q08. Published confirmation/version: none.

## R21 — Horizon extension

Status: **provisional**. Planned enforcement: calendar validation / solver domain.

Keep accesses in weeks 1..horizon_weeks until extension and its supply are authorised. Never invent extra weeks to hide infeasibility; report horizon-limited results as conditional.

Sources: [PS1/01_data/06_PARAMETERS.csv — horizon parameters, line 3](../../data/baselines/ps1-0dfd901f97bf579f/PS1/01_data/06_PARAMETERS.csv).

Examples: [E15](examples.md#e15), [E16](examples.md#e16). Organiser question: Q08. Published confirmation/version: none.

## R22 — Scenario A policy

Status: **documented**. Planned enforcement: scenario adapter / solver / checker.

No supply excess and no ECLO. Delay may occur; objective interpretation is R28. Never relax workload or protection to produce a result.

Sources: [PS1/PS1_README.md — 2.5 A, line 99](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E03](examples.md#e03), [E17](examples.md#e17). Organiser question: None currently required. Published confirmation/version: none.

## R23 — Scenario B policy

Status: **documented**. Planned enforcement: scenario adapter / solver / checker.

Planned completion is hard. Excess capacity is soft with no stated numeric ceiling. ECLO may occur in any week. Prose suggesting P3 slip in B conflicts with the explicit hard deadline; retain the hard deadline.

Sources: [PS1/PS1_README.md — 2.5 B, line 100](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E03](examples.md#e03), [E17](examples.md#e17). Organiser question: Q09. Published confirmation/version: none.

## R24 — Scenario C capacity policy

Status: **documented**. Planned enforcement: scenario adapter / solver / checker.

Allow at most one excess group per location/week above the supplied capacity, penalise every excess unit, permit delayed completion. Do not bake an additional supply increase into this allowance.

Sources: [PS1/PS1_README.md — 2.5 C, line 101](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E03](examples.md#e03), [E25](examples.md#e25). Organiser question: None currently required. Published confirmation/version: none.

## R25 — Scenario C ECLO span and affected lines

Status: **documented**. Planned enforcement: ECLO checker / solver.

For each affected line, ECLO weeks must fit in at most two adjacent week buckets. Empty/single-week sets are allowed. Different lines choose independently; cross-line Live accesses must fit both. Determining affected lines depends on unresolved R15.

Sources: [PS1/PS1_README.md — 2.4 rule 9, line 93](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E18](examples.md#e18). Organiser question: None currently required. Published confirmation/version: none.

## R26 — ECLO penalty unit

Status: **provisional**. Planned enforcement: score calculator.

Provisionally charge 5 per eclo=1 activity-access row. Also expose the count separately; do not deduplicate by local groups across locations and call that physical nights. The alternative physical-possession price remains open.

Sources: [PS1/PS1_README.md — 2.5 ECLO, line 107](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.7 detail, line 199](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E19](examples.md#e19). Organiser question: Q10. Published confirmation/version: none.

## R27 — Mixed ECLO flags within a shared group

Status: **provisional**. Planned enforcement: group builder / checker.

Until clarified, require equal ECLO flags within a local sharing group. This is an explicitly stricter development choice, not a proven official constraint. Do not infer an extra ECLO award for a member flagged standard.

Sources: [PS1/PS1_README.md — 2.4 rule 5, line 89](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E20](examples.md#e20). Organiser question: Q10. Published confirmation/version: none.

## R28 — Delay formula and metrics

Status: **provisional**. Planned enforcement: score calculator / comparison UI.

Primary development score uses per-activity weighted planned-date lateness (100/10/1)*(1.3/1.2/1.0)*days. Separately report contract-day lateness and its contract-weighted total. A=delay, B=7*excess+5*ECLO, C=delay+7*excess+5*ECLO. Numeric scores remain provisional; unknown protection prevents a full-feasibility claim.

Sources: [PS1/PS1_README.md — 2.5 formula, line 115](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.7, line 198](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E21](examples.md#e21), [E22](examples.md#e22). Organiser question: Q09. Published confirmation/version: none.

## R29 — Weighted priority versus strict precedence

Status: **provisional**. Planned enforcement: objective adapter / alternative ranking.

Minimise the scalar penalty; do not silently impose lexicographic contract priorities or a fixed ECLO-before-capacity heuristic. Aggregate weighted trade-offs can contradict prose saying never delay higher tiers. Compare alternatives under the chosen formula, not the prose's incomparable batch-cost ratios.

Sources: [PS1/PS1_README.md — 2.5, line 110](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.5 formula, line 125](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E23](examples.md#e23). Organiser question: Q09. Published confirmation/version: none.

## R30 — Occupancy export versus protection

Status: **provisional**. Planned enforcement: exporter / export checker.

Export work-span rows only as the sample does. Keep buffers/mirrors/cross-line effects in separate derived records; do not count them as extra submitted working rows without expander confirmation.

Sources: [PS1/PS1_README.md — 2.6, line 156](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E24](examples.md#e24). Organiser question: Q03. Published confirmation/version: none.

## R31 — Results aggregation and target date

Status: **provisional**. Planned enforcement: results exporter / metrics.

One result per scenario/contract; complete at the maximum finishing week across its activities/types, using R19. Overrun=max(0, completion-planned_completion_date); keep contractual dates separate. Multiple project rows with conflicting planned dates require clarification rather than an arbitrary first match.

Sources: [PS1/PS1_README.md — 2.6, line 159](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 2.3, line 72](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E15](examples.md#e15), [E21](examples.md#e21), [E22](examples.md#e22). Organiser question: Q07. Published confirmation/version: none.

## R32 — Scenario input identity

Status: **provisional**. Planned enforcement: run configuration / provenance.

Develop A/B/C against the same frozen eight CSVs until another manifest is supplied. Label C input applicability provisional. Never edit the baseline or fabricate the amended C capacities.

Sources: [PS1/PS1_README.md — 2.5 C, line 101](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E25](examples.md#e25). Organiser question: Q11. Published confirmation/version: none.

## R33 — Output contract and unsupported instances

Status: **documented**. Planned enforcement: import contract / exporter / hosted UI.

Three CSVs per scenario, exact documented columns. The eventual importer must accept supported unseen IDs/counts, not just the sample. Endpoint/category variations and solve-time limits still need organiser confirmation; reject unsupported structures clearly.

Sources: [PS1/PS1_README.md — 2.6, line 163](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 4, line 236](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E26](examples.md#e26). Organiser question: Q12. Published confirmation/version: none.

## R34 — No fabricated success under congestion

Status: **provisional**. Planned enforcement: run-status reporting.

Persist in searching permitted alternatives, but distinguish timeout from proven infeasibility under selected assumptions. The brief's request not to declare impossibility cannot authorise dropping work, exceeding hard scenario limits or claiming an unchecked feasible result.

Sources: [PS1/PS1_README.md — 1, line 26](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md); [PS1/PS1_README.md — 1, line 25](../../data/baselines/ps1-0dfd901f97bf579f/PS1/PS1_README.md).

Examples: [E17](examples.md#e17), [E25](examples.md#e25). Organiser question: Q12. Published confirmation/version: none.
