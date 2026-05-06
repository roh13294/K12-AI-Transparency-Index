// script.js — legacy fallback copy of the index table logic.
// It is currently not loaded by the live pages, which use dashboard.js.
// Keep this file only as a non-authoritative reference unless the site wiring changes.

"use strict";

let districts = [];

// ---------- tiny DOM helpers ----------
function $(id) {
  return document.getElementById(id);
}

function setText(id, text) {
  const el = $(id);
  if (el) el.textContent = text;
}

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

// If tier is missing in JSON, compute it from score
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
  const safe = esc(url);
  return `<a href="${safe}" target="_blank" rel="noopener">${esc(label)}</a>`;
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
      <td>${links}</td>
    </tr>
  `;
}

// ---------- render + filters ----------
function renderRows(list) {
  const tbody = $("districtTableBody");
  if (!tbody) return;

  const cap = 1000;
  const shown = list.slice(0, cap);

  tbody.innerHTML = shown.map(rowHtml).join("");

  if (list.length > cap) {
    setText("statusText", `Showing first ${cap} of ${list.length} results. Narrow your search to refine.`);
  } else {
    setText("statusText", `${list.length} results.`);
  }
}

function applyFilters() {
  const qEl = $("searchInput");
  const fEl = $("scoreFilter");

  const q = (qEl?.value || "").trim().toLowerCase();
  const filter = (fEl?.value || "ALL").toUpperCase();

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

  setText("statDistricts", String(n));
  setText("statAvg", avg.toFixed(2));
  setText("statZero", `${zeros} (${zeroPct.toFixed(2)}%)`);
}

async function init() {
  // these IDs exist in your index.html, but we still guard anyway
  setText("statusText", "Loading districts...");

  try {
    // Use a relative path that works for localhost AND GitHub Pages
    const res = await fetch("./data/district_scores.json", { cache: "no-store" });
    if (!res.ok) {
      setText("statusText", `Failed to load data (HTTP ${res.status}). Check data/district_scores.json is committed.`);
      return;
    }

    districts = await res.json();
    setStatsFromData();

    $("searchInput")?.addEventListener("input", applyFilters);
    $("scoreFilter")?.addEventListener("change", applyFilters);

    applyFilters();
  } catch (e) {
    console.error(e);
    setText("statusText", "Error loading districts. Check console + confirm district_scores.json is valid JSON.");
  }
}

// IMPORTANT: wait until DOM is loaded (fixes your null/textContent crash)
window.addEventListener("DOMContentLoaded", init);
