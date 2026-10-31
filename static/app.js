import {
  $,
  safe,
  request,
  sample,
  busy,
  notify,
  jsonPost,
  savedOnly,
} from "./ui.js";
let snapshot = savedOnly,
  version = 0,
  activeIncident = null;
function render(incident, trace = []) {
  activeIncident = incident;
  const state = incident.state,
    refs = new Set(state.diagnosis.evidence_refs),
    mode = state.reasoning.diagnostician;
  $("status").textContent = incident.status.replaceAll("_", " ");
  $("investigation").innerHTML =
    `<div class="panel result"><div class="panel-head"><h2>${safe(state.scenario_name)}</h2><span class="mono quiet">v${incident.version}</span></div><div class="notice"><span class="badge">${safe(mode)}</span><h3>${safe(state.diagnosis.summary)}</h3><span class="mono">${safe(state.diagnosis.root_cause)}</span></div><div class="timeline">${trace.map((event, i) => `<div class="step"><b>${i + 1}</b><p>${safe(event.event_type.replaceAll(".", " / ").replaceAll("_", " "))}<br><span class="quiet mono">${safe(event.created_at)}</span></p></div>`).join("")}</div><div class="evidence-grid">${state.evidence.map((tool) => `<article class="evidence"><h3>${safe(tool.tool.replaceAll("_", " "))}</h3>${tool.items.map((item) => `<p>${refs.has(item.id) ? '<span class="badge">Cited evidence</span><br>' : ""}<span class="mono quiet">${safe(item.id)}</span><br>${safe(item.message || item.step || `${item.name}: ${item.current} ${item.unit} (baseline ${item.baseline})`)}</p>`).join("")}</article>`).join("")}</div><div class="decision"><span class="eyebrow">${state.proposal.abstained ? "Escalation" : "Proposed response"}</span><h3>${safe(state.proposal.action)}</h3><p>${safe(state.proposal.description)}</p>${state.approval ? `<p class="badge">${state.approval.approved ? "Approved" : "Rejected"} · ${safe(state.approval.actor)} (unverified label)</p>` : `<label for="reviewer">Reviewer label (unverified)</label><div class="form-row"><div><input id="reviewer" placeholder="Your name" maxlength="80"></div><button id="approve" class="primary">Approve simulation</button><button id="reject">Reject</button></div>`}<p class="mode-note">${safe(state.proposal.impact)}</p></div><details><summary>Inspect raw event payloads</summary><pre>${safe(JSON.stringify(trace, null, 2))}</pre></details></div>`;
  if (snapshot) {
    for (const id of ["reviewer", "approve", "reject"])
      if ($(id)) $(id).disabled = true;
  }
  for (const [id, approved] of [
    ["approve", true],
    ["reject", false],
  ])
    $(id)?.addEventListener("click", () =>
      busy($(id), async () => {
        if (snapshot)
          throw new Error(
            "Saved investigations are read-only. Use the live simulator to record a decision.",
          );
        const actor = $("reviewer").value.trim();
        if (actor.length < 2)
          throw new Error(
            "Enter a reviewer label with at least two characters.",
          );
        $("approve").disabled = true;
        $("reject").disabled = true;
        try {
          const updated = await request(
            `/api/incidents/${incident.id}/approval`,
            { ...jsonPost({ approved, actor }), key: "approval" },
          );
          const events = await request(`/api/incidents/${incident.id}/trace`, {
            key: "trace",
          });
          render(updated, events);
        } catch (error) {
          $("approve").disabled = false;
          $("reject").disabled = false;
          throw error;
        }
      }),
    );
}
function scenarios(items) {
  $("scenarios").innerHTML = items
    .map(
      (item) =>
        `<button class="scenario" data-id="${safe(item.id)}"><strong>${safe(item.name)}</strong><span>${safe(item.summary)}</span></button>`,
    )
    .join("");
  for (const button of document.querySelectorAll("[data-id]"))
    button.addEventListener("click", () => {
      if (savedOnly) {
        sample().then((data) => {
          const record = data.incidents?.[button.dataset.id];
          if (record) render(record.incident, record.trace);
        });
        return;
      }
      start(button.dataset.id, button);
    });
}
async function start(id, button) {
  snapshot = false;
  const token = ++version;
  for (const item of document.querySelectorAll(".scenario"))
    item.classList.toggle("selected", item === button);
  $("status").textContent = "Investigating";
  $("investigation").innerHTML =
    '<div class="panel"><span class="busy-indicator"></span> Gathering evidence…</div>';
  try {
    const incident = await request("/api/incidents", {
      ...jsonPost({ scenario: id }),
      key: "incident",
      timeout: 180000,
    });
    const trace = await request(`/api/incidents/${incident.id}/trace`, {
      key: "trace",
    });
    if (token === version) render(incident, trace);
  } catch (error) {
    if (token === version) {
      $("status").textContent = "Interrupted";
      $("investigation").innerHTML =
        `<div class="panel"><p class="error">${safe(error.message)}</p><button id="retry">Retry investigation</button></div>`;
      $("retry").addEventListener("click", () => start(id, button));
    }
  }
}
async function saved() {
  version++;
  snapshot = true;
  const data = await sample();
  scenarios(data.scenarios);
  render(data.incident, data.trace);
  $("benchmark").textContent = JSON.stringify(data.benchmark, null, 2);
  $("mode").innerHTML =
    "<strong>Saved investigation</strong> · Recorded sample, not a fresh model run. Approval is disabled in this walkthrough.";
}
$("saved").addEventListener("click", () => busy($("saved"), saved));
$("evaluate").addEventListener("click", () =>
  busy($("evaluate"), async () => {
    const data = await sample();
    const report = snapshot
      ? data.policy
      : await request("/api/evaluate", {
          ...jsonPost({
            cases: data.scenarios.map((item) => ({ scenario: item.id })),
          }),
          key: "eval",
          timeout: 180000,
        });
    $("eval-result").innerHTML =
      `<pre>${safe(JSON.stringify({ cases: report.cases, read_only_tools_rate: report.read_only_tools_rate, valid_evidence_rate: report.valid_evidence_rate, approval_gate_rate: report.approval_gate_rate, scope: report.scope }, null, 2))}</pre>`;
  }),
);
if (savedOnly) saved().catch((error) => notify(error.message, true));
else
  request("/api/scenarios", { key: "scenarios", timeout: 15000 })
    .then(scenarios)
    .catch((error) => {
      $("scenarios").innerHTML =
        '<p class="error">The live simulator is unavailable. Load the saved investigation above.</p>';
      notify(error.message, true);
    });
