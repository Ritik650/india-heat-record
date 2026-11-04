# Dashboard design tokens

Generated with Stitch (project `6032385907136677847`, screen `2cc93b0ab2ff410ea78e889f36acf6c3`) before the Grafana dashboard was built, then applied to its panels. Grafana sets the layout grid, so the design's grid became panel positions rather than code.

| Token | Value | Used for |
|---|---|---|
| Background | `#f7f9fb` | Page behind the panels |
| Surface | `#ffffff` | Panels |
| Text | `#191c1e` | Titles and values |
| Muted text | `#45474c` | Axis labels and notes |
| Hairline | `#e2e8f0` | Panel borders and gridlines |
| Cool | `#2a78d6` | Cool end of the warming scale, and the single-series colour |
| Warm | `#d03b3b` | Warm end of the warming scale |
| Neutral midpoint | `#f0efec` | Middle of the diverging scale |
| Font | Inter, falling back to the system sans | All text |

The design asked for four things that carry into the panels: summary tiles before detail, colour only on data, no gradients, and thin hairlines in place of heavy cards.

The cool and warm values replace Stitch's `#0284c7` and `#dc2626` with colours from the validated chart palette, because the static charts, the dashboard and the site should use one scale.

The live site in `site/` uses the same screen's layout: a top bar, a title with its scope note, summary tiles, a map beside a ranked list, a grid of chart panels and a severity-coded quality table. Stitch's sample numbers, map image and branding were placeholders, and none of them are used. Every figure on the site comes from `data/mart`.
