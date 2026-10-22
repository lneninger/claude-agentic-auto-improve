# Design foundation

The rules every page of a project obeys, whatever kind of page it is. This file exists once. `website-design` reads it; `application-design` reads it from its sibling folder and adds its own layer. Neither skill restates it.

## App Theme Awareness (CRITICAL)

**A project may hold several frontend applications, and they do not share a theme.** Which
applications exist is the `frontend.roots` slot of `.claude/project-profile.md`; which theme each
one carries is the `frontend.theme-polarity` slot beside it. Read both before you write a single
colour class, and never infer a theme from an application's name.

| Slot | What it gives you |
| --- | --- |
| `frontend.roots` | every application root, one per line — the `Location` column |
| `frontend.theme-polarity` | each application's polarity: `light`, `dark`, `both`, or `none` for a library |

**Before writing any color class**, determine which app you're working in, then apply the polarity
its slot declares:
- **A `light` app:** Use `-700` suffix for semantic text (`text-green-700`, `text-red-700`), `-100` for subtle backgrounds (`bg-green-100`)
- **A `dark` app:** Use `-400` suffix for semantic text (`text-green-400`, `text-red-400`), `-500/15` for subtle backgrounds (`bg-green-500/15`)
- **A `both` app, and every app:** Use Material token utilities (`bg-surface-container`, `text-on-surface-variant`, `border-outline-variant`) which adapt automatically via the `@theme` bridge. On a `both` app these are the only safe choice, because one hard-coded polarity will be wrong half the time.

## Tailwind 4 @theme Bridge

Both apps have a `@theme` block in `styles.scss` that maps Material 3 CSS custom properties to Tailwind utilities. This means:
- `bg-surface`, `bg-surface-container`, `bg-surface-variant` — work as native Tailwind utilities
- `text-on-surface`, `text-on-surface-variant`, `text-primary` — work as native Tailwind utilities
- `border-outline`, `border-outline-variant` — work as native Tailwind utilities
- Opacity modifiers work: `bg-surface-variant/50`, `border-outline/20`
- Hover/focus variants work: `hover:bg-surface-variant`

**Never use** `text-gray-*` for muted text or `bg-gray-*` for backgrounds — use the token utilities instead.

## Reference Library

**Consult before answering any design question.** The authoritative rows name slots in
`.claude/project-profile.md`, not literal files. Open the `review.documents` slot, read the paths it
lists, and consult those.

| Source | Covers | Authority |
|---|---|---|
| The design-pattern document named in `review.documents` | Chart Color Reference & Chart-Type Guide, the `@theme` conversion table, product patterns | **Authoritative** |
| The Material-rules document named in `review.documents` | Material component patterns | **Authoritative** |
| The project handbook named in `review.documents` → Frontend Rules | Standalone/OnPush, `@theme` bridge, `scroll-edge`, banned utilities | **Authoritative** |
| `/ui-ux-designer` domain judgement | Everything not covered above | Advisory |

> **Note.** Earlier revisions of the designer agent file cited a curated `~/.claude/references/ui-ux-pro-max/`
> extract (`ux-guidelines.md`, `chart-decisions.md`, `product-patterns.md`,
> `finance-palettes.md`). That directory never existed on disk — the absence was independently
> confirmed during contract review on 2026-08-18 and again during the 2026-08-25 setup merge.
> The rows above are the real sources. Do not reintroduce the phantom paths.

**Priority rules:**

1. Advisory sources are **advisory**. When they conflict with project rules — every document named in the `review.documents` slot, plus `architecture-guard.py` — the project rule wins.
2. Ignore any upstream "use `bg-gray-*`" guidance — the `@theme` bridge is authoritative; `bg-surface-variant` / `text-on-surface-variant` always win.

## Design Philosophy

2. **Visual hierarchy through weight and color**: Use font weight, size, and color — not decorative borders — to create hierarchy.
3. **Semantic color system**: Green = profit/buy/success, Red = loss/sell/error, Amber = warning/pending, Blue = info/neutral. These must be consistent everywhere.
4. **Motion with purpose**: Animate only state changes (loading→loaded, value updates), never for decoration. Keep durations under 200ms.
5. **Keyboard-first**: Everything operable without a mouse. Tab order must be logical.

(Philosophy rules 2-5 keep their original numbers; rule 1, information density, belongs to `application-design`. Rule 3's profit/buy and loss/sell wording is trading-terminal guidance; read it as the project's positive/negative semantic pair when the project is not a trading one.)

