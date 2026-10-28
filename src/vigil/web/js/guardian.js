import { h, s, $, clear, api, TIER, inr, mmss, rid, sleep, reduced } from "./util.js";

const W = 640, H = 230, L = 88, R = 24, T = 14, B = 36;
const BANDS = [
  ["hold", 0.8, 1, "Hold"], ["friction", 0.5, 0.8, "Slow down"], ["nudge", 0.25, 0.5, "Heads-up"], ["allow", 0, 0.25, "OK"],
];
const y = (p) => T + (1 - p) * (H - T - B);

const st = { calls: [], call: null, tl: null, shown: 0, playing: false, revealed: false, token: 0, chat: rid() };

export async function initGuardian() {
  st.calls = await api("/v1/demo/calls");
  const list = $("#callList");
  for (const c of st.calls) {
    list.append(h("button", { type: "button", class: "call-btn", "data-id": c.id, "aria-pressed": "false", onclick: () => select(c.id) },
      h("strong", {}, c.title), h("span", {}, c.blurb)));
  }
  $("#lang").addEventListener("change", () => refresh());
  $("#senior").addEventListener("change", () => refresh());
  $("#play").addEventListener("click", play);
  $("#payBtn").addEventListener("click", () => reveal());
  $("#askForm").addEventListener("submit", ask);
  await select(st.calls[0].id);
}

const profile = () => ({
  user_id: "demo-user", preferred_language: $("#lang").value, senior: $("#senior").checked, trusted_contact_opted_in: true,
});

async function select(id) {
  st.call = st.calls.find((c) => c.id === id);
  for (const b of document.querySelectorAll(".call-btn")) b.setAttribute("aria-pressed", String(b.dataset.id === id));
  // Switch the warning language and senior default to match the call, then fetch the analysis.
  $("#lang").value = st.call.language;
  $("#senior").checked = !!st.call.senior;
  await refresh();
}

async function refresh() {
  st.token++;
  st.playing = false; st.revealed = false; st.shown = 0;
  $("#play").disabled = true;
  const c = st.call;
  st.tl = await api("/v1/conversation/timeline", {
    method: "POST", body: { profile: profile(), transcript: c.turns, txn: c.txn ?? undefined },
  });
  $("#play").disabled = false; $("#play").textContent = "Play call";
  clear($("#transcript"));
  $("#payBar").hidden = true;
  $("#why").hidden = true;
  drawThread();
  setVerdict(null);
}

function setVerdict(tier, o = {}) {
  const v = $("#verdict");
  v.className = `verdict t-${tier ?? "allow"}`;
  $("#vTier").textContent = tier ? (o.word ?? TIER[tier].name) : "Ready";
  $("#vScore").textContent = o.score != null ? `Scam risk ${Math.round(o.score * 100)} out of 100` : "";
  $("#vLine").textContent = o.line ?? (tier ? TIER[tier].live : "Press “Play call” to begin.");
  $("#vMsg").textContent = o.msg ?? "";
  const steps = clear($("#vSteps"));
  for (const t of o.steps ?? []) steps.append(h("li", {}, t));
  clear($("#vActions"));
}

function drawThread() {
  const svg = clear($("#thread"));
  const n = st.call.turns.length + (st.call.txn ? 1 : 0);
  const X = (i) => L + (n <= 1 ? 0 : (i / (n - 1)) * (W - L - R));
  for (const [t, lo, hi, label] of BANDS) {
    svg.append(s("rect", { class: `band-${t}`, x: 0, y: y(hi), width: W, height: y(lo) - y(hi) }));
    svg.append(s("text", { class: "band-label", x: 10, y: y((lo + hi) / 2) + 4 }, label));
  }
  // x labels (time of each sentence)
  st.call.turns.forEach((t, i) => svg.append(s("text", { class: "axis-label", x: X(i), y: H - 14, "text-anchor": "middle" }, mmss(t.t))));
  if (st.call.txn) {
    const px = X(n - 1);
    svg.append(s("line", { class: "pay-marker", x1: px, x2: px, y1: T, y2: H - B }));
    svg.append(s("text", { class: "pay-label", x: px, y: H - 14, "text-anchor": "middle" }, "Payment"));
  }
  st.geo = { X, n };
  const g = s("g", { id: "pts" });
  svg.append(g);
  plot();
}

function plot(final = null) {
  const g = $("#pts"); if (!g) return;
  clear(g);
  const pts = st.tl.points.slice(0, st.shown).map((p, i) => ({ x: st.geo.X(i), p: p.score, tier: p.tier }));
  if (final) pts.push({ x: st.geo.X(st.geo.n - 1), p: final.score, tier: final.tier });
  if (pts.length > 1) {
    g.append(s("polyline", { class: `thread-line${reduced() ? "" : " draw"}`, points: pts.map((q) => `${q.x},${y(q.p)}`).join(" ") }));
  }
  for (const q of pts) g.append(s("circle", { class: "thread-dot", cx: q.x, cy: y(q.p), r: 6, fill: `var(--${q.tier})` }));
}

function turnEl(t, i) {
  return h("li", { class: `turn ${t.speaker}`, "data-i": i },
    h("small", {}, `${t.speaker === "caller" ? "Caller" : "You"} · ${mmss(t.t)}`), t.text);
}

