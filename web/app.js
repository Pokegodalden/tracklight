"use strict";
const $ = id => document.getElementById(id);
const state = {run: null, runs: [], selected: null, page: "overview", busy: false, comparison: null, targetConflict: null};
const token = document.querySelector('meta[name="ps1-token"]').content;
function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
function option(value, text) { const n = el("option", "", text); n.value = value; return n; }
function human(value) { return String(value || "Not evaluated").replaceAll("_", " ").toLowerCase().replace(/^./, c => c.toUpperCase()); }
function project(a) { return state.run.model.project_types.find(p => p.contract_number === a.contract_number && p.activity_type === a.activity_type); }
function accesses(id) { return (state.run?.tables?.["SCHEDULE_ACCESS.csv"] || []).filter(r => r.activity_id === id); }
function report() { return state.run?.validation?.report; }
function covered(a) { return accesses(a.activity_id).reduce((s,r) => s + (r.eclo ? 1.5 : 1), 0); }
function dateWeek(w) { const d = new Date(state.run.model.calendar.start+"T12:00:00Z"); d.setUTCDate(d.getUTCDate()+(w-1)*7); return d.toLocaleDateString("en-GB", {day:"2-digit",month:"short",timeZone:"UTC"}); }
function locationName(id) { const parts = id.split(":"); return (parts[2] || id).replaceAll("_", " → "); }
function page(name) { state.page = name; for (const p of ["overview","activities","checks","review","replan"]) $(p).hidden = p !== name; document.querySelectorAll(".nav").forEach(b => b.classList.toggle("active", b.dataset.page === name)); }
function errorMessage(error) { let text = error.message || String(error); const items = error.details?.issues || []; if (items.length) text += "\n"+items.slice(0,8).map(i => `${i.file || i.source?.file || i.rule_id || "Input"}${i.line ? ":"+i.line : ""}: ${i.message}`).join("\n"); if (items.length > 8) text += `\n…and ${items.length-8} further findings.`; if (state.run) text += `\nStill viewing: ${state.run.label} (${state.run.id.slice(0,8)}).`; return text; }
async function waitForJob(jobId){
  state.jobId=jobId;$("cancelJob").hidden=false;
  try{for(;;){
    const response=await fetch(`/api/jobs/${jobId}`),data=await response.json();
    if(!response.ok)throw new Error(data.error||"Job status unavailable. Reload to recover the session.");
    if(data.state==="done")return data.result;
    if(["failed","cancelled","timed_out","interrupted","storage_limit"].includes(data.state)){const e=new Error(data.error||human(data.state));e.details=data.details;throw e;}
    $("busy").textContent=`${human(data.state)} · original runs remain available · refresh resumes this job.`;
    await new Promise(resolve=>setTimeout(resolve,750));
  }}finally{state.jobId=null;$("cancelJob").hidden=true;}
}
async function request(path, body) { const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json","X-PS1-Token":token,"X-Request-ID":crypto.randomUUID()},body:JSON.stringify(body)}); const data = await response.json(); if (!response.ok) { const e = new Error(data.error || "Request failed"); e.details = data.details; throw e; } return response.status===202 ? await waitForJob(data.job_id) : data; }
function controls() { $("optimise").disabled=state.busy || !state.run || !!state.run?.planning_context; $("solveScenario").disabled=state.busy; $("solveSeconds").disabled=state.busy; $("generate").disabled = state.busy || !state.run || !!state.run?.planning_context; $("export").disabled = state.busy || !state.run?.tables; for (const id of ["loadSample","openImport","runSelect"]) $(id).disabled = state.busy; planningControls(); replanControls(); }
async function action(message, task) { if (state.busy) return; state.busy = true; $("error").hidden = true; $("busy").textContent = message; $("busy").hidden = false; controls(); try { await task(); } catch (e) { $("error").textContent = errorMessage(e); $("error").hidden = false; } finally { state.busy = false; $("busy").hidden = true; controls(); } }
function load(run) {
  state.run = run; state.comparison=run.replanning?.comparison||run.alternative?.comparison||null; state.targetConflict=null; $("reviewNote").value=""; $("reviewChoice").value="comment"; $("activitySearch").value=""; if (!state.runs.some(r => r.id === run.id)) state.runs.push({id:run.id,label:run.label,scenario:run.scenario});
  try { sessionStorage.setItem("ps1-selected-run",run.id); } catch (_) { /* Session restoration still works without browser storage. */ }
  $("runSelect").replaceChildren(...state.runs.map(r => option(r.id, `${r.label} · ${r.scenario} · ${r.id.slice(0,6)}`))); $("runSelect").value = run.id;
  state.selected = run.model.activities.some(a => a.activity_id === "A001") ? "A001" : run.model.activities[0]?.activity_id;
  $("lineFilter").replaceChildren(...run.model.lines.map(l => option(l.line_code, `${l.line_code} · ${l.line_name}`)));
  $("weekStart").replaceChildren(...Array.from({length:run.model.calendar.weeks}, (_,i) => option(i+1, `Week ${i+1}`)));
  $("weekStart").value = String(Math.min(21, Math.max(1,run.model.calendar.weeks-5)));
  if (run.label !== "Supplied sample") $("weekStart").value = "1";
  $("runKind").textContent = run.optimisation ? "SOLVER RESULT" : run.construction ? "GENERATED DRAFT" : run.tables ? "IMPORTED SCHEDULE" : "INPUTS LOADED";
  $("runTitle").textContent = `${run.label} · Scenario ${run.scenario}`; $("runId").textContent = run.id.slice(0,8);
  $("horizon").textContent = `${run.model.calendar.weeks} weeks · ${run.model.calendar.start} — ${run.model.calendar.inclusive_end}`;
  $("ruleRevision").textContent = run.rule_profile ? `${run.rule_profile.profile_id} · README ${run.rule_profile.source_updates[0].commit.slice(0,7)} · Confirmed: successors start in a strictly later week, including across contracts.` : "";
  $("navCount").textContent = run.model.activities.length;
  const selected=run.model.activities.find(a=>a.activity_id===state.selected), loc=run.model.locations.find(l=>l.location_id===selected?.start_location_id); if(loc){$("lineFilter").value=loc.line_code;$("boundFilter").value=loc.bound;}
  const unfinished = run.construction?.unfinished || [];
  $("unfinished").hidden = !unfinished.length;
  $("unfinished").textContent = !unfinished.length ? "" : `Partial draft · ${unfinished.length} activities unfinished · ${run.construction?.remaining_scaled_units/2} units unplaced. The heuristic did not place all work; this is not proof of infeasibility. Inspect an activity for the reasons.`;
  $("footerStatus").textContent = `${run.model.activities.length} activities visible · Sources preserved · Review export only`;
  const weeks = report()?.physical_night_diagnostic?.weeks || [];
  $("conflictWeek").replaceChildren(...weeks.map(w => option(w.week, `Week ${w.week}${w.status === "INCONSISTENT_UNDER_ASSUMPTIONS" ? " · review" : ""}`)));
  $("conflictWeek").value = String(weeks.find(w=>w.week===23)?.week || weeks.find(w=>w.conflicts.length)?.week || weeks[0]?.week || "");
  renderMetrics(); renderTimeline(); renderDetails(); renderActivities(); renderChecks(); renderSolver(); renderPlanning(); renderReplan(); controls();
}
function renderMetrics() {
  const run = state.run, r = report(), acts = run.model.activities;
  const required = acts.reduce((s,a)=>s+a.workload_units_scaled/2,0), supplied = acts.reduce((s,a)=>s+Math.min(covered(a),a.workload_units_scaled/2),0);
  const violations = r?.findings.filter(f=>f.severity==="violation" || f.severity==="error").length;
  const conflictWeeks = r?.physical_night_diagnostic?.weeks?.filter(w=>w.status==="INCONSISTENT_UNDER_ASSUMPTIONS").length;
  const cards = [["ACTIVITIES", acts.length, `${new Set(acts.map(a=>a.contract_number)).size} contracts · all requests visible`, ""],
    ["WORK ALLOCATED", `${supplied} / ${required}`, "Standard-equivalent units covered", "teal-text"],
    ["WEEKLY VIOLATIONS", violations ?? "—", r ? "Under the provisional rule profile" : "Load or generate a schedule to check", ""],
    ["WEEKS TO REVIEW", conflictWeeks ?? "—", "Conditional full-night diagnostic", "purple-text"]];
  $("metrics").replaceChildren(...cards.map(([label,value,note,cls])=>{ const card = el("article","metric"); card.append(el("div","metric-label",label),el("div",`metric-value ${cls}`,value),el("div","metric-note",note)); return card; }));
}
function selectActivity(id, week) { state.selected = id; page("overview"); const a = state.run.model.activities.find(a=>a.activity_id===id); if (a) { const loc=state.run.model.locations.find(l=>l.location_id===a.start_location_id); if(loc){$("lineFilter").value=loc.line_code;$("boundFilter").value=loc.bound;} } if (Number.isFinite(week)) $("weekStart").value = String(Math.min(state.run.model.calendar.weeks, Math.max(1, week-2))); renderTimeline(); renderDetails(); }
function renderTimeline() {
  if (!state.run) return;
  const start = Number($("weekStart").value), horizon = state.run.model.calendar.weeks;
  const weeks = Array.from({length:Math.min(6,horizon-start+1)},(_,i)=>start+i);
  const locations = state.run.model.locations.filter(l=>l.line_code===$("lineFilter").value && l.bound===$("boundFilter").value && ($("kindFilter").value==="all" || l.location_kind===$("kindFilter").value));
  const occupancy = state.run.tables?.["SCHEDULE_OCCUPANCY.csv"] || [];
  const byCell = new Map(); for (const o of occupancy) { const key = `${o.location_id}|${o.week}`; if (!byCell.has(key)) byCell.set(key, []); byCell.get(key).push(o.activity_id); }
  const diag = report()?.physical_night_diagnostic?.weeks || [];
  const conditional = new Set(); for (const w of diag) for (const c of w.conflicts || []) for (const a of c.activities || []) conditional.add(`${a}|${w.week}`);
  const table = $("timeline"); table.setAttribute("aria-label","Activity accesses by week and location"); table.replaceChildren(); const head = el("thead"), hr = el("tr"); hr.append(el("th","","TRACK LOCATION")); for (const w of weeks) { const th=el("th","",`W${String(w).padStart(2,"0")}`); th.append(el("small","",dateWeek(w))); hr.append(th); } head.append(hr); table.append(head);
  const body=el("tbody"); for (const loc of locations) { const tr=el("tr"), label=el("th","",locationName(loc.location_id)); label.scope="row"; label.append(el("small","",`${loc.bound} · ${loc.supply_capacity} default weekly slots`)); tr.append(label);
    for (const w of weeks) { const td=el("td"), jobs=[...new Set(byCell.get(`${loc.location_id}|${w}`)||[])]; const override=state.run.planning_context?.weekly_supply.find(r=>r.location_id===loc.location_id&&r.week===w);if(override)td.append(el("small","supply-override",`Supply: ${override.capacity}`)); if (jobs.length) { const b=el("button","cell",`${jobs[0]}${jobs.length>1 ? ` +${jobs.length-1}` : ""}`); b.title=`Week ${w}, ${loc.location_id}: ${jobs.join(", ")}`; b.setAttribute("aria-label",b.title); if(jobs.some(a=>conditional.has(`${a}|${w}`)))b.classList.add("conditional"); if(report()?.findings.some(f=>f.severity==="violation" && f.week===w && (f.location_id===loc.location_id || jobs.some(a=>f.activities.includes(a))))) b.classList.add("violation"); if(jobs.includes(state.selected))b.classList.add("selected"); b.addEventListener("click",()=>{state.selected=jobs[0];renderTimeline();renderDetails(jobs);}); td.append(b); } else td.append(el("span","empty-cell","·")); tr.append(td); } body.append(tr); } if (!locations.length) { const tr=el("tr"),td=el("td","empty","No locations match these filters.");td.colSpan=weeks.length+1;tr.append(td);body.append(tr); } table.append(body);
  $("prevWeeks").disabled = start===1; $("nextWeeks").disabled = start+6>horizon;
}
function detailSection(title, content) { const section=el("section","detail-section");section.append(el("h3","",title),content);return section; }
function renderDetails(cellJobs) {
  const box=$("details");box.replaceChildren(); const a=state.run?.model.activities.find(a=>a.activity_id===state.selected); if(!a){$("detailTitle").textContent="Select an activity";box.append(el("p","empty","Choose an activity to inspect its requirements."));return;}
  $("detailTitle").textContent=a.activity_id; if(cellJobs?.length>1){const label=el("label","","Activities in this cell"),select=el("select");select.append(...cellJobs.map(id=>option(id,id)));select.value=a.activity_id;select.addEventListener("change",()=>{state.selected=select.value;renderDetails(cellJobs);renderTimeline();});label.append(select);box.append(label);}
  const badges=el("div","detail-type");badges.append(el("span","tag",a.activity_type),el("span","tag muted",a.access_type),el("span","tag muted",a.nature_of_works));box.append(badges);
  const p=project(a), dl=el("dl","detail-grid");for(const [label,value] of [["Contract",a.contract_number],["Priority",`${p.contract_priority} / activity ${a.activity_priority}`],["Work allocated",`${covered(a)} / ${a.workload_units_scaled/2} units`],["Planned start",a.planned_start_date],["Target finish",p.planned_completion_date],["Predecessor",a.predecessor_activity_id||"None"]]) {const d=el("div");d.append(el("dt","",label),el("dd","",value));dl.append(d);}box.append(dl);
  if(a.predecessor_activity_id) box.append(detailSection("Dependency rule · confirmed",el("p","",`Must start in a strictly later week than ${a.predecessor_activity_id}’s last scheduled access. Cross-contract links are allowed; same-week sequencing is forbidden (README §2.4, rule 3).`)));
  const pills=el("div","week-pills"),rows=accesses(a.activity_id).sort((a,b)=>a.week-b.week); for(const r of rows)pills.append(el("span","week-pill",`W${r.week}${r.eclo ? " · ECLO" : ""}`));if(!rows.length)pills.append(el("p","empty","No accesses allocated."));box.append(detailSection("Allocated weeks",pills));
  const span=el("div","span-list");for(const l of a.working_span.location_ids)span.append(el("div","",l));box.append(detailSection("Working locations",span));
  const why=el("p","",(!state.run.tables ? "No schedule was produced for these inputs. Inspect the solver outcome, if present, for the reason; no allocations have been chosen." : state.run.optimisation?.selected_from === "incumbent" ? "The previous complete allocation was retained because this search found no new solution. See the solver report for the remaining bound and model assumptions." : state.run.optimisation ? "Chosen jointly by the constraint solver to minimise the provisional scenario score. Workload, precedence, sharing and resource rules are enforced; full protection is still unverified. See the solver report for bounds and assumptions." : state.run.construction ? "The baseline tries activities by priority and target date, using the first available week after release and predecessor completion. Each access has its own group; the baseline does not try sharing." : "These are supplied allocations. They are preserved for inspection; their original scheduling rationale was not supplied."));box.append(detailSection("Why this allocation?",why));
  const unfinished=state.run.construction?.unfinished.find(u=>u.activity_id===a.activity_id); if(unfinished){const reasons=el("div");reasons.append(el("p","",`${unfinished.remaining_scaled_units/2} units remain unplaced.`));for(const [code,count] of Object.entries(unfinished.deferred_weeks_by_reason))reasons.append(el("p","",`${human(code)}: ${count} weeks`));box.append(detailSection("Unfinished work",reasons));}
  if(state.run.planning_context){const c=state.run.planning_context;box.append(el("p","hint",`Completed through week ${c.completed_through_week} · ${c.locked_activity_ids.includes(a.activity_id)?"Allocation locked":"Future allocation not explicitly locked"}.`));}
  renderPlanningDetails(box,a);
}
function renderActivities() { if(!state.run)return;const q=$("activitySearch").value.toLowerCase();const rows=[];for(const a of state.run.model.activities.filter(a=>`${a.activity_id} ${a.contract_number} ${a.activity_type}`.toLowerCase().includes(q))){const tr=el("tr"),work=covered(a),required=a.workload_units_scaled/2;tr.append(el("td","",a.activity_id));const contract=el("td","",a.contract_number);contract.append(el("small","",a.activity_type));tr.append(contract,el("td","",required),el("td","",work),el("td","",a.planned_start_date));const status=el("td"),tag=el("span",`progress ${work<required ? "partial" : ""}`,work>=required ? "Work allocated" : work ? "Partly allocated" : "Not allocated");status.append(tag);tr.append(status);const cell=el("td"),b=el("button","inspect","Inspect →");b.setAttribute("aria-label",`Inspect ${a.activity_id}`);b.addEventListener("click",()=>selectActivity(a.activity_id,accesses(a.activity_id)[0]?.week));cell.append(b);tr.append(cell);rows.push(tr);}if(!rows.length){const tr=el("tr"),td=el("td","empty","No activities match your search.");td.colSpan=7;tr.append(td);rows.push(tr);}$("activityRows").replaceChildren(...rows);}
function inspectButtons(card, ids, week) { for(const id of [...new Set(ids||[])].slice(0,6)){const b=el("button","inspect",`Inspect ${id}`);b.addEventListener("click",()=>selectActivity(id,week));card.append(b);} }
function renderChecks() {
  const r=report();$("weeklyFindings").replaceChildren();$("ruleTable").replaceChildren();
  if(!r){$("weeklyStatus").textContent="NOT RUN";$("weeklyFindings").append(el("p","empty","Import a schedule or create a baseline to run the checks."));renderNight();return;}
  $("weeklyStatus").textContent=human(r.status);const violations=r.findings.filter(f=>f.severity==="violation"||f.severity==="error");if(!violations.length)$("weeklyFindings").append(el("p","empty","No implemented weekly violations. The unresolved checks below still prevent full validation."));
  for(const f of r.findings){const card=el("article",`finding ${f.severity}`);card.append(el("h3","",`${f.rule_id||"Input"} · ${human(f.code)}`),el("p","",f.message));if(f.week||f.location_id)card.append(el("small","",[f.week?`Week ${f.week}`:"",f.location_id].filter(Boolean).join(" · ")));if(f.observed!==null||f.expected!==null)card.append(el("small","",`Observed: ${JSON.stringify(f.observed)} · Expected: ${JSON.stringify(f.expected)}`));inspectButtons(card,f.activities,f.week);addAlternativeLink(card,"weekly",f,f.week);$("weeklyFindings").append(card);}
  const grid=el("div","rule-grid");for(const [rule,status] of Object.entries(r.rule_checks)){const item=el("div");item.append(el("b","",rule),el("div","",human(status)));grid.append(item);}$("ruleTable").append(grid,el("p","evidence",`Input identity: ${state.run.input_identity}\nRun: ${state.run.id}\nFull feasibility established: no · Official validation: not run`));renderNight();
}
function renderNight(){const container=$("nightFindings");container.replaceChildren();const diag=report()?.physical_night_diagnostic;if(!diag){container.append(el("p","empty","No diagnostic yet."));return;}const week=diag.weeks?.find(w=>w.week===Number($("conflictWeek").value));container.append(el("p","empty",`${human(diag.status)}. Abstract nights are not dated access permissions; full protection remains unverified.`));if(!week){container.append(el("p","empty","There are no evaluated occupied weeks to show."));return;}if(!week.conflicts.length)container.append(el("p","empty",week.status==="ASSIGNED" ? `Week ${week.week}: ${week.activity_count} activities have an assignment for the modelled relations only.` : human(week.status)));
  for(const c of week.conflicts){const card=el("article","finding conditional");card.append(el("h3","",human(c.kind)));let text="";if(c.kind==="equal_and_different_night"){const why=c.equality_path?.map(e=>e.location_id||`${e.contract}, local index ${e.access_night}`).join(" → ");text=`${c.activities.join(" and ")} are linked to the same night through ${why}. They must also use different nights because of ${c.inequality.location_id||c.inequality.contract||human(c.inequality.basis)}.`;}else if(c.kind==="simultaneous_workfront_excess")text=`${c.contract} needs ${c.observed} simultaneous workfronts in this linked group, but has ${c.limit}.`;else text=c.explanation||"These relations cannot fit within the selected abstract night limit.";card.append(el("p","",text),el("small","","Conditional finding · not an official benchmark verdict"));inspectButtons(card,c.activities,week.week);addAlternativeLink(card,"night",c,week.week);container.append(card);}
}
document.querySelectorAll(".nav").forEach(b=>b.addEventListener("click",()=>page(b.dataset.page)));$("viewChecks").addEventListener("click",()=>page("checks"));$("loadSample").addEventListener("click",()=>action("Loading and checking the supplied sample…",async()=>load(await request("/api/sample",{}))));$("runSelect").addEventListener("change",()=>action("Loading the saved run…",async()=>load(await request("/api/run",{id:$("runSelect").value}))));$("generate").addEventListener("click",()=>action("Constructing Scenario A and checking the resulting draft…",async()=>{load(await request("/api/generate",{id:state.run.id}));page("overview");}));
for(const id of ["lineFilter","boundFilter","kindFilter","weekStart"])$(id).addEventListener("change",renderTimeline);$("prevWeeks").addEventListener("click",()=>{$("weekStart").value=String(Math.max(1,Number($("weekStart").value)-6));renderTimeline();});$("nextWeeks").addEventListener("click",()=>{$("weekStart").value=String(Math.min(state.run.model.calendar.weeks,Number($("weekStart").value)+6));renderTimeline();});$("activitySearch").addEventListener("input",renderActivities);$("conflictWeek").addEventListener("change",renderNight);
$("openImport").addEventListener("click",()=>$("importDialog").showModal());$("cancelImport").addEventListener("click",()=>$("importDialog").close());
async function encoded(file){const raw=new Uint8Array(await file.arrayBuffer());if(raw.length>512*1024)throw new Error(`${file.name} exceeds 512 KiB.`);let data="";for(let offset=0;offset<raw.length;offset+=16384)data+=String.fromCharCode(...raw.subarray(offset,offset+16384));return {name:file.name,data:btoa(data)};}
$("importForm").addEventListener("submit",event=>{event.preventDefault();const inputs=[...$("inputFiles").files],schedule=[...$("scheduleFiles").files],scenario=$("scenario").value;$("importDialog").close();action("Importing your files and checking the new run…",async()=>{if(inputs.length!==8||(schedule.length!==0&&schedule.length!==3))throw new Error("Select exactly eight input CSVs and either zero or three schedule CSVs.");const files=await Promise.all([...inputs,...schedule].map(encoded));load(await request("/api/import",{files,scenario}));page("overview");});});
$("export").addEventListener("click",()=>action("Re-importing the export and comparing its validation report…",async()=>{const response=await fetch(`/api/export/${state.run.id}`);if(!response.ok){const result=await response.json();throw new Error(result.error);}const blob=await response.blob(),url=URL.createObjectURL(blob),link=el("a");link.href=url;link.download=`ps1-review-${state.run.id.slice(0,8)}.zip`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);$("footerStatus").textContent="Review pack exported · round-trip checked · not an official submission.";}));
action("Restoring this server session…",async()=>{
  const health=await (await fetch("/api/health")).json();
  if(health.scope==="hosted_step10"){
    const pending=await (await fetch("/api/jobs/current")).json();
    if(pending){try{const result=await waitForJob(pending.job_id);if(result?.id)try{sessionStorage.setItem("ps1-selected-run",result.id);}catch(_){} }catch(e){$("error").textContent=errorMessage(e);$("error").hidden=false;}}
  }
  state.runs = await request("/api/runs",{});
  let selected; try { selected=sessionStorage.getItem("ps1-selected-run"); } catch (_) {}
  const saved=state.runs.find(r=>r.id===selected)||state.runs.at(-1);
  load(await request(saved ? "/api/run" : "/api/sample",saved ? {id:saved.id} : {}));
});

