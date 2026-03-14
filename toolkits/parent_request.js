function getParam(name) {
  return new URLSearchParams(window.location.search).get(name) || "";
}

function cleanUrl(u) {
  u = (u || "").trim();
  return u;
}

function copyText(txt) {
  navigator.clipboard.writeText(txt);
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function wrapLines(doc, text, x, y, maxWidth, lineHeight) {
  const lines = doc.splitTextToSize(text, maxWidth);
  lines.forEach((line, i) => doc.text(line, x, y + i * lineHeight));
  return y + lines.length * lineHeight;
}

function buildEvidenceBlock(homepage, policy, tech, contact) {
  const parts = [];
  if (homepage) parts.push(`Homepage: ${homepage}`);
  if (policy) parts.push(`Policy page: ${policy}`);
  if (tech) parts.push(`Technology page: ${tech}`);
  if (contact) parts.push(`Contact page: ${contact}`);
  return parts.length ? parts.join("\n") : "No evidence links were captured in the automated crawl.";
}

function buildRequestLetter(d) {
  return `Subject: Request for district AI transparency and public disclosure

Hello [Superintendent / District Office],

I’m a parent/community member writing with a straightforward transparency request about AI use in ${d.district}.

I found your district in the National K–12 AI Transparency Index (score: ${d.score}/100, tier: ${d.tier}). The index only measures publicly visible signals, so I’m reaching out to verify what is currently documented and what can be shared publicly.

Could you please provide:

1) Whether the district has any written guidance on generative AI use by staff or students (policy, administrative guidelines, or memos).
2) Whether the district publicly discloses which AI tools are approved for classroom or administrative use.
3) Who is responsible for oversight of AI procurement and AI-related privacy/safety review (title is fine).
4) Where parents can find district-level information on AI use, data handling, and who to contact with concerns.

If something already exists publicly, a link is perfect. If it is internal, a short summary is still helpful.

Thank you for your time. I’m asking because families deserve clarity on what tools are being used and what safeguards exist.

Sincerely,
[Your name]
[Your city/state]
[Optional phone]

Evidence links captured by the crawler:
${buildEvidenceBlock(d.homepage, d.policy, d.tech, d.contact)}
`;
}

function buildBoardComment(d) {
  return `Hello Board Members,

My name is [Name] and I’m a parent/community member.

I’m here because AI tools are entering schools faster than public disclosure and oversight are keeping up. I checked ${d.district} in the National K–12 AI Transparency Index. The district currently scores ${d.score}/100 based on publicly visible transparency signals.

My request is simple:
1) Publish a short public page listing any approved AI tools and the purpose they are used for.
2) Name a point of accountability for AI oversight (a role/title is enough).
3) Publish a clear parent contact route for AI questions and concerns.

This is not about banning AI. It’s about basic transparency so families can trust what’s happening in classrooms and district systems.

Thank you.
`;
}

function makePdf(d) {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "pt", format: "letter" });

  const marginX = 54;
  let y = 64;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("K–12 AI Transparency — District Summary", marginX, y);
  y += 22;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  y = wrapLines(
    doc,
    `District: ${d.district}\nState: ${d.state}\nIndex score: ${d.score}/100\nTier: ${d.tier}`,
    marginX,
    y,
    504,
    14
  );
  y += 10;

  doc.setFont("helvetica", "bold");
  doc.text("Evidence links (public)", marginX, y);
  y += 16;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  y = wrapLines(doc, buildEvidenceBlock(d.homepage, d.policy, d.tech, d.contact), marginX, y, 504, 13);
  y += 10;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.text("What families can ask for (3 items)", marginX, y);
  y += 16;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  y = wrapLines(
    doc,
    "1) Public list of AI tools used (instruction + admin)\n2) Oversight owner (role/title) + review process\n3) Public parent contact route for AI questions",
    marginX,
    y,
    504,
    13
  );

  y += 18;
  doc.setFontSize(9);
  doc.text("Dashboard: https://roh13294.github.io/K12-AI-Transparency-Index/", marginX, y);

  const filenameSafe = `${d.state}_${d.district}`.replace(/[^\w\-]+/g, "_").slice(0, 80);
  doc.save(`${filenameSafe}_AI_Transparency_Summary.pdf`);
}

function init() {
  const d = {
    mode: getParam("mode") || "request",
    district: getParam("district"),
    state: getParam("state"),
    score: getParam("score"),
    tier: getParam("tier"),
    homepage: cleanUrl(getParam("homepage")),
    policy: cleanUrl(getParam("policy")),
    tech: cleanUrl(getParam("tech")),
    contact: cleanUrl(getParam("contact")),
  };

  document.getElementById("metaLine").textContent =
    `${d.district} | ${d.state} | Score ${d.score}/100 | ${d.tier}`;

  const card = `
    <div><strong>${d.district}</strong> (${d.state})</div>
    <div>Score: <strong>${d.score}/100</strong> | Tier: ${d.tier}</div>
    <div style="margin-top:8px;">
      ${d.homepage ? `<div>Homepage: <a target="_blank" rel="noopener" href="${d.homepage}">${d.homepage}</a></div>` : ""}
      ${d.policy ? `<div>Policy: <a target="_blank" rel="noopener" href="${d.policy}">${d.policy}</a></div>` : ""}
      ${d.tech ? `<div>Tech: <a target="_blank" rel="noopener" href="${d.tech}">${d.tech}</a></div>` : ""}
      ${d.contact ? `<div>Contact: <a target="_blank" rel="noopener" href="${d.contact}">${d.contact}</a></div>` : ""}
    </div>
  `;
  document.getElementById("districtCard").innerHTML = card;

  document.getElementById("hintLine").textContent =
    "Tip: If your district’s score is low, ask for a public AI tools list, an oversight owner, and a parent contact route. Simple transparency first.";

  const request = buildRequestLetter(d);
  const comment = buildBoardComment(d);

  document.getElementById("requestText").value = request;
  document.getElementById("commentText").value = comment;

  document.getElementById("btnCopyRequest").onclick = () => copyText(document.getElementById("requestText").value);
  document.getElementById("btnDownloadRequest").onclick = () =>
    downloadText(`${d.state}_${d.district}_parent_request.txt`.replace(/[^\w\-]+/g, "_"), document.getElementById("requestText").value);

  document.getElementById("btnCopyComment").onclick = () => copyText(document.getElementById("commentText").value);
  document.getElementById("btnDownloadComment").onclick = () =>
    downloadText(`${d.state}_${d.district}_board_comment.txt`.replace(/[^\w\-]+/g, "_"), document.getElementById("commentText").value);

  document.getElementById("btnCopyLinks").onclick = () =>
    copyText(buildEvidenceBlock(d.homepage, d.policy, d.tech, d.contact));

  document.getElementById("btnPdf").onclick = () => makePdf(d);

  // If someone hits #pdf, auto-generate immediately
  if (window.location.hash === "#pdf") {
    setTimeout(() => makePdf(d), 250);
  }

  // If mode=comment, scroll to comment section
  if ((d.mode || "").toLowerCase() === "comment") {
    setTimeout(() => document.getElementById("commentSection").scrollIntoView({ behavior: "smooth" }), 200);
  }
}

init();
