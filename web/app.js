// @ts-check
/// <reference path="./contracts.d.ts" />

/** @type {View | null} */
let state = null;
/** @type {AthleteSummary[]} */
let athletes = [];
let selected = new URLSearchParams(location.search).get("athlete") || "demo-alex";
let generation = 0;
let busy = false;
let toastTimer = 0;
/** @type {{user: boolean; text: string; meta?: string}[]} */
let messages = [];
/** @type {RuleTrace | null} */
let coachTrace = null;
const pageLabels = { today: "Today", dashboard: "Dashboard", goal: "My goal", plan: "Adaptive plan", wins: "Micro Wins", coach: "AI Coach" };
const modeCopy = {
  BUILD: ["Ready for your planned dose", "Recovery signals support keeping today's plan. More isn't automatically better."],
  MAINTAIN: ["Make consistency the goal", "Consolidate the planned stimulus. There is no need to add extra load."],
  RECOVER: ["Recovery is today's progress", "Your recovery signals suggest a lighter day to support continuity."],
  PROTECT: ["Give recovery the right of way", "Several provisional monitoring flags coincide. Consider a lighter dose and review your response; this is not confirmed overload."],
  INSUFFICIENT: ["Let's complete your training picture", "Not enough recovery evidence for a readiness score. Add a check-in; missing is not zero."],
};
const winRules = [
  ["Recovery Win", "Recovery", "Complete an accepted reduction without exceeding its duration or sRPE dose."],
  ["Consistency Win", "Consistency", "Record 3 key sessions within 80-100% of their planned duration, without excess RPE or load."],
  ["Strength Balance", "Strength", "Record 3+ direct sets in 2 muscle groups, no group above 12 this week, within the session dose in BUILD/MAINTAIN."],
  ["Smart Training", "Smart Decisions", "Accept a calculated recovery adjustment. A check-in or plan edit requires a new acceptance."],
  ["Adaptation Win", "Performance", "Log pace 2% faster than 3+ prior comparable runs: same RPE, distance within 10%, within dose, BUILD/MAINTAIN."],
  ["Comeback Win", "Consistency", "Complete an on-dose activity after 2 explicit rest days in BUILD/MAINTAIN."],
  ["Goal Progress Win", "Consistency", "Reach 80% on-plan adherence across at least 5 elapsed scheduled days."],
];

