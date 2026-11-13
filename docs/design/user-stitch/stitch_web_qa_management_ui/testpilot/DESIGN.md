---
name: TestPilot
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
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002113'
  on-tertiary-container: '#009668'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  headline-sm:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
  body-lg:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-sm:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
  metric-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

### Personality & Emotional Response
The design system delivers an exacting, high-density, mission-critical workspace tailored for QA automation engineers, test leads, and DevOps practitioners. The emotional experience balances surgical precision, calm control, and operational clarity. It avoids excessive ornamentation in favor of instant information retrieval, dense telemetry tables, actionable run reports, and structured test plan management.

### Design Movement: Modern Developer & Observability Minimal
The visual framework synthesizes the architectural purity of Linear with the functional data telemetry of Datadog and Playwright Cloud:
- **Hairline Structured Grid:** Relies on razor-sharp single-pixel dividing lines (`#E2E8F0`) instead of heavy card elevation to delineate spatial boundaries.
- **Low-Saturation Baseline with Targeted Signals:** 90% of surfaces remain neutral grays and crisp slates, allowing semantic state indicators (Pass, Fail, Flaky, Running) to communicate immediate status without sensory overload.
- **Bilingual Typographic Harmony:** Native Korean typography (Hangul) matches the structural tracking, baseline alignment, and weight cadence of Latin code identifiers, execution logs, and CSS/XPath selectors.

## Colors

### Palette Architecture
- **Primary (`#0F172A` - Slate 900):** Governs core interactive hierarchies, active tab strokes, prominent actions, and high-contrast typographic anchors.
- **Secondary (`#2563EB` - Royal Blue 600):** Deployed selectively for focused runtime links, deep-link test run IDs (`TR-4091`), interactive telemetry highlights, and selected multi-row actions.
- **Tertiary / Success (`#10B981` - Emerald 500):** Anchors Passed test suites, assertion success states, healthy CI/CD pipeline runs, and 100% test coverage indicators.
- **Neutral (`#64748B` - Slate 500):** Neutral anchor for secondary metadata, breadcrumbs, column header keys, and unselected status labels.

### Canvas & Surface Matrix
- **Base Background:** `#F8FAFC` (Slate 50) establishes a cool, glare-free ground.
- **Surface Elevation 01 (Panel/Table Row/Card):** `#FFFFFF` (Pure White).
- **Surface Elevation 02 (Sub-panels, Hover rows, Code wells):** `#F1F5F9` (Slate 100).
- **Hairline Border Rule:** `#E2E8F0` (Slate 200) strictly applied at 1px solid across split-panes, sidebars, cell borders, and card headers.

### Semantic Status Tokens
- **Pass / Success:** `#059669` (Emerald 600 text/border), `#ECFDF5` (Emerald 50 fill).
- **Fail / Critical Assertion:** `#E11D48` (Rose 600 text/border), `#FFF1F2` (Rose 50 fill).
- **Running / Flaky / Warning:** `#D97706` (Amber 600 text/border), `#FFFBEB` (Amber 50 fill).
- **Draft / Skipped / Idle:** `#64748B` (Slate 500 text/border), `#F8FAFC` (Slate 50 fill).

## Typography

### Structural Role & Strategy
- **Geist (Primary UI & Hangul Fallback):** Handles high information density without vertical clutter. Set letter-spacing to `-0.015em` across all headlines and labels for compact grouping. For Korean UI terms (e.g., `테스트 스위트`, `실패한 단언문`, `실행 소요 시간`), maintain vertical metrics via fallback stack: `Geist, Pretendard Variable, -apple-system, BlinkMacSystemFont, system-ui, sans-serif`.
- **JetBrains Mono (Technical Execution):** Reserved exclusively for test case IDs (`TC-1049`), DOM selectors (`page.locator('button[data-testid="submit"]')`), stack traces, execution duration (`142ms`), and assertion logs. Tabular figures ensure numeric alignment down execution matrices.

## Layout & Spacing

### Workspace Topology
- **Multi-Pane Architectural Layout:** Composed of three primary horizontal divisions: Fixed Navigation Rail (60px), Test Suite Hierarchy Tree / Filter Sidebar (280px-340px resizable), and Main Execution Workspace / Split Execution Detail View.
- **Data Grid Density:** Table row heights adhere to strict presets:
  - *Compact (Dense Test View):* 32px row height with `0.25rem` vertical cell padding.
  - *Standard (Suite & Run Management):* 40px row height with `0.5rem` vertical cell padding.
- **Desktop First Reflow:** At screens `< 1280px`, secondary split panes (e.g., Live Step Trace & Console Logs) collapse into a horizontal bottom drawer. At `< 768px`, the tree navigation converts into an overlay flyout drawer, maintaining an edge margin of `1rem`.

## Elevation & Depth

### Low-Contrast Structural Outlining
Visual layering avoids soft diffused dropshadows. Hierarchy is established through planar stratification, contrast shifts, and structural hairline borders:

