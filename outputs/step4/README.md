# Step 4 — schedule validation and physical-night diagnostic

Implemented 18 September 2026 under the unchanged provisional Step 2 profile.
Reviewed and revised to validator **0.1.1**; see [critique and corrections](review.md).
The supplied Scenario A sample passes the implemented weekly checks, but its
overall status remains **UNVERIFIED**. The separate diagnostic finds conditional
physical-night inconsistencies in **14 of its 29 occupied weeks**.

No solver, schedule repair or Step 5 interface has been built. The sample files
and frozen inputs remain unchanged.

## Outputs

- [Sample validation report](sample_validation.json): structured findings, per-rule results, independently calculated metrics and per-week night diagnostics.
- [Validation contract](validation_contract.md): implemented checks, status meanings, assumptions and limits.
- [Current verification log](review_verification.txt): full test suite, baseline and rule-pack integrity checks, and sample validation run.
- [Critique and corrections](review.md): reproduced gaps, fixes and retained limits.
- [Validator](../../ps1/validator.py) and [night diagnostic](../../ps1/night_diagnostic.py): local Python implementation with no additional dependencies.

## What the sample establishes

| Check or measurement | Result |
|---|---|
| Workload | All 54 activities complete; 192 standard-equivalent work units |
| Access / occupancy rows | 192 / 928; occupancy reconciles to independent span reconstruction |
| Implemented weekly violations | None |
| Contract completion and overrun | All 14 submitted result rows reconcile |
| Contract delay days | 28 |
| Activity delay days | 42 |
| Provisional activity-weighted delay / Scenario A arithmetic | 48.3 |
| Excess location-week units / ECLO accesses | 0 / 0 |
| Full protection / official acceptance | UNVERIFIED / not run |
| Conditional physical-night diagnostic | Inconsistencies in weeks 11–18, 20, 23–27 |

These are distinct conclusions. Passing the implemented weekly checks does not
make the sample dispatch-ready. The conditional night findings are not official
benchmark violations. The 48.3 arithmetic is neither an official score nor an
eligible validated submission score.

## Two concrete diagnostic witnesses

**Week 23, A001 and A011:** both use group b2 at PLAT:BET:S16:EB, which requires
the same abstract night under the full-night interpretation. They use different
groups at PLAT:BET:S15:EB, requiring different nights. The report records both
relations as the explanation of the contradiction.

**Week 25, A040 and A042:** sharing at PLAT:BET:S16:EB requires the same abstract
night, but contract C007 has one workfront. Their different local allocation
indices satisfy the local workfront check; the physical diagnostic sees two
simultaneous activities. This reproduces the earlier concern using an explicit
equality witness.

Witnesses are explanatory subsets, not claimed minimum conflict sets. Several
reported relations can describe the same underlying inconsistency.

## Implemented behaviour

The checker validates workload, release weeks, weekly uniqueness, allocations,
local workfronts, sharing, scenario capacity, ECLO settings/windows, predecessor
ordering and contract results. It calculates working occupancy from the inputs
and access placements, independently of both submitted occupancy and the
importer's cached span field.

Missing, extra or duplicate occupancy is a violation. Capacity, sharing and night
checks that require trustworthy occupancy then remain unevaluated; missing rows
cannot produce a clean capacity result. Incomplete workload has no completion
date and no complete aggregate delay/score. Submitted RESULTS cannot manufacture
completion.

The physical diagnostic uses equality constraints, separation constraints,
workfront limits and the known minimum Live opposite-bound working-core closure.
It assigns at most seven abstract nights per week when possible. Seven is a
calendar upper bound under the full-night assumption, not actual night availability.
Unresolved buffer geometry, Live interchange propagation and broader protection
semantics prevent an operational feasibility verdict even when an assignment exists.

Scenario C checks working-line ECLO windows independently. If Live ECLO is present,
the complete affected-line check remains unverified. Scenario C input applicability
also remains unconfirmed. The single supplied sample is checked as Scenario A;
B and C behaviour is exercised with synthetic cases, not fabricated sample answer keys.

## Verification

The complete suite has **88 passing tests**, including 29 validation/diagnostic
tests. Cases cover incomplete workload, two ECLO accesses yielding three work
units, illegal sharing, excess accounting, hard deadlines, predecessors,
missing/misleading output rows and line-specific ECLO windows. A combined Scenario
C example independently checks 9.1 delay + 21 excess + 5 ECLO = **35.1**.

The graph-colouring check is compared with an exhaustive two-colour oracle for
all 64 four-node graphs. Tests distinguish an eight-way separation contradiction
under a seven-night limit from an exhausted search budget. The known sample
witnesses and its 28/42/48.3 metrics are regression checks.
Additional review tests check assignment verification under optimised Python,
empty/partial diagnostic coverage, input-error visibility and night-limit witnesses.

## Run it

From the project root with Python 3.12:

```text
python -m ps1.validator data/baselines/ps1-0dfd901f97bf579f/PS1/01_data data/baselines/ps1-0dfd901f97bf579f/PS1/03_submission_sample --scenario A --output outputs/step4/sample_validation.json
python -m unittest discover -s tests -v
```

Python exits with **2** for a completed but unverified assessment, including the
sample; **1** means invalid inputs, implemented rule violations, a checker error, or a command/output
failure. No current path returns a successful full-validation code because the
required protection rules remain unresolved. Shell wrappers may present nonzero
codes differently; inspect the structured report for the exact result.

`--night-limit 1..7` selects a diagnostic what-if limit; default 7.
`--search-budget N` bounds exact search nodes per week; default 50000. These flags
do not change the weekly benchmark constraints or authorise extra access.

No plugin, API key, external service or solver package was needed. Step 4 is ready
for review within this explicitly partial validation scope; full official
equivalence remains dependent on organiser clarification and tooling.
