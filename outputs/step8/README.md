# Step 8 — controlled replanning

Implemented 19 September 2026. This completes Step 8 only; subsequent critique
and later workflow steps remain for the user. The preview is available at
http://127.0.0.1:8770/ under **Controlled replanning**.

## Implemented behaviour

| Request | Representation and behaviour |
| --- | --- |
| Longer remaining workload | Add positive half-unit increments to an existing activity's total requirement. Delivered work in completed weeks remains credited and frozen; only remaining work is rescheduled. Already completed activities require a separate follow-up activity. |
| Weekly supply change | Replace nominal capacity at one location/week using an explicit, versioned planning overlay. Unlisted weeks retain the input CSV capacity. B retains paid excess and C retains its +1 allowance; zero nominal capacity does not mean a complete operational closure. |
| Urgent activity | Add a new complete activity record under an existing contract/activity type, with its own release date, priority, span, workload and predecessor. The UI offers a template and editable fields. Existing project resources, dates and strict predecessor rules still apply. |
| Locked allocations | Freeze selected activities' complete weekly allocations, ECLO and sharing relationships. Sharing partners may consequently need to retain an allocation too. Raw group names and local night indices can change because they are not physical dates. |
| Completed work | Freeze all allocations and absences through a planner-declared week, including occupancy and sharing. No activity can be inserted into that history. The declaration assumes those weeks were delivered as scheduled. |

Each request produces a separate run. Changed activity inputs are saved as new
CSV bytes; original inputs and schedules remain unchanged. The cumulative
planning context is included in the exact schedule version, so reviews cannot
silently carry across a disruption. Subsequent revisions inherit weekly supply,
the completed-week cutoff and explicit locks. Completed time cannot move
backwards and inherited locks cannot be removed silently.

The solver minimises the provisional scenario objective first, then the number
of activities whose allocations change. The integer objective is
`scenario_score_tenths * (number_of_activities + 1) + changed_activity_count`.
The second term cannot outweigh even one unit of the first. Changed activity
count includes weeks, ECLO and semantic sharing relationships, not arbitrary
label renaming. Both objectives are claimed optimal only when the combined
model is proven optimal. Time-limited candidates retain explicit bound/status
information; a timeout is not an infeasibility finding.

Complete candidates pass the existing whole-schedule checks, conditional night
assignment, applicable conservative C policy, objective reconciliation and a new
independent completed-work/lock audit over exported decisions. The optimiser's
changed-activity count is also reconciled with the independent comparison. No
local-only validation shortcut is used. Post-solve access pruning is disabled
for revisions because it could alter a frozen decision or worsen churn.

If a locked proposal is proven infeasible, a separate bounded diagnostic may
test it without explicit locks while keeping completed work frozen. A successful
counterfactual identifies the lock set collectively as blocking; it does not
claim a minimal conflict set, release actual locks or publish the diagnostic
schedule. Return to the preserved parent and submit a different proposal to
reconsider newly introduced locks. To reconsider an inherited lock, return to
the version before it was introduced.

**Return to original version** selects the exact preserved parent and leaves the
revision available. The parent's old requirements still apply: rollback does
not resolve the disruption. Ordinary baseline/alternative/scenario generation
is blocked on disruption versions to prevent bypassing their context.

## Demonstration

Final evidence: [review-demo/summary.json](review-demo/summary.json),
[comparison](review-demo/comparison.json), [proposal](review-demo/proposal.json),
and the parent/revised review packs in that folder. The earlier `demo/` folder
is intermediate evidence; use `review-demo/` for the final source fingerprints.

The starting point is the saved Step 7 Scenario A solution, revalidated with the
current code. The reproducible disruption adds **one unit to A001**, declares
**weeks 1–10 completed**, and **locks A002**.

| Measure | Parent | Revision |
| --- | ---: | ---: |
| Activities completed | 54 / 54 | 54 / 54 |
| Required workload covered / required | 192 / 192 | 193 / 193 |
| Implemented weekly violations | 0 | 0 |
| Conditional conflict weeks | 0 | 0 |
| Provisional Scenario A score | 25.2 | 25.2 |
| ECLO accesses / excess slots | 0 / 0 | 0 / 0 |
| Final completion | 18 July 2027 | 18 July 2027 |

