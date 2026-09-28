# PPT Creation Agent

Designs a slide-by-slide deck with Claude and builds it with `python-pptx`.

## Standalone usage
```bash
# From scratch, Claude's own judgment on content and layout
python run.py --brief "Q3 board update: revenue, churn, roadmap"

# Fill an existing .pptx template's real layouts/placeholders
python run.py --brief "Q3 board update" --template CompanyTemplate.pptx

# Use a PDF as a *reference* (text/images only — approximate, not exact)
python run.py --brief "Q3 board update" --template old_report.pdf
```

## As a Claude Code subagent
`Agent({ subagent_type: "ppt-creator", prompt: "Create a 6-slide deck on our Q3 results using CompanyTemplate.pptx" })`

## Notes
- `.pptx` templates are filled using their **real** slide layouts and
  placeholders — Claude is shown the actual layout names/placeholder list
  and must pick from them.
- `.pdf` templates have no editable slide structure, so they're used only as
  a content/image reference; the output deck is built from the default
  built-in layouts, not a reproduction of the PDF's exact visual design.
- Extracted images from a PDF reference are only inserted into the output
  deck when Claude decides they're relevant to a specific slide.