/** @param {string} id */
function el(id) {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing interface element: ${id}`);
  return node;
}
/** @param {unknown} value */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] ?? char);
}
/** @param {number | null | undefined} value @param {number} [digits] */
function fmt(value, digits = 0) {
  return value === null || value === undefined ? "--" : value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
/** @param {number | null} value */
function change(value) {
  return value === null ? "Baseline unavailable" : `${value >= 0 ? "+" : ""}${fmt(value, 1)}% vs baseline`;
}
/** @param {string} value @param {Intl.DateTimeFormatOptions} [options] */
function day(value, options = { month: "short", day: "numeric" }) {
  return new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US", { ...options, timeZone: "UTC" });
}
function currentPage() {
  const hash = location.hash.slice(1);
  return Object.hasOwn(pageLabels, hash) ? hash : "today";
}
function view() {
  if (!state) throw new Error("Athlete data is not loaded.");
  return state;
}
/** @param {unknown} value @returns {value is Record<string, unknown>} */
function object(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
/** @param {unknown} value @returns {value is View} */
function isView(value) {
  return object(value) && object(value.athlete) && typeof value.athlete.id === "string"
    && Array.isArray(value.athlete.plan) && Array.isArray(value.athlete.records)
    && object(value.features) && value.features.contract_version === 1
    && object(value.prediction) && value.prediction.contract_version === 1
    && object(value.prediction.monitoring_review) && typeof value.prediction.monitoring_review.summary === "string"
    && object(value.prediction.monitoring_review.facts) && Array.isArray(value.prediction.monitoring_review.contexts)
    && object(value.recommendation) && typeof value.today === "string"
    && object(value.evidence) && typeof value.evidence.rule_version === "string"
    && Array.isArray(value.evidence.rules) && Array.isArray(value.evidence.sources);
}
/** @param {unknown} value @returns {value is AthleteSummary[]} */
function isAthletes(value) {
  return Array.isArray(value) && value.every(item => object(item)
    && typeof item.id === "string" && typeof item.name === "string" && typeof item.focus === "string");
}
/** @param {unknown} value @returns {value is CoachReply} */
function isCoachReply(value) {
  return object(value) && typeof value.answer === "string" && typeof value.source === "string"
    && typeof value.as_of === "string" && typeof value.disclaimer === "string"
    && object(value.trace) && Array.isArray(value.trace.rules);
}
/** @param {string} path @param {Record<string, unknown>} [payload] @returns {Promise<unknown>} */
async function request(path, payload) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, payload ? {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload), signal: controller.signal,
    } : { signal: controller.signal });
    /** @type {unknown} */
    const data = await response.json();
    if (!response.ok) throw new Error(object(data) && typeof data.error === "string" ? data.error : `Server returned ${response.status}.`);
    return data;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The local server did not respond within 15 seconds. Check the server and retry.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
/** @param {unknown} error */
function errorText(error) {
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}
/** @param {string} text */
function notify(text) {
  el("toast").textContent = text;
  el("toast").hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { el("toast").hidden = true; }, 5500);
}
/** @param {unknown} error */
function showError(error) {
  el("error-banner").innerHTML = `${esc(errorText(error))} <button class="button subtle" data-action="retry">Retry connection</button>`;
  el("error-banner").hidden = false;
}
function setBusy(value = true) {
  busy = value;
  document.querySelectorAll("button[type=submit], button[data-action], button[data-topic]").forEach(node => {
    if (node instanceof HTMLButtonElement) node.disabled = value || node.dataset.locked === "true";
  });
  const picker = el("athlete-select");
  if (picker instanceof HTMLSelectElement) picker.disabled = value;
  const dataButton = el("open-data");
  if (dataButton instanceof HTMLButtonElement) dataButton.disabled = value;
}
async function loadAthlete() {
  const token = ++generation;
  const athleteId = selected;
  el("main").setAttribute("aria-busy", "true");
  el("main").innerHTML = `<div class="loading-state"><span class="loader"></span><h1>Reading your training picture...</h1><p>Calculating from local data, not a connected model.</p></div>`;
  setBusy();
  try {
    const data = await request(`/api/athletes/${encodeURIComponent(athleteId)}`);
    if (token !== generation) return;
    if (!isView(data)) throw new Error("Unexpected backend contract. Restart the app with the matching frontend/backend.");
    state = data;
    messages = [];
    coachTrace = null;
    el("error-banner").hidden = true;
    render();
    refreshDataStudio();
    const avatar = document.querySelector(".athlete-picker .avatar");
    if (avatar) avatar.textContent = data.athlete.name.charAt(0);
  } catch (error) {
    if (token !== generation) return;
    state = null;
    showError(error);
    el("main").innerHTML = `<div class="empty"><h1>We couldn't reach your local coach.</h1><p>No data has been invented or saved. Start the backend and retry.</p></div>`;
  } finally {
    if (token === generation) {
      setBusy(false);
      el("main").setAttribute("aria-busy", "false");
    }
  }
}
/** @param {string} action @param {Record<string, unknown>} payload @param {string} success */
async function mutate(action, payload, success) {
  const athleteId = selected;
  const data = await request(`/api/athletes/${encodeURIComponent(athleteId)}/${action}`, payload);
  if (!isView(data)) throw new Error("Unexpected backend response. Reload to inspect saved data.");
  state = data;
  // Explanations are tied to the previous snapshot and must not survive a mutation.
  messages = [];
  coachTrace = null;
  render();
  refreshDataStudio();
  notify(success);
}
/** @param {string} title @param {string} subtitle */
function pageHead(title, subtitle) {
  return `<div class="page-head"><div><span class="eyebrow">YOUR GOAL. YOUR RESPONSE. YOUR NEXT STEP.</span><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="date-label">${day(view().today, { weekday: "long", month: "long", day: "numeric" })} &middot; UTC</div></div>`;
}
/** @param {Mode} mode */
function modeClass(mode) {
  return mode === "PROTECT" ? "danger" : mode === "RECOVER" || mode === "INSUFFICIENT" ? "warn" : "";
}
function readinessPanel() {
  const { prediction: p, features: f } = view();
  const c = f.current;
  const score = p.readiness_score;
  const dash = (score ?? 0) / 100 * 314.159;
  return `<section class="panel"><div class="panel-title"><h2>Readiness snapshot</h2><span class="pill ${modeClass(p.mode)}">${esc(p.mode)}</span></div>
    <div class="readiness"><div class="gauge ${modeClass(p.mode)}" role="img" aria-label="Demo readiness ${fmt(score)} out of 100">
      <svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="50"/><circle class="gauge-fill" cx="60" cy="60" r="50" stroke-dasharray="${dash} 314.159"/></svg>
      <div class="gauge-center"><strong>${fmt(score)}</strong><span>${score === null ? "unavailable" : "/ 100 estimate"}</span></div></div>
      <div class="readiness-text"><h3>${esc(modeCopy[p.mode][0])}</h3><p>${esc(modeCopy[p.mode][1])}</p><span class="pill teal">HEURISTIC &middot; NOT A MODEL</span></div></div>
    <div class="recovery-meta"><div>Sleep<strong>${fmt(c?.sleep_hours, 1)} <small>h</small></strong></div><div>HRV<strong>${fmt(c?.hrv_ms)} <small>ms</small></strong></div><div>Self-reported fatigue<strong>${fmt(c?.fatigue)} <small>/10</small></strong></div></div>
    <p class="mini-tip">${Object.keys(p.component_scores).length} recovery components available. Source: ${esc(c?.recovery_source ?? "Missing")}.</p>
    <div class="button-row"><a class="text-link" href="#dashboard">See the underlying signals &#8594;</a><a class="text-link" href="#today" data-scroll="checkin">Update check-in &#8594;</a></div></section>`;
}
function missionPanel() {
  const v = view(), p = v.prediction, r = v.recommendation;
  const done = v.athlete.completions.find(c => c.date === v.today);
  const accepted = v.athlete.adjustments[v.today];
  return `<section class="panel mission"><div class="mission-top"><span class="mission-label">YOUR DAILY MISSION</span><span class="pill ${modeClass(p.mode)}">${esc(p.mode)}</span></div>
    <h2>${esc(done ? "Today's session is recorded." : r.title)}</h2><p>${esc(done ? "An actual session log, not an automatic completion. Your metrics now reflect the recorded dose." : r.explanation)}</p>
    <div class="mission-dose"><div><strong>${fmt(done?.duration_min ?? r.duration_min, 0)} <small>min</small></strong>${done ? "actual duration" : "suggested duration"}</div>
      <div><strong>${fmt(done?.session_rpe ?? r.session_rpe, 1)} <small>/10</small></strong>${done ? "actual RPE" : "suggested RPE"}</div>
      <div><strong>${fmt(done ? done.duration_min * done.session_rpe : r.load_au)} <small>AU</small></strong>sRPE load</div></div>
    <div class="button-row">${done ? `<span class="pill teal">RECORDED &amp; SAVED</span>` :
      !v.scheduled_today ? `<a class="button primary" href="#plan">Schedule today's session &#8594;</a>` :
      r.adjusted && !accepted ? `<button class="button primary" data-action="accept">Accept recovery adjustment &#8594;</button><a class="text-link" href="#plan">Compare with original</a>` :
      `<button class="button primary" data-action="log">Log actual session &#8594;</button>${accepted ? '<span class="pill teal">ADJUSTMENT ACCEPTED</span>' : '<a class="text-link" href="#plan">Review your plan</a>'}`}</div></section>`;
}
/** @param {string} title @param {number | null} value @param {string} unit @param {string} note @param {string} [icon] @param {boolean} [warn] */
function metric(title, value, unit, note, icon = "&#9671;", warn = false) {
  return `<article class="panel metric"><div class="metric-label">${esc(title)}<span class="metric-icon">${icon}</span></div><div class="metric-value">${fmt(value)}<small>${esc(unit)}</small></div><div class="metric-note ${warn ? "warn" : ""}">${esc(note)}</div></article>`;
}
function metricGrid() {
  const f = view().features, p = view().prediction;
  return `<div class="metric-grid">
    ${metric("7-day training load", f.weekly_load_au, "AU", change(f.load_change_pct), "&#9645;", (f.load_change_pct ?? 0) > 30)}
    ${metric("Demo fatigue index", p.fatigue_index, "/100", "100 minus demo readiness", "&#9684;", p.mode === "PROTECT")}
    ${metric("7-day strength volume", f.strength_volume_kg, "kg-reps", "Recorded volume, not muscle growth", "&#10807;")}
    ${metric("Plan adherence", view().adherence_pct, "%", "Actual logs / elapsed planned days", "&#9678;")}</div>`;
}
function loadChart() {
  const f = view().features;
  const maximum = Math.max(1, ...f.history.map(h => h.load_au ?? 0));
  return `<section class="panel"><div class="panel-title"><h2>Your last 7 days</h2><span>sRPE load &middot; AU</span></div>
    <div class="load-chart" role="img" aria-label="${esc(f.history.map(h => `${h.date}: ${h.load_au === null ? "missing" : h.load_au + " AU"}`).join("; "))}">${f.history.map(h =>
      `<div class="chart-col ${h.load_au === null ? "missing" : ""}" title="${esc(h.date + ": " + (h.load_au ?? "Missing") + " · " + h.source)}"><span class="chart-value">${fmt(h.load_au)}</span><div class="chart-bar" data-height="${h.load_au === null ? 15 : Math.max(3, h.load_au / maximum * 107)}"></div></div>`).join("")}</div>
    <div class="chart-dates">${f.history.map(h => `<span>${day(h.date, { weekday: "short" })}</span>`).join("")}</div>
    <div class="chart-legend"><span>${f.week_days_observed}/7 explicit activity days</span><span>Rest = 0 &middot; Missing = --</span></div></section>`;
}
/** @param {number | null} percentage */
function progress(percentage) {
  return `<div class="progress-track"><div class="progress-fill" data-value="${Math.max(0, Math.min(100, percentage ?? 0))}"></div></div>`;
}
function goalMini() {
  const v = view(), g = v.athlete.goal;
  return `<section class="panel"><div class="panel-title"><h2>The goal behind today</h2><a class="text-link" href="#goal">View goal &#8599;</a></div>
    <div class="goal-mini"><div class="goal-emblem">&#9678;</div><div><h3>${esc(g.goal_type)}</h3><p>${day(g.goal_date, { month: "long", day: "numeric", year: "numeric" })} &middot; ${v.goal_days_remaining > 0 ? v.goal_days_remaining + " days to go" : "Goal date reached"}</p><p>${g.target_time_min === null ? "No time target" : fmt(g.target_time_min) + " min target"}</p></div></div>
    <div class="goal-details"><span>Recorded plan adherence</span><strong>${fmt(v.adherence_pct)}%</strong></div>${progress(v.adherence_pct)}
    <p class="sub-copy">Not a predicted race result. Only completed, on-dose sessions count.</p>
    <div class="plan-phase"><div class="phase current"><strong>Demo week</strong>7-day editable plan</div><div class="phase"><strong>Next milestone</strong>80% across 5 days</div></div></section>`;
}
function reasonsPanel() {
  const p = view().prediction, review = p.monitoring_review, facts = review.facts, r = view().recommendation;
  return `<section class="panel decision-basis"><div class="panel-title"><h2>Evidence-informed review</h2><span class="pill warn">PROVISIONAL DECISION</span></div>
    <h3>${esc(review.summary)}</h3>
    <h3 class="section-gap">1. Observed facts</h3>
    <p class="sub-copy">Weekly load: ${fmt(facts.weekly_load_au)} AU (${facts.week_days_observed}/7 days); preceding weekly average: ${fmt(facts.baseline_weekly_load_au)} AU (${facts.baseline_days_observed}/28 days). Recovery: ${esc(facts.recovery_source)}.</p>
    <ul class="reason-list">${p.observed_signals.map(s => `<li>${esc(evidenceRule(s.rule_id).title)}: ${fmt(s.value, 1)} ${esc(s.unit)} &middot; ${esc(s.comparability)}${s.value === null ? " (unavailable)" : ""}</li>`).join("")}</ul>
    <details class="section-gap"><summary><strong>2. Source-supported monitoring context</strong></summary>
    ${review.contexts.map(c => `<p class="sub-copy">${esc(evidenceRule(c.rule_id).title)}: ${esc(c.support.replaceAll("-", " "))}. ${referenceLinks(c.source_ids)}</p>`).join("")}
    <p class="sub-copy">${esc(evidenceRule(review.rule_id).protocol)} ${referenceLinks(evidenceRule(review.rule_id).source_ids)}</p>
    <p class="sub-copy">References support methods and context, not the exact cuts. Sleep source: repository abstract reviewed; full text unavailable. Expand evidence details in Dashboard or Adaptive plan for source-specific scope.</p></details>
    <details class="section-gap"><summary><strong>3. Provisional decision criterion</strong></summary>
    <p class="sub-copy">${esc(review.criterion)}</p>
    <ul class="reason-list">${p.observed_signals.map(s => `<li>${esc(evidenceRule(s.rule_id).title)}: ${esc(s.operator)} ${s.threshold} ${esc(s.unit)} &mdash; ${s.crossed === null ? "not evaluated" : s.crossed ? "crossed provisional cut" : "no crossing"}</li>`).join("")}</ul></details>
    <h3 class="section-gap">4. Suggested review / action</h3><p class="sub-copy">${esc(review.review_action)}</p>
    <p class="sub-copy">${fmt(r.duration_min, 1)} min at RPE ${fmt(r.session_rpe, 1)} (${fmt(r.load_au)} AU). ${esc(r.explanation)} The original plan stays visible in Adaptive plan; acceptance is your choice.</p>
    <p class="source-label">${esc(review.limitations)}</p>
    <div class="source-label">${esc(p.rule_version)} &middot; ${esc(p.prediction_source)} &middot; ${esc(view().today)}<br>${referenceLinks(evidenceRule(review.rule_id).source_ids)}</div></section>`;
}
/** @param {string[]} ids */
function referenceLinks(ids) {
  return ids.map(id => {
    const source = view().evidence.sources.find(s => s.id === id);
    if (!source) throw new Error(`Missing source in evidence contract: ${id}`);
    return `<a class="text-link" href="${esc(source.accessible_url ?? source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.citation)} &#8599;</a>`;
  }).join(" &middot; ");
}
/** @param {string} id */
function evidenceRule(id) {
  const rule = view().evidence.rules.find(r => r.id === id);
  if (!rule) throw new Error(`Missing rule in evidence contract: ${id}`);
  return rule;
}
/** @param {string[]} ids */
function tracePanel(ids) {
  return `<section class="panel evidence-panel section-gap"><div class="panel-title"><h2>Evidence &amp; rule traceability</h2><span>${esc(view().evidence.rule_version)}</span></div>
    <div class="notice warn">A supported variable or method does not validate an exact threshold. All product, signal and reward cuts remain provisional. No calibrated confidence percentage is available.</div>
    ${ids.map(id => {
      const rule = evidenceRule(id);
      return `<details class="evidence-rule"><summary><strong>${esc(rule.title)}</strong><span class="pill ${rule.evidence.exact_threshold === "provisional" ? "warn" : "teal"}">${rule.evidence.exact_threshold === "provisional" ? "PROVISIONAL CUT" : "METHOD / DESCRIPTIVE"}</span></summary>
      <dl><dt>What is supported?</dt><dd>Variable: ${esc(rule.evidence.variable.replaceAll("-", " "))}. Method: ${esc(rule.evidence.method.replaceAll("-", " "))}. Exact cut: ${esc(rule.evidence.exact_threshold)}.</dd>
      <dt>Protocol / data needed</dt><dd>${esc(rule.protocol)}</dd><dt>Applicability</dt><dd>${esc(rule.population)}</dd><dt>Limitations</dt><dd>${esc(rule.limitations)}</dd><dt>References</dt><dd>${rule.source_ids.length ? referenceLinks(rule.source_ids) : "No scientific validation claimed; descriptive arithmetic / product filtering."}</dd></dl>
      ${rule.source_ids.map(sourceId => {
        const source = view().evidence.sources.find(s => s.id === sourceId);
        if (!source) throw new Error(`Missing evidence source: ${sourceId}`);
        return `<details class="source-context"><summary>${esc(source.citation)}: population &amp; protocol</summary><p><strong>Title:</strong> ${esc(source.title)}</p>${source.published_on ? `<p>Published: ${esc(source.published_on)}; reviewed: ${esc(source.reviewed_on)}; DOI: ${esc(source.doi)}.</p>` : ""}<p><strong>Population:</strong> ${esc(source.population)}</p><p><strong>Protocol:</strong> ${esc(source.protocol)}</p><p><strong>Scope:</strong> ${esc(source.supports)}</p><p><strong>Limitations:</strong> ${esc(source.limitations)}</p><p><strong>Content reviewed:</strong> ${esc(source.verification)}</p>${source.correction_url ? `<a class="text-link" href="${esc(source.correction_url)}" target="_blank" rel="noopener noreferrer">Consulted corrigendum &#8599;</a>` : ""}</details>`;
      }).join("")}</details>`;
    }).join("")}<p class="source-label">${esc(view().evidence.scope)}</p></section>`;
}
function observedSignalsPanel() {
  return `<section class="panel section-gap observed-signals"><div class="panel-title"><h2>Observed data, separate from the decision</h2><span>Demo flags, not clinical states</span></div><div class="table-wrap"><table><thead><tr><th>Observation / change</th><th>Value</th><th>Provisional cut</th><th>Result</th><th>Comparability</th></tr></thead><tbody>
    ${view().prediction.observed_signals.map(s => `<tr><td>${esc(evidenceRule(s.rule_id).title)}</td><td>${fmt(s.value, 1)} ${esc(s.unit)}</td><td>${esc(s.operator)} ${s.threshold} ${esc(s.unit)}</td><td>${s.crossed === null ? "Not evaluated / missing" : s.crossed ? "Crossed demo cut" : "No crossing"}</td><td>${esc(s.comparability)}</td></tr>`).join("")}</tbody></table></div><p class="sub-copy">No crossing does not prove readiness or safety. Missing observations are not a healthy baseline.</p></section>`;
}
function baselinesPanel() {
  const quality = view().features.baseline_quality;
  return `<section class="panel section-gap baseline-quality"><div class="panel-title"><h2>Individual baseline quality</h2><span>Descriptive variability, not significance</span></div><div class="equal-col">
    ${[["HRV", quality.hrv], ["Resting HR", quality.resting_hr]].map(([label, q]) => {
      if (typeof q === "string") throw new Error("Invalid baseline contract.");
      return `<article class="baseline-card"><h3>${esc(label)}</h3><span class="pill ${q.comparability === "declared-match" ? "teal" : "warn"}">${esc(q.status)}</span>
      ${extended("Mean", q.mean, q.unit, 1)}${extended("Population SD", q.population_sd, q.unit, 2)}${extended("Descriptive CV", q.coefficient_of_variation_pct, "%", 1)}
      <p class="sub-copy">${q.used_count}/${q.observation_count} observations used; minimum ${q.required_count}. ${esc(q.window_start)} to ${esc(q.window_end)}.</p><p class="sub-copy">Comparability: <strong>${esc(q.comparability)}</strong>; ${q.excluded_mismatch_count} known mismatches excluded. Device: ${esc(q.current_device ?? "unknown")}; protocol: ${esc(q.current_protocol ?? "unknown")}.</p><p class="sub-copy">${esc(q.notes.join(" "))}</p></article>`;
    }).join("")}</div><p class="source-label">Load baseline: ${quality.weekly_load.observation_count}/${quality.weekly_load.required_count} daily records; ${esc(quality.weekly_load.status)}. Daily SD ${fmt(quality.weekly_load.population_sd_daily_au, 1)} AU; RPE collection comparability unknown. ${referenceLinks(["buchheit-2014"])}</p></section>`;
}
function decisionHistoryPanel() {
  const a = view().athlete;
  return `<section class="panel section-gap decision-history"><div class="panel-title"><h2>Saved decisions &amp; actual outcomes</h2><a class="text-link" href="/api/athletes/${encodeURIComponent(a.id)}/decisions" download="athleteos-decision-log.json">Export replayable JSON &#8595;</a></div>
    <p class="sub-copy">Snapshots keep original inputs, features, rule/source manifest and recommendation. Later edits do not rewrite them. Outcomes record submitted session values, not physiological adaptation.</p>
    ${a.decision_snapshots.length ? `<div class="table-wrap"><table><thead><tr><th>Captured decision</th><th>Version / mode</th><th>Recommendation</th><th>Linked actual outcome</th></tr></thead><tbody>${[...a.decision_snapshots].reverse().slice(0, 12).map(s => {
      const outcome = a.decision_outcomes.find(o => o.decision_id === s.id);
      return `<tr><td>${esc(s.as_of)}<br><small>${esc(s.trigger)} &middot; ${esc(s.id.slice(0, 8))}</small></td><td>${esc(s.rule_version)}<br>${esc(s.mode)}</td><td>${fmt(s.recommendation.duration_min)} min / RPE ${fmt(s.recommendation.session_rpe, 1)}</td><td>${outcome ? `${fmt(outcome.duration_min)} min / RPE ${fmt(outcome.session_rpe, 1)} / ${fmt(outcome.actual_load_au)} AU<br>${outcome.on_plan ? "Within planned dose" : "Outside planned dose"}` : "No linked actual log"}</td></tr>`;
    }).join("")}</tbody></table></div>` : '<div class="empty"><h3>No saved decision yet</h3><p>Save a decision, change a goal/plan/check-in, import data or accept a recommendation. Viewing a page does not create history.</p></div>'}
    ${a.completions.some(c => c.trace_status === "legacy-unrecorded") ? '<div class="notice warn">Legacy session logs are preserved, but their original decision inputs were not recorded. They are not retrospectively reconstructed.</div>' : ""}
    <div class="button-row"><button class="button subtle" data-action="snapshot">Save current decision snapshot</button></div></section>`;
}
function winPreview() {
  const wins = view().athlete.wins, latest = wins[wins.length - 1];
  return `<section class="panel win-preview"><div class="win-icon">&#10022;</div><div><h3>${esc(latest ? latest.title : "Smart decisions are worth celebrating.")}</h3><p>${esc(latest ? latest.reason : "Micro Wins recognize verified actions, not simply doing more.")}</p></div><a class="text-link" href="#wins">${latest ? "View win" : "See the rules"} &#8594;</a></section>`;
}
/** @param {string} name @param {string} label @param {number | null | undefined} value @param {number} max @param {number} [step] */
function numberField(name, label, value, max, step = 1) {
  return `<label>${esc(label)}<input name="${esc(name)}" type="number" min="0" max="${max}" step="${step}" value="${value ?? ""}" placeholder="Not measured"></label>`;
}
function checkinPanel() {
  const c = view().features.current;
  return `<section id="checkin" class="panel"><div class="panel-title"><h2>How are you feeling today?</h2><span>Daily check-in &middot; UTC</span></div>
    <p class="sub-copy">Confirm or edit actual recovery values. Blank fields are saved as missing; they are never inferred.</p>
    <form id="checkin-form" class="section-gap"><div class="form-grid">
      ${numberField("sleep_hours", "Sleep (hours)", c?.sleep_hours, 24, 0.1)}
      ${numberField("fatigue", "Fatigue (0-10)", c?.fatigue, 10, 0.1)}
      ${numberField("soreness", "Soreness (0-10)", c?.soreness, 10, 0.1)}
      ${numberField("stress", "Stress (0-10)", c?.stress, 10, 0.1)}
      ${numberField("hrv_ms", "Measured HRV (ms)", c?.hrv_ms, 500, 0.1)}
      ${numberField("resting_hr_bpm", "Measured resting HR (bpm)", c?.resting_hr_bpm, 200, 0.1)}
      <details class="full metadata-form"><summary>Optional measurement device &amp; protocol</summary><p class="sub-copy">Declare both fields together. Use the same exact description for comparable measurements; declarations do not verify accuracy. No Garmin connection.</p><div class="form-grid">
      <label>HRV device<input name="hrv_device" maxlength="160" value="${esc(c?.hrv_device)}" placeholder="Unknown unless declared"></label>
      <label>HRV index &amp; recording protocol<input name="hrv_protocol" maxlength="160" value="${esc(c?.hrv_protocol)}" placeholder="e.g. RMSSD; morning; seated; 5 min"></label>
      <label>Resting HR device<input name="resting_hr_device" maxlength="160" value="${esc(c?.resting_hr_device)}" placeholder="Unknown unless declared"></label>
      <label>Resting HR recording protocol<input name="resting_hr_protocol" maxlength="160" value="${esc(c?.resting_hr_protocol)}" placeholder="e.g. morning; seated; 5 min"></label></div></details></div>
      <div class="form-error" role="alert" hidden></div><div class="button-row"><button class="button primary" type="submit">Save check-in &amp; recalculate</button><span class="sub-copy">Saved locally when confirmed</span></div></form></section>`;
}
function todayPage() {
  const name = view().athlete.name.split(" ")[0];
  return pageHead(`A good day starts with a smart plan, ${name}.`, "One daily mission. Connected to your goal and how you're responding.")
    + `<div class="two-col">${missionPanel()}${readinessPanel()}</div><div class="section-heading"><h2>Your training, at a glance</h2><a class="text-link" href="#dashboard">Full dashboard &#8594;</a></div>`
    + metricGrid() + `<div class="two-col section-gap">${loadChart()}${goalMini()}</div><div class="two-col section-gap">${checkinPanel()}<div class="stack">${reasonsPanel()}${winPreview()}</div></div>`;
}
function dashboardPage() {
  const f = view().features, p = view().prediction;
  const sets = f.direct_sets_by_muscle;
  return pageHead("The response behind the routine.", "Transparent training and recovery metrics. No missing values disguised as measurements.")
    + metricGrid() + `<div class="two-col section-gap">${loadChart()}${readinessPanel()}</div>
    <div class="equal-col section-gap"><section class="panel"><div class="panel-title"><h2>Load &amp; response</h2><span>Explicit units</span></div>
      ${extended("Weekly baseline (prior 28 days / 4)", f.baseline_weekly_load_au, "AU")}
      ${extended("Monotony (mean / population SD)", f.monotony_ratio, "ratio", 2)}
      ${extended("Strain (weekly load x monotony)", f.strain_au, "AU")}
      ${extended("Exercise HR reserve", f.hr_reserve_ratio, "ratio", 2)}
      ${extended("HRV baseline", f.hrv_baseline_ms, "ms", 1)}
      ${extended("Resting HR baseline", f.resting_hr_baseline_bpm, "bpm", 1)}
      ${extended("RPE 3-5 run pace", f.pace_min_per_km, "min/km", 2)}
      <p class="sub-copy">Pace: ${esc(change(f.pace_change_pct))}. Lower pace means faster; terrain/weather are not controlled. Descriptive, not a forecast.</p></section>
    <section class="panel"><div class="panel-title"><h2>Muscle stimulus</h2><span>Direct sets &middot; 7 days</span></div>
      ${sets ? Object.entries(sets).map(([muscle, count]) => `<div class="muscle-row"><div class="muscle-label"><span>${esc(muscle)}</span><strong>${count} direct sets</strong></div>${progress(count / 12 * 100)}</div>`).join("") : '<div class="empty"><h3>Weekly sets unavailable</h3><p>Need 7 explicit daily activity records.</p></div>'}
      <p class="sub-copy">Bars use 12 sets as the demo balance-rule ceiling, not an optimal prescription. Indirect sets are excluded.</p>
      <div class="section-gap"><h3>Epley formula estimates, by exercise</h3>${f.e1rm_estimates.length ? f.e1rm_estimates.map(e => extended(`${e.exercise} · ${day(e.date)}`, e.e1rm_kg, "kg", 1) + `<p class="sub-copy">${esc(e.protocol_status)} &middot; ${esc(e.limitations)}</p>`).join("") : '<p class="sub-copy">No positive-weight strength sets with 1-10 reps available.</p>'}</div>
      <p class="sub-copy">Volume = sets x reps x kg. These are calculated metrics, not a tested max or measured muscle growth.</p></section></div>
    <div class="equal-col section-gap"><section class="panel"><div class="panel-title"><h2>Monitoring signals, not confirmed overload</h2><span class="pill ${modeClass(p.mode)}">${esc(p.mode)}</span></div><h3>${esc(p.monitoring_review.summary)}</h3>
      <ul class="reason-list">${(p.signals.length ? p.signals : ["No qualifying crossings in the supplied evidence; not proof of safety."]).map(s => `<li class="warning">${esc(s)}</li>`).join("")}</ul><p class="source-label">${esc(p.limitations)}</p></section>
    <section class="panel"><div class="panel-title"><h2>Data quality &amp; provenance</h2><a class="text-link" href="#" data-action="data">Open data studio &#8599;</a></div>
      ${f.warnings.length ? `<ul class="warning-list">${f.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : '<p class="sub-copy">All calculation prerequisites are available. Synthetic data still does not validate this heuristic.</p>'}
      <p class="source-label">${esc(f.current?.recovery_source ?? "Missing recovery")} &middot; ${view().athlete.records.length} explicit daily records &middot; as of ${esc(view().today)} UTC</p></section></div>`
    + observedSignalsPanel() + baselinesPanel() + reasonsPanel()
    + tracePanel(["monitoring-review", "srpe", "baseline", "sleep", "hrv", "resting-hr", "weekly-load", "readiness", "dose", "strength-volume", "epley", "pace"])
    + decisionHistoryPanel();
}
/** @param {string} label @param {number | null} value @param {string} unit @param {number} [digits] */
function extended(label, value, unit, digits = 0) {
  return `<div class="metric-extended"><span>${esc(label)}</span><strong>${fmt(value, digits)} ${esc(unit)}</strong></div>`;
}
function goalPage() {
  const g = view().athlete.goal;
  return pageHead("Define the finish line. Protect the journey.", "Your goal gives the plan context; demo recommendations respond to your recovery data.")
    + `<div class="two-col"><section class="panel"><div class="panel-title"><h2>Your north star</h2><span class="pill">EDITABLE &amp; PERSISTENT</span></div><form id="goal-form"><div class="form-grid">
      <label>Goal type<select name="goal_type">${["Marathon", "Half marathon", "10K", "Strength", "General fitness"].map(type => `<option${g.goal_type === type ? " selected" : ""}>${type}</option>`).join("")}</select></label>
      <label>Goal date<input name="goal_date" type="date" value="${esc(g.goal_date)}" required></label>
      <label>Target time (minutes, optional)<input name="target_time_min" type="number" min="1" max="1440" step="0.1" value="${g.target_time_min ?? ""}" placeholder="No time target"><span class="field-hint">For timed goals only; not a predicted finish.</span></label>
      <label>Secondary priority<input name="secondary" maxlength="200" value="${esc(g.secondary)}" placeholder="What else matters?"></label></div><div class="form-error" role="alert" hidden></div><div class="button-row"><button class="button primary" type="submit">Save my goal</button></div></form>
      <div class="notice">The demo does not auto-generate a race-specific training program. Edit your sessions in Adaptive plan; goal context is explained by the coach.</div></section><div class="stack">${goalMini()}${winPreview()}</div></div>
    <section class="panel section-gap"><div class="panel-title"><h2>Goal progress, without a false forecast</h2><a class="text-link" href="#plan">Manage sessions &#8594;</a></div><div class="mini-stats"><span>Days remaining<strong>${view().goal_days_remaining}</strong></span><span>On-plan adherence<strong>${fmt(view().adherence_pct)}%</strong></span><span>Verified wins<strong>${view().athlete.wins.length}</strong></span></div><p class="sub-copy">Adherence requires a submitted actual log within 80-100% of the chosen duration and no excess RPE or sRPE load. No predicted race time, injury certainty, or muscle-growth claim.</p></section>`;
}
function sessionList() {
  const v = view(), sessions = v.athlete.plan.filter(s => s.date >= v.today).slice(0, 14);
  return `<section class="panel"><div class="panel-title"><h2>Upcoming plan</h2><span>Up to 14 upcoming sessions</span></div><div class="session-list">${sessions.length ? sessions.map(s => {
    const completed = v.athlete.completions.some(c => c.date === s.date);
    return `<div class="session-row ${s.date === v.today ? "today" : ""}"><div class="session-day">${day(s.date, { weekday: "short" })}<strong>${day(s.date, { day: "numeric" })}</strong></div>
      <div><div class="session-title">${esc(s.title)}</div><div class="session-sub">${esc(s.sport_type)} &middot; ${s.key ? "Key session" : "Supporting session"}${completed ? " · Recorded" : ""}</div></div>
      <div class="session-dose">${fmt(s.duration_min)} min<br>${fmt(s.duration_min * s.session_rpe)} AU</div>
      <button class="button ghost" data-action="edit-plan" data-date="${esc(s.date)}"${completed ? ' data-locked="true" disabled' : ""}>Edit</button></div>`;
  }).join("") : '<div class="empty"><h3>No upcoming sessions</h3><p>Add a session using the form. Plans are not silently extended.</p></div>'}</div><p class="sub-copy">Future recovery is unknown: adaptations are calculated for today only.</p></section>`;
}
/** @param {Session | null} [session] */
function planForm(session = null) {
  const s = session ?? { date: view().today, title: "Easy aerobic run", sport_type: "run", duration_min: 45, session_rpe: 4, key: false };
  return `<section class="panel" id="plan-editor"><div class="panel-title"><h2>Add or edit a session</h2><span>One session per date</span></div><form id="plan-form"><div class="form-grid">
    <label>Session date<input name="date" type="date" value="${esc(s.date)}" min="${esc(view().today)}" required></label>
    <label>Sport<select name="sport_type">${["run", "walk", "cycle", "strength", "rest"].map(sport => `<option${s.sport_type === sport ? " selected" : ""}>${sport}</option>`).join("")}</select></label>
    <label class="full">Session name<input name="title" maxlength="80" value="${esc(s.title)}" required></label>
    ${numberField("duration_min", "Planned duration (min)", s.duration_min, 1440, 0.1)}
    ${numberField("session_rpe", "Planned RPE (0-10)", s.session_rpe, 10, 0.1)}
    <div class="full strength-inputs"${s.sport_type === "strength" ? "" : " hidden"}>${strengthInputs(s)}</div>
    <label class="check-label full"><input name="key" type="checkbox"${s.key ? " checked" : ""}>Key session for my goal</label></div>
    <div class="form-error" role="alert" hidden></div><div class="button-row"><button class="button primary" type="submit">Save session</button><span class="sub-copy">Rest days require 0 min and RPE 0.</span></div></form></section>`;
}
/** @param {StrengthFields} values */
function strengthInputs(values) {
  return `<div class="form-grid"><label>Exercise<input name="exercise" maxlength="80" value="${esc(values.exercise)}" placeholder="e.g. Squat"></label><label>Direct muscle group<select name="muscle_group">${["legs", "push", "pull", "core"].map(m => `<option${values.muscle_group === m ? " selected" : ""}>${m}</option>`).join("")}</select></label>
    ${numberField("sets", "Sets (integer, 1+)", values.sets, 100)}
    ${numberField("reps", "Reps per set (integer, 1+)", values.reps, 100)}
    ${numberField("load_kg", "External load (kg)", values.load_kg, 1000, 0.1)}
    ${numberField("rir", "Reps in reserve (0-10, optional)", values.rir, 10, 0.1)}</div>`;
}
function comparisonPanel() {
  const v = view(), s = v.today_session, r = v.recommendation;
  return `<section class="panel"><div class="panel-title"><h2>Today's adaptive decision</h2><span class="pill ${modeClass(v.prediction.mode)}">${esc(v.prediction.mode)}</span></div>
    <div class="comparison"><div class="comparison-box"><span>ORIGINAL PLAN</span><h3>${esc(s.title)}</h3><p>${fmt(s.duration_min)} min &middot; RPE ${fmt(s.session_rpe, 1)}<br>${fmt(s.duration_min * s.session_rpe)} AU</p></div><div class="comparison-arrow">&#8594;</div><div class="comparison-box adapted"><span>${r.adjusted ? "ADAPTED RECOMMENDATION" : "KEEP / INSUFFICIENT EVIDENCE"}</span><h3>${esc(r.title)}</h3><p>${fmt(r.duration_min)} min &middot; RPE ${fmt(r.session_rpe, 1)}<br>${fmt(r.load_au)} AU</p></div></div>
    <p class="sub-copy">${esc(r.explanation)}</p><div class="button-row"><a class="button primary" href="#today">Back to daily mission &#8594;</a><a class="text-link" href="#coach">Ask about this decision</a></div></section>`;
}
function planPage() {
  const scoring = evidenceRule("readiness").parameters, dose = evidenceRule("dose").parameters;
  return pageHead("A plan that listens, not just pushes.", "Keep the original plan visible. Today's adjustment is grounded in supplied recovery signals.")
    + comparisonPanel() + `<div class="section-gap">${reasonsPanel()}</div>` + observedSignalsPanel() + baselinesPanel()
    + `<div class="two-col section-gap">${sessionList()}${planForm(view().athlete.plan.find(s => s.date === view().today) ?? null)}</div>`
    + `<section class="panel section-gap"><div class="panel-title"><h2>Demo decision thresholds</h2><span>Uncalibrated, non-clinical</span></div><div class="table-wrap"><table><thead><tr><th>Mode</th><th>Trigger</th><th>Today's action</th></tr></thead><tbody>
      <tr><td>BUILD</td><td>Readiness &ge;${scoring.build_score_at_least}, no crossed signals</td><td>Keep plan; no automatic increase</td></tr>
      <tr><td>MAINTAIN</td><td>Below BUILD cut or 1 signal, unless RECOVER applies</td><td>Keep dose</td></tr>
      <tr><td>RECOVER</td><td>${scoring.recover_signals} signals or readiness &lt;${scoring.recover_score_below}</td><td>${Number(dose.recover_factor) * 100}% duration; RPE &le;${dose.recover_rpe_cap}; walk</td></tr>
      <tr><td>PROTECT</td><td>${scoring.protect_signals}+ coincident signals</td><td>${Number(dose.protect_factor) * 100}% duration; RPE &le;${dose.protect_rpe_cap}; walk</td></tr>
      <tr><td>INSUFFICIENT</td><td>&lt;${scoring.minimum_components} recovery components and too few signals</td><td>No score; request evidence</td></tr></tbody></table></div><p class="sub-copy">Every displayed cut and reduction is provisional, not an exact scientific prescription. PROTECT takes precedence; a scheduled rest day stays rest.</p></section>`
    + tracePanel(["monitoring-review", "readiness", "dose", "sleep", "fatigue", "soreness", "hrv", "resting-hr", "weekly-load", "wins"])
    + decisionHistoryPanel();
}
function winsPage() {
  const wins = view().athlete.wins;
  return pageHead("Small wins. Smarter training.", "Celebrate decisions that support the goal, not a streak that punishes recovery.")
    + (wins.length ? `<div class="win-grid">${wins.map(w => `<article class="panel win-card" data-earned="true"><div class="win-icon">&#10022;</div><span class="pill">${esc(w.category)}</span><h3 class="section-gap">${esc(w.title)}</h3><p>${esc(w.reason)}</p><small>${day(w.date)} &middot; ${esc(w.goal_type)} &middot; Verified demo action &middot; ${esc(w.rule_version ?? "Legacy: unrecorded rule version")}</small></article>`).join("")}</div>` : `<div class="empty"><div class="win-icon" aria-hidden="true">&#10022;</div><h3>No earned wins yet &mdash; and that's okay.</h3><p>Demo history alone doesn't grant rewards. Accept an adjustment or record an actual on-dose session to satisfy a rule.</p></div>`)
    + `<div class="section-heading"><h2>The rules behind the recognition</h2><span>Deterministic &middot; No LLM triggers</span></div><div class="win-grid">${winRules.map(([title, category, rule]) => `<article class="panel win-card ${wins.some(w => w.title === title) ? "" : "locked"}"><span class="pill">${esc(category)}</span><h3 class="section-gap">${esc(title)}</h3><p>${esc(rule)}</p><small>${wins.some(w => w.title === title) ? "Earned at least once" : "Not earned yet"}</small></article>`).join("")}</div>`
    + `<section class="panel section-gap"><h2>Your win timeline</h2>${wins.length ? [...wins].reverse().map(w => `<div class="timeline-row"><span>${day(w.date)}</span><div><strong>${esc(w.title)}</strong><p>${esc(w.reason)}</p></div></div>`).join("") : '<p class="sub-copy">Your timeline will appear after a verified action. Imported data never pretends to be a completed app mission.</p>'}<p class="source-label">Strength and performance wins are disabled in RECOVER/PROTECT. These are demo motivation rules, not validated prescriptions.</p></section>` + tracePanel(["wins"]);
}
function coachPage() {
  const initial = `Hi ${view().athlete.name.split(" ")[0]}. I'm your demo data explainer, not a connected AI model. Today's mode is ${view().prediction.mode}. I can explain your actual calculations, plan adjustment, and Micro Win rules.`;
  const thread = [{ user: false, text: initial, meta: `${view().today} UTC · ${view().prediction.prediction_source}` }, ...messages];
  return pageHead("Your data, explained like a teammate.", "Bounded, deterministic answers grounded in the current backend snapshot.")
    + `<div class="coach-layout"><section class="panel"><div class="panel-title"><h2>AI Coach <span class="pill">DEMO EXPLAINER</span></h2><span>Not an LLM</span></div><div class="coach-thread" role="log" aria-live="polite">${thread.map(m => `<div class="coach-message ${m.user ? "user" : ""}"><div class="coach-avatar">${m.user ? esc(view().athlete.name.charAt(0)) : "&#9671;"}</div><div><div class="coach-bubble"><p>${esc(m.text)}</p></div>${m.meta ? `<div class="coach-meta">${esc(m.meta)}</div>` : ""}</div></div>`).join("")}</div>
    <div class="coach-questions">${Object.entries({ readiness: "Why this readiness?", plan: "How does today support my goal?", load: "Explain my load", overload: "Review load and recovery", strength: "What about strength?", wins: "How do I earn a win?" }).map(([topic, text]) => `<button data-topic="${topic}">${text}</button>`).join("")}</div>
    <p class="coach-scope">Choose a supported question. No free-form medical advice, invented metrics, or model connection.</p></section><div class="stack">${reasonsPanel()}${goalMini()}<section class="panel"><h3>Grounded in what we know</h3><p class="sub-copy">Recorded data &rarr; calculated metrics &rarr; provisional product decision. Missing data stays missing; sources do not validate every cut.</p><p class="source-label">${esc(view().prediction.limitations)}</p></section></div></div>`
    + baselinesPanel() + tracePanel(coachTrace?.rules.map(r => r.id) ?? ["monitoring-review", "readiness", "sleep", "hrv", "resting-hr", "dose"]);
}
function render() {
  if (!state) return;
  const page = currentPage();
  document.querySelectorAll("nav a").forEach(node => {
    const active = node instanceof HTMLElement && node.dataset.page === page;
    node.classList.toggle("active", active);
    if (active) node.setAttribute("aria-current", "page"); else node.removeAttribute("aria-current");
  });
  const title = Object.entries(pageLabels).find(([key]) => key === page)?.[1] ?? "Today";
  el("page-label").textContent = title;
  document.title = `AthleteOS | ${title}`;
  const pages = { today: todayPage, dashboard: dashboardPage, goal: goalPage, plan: planPage, wins: winsPage, coach: coachPage };
  const renderer = Object.entries(pages).find(([key]) => key === page)?.[1] ?? todayPage;
  el("main").innerHTML = renderer();
  el("main").setAttribute("aria-busy", "false");
  applyMeters();
}
function applyMeters() {
  document.querySelectorAll(".progress-fill[data-value]").forEach(node => {
    if (node instanceof HTMLElement) node.style.width = `${Number(node.dataset.value)}%`;
  });
  document.querySelectorAll(".chart-bar[data-height]").forEach(node => {
    if (node instanceof HTMLElement) node.style.height = `${Number(node.dataset.height)}px`;
  });
}
function refreshDataStudio() {
  if (!state) return;
  const a = state.athlete, sources = new Map();
  for (const r of a.records) sources.set(r.source, (sources.get(r.source) ?? 0) + 1);
  const link = el("export-link");
  if (link instanceof HTMLAnchorElement) link.href = `/api/athletes/${encodeURIComponent(selected)}/export`;
  el("data-provenance").innerHTML = `<h3 class="section-gap">Current athlete: ${esc(a.name)}</h3><div class="notice">CSV athlete_id must be <strong>${esc(a.id)}</strong>; timezone must be UTC. Importing historical dates does not supply today's missing recovery.</div>
    <div class="table-wrap provenance-table"><table><thead><tr><th>Source</th><th>Daily activity records</th></tr></thead><tbody>${[...sources.entries()].map(([source, count]) => `<tr><td>${esc(source)}</td><td>${count}</td></tr>`).join("") || '<tr><td>No observations</td><td>0</td></tr>'}</tbody></table></div><p class="sub-copy">Legacy CSV is still accepted. Exports append hrv_device, hrv_protocol, resting_hr_device, resting_hr_protocol in that order. Supply each pair together and its measured value, or leave both blank. Exact declared matches are not independently verified; unknown metadata remains unknown.</p><p class="sub-copy">App check-ins never imply activity/rest. Changes and immutable decision snapshots persist locally; imported data never reconstructs a past decision.</p>`;
}
/** @param {FormData} data @param {string} name */
function formText(data, name) {
  const value = data.get(name);
  return typeof value === "string" ? value : "";
}
/** @param {FormData} data @param {string} name */
function formNumber(data, name) {
  const value = formText(data, name).trim();
  return value === "" ? null : Number(value);
}
/** @param {FormData} data @returns {Record<string, unknown>} */
function strengthPayload(data) {
  return { exercise: formText(data, "exercise"), muscle_group: formText(data, "muscle_group"),
    sets: formNumber(data, "sets"), reps: formNumber(data, "reps"),
    load_kg: formNumber(data, "load_kg"), rir: formNumber(data, "rir") };
}
function openData() {
  if (busy || !state) return;
  refreshDataStudio();
  const dialog = el("data-dialog");
  if (dialog instanceof HTMLDialogElement) dialog.showModal();
}
function openLog() {
  const v = view(), accepted = v.athlete.adjustments[v.today], dose = accepted?.recommendation ?? v.recommendation;
  let dialog = document.getElementById("log-dialog");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "log-dialog";
    document.body.append(dialog);
  }
  dialog.innerHTML = `<div class="dialog-head"><div><span class="eyebrow">ACTUALS, NOT ASSUMPTIONS</span><h2 id="log-title">Log your completed session</h2></div><button class="icon-button" data-close="log-dialog" aria-label="Close session log">&times;</button></div><p>${esc(dose.title)} &middot; ${esc(v.today)} UTC. Suggested dose: ${fmt(dose.duration_min)} min, RPE ${fmt(dose.session_rpe, 1)}.</p>
    <div class="notice">This replaces today's uncompleted activity observation, not other days. Recovery values are preserved. Distance and strength are never guessed.</div><form id="complete-form"><div class="form-grid">
    ${numberField("duration_min", "Actual duration (min)", dose.duration_min, 1440, 0.1)}
    ${numberField("session_rpe", "Actual session RPE (0-10)", dose.session_rpe, 10, 0.1)}
    ${["run", "walk", "cycle"].includes(dose.sport_type) ? numberField("distance_km", "Actual distance (km, optional)", null, 500, 0.001) : ""}
    ${dose.sport_type === "strength" ? `<div class="full">${strengthInputs(v.today_session)}</div>` : ""}</div>
    <label class="check-label"><input type="checkbox" required>I confirm these are actual completed values, not just my plan.</label>
    <div class="form-error" role="alert" hidden></div><div class="button-row"><button type="submit" class="button primary">Save actual session</button></div></form>`;
  dialog.setAttribute("aria-labelledby", "log-title");
  if (dialog instanceof HTMLDialogElement) dialog.showModal();
}

