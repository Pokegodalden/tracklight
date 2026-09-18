# PS1 organiser clarification draft

Version 0.1.0; baseline `ps1-0dfd901f97bf579f`. No organiser response or official tool result is available.

Prepared for review; not sent. The user confirmed there is no new organiser information. P0 means resolve before freezing solver/protection/scoring behaviour; P1 means resolve before claiming full coverage of the affected feature. Both remain important.

Please answer with concrete expected outcomes or location lists and identify the validator/brief version. The examples are in the accompanying example pack.

## Q01 (P0)

Must every activity access use one common physical night over its full span, or does the judged model check local location/week packing only?

Return a physical-night assignment for Week 23 A001/A011, a corrected sample, or explicit confirmation of local-only validation. Equal at S16 and unequal at S15 cannot both hold under the full-night interpretation.

Examples: [E07](examples.md#e07).

Response / organiser version: pending.

## Q02 (P0)

Which field defines simultaneous work for a contract's workfront cap?

Explain Week 25 A040/A042 (C007 workfront=1, local nights 3/1, shared b4). State whether shared groups override local indices and supply expected pass/fail.

Examples: [E08](examples.md#e08).

Response / organiser version: pending.

## Q03 (P0)

Please specify the complete protection-expansion algorithm and export scope.

Return exact working/buffer/mirrored/cross-line location lists for E09-E11, including a terminal, a buffer touching an interchange, and direct hub work. Confirm platform inclusion, trigger, propagation limit, capacity treatment, and whether occupancy exports remain working-span-only as E24 shows. Confirm separate line capacities from section 2.2.

Examples: [E09](examples.md#e09), [E10](examples.md#e10), [E11](examples.md#e11), [E24](examples.md#e24).

Response / organiser version: pending.

## Q04 (P0)

Is the sharing exemption local to a group/location, pairwise across a possession, or transitive across linked groups?

Give a verdict for A-B at X and B-C at Y with an A-C protected intersection at Z. Clarify the scope of the PC/C buffer-free prose.

Examples: [E12](examples.md#e12).

Response / organiser version: pending.

## Q05 (P0)

How does the validator determine whether two protected footprints overlap in time?

Specify the comparison key or required night mapping. Give pass/fail for same night, different nights, and only weekly/group information. Do not rely on identical label strings across locations.

Examples: [E13](examples.md#e13).

Response / organiser version: pending.

## Q06 (P1)

Is predecessor_activity_id enforced, and may a successor start in the predecessor's finishing week?

Return E14 outcomes and treatment of cycles, unknown IDs, full-workload completion and same-week sequencing.

Examples: [E14](examples.md#e14).

Response / organiser version: pending.

## Q07 (P1)

What are the exact date-to-week and completion conventions?

Confirm partial-week planned starts, week-end completion, planned versus contractual overrun target, and contract aggregation across activity types. Supply a non-Monday start/non-Sunday deadline example.

Examples: [E06](examples.md#e06), [E15](examples.md#e15), [E21](examples.md#e21), [E22](examples.md#e22).

Response / organiser version: pending.

## Q08 (P1)

Does static supply repeat weekly, and may schedules extend beyond horizon_weeks?

Specify capacity/calendar beyond the horizon, missing-location handling and whether any actual weekday availability is supplied. Confirm extension policy separately for A/B/C.

Examples: [E16](examples.md#e16).

Response / organiser version: pending.

## Q09 (P0)

Which formula and priority policy are authoritative?

Return official sample metrics/objective and formula version: contract days 28 versus activity days 42 versus weighted activity 48.3. Resolve E21's 23.1 versus 14 delay score, E23's scalar versus lexicographic ranking, and the B hard deadline versus prose suggesting P3 slip. Confirm 7 per excess unit and 5 per ECLO unit; the heuristic table compares different batch quantities.

Examples: [E17](examples.md#e17), [E21](examples.md#e21), [E22](examples.md#e22), [E23](examples.md#e23).

Response / organiser version: pending.

## Q10 (P1)

How are ECLO yield, penalties and flags handled for co-sharing activities?

For two activities in one ECLO possession, state penalty 10 or 5 (or another documented rule), each activity's credited workload, and whether mixed 0/1 flags are legal. Define possession identity if used for deduplication.

Examples: [E19](examples.md#e19), [E20](examples.md#e20).

Response / organiser version: pending.

## Q11 (P1)

Which input files belong to A, B and C?

Provide authoritative scenario manifests/checksums or confirm all use the supplied eight files. If C has amended supply, provide that file; also provide B/C sample outputs if available.

Examples: [E25](examples.md#e25).

Response / organiser version: pending.

## Q12 (P0)

Please provide official tooling and the hidden-instance execution contract.

Provide validator/expander package or repository, version/commit, exact commands, sample validator JSON, limits on solve time/memory/file sizes and allowed schema/category/path variations. Confirm how an infeasible or timed-out instance should be reported without weakening hard constraints.

Examples: [E17](examples.md#e17), [E25](examples.md#e25), [E26](examples.md#e26).

Response / organiser version: pending.
