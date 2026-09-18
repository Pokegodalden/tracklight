# Step 2 — rules and small examples

Prepared 18 September 2026 for review. Scope: Step 2 of workflow.txt only.
The user confirmed that no new organiser clarification or official tool is
available. This specification is tied to the frozen Step 1 input pack.

There are **34 rules: 15 documented, 16 provisional and 3 deferred**, with
**26 examples** and **12 draft organiser questions**. “Documented” means stated
in the supplied brief or data; it does not mean independently confirmed by an
organiser or official validator.

## Reviewable outputs

- [Rule register](rule_register.md): interpretation, source/line, status, example and intended enforcement for each rule.
- [Small examples](examples.md): isolated inputs, expected outcomes under competing interpretations, and exact sample evidence where relevant.
- [Organiser questions](organiser_questions.md): prioritised, concrete questions; prepared but not sent.
- [Versioned development profile](../../specs/ps1/v0.1.0/profile.json): machine-readable choices and explicit unconfigured rules.
- [Verification report](verification.json): consistency, source-record and selected arithmetic checks.

The canonical register and examples are [rules.json](../../specs/ps1/v0.1.0/rules.json)
and [examples.json](../../specs/ps1/v0.1.0/examples.json). The Markdown views are
generated from those files. The profile pins their exact byte fingerprints as
well as the baseline and eight-input identities.

## Decisions for development

| Topic | Selected interpretation | Qualification |
|---|---|---|
| Weekly allocation | Local location/week sharing and contract/type/week access indices | A separate diagnostic will test common physical-night consistency; local labels are not calendar nights. |
| Network | Line-aware platforms and tunnels; separate ALP/BET capacities | Live protection can connect the lines; its exact footprint remains unresolved. |
| Dependencies | Finish a predecessor in an earlier week | Provisional and stricter than permitting within-week sequencing. |
| Calendar | Seven-day buckets from horizon_start; finish on the last day of the last allocated week | Matches all 14 sample contract results; does not establish every hidden-date convention. |
| Supply/horizon | Repeat supplied capacities within weeks 1..horizon_weeks | Missing supply is an error; no invented extension or amended Scenario C file. |
| Scenario A | No excess capacity; no ECLO; delay permitted | Optimise the disclosed provisional delay formula. |
| Scenario B | Hard planned completion dates; penalised excess capacity and ECLO | The brief's suggestion that P3 can slip conflicts with this hard deadline. |
| Scenario C | At most one excess group per location/week; ECLO in at most two adjacent weeks per affected line | Line windows are independent; cross-line Live effects depend on the unresolved footprint. |
| ECLO | Charge per activity-access row; require consistent flags within each local sharing group | Both are provisional; uniform flags are an additional development restriction. |
| Score | Activity-weighted delay, plus applicable excess/ECLO penalties | Show contract delay separately; do not present this as the official score. |
| Occupancy export | Working span only; protection stored separately | Based on the sample, pending the official expander. |

## Findings that affect the design

**Weekly labels do not establish a physically consistent night.** In Week 23,
A001 and A011 share a group at one platform and have different groups at another
platform on the same span ([E07](examples.md#e07)). Under a one-full-night-per-access
interpretation, that demands both equal and unequal nights. This is a conditional
inconsistency, not proof that the official benchmark rejects the sample.

**Local workfront accounting can miss physical concurrency.** In Week 25,
A040 and A042 use different contract-local indices but share one occupancy group;
their contract has one workfront ([E08](examples.md#e08)). The local-index limit
and a physical simultaneity check answer different questions.

**Contract delay is not the same as activity delay or a weighted score.** With
the selected week-end convention, the sample has 28 contract delay days,
42 activity delay days and a candidate activity-weighted delay score of 48.3
([E22](examples.md#e22)). These are different measurements, not three competing
calculations of one confirmed official score. All 14 sample contract completion
dates reconcile under this convention.

**The priority narrative cannot substitute for the objective.** A weighted sum
can prefer seven P1 delay days over 77 P2 delay days (700 versus 770 under the
example's multipliers). Strict priority ordering would choose differently
([E23](examples.md#e23)). The implementation must disclose which rule it uses.

## Unresolved protection rules and the Step 2 gate

Three choices remain deliberately unconfigured:

- R12: exact buffer geometry, terminal treatment and mirrored extent.
- R15: the trigger and locations affected by Live interchange propagation.
- R17: how to establish simultaneous protection conflicts from weekly decisions.

Their explicit handling policy is **UNVERIFIED**, never PASS. Dependencies such
as Live opposite-bound checks, sharing exemptions and Scenario C affected-line
windows must inherit that uncertainty where relevant. The 16 provisional rules
are also assumptions, even though a development choice has been recorded.

Step 2's specification gate is met: every rule has a documented interpretation,
an explicit development assumption, or a declared unresolved policy that blocks
a full-feasibility claim. This permits Step 3 data/import/network work after
review. It does **not** establish full protection validation, official scoring
equivalence, or operational readiness. Step 3 has not been started.

## Verification and limits

The checker verifies the frozen baseline, version/fingerprint consistency,
source anchors, reciprocal rule/example links, and all 28 cited CSV records.
It recomputes nine selected evidence/arithmetic observations, including the two
conditional sample contradictions and the delay/date reconciliation.

The examples are specifications, not complete eight-CSV submission fixtures.
Their other expected outcomes are authored cases for later implementation tests.
No scheduler or official feasibility validator has been implemented in this step.
Regression tests check that specification drift, changed evidence, invented
official results and treating unknown checks as passed are detected.

Run from the project root with Python 3.12:

```text
python tools/rule_pack.py
python -m unittest discover -s tests -v
```

Use `python tools/rule_pack.py --render` to refresh the derived Markdown views
from a consistent canonical pack. Preserve released versions when new organiser
information arrives; create a new profile version, update its source evidence
and fingerprints, and rerun the checks before adopting it.

## Tools and apps

Step 2 uses local text/JSON files and Python's standard library. No additional
plugin, account connection or API key is needed. Notion is optional for a shared
register; Teams/Outlook are optional only if the user later asks to send the
clarification draft. Step 3 can also proceed with local development tools.
