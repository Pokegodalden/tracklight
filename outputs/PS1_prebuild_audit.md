# PS1 pre-build audit

Audit date: 17 September 2026. Scope: the eight supplied input CSVs, three sample output CSVs, the SVG topology reference, the Draw.io reference, and the PS1 README. No source files were edited. No project application or production solver was built.

## Decision

The data are sufficient to design the importer, network model, workload ledger, weekly planning interface, and independent accounting checks. They are not sufficient to certify equivalence with the judges' validator or to claim that the sample is a complete physical-night dispatch plan.

The most consequential unresolved issue is the relationship between local co-sharing groups, contract-local access-night indices, and a common physical night. There are concrete counterexamples in the sample, not merely missing documentation. Obtain the official validator/expander and clarify these examples before freezing the optimisation model.

## Evidence and limits

The audit parsed every supplied CSV row, checked keys and references, reconstructed work spans from sector topology, reconciled workload, checked local grouping and allocation limits, and independently recomputed all contract completion summaries. Core counts and the contract-overrun total were also cross-checked with PowerShell Import-Csv, separately from the Python audit.

The SVG was parsed, rendered, and visually inspected. Draw.io XML and all non-empty cell annotations were inspected. The Draw.io drawing was not rendered as a complete visual page.

The pack contains no executable official validator, expansion tool, official validator report, B/C sample, or scenario-specific alternate supply file. All claims below distinguish direct observations, conditional interpretations, and unverified official behaviour.

## 1. Actual instance

| Item | Observed value |
|---|---:|
| Input CSVs | 8 |
| Lines | 2: ALP and BET |
| Station-line memberships | 20 |
| Distinct station identifiers | 18; H01 and H02 belong to both lines |
| Undirected line sectors | 18; 9 per line |
| Bookable locations | 76: 36 directional tunnel sectors and 40 directional platforms |
| Contracts | 14 |
| Activities | 54 |
| Required workload | 192 standard-access-equivalent units |
| Predecessor links | 6 |
| Horizon | 30 weeks, 4 January–1 August 2027 |
| Sample scenario | A only |
| Sample activity-access rows | 192, all standard accesses |
| Sample occupancy rows | 928 |
| Occupied location-week groups | 751 |
| Groups containing multiple activities | 129 |

There are 31 Non-live (Consist), 21 Non-live (Others), and 2 Live activities. Access types comprise 43 C, 10 PC, and 1 PM activity. These are two independent classifications.

### Schema and joins

| File | Records | Key and interpretation |
|---|---:|---|
| 01_LINES.csv | 2 | line_code |
| 02_STATIONS.csv | 20 | (line_code, station_id); station_id alone is not unique |
| 03_SECTORS.csv | 18 | sector_id; derive adjacency within each line |
| 04_LOCATION_SUPPLY.csv | 76 | location_id; fixed supply_capacity, with no week column |
| 05_BUFFER_LOCATION.csv | 3 | nature_of_works maps to buffer count and opposite-bound flag |
| 06_PARAMETERS.csv | 2 | horizon_start and horizon_weeks only |
| 07_PROJECT_DETAILS.csv | 14 | use (contract_number, activity_type) for joins consistent with the brief; contract_number happens to be unique here |
| 08_ACTIVITY_DETAILS.csv | 54 | activity_id; includes predecessor_activity_id |

Important implementation details:

- `activity_type` means Renewal or Construction. It does not mean PM/PC/C or Live/Non-live.
- Project `nature_of_activity` joins to buffer-table `nature_of_works`; the column names differ.
- Sector `seq` is numbered 1–18 across the two lines, whereas station `seq` is 1–10 within each line. Sort/filter within a line; never infer an ALP-to-BET connection from consecutive sector sequence numbers.
- Activity identifiers contain gaps. There are 54 activities, not 75; missing numeric suffixes are not missing records.
- Every activity endpoint in this instance is a SEC location. Platform endpoints, reversed paths, and multi-type contracts are not exercised by this sample.
- All sectors have is_shared=0. The CSV and SVG support separate H01–H02 tunnel capacity on each line.
- There is no dated maintenance calendar, individual roster, equipment inventory, named weekday, or clock-time field.
- Only two parameters are supplied. Scoring coefficients and detailed calendar/protection semantics cannot be recovered from 06_PARAMETERS.csv.

