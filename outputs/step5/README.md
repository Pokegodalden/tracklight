# Step 5 — working import-to-export prototype

Historical implementation report. See [the Step 5 review](review.md) for the
current corrections; Step 6 optimisation has since been implemented and reviewed.

Implemented 18 September 2026. This delivers Step 5 of workflow.txt; Step 6
optimisation has not started. The Step 2 profile and frozen source pack are unchanged.

## Run and inspect

From the project root, run `python -m ps1.webapp --port 8765` with Python 3.12,
then open http://127.0.0.1:8765. No packages, API keys or external services are needed.

1. The supplied sample loads and is checked automatically.
2. Explore the weekly timeline by line, direction, location kind and week. A cell
   with several activities opens an activity selector in the inspector.
3. Open **Activities** to search all requests, including those with no allocation.
4. Open **Checks & conflicts**. Week 23 reproduces the same-night/different-night
   contradiction involving A001 and A011. Week 25 includes the C007 workfront issue.
5. **Create Scenario A baseline** produces a separate generated draft; use the run
   selector to return to the sample. Imported allocation reasoning is explicitly
   unknown; generated allocation reasoning describes the heuristic.
6. **Import CSV files** accepts the eight named inputs, optionally with all three
   schedule CSVs. A/B/C selects the supplied schedule's validation scenario;
   construction is currently Scenario A only. Input-only runs cannot export until
   a schedule is generated. Malformed imports leave the current run visible.
7. **Export review pack** re-imports the exact schedule bytes and compares its
   complete validation report to the displayed report before downloading a ZIP.

Each ZIP contains the three named schedule CSVs plus separate manifest,
validation, construction and explanation files. The sample's CSVs remain
byte-for-byte identical. Incomplete generated contracts receive no invented
completion dates; their missing RESULTS rows are explicitly reported as violations.

Runs use temporary local storage and disappear when the server stops. Reloading
the browser starts a fresh UI session and loads another sample run; it does not
restore the previous selector. Export important runs first. There is a 16-run
server-session limit. A review ZIP can be unpacked and its three CSVs re-imported
alongside the original eight inputs; the ZIP itself is not an upload format.

## Observed results

| Measure | Supplied sample | Scenario A baseline |
|---|---:|---:|
| Activities retained | 54 | 54 |
| Work allocated / required units | 192 / 192 | 163 / 192 |
| Activities with unfinished workload | 0 | 7 |
| Complete contract result rows | 14 | 10 |
| Implemented weekly violations | 0 | 11 |
| Conditional night-conflict weeks | 14 | 0 among placed accesses |
| Overall provisional status | UNVERIFIED | INVALID_UNDER_PROFILE |
| Officially validated / submission-ready | No | No |

The 11 baseline violations are seven incomplete workloads and four missing
contract-result rows. The remaining 29 units belong to A003, A004, A007, A036,
A055, A057 and A060. A004 waits on a predecessor that the heuristic never finishes;
the others are constrained by the capacity available in this particular greedy
ordering. These are recorded execution reasons, not proofs of infeasibility or
minimal causal explanations. Several unfinished activities receive no access.

The sample's provisional arithmetic score is 48.3, but it is not eligible for an
official-feasibility claim. The partial baseline has no full score. Fewer night
conflicts in a partial plan is not evidence that it is better than the sample.

## Baseline method and limits

The generator iterates weeks, then sorts requests by contract priority, target
date, activity priority and ID. It places at most one standard access per activity
per week after release and full predecessor completion in an earlier week.
It respects nominal weekly location supply and project-type access/workfront
limits, uses no ECLO, and gives each access its own co-share group.

For construction only, it tries seven abstract nights and separates overlapping
working cores and known Live opposite-bound mirrors. These abstract choices are
diagnostic metadata, not dated track permissions or the CSV's contract-local
access index. The seven-night assumption does not redefine the provisional rules.
The independent Step 4 checker evaluates every generated schedule.

This is a deterministic first-fit method with no sharing, backtracking or
optimisation. Its deliberate simplicity can waste scarce capacity and strand work.
Protection buffers, interchange expansion and disputed semantics stay unverified.
No complete-feasibility or optimality claim is made. Step 6 must address complete
workload and scenario objectives rather than treating this partial result as an
accepted incumbent.

## Verification and reproducibility

Run `python -m unittest discover -s tests -v` for the existing checks and 12 Step 5
tests. The Step 5 checks cover byte-identical sample export; deterministic generation;
parent preservation; partial and zero-capacity workloads; failed-import cleanup;
changed line/activity identifiers; report-drift rejection; malformed filenames and
base64; semantically invalid schedules; HTTP upload/generate/export; and local
request boundaries.

Run `python tools/step5_report.py` to regenerate [measured evidence](evidence.json),
[sample review pack](sample-review.zip) and [baseline review pack](baseline-review.zip).
This uses the same backend as the web app. Run IDs and ZIP timestamps can differ;
schedule contents and scheduling decisions are deterministic.

Browser verification exercised the sample conflict explanation, generation,
all-54 activity list, A003's unfinished-work inspector, review download, and the
actual eight-file chooser/import path. Backend tests additionally exercise renamed
input identifiers; this is a hidden-style compatibility check, not a guarantee for
every unseen instance. Browser layout was inspected at the app's current viewport.

## Tools and next review

Used local Python, JavaScript and the installed browser automation capability.
No new plugins, accounts or paid APIs are required for Step 5. See
[hosting.md](hosting.md) for deployment work still needed. A separate user-directed
critique can now assess the prototype before Step 6.
