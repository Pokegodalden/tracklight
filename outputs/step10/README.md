# Step 10 — reproducible delivery and deployment preparation

Step 9 was skipped as requested. The local Step 10 implementation and candidate
package are prepared. **The overall delivery gate remains open:** there is no
published hosted URL, GitLab URL or YouTube URL yet. Account destinations,
visibility, hosting budget and real host limits still need to be established.

## Deliverables

- `final-release/submission/A`, `B`, `C`: exactly three original-schema CSVs per
  scenario; no diagnostic columns. `final-release/tracklight-ABC-candidates.zip`
  contains those nine files. These are candidates, not officially accepted plans.
- `final-release/evidence`: independently re-imported validations, review packs,
  solver outcomes, baseline comparison, synthetic upload and disruption evidence.
- `final-release/manifest.json`: exact input/rule/source/file hashes, package and
  Python versions, solver settings, measured times and unresolved limitations.
- `tracklight-source.zip`: allowlisted source and evidence, with file fingerprints;
  excludes session stores, environments, git history and publication credentials.
- `tracklight-walkthrough.mp4`: three-minute captioned walkthrough using actual
  browser captures. `docs/walkthrough.json` is the scene script;
  `docs/youtube-upload.md` is the upload description draft. No video was uploaded.
- `docs/deployment.md`, `Dockerfile`, `requirements-hosted.txt` and
  `.gitlab-ci.yml`: deployment and CI preparation. Docker and GitLab CI have not
  been executed on a chosen host/runner.

Use **final-release**, not the earlier `release` experiment. The earlier C run
found a much worse incumbent before target-scenario warm-start reuse was added.
Historical Step 6–8 results remain historical evidence, not this release's manifest.

## Measured results

Public benchmark: 54 activities, 192 standard-equivalent units, identical input
bytes and provisional rule profile. One solver worker, seed 0, 30-second search
limit. Wall times include setup/checking and may exceed the search limit.

| Candidate | Completed | Work covered | Provisional score | Wall seconds | Model proof |
| --- | --- | --- | --- | --- | --- |
| A | 54/54 | 192/192 | 25.2 | 29.38 | Optimal for disclosed model |
| B | 54/54 | 192/192 | 35.0 | 30.64 | Optimal for disclosed model |
| C | 54/54 | 192/192 | 25.2 | 12.38 | Optimal for disclosed model |

All three have zero implemented weekly violations and zero conditional night
conflict weeks. This does **not** establish full protection or official acceptance.
Different scenarios have different constraints/objectives; their scores are not
a general ranking. C started from an independently checked A incumbent retagged
for C, so these timings are workflow measurements, not equal cold-start benchmarks.

The deterministic greedy baseline completes 47/54 activities and 163/192 units in
0.15 seconds. Its incomplete score is not ranked against complete solutions.
The supplied sample covers all work but has 14 conditional conflict weeks and a
provisional score of 48.3. The A comparison demonstrates repair under our model,
not a measured operational saving or official validator improvement.

The synthetic renamed public instance completes all work with score 25.2. It
tests identifier independence and upload plumbing, not unknown topology/scale
or official hidden-instance performance. Additional importer/model tests cover
small synthetic cases; genuine hidden data and host limits remain unavailable.

The disruption adds one unit to A001, freezes weeks 1–10 and locks A002. Its
independent lock audit passes; all 193 units are covered, score stays 25.2, one
activity changes and rollback preserves both versions. The earlier Step 8 demo
changed four activities from a different parent allocation; churn depends on the
exact parent. Do not mix their provenance.

## Implementation and validation

`ps1.hosted` wraps the existing Workspace in pinned Waitress, preserving the
independent validator and reviewed scheduling semantics. It adds session-owned
durable checkpoints, a serial subprocess queue, idempotent requests, refresh
recovery, cancellation, a wall deadline, retention and quotas. HTTPS/Host/Origin/
CSRF checks and a shared judging password protect the public-mode boundary.
This is a single-instance judging service, not an individual-account platform.

One small scheduling workflow improvement copies an incumbent into the requested
scenario, then revalidates it against that scenario before using it. A feasible
A incumbent can help C; an A plan missing B's deadlines cannot be retained for B.
The parent is unchanged. No rule, objective or independent-check semantics were
relaxed to obtain the reported scores.

The **166-test suite passes**, including seven new hosted transport/persistence/
timeout/isolation/incumbent tests using real child worker processes. Frozen-input
verification and rule-pack checks remain required in the reproduction procedure.
The browser exercised all eight uploaded CSVs, asynchronous solve and refresh,
conflict explanation, checked alternative, comparison, controlled revision,
export and return to the parent while retaining both versions. Captures are in
`video-frames`. Video decode/layout and clean-source reproduction results are
recorded separately in `verification.json` and `video-manifest.json`. A clean
archive extraction passed the frozen baseline, rule-pack checks and all 166 tests
using the existing pinned Python environment; see `reproduction-results.txt`.
This was not a fresh dependency installation or a Docker/Linux execution.

An upstream check found main still at README commit `966c976…`; the published
PS1 README matches the frozen reviewed bytes and the PS1 tree contains no official
validator. See `upstream-check.json`. Eleven organiser questions remain open;
full buffer/mirror/interchange protection and dated physical-night semantics are
not inferred from missing guidance. Scenario C retains the disclosed conservative
Live-line policy. No DataMall or OBU credentials are needed or included.

## Reproduce and continue publication

Use Python 3.12. From an extracted source package:

```text
python -m venv .venv
python -m pip install -r requirements-hosted.txt
python tools/baseline.py verify data/baselines/ps1-0dfd901f97bf579f
python tools/rule_pack.py
python -m unittest discover -s tests -v
python tools/step10_package.py --output-dir outputs/step10/new-release --seconds 30
python -m ps1.hosted --local --port 8780 --data-dir .tracklight
```

Activate that virtual environment first, or replace `python` with its executable.
The output directory must be new. Optimal objective values are the reproduction
target; tie allocations, timing and byte hashes can vary between platforms/runs.
The stored manifest verifies the supplied artifact bytes, not future tie choices.
Optional video rendering uses `requirements-video.txt` and
`python tools/build_walkthrough.py --captions-only` with the supplied captures.

Before publication, select the hosting project/budget, GitLab namespace and
YouTube channel/visibility. Then build the container, verify the deployed upload/
solve/recovery/isolation flow under actual resource limits, run GitLab CI and
publish the prepared video with verified URLs. The existing GitHub repository
is not a substitute for the challenge's requested GitLab URL. No new pushes or
external publications were performed in this step.

Tools used: local Python/PowerShell, browser automation and local video rendering.
No optional plugin is required. Hosting/GitLab/YouTube account access is needed
for the outstanding external actions; specific connectors are optional.
