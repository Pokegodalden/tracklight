# Step 6 — A/B/C optimisation implemented

Review update: see [critique and corrections](review.md) and [reviewed runs](reviewed-runs/summary.json)
for version 0.1.1 and the 128-test verification. The results and fingerprints in
`runs/` below remain historical version 0.1.0 evidence. Current preview: http://127.0.0.1:8768.

The local web app now optimises complete schedules for A, B and C using OR-Tools
CP-SAT. It retains the supplied sample and greedy baseline as separate runs,
validates generated decisions independently, and exports solver evidence beside
the three required CSVs. Step 7 alternatives/review tooling has not started.

**The solver's guarantees apply to an explicit weekly/core-night model. Full
protection, official score equivalence and official acceptance remain unverified.**
Unresolved rules were not marked as passed, and the pinned v0.2.0 rule pack was
not altered. The [model contract](model_contract.md) lists all extra assumptions.

## Measured results on the supplied instance

All three solutions cover all 54 activities, all 14 contracts and all 192 required
standard-equivalent work units. No implemented weekly violations or conditional
physical-night contradictions were found. Each export was re-imported and checked.

| Measure | A | B | C |
|---|---:|---:|---:|
| Provisional objective | 25.2 | 35.0 | 25.2 |
| Proven model lower bound | 25.2 | 35.0 | 25.2 |
| Model objective gap | 0% | 0% | 0% |
| Contract delay days | 21 | 0 | 21 |
| Activity delay days | 21 | 0 | 21 |
| ECLO activity accesses | 0 | 7 | 0 |
| Excess location/week slots | 0 | 0 | 0 |
| Scheduled accesses | 192 | 189 | 192 |
| Total local run time | 7.42 s | 10.93 s | 17.47 s |

These runs used a 30-second CP-SAT search limit, four workers and seed 0. Model
construction and independent checks are outside the search-time budget. Times
are observations from this machine, not promised performance on hidden instances.

Scenario B meets every planned completion date. Its seven ECLO accesses contribute
an extra 3.5 standard units, so 189 accesses deliver 192.5 units; the 0.5 excess
yield is permitted by the workload >= rule. Scenario C's optimum does not need
ECLO or extra capacity on this instance. Forced-resource tests separately exercise
those features and the C window constraints.

The Step 5 greedy baseline covered 163/192 units with seven unfinished activities
and had no valid full objective. The supplied sample covers all work with a
provisional score of 48.3 but has conditional night contradictions in 14 weeks.
The new A result improves that arithmetic score to 25.2 while satisfying the
modelled night relations. This is not a comparison against the unpublished
official reference solver. A/B/C objectives encode different policies and should
not be ranked as interchangeable choices solely by their numbers.

## Open and use

The current preview is at http://127.0.0.1:8767. To start it again from the project
directory on Windows:

```powershell
.\.venv\Scripts\python.exe -m ps1.webapp --port 8767
```

The project-local environment is already installed. On a fresh checkout with
Python 3.12, create `.venv` and install the root `requirements.txt` first.

1. Load the sample or import eight input CSVs, optionally with a schedule.
2. Select A, B or C in **Optimise a scenario**, then choose 10, 30 or 60 seconds.
3. Inspect the complete model result, objective components, lower bound, gap and
   assumptions. The original run remains in the selector.
4. **Export review pack** downloads the three CSVs, independent validation,
   provenance and `optimisation.json`. **Download solver report** also works when
   the run has no schedule, preserving timeout or model-infeasibility evidence.
5. Rerun a complete model-compatible solution with the same scenario to use it
   as an incumbent. If search ends without finding a new solution, it is retained.

The sample itself has conditional night contradictions, so it remains available
for inspection but cannot seed a model-compatible incumbent. Incomplete plans
are never silently substituted for a failed optimiser run. Every required
activity stays visible even when no complete solution is found.

This is still a single-user local server. One bounded solve runs synchronously;
other API requests wait. There is no cancellation/job queue or multi-user hosting
guarantee. Session runs disappear when the server stops; export important work.
The earlier Step 5 hosting assessment remains applicable.

## Outputs and reproduction

- [Run summary](runs/summary.json)
- [A review pack](runs/A/review-pack.zip), [A solver report](runs/A/optimisation.json), [A validation](runs/A/validation.json)
- [B review pack](runs/B/review-pack.zip), [B solver report](runs/B/optimisation.json), [B validation](runs/B/validation.json)
- [C review pack](runs/C/review-pack.zip), [C solver report](runs/C/optimisation.json), [C validation](runs/C/validation.json)

Each A/B/C directory also contains `RESULTS.csv`, `SCHEDULE_ACCESS.csv` and
`SCHEDULE_OCCUPANCY.csv` separately: nine CSVs total. These are review candidates,
not an officially accepted submission. Initial development runs are retained in
`initial-runs/`; `runs/` contains the final-code outputs.

To repeat the experiment, use a **new or empty directory** to avoid stale CSVs
being mistaken for a later timeout or failed attempt:

```powershell
.\.venv\Scripts\python.exe tools/step6_report.py --seconds 30 --workers 4 --output-dir outputs/step6/repeat-01
.\.venv\Scripts\python.exe tools/step6_report.py --inputs PATH_TO_EIGHT_CSVS --scenario A --seconds 60 --output-dir outputs/step6/another-instance
```

Inputs, rule/source revision, implementation fingerprints, solver version,
settings, timing, objective and bound are recorded. Dependencies are pinned at the
project root. Tied schedules and runtimes can vary, particularly with multiple
workers; a fixed seed does not promise identical multi-worker CSVs.

## Verification

**121 tests passed** in 13.977 seconds; see [test output](test-results.txt) and
[final-code/export fingerprints](verification.json).
The 15 new optimiser tests include hand-calculated sharing, ECLO, excess-cost,
precedence and workfront cases; C allowance and independent/coupled windows;
Live opposite-bound separation; release infeasibility; timeout/incumbent retention;
input immutability; and rejection of corrupt occupancy or a corrupt working span.

The original 15-file source pack and v0.2.0 specification verification also passed.
The optimiser uses importer spans; the checker reconstructs spans from topology
independently. Both raw solver output and the result after removal of redundant
accesses are checked, including reconciliation of the exact scaled objective.

Browser checks exercised the scenario selector, Scenario A/B solves and result panel.
Its visible result showed score 35.0, zero delay, seven ECLO accesses and zero gap.
The earlier UI's sample, baseline, import, activity list and conflict inspection
remain available. New solver results and exports continue to show protection as
unverified.

## Dependencies and remaining limits

Added OR-Tools 9.15.6755 in `.venv`; no new plugin, account, API credential or paid
service is required. Public hosting, official validation tooling and unresolved
protection semantics remain outstanding. The implementation is ready for the
requested Step 6 critique; it does not resolve those external dependencies.
