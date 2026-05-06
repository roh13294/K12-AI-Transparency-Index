"use strict";

// dashboard.js — ONLY for index.html

let districts = [];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => {
    switch (c) {
      case "&": return "&amp;";
      case "<": return "&lt;";
      case ">": return "&gt;";
      case '"': return "&quot;";
      case "'": return "&#39;";
      default: return c;
    }
  });
}

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function tierFromScore(score) {
  if (score >= 80) return "Leading Transparency";
  if (score >= 60) return "Emerging Governance";
  if (score >= 40) return "Limited Disclosure";
  if (score >= 20) return "Minimal Transparency";
  return "No Public AI Governance Signals";
}

function signalsFound(d) {
  const signals = [];
  if (toNum(d.public_ai_policy_exists) === 1) signals.push("AI policy");
  if (toNum(d.ai_use_publicly_disclosed) === 1) signals.push("Disclosure");
  if (toNum(d.oversight_named) === 1) signals.push("Oversight");
  if (toNum(d.board_policy_mentions_ai) === 1) signals.push("Board policy");
  if (toNum(d.public_contact_available) === 1) signals.push("Public contact");
  return signals.length ? signals.join(", ") : "None found";
}

function linkOrEmpty(label, url) {
  if (!url) return "";
  return `<a class="link" href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
}

function actionHref(d) {
  const params = new URLSearchParams({
    district: d.district || "",
    state: d.state || "",
    score: String(toNum(d.index_score)),
    tier: d.tier || tierFromScore(toNum(d.index_score)),
    homepage: d.homepage || "",
    policy: d.found_policy_url || "",
    tech: d.found_tech_url || "",
    contact: d.found_contact_url || "",
  });
  return `toolkits/parent_request.html?${params.toString()}`;
}

function rowHtml(d) {
  const district = esc(d.district || "");
  const state = esc(d.state || "");
  const score = toNum(d.index_score);
  const tier = esc(d.tier || tierFromScore(score));
  const signals = esc(signalsFound(d));

  const links = [
    linkOrEmpty("Homepage", d.homepage),
    linkOrEmpty("Policy", d.found_policy_url),
    linkOrEmpty("Tech", d.found_tech_url),
    linkOrEmpty("Contact", d.found_contact_url),
  ].filter(Boolean).join(" <span class='sep'>|</span> ");

  const action = `<a class="btn small secondary" href="${actionHref(d)}">Take action</a>`;

  return `
    <tr>
      <td>${district}</td>
      <td><span class="pill">${state}</span></td>
      <td>${score}</td>
      <td>${tier}</td>
      <td>${signals}</td>
      <td>${links}</td>
      <td>${action}</td>
    </tr>
  `;
}

function setStatus(text) {
  const el = document.getElementById("statusText");
  if (el) el.textContent = text;
}

function renderRows(list) {
  const tbody = document.getElementById("districtTableBody");
  if (!tbody) return;

  const cap = 1000;
  const shown = list.slice(0, cap);
  tbody.innerHTML = shown.map(rowHtml).join("");

  if (list.length > cap) {
    setStatus(`Showing first ${cap} of ${list.length} results. Narrow your search to refine.`);
  } else {
    setStatus(`${list.length} results.`);
  }
}

function applyFilters() {
  const qEl = document.getElementById("searchInput");
  const fEl = document.getElementById("scoreFilter");

  const q = (qEl?.value || "").trim().toLowerCase();
  const filter = fEl?.value || "ALL";

  let out = districts;

  if (q) {
    out = out.filter((d) => {
      const name = String(d.district || "").toLowerCase();
      const st = String(d.state || "").toLowerCase();
      return name.includes(q) || st.includes(q);
    });
  }

  out = out.filter((d) => {
    const s = toNum(d.index_score);
    if (filter === "ALL") return true;
    if (filter === "ZERO") return s === 0;
    if (filter === "LOW") return s >= 1 && s <= 30;
    if (filter === "MID") return s >= 31 && s <= 60;
    if (filter === "HIGH") return s >= 61;
    return true;
  });

  renderRows(out);
}

function setStatsFromData() {
  const n = districts.length;
  const scores = districts.map((d) => toNum(d.index_score));
  const avg = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const zeros = scores.filter((s) => s === 0).length;
  const zeroPct = n ? (zeros * 100 / n) : 0;

  document.getElementById("statDistricts").textContent = String(n);
  document.getElementById("statAvg").textContent = avg.toFixed(2);
  document.getElementById("statZero").textContent = `${zeros} (${zeroPct.toFixed(2)}%)`;
}

async function init() {
  setStatus("Loading districts...");

  let res;
  try {
    res = await fetch("data/district_scores.json", { cache: "no-store" });
  } catch (err) {
    if (window.location.protocol === "file:") {
      setStatus("Error: Browsers block loading JSON data via file:// protocol. Please use a local web server (e.g. python3 -m http.server)");
    } else {
      setStatus("Network error failed to load district data.");
    }
    return;
  }

  if (!res.ok) {
    setStatus(`Failed to load data (HTTP ${res.status}) at data/district_scores.json`);
    return;
  }

  const data = await res.json();
  districts = Array.isArray(data) ? data : (data?.districts || data?.rows || []);

  if (!Array.isArray(districts) || districts.length === 0) {
    setStatus("Loaded JSON but found 0 rows. JSON might not be an array.");
    return;
  }

  setStatsFromData();

  document.getElementById("searchInput")?.addEventListener("input", applyFilters);
  document.getElementById("scoreFilter")?.addEventListener("change", applyFilters);

  applyFilters();
}

init().catch((e) => {
  console.error("Dashboard init error:", e);
  setStatus("JavaScript crashed during initialization. Check console for details.");
});
