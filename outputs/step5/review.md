# Step 5 critique and corrections

Reviewed 18 September 2026, alongside Step 6. The prototype is useful for local
planning review, but its original run recovery, navigation and provenance checks
needed correction. These changes are implemented, not proposals for a later step.

| Finding | Consequence | Correction |
|---|---|---|
| Refresh created a new sample and forgot the browser's run list. | Existing server runs became inaccessible through the UI and repeated refreshes consumed the 16-run allowance. | Authenticated session-list and run-retrieval routes restore the selected run without creating a run. If the server restarted, a fresh session loads normally. |
| Weekly finding buttons used the separate night-diagnostic week selector. | Inspection could jump to an unrelated week. | Each finding passes its own week; night findings pass their diagnostic week. |
| An invalid imported week could set a nonexistent timeline option. | An out-of-horizon schedule could break the displayed date range. | Clamp navigation to the horizon while keeping the original invalid week visible in the finding and activity details. |
| An input-only or unsuccessful solver run used an allocation explanation. | The inspector could say a solver chose work when it produced no schedule. | Separate explanations for no schedule, retained incumbent, new solver result, baseline and supplied schedule. |
| Export computed source hashes at download time and did not explicitly compare input identity. | Changed files could be attributed to an earlier run whose aggregate report happened to be unchanged. | Pin Python/UI fingerprints at workspace and run creation; reject further scheduling/export on source drift. Compare input identity, report and rule evidence during export. |

The session remains temporary. Refresh recovery does not provide disk persistence,
multi-user ownership or recovery after a server restart. Export important runs.
Source fingerprints detect file changes; they are not signed build attestations.
Changing source now requires restart and re-import before a new review pack can
be produced. The reviewed preview is at http://127.0.0.1:8768.

Verification included browser refresh preserving the exact selected baseline ID
and two-run list; switching back to the original sample; and a deliberately
invalid Week 999 finding opening Week 30 while its original W999 remained visible.
A synthetic A001 workload of 100 units produced a model precheck failure, kept
all activities visible and disabled CSV export. Its inspector correctly stated
that no allocations had been chosen. These fixtures are in `review-fixtures/`
and are explicitly synthetic; the frozen benchmark was not edited.

Backend tests cover read-only session recovery, token enforcement, source/input
identity drift, failed-import cleanup, byte-preserving exports, parent preservation
and solver publication rejection. See the [combined 128-test output](../step6/review-test-results.txt)
and [review verification](../step6/review-verification.json).

The baseline is still a partial first-fit comparison: 163/192 work units and
seven unfinished activities. It deliberately does not prove infeasibility or
perform the optimiser's sharing search. The original sample remains an unchanged
diagnostic example, not an endorsed feasible schedule. Public hosting and official
validation remain outstanding. No additional plugin or external account is needed
for these corrections; local Python and browser testing were sufficient.
