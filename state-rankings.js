"use strict";

(function () {
  let nationalSummary = null;
  let stateRecords = [];

  function $(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => {
      switch (char) {
        case "&":
          return "&amp;";
        case "<":
          return "&lt;";
        case ">":
          return "&gt;";
        case '"':
          return "&quot;";
        case "'":
          return "&#39;";
        default:
          return char;
      }
    });
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
  }

  function setClass(id, className) {
    const el = $(id);
    if (el) el.className = className;
  }

  function formatScore(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num.toFixed(1) : "—";
  }

  function formatPercent(rate) {
    const num = Number(rate);
    return Number.isFinite(num) ? `${(num * 100).toFixed(1)}%` : "—";
  }

  function formatDistrictCount(count) {
    return `${count} district${count === 1 ? "" : "s"} audited`;
  }

  function tierCellHtml(tiers) {
    return `
      <div class="tier-stack">
        <span>Leading: ${tiers.leading_transparency}</span>
        <span>Emerging: ${tiers.emerging_governance}</span>
        <span>Limited: ${tiers.limited_disclosure}</span>
        <span>Minimal: ${tiers.minimal_transparency}</span>
        <span>No public signals: ${tiers.no_public_signals}</span>
      </div>
    `;
  }

  function rowHtml(record) {
    return `
      <tr>
        <td>${record.rank}</td>
        <td>
          <span class="table-strong">${esc(record.state_name)}</span>
          <span class="table-subtle">${esc(record.state_code)}</span>
        </td>
        <td>${record.districts_audited}</td>
        <td>${formatScore(record.average_score)}</td>
        <td>${formatScore(record.median_score)}</td>
        <td>
          <span class="table-strong">${esc(record.highest_scoring_district)}</span>
          <span class="table-subtle">Score ${record.highest_score}</span>
        </td>
        <td>
          <span class="table-strong">${esc(record.lowest_scoring_district)}</span>
          <span class="table-subtle">Score ${record.lowest_score}</span>
        </td>
        <td>${tierCellHtml(record.tier_distribution)}</td>
      </tr>
    `;
  }

  function sortRecords(records, sortValue) {
    const list = [...records];

    switch (sortValue) {
      case "avg-asc":
        return list.sort((a, b) => a.average_score - b.average_score || a.state_name.localeCompare(b.state_name));
      case "districts-desc":
        return list.sort((a, b) => b.districts_audited - a.districts_audited || b.average_score - a.average_score);
      case "districts-asc":
        return list.sort((a, b) => a.districts_audited - b.districts_audited || b.average_score - a.average_score);
      case "state-asc":
        return list.sort((a, b) => a.state_name.localeCompare(b.state_name));
      case "state-desc":
        return list.sort((a, b) => b.state_name.localeCompare(a.state_name));
      case "median-desc":
        return list.sort((a, b) => b.median_score - a.median_score || b.average_score - a.average_score);
      case "median-asc":
        return list.sort((a, b) => a.median_score - b.median_score || b.average_score - a.average_score);
      case "avg-desc":
      default:
        return list.sort((a, b) => b.average_score - a.average_score || b.districts_audited - a.districts_audited);
    }
  }

  function setTableStatus(text, isError) {
    const el = $("stateStatusText");
    if (!el) return;
    el.textContent = text;
    setClass("stateStatusText", isError ? "status is-error" : "status");
  }

  function applyTable() {
    const tbody = $("stateTableBody");
    if (!tbody) return;

    const query = ($("stateSearchInput")?.value || "").trim().toLowerCase();
    const sortValue = $("stateSortSelect")?.value || "avg-desc";

    let filtered = stateRecords;
    if (query) {
      filtered = filtered.filter((record) => {
        return record.state_name.toLowerCase().includes(query) || record.state_code.toLowerCase().includes(query);
      });
    }

    const sorted = sortRecords(filtered, sortValue);
    tbody.innerHTML = sorted.map(rowHtml).join("");

    if (sorted.length === 0) {
      setTableStatus("No matching states found.");
      return;
    }

    setTableStatus(`Showing ${sorted.length} state summaries.`);
  }

  function renderStateOverview() {
    if (!nationalSummary) return;

    setText("overviewStates", String(nationalSummary.states_covered));
    setText("overviewDistricts", String(nationalSummary.districts_audited));
    setText("overviewAverage", formatScore(nationalSummary.national_average_score));
    setText("overviewHighestState", nationalSummary.highest_average_state.state_name);
    setText(
      "overviewHighestStateNote",
      `${formatScore(nationalSummary.highest_average_state.average_score)} average | ${formatDistrictCount(nationalSummary.highest_average_state.districts_audited)}`
    );
    setText("overviewLowestState", nationalSummary.lowest_average_state.state_name);
    setText(
      "overviewLowestStateNote",
      `${formatScore(nationalSummary.lowest_average_state.average_score)} average | ${formatDistrictCount(nationalSummary.lowest_average_state.districts_audited)}`
    );
    setText("overviewMedianState", formatScore(nationalSummary.median_state_average));
    setText("stateGeneratedAt", nationalSummary.generated_at);
  }

  function renderPolicyEvidence() {
    if (!nationalSummary) return;

    const highest = nationalSummary.highest_average_state;
    const lowest = nationalSummary.lowest_average_state;

    setText("evidenceDistricts", String(nationalSummary.districts_audited));
    setText("evidenceStates", String(nationalSummary.states_covered));
    setText("evidenceAverage", formatScore(nationalSummary.national_average_score));
    setText(
      "evidenceZero",
      `${nationalSummary.zero_score_districts} (${formatPercent(nationalSummary.zero_score_rate)})`
    );
    setText("evidenceVariation", `${highest.state_name} to ${lowest.state_name}`);
    setText(
      "evidenceVariationNote",
      `${formatScore(highest.average_score)} highest average | ${formatScore(lowest.average_score)} lowest average`
    );
    setText(
      "policyEvidenceStatus",
      "State variation reflects the audited districts in this dataset. Sample sizes vary by state."
    );
  }

  async function loadStateData() {
    const statePage = $("stateTableBody") || $("overviewStates");
    const policyPage = $("evidenceDistricts");
    if (!statePage && !policyPage) return;

    if ($("stateStatusText")) {
      setTableStatus("Loading state summaries...");
    }

    if ($("policyEvidenceStatus")) {
      setText("policyEvidenceStatus", "Loading evidence cards...");
    }

    let response;
    try {
      response = await fetch("data/state_rankings.json", { cache: "no-store" });
    } catch (error) {
      if (window.location.protocol === "file:") {
        setTableStatus("Browsers block loading JSON over file://. Preview the site through a local server.", true);
      } else {
        setTableStatus("Unable to load state summary data.", true);
      }
      if ($("policyEvidenceStatus")) {
        setText("policyEvidenceStatus", "Unable to load the state evidence summary.");
      }
      return;
    }

    if (!response.ok) {
      setTableStatus(`Failed to load data (HTTP ${response.status}).`, true);
      if ($("policyEvidenceStatus")) {
        setText("policyEvidenceStatus", "Unable to load the state evidence summary.");
      }
      return;
    }

    const payload = await response.json();
    nationalSummary = payload?.national_summary || null;
    stateRecords = Array.isArray(payload?.states) ? payload.states : [];

    if (!nationalSummary || stateRecords.length === 0) {
      setTableStatus("Loaded state data but found no rows.", true);
      if ($("policyEvidenceStatus")) {
        setText("policyEvidenceStatus", "Loaded the file but did not find usable state summaries.");
      }
      return;
    }

    renderStateOverview();
    renderPolicyEvidence();

    if ($("stateSearchInput")) {
      $("stateSearchInput").addEventListener("input", applyTable);
    }

    if ($("stateSortSelect")) {
      $("stateSortSelect").addEventListener("change", applyTable);
    }

    applyTable();
  }

  document.addEventListener("DOMContentLoaded", () => {
    loadStateData().catch((error) => {
      console.error("State rankings initialization failed:", error);
      setTableStatus("JavaScript crashed while building the state table.", true);
      if ($("policyEvidenceStatus")) {
        setText("policyEvidenceStatus", "JavaScript crashed while loading the evidence cards.");
      }
    });
  });
})();
