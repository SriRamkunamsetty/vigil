import { h, $, clear, api, pct } from "./util.js";

const KIND = {
  used_car: "Buying a used car", family_real: "Real family emergency", landlord_rent: "Paying new landlord rent",
  police_verification: "Genuine police verification", friend_split: "Splitting a bill", delivery_cod: "Delivery payment",
  bank_advisory: "Bank safety messages", bank_care_genuine: "Genuine bank call", advisor_sip: "Investment advisor",
  insurance_premium: "Insurance premium", plain_payment: "Ordinary payments",
};
const LANG = { en: "English", hi: "Hindi", hinglish: "Hinglish", te: "Telugu" };

const bars = (rows, warn = () => false) => h("div", { class: "bars" }, rows.map(([label, v, extra]) =>
  h("div", { class: `bar-row${warn(v) ? " warn" : ""}` }, h("span", {}, label),
    h("span", { class: "track" }, h("i", { style: `width:${Math.max(1, v * 100)}%` })), h("span", { class: "num" }, extra ?? pct(v)))));

export async function initEval() {
  const body = clear($("#evalBody"));
  let r;
  try { r = await api("/v1/eval/results"); }
  catch { $("#evalDisclaimer").textContent = "No results yet. Run vigil-eval to create them."; return; }
  const c = r.conversations;
  $("#evalDisclaimer").textContent = `${r.disclaimer} ${c.n.toLocaleString("en-IN")} made-up conversations and payments, ${pct(c.scam_share)} of them scams. We compare Vigil with simpler approaches on the same data.`;

  const fused = c.systems.find((x) => x.system === "Vigil fused");
  const unseen = c.fused_recall_by_wording_family.unseen.recall;
  const seen = c.fused_recall_by_wording_family.seen.recall;
  const worst = Object.entries(c.benign_friction_by_kind).sort((a, b) => b[1].friction_or_hold_rate - a[1].friction_or_hold_rate)[0];

  const grid = h("div", { class: "eval-grid" });
  body.append(grid);

  grid.append(h("section", { class: "eval-card" }, h("h3", {}, "Scams caught vs. honest customers bothered"),
    h("p", { class: "lead" }, "At the “slow down or hold” level. Higher catch rate is better, lower false alarms is better. Ranges are 95% confidence."),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Approach"), h("th", { class: "num" }, "Scams caught"), h("th", { class: "num" }, "False alarms"))),
      h("tbody", {}, c.systems.map((x) => h("tr", { class: x.system === "Vigil fused" ? "me" : "" },
        h("td", {}, x.system === "Vigil fused" ? "Vigil (call + payment together)" : x.system),
        h("td", { class: "num" }, `${pct(x.friction.recall)} (${pct(x.friction.recall_ci[0])}–${pct(x.friction.recall_ci[1])})`),
        h("td", { class: "num" }, pct(x.friction.fpr, 1))))))));

  grid.append(h("section", { class: "eval-card" }, h("h3", {}, "Catch rate by wording"),
    h("p", { class: "lead" }, "“Seen” scam wording is similar to what the rules were written from. “Unseen” is paraphrased. The gap is the main weakness."),
    bars([["Seen wording", seen], ["Unseen wording", unseen]], (v) => v < 0.6),
    h("h4", {}, "By language"),
    bars(Object.entries(c.fused_recall_by_language).map(([k, v]) => [`${LANG[k] ?? k} (${v.n})`, v.recall]))));

  grid.append(h("section", { class: "eval-card" }, h("h3", {}, "Honest customers who got friction anyway"),
    h("p", { class: "lead" }, "Situations that look like scams but are not. Share of cases where Vigil asked for “slow down” or “hold”."),
    bars(Object.entries(c.benign_friction_by_kind).sort((a, b) => b[1].friction_or_hold_rate - a[1].friction_or_hold_rate)
      .map(([k, v]) => [KIND[k] ?? k, v.friction_or_hold_rate, pct(v.friction_or_hold_rate, 1)]), (v) => v > 0.05)));

  const t = c.time_to_intervene;
  grid.append(h("section", { class: "eval-card" }, h("h3", {}, "Speed and timing"),
    h("table", {}, h("tbody", {},
      row("Time to decide (median / slowest 5%)", `${c.latency_ms.p50} ms / ${c.latency_ms.p95} ms`),
      row("Warned before the payment", `${pct(t.share_warned_before_payment)} of scam calls`),
      row("Median warning lead time", `${Math.round(t.median_lead_seconds)} seconds before payment`),
      row("Score calibration error", c.calibration_ece.toFixed(3))))));

  const n = r.network;
  const rules = Object.entries(n.rules);
  grid.append(h("section", { class: "eval-card" }, h("h3", {}, "Finding mule accounts"),
    h("p", { class: "lead" }, `${n.true_mules} mule accounts hidden among ${n.accounts.toLocaleString("en-IN")}, plus ${n.hard_negative_accounts} look-alikes (shops, payroll, charities).`),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Rule"), h("th", { class: "num" }, "Precision"), h("th", { class: "num" }, "Found"), h("th", { class: "num" }, "Look-alikes hit"))),
      h("tbody", {}, rules.map(([k, v]) => h("tr", { class: k.startsWith("Vigil") ? "me" : "" },
        h("td", {}, k), h("td", { class: "num" }, pct(v.precision)), h("td", { class: "num" }, pct(v.recall)), h("td", { class: "num" }, String(v.hard_negatives_flagged))))))));

  const ex = r.exchange;
  grid.append(h("section", { class: "eval-card" }, h("h3", {}, "Sharing across banks"),
    h("p", { class: "lead" }, "Scams with no call transcript, only payment details."),
    bars([["One bank alone", ex.without_exchange.recall], ["Banks sharing", ex.with_exchange.recall]]),
    h("p", { class: "hint" }, "This jump is overstated: in our made-up data scammers reuse the same payees, which real ones do less often.")));

  body.append(h("section", { class: "eval-card limits", style: "margin-top:1.25rem" }, h("h3", {}, "Limits you should know about"),
    h("ul", { class: "caveats" },
      h("li", {}, "Everything above uses synthetic data written by us. It shows how the approaches compare, not how Vigil would do against real fraud."),
      h("li", {}, `Paraphrased scams are caught ${pct(unseen)} of the time against ${pct(seen)} for familiar wording. Gemini is meant to close this gap. That needs a live model, so it is not measured here.`),
      h("li", {}, `${KIND[worst[0]] ?? worst[0]} still gets friction ${pct(worst[1].friction_or_hold_rate)} of the time, because a large first payment looks like a scam payment.`),
      h("li", {}, "Mule accounts are found almost perfectly because we built the data and the detector. Real networks are messier."),
      h("li", {}, "Warnings in Hindi and Telugu need review by native speakers before any real use."))));
}

function row(k, v) { return h("tr", {}, h("td", {}, k), h("td", { class: "num" }, v)); }
