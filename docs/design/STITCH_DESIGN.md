---
name: QA Lab Studio
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#006329'
  on-tertiary: '#ffffff'
  tertiary-container: '#007f36'
  on-tertiary-container: '#c7ffca'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#7ffc97'
  tertiary-fixed-dim: '#62df7d'
  on-tertiary-fixed: '#002109'
  on-tertiary-fixed-variant: '#005320'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
  label-ui:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 12px
  margin: 16px
  space-xs: 4px
  space-sm: 8px
  space-md: 12px
  space-lg: 16px
  space-xl: 24px
---

## Brand & Style

This design system delivers an exacting, editorial SaaS aesthetic tailored for QA engineers, test automation developers, and technical product teams. It rejects decorative tech tropes—banning neon accents, purplish ambient gradients, and marketing bloat—in favor of razor-sharp operational clarity, dense data presentation, and rapid visual scanning.

The experience evokes high-end instruments: scientific grade, clinical, calm, and unfailingly reliable. The visual environment remains strictly light-themed, establishing immediate legibility across high-density test suites, stack traces, and multi-run matrices. The tonal balance between pure white structural containers and pale cool gray background planes creates depth without relying on heavy decorative effects.

## Colors

The palette establishes an ink-on-paper feel with targeted technical signals. Color serves strictly functional roles: identifying interaction points and communicating deterministic test states (PASS, FAIL, ERROR).

### Application Hierarchy
- **Canvas & Backing Plane:** `#F8FAFC` provides the primary app viewport backing, with `#F1F5F9` reserved for table headers, segmented track bars, and recessed code blocks.
- **Surface & Shell:** `#FFFFFF` is used universally for sidebars, navigation panels, floating modals, and modular cards.
- **Hairline Structural Borders:** `#E2E8F0` defines all element boundaries, column dividers, and list separators with sub-pixel sharpness.
- **Ink Typography:** `#0F172A` (Slate 900) anchors all primary headers, assertions, code lines, and active states. `#475569` (Slate 600) covers supporting copy, while `#64748B` (Slate 500) supplies timestamp, metadata, and placeholder text.
- **Primary Electric Cobalt:** `#2563EB` acts as the active execution and interaction tint, with `#1D4ED8` serving as the pressed state and `#EFF6FF` providing hover wash states.
- **Status Signals:**
  - **PASS:** `#16A34A` text and glyph with `#DCFCE7` background tint.
  - **FAIL:** `#DC2626` text and glyph with `#FEE2E2` background tint.
  - **ERROR / TIMEOUT:** `#D97706` text and glyph with `#FEF3C7` background tint.
  - **SKIPPED / PENDING:** `#64748B` text with `#F1F5F9` background tint.

## Typography

The type system prioritizes high-density tabular rendering and cross-script precision. Typography is set using `Inter` (paired with `Pretendard` in Korean locales via CSS fallback) alongside `JetBrains Mono` for code snippets, assertions, timestamps, network payloads, and test IDs.

Font sizes scale compactly around 11px to 14px to maximize screen real estate, ensuring full test matrices, JSON bodies, and DOM trees remain visible without vertical pagination. Letter spacing is slightly tightened on UI labels and headings to sustain an editorial feel.

## Layout & Spacing

Layout geometry follows a compact desktop workspace standard. Spacing adheres to a tight 4px baseline rhythm, avoiding inflated gaps and hollow margins.

- **Workspace Division:** A persistent 240px wide `#FFFFFF` navigation sidebar sits on the left with a hairline border. The primary operational space uses flexible panes (Split Pane architecture) to hold test lists, runner consoles, DOM inspectors, and network waterfalls simultaneously.
- **Grid and Content Margins:** Data grids and inspection tables span 100% of pane width with 12px gutters. Section padding inside inspection cards stays locked at 12px (`space-md`) or 16px (`space-lg`), keeping information immediately readable without unnecessary whitespace padding.
- **Scroll Behavior:** Main viewport nesting avoids window-level scrolling; instead, panels contain independent, frictionless vertical scrolls with slim 4px hover-revealed scrollbars.

