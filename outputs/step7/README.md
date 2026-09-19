# Step 7 — alternatives and planner review

Implemented on 19 September 2026. This is the scheduled Step 7 implementation
report. The requested subsequent critique and Step 8 remain for a later turn.
The workflow and Step 5/6 review documents were read before implementation.

## What is available

- **Conflict explanations and checked alternatives.** A finding identifies the
  activities, week, locations and contradictory requirements. An actionable
  conflict can launch the existing scenario solver. The parent stays intact;
  only a complete candidate passing the existing independent checks is described
  as a checked model alternative. A timeout without an incumbent remains a
  no-solution outcome. Unresolved rules ask for clarification rather than offering
  an invented repair.
- **Compare & review.** Compare completion, delay, ECLO, excess capacity, conditional
  conflicts and changed activity allocations. Expand the allocation table or open
  either plan in the activity inspector. The comparison verifies identical input
  bytes, rule evidence and implementation fingerprints. Different scenarios can
  be compared by components, but their aggregate scores are not ranked.
- **Activity context.** Existing workloads, deadlines and working spans are joined
  by local sharing partners and the known opposite-bound working-core effect of
  Live activities. Full protection and buffer effects remain explicitly unknown.
- **Versioned review.** Comments, changes-needed decisions, draft rejection and
  recommendations for planning review attach to a digest of the exact three
  schedule CSVs, input identity, scenario, rules and implementation. Recommendations
  require complete work and successful implemented checks. Notes are append-only
  within the session; identical request retries are idempotent. Stale versions
  are rejected. Names are self-entered and are not authenticated signatures.
- **Export evidence.** Review packs include the review journal, alternative
  explanation/comparison, exact snapshot identity and integrity hashes. The
  original three-CSV submission schema is unchanged. Export still independently
  re-imports and checks the exact bytes, identities and report before packaging.

No changes were made to the reviewed optimiser, independent validator, night
diagnostic, importer, frozen inputs or rule profile. Scenario C retains its
conservative all-input-lines Live ECLO policy and explicitly labels a failure of
that construction policy separately from an organiser-confirmed rule violation.

## Demonstration and results

Final evidence is in [review-demo/](review-demo/), generated from the final source
fingerprints. The earlier `demo/` folder is intermediate evidence; use
`review-demo/` for the final results.

The supplied sample's Week 23 conflict requires A001 and A011 to share a night
through `PLAT:BET:S16:EB`, while requiring separate nights at `PLAT:BET:S15:EB`.
Those conditions cannot both hold under the disclosed full-night interpretation.
The checked alternative reschedules/regroups the whole Scenario A plan.

| Measure | Supplied sample | Checked alternative |
| --- | ---: | ---: |
| Completed activities | 54 / 54 | 54 / 54 |
| Covered workload units | 192 / 192 | 192 / 192 |
| Weekly violations | 0 | 0 |
| Conditional conflict weeks | 14 | 0 |
| Activity delay days, summed | 42 | 21 |
| Contract delay days, summed | 28 | 21 |
| Provisional Scenario A score | 48.3 | 25.2 |
| ECLO accesses / excess slots | 0 / 0 | 0 / 0 |
| Final completion | 25 July 2027 | 18 July 2027 |

**52 activities have changed allocations.** This is a whole-plan alternative,
with no minimum-change guarantee. It is not a local two-activity repair. Group
label renaming alone is excluded from the changed-allocation count; actual
sharing relationships, weeks, access counts and same-project night relationships
are compared. The exact schedule identity still records all CSV byte changes.

The demo also re-imports the previously reviewed Scenario B CSVs and checks that
an A/B comparison does not present an aggregate score improvement. Demonstration
review notes are explicitly labelled automated examples, not real planner sign-off.

## Validation

- **143 automated tests pass**, including 15 new planner tests. Coverage includes
  real solver alternatives, timeout outcomes, unchanged parents, exact versions,
  semantic allocation comparison, cross-scenario scoring, missing metrics,
  conservative C limits, review retry behaviour, stale reviews, export hashes and
  the token-protected HTTP routes. See [test-results.txt](test-results.txt).
- JavaScript syntax check passes. Frozen snapshot verification checks all 15
  files; rule-pack consistency verification passes for v0.2.0.
- The complete supplied-instance demonstration checks the exported CSV and review
  hashes and preserves parent bytes. Final independent revalidation and browser
  checks are recorded in [verification.json](verification.json).

## Use and reproduce

Start the app from the repository root:

```powershell
.\.venv\Scripts\python.exe -m ps1.webapp --port 8769
```

Open http://127.0.0.1:8769. Choose **Checks & conflicts → Review alternatives**,
then **Find checked alternative**. Inspect the comparison before recording a
decision. Export the review pack before stopping the server.

Reproduce the final demonstration into a new directory:

```powershell
.\.venv\Scripts\python.exe tools/step7_report.py --output-dir outputs/step7/repeat-01
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tool rejects a nonempty destination. Parallel solver search can produce a
different equally scored allocation; each result retains its own exact identity.
New local API routes are `/api/alternative`, `/api/compare` and `/api/review`.
The existing browser session token protects these POST operations.

## Remaining limits

These results establish success only under the disclosed model. Full protection,
dated operational nights and official validator acceptance remain unresolved;
exports remain review drafts and `official_validation` remains `NOT_RUN`.
Review records do not authorise track entry. There is no authenticated multi-user
approval workflow, digital signature or permanent review database. Refresh retains
the server session; stopping the server discards temporary runs. Exported journals
remain readable evidence, but the CSV import flow does not restore journal history.

Alternatives use the existing whole-plan scenario objective. Locked allocations,
completed-work freezing and minimising disruption belong to Step 8. No new plugin
or external app was required: local Python/OR-Tools, JavaScript and browser testing
were sufficient. Step 7 changes are local and have not been pushed to GitHub.
