# Icon sources and licensing

This catalog is curated from each source's own official/free assets, not
drawn or licensed by this project. See `build_catalog.py`'s own docstring
for exact download URLs (versioned, re-check before refreshing).

## aws/, gcp/, azure/

Official architecture icon packages from AWS, Google Cloud, and Microsoft
Azure respectively:
- AWS: per AWS's own icon usage guidelines (aws.amazon.com/architecture/icons/)
  -- free to use in architecture diagrams and related materials
  (whitepapers, presentations, data sheets, posters). No implied AWS
  endorsement.
- GCP: per Google Cloud's own icon terms (cloud.google.com/icons) -- free to
  use for referencing Google Cloud services/architecture.
- Azure: per Microsoft's own Azure Architecture Icons terms
  (learn.microsoft.com/en-us/azure/architecture/icons/) -- free to use for
  referencing Azure services/architecture. This package ships SVG only; the
  matching PNGs in azure/png/ were rasterized here via @resvg/resvg-js (see
  build_catalog.py), not provided by Microsoft.

## general/

Sourced from [Tabler Icons](https://tabler.io/icons) (`@tabler/icons` npm
package), MIT licensed (Copyright (c) 2020-2026 Paweł Kuna) -- free to use,
copy, modify, and distribute, including commercially, with the copyright
notice preserved here rather than per-icon. Original stroke color
(`currentColor`) was replaced with a fixed dark hex (`#0B0B0B`) before
rasterizing to PNG, since these are used as standalone image files, not
CSS-styled inline SVG.
