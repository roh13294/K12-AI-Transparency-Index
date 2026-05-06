# K–12 AI Transparency Index

Version `v2.0`  
February 2026  
1,913 districts  
50 states

The K–12 AI Transparency Index is a student-led national project tracking public AI transparency signals across U.S. public school districts. It is designed to help students, families, educators, school boards, policymakers, and reporters understand whether districts publicly disclose basic information about AI use in schools.

The project focuses on public AI transparency signals only. It does not claim to measure internal district practices that are not publicly disclosed.

## What the site includes

- K–12 AI Transparency Index homepage
- District audit scores and searchable district table
- Methodology page
- District Responses page
- Public Toolkits
- Students for K–12 AI Transparency coalition layer
- Model District AI Transparency Policy
- Student AI Transparency and Human Review Act

## Core framing

- We are not anti-AI. We are pro-transparency.
- Students and families deserve to know when AI is used in schools, what data it processes, and what human protections exist.
- The index identifies transparency gaps. The coalition turns that evidence into action.

## Data and structure

Key repo files:

- `index.html`
- `methodology.html`
- `responses/index.html`
- `toolkits/index.html`
- `coalition.html`
- `join.html`
- `model-policy.html`
- `legislation.html`
- `dashboard.js`
- `site.js`
- `campaign-config.js`
- `style.css`
- `data/district_scores.json`
- `data/district_scores.csv`
- `data/state_summary.csv`

## Static GitHub Pages deployment

This site is a static GitHub Pages site built with HTML, CSS, and vanilla JavaScript.

### Local preview

From the repository root:

```bash
python3 -m http.server
```

Then open:

```text
http://localhost:8000/
```

### Publish on GitHub Pages

1. Push the repository to GitHub.
2. In the repository settings, enable GitHub Pages.
3. Set deployment to serve from the repository root or the configured Pages branch/root used by the project.
4. Confirm the site resolves under:

```text
https://roh13294.github.io/K12-AI-Transparency-Index/
```

All new links and assets are kept GitHub Pages compatible for deployment under `/K12-AI-Transparency-Index/`.

## Updating coalition launch content

- Update coalition counters in `campaign-config.js`
- Update the Join form URL in `campaign-config.js`
- Update contact placeholders in `campaign-config.js`
- Replace placeholder download links in `campaign-config.js`
