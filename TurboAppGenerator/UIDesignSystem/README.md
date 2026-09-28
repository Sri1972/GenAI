# Mobility Global — UI System

Component library built on Mobility Global brand tokens for use in all Figma mockups.

## Brand Colors Used

| Token | Name | Hex | Usage |
|---|---|---|---|
| Primary | Vital Blue | `#132445` | Sidebar, headers, primary text |
| Primary | Forward Blue | `#0064D2` | Buttons, links, active states, focus rings |
| Primary | Morning Mist | `#B8EAF5` | Active tab bg, hover states, info backgrounds |
| Neutral | Quiet Light | `#EFEFE5` | Page background |
| Neutral | White | `#FFFFFF` | Cards, header, modal backgrounds |
| Accent | Steady Lilac | `#420E71` | Tags, Premium badges (sparingly) |
| Accent | Vital Spark | `#FFE783` | Warning/notification highlights (sparingly) |
| Semantic | Success | `#059669` | Success badges, positive trends |
| Semantic | Error | `#DC2626` | Error states, danger actions |

## Components in the UI System

| # | Component | Variants |
|---|---|---|
| 1 | Color Palette | All 12 brand + semantic colors as swatches |
| 2 | Typography | H1–H4, Body LG/MD/SM, Caption |
| 3 | Buttons | Primary, Secondary, Ghost, Danger, Disabled, Success · SM/MD/LG sizes |
| 4 | Form Inputs | Default, Focused, Filled, Error, Disabled · Textarea |
| 5 | Dropdowns | Closed, Open with options list |
| 6 | Tabs | Horizontal (4 tabs) · Vertical (sidebar style) |
| 7 | Badges | Active, Inactive, Pending, Error, New, Premium, Beta · Notification counts |
| 8 | Cards | Basic, Info, Warning, Success · all with accent stripe + shadow |
| 9 | KPI Cards | Metric + value + trend indicator in 4 colors |
| 10 | Data Table | Header (Vital Blue) + alternating rows + status badges |
| 11 | Alert Banners | Info, Success, Warning, Error |
| 12 | Header | Desktop header with logo, nav, search, avatar |
| 13 | Sidebar | Vital Blue nav with active state (Forward Blue) + user profile |
| 14 | Footer | Vital Blue footer with copyright + links |
| 15 | Modal | Overlay scrim + dialog with Vital Blue header + Cancel/Confirm |
| 16 | Breadcrumb | Multi-level with Forward Blue links |
| 17 | Pagination | Page buttons with Forward Blue active state |
| 18 | Progress Bar | Track + fill in brand colors with labels |
| 19 | Avatars | SM/MD/LG/XL circles with initials in brand colors |
| 20 | Search Bar | Rounded, Forward Blue focus ring, Morning Mist background |
| 21 | Tooltip | Vital Blue background, white text, arrow pointer |

## How to Build

Prerequisites: MCP server + relay running, Figma Desktop Bridge showing "Local Ready"

```bash
cd TurboUIGen/UIDesignSystem
python build_ui_system.py
```

Then switch to the **"UI System"** page in Figma to review all components.

## Files

```
UIDesignSystem/
├── build_ui_system.py   ← Runs the Figma builder
├── brand_tokens.json    ← All design tokens (colors, spacing, radius, etc.)
└── README.md            ← This file
```
