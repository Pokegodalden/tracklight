# PS1 acceptance checklist

Baseline: `ps1-0dfd901f97bf579f`. Prepared 18 September 2026.
This separates completion of Step 1 from acceptance of the future application.
Project scope remains PS1. No schedule has been generated or certified in Step 1.

## Step 1 gate

| ID | Criterion | Evidence | Status |
|---|---|---|---|
| S1-01 | Inventory both READMEs, eight inputs, two diagrams and three sample outputs | Frozen pack and manifest contain 15 files | Complete |
| S1-02 | Preserve exact original bytes and identify each file | Per-file SHA-256, byte sizes, source paths and independent source/copy comparison | Complete |
| S1-03 | Identify the full pack and the eight-input dataset separately | Pack and input-data fingerprints in manifest | Complete |
| S1-04 | Recompute the stated baseline | CSV row counts, distinct station/contract counts and workload total | Complete |
| S1-05 | Record the horizon and calendar limitation | 2027-01-04, 30 weeks; inclusive arithmetic end 2027-08-01; no dated operational access calendar | Complete |
| S1-06 | Define application/submission acceptance without claiming it has passed | Requirements below | Complete |
| S1-07 | Track missing dependencies and their impact | dependency_register.md | Complete |
| S1-08 | Provide a repeatable integrity check | Baseline verifier, independent PowerShell cross-check and disposable-copy integrity tests | Complete |

Complete here means the Step 1 evidence exists and was checked. It does not
mean the rules are resolved, the sample is dispatchable, or the app is complete.

## Mandatory challenge acceptance for the finished project

Source: frozen `PS1/PS1_README.md`, sections 1, 2.4-2.7, 3.2 and 4.
The requirement categories below are paraphrased criteria, not additional
instructions from the source. Ambiguous implementation details go to Step 2.

| ID | Requirement | Evidence required before marking passed | Current status |
|---|---|---|---|
| APP-01 | Complete every supplied activity's workload; no dropped or truncated work | Per-activity delivered/required reconciliation under the applicable yield rule | Not implemented |
| APP-02 | Enforce applicable hard safety and allocation rules | Versioned rule profile, independent checks, targeted boundary cases, official report when available | Not implemented; rule details unresolved |
| APP-03 | Handle A, B and C separately | Three scenario runs, each with complete workload and its own applicable rules | Not implemented |
| APP-04 | Apply each scenario's objective and explain trade-offs | Score-component breakdown, confirmed formula version, comparison under identical inputs | Not implemented; scoring interpretation unresolved |
| APP-05 | Produce the required CSV schema for each scenario | RESULTS.csv, SCHEDULE_ACCESS.csv and SCHEDULE_OCCUPANCY.csv for each of A/B/C; nine output CSVs in total | Not implemented |
| APP-06 | Reconcile exported results and occupancy | Independent re-import and checks against access decisions and inputs | Not implemented |
| APP-07 | Support unseen eight-CSV instances | Hosted UI upload, validation errors and live scheduling without hard-coded sample counts or IDs | Not implemented |
| APP-08 | Provide usable visualisation and explanations | Controller-facing walkthrough of an allocation, a conflict and a trade-off | Not implemented |
| APP-09 | Prove official feasibility/score claims | Exact official validator version, invocation and saved outputs | External dependency missing |
| SUB-01 | Submit public test results | Precomputed A/B/C output sets, following section 2.6 | Not started |
| SUB-02 | Submit a hosted live web application URL | Accessible app supports judges uploading hidden instances and running the scheduler | Hosting not selected |
| SUB-03 | Submit a three-minute YouTube video | Reviewed demonstration video and working YouTube URL | Not started; publication/account access not configured |
| SUB-04 | Submit a GitLab repository URL | Complete source, solver, setup instructions and documentation in an accessible repository | Repository not created; account/access not configured |

Important discovery: section 3.1 permits several form factors in general, but
section 4 explicitly asks for a hosted web application. Plan the submission
around the explicit deliverable, subject to an organiser update. A CLI-only
prototype will not satisfy the currently supplied deliverable list.

## Project engineering acceptance

These are our selected quality criteria, not extra official scoring rules.

| ID | Criterion | Evidence | Current status |
|---|---|---|---|
| ENG-01 | Reproduce a run against exact inputs | Pack/input fingerprint, rule and formula version, scenario, code version, dependency versions, solver settings and time limit | Input provenance ready; run system pending |
| ENG-02 | Report solver outcome honestly | Distinguish feasible, proven optimal, proven infeasible and no solution found within the limit | Not implemented |
| ENG-03 | Protect complete feasible results from later failed searches | Retained validated incumbent where one exists | Not implemented |
| ENG-04 | Separate validation levels | Input checks, implemented-rule checks, conditional physical-night checks and official acceptance shown distinctly | Defined; not implemented |
| ENG-05 | Account for unresolved physical-night semantics | Conditional consistency diagnostic and explicit availability/calendar limitations | Pending Step 2/4 |
| ENG-06 | Compare against a baseline fairly | Same inputs/rules, measured runtime, workload completion and objective components | Not implemented |

For future runs, reference the snapshot ID plus the full pack and input hashes.
Absolute source paths and capture time are provenance metadata, not identity.
Changing an input or reference creates a new pack version; never update an old
snapshot to make a verification failure disappear.

## Selected extensions and non-gates

Controlled replanning is in our project workflow, but PS1 section 3.3 describes
it as bonus scope. Natural-language querying and other innovation are optional.
DataMall enrichment, OBU integration, external collaboration apps and slide decks
are not prerequisites for the core challenge output. If time is constrained,
protect the mandatory submission items first.

Deployment, publishing a video and repository sharing are future actions. Step 1
records their requirements; it does not perform them or choose account visibility.

Review update: workflow.txt now explicitly includes the hosted app, YouTube
video and GitLab URL and gives mandatory submission readiness priority over
bonus replanning. Snapshot integrity verification has expanded to 19 passing
tests. These corrections do not change the frozen inputs or close any Step 2
rule clarification.
