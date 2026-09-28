# AutoPulse — Phase 4: AI Concierge

## What to add

Add 1 new page to the existing AutoPulse app. Keep all existing pages and data unchanged.

Add to the sidebar last:
8. AI Concierge

---

## New Data

### personas.json
Three personas, each with id, name, role, accentColor, and a prompts array of 5 objects (each with id, label, question).

- **VP of Sales** (accent `#0064D2`) — Q4 Revenue Summary, Top Markets by Growth, EV Mix Trend, Competitive Landscape, Board Deck Bullets
- **Dealer Analyst** (accent `#420E71`) — Dealer Scorecard, Inventory Health, Days-to-Sale Analysis, Regional Gaps, Restock Recommendations
- **Market Strategist** (accent `#059669`) — Global Expansion Targets, Segment Mix Analysis, Asia Pacific Outlook, Price Point Sensitivity, Forecast Scenarios

### aiResponses.json
A flat object keyed by prompt question string. Each value is a 3–5 sentence automotive analytics response. Write one response per persona prompt (15 total).

### slideTemplates.json
4 templates: Executive Summary (navy `#132445`), Regional Deep Dive (teal `#0891B2`), Market Analysis (purple `#420E71`), Dealer Spotlight (amber `#D97706`). Each has id, name, description, primary (color hex).

---

## New Page

### AI Concierge
Three-column layout, full height.

**Left column (240px fixed):** Persona selector.
- Three persona cards — name, role, colored left border. Clicking selects the persona.
- Below the cards: 5 prompt buttons for the active persona. Clicking a button sends that question to the chat.

**Center column (flex):** Chat panel.
- User messages right-aligned in dark navy bubbles.
- AI responses left-aligned in white bubbles with a light border.
- While loading: a typing indicator (three bouncing dots).
- Text input at the bottom with a Send button. Enter key submits.
- All responses come from aiResponses.json — look up the question string to get the answer. If the question is not in the map, return a generic "I don't have data on that right now" message.
- **Each AI response must include an inline chart rendered below the text bubble.** Use a different chart type per response to showcase variety:
  - Bar chart (grouped or stacked) for comparisons (e.g. revenue by region, volume by make)
  - Line chart for trends over time (e.g. quarterly revenue, EV mix trend)
  - Area chart (stacked) for composition over time (e.g. segment mix by quarter)
  - Donut / pie chart for share breakdowns (e.g. market share, EV vs ICE split)
  - Horizontal bar chart for rankings (e.g. top dealers, top markets by growth)
  - Scatter plot for correlation views (e.g. price sensitivity vs units sold)
  - Assign chart types to prompts so that across the 15 persona prompts, at least 5 distinct chart types appear.
  - Charts use real data from the existing data files (globalSales, stateSales, forecast, kpis) — derive aggregations as needed.
  - Charts are rendered using the mobility-global-ds chart components (same as other pages). Each chart is 100% wide, ~240px tall, inside the AI bubble container.

**Right column (280px fixed):** Export panel.
- Four slide template cards showing name, description, and a colored top stripe.
- Each card has an "Export PPTX" button. Clicking it exports the current chat as a real `.pptx` file using pptxgenjs:
  - Slide 1: cover slide with app name and persona name, background in the template's primary color.
  - One slide per AI message in the chat. Each slide must include:
    - The question as a subtitle at the top.
    - The AI response text on the left half of the slide.
    - The associated chart on the right half of the slide, rendered as a native pptxgenjs chart (bar, line, doughnut, area, or scatter — matching the chart type shown in the chat). Use the same data aggregations that power the inline D3 charts, converted to pptxgenjs chart data format (labels + values arrays for bar/donut, categories + series for line/area).
  - If a message has no chart, the text should span the full slide width.
  - Use `pptx.writeFile({ fileName: 'autopulse-report.pptx' })`.
