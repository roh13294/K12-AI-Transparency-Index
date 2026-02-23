
// script.js — GitHub Pages safe, matches current index.html IDs


let districts = [];


// ---------- helpers ----------
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
  // Matches your earlier tier outputs
  if (score >= 75) return "Leading Transparency";
  if (score >= 60) return "Emerging Governance";
  if (score >= 55) return "Limited Disclosure";
  if (score >= 30) return "Minimal Transparency";
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
  return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
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
  ].filter(Boolean).join(" | ");


  return `
    <tr>
      <td>${district}</td>
      <td><span class="pill">${state}</span></td>
      <td>${score}</td>
      <td>${tier}</td>
      <td>${signals}</td>
      <td>${links || ""}</td>
    </tr>
  `;
}


// ---------- UI + filtering ----------
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


  const qRaw = (qEl && qEl.value) ? qEl.value.trim().toLowerCase() : "";
  const filter = (fEl && fEl.value) ? fEl.value : "ALL";


  let out = districts;


  if (qRaw) {
    out = out.filter((d) => {
      const name = String(d.district || "").toLowerCase();
      const st = String(d.state || "").toLowerCase();
      return name.includes(qRaw) || st.includes(qRaw);
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


// Optional: set headline stats from the loaded dataset
function setStatsFromData() {
  const n = districts.length;


  const scores = districts.map((d) => toNum(d.index_score));
  const avg = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const zeros = scores.filter((s) => s === 0).length;
  const zeroPct = n ? (zeros * 100 / n) : 0;


  const dEl = document.getElementById("statDistricts");
  const aEl = document.getElementById("statAvg");
  const zEl = document.getElementById("statZero");


  if (dEl) dEl.textContent = String(n);
  if (aEl) aEl.textContent = avg.toFixed(2);
  if (zEl) zEl.textContent = `${zeros} (${zeroPct.toFixed(2)}%)`;
}


async function init() {
  try {
    setStatus("Loading districts...");


    const res = await fetch("data/district_scores.json", { cache: "no-store" });
    if (!res.ok) {
      setStatus(`Failed to load data (HTTP ${res.status}). Check data/district_scores.json is committed.`);
      return;
    }


    districts = await res.json();


    // Stats
    setStatsFromData();


    // Hook up listeners (match index.html IDs)
    const searchEl = document.getElementById("searchInput");
    const filterEl = document.getElementById("scoreFilter");


    if (searchEl) searchEl.addEventListener("input", applyFilters);
    if (filterEl) filterEl.addEventListener("change", applyFilters);


    applyFilters();
  } catch (e) {
    console.error(e);
    setStatus("Error loading districts. Check console and confirm data/district_scores.json is valid JSON.");
  }
}


init();