## Elevation & Depth

Visual hierarchy uses crisp hairline borders and subtle planar contrasts instead of pronounced drop shadows.

- **Flat Planes & Borders:** Surfaces rest on the `#F8FAFC` base, separated primarily by solid 1px `#E2E8F0` hairline rules.
- **Feather-Light Elevation:** Interactive cards and floating panels use an ultra-restrained shadow formula:
  - Low base: `0 1px 2px 0 rgba(15, 23, 42, 0.04)`
  - Elevated dropdown / flyout: `0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(226, 232, 240, 1)`
  - Modal dialog: `0 12px 32px -4px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(226, 232, 240, 1)`
- **Layering Over Blur:** Backdrops under modals use a flat neutral wash (`rgba(15, 23, 42, 0.35)`) without heavy gaussian blurs to maintain instant visual acuity and UI performance.

## Shapes

Corner rounding balances contemporary engineering software standards with geometric crispness. 

- **Containers & Surfaces:** Main cards, modal frames, and preview docks feature a 10px to 12px radius, avoiding both rigid brutalist squares and bubbly tablet interfaces.
- **Interactive Controls:** Buttons, text fields, chips, and run badges standardize on 6px to 8px radii (`rounded-md`), preserving vertical rhythm within dense rows.
- **Status Pills:** Badges communicating test status (PASS / FAIL / WARN) utilize 4px to 6px radii to read as structured tags rather than consumer pill indicators.

## Components

### Buttons
- **Primary:** Background `#2563EB`, text `#FFFFFF`, font-weight 500, height 32px, padding 0 12px, border-radius 6px. Active hover: `#1D4ED8`. Focus outline: 2px offset `#2563EB`.
- **Secondary / Outline:** Background `#FFFFFF`, border `1px solid #E2E8F0`, text `#0F172A`. Hover: background `#F8FAFC`, border `#CBD5E1`.
- **Ghost Action (Table Actions):** Background transparent, text `#64748B`. Hover: background `#F1F5F9`, text `#0F172A`.

### Status Badges & Chips
- **Format:** Height 20px, font `JetBrains Mono` 11px, weight 500, padding 0 6px, border-radius 4px.
- **PASS:** Background `#DCFCE7`, border `1px solid #BBF7D0`, text `#16A34A`.
- **FAIL:** Background `#FEE2E2`, border `1px solid #FECACA`, text `#DC2626`.
- **ERROR / TIMEOUT:** Background `#FEF3C7`, border `1px solid #FDE68A`, text `#D97706`.

### Data Tables & Test Runs
- Row height: 36px fixed.
- Header: Background `#F8FAFC`, text `#64748B`, font-size 11px, uppercase, letter-spacing `0.04em`, bottom border `1px solid #E2E8F0`.
- Cells: Text `#0F172A`, font-size 12px, vertical alignment centered, border-bottom `1px solid #F1F5F9`. Hover state: background `#F8FAFC`.

### Form Inputs & Search Fields
- Height 32px, background `#FFFFFF`, border `1px solid #E2E8F0`, text `#0F172A`, placeholder `#94A3B8`.
- Focus state: border `#2563EB`, shadow `0 0 0 1px #2563EB`.

### Cards & Panels
- Background `#FFFFFF`, border `1px solid #E2E8F0`, box-shadow `0 1px 3px rgba(15, 23, 42, 0.04)`, border-radius 10px. 
- Headers feature a bottom divider border (`#E2E8F0`) with 12px padding and clear metadata groupings.

### Log Terminal & Inspector
- Background `#0F172A`, text `#F8FAFC`, font `JetBrains Mono` 12px, line-height 18px.
- Timestamps in `#64748B`, assertion keywords highlighted with primary cobalt and status reds/greens.