## Angular Material 21 Theming

### Actual Theme Configuration

Both apps use `mat.theme()` in their `styles.scss`:

```scss
@include mat.theme((
  color: (
    primary: mat.$azure-palette,
    tertiary: mat.$blue-palette,
    // an app whose frontend.theme-polarity is `dark` adds: theme-type: dark
  ),
  typography: Roboto,
  density: 0,
));
```

The `@theme` bridge in each `styles.scss` then maps all `--mat-sys-*` tokens to Tailwind utilities.

### Using Material Token Utilities in Templates

```html
<!-- Use the @theme-bridged Tailwind utilities (NOT arbitrary property syntax) -->
<div class="bg-surface-container text-on-surface border border-outline-variant rounded-lg p-4">
  <span class="text-on-surface-variant text-xs">Label</span>
  <span class="text-on-surface text-lg font-mono tabular-nums">$1,247.50</span>
</div>
```

**Never use** the `bg-[--mat-app-background-color]` arbitrary property syntax — the `@theme` bridge makes proper utilities available.

### Inline Style Elimination (HARD RULE)

**Never write inline `style="..."` for colors, backgrounds, or borders** when a `@theme`-bridged Tailwind utility exists. The "Inline Style to Tailwind Conversion" table in the design-pattern document named by `review.documents` is the authoritative reference.

Quick examples:

| Banned | Use instead |
| --- | --- |
| `style="color: var(--mat-sys-primary)"` | `text-primary` |
| `style="color: var(--mat-sys-on-surface-variant)"` | `text-on-surface-variant` |
| `style="background: var(--mat-sys-surface-container)"` | `bg-surface-container` |
| `style="border-top: 1px solid var(--mat-sys-outline-variant)"` | `border-t border-outline-variant` |
| `style="background: color-mix(... primary 15%...)"` | `bg-primary/15` |
| `style="color: #44464f"` | `text-on-surface-variant` |

**When editing an existing file** that contains inline Material token styles, **migrate them** to Tailwind classes in the same edit. This is a progressive cleanup — don't touch files outside the task scope, but fix what you touch.

## Accessibility Standards (WCAG 2.1 AA)

### Color Contrast
- Body text on background: minimum 4.5:1 ratio
- Large text / UI components: minimum 3:1 ratio
- **Light theme (any app whose `frontend.theme-polarity` is `light`):** Green-700, Red-700, Amber-700 on white/light surface: all pass
- **Dark theme (any app whose `frontend.theme-polarity` is `dark`):** Green-400, Red-400, Amber-400 on dark surface: all pass

### Keyboard Navigation
```html
<!-- All interactive elements must be keyboard-accessible -->
<div role="row" tabindex="0"
     (click)="select(item)"
     (keydown.enter)="select(item)"
     (keydown.space)="select(item)"
     [attr.aria-selected]="isSelected(item)">
```

### ARIA Labels for Icon Buttons
```html
<button mat-icon-button [attr.aria-label]="'Delete strategy ' + item().name">
  <mat-icon>delete</mat-icon>
</button>
```

## Visual Design Checklist

Before delivering any UI work:
- [ ] Consistent semantic color usage (green=profit, red=loss, amber=warning)
- [ ] All `mat-icon-button` elements have `aria-label`
- [ ] Hover/focus states visible and consistent
- [ ] No hardcoded pixel values — use Tailwind scale
- [ ] Animations use `transition-` classes, not inline styles
- [ ] Mobile viewport tested (at least 375px wide)
- [ ] Dark theme tokens used via Material CSS custom properties where applicable

(The checklist items about `tabular-nums`, loading/error/empty states and the font-size scale are in `application-design`'s patterns file.)

## What You Must Never Do
- Never use hardcoded hex colors in templates (`style="color: #44464f"`) — use `text-on-surface-variant` or Tailwind palette classes
- Never use `text-gray-*` for muted text — use `text-on-surface-variant` (adapts to theme)
- Never use `bg-gray-*` for subtle backgrounds — use `bg-surface-variant` or `bg-surface-container`
- Never use `bg-[--mat-app-background-color]` arbitrary property syntax — use the `@theme`-bridged utilities
- Never use `!important` in styles unless overriding a third-party library
- Never rely on color alone to convey state — always pair with icon, text, or shape
- Never add decorative animations that run continuously — flash effects only on data change
- Never assume dark theme — check which app you're working in first

(The rule against text smaller than `text-xs` is in `application-design`'s patterns file.)
