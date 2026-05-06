"use strict";

(function () {
  const config = window.CAMPAIGN_CONFIG || {};
  const basePrefix = document.body?.dataset?.basePrefix || "";
  const currentPage = document.body?.dataset?.page || "";

  const navItems = [
    { key: "index", label: "Index", href: "index.html" },
    { key: "methodology", label: "Methodology", href: "methodology.html" },
    { key: "responses", label: "District Responses", href: "responses/index.html" },
    { key: "toolkits", label: "Toolkits", href: "toolkits/index.html" },
    { key: "coalition", label: "Coalition", href: "coalition.html" },
    { key: "model-policy", label: "Model Policy", href: "model-policy.html" },
    { key: "legislation", label: "Legislation", href: "legislation.html" },
    { key: "join", label: "Join", href: "join.html" },
  ];

  function prefixHref(href) {
    return `${basePrefix}${href}`;
  }

  function resolveConfiguredHref(href) {
    if (!href) return href;
    if (/^(?:[a-z]+:|#|\/)/i.test(href)) {
      return href;
    }
    return prefixHref(href);
  }

  function buildMailtoHref(email, el) {
    const params = new URLSearchParams();
    const subject = el.getAttribute("data-mailto-subject");
    const body = el.getAttribute("data-mailto-body");

    if (subject) params.set("subject", subject);
    if (body) params.set("body", body);

    const query = params.toString();
    return query ? `mailto:${email}?${query}` : `mailto:${email}`;
  }

  function renderNav() {
    const mount = document.querySelector("[data-site-nav]");
    if (!mount) return;

    const links = navItems.map((item) => {
      const active = item.key === currentPage ? " is-active" : "";
      return `<a class="nav-link${active}" href="${prefixHref(item.href)}">${item.label}</a>`;
    }).join("");

    mount.innerHTML = `
      <nav class="site-nav" aria-label="Primary">
        <div class="nav-shell">
          <a class="nav-brand" href="${prefixHref("index.html")}">K–12 AI Transparency Index</a>
          <div class="nav-links">${links}</div>
        </div>
      </nav>
    `;
  }

  function assignConfiguredLinks() {
    document.querySelectorAll("[data-config-link]").forEach((el) => {
      const key = el.getAttribute("data-config-link");
      const href = resolveConfiguredHref(config[key]);
      if (href) {
        el.setAttribute("href", href);
      }
    });

    document.querySelectorAll("[data-config-email]").forEach((el) => {
      const key = el.getAttribute("data-config-email");
      const email = config[key];
      if (!email) return;

      const isMailto = el.tagName === "A";
      if (isMailto) {
        el.setAttribute("href", buildMailtoHref(email, el));
      }

      if (el.hasAttribute("data-fill-text")) {
        el.textContent = email;
      }
    });
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((el) => {
      el.textContent = value;
    });
  }

  function renderProgress() {
    const progress = config.campaignProgress || {};
    const impact = config.impactTracker || {};

    document.querySelectorAll("[data-progress-key]").forEach((el) => {
      const key = el.getAttribute("data-progress-key");
      if (!key) return;

      if (key === "statesRepresented") {
        const total = Number(progress.statesTarget || 50);
        el.textContent = `${Number(progress.statesRepresented || 0)} / ${total}`;
        return;
      }

      el.textContent = String(progress[key] ?? 0);
    });

    document.querySelectorAll("[data-impact-key]").forEach((el) => {
      const key = el.getAttribute("data-impact-key");
      if (!key) return;
      el.textContent = String(impact[key] ?? 0);
    });
  }

  renderNav();
  assignConfiguredLinks();
  renderProgress();
  setText("[data-year]", String(new Date().getFullYear()));
})();
