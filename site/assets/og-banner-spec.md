# RuleDSL OpenGraph banner specification

This file is the reproducible design specification for the next `og-banner.png`.
The current PNG remains in place until it can be regenerated and visually reviewed;
no editable source or generation script for the existing binary is present in this
repository.

## Canvas and export

- Canvas: 1200 × 630 px, sRGB, opaque PNG.
- Keep all text inside a 96 px safe margin on every edge.
- Export at the exact canvas size; do not upscale a smaller raster.
- Verify legibility in a 600 × 315 px preview and with a centered 1.91:1 crop.

## Copy

Use exactly these three lines, with no additional product or version claims:

```text
RuleDSL
Executable Business Policies
Deterministic · Versioned · Auditable
```

`RuleDSL` is the product identity. Do not use `SDK` as the dominant label.

## Visual direction

- Preserve the site's restrained dark identity.
- Background: `#0f1117`, optionally with a subtle radial glow using `#6c8cff`
  below 18% opacity.
- Primary text: `#eef0f6`.
- Product accent: `#7f9cff`.
- Supporting accent: `#5ddbd1`.
- Use a system sans-serif stack; do not introduce an external font dependency.
- Left-align the copy on a simple grid. Use high contrast and generous spacing.
- Avoid diagrams, screenshots, tiny version text, performance claims, stock imagery,
  logos from third parties and decorative elements that compete with the wording.

## Suggested hierarchy

- `RuleDSL`: 42–52 px, semibold, accent color.
- `Executable Business Policies`: 70–82 px, bold, primary text, no more than two lines.
- `Deterministic · Versioned · Auditable`: 30–36 px, medium, supporting accent.

## Regeneration checklist

1. Produce an editable source alongside this specification before replacing the PNG
   (SVG, design-tool source, or a documented script are acceptable).
2. Export `site/assets/og-banner.png` at 1200 × 630 px.
3. Confirm the metadata URL in `site/index.html` still resolves under
   `/RuleDSL-SDK/assets/og-banner.png`.
4. Preview the export at LinkedIn/Twitter card sizes and check the safe margins.
5. Record the source and export method in the pull request.
