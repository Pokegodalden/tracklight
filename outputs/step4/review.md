# Step 4 critique and corrections

Reviewed 18 September 2026. Validator revised to **0.1.1**. Step 2's rule profile
and the frozen data remain unchanged. Step 5 has not started.

The initial weekly accounting and sample reconciliation were sound for the tested
cases, but the diagnostic's verification and reporting needed improvement. Eight
new regression tests reproduced the following gaps before the fixes.

## Findings and changes

| Priority | Reproduced gap | Correction |
|---|---|---|
| High | The final assignment checks used Python assertions, which disappear under `python -O`. Fault injection of two separated activities assigned to the same night then escaped the checks. Night label 0 also passed the original checks even without optimisation. | Explicit runtime verification now checks exact component coverage, integer labels within the night limit, equality, separation and workfront limits. It remains active under optimisation. Failure suppresses the assignment and produces INTERNAL_ERROR / VALIDATION_ERROR, not a false infeasibility claim against the user's schedule. |
| Medium | Deleting an input file produced an invalid overall status with an empty primary findings list. The reason was available only in the nested importer report, while the command summary counted zero findings. | Include input-stage findings and source locations in the primary report. Keep `rule_id` null for input errors rather than inventing a scheduling rule attribution. |
| Medium | An empty access file yielded ASSIGNED_FOR_MODELLED_RELATIONS despite assigning nothing. A partial schedule's diagnostic did not disclose how much required work was outside its scope. | Empty diagnostics now say NO_ACCESSES. Populated diagnostics explicitly report required/scheduled activity counts, unscheduled and incomplete activity IDs, and workload completeness. Partial assignments still help inspect submitted work, but cannot imply all work is scheduled. |
| Medium | Exact search could report a night-limit contradiction with an empty conflict list. Eight mutually separated activities under seven nights reproduced this. | Include a replayable constraint witness: component membership, equality edges, separation edges with their reasons, and the selected limit. It is not claimed minimal or an independently certified proof trace. |
| Low | Invalid diagnostic settings were checked only when the diagnostic was reached, so malformed inputs or blocked occupancy could bypass option validation. | Validate options at the public and internal checker entry points, before data processing. Invalid limits, negative budgets and booleans masquerading as integer limits are rejected consistently. |
| Low | Capacity findings named the location/week but left the affected activity list empty. | Include all contributing activities and the supplied capacity's source row. |

The fault-injection tests demonstrate weaknesses in the verification safeguards;
they do **not** demonstrate that the original graph-colouring algorithm generated
an invalid assignment on the supplied sample. The existing exhaustive comparison
on all four-node graphs is retained.

## Decisions retained

Weekly benchmark violations and conditional physical-night conflicts remain
separate. A contradictory full-night interpretation must not silently redefine
the benchmark constraints. The seven-night limit remains a calendar upper bound,
not an operational access calendar; lower limits are explicitly diagnostic cases.

Buffer and interchange semantics remain unresolved. The diagnostic continues to
check only modelled relations and the known Live opposite-bound working core.
It does not fill missing protection footprints with guesses or turn unresolved
checks into passes. Scenario C's affected-line completeness and input applicability
remain provisional.

The checker still withholds full-feasibility and official-score claims. Search
exhaustion remains different from a proven contradiction within the conditional
model. Uploaded-file limits, wall-time limits and a user interface remain later
application work.

## Verification and outcome

The full suite now contains **88 tests**, including 29 validator/diagnostic tests.
New checks cover runtime verification under optimised Python, malformed assignment
payloads, hidden input errors, empty/partial coverage, invalid options, night-limit
witnesses and actionable capacity findings.

The refreshed sample report retains the same substantive results: no implemented
weekly violations, provisional arithmetic **48.3**, and conditional night
inconsistencies in **14 of 29 occupied weeks**. R10 now also exposes the conditional
diagnostic result in the per-rule summary, without classifying it as a benchmark
violation. Overall status remains UNVERIFIED.

See [current verification](review_verification.txt), the refreshed
[sample report](sample_validation.json), and the updated
[validation contract](validation_contract.md). The original
[verification log](verification.txt) is retained as historical evidence.