Four activities change. The completed-work and A002 lock audit passes, and the
solver proves the primary objective and the four-activity minimum for this
model. This run took about 11.85 seconds including construction and verification.
The parent bytes are unchanged; selecting the parent again and retaining the
revision was verified. Exported reports reproduce through independent validation.

The comparison labels changed requirements and planning constraints explicitly.
It shows component consequences and suppresses an aggregate score-improvement
claim: these runs are not the same input problem.

## Validation and use

**159 tests pass**, including 16 controlled-replanning tests covering all four
change types, A/B/C supply allowances, score-before-churn ordering, completed
history, sharing locks, impossible locks, inherited context, timeouts, stale
versions, invalid proposals, exports, HTTP session protection and rollback.
JavaScript syntax, the 15-file frozen snapshot and the v0.2.0 rule pack pass.
See [test-results.txt](test-results.txt) and [verification.json](verification.json).

Start a local server from the repository root:

```powershell
.\.venv\Scripts\python.exe -m ps1.webapp --port 8770
```

1. Optimise or import a complete checked model plan. The supplied sample needs
   repair before controlled replanning is enabled.
2. Open **Controlled replanning**, declare completed weeks and activity locks,
   then select a change. Submit **Create checked revision**.
3. Inspect the lock audit, solver status and **revision comparison**. Record any
   planning review against this new exact version in **Compare & review**.
4. Export the revised review pack, or return to the preserved parent.

The UI submits one disruption per revision. The local `/api/replan` endpoint
also accepts a batch of distinct change targets in `proposal.changes`, with
`completed_through_week` and `locked_activity_ids`. `/api/rollback` requires the
current revision ID and exact version. Both use the existing session protection.

Reproduce the demonstration into an empty/new directory:

```powershell
.\.venv\Scripts\python.exe tools/step8_report.py --output-dir outputs/step8/repeat-01
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Allocation details can vary between solver runs; each result records its own
fingerprints. The demo script independently checks both exported reports and
rollback rather than assuming the saved metrics.

## Export and remaining limits

Revision ZIPs preserve the three unchanged output schemas and add revised
`inputs/`, `planning-context.json`, `replanning.json` and the immediate parent's
input/schedule evidence under `parent/`. The manifest hashes the context and
replanning evidence. To validate extracted revised CSVs with their weekly supply:

```powershell
.\.venv\Scripts\python.exe -m ps1.validator PATH_TO_EXTRACTED_PACK/inputs PATH_TO_EXTRACTED_PACK --scenario A --planning-context PATH_TO_EXTRACTED_PACK/planning-context.json
```

The validator's nonzero `UNVERIFIED` exit status remains intentional: official
acceptance is not established. The three CSVs alone do not carry the disruption
overlay or locks. The existing browser CSV import flow does not restore a full
revision chain or its review history; retain the ZIP and JSON evidence. Session
storage is temporary and there is still no authenticated multi-user approval.

Completed work is a whole-week declaration, not actual-progress telemetry or
partial-night accounting. Urgent work uses existing project definitions; adding
new contracts is outside this step. Churn counts changed activities, not individual
row edits or total accesses. Equal-score/equal-churn revisions can retain extra
accesses; minimum total access usage is not claimed. Covered workload in the table
is capped at each activity's requirement, rather than counting overdelivery.
Replanning supports at most 20,000 interacting
activity-pair/weeks in addition to existing prototype limits. Build/check time
is additional to the selected solver limit, and the optional lock diagnostic can
add up to five seconds of solver search.

Full buffer/interchange protection, dated night availability, the official
validator and unresolved organiser rules remain unchanged limitations. Scenario C
keeps the conservative all-input-lines Live ECLO interpretation. This tool
provides planning drafts and does not authorise track entry.

No new plugin or external account was needed. The work uses local Python,
OR-Tools, JavaScript and browser verification. Changes are local; no GitHub push
or later workflow step was performed.