function renderSolver(){
  const meta=state.run?.optimisation, box=$("solverResult");box.replaceChildren();box.hidden=!meta;$("solverReport").hidden=!meta;if(!meta)return;
  const labels={OPTIMAL_MODEL_UNVERIFIED:"Optimal for the disclosed model · protection unverified",FEASIBLE_MODEL_UNVERIFIED:"Complete model solution · optimality not proved",RETAINED_INCUMBENT_UNVERIFIED:"Previous complete model solution retained",INFEASIBLE_MODEL:"No solution exists within this model",NO_SOLUTION_WITHIN_LIMIT:"No solution found within the time limit"};
  box.append(el("h3","",labels[meta.status]||human(meta.status)));
  if(meta.objective_tenths!==null){const m=meta.metrics;box.append(el("p","",`Provisional score ${(meta.objective_tenths/10).toFixed(1)} · model lower bound ${(meta.best_bound_tenths/10).toFixed(1)} · gap ${(100*meta.relative_gap).toFixed(1)}%`));box.append(el("p","",`Activity delay: ${m.activity_delay_days} days (${(m.activity_weighted_delay_tenths/10).toFixed(1)} weighted) · excess location/week slots: ${m.excess_location_week_units} · ECLO accesses: ${m.eclo_activity_accesses}`));}
  else{box.append(el("p","","All activities remain visible. No partial schedule is substituted. This result does not establish official PS1 infeasibility."));for(const item of meta.infeasibility_evidence||[])box.append(el("p","",`${item.activity_id||"Model"}: ${item.reason}`));}
  box.append(el("p","",`${(meta.elapsed_seconds||0).toFixed(2)} seconds total · search limit ${meta.settings.time_limit_seconds}s · ${meta.settings.workers} workers`));
  const details=el("details"),summary=el("summary","","Model scope and assumptions");details.append(summary);for(const text of meta.assumptions)details.append(el("p","",text));box.append(details);
}
$("optimise").addEventListener("click",()=>{const scenario=$("solveScenario").value,seconds=Number($("solveSeconds").value);action(`Optimising Scenario ${scenario}… search is limited to ${seconds}s, followed by independent validation.`,async()=>{load(await request("/api/optimise",{id:state.run.id,scenario,seconds}));page("overview");});});
$("solverReport").addEventListener("click",()=>{const payload={input_identity:state.run.input_identity,rule_profile:state.run.rule_profile,optimisation:state.run.optimisation};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}));const link=el("a");link.href=url;link.download=`ps1-solver-${state.run.scenario}-${state.run.id.slice(0,8)}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);});

function planningControls() {
  $("comparePlans").disabled=state.busy||!state.run?.tables||!$("compareRun").value;
  $("findAlternative").disabled=state.busy||!state.run?.tables||!state.targetConflict||!!state.run?.planning_context;
  for(const id of ["compareRun","alternativeConflict","alternativeSeconds"]) $(id).disabled=state.busy;
  $("reviewFields").disabled=state.busy||!state.run?.tables;
}
function addAlternativeLink(card, kind, evidence, week) {
  const item=state.run.planning?.conflicts.find(c=>c.kind===kind && c.week===week && JSON.stringify(c.evidence)===JSON.stringify(evidence));
  if(!item)return;
  if(!item.actionable){card.append(el("p","hint","Clarification required · a schedule change cannot certify this unresolved finding."));return;}
  const b=el("button","inspect alternative-link","Review alternatives →");
  b.addEventListener("click",()=>{state.targetConflict=item.id;page("review");renderPlanning();});card.append(b);
}
function renderPlanningDetails(box,a) {
  const context=state.run.planning?.activities[a.activity_id];
  const partners=el("div","sharing-rows");
  partners.append(el("p","","Reported local sharing; partners can differ by location. Check findings before relying on these groups."));
  if(context?.sharing.length){const details=el("details"),heading=el("summary","",`${context.sharing.length} location/week sharing records`);details.append(heading);for(const s of context.sharing)details.append(el("p","",`Week ${s.week} · ${s.location_id} · with ${s.partners.join(", ")}`));partners.append(details);}
  else partners.append(el("p","empty","No reported local sharing partners."));
  box.append(detailSection("Sharing partners",partners));
  const protection=el("div");protection.append(el("p","",context?.protection_note||"Complete protection remains unverified."));
  if(context?.known_live_mirror_core.length){const details=el("details"),title=el("summary","","Known Live opposite-bound working core");details.append(title);for(const l of context.known_live_mirror_core)details.append(el("p","",l));protection.append(details);}
  protection.append(el("p","hint","This is not a confirmed full protection footprint or a track-entry authorisation."));
  box.append(detailSection("Protection · unverified",protection));
}
function renderPlanning() {
  if(!state.run)return;
  const selected=$("compareRun").value;
  const others=state.runs.filter(r=>r.id!==state.run.id);
  $("compareRun").replaceChildren(option("","Choose another run"),...others.map(r=>option(r.id,`${r.label} · ${r.scenario} · ${r.id.slice(0,6)}`)));
  $("compareRun").value=others.some(r=>r.id===selected)?selected:(state.run.parent_id||"");
  const conflicts=(state.run.planning?.conflicts||[]).filter(c=>c.actionable);
  $("alternativeConflict").replaceChildren(option("",conflicts.length?"Choose a finding from this run":"No implemented conflict to repair"),...conflicts.map(c=>option(c.id,`${c.week?`W${c.week} · `:""}${c.title} · ${c.activities.slice(0,3).join(", ")||c.rule}`)));
  $("alternativeConflict").value=state.targetConflict||"";
  renderAlternativeTarget();renderComparison();renderReview();planningControls();
}
function renderAlternativeTarget() {
  const box=$("alternativeTarget");box.replaceChildren();
  const c=state.run.planning.conflicts.find(c=>c.id===state.targetConflict);
  if(c){box.append(el("h3","",c.title),el("p","",c.explanation),el("p","",c.proposal));if(c.week)box.append(el("p","hint",`Week ${c.week} · ${c.rule} · ${c.activities.join(", ")}`));}
  else box.append(el("p","","Select an implemented weekly finding, conditional night issue or disclosed model-policy finding. Unresolved protection rules still require clarification."));
  const outcome=$("alternativeOutcome"),alt=state.run.alternative;outcome.replaceChildren();
  if(alt){outcome.append(el("p","comparison-warning",alt.status==="CHECKED_MODEL_ALTERNATIVE"?"A complete replacement passed the implemented weekly checks and conditional night assignment. Full protection remains unverified.":"No checked replacement was found. The original run remains available; see the solver outcome for the search result."));outcome.append(el("p","hint",`Requested for ${alt.target.week?`Week ${alt.target.week} · `:""}${alt.target.title}. ${alt.strategy}`));}
}
function metricText(value){return value===null||value===undefined?"Not available":String(value);}
function deltaText(value){return value===null||value===undefined?"—":`${value>0?"+":""}${value}`;}
function weeksText(plan){return plan?.accesses?.length?plan.accesses.map(r=>`W${r.week}${r.eclo?" ECLO":""}`).join(", "):"No accesses";}
function viewActivityRun(runId,id,week){action("Opening the compared schedule…",async()=>{if(state.run.id!==runId)load(await request("/api/run",{id:runId}));selectActivity(id,week);});}
function renderComparison() {
  const box=$("comparisonResult"),c=state.comparison;box.replaceChildren();
  if(!c){box.append(el("p","empty","Compare two saved schedules to see completion, delay, ECLO, capacity use and changed allocations."));return;}
  box.append(el("p","comparison-warning",c.comparison_note));
  box.append(el("p","evidence",`Base: ${c.base_run_id} · Scenario ${c.base_snapshot.scenario}\nCandidate: ${c.candidate_run_id} · Scenario ${c.candidate_snapshot.scenario}\nIdentical input bytes: ${c.same_inputs ? "yes" : "no — declared disruption"} · Same planning constraints: ${c.same_planning_context !== false ? "yes" : "no"} · Same rules and implementation: ${c.same_rules && c.same_implementation ? "yes" : "no"} · ${c.changed_activity_count} activities have changed allocations.`));
  const status=el("div","comparison-status");for(const [name,m] of [["Base",c.before],["Candidate",c.after]])status.append(el("p","",`${name}: ${human(m.status)} · ${metricText(m.complete_activities)}/${m.required_activities} activities complete · night check: ${human(m.night_status)}${m.c_window_check ? ` · Conservative C window: ${m.c_window_check.passed ? "pass" : "requires review"}` : ""}`));box.append(status);
  const table=el("table","comparison-table"),head=el("thead"),h=el("tr");for(const t of ["Measure","Base","Candidate","Change"])h.append(el("th","",t));head.append(h);table.append(head);
  const body=el("tbody");for(const [key,label] of [["covered_units","Work covered (standard units)"],["complete_activities","Activities complete"],["completion_date","Final completion date"],["activity_delay_days","Activity delay days"],["contract_delay_days","Contract delay days"],["weighted_delay","Weighted activity delay"],["eclo_accesses","ECLO activity accesses"],["excess_slots","Excess location/week slots"],["weekly_violations","Implemented weekly violations"],["night_conflict_weeks","Conditional conflict weeks"],["score","Provisional scenario score"]]){const tr=el("tr");tr.append(el("th","",label),el("td","",metricText(c.before[key])),el("td","",metricText(c.after[key])),el("td","",key==="score"&&!c.scores_comparable?"Changed requirements / policies":deltaText(c.deltas[key])));body.append(tr);}table.append(body);const scroll=el("div","table-scroll");scroll.append(table);box.append(scroll);
  const changes=el("details");changes.append(el("summary","",`Inspect ${c.changed_activity_count} changed activities`));
  const changeTable=el("table","comparison-table changes-table"),ch=el("tr"),thead=el("thead"),tbody=el("tbody");for(const text of ["Activity","Base accesses","Candidate accesses","What changed"])ch.append(el("th","",text));thead.append(ch);changeTable.append(thead);
  for(const r of c.changes){const tr=el("tr");tr.append(el("th","",r.activity_id));for(const [key,runId,completion] of [["before",c.base_run_id,r.before_completion],["after",c.candidate_run_id,r.after_completion]]){const td=el("td","",weeksText(r[key]));td.append(el("small","",`Completion: ${metricText(completion)}`));const b=el("button","inspect",key==="before"?"Inspect base":"Inspect candidate");b.addEventListener("click",()=>viewActivityRun(runId,r.activity_id,r[key]?.accesses[0]?.week));td.append(b);tr.append(td);}tr.append(el("td","",r.changed.map(k=>({accesses:"Weeks / ECLO / access count",sharing:"Location sharing partners or coverage",same_project_night:"Same-project night relationships"})[k]).join("; ")));tbody.append(tr);}changeTable.append(tbody);const changesScroll=el("div","table-scroll");changesScroll.append(changeTable);changes.append(changesScroll);box.append(changes);
  const evidence=el("details");evidence.append(el("summary","","Exact versions and comparison evidence"),el("p","evidence",`Base version: ${c.base_snapshot.version}\nCandidate version: ${c.candidate_snapshot.version}\nInput identity: ${c.base_snapshot.input_data_sha256}\nRule profile: ${c.base_snapshot.rule_profile.profile_id} · ${c.base_snapshot.rule_profile.profile_sha256}`));box.append(evidence,el("p","hint",c.scope));
  const controls=el("div","planning-actions");for(const [name,id] of [["Open base run",c.base_run_id],["Open candidate run",c.candidate_run_id]]){const b=el("button","button secondary",name);b.disabled=id===state.run.id;b.addEventListener("click",()=>action("Loading the selected plan…",async()=>{load(await request("/api/run",{id}));page("review");}));controls.append(b);}const download=el("button","button secondary","Download comparison");download.addEventListener("click",()=>downloadJson(c,`ps1-comparison-${c.base_run_id.slice(0,6)}-${c.candidate_run_id.slice(0,6)}.json`));controls.append(download);box.append(controls);
}
function renderReview() {
  const run=state.run,review=run.planner_review;
  $("reviewDecision").textContent=review.current_decision?human(review.current_decision):"No decision";
  $("reviewVersion").textContent=`Reviewing: ${run.label} · ${run.scenario} · ${run.id}\nExact version: ${run.schedule_snapshot.version}\n${review.scope}`;
  $("reviewChoice").querySelector('option[value="recommend_for_planning"]').disabled=!run.planning.summary.checked_model_plan;
  const history=$("reviewHistory");history.replaceChildren();
  if(!review.records.length)history.append(el("p","empty","No comments or decisions recorded for this exact schedule version."));
  for(const event of [...review.records].reverse()){const card=el("article","review-record");card.append(el("h3","",`${human(event.decision)} · ${event.reviewer}`),el("p","",event.note),el("small","",`${event.recorded_at} · version ${event.snapshot_version}`));history.append(card);}
}
function downloadJson(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"})),a=el("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
$("alternativeConflict").addEventListener("change",()=>{state.targetConflict=$("alternativeConflict").value||null;renderAlternativeTarget();planningControls();});
$("compareRun").addEventListener("change",planningControls);
$("comparePlans").addEventListener("click",()=>action("Comparing exact schedule versions…",async()=>{state.comparison=await request("/api/compare",{base_id:state.run.id,candidate_id:$("compareRun").value});renderComparison();}));
$("findAlternative").addEventListener("click",()=>action("Searching for a complete checked replacement; other allocations may change…",async()=>{load(await request("/api/alternative",{id:state.run.id,version:state.run.schedule_snapshot.version,conflict_id:state.targetConflict,seconds:Number($("alternativeSeconds").value)}));page("review");}));
$("reviewForm").addEventListener("submit",event=>{event.preventDefault();const payload={id:state.run.id,version:state.run.schedule_snapshot.version,reviewer:$("reviewerName").value,decision:$("reviewChoice").value,note:$("reviewNote").value,request_id:crypto.randomUUID()};action("Recording review against this exact schedule version…",async()=>{const comparison=state.comparison;load(await request("/api/review",payload));state.comparison=comparison;renderComparison();page("review");$("footerStatus").textContent="Planner review recorded · export the review pack to retain it · no track-entry authorisation.";});});

function replanControls(){
  $("replanFields").disabled=state.busy||!state.run?.planning?.summary.checked_model_plan;
  $("rollback").disabled=state.busy||!state.run?.replanning;
  $("reviewRevision").disabled=state.busy||!state.run?.replanning?.comparison;
  $("downloadReplan").disabled=state.busy||!state.run?.replanning;
}
function disruptionFields(){for(const [type,id] of [["workload","workloadFields"],["weekly_supply","supplyFields"],["urgent_activity","urgentFields"]])$(id).hidden=$("disruptionType").value!==type;}
function urgentTemplate(){
  const a=state.run.model.activities.find(a=>a.activity_id===$("urgentTemplate").value);if(!a)return;
  const data={};for(const k of ["activity_id","contract_number","activity_type","start_location_id","end_location_id","total_accesses","planned_start_date","predecessor_activity_id","activity_priority"])data[k]=a[k];
  data.activity_id="URGENT01";data.total_accesses=1;data.predecessor_activity_id="";
  const start=new Date(state.run.model.calendar.start+"T12:00:00Z");start.setUTCDate(start.getUTCDate()+7*Number($("completedWeek").value));data.planned_start_date=start.toISOString().slice(0,10);
  $("urgentDefinition").value=JSON.stringify(data,null,2);
}
function renderReplan(){
  const r=state.run,c=r.planning_context||{};
  $("replanEligibility").textContent=r.planning.summary.checked_model_plan?"This version passes implemented checks. Original inputs and schedule will be preserved.":"Start from a complete checked model plan: optimise or repair this draft first. A failed revision can return to its preserved parent.";
  $("completedWeek").value=c.completed_through_week||0;$("completedWeek").min=c.completed_through_week||0;$("completedWeek").max=r.model.calendar.weeks;
  $("lockActivities").value=(c.locked_activity_ids||[]).join(", ");
  for(const id of ["workloadActivity","urgentTemplate"])$(id).replaceChildren(...r.model.activities.map(a=>option(a.activity_id,`${a.activity_id} · ${a.contract_number} · ${a.activity_type}`)));
  $("supplyLocation").replaceChildren(...r.model.locations.map(l=>option(l.location_id,l.location_id)));$("supplyWeek").max=r.model.calendar.weeks;$("supplyWeek").value=Math.min(r.model.calendar.weeks,Number($("completedWeek").value)+1);
  urgentTemplate();disruptionFields();
  const box=$("replanOutcome");box.replaceChildren();
  if(!r.replanning){box.append(el("p","empty","No disruption on this run. Propose a change to create a separate revision."));return;}
  const rec=r.replanning,meta=r.optimisation;
  box.append(el("h3","",human(rec.status)),el("p","",`Parent: ${rec.parent_run_id} · completed through week ${c.completed_through_week} · locked activities: ${c.locked_activity_ids.join(", ")||"none"}`));
  box.append(el("p","",`Solver: ${human(meta.status)}${meta.changed_activity_count!==undefined ? ` · ${meta.changed_activity_count} activities changed` : ""}. ${meta.churn_optimality_proven?"Scenario score and churn are optimal for the disclosed model.":"Minimum churn is not proven."}`));
  if(rec.lock_audit)box.append(el("p","",`Independent completed-work and lock check: ${rec.lock_audit.passed?"pass":"failed"}.`));
  if(rec.lock_diagnostic)box.append(el("p","comparison-warning",rec.lock_diagnostic.explanation+" Actual locks remain in force. Return to the parent to submit a different proposal."));
  if(!r.tables)for(const f of meta.infeasibility_evidence||[])box.append(el("p","",`${f.activity_id||"Model"}: ${f.reason}`));
  const details=el("details");details.append(el("summary","","Exact disruption proposal and cumulative constraints"),el("pre","",JSON.stringify({proposal:rec.proposal,context:c},null,2)));box.append(details,el("p","hint",rec.scope));
}
$("disruptionType").addEventListener("change",disruptionFields);
$("urgentTemplate").addEventListener("change",urgentTemplate);
$("replanForm").addEventListener("submit",event=>{
  event.preventDefault();action("Replanning with completed work and locks preserved…",async()=>{
    const type=$("disruptionType").value,changes=[];
    if(type==="workload")changes.push({type,activity_id:$("workloadActivity").value,additional_units:Number($("extraUnits").value)});
    if(type==="weekly_supply")changes.push({type,location_id:$("supplyLocation").value,week:Number($("supplyWeek").value),capacity:Number($("supplyCapacity").value)});
    if(type==="urgent_activity")changes.push({type,activity:JSON.parse($("urgentDefinition").value)});
    const proposal={completed_through_week:Number($("completedWeek").value),locked_activity_ids:$("lockActivities").value.split(",").map(s=>s.trim()).filter(Boolean),changes};
    load(await request("/api/replan",{id:state.run.id,version:state.run.schedule_snapshot.version,proposal,seconds:Number($("replanSeconds").value)}));page("replan");
  });
});
$("reviewRevision").addEventListener("click",()=>{state.comparison=state.run.replanning.comparison;renderComparison();page("review");});
$("rollback").addEventListener("click",()=>action("Returning to the preserved parent without deleting the revision…",async()=>{load(await request("/api/rollback",{id:state.run.id,version:state.run.schedule_snapshot.version}));page("replan");$("footerStatus").textContent="Original version restored for viewing · revision retained · original requirements apply.";}));
$("downloadReplan").addEventListener("click",()=>downloadJson({snapshot:state.run.schedule_snapshot,replanning:state.run.replanning,optimisation:state.run.optimisation},`ps1-disruption-${state.run.id.slice(0,8)}.json`));

$("cancelJob").addEventListener("click",async()=>{if(!state.jobId)return;try{await request("/api/jobs/cancel",{job_id:state.jobId});}catch(e){$("error").textContent=errorMessage(e);$("error").hidden=false;}});
