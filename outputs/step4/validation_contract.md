# Step 4 validation contract — version 0.1.1

The public entry point accepts the eight-CSV input directory, a directory with
one scenario's three output CSVs, and an explicit A/B/C scenario. Inputs are
imported afresh through the reviewed Step 3 importer and pinned Step 2 profile.
Uploaded or edited normalized JSON is not a trusted input format.

## File contract and error handling

Files are SCHEDULE_ACCESS.csv, SCHEDULE_OCCUPANCY.csv and RESULTS.csv, with the
brief's exact column sets. Column order may vary. The reader rejects malformed
UTF-8/CSV, duplicate headings, missing/extra columns and invalid numeric/date values.
Each parsed row retains its source filename and starting physical line.

Access sequence is a positive, unique identifier within an activity. This version
does not infer chronological ordering from access_seq or require contiguous
numbering. Week and local night index must be positive; ECLO must be 0/1.
Group labels are nonblank opaque text scoped to location/week, including internal
spaces. They are not interpreted as globally named possessions or weekdays.

Unknown activities, duplicate activity/week accesses, duplicate access sequences
and out-of-horizon accesses block downstream schedule calculations. Other
independent checks continue where their prerequisites remain valid. The report
is not guaranteed to list every downstream problem when an earlier prerequisite
fails.

RESULTS must contain one row for every imported contract, all in the requested
scenario. Unknown/duplicate contracts and scenario mismatches are violations.
Missing activities remain part of the required workload, even if every submitted
row otherwise looks consistent.

## Check coverage

| Rules | Implemented check / disposition |
|---|---|
| R01 | Sum exact scaled yields: standard 2, ECLO 3; required workload must be met for every activity |
| R02, R03, R21 | Independently compute release week; one activity access/week; supplied horizon only |
| R04, R30 | Traverse explicit input sector endpoints and compare all expected work locations to submitted occupancy |
| R05, R09 | Check legal PM/PC/C mix per local group; labels have only local scope |
| R06, R22–R24 | Count distinct local groups; sum excess across location-weeks; A allows zero excess, B penalises it, C allows at most one per location/week |
| R07, R08 | Check contract/type local index range, distinct index count and activity count per index |
| R18 | Successor starts strictly after predecessor's finishing week; incomplete predecessor is a violation |
| R19, R31 | Independently derive week-end completion; contract max activity completion; planned-date overrun; compare RESULTS |
| R22, R23 | A forbids ECLO; B forbids planned-date overrun |
| R25 | C working-line ECLO weeks fit max-min <= 1; empty/single-week sets allowed; Live affected-line completeness stays unverified |
| R26–R28 | Count ECLO per access, enforce provisional shared flags, compute the selected weighted arithmetic using integer tenths |
| R32 | Scenario C input applicability remains unverified |
| R33 | Output schema, identities and scenario selection |
| R12, R13, R15–R17 | Full protection checks remain UNVERIFIED, including dependencies on unresolved rules |
| R10 | Separate conditional physical-night diagnostic; does not alter weekly benchmark verdicts |

Other input requirements remain covered by Step 3 or are interpretation/reporting
policies, rather than additional implemented schedule predicates. Per-rule PASS
means the implemented check passes under this profile; it is not official
confirmation. NOT_APPLICABLE and NOT_EVALUATED are distinct from PASS.

If occupancy coverage fails, grouping, capacity totals and physical-night checks
cannot be established. No invented groups fill the gaps. Scores are withheld.
If an activity's workload is incomplete, its finish date remains null and complete
aggregate delay/score totals are withheld. Complete contracts may still have
their individual results checked.

When all workload and occupancy prerequisites hold, arithmetic can be reported
even if a different hard rule fails. It is explicitly ineligible as a validated
score; `score_eligible` is false. A/B/C arithmetic is respectively delay,
7*excess+5*ECLO, and delay+7*excess+5*ECLO. Delay uses the provisional activity
weights; contract delay metrics are separately labelled. No optimality is claimed.

## Conditional physical-night model

For each occupied week, one variable represents the entire activity access:

