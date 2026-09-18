# Step 6 model contract — weekly-core-nights-0.1.0

Active source rules: `ps1-provisional-0.2.0`, README commit `966c976`. Optimiser
version: `ps1-cpsat-0.1.1`. The frozen source and rule profile are preserved.

## Variables and enforced decisions

For each activity, released week and abstract night 1..7, a Boolean chooses an
access. At most one is selected per activity/week. An ECLO flag can be true only
for a selected access. Standard and ECLO accesses yield exactly 2 and 3 scaled
units respectively; every activity must meet its full required scaled workload.

The last selected week determines activity completion. Successors must start in
a strictly later week, including across contracts. Each contract/type has its
supplied cap on distinct nights and concurrent activities per night. Exported
`access_night` values are locally renumbered indices, not calendar weekdays.

At a working location/night, all present activities form one local group. Its
composition is PM alone, at most one PC with up to three C, or up to four C.
ECLO flags agree inside each group. Used local nights count toward weekly supply.
Known Live opposite-bound working cores cannot overlap other work on that night.

The CSV group label `n1` is still scoped to location/week. Labels may recur at
unrelated locations; they do not independently create a global sharing identity.
Abstract-night assignments are separate solver metadata, not track permissions.

## Explicit scenarios and objective

| Configuration | A | B | C |
|---|---|---|---|
| Weekly supply | Nominal hard cap | Extra slots allowed | Nominal + at most one |
| ECLO | Forbidden | Allowed | Allowed in line windows |
| Planned completion | Penalised delay | Hard deadline | Penalised delay |
| Objective | Weighted activity delay | 7 × excess + 5 × ECLO | Weighted activity delay + 7 × excess + 5 × ECLO |

Activity delay uses the provisional contract weights 100/10/1 and activity
multipliers 1.3/1.2/1.0. Completion is the last day of the final week; B therefore
cannot use a week whose ending date exceeds its planned date. Excess is counted
per location/week; ECLO is counted per activity access. Internally all objective
values are integer tenths. Neither the disputed alternative score nor a
lexicographic priority rule is silently substituted.

## Additional model assumptions and unresolved rules

Seven common full-night labels impose consistent night assignments across working
spans. This is stronger than the local-only weekly accounting interpretation and
does not identify which dated nights are actually available. In particular B's
model has at most seven nights even when its benchmark excess allowance has no
explicit upper bound. Bounds and infeasibility claims refer to this model only.

Each line's C window is chosen independently and covers at most two adjacent
weeks of actual ECLO use. Because the complete affected-line map for Live work
is still unknown, **every Live ECLO access must fit every input line's window**.
This conservative intersection covers any cross-line effect but can exclude
solutions that a clarified, narrower affected-line rule would permit. Non-Live
ECLO affects its own line only. A separate check reconstructs these line-week sets
from exported decisions. It does not claim to determine real electrical isolation.

Full buffer geometry, interchange propagation, sharing/protection exemptions and
temporal protection rules remain unverified. No invented buffer algorithm is
enforced as an official rule. Working-span CSV occupancy remains separate from
unresolved protection footprints. Scenario C also lacks an authoritative amended
input manifest. Thus model solutions are not fully feasible PS1/operational plans.

The model is neither an exact implementation nor a simple relaxation of the full
unknown rules: some model restrictions are stronger and some protection constraints
are missing. Its lower bound must not be presented as a bound on the full PS1 optimum.

## Outcomes, incumbent and export guarantees

| Outcome | Meaning |
|---|---|
| OPTIMAL_MODEL_UNVERIFIED | Solver proved the objective optimal for this model; full protection remains unknown. |
| FEASIBLE_MODEL_UNVERIFIED | A complete independently checked model solution exists; optimality is unproved. |
| RETAINED_INCUMBENT_UNVERIFIED | Search found no new solution before its limit; a complete checked model-compatible incumbent was retained. |
| INFEASIBLE_MODEL | A necessary-condition precheck failed, or CP-SAT proved this model infeasible. Not an official/full-problem infeasibility claim. |
| NO_SOLUTION_WITHIN_LIMIT | No solution and no infeasibility proof were obtained. No partial CSV schedule is fabricated. |

The parent run remains separate. Same-scenario incumbent acceptance requires full
workload, no implemented violations, a verified conditional night assignment and
the conservative C window check when applicable. Accepted incumbents supply hints,
an objective upper bound, and a fallback on timeout. A contradiction between an
accepted incumbent and a solver infeasibility result is treated as an internal error.

Feasible outputs are independently checked before publication; mismatched scores
or invalid decisions are withheld. Redundant accesses with no required workload
contribution are removed, and the reduced schedule is checked again. This can
improve a non-optimal incumbent's objective but cannot increase it. If a claimed
optimal result improved during this reduction, the implementation would reject
the contradiction. Bounds remain in primary objective tenths.

Every review ZIP is re-imported through the public validator; its report and
profile evidence and input identity must match the displayed run. Implementation
fingerprints are pinned at session/run creation; source changes stop further
scheduling and export until restart and re-import. Solver CSV publication also
requires a successful conditional night diagnostic before the new run is stored.
Contradictory bounds are rejected; retained incumbents carry their night witness.
Each CLI experiment uses an empty
output directory so a later failed run cannot leave previous successful CSVs
masquerading as its own output. Search settings and model assumptions accompany
successful and unsuccessful outcomes alike.

## Local resource boundaries

Existing upload limits still apply: 250 activities, 500 locations, 104 weeks,
1,500 access rows, 20,000 occupancy rows and 16 successful runs per session.
The optimiser additionally limits model construction to 60,000 activity/week/night
choices and 300,000 location/choice memberships. Rejection preserves the parent.
The web search limit is 1..60 seconds; the CLI supports up to 300 seconds and 1..8
workers. These limits are prototype choices, not organiser-provided limits.

Model building, validation and export add time outside the CP-SAT search budget.
There is no process-level hard wall-clock or memory quota in this local version.
A public deployment still needs bounded background jobs, cancellation, isolated
run ownership and measured hidden-instance resource limits.

Implementation references: [Google CP-SAT status documentation](https://developers.google.com/optimization/cp/cp_solver)
and [official OR-Tools package](https://pypi.org/project/ortools/).
