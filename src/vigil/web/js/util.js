// Small DOM + API helpers. Never uses innerHTML: all server text goes through textContent.
export function h(tag, attrs = {}, ...kids) {
  const ns = ["svg", "path", "line", "circle", "rect", "text", "g", "title", "polyline", "defs", "marker"].includes(tag) && attrs.__svg;
  const el = ns ? document.createElementNS("http://www.w3.org/2000/svg", tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "__svg" || v === undefined || v === null || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
export const s = (tag, attrs = {}, ...kids) => h(tag, { ...attrs, __svg: true }, ...kids);
export const $ = (sel, root = document) => root.querySelector(sel);
export const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

export async function api(path, { method = "GET", body, headers = {}, key } = {}) {
  const opts = { method, headers: { Accept: "application/json", ...headers } };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = new Error(data.detail || data.title || `Request failed (${res.status})`);
    e.status = res.status; throw e;
  }
  return data;
}

export const TIER = {
  allow: { name: "Looks fine", live: "Nothing worrying so far." },
  nudge: { name: "Heads-up", live: "Something about this call is off." },
  friction: { name: "Slow down", live: "This call shows classic scam pressure." },
  hold: { name: "Payment held", live: "This matches a known scam. Stop here." },
};
export const tierColor = (t) => `var(--${t})`;
export const inr = (n) => "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
export const pct = (x, d = 0) => (x * 100).toFixed(d) + "%";
export const mmss = (t) => `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`;
export const rid = () => Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, "0")).join("");
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
