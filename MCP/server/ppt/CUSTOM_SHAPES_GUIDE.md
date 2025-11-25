# Custom Shapes Tool - add_shape_slide

## Overview

The `add_shape_slide` tool allows you to add any PowerPoint shape to a slide with automatic text-based sizing, custom colors, and flexible positioning.

## Features

✅ **20+ Shape Types** - Circles, squares, stars, hearts, arrows, and more
✅ **Auto-sizing** - Shapes automatically resize based on text content
✅ **Custom Colors** - Full RGB color control for both shapes and text
✅ **Multiple Shapes** - Add multiple shapes to a single slide
✅ **Flexible Positioning** - Precise control over position and size

## Supported Shape Types

### Basic Shapes
- `circle` / `oval` - Round shapes
- `square` - Perfect square
- `rectangle` - Standard rectangle
- `rounded_rectangle` - Rectangle with rounded corners

### Polygons
- `triangle` - Isosceles triangle
- `diamond` - Diamond shape
- `pentagon` - 5-sided polygon
- `hexagon` - 6-sided polygon
- `octagon` - 8-sided polygon

### Special Shapes
- `star` / `star5` - 5-pointed star
- `star6` - 6-pointed star
- `star7` - 7-pointed star
- `arrow` - Right-pointing arrow
- `heart` - Heart shape
- `cloud` - Cloud shape
- `lightning` - Lightning bolt
- `sun` - Sun shape
- `moon` - Moon/crescent shape

## Usage Examples

### Basic Shape with Auto-sizing

```python
await session.call_tool("add_shape_slide", {
    "presentation_id": "demo",
    "title": "My Shapes",
    "shapes": [
        {
            "shape_type": "circle",
            "text": "Hello World",
            "left": 3,
            "top": 3
        }
    ]
})
```

**Result:** Circle automatically sized to fit "Hello World" text

### Custom Size and Color

```python
{
    "shape_type": "rectangle",
    "text": "Custom Rectangle",
    "left": 2,
    "top": 2,
    "width": 4,
    "height": 2,
    "color": [68, 114, 196],  # Blue
    "text_color": [255, 255, 255],  # White text
    "font_size": 18
}
```

### Multiple Shapes on One Slide

```python
await session.call_tool("add_shape_slide", {
    "presentation_id": "demo",
    "title": "Process Flow",
    "shapes": [
        {
            "shape_type": "rounded_rectangle",
            "text": "Start",
            "left": 1,
            "top": 3,
            "color": [112, 173, 71]
        },
        {
            "shape_type": "arrow",
            "text": "→",
            "left": 3.5,
            "top": 3.25,
            "width": 1.5,
            "height": 0.5,
            "color": [68, 114, 196]
        },
        {
            "shape_type": "rounded_rectangle",
            "text": "End",
            "left": 5.5,
            "top": 3,
            "color": [237, 125, 49]
        }
    ]
})
```

## Parameters

### Required Parameters
- `shape_type` (string) - Type of shape to create
- `left` (number) - Left position in inches
- `top` (number) - Top position in inches

### Optional Parameters
- `text` (string) - Text to display in shape
- `width` (number) - Width in inches (auto-sized if omitted and text provided)
- `height` (number) - Height in inches (auto-sized if omitted and text provided)
- `color` (array) - RGB color as [R, G, B], e.g., [68, 114, 196]
- `text_color` (array) - Text RGB color as [R, G, B], e.g., [255, 255, 255]
- `font_size` (number) - Font size in points (default: 14)

## Auto-sizing Logic

When `width` or `height` are omitted and `text` is provided:

1. **Estimated Width**: `max(1.5, min(6, text_length * 0.1))` inches
2. **Estimated Height**: `max(0.8, min(3, line_count * 0.4))` inches

Special cases:
- **Circles**: Width and height forced equal (uses larger dimension)
- **Squares**: Width and height forced equal (uses larger dimension)

## Color Presets

Common colors you can use:

```python
# Professional colors
blue = [68, 114, 196]
green = [112, 173, 71]
yellow = [255, 192, 0]
orange = [237, 125, 49]
red = [192, 0, 0]

# Basic colors
white = [255, 255, 255]
black = [0, 0, 0]
gray = [128, 128, 128]
```

## Use Cases

### 1. Organizational Charts
Create org charts with rounded rectangles at different levels

### 2. Process Diagrams
Combine shapes with arrows to show workflows

### 3. Infographics
Use circles with metrics, stars for ratings, hearts for favorites

### 4. Callouts & Highlights
Add cloud shapes or stars to emphasize key points

### 5. Custom Icons
Create simple icon-based visualizations with shapes

### 6. Decision Trees
Use diamonds for decisions, rectangles for actions

## Comparison with Other Tools

| Tool | Purpose | Flexibility |
|------|---------|-------------|
| `add_process_flow_slide` | Horizontal/vertical flows | Pre-defined chevron layout |
| `add_timeline_slide` | Timeline with events | Fixed horizontal timeline |
| `add_diagram_slide` | Cycle/pyramid/matrix | Pre-defined diagram types |
| **`add_shape_slide`** | **Any custom layout** | **Full control over positioning** |

Use `add_shape_slide` when you need:
- Custom positioning not available in pre-defined tools
- Specific shape types (stars, hearts, etc.)
- Mixed shape types on one slide
- Full control over layout

## Testing

Run the test script:

```bash
python test_shapes.py
```

Or explore all examples:

```bash
python custom_shapes_demo.py
```

## Tips & Best Practices

1. **Positioning**: PowerPoint slides are typically 10" wide × 7.5" tall (standard 4:3)
2. **Text Length**: Keep text concise for best auto-sizing results
3. **Color Contrast**: Use light text on dark shapes or dark text on light shapes
4. **Alignment**: Space shapes evenly (e.g., left: 1, 3.5, 6 for three shapes)
5. **Font Sizes**: 14-18pt works well for most shapes; use larger for emphasis
6. **Multi-line Text**: Use `\n` for line breaks in text

## Complete Example

```python
# Create a complete dashboard slide
await session.call_tool("add_shape_slide", {
    "presentation_id": "dashboard",
    "title": "Q4 Metrics Dashboard",
    "shapes": [
        # Metric 1
        {
            "shape_type": "circle",
            "text": "85%\nUptime",
            "left": 1.5,
            "top": 2.5,
            "width": 2,
            "height": 2,
            "color": [112, 173, 71],
            "font_size": 20
        },
        # Metric 2
        {
            "shape_type": "circle",
            "text": "1.2M\nUsers",
            "left": 4,
            "top": 2.5,
            "width": 2,
            "height": 2,
            "color": [68, 114, 196],
            "font_size": 20
        },
        # Metric 3
        {
            "shape_type": "circle",
            "text": "$5.2M\nRevenue",
            "left": 6.5,
            "top": 2.5,
            "width": 2,
            "height": 2,
            "color": [255, 192, 0],
            "font_size": 20
        },
        # Status star
        {
            "shape_type": "star",
            "text": "★",
            "left": 4,
            "top": 5.5,
            "width": 1.5,
            "height": 1.5,
            "color": [255, 192, 0],
            "font_size": 48
        }
    ]
})
```

## Summary

The `add_shape_slide` tool provides maximum flexibility for creating custom layouts with any combination of shapes, making it perfect for:
- Custom diagrams
- Infographics
- Organizational charts
- Process flows with mixed shapes
- Dashboard layouts
- Any visualization not covered by pre-defined tools

Now you have **16 total tools** in the PowerPoint MCP Server! 🎉
