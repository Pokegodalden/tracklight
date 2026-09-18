# Tracklight

Night railway track-access scheduling for the LTA NebulaX PS1 hackathon.

Authors: [Pokegodalden](https://github.com/Pokegodalden),
[WhitebloodWind](https://github.com/WhitebloodWind), and
[Ausgustine](https://github.com/Ausgustine). See [AUTHORS.md](AUTHORS.md).

Development follows [workflow.txt](workflow.txt), one reviewed step at a time.

Steps 5 and 6 have now been reviewed and corrected. See the [interface/export
review](outputs/step5/review.md), [solver review](outputs/step6/review.md) and
[regenerated A/B/C results](outputs/step6/reviewed-runs/summary.json).
The current reviewed preview runs at http://127.0.0.1:8768; earlier preview
processes and historical reports have been left intact.

The [README update review](outputs/readme-update-966c976/README.md) adopts upstream
commit `966c976005db2e3e40a691cff268fdb8f396a5df`. Active rule profile:
[v0.2.0](specs/ps1/v0.2.0/profile.json). Strict later-week predecessor precedence
is now documented, including cross-contract links and the prohibition on cycles.
The existing scheduler already followed this rule; the original data and v0.1.0
pack are preserved. Historical Step 1–5 reports describe the version at that time.

- [Current rule register](outputs/readme-update-966c976/rule_register.md)
- [Current organiser questions: Q06 resolved, 11 open](outputs/readme-update-966c976/organiser_questions.md)
- [Refreshed run evidence](outputs/readme-update-966c976/runs/evidence.json)

Step 1: inputs frozen and acceptance defined. Step 2: versioned rules and
examples prepared; predecessor clarification adopted, remaining critique deferred
pending the unresolved organiser information.
Step 3: importer and network model implemented under the provisional profile.
Step 4: provisional schedule checker and conditional physical-night diagnostic
implemented. Full protection validation remains unverified.
Step 5: local web import/review/export prototype and a deterministic Scenario A
baseline implemented. The baseline is partial.
Step 6: OR-Tools optimisation for A/B/C is implemented, with complete independently
checked model solutions for the supplied instance. Full protection and official
acceptance remain unverified. [Step 6 results and scope](outputs/step6/README.md).

Start the app from this project directory using its Python 3.12 virtual environment:

```text
.\.venv\Scripts\python.exe -m ps1.webapp --port 8768
```

Open http://127.0.0.1:8768. Browser refresh restores the selected server-session
run; a fresh server session loads the supplied sample automatically. Use
**Create Scenario A baseline** to create a separate run, or **Import CSV files**
for another eight-file input instance. **Optimise scenario** solves A, B or C
with a bounded search and shows the score, lower bound and model assumptions.
Exports are review packs, not accepted
submissions. Export before stopping the server; runs use temporary local storage.

On a fresh checkout, first run `python -m venv .venv`, then
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
OR-Tools and its dependencies are pinned in [requirements.txt](requirements.txt).
Run the test suite with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

- [Step 5 report and usage](outputs/step5/README.md)
- [Step 5 measured evidence](outputs/step5/evidence.json)
- [Hosting and hidden-instance assessment](outputs/step5/hosting.md)

- [Step 1 report](outputs/step1/README.md)
- [Acceptance checklist](outputs/step1/acceptance_checklist.md)
- [Dependency register](outputs/step1/dependency_register.md)
- [Step 1 critique and corrections](outputs/step1/review.md)
- [Frozen input manifest](data/baselines/ps1-0dfd901f97bf579f/manifest.json)
- [Step 2 report](outputs/step2/README.md)
- [Rule register](outputs/step2/rule_register.md)
- [Rule examples](outputs/step2/examples.md)
- [Historical Step 2 rule profile](specs/ps1/v0.1.0/profile.json)
- [Step 3 report](outputs/step3/README.md)
- [Step 3 critique and corrections](outputs/step3/review.md)
- [Supported input contract](outputs/step3/input_contract.md)
- [Imported model and network](outputs/step3/import_result.json)
- [Step 4 report](outputs/step4/README.md)
- [Step 4 critique and corrections](outputs/step4/review.md)
- [Sample validation and night diagnostic](outputs/step4/sample_validation.json)
- [Validation contract and limitations](outputs/step4/validation_contract.md)

The source READMEs inside `data/baselines/` are evidence from the supplied pack.
They are distinct from this project README. The root source README mentions
other problem statements; development remains limited to PS1.

Verify the frozen snapshot with Python 3.12 (the checked runtime):

```text
python tools/baseline.py verify data/baselines/ps1-0dfd901f97bf579f
python tools/rule_pack.py
python -m ps1.importer data/baselines/ps1-0dfd901f97bf579f/PS1/01_data --output outputs/step3/import_result.json
python -m unittest discover -s tests -v
```

The verifier checks recorded bytes and inventory; it is not the official
scheduling validator. Frozen copies are ordinary files with tamper-detecting
fingerprints, not access-controlled immutable storage. Do not edit them in place.

For an updated organiser pack retaining the same reviewed PS1 file layout,
create a new snapshot. This utility is not the eventual eight-CSV hidden-instance
importer: it also requires the original brief, references and sample file paths.
If an organiser changes that layout, review it before adapting the utility.

```text
python tools/baseline.py freeze --source-root PATH_TO_PS1 --root-readme PATH_TO_ROOT_README
```

Each snapshot records its own provenance and content identities. Future solver
runs must reference those identities alongside code/rule versions and settings.

New snapshots are written to a temporary directory, checked, and renamed into
place only after verification and a final source comparison. Ordinary exceptions
clean up that temporary directory. An abrupt process termination may leave a
`.staging-*` directory; it is not a published baseline. Existing baselines are
verified and reused without rewriting their manifests, or rejected if damaged.

The input-data fingerprint covers exactly the eight named input CSVs. Extra
notes or references affect only the pack fingerprint. Additional files are
preserved and listed, but their meaning requires review; calendar availability
is unassessed (`null`) for extended packs. The original benchmark counts remain
comparison diagnostics, not limits on future instances.
