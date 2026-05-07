# Ghostbadger Report Templates

This directory contains report templates and their assets. When running via Docker, this directory is bind-mounted from `./resources/` on the host so you can edit everything freely without rebuilding the image.

## Directory Structure

```
resources/
  templates/
    mytpl.html        # Template markup (Vue + HTML)
    mytpl.css         # Template styles
  assets/
    mytpl/            # Per-template static files (logo, background, etc.)
      logo.png
    _evidence/        # Auto-populated at runtime — do not edit
```

> [!WARNING]
> The included templates are for demo purposes only. Do not use them for real client deliverables without reviewing and customizing them to your needs.

A template is active when both `templates/<name>.html` and `templates/<name>.css` exist with the same stem. The name is what appears in the template selector in the UI.

> [!TIP]
> The demo templates included here are based on [SysReptor](https://github.com/Syslifters/sysreptor) templates. If you already have SysReptor templates, you can copy them into `templates/` and adapt them for Ghostbadger with minimal changes — the rendering engine is the same.

---

## Creating a New Template

1. Create `templates/mytemplate.html` and `templates/mytemplate.css`
2. Optionally create `assets/mytemplate/` and put images there
3. The template will appear in the UI immediately (no restart needed)

---

## Template Markup

Templates are Vue 3 fragments rendered inside a headless browser. Use standard HTML with Vue directives and the special components listed below.

### Top-level Variables

| Variable | Type | Description |
|---|---|---|
| `report` | object | All Ghostwriter report fields |
| `finding_groups` | array | `[{ findings: [...] }]` |
| `pentesters` | array | Alias for `report.team` |

### Common `report.*` Fields

> [!IMPORTANT]
> `extra_fields` are custom fields defined in your Ghostwriter instance under **Commandcenter → Extra Field Configurations → Extra fields for Reports**. The field names listed below reflect our own setup — yours may differ. Check your Ghostwriter instance and adjust template references accordingly.


```
report.title
report.report_date
report.complete              # bool — false triggers watermark logic

report.client.name
report.client.short_name
report.client.address

report.company.name
report.company.short_name
report.company.address
report.company.email
report.company.twitter

report.project.start_date
report.project.end_date
report.project.codename
report.project.type

report.team                  # array of { name, email, phone, role, start_date, end_date, timezone, description }
report.recipient.name
report.recipient.job_title
report.recipient.email
report.recipient.phone

report.scope                 # array of { name, scope[], total, description, disallowed, requires_caution }
report.whitecards            # array of { title, description } — provided accounts / whitelisted items

report.extra_fields.about_us           # markdown — company/team intro
report.extra_fields.executive_summary  # markdown — high-level summary for management
report.extra_fields.attack_chain       # markdown — optional attack chain narrative
report.extra_fields.methodology        # markdown — testing methodology and approach
report.extra_fields.scope_text         # markdown — prose addendum to the scope list
report.extra_fields.disclaimer         # markdown — legal disclaimer / liability statement
report.extra_fields.appendix           # markdown — optional appendix (hidden when empty)

report.totals.findings        # total finding count
report.totals.findings_critical
report.totals.findings_high
report.totals.findings_medium
report.totals.findings_low
report.totals.findings_info
report.totals.team
report.totals.scope
```

### Finding Fields

Iterate findings with:

```html
<div v-for="finding in finding_groups[0].findings">
```

Each finding has:

```
finding.id
finding.title
finding.severity              # Title Case: "Critical" | "High" | "Medium" | "Low" | "Informational"
finding.severity_color_hex    # e.g. "#FF2600" — Ghostwriter's configured severity colour
finding.description
finding.impact
finding.recommendation
finding.mitigation
finding.replication_steps
finding.affected_entities
finding.references
finding.finding_type
finding.assigned_to
finding.cvss_score
finding.cvss_vector
finding.tags                  # string[] e.g. ["phishing", "CWE:89", "ATT&CK:T1190"]

# Augmented by Ghostbadger:
finding.cvss.level            # "critical" | "high" | "medium" | "low" | "info"
finding.cvss.level_number     # 1–5
finding.cvss.score            # float
finding.cvss.vector           # string

finding.evidence              # array of { path, friendly_name, caption, description }
```

### Evidence Images

Evidence is fetched from Ghostwriter when a report is generated and stored under `assets/_evidence/`. Reference images using the `path` field directly as the `src`:

```html
<img :src="ev.path" v-for="ev in finding.evidence" />
```

---

## Special Components

These are provided by the SysReptor rendering bundle.

### `<markdown>`
Renders a Ghostwriter markdown field as HTML:
```html
<markdown :text="report.extra_fields.executive_summary" />
```

### `<pagebreak />`
Forces a page break at that point in the PDF.

### `<table-of-contents>`
Generates a TOC from all headings with `class="in-toc"`:
```html
<table-of-contents id="toc" v-slot="tocItems">
  <ul>
    <li v-for="item in tocItems" :class="'toc-level' + item.level">
      <ref :to="item.id" />
    </li>
  </ul>
</table-of-contents>
```

Each `item` exposes `id`, `level`, `title`, and `attrs` (all HTML attributes of the source element). Use `data-*` attributes on headings to pass metadata into TOC entries:
```html
<!-- on the heading -->
<h2 :id="'f' + finding.id" class="in-toc" :data-tags="(finding.tags || []).join(',')">

<!-- in the TOC -->
<li :class="{'highlight': item.attrs['data-tags']?.includes('phishing')}">
```

### `<ref>`
Cross-reference to another element by id. Renders as heading text or page number depending on context:
```html
<ref :to="'f' + finding.id" />                       <!-- heading text -->
<ref :to="'f' + finding.id" class="ref-page" />      <!-- page number -->
```

### `<comma-and-join>`
Joins named slots with commas and "and":
```html
<comma-and-join>
  <template #critical v-if="report.totals.findings_critical > 0">
    <strong>{{ report.totals.findings_critical }} Critical</strong>
  </template>
  <template #high v-if="report.totals.findings_high > 0">
    <strong>{{ report.totals.findings_high }} High</strong>
  </template>
</comma-and-join>
```

### `<list-of-figures>`
Generates a list of all `<figure>` elements with `<figcaption>`:
```html
<list-of-figures id="lof" v-slot="items">
  <div v-if="items.length > 0">
    <h2 class="in-toc numbered">Figure List</h2>
    <ul>
      <li v-for="item in items"><ref :to="item.id" /></li>
    </ul>
  </div>
</list-of-figures>
```
Figures must be wrapped in `<figure>/<figcaption>` to appear in this list.

### `<chart>`
Renders a Chart.js chart:
```html
<chart :width="15" :height="10" :config="{
  type: 'bar',
  data: { labels: [...], datasets: [{ data: [...], backgroundColor: [...] }] },
  options: { plugins: { legend: { display: false } } }
}" />
```
Use `cssvar('--color-risk-critical')` to reference CSS variables inside chart config.

---

## Page Layout (CSS)

Headers and footers use CSS `position: running()` — elements placed in running positions appear on every page. Use `data-sysreptor-generated="page-header"` / `"page-footer"` and `data-sysreptor-rendersections="always"` so they render on every page including the cover.

```html
<div data-sysreptor-generated="page-header" data-sysreptor-rendersections="always">
  <div id="header-right"><img src="mytemplate/logo.png" /></div>
</div>
```

```css
#header-right { position: running(header-right); }
@page { @top-right { content: element(header-right); } }
```

Footer works the same with `position: running(footer-left/center/right)` and `@bottom-left/center/right`.

### Page Margins

```css
@page {
  size: A4 portrait;
  margin: 35mm 20mm 25mm 20mm; /* top right bottom left */
}
```

### Numbered Headings

Add `class="in-toc numbered"` to any heading to include it in the TOC and auto-number it:

```html
<h1 id="findings" class="in-toc numbered">Findings</h1>
```

---

## Risk Color Classes

Define these in your template CSS to enable dynamic severity styling. The `finding.cvss.level` value (`critical`, `high`, `medium`, `low`, `info`) can be used to apply them dynamically:

```html
<td :class="'risk-bg-' + finding.cvss.level">{{ finding.cvss.score }}</td>
```

```css
.risk-critical { color: #FF2600; font-weight: bold; }
.risk-high     { color: #FF9300; font-weight: bold; }
.risk-medium   { color: #FFDA00; font-weight: bold; }
.risk-low      { color: #0096FF; font-weight: bold; }
.risk-info     { color: #00AE51; font-weight: bold; }

.risk-bg-critical { background-color: #FF2600; color: white; }
.risk-bg-high     { background-color: #FF9300; }
.risk-bg-medium   { background-color: #FFDA00; }
.risk-bg-low      { background-color: #0096FF; }
.risk-bg-info     { background-color: #00AE51; }
```

---

## Assets

Static files (logos, backgrounds) go in `assets/<templatename>/` and are referenced relative to the `assets/` directory:

```html
<img src="mytemplate/logo.png" />
```

---

## Template Utilities

These are available globally in all template expressions:

| Utility | Example |
|---|---|
| `lodash` | `lodash.capitalize(finding.cvss.level)` |
| `cssvar(name)` | `cssvar('--color-risk-critical')` — reads a CSS variable (use inside chart configs) |
| `formatDate(date, style?, locale?)` | `formatDate(report.report_date, 'long')` |

---

## Tips

- No restart needed after editing — templates are read from disk on every render
- Guard optional fields with `v-if="field"` to avoid blank sections — whitespace-only strings are normalised to `null` by the pipeline before reaching the template
- Use `finding.tags` (string array) to conditionally style findings — e.g. badges, TOC highlights
- The `testing` template is the most complete reference — start by copying it
