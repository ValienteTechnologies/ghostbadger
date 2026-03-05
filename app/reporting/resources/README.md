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

```
report.title
report.report_date
report.complete              # bool — false triggers watermark logic

report.client.name
report.client.address
report.company.name
report.company.address

report.project.start_date
report.project.end_date

report.team                  # array of { name, email, phone, role }
report.recipient.name

report.scope                 # array of { name, scope[], disallowed }

report.extra_fields.about_us
report.extra_fields.executive_summary
report.extra_fields.attack_chain
report.extra_fields.methodology
report.extra_fields.scope_text
report.extra_fields.provided_users
report.extra_fields.disclaimer
report.extra_fields.appendix_sections  # array of { title, content }

report.totals.findings_critical
report.totals.findings_high
report.totals.findings_medium
report.totals.findings_low
report.totals.findings_info
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
finding.severity          # "critical" | "high" | "medium" | "low" | "informational"
finding.description
finding.impact
finding.recommendation
finding.replication_steps
finding.affected_entities
finding.references
finding.cvss_score
finding.cvss_vector

# Augmented by Ghostbadger:
finding.cvss.level         # "critical" | "high" | "medium" | "low" | "info"
finding.cvss.level_number  # 1–5
finding.cvss.score         # float
finding.cvss.vector        # string

finding.evidence           # array of { path, friendly_name, caption, description }
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

---

## Page Layout (CSS)

Headers and footers use CSS `position: running()` — elements placed in running positions appear on every page.

```html
<div id="header-right" data-sysreptor-generated="page-header">
  <img src="mytemplate/logo.png" />
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

These CSS classes are defined in the base stylesheet:

| Class | Use |
|---|---|
| `.risk-critical/high/medium/low/info` | Colored text, bold |
| `.risk-bg-critical/high/medium/low/info` | Colored background |

Use dynamically with `:class="'risk-bg-' + finding.cvss.level"`.

---

## Assets

Static files (logos, backgrounds) go in `assets/<templatename>/` and are referenced relative to the `assets/` directory:

```html
<img src="mytemplate/logo.png" />
```

---

## Tips

- No restart needed after editing — templates are read from disk on every render
- Guard optional fields with `v-if="field && field.trim()"` to avoid blank sections
- `lodash` is available globally (e.g. `lodash.capitalize(finding.cvss.level)`)
- The `testing` template is the most complete reference — start by copying it