async function play() {
  if (st.playing) return;
  const token = ++st.token;
  st.playing = true; st.revealed = false; st.shown = 0;
  $("#payBar").hidden = true; $("#why").hidden = true;
  $("#play").textContent = "Playing…"; $("#play").disabled = true;
  const box = clear($("#transcript"));
  drawThread();
  setVerdict("allow", { line: "Listening…" });
  for (let i = 0; i < st.call.turns.length; i++) {
    if (token !== st.token) return;
    box.append(turnEl(st.call.turns[i], i));
    box.lastChild.scrollIntoView({ block: "nearest" });
    st.shown = i + 1;
    plot();
    const p = st.tl.points[i];
    for (const el of box.querySelectorAll(".latest")) el.classList.remove("latest");
    box.lastChild.classList.add("latest"); box.lastChild.style.setProperty("--tier", `var(--${p.tier})`);
    setVerdict(p.tier, { score: p.score });
    await sleep(reduced() ? 0 : 1100);
  }
  if (token !== st.token) return;
  st.playing = false;
  $("#play").textContent = "Play again"; $("#play").disabled = false;
  if (st.call.txn) {
    $("#payText").textContent = `Next: pay ${inr(st.call.txn.amount_inr)} to ${st.call.txn.payee_ref}`;
    $("#payBar").hidden = false;
    $("#payBtn").focus();
  } else {
    reveal();
  }
}

function reveal() {
  if (!st.tl || st.revealed || st.shown < st.call.turns.length) return;
  st.revealed = true;
  $("#payBar").hidden = true;
  const f = st.tl.final;
  plot(st.call.txn ? f : null);
  const iv = f.intervention;
  const held = f.tier === "hold";
  setVerdict(f.tier, {
    score: f.score, word: held ? "Payment held" : undefined,
    line: iv?.headline ?? (f.tier === "allow" ? "No sign of a scam in this call." : TIER[f.tier].live),
    msg: iv?.message ?? "", steps: iv?.steps ?? [],
  });
  const act = $("#vActions");
  if (f.actions.offer_trusted_contact_alert) {
    act.append(h("button", { type: "button", onclick: trustedContact }, "Alert my trusted contact"));
  }
  if (f.tier === "hold" || f.tier === "friction") {
    act.append(h("a", { class: "ghost", href: "tel:1930", style: "text-decoration:none;display:inline-block" }, "Call 1930"));
  }
  explain(f);
  $("#verdict").scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
}

function explain(f) {
  $("#why").hidden = false;
  const ul = clear($("#drivers"));
  const top = f.drivers.slice(0, 6);
  const max = Math.max(...top.map((d) => d.contribution), 1);
  for (const d of top) {
    ul.append(h("li", {}, h("span", {}, d.label),
      h("span", { class: "drv-bar", role: "img", "aria-label": `strength ${d.contribution.toFixed(1)}` }, h("i", { style: `width:${Math.max(6, (d.contribution / max) * 100)}%;--tier-color:var(--${f.tier})` }))));
  }
  for (const d of f.protective.slice(0, 2)) ul.append(h("li", {}, h("span", {}, `Lowers risk: ${d.label}`), h("span")));
  const ev = clear($("#evidence"));
  for (const e of f.evidence.slice(0, 5)) {
    ev.append(h("li", {}, `“${e.excerpt}”`, " ", h("span", {}, `at ${mmss(e.t)}`)));
  }
  if (!f.evidence.length) ev.append(h("li", {}, "No suspicious phrases in the conversation."));
  highlight(f.evidence);
  const parts = [];
  if (f.first_flag_t != null) parts.push(`Vigil first raised a flag ${mmss(f.first_flag_t)} into the call.`);
  parts.push(f.ai_layer === "used" ? "Gemini added extra pattern checks." : "Rule-based check only. Gemini was not used.");
  parts.push("Scam risk is an estimate from hand-set weights, not a probability measured on real fraud.");
  $("#whyNote").textContent = parts.join(" ");
}

function highlight(evidence) {
  for (const e of evidence) {
    const li = $(`#transcript [data-i="${e.utterance_index}"]`);
    if (!li) continue;
    const needle = e.excerpt.replace(/ \(AI\)$/, "").toLowerCase();
    const walker = [...li.childNodes].find((n) => n.nodeType === 3 && n.nodeValue.toLowerCase().includes(needle));
    if (!walker) continue;
    const at = walker.nodeValue.toLowerCase().indexOf(needle);
    const mid = walker.splitText(at); const rest = mid.splitText(needle.length);
    const mark = h("mark", {}, mid.nodeValue); mid.replaceWith(mark); void rest;
  }
}

async function trustedContact() {
  const dlg = $("#dlg");
  $("#dlgBody").textContent = "Vigil will message the person you chose: “Someone may be pressuring a family member to send money right now. Please call them.” No account details are shared.";
  dlg.returnValue = "";
  dlg.showModal();
  dlg.addEventListener("close", () => {
    if (dlg.returnValue === "ok") {
      $("#vActions").append(h("p", { class: "ok" }, "Alert approved. Demo only, so nothing was sent."));
    }
  }, { once: true });
}

async function ask(e) {
  e.preventDefault();
  const text = $("#askText").value.trim();
  if (!text) return;
  const out = $("#askOut");
  out.textContent = "Checking…";
  try {
    const r = await api("/v1/agents/chat", { method: "POST", body: { session_id: st.chat, message: text, language: $("#lang").value } });
    out.textContent = r.reply || "No reply.";
    for (const a of r.approvals ?? []) out.append(h("span", {}, `\nWaiting for your approval: ${a.tool}`));
  } catch (err) {
    out.textContent = `Could not check: ${err.message}`;
  }
}
