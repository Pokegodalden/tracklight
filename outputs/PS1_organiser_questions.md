# PS1 clarification questions

These questions refer to the supplied 54-activity instance and Scenario A sample. They are drafted for review; no message has been sent to the organisers.

1. **Official tools:** Could you provide the exact validator/expander package, invocation instructions, version, and validator JSON for the supplied sample? The pack references `trackaccess expand` and the judges' validator, but contains no executable implementation.

2. **Common physical nights:** Is the judged model intentionally a local location/week packing abstraction, or must each activity access map to one common physical night across its whole span? In Week 23, A001 and A011 share group b2 at PLAT:BET:S16:EB, but have b2 and b1 respectively at PLAT:BET:S15:EB. How should this translate into nights if different groups at the same location represent separate nights?

3. **Sharing versus workfronts:** C007 has one workfront. In Week 25, A040 and A042 use access_night 3 and 1 but share b4 at SEC:BET:S15_S16:EB. Are these intended to be simultaneous? How should co_share_group and contract-local access_night be reconciled?

4. **Protection:** Exactly which sectors and platforms form the buffer, opposite-bound closure, and Live-only interchange effect? Are buffers compared by week, by group, or by another night mapping? Does a sharing exemption propagate across connected groups or apply only to a pair sharing a particular location? Should the exported occupancy contain work spans only, as the sample does?

5. **Predecessors:** Is predecessor_activity_id mandatory? Must the predecessor's full workload finish in an earlier week, or can a successor start later within the same week? How are cycles and unknown predecessor IDs handled?

6. **Scoring:** Should the supplied sample produce 28 contract-overrun days, 42 activity-overrun days, and 48.3 weighted activity-delay units? Which is used for objective_score and priority_overrun? Please confirm the authoritative formula/version and whether ECLO penalties count activity accesses or shared physical nights.

7. **ECLO and sharing:** Must co-sharing members use the same eclo flag? If several activities share one possession, how is ECLO yield and penalty counted? Does a line's Scenario C window include work whose closure affects the line, even when its work span is on the other line?

8. **Weekly granularity and horizon:** Please confirm the at-most-one-access-per-activity-per-week rule and Sunday completion convention. Can A/C schedules extend beyond horizon_weeks? If so, what supply applies? Are the static LOCATION_SUPPLY values repeated in every week?

9. **Scenario instances:** Do A, B, and C use the same eight input files, or will C receive a separately amended supply file? Only one supply table and an A submission were included.

10. **Hidden-instance contract:** What input variations and solve-time/resource limits will judges use? Can endpoints be platforms, paths be reversed, contracts have multiple activity_type rows, or dates fall outside Monday/Sunday conventions? Which columns and categories are guaranteed?