document.addEventListener("submit", async event => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  event.preventDefault();
  if (busy || !state) return;
  const errorNode = form.querySelector(".form-error") ?? document.getElementById("import-error");
  if (errorNode instanceof HTMLElement) errorNode.hidden = true;
  const data = new FormData(form);
  setBusy();
  try {
    if (form.id === "goal-form") {
      await mutate("goal", { goal_type: formText(data, "goal_type"), goal_date: formText(data, "goal_date"),
        target_time_min: formNumber(data, "target_time_min"), secondary: formText(data, "secondary") }, "Goal saved locally.");
    } else if (form.id === "checkin-form") {
      /** @type {Record<string, number | string | null>} */
      const payload = Object.fromEntries(["sleep_hours", "fatigue", "soreness", "stress", "hrv_ms", "resting_hr_bpm"].map(f => [f, formNumber(data, f)]));
      for (const field of ["hrv_device", "hrv_protocol", "resting_hr_device", "resting_hr_protocol"]) payload[field] = formText(data, field);
      await mutate("checkin", payload, "Check-in saved. Today's recommendation recalculated.");
    } else if (form.id === "plan-form") {
      const sport = formText(data, "sport_type");
      await mutate("plan", { date: formText(data, "date"), title: formText(data, "title"),
        sport_type: sport, duration_min: formNumber(data, "duration_min"), session_rpe: formNumber(data, "session_rpe"),
        key: data.has("key"), ...(sport === "strength" ? strengthPayload(data) : {}) }, "Plan session saved locally.");
    } else if (form.id === "complete-form") {
      const dose = view().athlete.adjustments[view().today]?.recommendation ?? view().recommendation;
      await mutate("complete", { duration_min: formNumber(data, "duration_min"),
        session_rpe: formNumber(data, "session_rpe"), distance_km: formNumber(data, "distance_km"),
        ...(dose.sport_type === "strength" ? strengthPayload(data) : {}) }, "Actual session saved. Eligible Micro Wins verified.");
      const dialog = el("log-dialog");
      if (dialog instanceof HTMLDialogElement) dialog.close();
    } else if (form.id === "import-form") {
      const input = el("csv-file");
      const file = input instanceof HTMLInputElement ? input.files?.[0] : null;
      if (!file) throw new Error("Choose a CSV file.");
      if (file.size > 1_500_000) throw new Error("CSV exceeds the 1.5 MB local import limit.");
      await mutate("import", { csv: await file.text() }, "CSV validated and saved. Matching dates replaced.");
      form.reset();
    }
  } catch (error) {
    if (errorNode instanceof HTMLElement) {
      errorNode.textContent = errorText(error);
      errorNode.hidden = false;
    } else showError(error);
  } finally {
    setBusy(false);
  }
});

