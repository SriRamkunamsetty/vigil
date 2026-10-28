import { h, s, $, clear, api, TIER, inr, rid } from "./util.js";

const W = 760, H = 420;
const st = { rings: [], sel: null, detail: null, payee: null };

export async function initNetwork() {
  const r = await api("/v1/network/rings");
  st.rings = r.rings;
  $("#netSummary").textContent = `${r.flagged_accounts} suspicious accounts among ${r.accounts.toLocaleString("en-IN")} in ${r.rings.length} rings`;
  const list = $("#ringList");
  for (const ring of r.rings) {
    list.append(h("button", { type: "button", class: "ring-btn", "data-id": ring.ring_id, "aria-pressed": "false", onclick: () => select(ring.ring_id) },
      h("strong", {}, `Ring ${ring.ring_id.slice(2)} · ${inr(ring.exposure_inr)}`),
      h("span", {}, `${ring.victims} senders, ${ring.accounts} linked accounts, ${ring.layering_depth} hops`)));
  }
  $("#approveForm").addEventListener("submit", publish);
  initEffect();
  if (r.rings.length) await select(r.rings[0].ring_id);
}

async function select(id) {
  for (const b of document.querySelectorAll(".ring-btn")) b.setAttribute("aria-pressed", String(b.dataset.id === id));
  const d = await api(`/v1/network/rings/${id}`);
  st.sel = id; st.detail = d;
  $("#publishOut").textContent = "";
  draw(d);
  $("#caseNote").hidden = false;
  $("#caseText").textContent = d.case_note;
  const ul = clear($("#acctList"));
  for (const a of d.top_accounts) {
    ul.append(h("li", {}, h("code", {}, a.account_id), ` · ${Math.round(a.score * 100)} out of 100`,
      a.reasons.length ? ` — ${a.reasons.slice(0, 3).join("; ")}` : ""));
  }
}

function layout(d) {
  const ids = new Set(d.nodes.map((n) => n.id));
  const kind = Object.fromEntries(d.nodes.map((n) => [n.id, n.kind]));
  const out = {};
  for (const e of d.edges) (out[e.src] ??= []).push(e.dst);
  // depth = hops from an entry account, so layers spread left to right
  const depth = {};
  const queue = d.nodes.filter((n) => n.kind === "entry").map((n) => n.id);
  queue.forEach((q) => (depth[q] = 0));
  while (queue.length) {
    const u = queue.shift();
    for (const v of out[u] ?? []) if (ids.has(v) && kind[v] !== "victim" && depth[v] === undefined) { depth[v] = depth[u] + 1; queue.push(v); }
  }
  const mid = Math.max(1, ...d.nodes.filter((n) => n.kind === "layer").map((n) => depth[n.id] ?? 1));
  const cols = {};
  for (const n of d.nodes) {
    const c = n.kind === "victim" ? 0 : n.kind === "entry" ? 1 : n.kind === "cashout" ? mid + 2 : 1 + (depth[n.id] ?? 1);
    (cols[c] ??= []).push(n);
  }
  const keys = Object.keys(cols).map(Number).sort((a, b) => a - b);
  const pos = {};
  keys.forEach((c, ci) => {
    const x = 70 + (keys.length === 1 ? 0 : (ci / (keys.length - 1)) * (W - 140));
    const nodes = cols[c];
    nodes.forEach((n, i) => { pos[n.id] = { x, y: 56 + ((i + 0.5) / nodes.length) * (H - 90), n }; });
  });
  return { pos, keys, cols };
}

