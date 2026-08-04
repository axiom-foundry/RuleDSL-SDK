# RuleDSL OpenGraph banner specification

The committed `og-banner.png` is exported from the editable, repository-native
[`og-banner.svg`](og-banner.svg). The SVG contains all shapes, colors and copy; it
does not load fonts, images or other resources from the network.

## Canvas and export

- Canvas: 1200 × 630 px, browser-rendered RGB using sRGB CSS colors, opaque PNG; an embedded ICC profile is not required.
- Keep all text inside a 96 px safe margin on every edge.
- Export at the exact canvas size; do not upscale a smaller raster.
- Verify legibility in a 600 × 315 px preview and with a centered 1.91:1 crop.

## Copy

Use exactly these three content lines, with no additional product or version claims.
The middle line may wrap at the documented canvas size:

```text
RuleDSL
Executable Business Policies
Deterministic · Versioned · Replayable
```

`RuleDSL` is the product identity. Do not use `SDK` as the dominant label.

## Visual direction

- Preserve the site's restrained dark identity.
- Background: `#0f1117`, with the source's subtle radial glows below 18% opacity.
- Primary text: `#eef0f6`.
- Product accent: `#7f9cff`.
- Supporting accent: `#5ddbd1`.
- Use the system `Segoe UI, Arial, sans-serif` stack; do not load an external font.
- Left-align the copy on the source's simple grid. Use high contrast and generous spacing.
- Avoid diagrams, screenshots, tiny version text, performance claims, stock imagery,
  third-party logos and decorative elements that compete with the wording.

## Hierarchy

- `RuleDSL`: 52 px, bold, accent color.
- `Executable Business Policies`: 78 px, bold, primary text, wrapped to two visual lines.
- `Deterministic · Versioned · Replayable`: 34 px, semibold, supporting accent.

## Export procedure

The committed raster was rendered on Windows with Microsoft Edge
`151.0.4129.59`. From the repository root, use an empty temporary browser profile
and the exact viewport below:

```powershell
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$root = (Resolve-Path ".").Path
$profile = Join-Path ([IO.Path]::GetTempPath()) "ruledsl-og-export-$PID"
New-Item -ItemType Directory -Path $profile | Out-Null
try {
    $svgUrl = "file:///$(($root -replace '\\', '/'))/site/assets/og-banner.svg"
    $edgeArgs = @(
        "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--window-size=1200,630",
        "--user-data-dir=$profile",
        "--screenshot=$root\site\assets\og-banner.png",
        $svgUrl
    )
    $process = Start-Process -FilePath $edge -ArgumentList $edgeArgs -Wait `
        -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "Edge export failed: $($process.ExitCode)" }
} finally {
    Remove-Item -LiteralPath $profile -Recurse -Force
}
```

Two clean exports in that recorded environment produced the same SHA-256:

```text
f98d709bab98d920bfbed73d274551cd2f4f8e05848bd7303c054b3fc6de5a00
```

The source and command make regeneration deterministic within the recorded
browser/OS/font-rendering environment. PNG bytes can differ across browser builds,
operating systems or installed font versions; do not claim cross-environment byte
reproducibility. The export must still satisfy the dimensions, opacity and visual
checks below.

## Regeneration checklist

1. Edit `site/assets/og-banner.svg`; do not edit the PNG directly.
2. Export `site/assets/og-banner.png` at 1200 × 630 px with the documented command.
3. Confirm the raster is opaque and its copy matches the SVG.
4. Confirm the metadata URL in `site/index.html` still resolves under
   `/RuleDSL-SDK/assets/og-banner.png`.
5. Preview the export at 1200 × 630 and 600 × 315; check legibility and the 96 px
   source-canvas safe margin.
6. Record the renderer version and resulting SHA-256 in the pull request.
