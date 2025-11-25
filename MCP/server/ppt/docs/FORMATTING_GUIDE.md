# PowerPoint Slide Formatting Guide

## Overview

The PPT MCP server now supports comprehensive formatting options for content slides, allowing you to customize fonts, colors, and borders for professional presentations.

## Supported Slide Types

The following slide types support formatting:
- `add_content_slide` - Bullet point slides
- `add_two_column_slide` - Two-column layout slides

## Formatting Parameters

All formatting parameters are **optional**. If not provided, the presentation will use default template settings.

### Font Size

Control text size in points:

```json
{
  "font_size": 18,           // Content text size
  "title_font_size": 28      // Title text size
}
```

**Common sizes:**
- Title: 28-32 points (large, prominent)
- Subtitle: 24-28 points
- Body text: 18-20 points (readable)
- Details/notes: 14-16 points (smaller)

### Font Color

Specify colors using RGB arrays `[R, G, B]` where each value is 0-255:

```json
{
  "font_color": [0, 0, 0],         // Content text color
  "title_font_color": [0, 51, 102] // Title text color
}
```

**Common colors:**
- Black: `[0, 0, 0]`
- White: `[255, 255, 255]`
- Red: `[255, 0, 0]`
- Green: `[0, 128, 0]`
- Blue: `[0, 0, 255]`
- Dark Blue: `[0, 51, 102]`
- Orange: `[255, 127, 0]`
- Corporate Blue: `[68, 114, 196]`

### Borders

Add borders to text boxes for visual emphasis:

```json
{
  "border_color": [68, 114, 196],  // Border color (RGB)
  "border_width": 1.5              // Border thickness in points
}
```

**Border widths:**
- Subtle: 1.0-1.5 points
- Standard: 1.5-2.0 points
- Prominent: 2.0-3.0 points

## Complete Example

### Content Slide with Full Formatting

```json
{
  "tool": "add_content_slide",
  "arguments": {
    "presentation_id": "quarterly_review",
    "title": "Key Achievements Q1 2025",
    "content": [
      "Delivered 5 major projects on time",
      "Reduced operational costs by 15%",
      "Improved customer satisfaction to 92%",
      "Launched new product line successfully"
    ],
    "title_font_size": 32,
    "title_font_color": [0, 51, 102],
    "font_size": 20,
    "font_color": [0, 0, 0],
    "border_color": [68, 114, 196],
    "border_width": 1.5
  }
}
```

### Two-Column Slide with Formatting

```json
{
  "tool": "add_two_column_slide",
  "arguments": {
    "presentation_id": "quarterly_review",
    "title": "Strengths vs Challenges",
    "left_content": [
      "Strong team collaboration",
      "Excellent delivery track record",
      "High customer retention"
    ],
    "right_content": [
      "Resource capacity constraints",
      "Budget limitations",
      "Technology debt"
    ],
    "title_font_size": 28,
    "title_font_color": [0, 51, 102],
    "font_size": 18,
    "font_color": [0, 0, 0],
    "border_color": [68, 114, 196],
    "border_width": 1.5
  }
}
```

## Design Best Practices

### Professional Color Schemes

**Corporate/Professional:**
- Titles: Dark blue `[0, 51, 102]`
- Body: Black `[0, 0, 0]`
- Borders: Corporate blue `[68, 114, 196]`

**High Contrast:**
- Titles: Black `[0, 0, 0]`
- Body: Dark gray `[64, 64, 64]`
- Borders: Black `[0, 0, 0]`

**Emphasis/Warning:**
- Titles: Dark red `[204, 0, 0]`
- Body: Black `[0, 0, 0]`
- Borders: Red `[255, 0, 0]`

**Success/Positive:**
- Titles: Dark green `[0, 102, 0]`
- Body: Black `[0, 0, 0]`
- Borders: Green `[0, 128, 0]`

### Font Size Hierarchy

Create visual hierarchy with consistent sizing:

```
Title Slide:        Title: 40pt, Subtitle: 28pt
Section Headers:    Title: 32pt, Body: 20pt
Content Slides:     Title: 28pt, Body: 18pt
Detail Slides:      Title: 24pt, Body: 16pt
```

### Border Usage

Use borders strategically:
- **Executive summaries:** Add borders to emphasize key points
- **Comparison slides:** Use borders to separate columns visually
- **Action items:** Border important takeaways
- **Avoid:** Overusing borders on every slide (creates visual clutter)

## Backward Compatibility

All formatting parameters are optional. Existing code without formatting will continue to work with default styles:

```json
{
  "tool": "add_content_slide",
  "arguments": {
    "presentation_id": "my_presentation",
    "title": "Simple Slide",
    "content": ["Point 1", "Point 2", "Point 3"]
  }
}
```

This will create a slide with default template formatting.

## Advanced Techniques

### Mixed Emphasis Presentations

Vary formatting across slides to emphasize different sections:

1. **Title slide:** Large fonts, no borders
2. **Executive summary:** Medium-large fonts, subtle borders
3. **Data slides:** Standard fonts, no borders
4. **Key findings:** Large fonts, prominent borders
5. **Conclusion:** Large fonts, colored emphasis

### Professional PMO Presentations

Example structure with formatting:

```python
# Title slide (no formatting needed - uses template)
add_title_slide(...)

# Executive summary - emphasized
add_content_slide(
    title_font_size=32,
    title_font_color=[0, 51, 102],
    font_size=20,
    border_color=[68, 114, 196],
    border_width=2.0
)

# Data slides - standard formatting
add_content_slide(
    font_size=18,
    font_color=[0, 0, 0]
)

# Key recommendations - highly emphasized
add_content_slide(
    title_font_size=32,
    title_font_color=[204, 0, 0],
    font_size=20,
    font_color=[0, 0, 0],
    border_color=[204, 0, 0],
    border_width=2.5
)
```

## Testing Your Formatting

1. Start with default formatting (no parameters)
2. Add title formatting first
3. Adjust body text size for readability
4. Add colors for branding
5. Add borders last for emphasis

Preview your presentation after each change to ensure the formatting meets your needs.

## RGB Color Picker

To find RGB values for specific colors:
- Use PowerPoint's color picker (More Colors → Custom)
- Use online tools like [RGB Color Codes](https://www.rapidtables.com/web/color/RGB_Color.html)
- Use design tools like Adobe Color or Coolors.co

## Troubleshooting

**Text too small/large:**
- Adjust `font_size` in increments of 2-4 points
- Standard body text is 18-20 points
- Ensure titles are 8-12 points larger than body

**Colors not visible:**
- Check RGB values are within 0-255 range
- Ensure sufficient contrast (dark text on light background)
- Test presentation on projector/screen (colors may appear different)

**Borders too thick/thin:**
- Standard borders are 1.5 points
- Adjust in 0.5 point increments
- Preview on actual screen to check visibility

**Inconsistent formatting:**
- Use same parameters across similar slide types
- Create parameter constants in your code
- Document your formatting standards
