import { api, $ } from "./util.js";
import { initGuardian } from "./guardian.js";
import { initNetwork } from "./network.js";
import { initPayments } from "./payments.js";
import { initEval } from "./evaluation.js";

const inits = { guardian: initGuardian, network: initNetwork, payments: initPayments, eval: initEval };
const done = new Set();
const tabs = [...document.querySelectorAll("[role=tab]")];

function show(name) {
  for (const t of tabs) {
    const on = t.id === `t-${name}`;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
  }
  if (!done.has(name)) { done.add(name); inits[name]().catch((e) => console.error(name, e)); }
  history.replaceState(null, "", `#${name}`);
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => show(t.id.slice(2)));
  t.addEventListener("keydown", (e) => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    const n = tabs[(i + d + tabs.length) % tabs.length];
    n.focus(); show(n.id.slice(2));
  });
});

api("/v1/meta").then((m) => {
  $("#status").textContent = m.llm_enabled
    ? "Gemini is helping explain decisions. The decision itself is rule-based."
    : "Running without Gemini: rule-based checks only. Demo data is synthetic.";
}).catch(() => { $("#status").textContent = "Could not reach the Vigil service."; });

const start = location.hash.slice(1);
show(inits[start] ? start : "guardian");