1. Members of one location/week/group require equal nights.
2. Activities sharing a contract/type/local index require equal nights.
3. Different local groups at one location require different nights.
4. Different indices within one contract/type require different nights; matching indices across contracts carry no relation.
5. Equal-night components cannot exceed contract/type workfront limits.
6. A Live activity's opposite-bound working core must be separated from other work occupying that core. This is only the known minimum mirror effect, not the complete buffered footprint.

Equality components are formed first. A component that also requires a pair to
be on different nights yields an explicit equality-path witness. Overfull
workfront components likewise carry witnesses. The remaining component graph
is coloured using up to seven abstract nights (or a user-selected lower diagnostic
limit). Different contract indices cannot accidentally collapse into a single
assigned night because their separation edges remain in the graph.

Greedy DSATUR is attempted first, followed by deterministic bounded backtracking
when needed. Search exhaustion returns UNKNOWN_SEARCH_LIMIT, never an
infeasibility claim. To bound recursion, a greedy failure with more than 400
components also returns UNKNOWN_SEARCH_LIMIT. These are prototype diagnostic
limits, not organiser runtime requirements. Search budgets count nodes, not wall
time. Constraint construction and file sizes are not yet bounded for hostile web
uploads; that belongs to the later hosted application.

Successful assignments are rechecked against generated equality, separation and
workfront constraints, exact component coverage and integer labels within the
selected night limit. These are explicit runtime checks, not removable Python
assertions. Failure produces INTERNAL_ERROR, publishes no assignment, and makes
the overall checker status VALIDATION_ERROR. It is not evidence against the schedule.

An exact search that exhausts all choices proves only
inconsistency within these declared assumptions and night limit. Conflict witnesses
are not guaranteed minimal. No assignment supplies calendar dates, an access
permit or proven full protection compatibility.

Night-limit contradictions include component membership, equality edges and
separation edges/reasons so the bounded graph can be replayed. This is evidence
supporting the computation, not a minimal unsatisfiable subset or an independently
certified proof trace. Empty access sets return NO_ACCESSES. Diagnostics report
the amount of submitted work examined, including unscheduled/incomplete activities;
an assignment for partial work does not establish that required work is scheduled.
Invalid diagnostic settings are rejected before import and schedule checking.

The unresolved buffer/interchange footprints are null. They do not generate
guessed separation edges. Their absence is recorded even when an assignment is
found. R16's broader exemption meaning and R17's weekly-versus-night semantics
remain unverified; the night model is explicitly conditional on simultaneous
full-night work and the chosen local-sharing interpretation.

## Report and provenance

Every ordinary finding carries a rule ID, code, severity, activities, location,
week, observed/expected values, explanation and source where applicable. Night
witnesses live under their week and carry the equality/separation relationships
needed to explain the conditional issue.
Input-stage failures and warnings also appear in the primary findings list with
their source file/line and `stage: input`. Their rule ID is null because the
importer's error is not automatically a scheduling-rule violation. Capacity
findings identify the activities contributing to the location/week demand.

The report binds actual input hashes, profile hash, schedule file hashes,
validator/diagnostic source hashes and night-search settings. The source sample
is never rewritten. Output publication reuses the importer's atomic JSON writer,
and additionally refuses output inside the schedule directory. A failed save
leaves the previous file unchanged and returns an error; callers must not treat
it as the latest result.

Overall status is INVALID_INPUT_OR_SCHEDULE for parse/import failures,
INVALID_UNDER_PROFILE for implemented schedule violations, or UNVERIFIED when
those checks pass but required rules are unresolved. The physical-night status
is separate. `full_feasibility_established` and operational authorisation remain
false. This checker is not the missing official validator or expander.
VALIDATION_ERROR identifies a failed internal assignment check. R10 uses
CONDITIONAL_ASSIGNMENT, CONDITIONAL_CONFLICT, UNKNOWN_SEARCH_LIMIT, NOT_APPLICABLE
or ERROR in the per-rule summary; these are not ordinary benchmark pass/fail results.
