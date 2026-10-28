import { h, $, clear, api, inr } from "./util.js";

const WORD = { approve: "Approved", step_up: "Needs your OK", deny: "Blocked" };
let cases = [];

export async function initPayments() {
  cases = await api("/v1/agent-payments/cases");
  const list = $("#caseList");
  for (const c of cases) {
    list.append(h("button", { type: "button", class: "case-btn", "data-id": c.case_id, "aria-pressed": "false", onclick: () => select(c.case_id) },
      h("strong", {}, c.title), h("span", {}, c.story)));
  }
  await select(cases[0].case_id);
}

function kv(pairs) {
  return h("dl", {}, pairs.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));
}

async function select(id) {
  for (const b of document.querySelectorAll(".case-btn")) b.setAttribute("aria-pressed", String(b.dataset.id === id));
  const c = cases.find((x) => x.case_id === id);
  const r = await api("/v1/agent-payments/verify-demo", { method: "POST", body: { case_id: id } });
  const v = r.verdict;
  const i = c.intent, k = c.cart;
  const injected = k.notes && /ignore|instruction|do not flag|mark this/i.test(k.notes);
  const view = clear($("#caseView"));
  view.append(h("article", { class: "case-card" },
    h("h3", {}, c.title),
    h("p", { class: "story" }, c.story),
    h("div", { class: "verdict-row" }, h("span", { class: `badge ${v.decision}` }, WORD[v.decision]),
      h("span", { class: "hint" }, v.decision === r.expected ? "Matches what we expect for this scenario." : `Expected ${r.expected}.`)),
    h("div", { class: "pair" },
      h("div", {}, h("h4", {}, "What you signed"), kv([
        ["Task", i.description], ["Budget", inr(i.max_amount_inr)],
        ["Categories", (i.allowed_categories ?? []).join(", ") || "any"],
        ["Stores", (i.allowed_merchants ?? ["any"]).join(", ")], ["Agent", c.agent_id],
      ])),
      h("div", {}, h("h4", {}, "What the store sent"), kv([
        ["Store", k.merchant_id], ["Items", k.items.map((x) => `${x.title} × ${x.qty}`).join("; ")], ["Total", inr(k.total_inr)],
      ]), k.notes ? h("p", { class: injected ? "injected" : "hint" }, `Cart note: “${k.notes}”`) : null)),
    h("h4", {}, "What Vigil checked"),
    h("ul", { class: "checks" }, v.checks.map((ch) => h("li", {},
      h("span", { class: ch.passed ? "v" : "x", "aria-label": ch.passed ? "passed" : "failed" }, ch.passed ? "✓" : "✗"),
      h("span", {}, ch.name.replaceAll("_", " "), h("small", {}, ch.detail)))))),
  );
}
