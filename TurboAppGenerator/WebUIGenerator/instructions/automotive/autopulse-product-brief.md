# AutoPulse Global — Product Brief

## What We Want to Build

We need a sales intelligence platform for our automotive business called **AutoPulse Global**. Today our sales teams are working off disconnected spreadsheets and stale weekly reports. By the time insights reach leadership, opportunities are already missed. We want one platform where everyone — from the VP to the dealer analyst — can see what's happening in real time.

## The Big Picture

AutoPulse is a dashboard-driven analytics platform that covers our global automotive sales, US dealer network, vehicle inventory, and forward-looking forecasts. It should also have an AI assistant that people can ask questions to in natural language instead of waiting for an analyst to pull a report.

## Who Uses It

Three main audiences:
- **Executives** — need the 30,000-foot view. KPIs, trends, "are we on track?" answers.
- **Dealer Operations** — need to see inventory health, which vehicles are aging on lots, which states are underperforming.
- **Strategy/Planning** — need forecasts, scenario planning, market comparisons, and expansion signals.

## What It Should Do

1. **Executive dashboard** — key metrics at a glance with revenue trends and performance by region and make.

2. **Global sales map** — visualize where we sell across 15+ countries (Americas, Europe, Asia Pacific, Middle East & Africa). Filter by make and quarter. We track Tesla, Toyota, BMW, Ford, Mercedes, Volkswagen, Hyundai, and Honda.

3. **US deep dive** — state-level view of sales volume, dealer counts, and growth. Click into a state for detail.

4. **Full data explorer** — let power users search, filter, sort, and export the raw global sales data. Must support Excel and PDF export.

5. **Inventory tracker** — show vehicle stock across the dealer network at VIN level. Highlight aging inventory (how long vehicles have sat on lots). Filter by status, make, location.

6. **Forecast & scenarios** — monthly projections for the next 12+ months. Actual vs. forecast vs. prior year. Support base, optimistic, and pessimistic scenarios. Show the EV vs. ICE split.

7. **AI concierge** — a chat interface where users can ask questions about the data. The AI adapts its responses based on who's asking (executive gets bullet-point summaries, analyst gets detailed numbers, strategist gets market comparisons).

8. **Query builder** — a power-user tool to slice and dice data interactively. Left panel shows all available fields (columns) from the data. Users can select which columns to display in the results grid and which columns to use as filters. Filters support conditions like equals, contains, greater than, less than, and between. An "Execute Query" action calls the API with the selected display fields and filter criteria, and shows results in a sortable, exportable grid. Users should be able to save and reuse queries they build often.

## Data We Have

- Global quarterly sales: country, region, make, model, units, revenue, growth, market share
- US state sales: state, make, model, units, revenue, dealer count, growth
- Vehicle inventory: VIN, make, model, year, trim, color, MSRP, status, dealer location, days on lot
- Monthly forecast: actuals, forecast, confidence bands, EV/ICE split, prior year comparison

## Phased Delivery

We want to deliver incrementally so users get value early:
1. Dashboard + Global Map + US Map + Analytics
2. Sales data grid + Inventory management
3. Forecasting with scenario planning
4. AI Concierge

## Key Expectations

- Everything must be exportable (Excel, PDF) wherever there's a data table
- Must feel responsive and polished on desktop
- AI assistant must read real data, not canned responses
- Each phase stands alone — users shouldn't need to wait for Phase 4 to get value from Phase 1
