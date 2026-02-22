let districts = [];

const NATIONAL = {
  districts: 1913,
  avg: 17.07,
  zero: "715 (37.38%)"
};

function setStats() {
  document.getElementById("statDistricts").textContent = NATIONAL.districts;
  document.getElementById("statAvg").textContent = NATIONAL.avg;
  document.getElementById("statZero").textContent = NATIONAL.zero;
}

function signalsFound(d) {
  const hits = [];
  if (d.public_ai_policy_exists === "1") hits.push("AI policy");
  if (d.ai_use_publicly_disclosed === "1") hits.push("Disclosure");
  if (d.oversight_named === "1") hits.push("Oversight");
  if (d.board_policy_mentions_ai === "1") hits.push("Board mention");
  if (d.public_contact_available === "1") hits.push("Public contact");
  if (hits.length === 0) return "None found";
  return hits.join(", ");
}

function linksCell(d) {
  const parts = [];
  if (d.homepage) parts.push(`<a class="a" href="${d.homepage}" target="_blank" rel="noreferrer">Homepage</a>`);
  if (d.found_policy_url) parts.push(`<a class="a" href="${d.found_policy_url}" target="_blank" rel="noreferrer">Policy</a>`);
  if (d.found_tech_url) parts.push(`<a class="a" href="${d.found_tech_url}" target="_blank" rel="noreferrer">Tech</a>`);
  if (d.found_contact_url) parts.push(`<a class="a" href="${d.found_contact_url}" target="_blank" rel="noreferrer">Contact</a>`);
  return parts.length ? parts.join(" | ") : "";
}

function rowHtml(d) {
  const score = Number(d.index_score);
  return `
    <tr>
      <td>${escapeHtml(d.district || "")}</td>
      <td><span class="badge">${escapeHtml(d.state || "")}</span></td>
      <td class="num">${isNaN(score) ? "" : score}</td>
      <td>${escapeHtml(d.tier || "")}</td>
      <td>${escapeHtml(signalsFound(d))}</td>
      <td>${linksCell(d)}</td>
    </tr>
  `;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function applyFilters() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const sf = document.getElementById("scoreFilter").value;

  let out = districts;

  if (q) {
    out = out.filter(d =>
      (d.district || "").toLowerCase().includes(q) ||
      (d.state || "").toLowerCase().includes(q)
    );
  }

  if (sf !== "all") {
    if (sf === "60") out = out.filter(d => Number(d.index_score) >= 60);
    else out = out.filter(d => String(d.index_score) === sf);
  }

  const tbody = document.getElementById("tbody");
  tbody.innerHTML = out.slice(0, 1000).map(rowHtml).join("");

  const loading = document.getElementById("loading");
  loading.textContent = out.length > 1000
    ? `Showing first 1000 of ${out.length} results. Narrow your search to refine.`
    : `${out.length} results.`;
}

async function init() {
  setStats();

  const res = await fetch("data/district_scores.json");
  districts = await res.json();

  document.getElementById("search").addEventListener("input", applyFilters);
  document.getElementById("scoreFilter").addEventListener("change", applyFilters);

  applyFilters();
}

init();