- **Level 0 (App Shell Background):** `#F8FAFC` flat canvas.
- **Level 1 (Card Panes, Grid Rows, Headers):** `#FFFFFF` surface bordered by a crisp `1px solid #E2E8F0` hairline.
- **Level 2 (Dropdowns, Context Menus, Tooltips):** `#FFFFFF` surface with `1px solid #CBD5E1` border and a micro shadow `0px 2px 4px -1px rgba(15, 23, 42, 0.06), 0px 4px 6px -1px rgba(15, 23, 42, 0.04)`.
- **Level 3 (Modal Dialogs, Trace Replay Overlays):** `#FFFFFF` anchored over a backdrop scrim `#0F172A` at 40% opacity with `0px 10px 15px -3px rgba(15, 23, 42, 0.08)`.
- **Active Focus & Row Selection:** Indicated by a 1px inner border using `#2563EB` or a `#EFF6FF` tint overlay, avoiding excessive glow or halo rings.

## Shapes

### Edge Precision
- **Base Elements (Buttons, Inputs, Tag Chips):** Fixed corner radius of `4px` (`0.25rem`). This imparts a structured instrument-like feel suitable for code and data tables.
- **Surfaces & Overlays (Modals, Slide-out Drawers, Code Panels):** Maximum corner radius of `6px` or `8px` (`rounded-lg`). Inner components strictly match concentric corner geometry.
- **Badge Indicators (Status Dots, Severity Counters):** Status badges maintain `4px` roundedness; standalone metric counts (e.g., `+12`) use fully circular badges (`9999px`) only when constrained to 1:1 aspect ratios.

## Components

### Buttons
- **Primary Action (e.g., '테스트 실행' - Run Test):** Background `#0F172A`, text `#FFFFFF`, border `1px solid #0F172A`. On hover: `#1E293B`. Active: `#334155`.
- **Secondary Action (e.g., '필터 추가' - Add Filter):** Background `#FFFFFF`, text `#0F172A`, border `1px solid #E2E8F0`. On hover: `#F8FAFC` with border `#CBD5E1`.
- **Destructive Action (e.g., '스위트 삭제' - Delete Suite):** Background `#FFFFFF`, text `#E11D48`, border `1px solid #FECDD3`. On hover: `#FFF1F2`.
- **Icon / Utility Actions:** Ghost button, `28px x 28px`, text `#64748B`, hover background `#F1F5F9`.

### Status Badges & Chips
- **Pass Badge:** Fill `#ECFDF5`, border `1px solid #A7F3D0`, text `#065F46`, font `label-sm`. Prefixed with an emerald dot indicator `w-1.5 h-1.5 rounded-full bg-emerald-500`.
- **Fail Badge:** Fill `#FFF1F2`, border `1px solid #FECDD3`, text `#9F1239`, font `label-sm`. Prefixed with a rose dot indicator.
- **Running / Queue Badge:** Fill `#FFFBEB`, border `1px solid #FDE68A`, text `#92400E`, font `label-sm`. Dot animates with subtle pulse.
- **Environment Tag Chips (e.g., `staging`, `chrome-headless`, `worker-02`):** Fill `#F1F5F9`, border `1px solid #E2E8F0`, text `#475569`, font `code-sm`.

### Form Inputs & Search Filters
- **Selector Input & Filter Bar:** Background `#FFFFFF`, border `1px solid #CBD5E1`, text `#0F172A`, placeholder `#94A3B8`. Height `32px` standard.
- **Focus State:** Border shifts cleanly to `#2563EB` with an offset outline of `1px solid rgba(37, 99, 235, 0.25)`.
- **Monospace Code Inputs (XPath, Selector, JSON Assertion):** Uses `JetBrains Mono` font at `12px`, with a `#F8FAFC` background.

### Checkboxes & Bulk Selection
- **Square Box:** `14px x 14px`, `rounded-sm` (2px radius).
- **Default:** Border `1px solid #CBD5E1`, background `#FFFFFF`.
- **Checked:** Background `#0F172A`, border `#0F172A`, white check icon centered.
- **Indeterminate:** Background `#0F172A`, horizontal white bar centered.

### Navigation Tabs
- **Segmented Workspace Tabs (e.g., '개요', '실행 로그', '단언 결과', '네트워크 추적'):** Inline horizontal list with a bottom border `#E2E8F0`. Active tab displays a solid 2px underbar `#0F172A` and bold text (`#0F172A`). Inactive tabs remain `#64748B` with hover color `#334155`.

### Execution Tree & Trace Split Panes
- **Tree View:** Multi-level collapsible tree with 16px indents, connecting guide lines in `#E2E8F0`. Hover row highlights with `#F8FAFC`.
- **Trace Inspector:** Split pane containing side-by-side DOM snapshots, network waterfall charts, and line-by-line code steps with execution duration badges formatted via `metric-mono`.