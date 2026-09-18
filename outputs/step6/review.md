# Step 6 critique and corrections

Reviewed 18 September 2026. The A/B/C model and independent accounting survive
this review. The largest code issue was an incomplete final publication gate;
the largest remaining product limitation is the gap between the disclosed model
and the organiser's unresolved full rules.

| Finding | Correction and evidence |
|---|---|
| The optimiser checked night consistency internally, but the final CSV re-import gate omitted it. | Require a successful conditional night assignment at publication too. A regression substitutes the supplied sample, which passes weekly accounting but has contradictory night relations; publication now fails. |
| The new run was stored before the final check, and rejection left its temporary directory behind. | Validate before publishing. Failed candidates remove their generated directory and preserve the parent's files and view. |
| Some invalid decisions have no computable metrics. | Reject these explicitly through the same structured error instead of dereferencing missing metrics. An out-of-horizon candidate exercises this path. |
| Clamping negative gaps to zero could conceal a contradictory bound. | Reject non-finite bounds and bounds above the independently checked objective; permit only negligible floating-point tolerance. |
| Timeout fallback retained CSVs but omitted the incumbent's abstract-night witness from solver metadata. | Retain that witness along with the complete checked schedule. The timeout test checks every activity/week is covered. |
| Set iteration could change model construction order across processes. | Sort working-location and mirror-pair iteration. This removes that avoidable source of variation; it does not promise identical multi-worker schedules. |

Optimiser version is now `ps1-cpsat-0.1.1`. The mathematical model remains
`weekly-core-nights-0.1.0`; no protection geometry, objective weight or challenge
rule was invented or relaxed during this review. The updated
[model contract](model_contract.md) states the scope precisely.

Final-code experiments are in [reviewed-runs/](reviewed-runs/summary.json), with
three CSVs, an independent validation report, solver metadata, provenance and a
review ZIP for each scenario. Older `runs/`, `initial-runs/` and intermediate
`review-runs/` remain historical evidence.

| Final checked measure | A | B | C |
|---|---:|---:|---:|
| Provisional objective | 25.2 | 35.0 | 25.2 |
| Model lower bound | 25.2 | 35.0 | 25.2 |
| Gap within this model | 0% | 0% | 0% |
| Required activities completed | 54/54 | 54/54 | 54/54 |
| Implemented weekly violations | 0 | 0 | 0 |
| Conditional night check | Assigned | Assigned | Assigned |

All runs use the same frozen eight-file instance, active v0.2.0 rule profile,
30-second CP-SAT search limit, four workers and seed 0. Runtime includes additional
model-building/checking work; it is not a strict end-to-end limit. Measured timings
and exact component totals are retained in the run files, not projected onto
hidden instances. A, B and C use different objectives/policies, so their numerical
scores are not directly interchangeable rankings of operational desirability.

128 tests passed, including the hand-calculated scheduling cases, timeout retention,
corrupt output rejection and new publication/provenance boundaries. The 15-file
frozen pack, 34-rule specification and 26 examples also passed verification.
See [test output](review-test-results.txt) and [artifact verification](review-verification.json).
Browser checks and interface corrections are recorded in the [Step 5 review](../step5/review.md).

Three limits must remain explicit before moving on:

1. Buffers, interchange effects and actual dated night availability are unresolved.
   A checked abstract-night assignment is not a track-entry permission or a fully
   protected operational plan. No official validator has been run.
2. Scenario C uses the supplied instance provisionally. Its Live ECLO policy
   constrains all input lines, which may be more restrictive than the eventual
   affected-line map. Combined with missing protection constraints, the model is
   neither an exact implementation nor a simple relaxation of the unknown full
   problem. Its optimum and lower bound apply only to the disclosed model.
3. This remains a bounded, synchronous, single-user local application. Public
   hosting still needs background jobs, cancellation, run isolation and measured
   hidden-instance limits. No persistent run storage or deployment is claimed.

The workflow now makes publication, provenance and model-scope checks explicit.
Steps 5 and 6 are ready for subsequent interface work under these stated limits;
official submission readiness is still unestablished. Existing local tools and
pinned OR-Tools are sufficient. No new plugin, external API or credential is needed.