## 2. Supply and likely bottlenecks

Supply is a static template: 24 locations have capacity 4, 40 have capacity 2, and 12 have capacity 1. Interpreting the same value in every week is consistent with the supplied sample and brief, but the CSV does not contain week-specific overrides.

The 12 capacity-1 locations are the four directional H01–H02 tunnels and eight directional interchange platforms. Adjacent tunnels have capacity 2; outer tunnels have capacity 4; ordinary platforms have capacity 2.

This means a tunnel with apparent spare capacity may still be constrained by a platform on the work span. Do not equate supply_capacity with the separate within-group limit of four compatible activities.

| Location | Capacity | Weeks at nominal capacity in sample | Activity-occupancy rows |
|---|---:|---:|---:|
| PLAT:BET:H01:EB | 1 | 24 of 30 | 43 |
| PLAT:BET:H02:EB | 1 | 22 of 30 | 48 |
| SEC:BET:H01_H02:EB | 1 | 21 of 30 | 36 |
| PLAT:ALP:H01:WB | 1 | 21 of 30 | 21 |

These are observed saturation counts, not proof that adding capacity at those locations would improve the optimum. Release dates, contract caps, other locations, and protection rules may remain binding. The Beta eastbound interchange is nevertheless a useful initial inspection view.

## 3. Sample accounting checks

The audit's direct accounting checks found no failures in:

- Primary/composite keys and checked foreign-key references.
- Required cells, activity/project type matching, and access field domains.
- Exactly 192 delivered units against 192 required units, with exact completion for each of the 54 activities.
- One access per activity/week and sequential access_seq values.
- Planned-start-week limits and the 30-week horizon.
- Scenario A's prohibition of ECLO.
- Complete work-span occupancy and absence of orphan occupancy rows.
- Distinct weekly access-night caps and local workfront counts.
- Legal PM/PC/C composition within each location/week/group.
- Number of distinct groups within nominal location capacity.
- Recalculated contract completion dates and overrun values.

All six predecessor links are also consistent with a strict finish-before-next-week-start interpretation. That is a conditional check: the README does not fully specify predecessor enforcement.

There are 26 direct check categories and one conditional predecessor check. This is not an official feasibility result and does not cover all protection semantics.

### Occupancy format

Reconstructing each activity's contiguous tunnel span and all associated platforms reproduces all 928 occupancy rows exactly. The sample records the actual work span only, not the expanded buffer or mirrored closure footprint.

For example, A074 has just three occupancy rows in Week 21: ALP H01 platform EB, ALP H02 platform EB, and ALP H01–H02 tunnel EB. The sample does not write its opposite-bound or Beta closures as additional occupancy rows.

Design separate representations for work occupancy and derived protection effects. Do not add derived closures to exported occupancy without checking the official expander.

### Local groups

There are 751 occupied location-week groups for 928 activity-location rows: 177 fewer groups than the naive one-row-one-group count. This is not a reduction of 177 whole-network physical nights. An activity covers multiple locations.

Group membership is location-specific. In 169 of 192 activity-week allocations, the activity has different group labels at different locations. A001 in Week 22 is b2 on platforms and b4 on its tunnels. Labels must therefore be treated as arbitrary within their documented scope.

In 73 shared location-week groups, members have different contract-local access_night values. This is expected to be possible across different contracts because the indices are explicitly local; it is not by itself an error.

## 4. Completion and score reconciliation

All 14 RESULTS.csv completion dates match the Sunday ending the contract's last scheduled week:

`completion = horizon_start + (7 * last_week - 1) days`

The sample has three contracts late against planned_completion_date:

| Contract | Planned | Sample completion | Overrun |
|---|---|---|---:|
| C006 | 4 July 2027 | 18 July 2027 | 14 days |
| C010 | 16 May 2027 | 23 May 2027 | 7 days |
| C014 | 18 July 2027 | 25 July 2027 | 7 days |
| Total | | | 28 contract-days |

All three are contract Priority 3. No contract is late against its later contractual completion date. The planned and contractual dates must remain distinct.

Under the README's per-activity weighted interpretation, five activities are late:

| Activity | Contract | Days late | Weighted contribution |
|---|---|---:|---:|
| A035 | C006 | 7 | 9.1 |
| A036 | C006 | 14 | 18.2 |
| A038 | C006 | 7 | 7.0 |
| A059 | C010 | 7 | 7.0 |
| A075 | C014 | 7 | 7.0 |
| Total | | 42 activity-days | 48.3 |

Thus 28 contract-days, 42 activity-days, and 48.3 weighted penalty units describe different quantities. 48.3 is an independently reconstructed candidate score, not an official validator output. The supplied sample has no objective_score or formula_version report.

## 5. Delay that cannot be removed by extra local capacity alone

Assume the README's at-most-one-access-per-activity-per-week rule, standard yield 1, ECLO yield 1.5, Sunday completion, and per-activity scoring. Relax all spatial, resource, grouping, and predecessor restrictions to obtain lower bounds.

- A036 needs 7 units, is released in Week 22, and has a planned deadline at the end of Week 26. Scenario A requires seven standard weeks, so Week 28 and 14 days' overrun are the earliest possible. Scenario B needs at least four ECLO accesses in its five available weeks. Scenario C permits at most two ECLO accesses for this activity, so it needs at least six weeks and cannot eliminate all delay.
- A059 needs 7 units from Week 14, with a deadline at the end of Week 19. Scenario A cannot finish before Week 20, seven days late. Scenario B needs at least two ECLO accesses within the six available weeks.

Derived bounds:

- Scenario A has at least 21 contract-days of delay from these two distinct contracts, and at least 25.2 activity-weighted penalty units.
- Scenario B requires at least six ECLO activity-accesses in total, hence at least 30 ECLO penalty units if the penalty is charged per activity-access. This does not prove B feasible or determine required excess capacity.
- Scenario C cannot be completely on time under these rules because of A036. Its delay-only lower bound is 9.1. Including the individual ECLO costs yields a relaxed combined lower bound of 25.2.

Why C's combined bound is higher than its delay-only bound: for A036, two ECLO accesses reduce weighted delay from 18.2 to 9.1 but add 10 ECLO penalty units, producing 19.1. For A059, two ECLO accesses replace a delay penalty of 7 with an ECLO cost of 10. Considered individually, accepting those Priority-3 delays is cheaper. Other network effects can still justify ECLO in the full problem.

The sample's reconstructed 48.3 versus the relaxed 25.2 bound is not proof that the 23.1 difference can be eliminated. No optimal schedule has been solved or certified.

## 6. Physical-night consistency: the highest-priority clarification

The following are conditional contradictions if one activity access occupies its whole span on one common physical night, shared groups denote the same night, and different groups at the same location denote different nights, as the README describes.

### Example A: sharing changes along identical work spans

At Week 23:

| Location | A001 | A011 |
|---|---|---|
| PLAT:BET:S15:EB | b2 | b1 |
| PLAT:BET:S16:EB | b2 | b2 |

Both activities cover BET S15–S17 EB. They share at S16 but are assigned different groups at S15. A shared night at one location and different nights at another cannot describe one simultaneous through-span access for each activity.

Evidence: SCHEDULE_OCCUPANCY.csv lines 7, 8, 143, and 144, including the header in line numbering.

### Example B: the same contractor and workfront

In Week 25, A040 and A042 belong to C007, whose number_of_workfronts is 1. Their access_night values are 3 and 1, respectively. However, they share group b4 at SEC:BET:S15_S16:EB. The local workfront count passes because the indices differ, while literal simultaneous co-sharing would put two activities of that same one-workfront contractor together.

Evidence: SCHEDULE_OCCUPANCY.csv lines 531 and 556, the Week-25 access rows for A040/A042, and the C007 project row.

A diagnostic that joins activities connected by shared groups finds 49 location-week/component inconsistencies and three component/contract cases with multiple local night indices. These are diagnostic counts under the stated physical-night interpretation, not official rule-violation counts or 49 independent unsafe events.

The organiser may intend a purely local weekly packing abstraction. If so, the application should explicitly distinguish its allocation plan from a physically dispatchable nightly plan. If a common-night plan is intended, the schema, sample, or validation may need clarification or correction.

