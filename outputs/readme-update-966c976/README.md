# PS1 README update adopted — commit 966c976

Reviewed against the exact [organiser commit](https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/commit/966c976005db2e3e40a691cff268fdb8f396a5df).
The commit changes only `PS1/PS1_README.md` (14 additions, 11 deletions).
Our frozen README is byte-identical to its parent revision, so this comparison
covers the complete change from the brief used by the project.

## What changed

| Change | Meaning for the project |
|---|---|
| New section 2.4 rule 3: predecessor precedence | The successor's first scheduled access must be in a strictly later week than the predecessor's last scheduled access. Same-week ordering is forbidden even if actual clock times could be sequenced. |
| Cross-contract predecessor links explicitly allowed | Resolve predecessors globally by activity ID, not within one contract. |
| Predecessor cycles explicitly prohibited | Retain cycle rejection with an identified dependency path. |
| Nullable predecessor field added to the activity description | The existing optional field is now explained in the brief; the CSV schema itself is unchanged. |
| Operating rules renumbered and access-cap/workfront references corrected | Weekly allocation is rule 7; workfronts rule 8; ECLO continuity rule 10. The limits and formulas themselves did not change. |
| Technical-execution table formatting corrected | No judging-policy change. |

The phrase FS+0 does **not** authorise same-week scheduling: the explicit
week-level requirement controls the implementation. If a predecessor reaches
its required yield in week 2 but retains another scheduled access in week 4,
its successor cannot start before week 5. R01 still independently requires
complete workload for every activity.

## Project changes made

- Created and activated [rule profile v0.2.0](../../specs/ps1/v0.2.0/profile.json).
  Internal **R18** is now documented. Internal rule IDs remain stable; R18 maps
  to README section 2.4 rule 3, rather than renumbering our entire register.
- Resolved **Q06** from the published brief, without claiming a direct organiser
  response or official validator verdict. Unknown-ID rejection remains an input
  integrity policy; the brief does not specify official error wording or format.
- Updated E14, the [rule register](rule_register.md), [question list](organiser_questions.md),
  importer metadata, validation explanation and [workflow](../../workflow.txt).
- Pinned the downloaded README's SHA-256 in the active profile. Imports verify
  that evidence; runs and review exports carry the profile identity and exact
  upstream commit. Export rejects a mismatch in rule evidence as well as a
  mismatch in the validation report.
- Added visible README/profile information and a confirmed dependency explanation
  in the activity inspector. The updated local preview is running at
  http://127.0.0.1:8766; the earlier process on 8765 was left intact.
- Preserved the original snapshot, v0.1.0 specifications and historical Step 1–5
  reports. Fresh exports and evidence are stored in [runs/](runs/evidence.json).

The existing importer, validator and baseline already enforced the clarified
dependency semantics. Scheduling decisions therefore did not need to change.
This is an evidence/version update with stronger regression coverage, not a new
optimisation algorithm.

## Verification and impact

The [comparison](comparison.json) verifies that all three schedule CSVs for both
the sample and generated baseline remain byte-identical to their Step 5 exports.
Their validation reports also remain equal; provenance identifies the new release.

| Result | Sample | Scenario A baseline |
|---|---:|---:|
| Required units allocated | 192 / 192 | 163 / 192 |
| Unfinished activities | 0 | 7 |
| Implemented weekly violations | 0 | 11, all completeness/result omissions |
| Conditional night-conflict weeks | 14 | 0 among placed accesses |
| Full feasibility / official acceptance | Unverified | Not established; partial draft |

All six sample predecessor links satisfy the confirmed rule:

| Predecessor → successor | Last predecessor week | First successor week |
|---|---:|---:|
| A003 → A004 | 16 | 21 |
| A012 → A013 | 20 | 22 |
| A037 → A038 | 9 | 10 |
| A048 → A049 | 3 | 8 |
| A050 → A051 | 18 | 26 |
| A065 → A066 | 20 | 25 |

The baseline still leaves A004 unfinished because A003 is unfinished. The update
confirms that this dependency cannot be bypassed; it does not prove that A003
cannot be placed by a better scheduler.

All **106 tests passed** in 11.701 seconds. Checks include source-pack verification, rule-pack source
anchors/fingerprints, export round trips and a browser check of A004's dependency
explanation. See [test output](test-results.txt), [specification verification](verification.json)
and [run evidence](runs/evidence.json). New regression coverage includes cross-contract
imports, last-access precedence after excess yield, preserved unresolved questions,
source-evidence integrity and export provenance drift.

## What this update does not resolve

The remaining 11 questions are still open. In particular, there is no new
physical-night assignment, protection-expansion algorithm, buffer exemption scope,
interchange trigger, official score result, Scenario C input manifest or official
validator/hidden-instance execution contract in this commit. Rules R12/R15/R17
remain unconfigured; the sample's conditional night contradictions remain.

Do not infer these rules from the newly inserted predecessor paragraph, and do
not treat the current partial baseline as a complete accepted incumbent. Continue
with the planned Step 5 critique before Step 6 optimisation; no Step 6 work was
started during this update.

## Reproduce

```text
python tools/rule_pack.py
python tools/baseline.py verify data/baselines/ps1-0dfd901f97bf579f
python -m unittest discover -s tests -v
python tools/step5_report.py --output-dir outputs/readme-update-966c976/runs
python -m ps1.webapp --port 8766
```

Archived evidence: [commit metadata](../../data/source_updates/966c976005db2e3e40a691cff268fdb8f396a5df/commit.json),
[source diff](../../data/source_updates/966c976005db2e3e40a691cff268fdb8f396a5df/README.diff),
[updated README](../../data/source_updates/966c976005db2e3e40a691cff268fdb8f396a5df/PS1_README.md),
and [source manifest](../../data/source_updates/966c976005db2e3e40a691cff268fdb8f396a5df/manifest.json).
No new plugins or external API credentials are required.
