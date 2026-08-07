# Chart Generation User Guide

## How to Request Charts with Framework Selection

### Framework Selection in Queries

You can now explicitly specify which charting framework to use in your natural language queries:

#### Use D3.js (Modern, Interactive)
```
"Show me resource allocation using D3"
"Create a line chart with D3.js"  
"Render the data with d3 javascript"
"Use D3 for this chart"
```

#### Use Chart.js (Simple, Compatible)
```
"Show me a bar chart using Chart.js"
"Create chart with chartjs"
"Render using Chart.js"
"Use chartjs for this visualization"
```

#### Auto-Select (Default: D3)
```
"Show me a line chart"
"Create a bar chart"
"Visualize the data"
```

## Data Labels Feature

All D3 charts now include **visible data labels** on the chart elements (not just in tooltips). This means:

✅ **Screenshots are useful** - Values are visible in static images  
✅ **PowerPoint friendly** - Export charts as images with data intact  
✅ **Presentation ready** - No need for hover to see values  

### What's Included

**Line Charts:**
- Labels above each data point
- Rounded to 1 decimal place
- Color-coded to match line color

**Bar Charts:**
- Labels on top of each bar
- Rounded to 1 decimal place
- Dark color for visibility

**Grouped Bar Charts:**
- Labels on each bar in the group
- Easy comparison between series

## Performance Note

**Previous Issue:** Chart generation was slow because data was being converted to packed circle format unnecessarily.

**Solution:** The automatic packed circle conversion now only happens when:
- Single numeric field per category
- Explicitly requested pie/proportional chart
- NOT when framework preference is specified

**Result:** Charts generate much faster now (typically < 2 seconds)

## Examples

### Example 1: Resource Allocation with D3
```
User: "Show resource allocation for Jasveer Singh for 2025 using D3"
```

Result:
- ✅ Detects "using D3" preference
- ✅ Generates D3 line chart
- ✅ Includes data labels on all points
- ✅ Fast generation (< 2 seconds)

### Example 2: Budget Chart with Chart.js
```
User: "Create a bar chart of project budgets with Chart.js"
```

Result:
- ✅ Detects "with Chart.js" preference
- ✅ Generates Chart.js bar chart
- ✅ Simple, compatible rendering

### Example 3: Default (No Framework Specified)
```
User: "Show me monthly hours trend"
```

Result:
- ✅ Defaults to D3.js
- ✅ Modern, interactive chart
- ✅ Data labels included

## Technical Details

### Framework Detection Keywords

**D3.js:**
- d3
- d3.js
- d3 js
- use d3
- with d3
- using d3
- d3 javascript

**Chart.js:**
- chartjs
- chart.js
- chart js
- use chartjs
- with chartjs
- using chartjs

### Data Label Positioning

**Line Charts:**
- Labels 8px above data points
- Font: 11px, bold
- Color: Matches line color
- Format: Rounded to 1 decimal

**Bar Charts:**
- Labels 5px above bar top
- Font: 11px, bold
- Color: Dark gray (#333)
- Format: Rounded to 1 decimal

### Chart Generation Speed

| Scenario | Before | After |
|----------|--------|-------|
| Simple line chart | ~5-10s | ~2s |
| Bar chart | ~5-10s | ~2s |
| Packed circle | ~10-15s | ~2s |

Speed improvement from avoiding unnecessary format conversions.

## Tips

1. **For Screenshots:** Always use D3 charts - data labels are visible
2. **For Presentations:** D3 charts export well to images
3. **For Compatibility:** Use Chart.js if targeting older systems
4. **For Speed:** Specify framework explicitly in query
5. **For Interaction:** D3 charts have tooltips AND labels

## Troubleshooting

### Q: Chart generation is slow
**A:** Make sure you're specifying the framework in your query to avoid auto-detection delays

### Q: Can't see data in screenshot
**A:** Ensure you're using D3 - data labels are always visible (not just on hover)

### Q: Want simpler chart
**A:** Add "with Chart.js" to your query

### Q: Want interactive features
**A:** Use D3 (default) - includes hover tooltips, transitions, etc.

---

**Updated:** November 21, 2025  
**Version:** 2.0 with Data Labels and Framework Selection