function draw(d) {
  const svg = clear($("#graph"));
  const { pos, keys, cols } = layout(d);
  const defs = s("defs", {}, s("marker", { id: "arr", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto" },
    s("path", { d: "M0 0L10 5L0 10z", fill: "var(--muted)" })));
  svg.append(defs);
  const label = { victim: ["Senders", "paid in"], entry: ["Collectors", "first to receive"], layer: ["Pass-through", "moves it on"], cashout: ["Cash-out", "money leaves"] };
  for (const c of keys) {
    const sample = cols[c][0].kind; const [a, b] = label[sample];
    const x = pos[cols[c][0].id].x;
    svg.append(s("text", { class: "col-label", x, y: 18 }, a), s("text", { class: "col-sub", x, y: 33 }, b));
  }
  for (const e of d.edges) {
    const a = pos[e.src], b = pos[e.dst]; if (!a || !b) continue;
    const w = 0.8 + Math.log10(Math.max(10, e.amount)) * 0.45;
    const mx = (a.x + b.x) / 2;
    svg.append(s("path", { class: "edge", d: `M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`, "stroke-width": w, "marker-end": "url(#arr)" }));
  }
  for (const id in pos) {
    const { x, y, n } = pos[id];
    const r = n.kind === "victim" ? 5 : 9;
    const c = s("circle", { class: `node node-${n.kind}`, cx: x, cy: y, r, tabindex: 0, role: "button", "aria-label": `${n.kind} account ${n.id}` },
      s("title", {}, `${n.id}${n.reasons.length ? ": " + n.reasons.join("; ") : ""}`));
    const pick = () => {
      for (const el of svg.querySelectorAll(".node.sel")) el.classList.remove("sel");
      c.classList.add("sel");
      $("#graphCap").textContent = n.kind === "victim" ? `${n.id}: a sender who paid into this ring.`
        : `${n.id} (${Math.round(n.score * 100)} out of 100): ${n.reasons.join("; ") || "linked to the ring"}.`;
    };
    c.addEventListener("click", pick);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    svg.append(c);
  }
  const shown = d.nodes.filter((n) => n.kind === "victim").length;
  $("#graphCap").textContent = `Money flows left to right. Showing ${shown} of ${d.victims_total} senders. Select a dot to see why it was flagged.`;
}

async function publish(e) {
  e.preventDefault();
  const analyst = $("#analyst").value.trim();
  const out = $("#publishOut");
  try {
    const r = await api(`/v1/network/rings/${st.sel}/publish`, {
      method: "POST", body: { approved: true, analyst }, headers: { "X-Demo-Institution": "your-bank" },
    });
    out.textContent = `Approved by ${analyst}. Shared ${r.published} scrambled fingerprints with partner banks.`;
  } catch (err) { out.textContent = `Not shared: ${err.message}`; out.className = "hint"; }
}

/* ---------- network-effect demo ---------- */
function newPayee() { st.payee = `refund-desk-${rid().slice(0, 6)}@upi`; $("#payee").value = st.payee; }
async function snapshot(note) {
  const lk = await api("/v1/signals/lookup", { method: "POST", body: { kind: "payee", identifier: st.payee } });
  const a = await api("/v1/assess", {
    method: "POST", body: { profile: { user_id: "bank-c-customer" }, txn: { amount_inr: 20000, payee_ref: st.payee, payee_first_time: true } },
  });
  const status = lk.corroborated ? "Confirmed by 2 banks" : lk.reporters ? "Reported by 1 bank (warning only)" : "Nobody has reported it";
  const out = clear($("#effOut"));
  out.append(
    h("div", {}, "Banks that reported it", h("b", {}, String(lk.reporters))),
    h("div", {}, "What the payee looks like", h("b", {}, status)),
    h("div", {}, "Bank C customer pays ₹20,000", h("b", { style: `color:var(--${a.tier})` }, TIER[a.tier].name)),
  );
  if (note) out.append(h("p", { class: "hint", style: "grid-column:1/-1" }, note));
}
function initEffect() {
  newPayee(); snapshot();
  $("#effNew").addEventListener("click", () => { newPayee(); snapshot("New payee. Start again from Bank A."); });
  const report = (bank, note) => async () => {
    await api("/v1/signals/publish", { method: "POST", body: { kind: "payee", identifier: st.payee }, headers: { "X-Demo-Institution": bank } });
    await snapshot(note);
  };
  $("#effA").addEventListener("click", report("bank-a", "One report is a warning. Vigil asks for a closer look but does not block."));
  $("#effB").addEventListener("click", report("bank-b", "Two independent banks agree, so the flag is now strong. One mistaken bank cannot do this alone."));
  $("#effC").addEventListener("click", () => snapshot("This is what a customer of a third bank sees right now."));
}
