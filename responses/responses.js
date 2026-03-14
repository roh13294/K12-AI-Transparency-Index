"use strict";

const districtResponses = [
  {
    name: "Beecher Community School District",
    score: 0,
    dateContacted: "2026-03-14",
    status: "Contacted"
  },
  {
    name: "Plainwell Community Schools",
    score: 0,
    dateContacted: "2026-03-14",
    status: "Contacted"
  },
  {
    name: "Homer Community Schools",
    score: 0,
    dateContacted: "2026-03-14",
    status: "Contacted"
  }
];

function renderResponses() {
  const tbody = document.getElementById("responsesTableBody");
  if (!tbody) return;

  tbody.innerHTML = districtResponses.map(d => {
    const statusClass = "status-" + d.status.toLowerCase().replace(/\s+/g, '-');
    return `
      <tr>
        <td>${d.name}</td>
        <td>${d.score}</td>
        <td>${d.dateContacted}</td>
        <td><span class="pill ${statusClass}">${d.status}</span></td>
      </tr>
    `;
  }).join('');
}

document.addEventListener("DOMContentLoaded", renderResponses);