## 7. Protection semantics remain unverified

The buffer table gives two sectors for Live, one for Non-live (Consist), and zero for Non-live (Others). It does not specify every detail of platform inclusion, terminal truncation, mirrored-buffer extent, exemption aggregation, or calendar-night comparison.

Draw.io annotations support independent interchange allocations for non-live work, a cross-line effect for Live work, and a crossover that does not extend beyond the interchange. They remain illustrative, rather than an executable rule definition.

A deliberately conservative whole-week footprint interpretation produces 33 span/closure candidate pairs and 43 protected-footprint candidate pairs after a simple shared-location exemption. It is not adopted as the authoritative checker: work on different physical nights can legitimately coexist in one week, and group exemptions may have wider semantics.

For instance, A074's inferred Week-21 footprint intersects A004's work. They share a group on ALP H01 EB, so declaring a violation from the intersection alone would ignore the co-sharing rule. This demonstrates why a naive geographic conflict checker would produce false positives.

Do not publish these sensitivity counts as defects in the organisers' sample. They identify exactly where an official rule implementation is necessary.

## 8. Critique of the earlier recommendations

1. The earlier proposal described week-varying supply too readily. The actual file supplies a static per-location value. Weekly disruption overrides are an application extension, not an existing column.
2. The predecessor field is an important addition to the model. It was missing from the earlier core discussion because the README omitted its detailed semantics. Six valid links exist and are respected by this sample.
3. Reproducing sample CSV accounting is not enough to reproduce official feasibility. The earlier plan should make this distinction explicit.
4. A nightly dispatch interface was premature. The data establish weeks, local group labels, and local contractor indices, but the examples above prevent assuming a common calendar-night assignment.
5. Group formation cannot automatically be treated as one global set of possessions. The sample packs groups independently by location. Imposing a stronger global interpretation may reject the reference even while better matching physical operations.
6. The scenario objective should not be replaced by a strict priority-first policy. Weighted penalties permit aggregate trade-offs, and the sample's completion metrics have distinct activity and contract aggregation levels.
7. A zero-delay A or C target would be wrong for this instance under the one-access-per-week rule. Some overrun comes from release dates and workload, even before contention.
8. The 54-activity instance is small enough for a first exact optimisation experiment, but this is not a runtime guarantee for hidden instances. No solver performance has been measured in this audit.
9. The pack barely exercises Live work, has one PM activity, and contains no ECLO. It cannot validate B/C, continuity windows, complicated predecessor chains, mixed-type contracts, or every protection corner case.
10. Asset-condition modelling, crew rostering, spare parts, public APIs, and engineering-train logistics remain optional extensions. They do not resolve the current core specification risks.

## 9. Recommended build boundary

Proceed with a layered design:

- Import and preserve the eight input tables, their original identifiers, and source versions.
- Build canonical topology using line-scoped station keys and directional location keys.
- Separate work spans, derived protection effects, location sharing, and contractor-night accounting.
- Keep date conversion, predecessor semantics, co-sharing exemption rules, and scoring behind explicit versioned policies.
- Keep the official validator interface separate from an independent diagnostic checker.
- Show required/delivered workload, weekly allocation, local capacity, and score components in the UI.
- Label common-night dispatch and authorisation as unestablished until the mapping is resolved.

Before accepting the first solver implementation, require: full workload delivery, exact schema exports, official sample reproduction, A/B/C validation, negative test cases, and a comparison against the correct objective. The negative cases should exercise missing work, over-capacity groups, illegal mixes, workfront breaches, premature starts, predecessor violations, mirrored/cross-line closures, ECLO in A, and non-contiguous ECLO in C.

Do not hard-code the current IDs or optimise only for the supplied sample. Do not silently fill missing supply with an invented capacity, infer physical weekdays from access_night, or add a new global-night constraint to the judged model without confirming that it belongs there.

## 10. What this audit does not establish

No official feasibility verdict, official objective score, optimality proof, solver benchmark, actual-night lift, or B/C solution has been produced. Sources were not modified. Conditional diagnostics have not been disguised as confirmed failures. The audit establishes the data contract, reproducible accounting facts, useful lower bounds, and concrete questions needed to avoid building the wrong scheduler.