document.addEventListener("click", async event => {
  const target = event.target instanceof Element ? event.target.closest("[data-action], [data-topic], [data-close], [data-scroll]") : null;
  if (!(target instanceof HTMLElement)) return;
  if (target.dataset.close) {
    const dialog = el(target.dataset.close);
    if (dialog instanceof HTMLDialogElement) dialog.close();
    return;
  }
  if (target.dataset.scroll) {
    window.setTimeout(() => document.getElementById(target.dataset.scroll ?? "")?.scrollIntoView({ behavior: "smooth", block: "start" }), 30);
    return;
  }
  event.preventDefault();
  if (busy) return;
  const action = target.dataset.action;
  if (action === "retry") {
    if (athletes.length === 0) await initialize(); else await loadAthlete();
    return;
  }
  if (!state) return;
  if (action === "data") return openData();
  if (action === "log") return openLog();
  if (action === "edit-plan") {
    const session = view().athlete.plan.find(s => s.date === target.dataset.date);
    if (!session) return;
    el("plan-editor").outerHTML = planForm(session);
    el("plan-editor").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  setBusy();
  try {
    if (action === "accept") {
      await mutate("accept", {}, "Recovery adjustment accepted. Smart Training win verified.");
    } else if (action === "snapshot") {
      await mutate("snapshot", {}, "Decision snapshot saved with original inputs, rules and references.");
    } else if (target.dataset.topic) {
      const topic = target.dataset.topic;
      const data = await request(`/api/athletes/${encodeURIComponent(selected)}/coach`, { topic });
      if (!isCoachReply(data)) throw new Error("Unexpected coach response.");
      messages.push({ user: true, text: target.textContent ?? topic });
      messages.push({ user: false, text: data.answer, meta: `${data.as_of} UTC · ${data.source} · ${data.trace.rule_version} · provisional product cuts` });
      coachTrace = data.trace;
      render();
      const thread = document.querySelector(".coach-thread");
      thread?.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
    }
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
});
document.addEventListener("change", event => {
  const target = event.target;
  if (target instanceof HTMLSelectElement && target.id === "athlete-select") {
    selected = target.value;
    const url = new URL(location.href);
    url.searchParams.set("athlete", selected);
    history.replaceState(null, "", url);
    const dialog = el("data-dialog");
    if (dialog instanceof HTMLDialogElement) dialog.close();
    const form = el("import-form");
    if (form instanceof HTMLFormElement) form.reset();
    el("import-error").hidden = true;
    loadAthlete();
  }
  if (target instanceof HTMLSelectElement && target.name === "sport_type") {
    const section = target.form?.querySelector(".strength-inputs");
    if (section instanceof HTMLElement) section.hidden = target.value !== "strength";
  }
});
el("open-data").addEventListener("click", openData);
window.addEventListener("hashchange", () => {
  render();
  if (busy) setBusy();
  window.scrollTo(0, 0);
});
async function initialize() {
  try {
    const data = await request("/api/athletes");
    if (!isAthletes(data)) throw new Error("Unexpected athlete-list response.");
    athletes = data;
    const picker = el("athlete-select");
    if (picker instanceof HTMLSelectElement) {
      picker.innerHTML = athletes.map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join("");
      picker.value = selected;
    }
    await loadAthlete();
  } catch (error) {
    showError(error);
    el("main").setAttribute("aria-busy", "false");
    el("main").innerHTML = `<div class="empty"><h1>The local server is unavailable.</h1><p>Start the backend, then use Retry connection. No fallback metrics are shown.</p></div>`;
  }
}
initialize();
