# Tailwind CSS and styling rules

This is a rule document of the `angular-tailwind` add-on of the agentic-auto-improve plugin. The install skill copied it into your project. Do not edit it. The plugin replaces it when you update the add-on.

**What it holds, and what it does not.** This document holds the Tailwind CSS and styling rules (rules `T-001` to `T-025`): inline styles, colour tokens, component stylesheets, scroll containers, numbers and responsive layout. It also holds the scroll container pattern, with its snippet and install step. It does not hold the Angular code rules; those are in `ANGULAR_CODE_RULES.md`. It does not hold the rules for Angular Material components; those are in `ANGULAR_MATERIAL_RULES.md`. It does not hold the states pattern or the error banner; those are in `UI-UX-PATTERNS.md`.

**Which rule wins.** The project's own instructions win over every rule document. A document the project wrote and lists in `review.documents` wins over this plugin document where they disagree. For what it checks, the guard's verdict is final.

## How to read this document

- A rule has a stable ID such as `T-001`. The guard, the tests and the other documents refer to a rule by that ID. The guard prints the ID in each message.
- The line "Enforced by" tells you what stops a violation. "Guard blocks" means the edit-time guard (`architecture-guard.py`) refuses the edit. "Guard warns" means it prints a warning and lets the edit through. "Not enforced" means only a reader or a reviewer can catch it.
- The edit-time guard blocks template and decorator violations and only warns on stylesheets. Get it right the first time. Do not trial-and-error against the guard.
- A **theme bridge** is a `@theme` block in the global stylesheet. It maps the Material 3 colour tokens (`--mat-sys-*`) to Tailwind utilities, so you can write `bg-surface-container` instead of a raw colour. Several rules below need one.
- A **token utility** is a Tailwind class that comes from that bridge, such as `text-primary` or `border-outline-variant`.
- Project facts are placeholders in angle brackets:
  - `<frontend root>`: a path from the `frontend.roots` slot of the project profile (`.claude/project-profile.md`).
  - `<theme bridge file>`: the stylesheet of each app that holds the `@theme` block.
  - the polarity of an app (light, dark or both): the `frontend.theme-polarity` slot.
  - the banned classes of an app: that app's `.app-rules.json`.
  - the design document: the one you list in `review.documents`.

## Inline styles and colours

### T-001 — No static style attribute

Templates (.component.html): ZERO static style="..." attributes allowed. Every static property must be a Tailwind utility from the @theme bridge. In short, a component template has no static `style="..."` attribute. Dynamic [style.prop]="expr()" bindings ARE allowed for runtime-computed values.

- Enforced by: guard blocks (`inline-style`), on every line of `*.component.html`.
- Allowed exceptions: the closed list in `T-008`. There is no other.
- Example: write `class="text-primary"`, not `style="color: var(--mat-sys-primary)"`.

### T-002 — Use token utilities, not inline token styles

Use token utilities (`text-primary`, `bg-surface-container`, `border-outline-variant`) instead of an inline `style="color: var(--mat-sys-*)"`.

| Instead of | Write |
| --- | --- |
| `style="color: var(--mat-sys-primary)"` | `text-primary` |
| `style="color: var(--mat-sys-on-surface-variant)"` | `text-on-surface-variant` |
| `style="background: var(--mat-sys-surface-container)"` | `bg-surface-container` |
| `style="opacity: 0.5"` | `opacity-50` |
| `style="border-top: 1px solid var(--mat-sys-outline-variant)"` | `border-t border-outline-variant` |
| `style="background: color-mix(... primary 15% ...)"` | `bg-primary/15` |
| `style="color: #44464f"` | `text-on-surface-variant` |

- Enforced by: guard blocks, but only indirectly: `T-001` blocks any static `style=`. Nothing checks that a token utility is chosen over a raw palette utility.
- Allowed exceptions: a fixed theme colour is always a utility class, never a binding. A colour that is computed at run time (a chart colour read from a theme token by a signal) may use a binding (`T-008`).

### T-003 — No gray utilities

Banned: text-gray-*, bg-gray-*, border-gray-* -> use text-on-surface-variant, bg-surface-variant, border-outline-variant (from the Material @theme bridge). They change with the theme; gray does not.

- Enforced by: guard blocks (`gray-utility:<label>`), in `*.component.html` and `*.component.ts`.
- Allowed exceptions: none.

### T-004 — No hard-coded hex colours in templates

Banned: hardcoded hex colors in templates -> use Material token utilities (text-primary, bg-surface-container, border-outline-variant, etc.).

- Enforced by: guard blocks (`hex-color`), in templates only. The check skips a template reference variable such as `#add`. A token that stands alone after whitespace and has no digit (for example `#fff`) is read as a reference variable and passes.
- Allowed exceptions: none. For a chart, bind a signal that reads a `var(--mat-sys-*)` token (`T-008`).

### T-005 — The theme bridge

Keep a `@theme` block in the global stylesheet (`<theme bridge file>`) that maps the Material 3 tokens to Tailwind utilities. Prefer these utilities to raw palette colours. This rule needs a precondition: the project has such a bridge. If it has none, say so and do not invent class names.

The vocabulary a bridge normally gives:

- Surfaces: `bg-surface`, `bg-surface-container`, `bg-surface-container-low`, `bg-surface-container-high`, `bg-surface-container-highest`, `bg-surface-variant`.
- Text: `text-on-surface`, `text-on-surface-variant`, `text-primary`, `text-secondary`, `text-error`.
- Borders: `border-outline`, `border-outline-variant`.
- Fills: `bg-primary`, `bg-primary-container`, `bg-error-container`, `bg-secondary-container`.

- Enforced by: not enforced.

### T-006 — Token utilities over palette colours

For any surface, text or border that has to change with the theme, prefer a token utility to a raw palette colour.

- Enforced by: not enforced beyond `T-003`.

### T-007 — Opacity and variants

Write opacity with the slash modifier: `bg-primary/15`, `border-outline/20`. Hover and focus variants work on tokens: `hover:bg-surface-variant`.

- Enforced by: not enforced.

### T-008 — The inline-style exceptions

A static `style` is never allowed in a component template, with this closed list of exceptions:

- (a) Bindings `[style.prop]`, `[style]` and `[attr.style]` whose value is computed at run time. Any property is allowed here, including a chart colour read from a theme token by a signal. `[style.width.px]` and `[style.height.px]` from a signal are typical.
- (b) A static `style` on an SVG element or on `canvas`, when every property is a positioning property.
  - The elements: `svg`, `g`, `text`, `tspan`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path`, `use`, `image`, `foreignObject`, and `canvas`.
  - The positioning properties: `position`, `left`, `top`, `right`, `bottom`, `transform`, `transform-origin`, `translate`.
  - The opening tag name must sit on the same line as `style=`, because the guard reads one line at a time. A tag split across lines is not excepted.
- (c) A tooltip `max-width`, written as a global class. This is a recipe, not an exception to `T-001`.

A static `style` never carries a colour, background or border value. A fixed theme colour is a utility class (`T-002`), never a binding.

- Enforced by: guard blocks (`inline-style`) everything outside this list.
- Example that passes: `<g style="transform: translate(4px, 8px)">` and `<text style="left: 0">`. Example that blocks: `<svg style="fill: #fff; left: 0">` (a colour) and `<div style="left: 0">` (not an SVG element).

### T-009 — Migrate what you touch

When you edit a file that has inline token styles, migrate them in the same edit. Do not touch files outside the task.

- Enforced by: not enforced. The guard's line rules scan only the new text of an edit, so they do not see the inline styles a file already holds.

## Component stylesheets

### T-010 — Component stylesheets stay near-empty

Component SCSS (.component.scss): near-empty. Only allowed content is third-party overrides / @keyframes / @media / @supports / @apply blocks. Raw property rules belong in the template as Tailwind classes.

- Enforced by: guard warns (`scss-warn:raw-property`).
- Allowed exceptions: the five kinds of content listed above.

### T-011 — Where an override is written

Overrides use :host ::ng-deep, but in a ViewEncapsulation.None component :host matches nothing, so scope them under the component's element selector (for example `my-widget .vendor-class`).

- An override that serves one component stays in that component's stylesheet: under `:host ::ng-deep` (encapsulated component) or under the element selector (`ViewEncapsulation.None`).
- An override that more than one component uses goes in the global stylesheet, scoped by a wrapper class (`M-006`).
- Enforced by: guard warns (`scss-warn:dead-host`) on a dead `:host`.

## Scroll containers

### T-012 — Use the shared scroll classes

Banned: inline overflow-y-auto / sticky top-0 for scroll containers -> use the global scroll-edge / scroll-edge-content / scroll-edge-header classes. Never write `relative`, `absolute`, `overflow-y-auto` or `sticky` by hand for a scrollable table or list.

- Enforced by: guard blocks (`scroll-edge`) on `overflow-y-auto` and on `sticky` with any offset in a class attribute. `relative` and `absolute` are not checked.
- Allowed exceptions: none. The pattern, its snippet and its markup are in "The scroll container pattern" below.

### T-013 — Scroll height is a class

Set the scroll height with a Tailwind class on the `scroll-edge` element (`h-80`, `h-96`), never with an inline style.

- Enforced by: guard blocks, indirectly, through `T-001`.
- Allowed exceptions: an arbitrary value such as `max-h-[400px]` only as the last resort in `T-019`.

### T-014 — A scroll wrapper needs a parent with a height

A scroll wrapper that fills its parent needs a parent with a height. Add `h-full min-h-0` to the template's root element, or `flex-1 min-h-0` inside a flex parent. If you do not, the content collapses to zero height and the page looks empty. This broke twice in the source project.

- Enforced by: guard warns (`height-chain-warn:scroll-edge-no-root-height`). On an edit it judges the whole file as it will be after the edit; when that file cannot be built (missing, not UTF-8, or the old text is absent or ambiguous) it judges the new fragment alone.

## Other styling rules

### T-015 — Global classes beat utilities

Global classes written with `@apply` are unlayered. They beat Tailwind utilities. A utility that sets a property the class already sets is silently dead. Change the class with a modifier class, not with a utility at the call site.

- Enforced by: not enforced. A project may add its own reminder in the `advisorRemindersAppendix` of an app's `.app-rules.json` (see `T-022`).

### T-016 — Prove styling in the right place

Do not prove styling with a class-presence assertion. A component test loads no global stylesheet. Use a source-text assertion over the stylesheet, or a rendered capture.

- Enforced by: not enforced.

### T-017 — No arbitrary properties for Material variables

Do not write the arbitrary-property syntax for Material variables, such as `bg-[--mat-app-background-color]`. Use the bridge (`T-005`).

- Enforced by: not enforced.

### T-018 — No important in styles

A stylesheet never writes `!important` except to override a third-party library. In a template, the `!` prefix is allowed only on an element a third-party library renders (Material), and never on the project's own elements (`M-003`).

- Enforced by: not enforced.

### T-019 — Use the Tailwind scale

Use the Tailwind scale, not hard-coded pixel values. An arbitrary value such as `max-h-[400px]` is a last resort: use it only when no scale step fits, and only inside a utility class. Never use one in `style=` or in a component stylesheet.

- Enforced by: not enforced.

### T-020 — Motion with purpose

Animate only state changes. Keep durations short. Use `transition-` classes. Do not run a decorative animation continuously.

- Enforced by: not enforced.

### T-021 — Check the theme polarity first

Check the theme polarity of the app (light, dark or both) before you choose a colour class. Never assume dark. The `frontend.theme-polarity` slot of the project profile is the only authority. This document never states the polarity of an app. If a project design document disagrees with the slot, report the mismatch. Do not choose between them.

- Enforced by: guard blocks the banned classes of an app through `T-022`.

### T-022 — Per-app rules file

Each app keeps an `.app-rules.json` with its banned classes, their token replacements and a reminder text (`advisorRemindersAppendix`). Read it for the app you work in. The values are project data.

- Enforced by: guard blocks (`app-banned-class:<class>`). The guard finds the app by the path segment after the frontend root.

### T-023 — Numbers

Write numbers with `font-mono tabular-nums`, so columns line up.

- Enforced by: not enforced.

### T-025 — Responsive layout

Test a narrow mobile viewport. Use responsive prefixes such as `hidden lg:flex` and `grid-cols-1 md:grid-cols-2 xl:grid-cols-3`.

- Enforced by: not enforced.

## The scroll container pattern

This pattern gives a table or a list a body that scrolls and a header that stays at the top. It is three classes. Use it instead of writing `overflow-y-auto` and `sticky` by hand (`T-012`).

### The snippet

The plugin ships it as `snippets/scroll-edge.scss` in the add-on. This is its content:

```scss
/* agentic-auto-improve:scroll-edge begin */
.scroll-edge {
  @apply relative;
}

.scroll-edge-content {
  @apply absolute inset-0 overflow-y-auto;
}

.scroll-edge-header {
  @apply sticky top-0 z-10;
  background-color: var(--scroll-edge-header-bg, var(--mat-sys-surface));
}
/* agentic-auto-improve:scroll-edge end */
```

- The header background is a named setting: `--scroll-edge-header-bg`. Its default is `var(--mat-sys-surface)`. To change it, set the setting on a parent element.
- The header rule uses a raw CSS property, not a bridge class such as `bg-surface`. This way it does not depend on how `@apply` treats a bridge class in your build setup.
- The wrapper has no `overflow-hidden`. If you want one, add it on the `scroll-edge` element as a utility class. It is optional.

### Where it goes

Put it at the end of the global stylesheet of the app (`<theme bridge file>` is usually that file). It must come after Tailwind and the theme bridge are loaded. If your project renames the classes, keep the same three roles and tell the guard through the project's own documents.

### Install step

The add-on install skill appends the snippet when the classes are missing. Run `/auto-improve-angular-tailwind-install` and, when it asks, name the global stylesheet. The skill:

- looks for the three class names in that file. If all three are there, it does nothing.
- if none are there, appends the snippet between the begin and end marker comments.
- if only some are there, it stops and tells you. Fix the stylesheet by hand, then run it again.

The uninstall skill never removes the snippet. Delete the marked block by hand if you want it gone.

### Usage: a table

```html
<div class="scroll-edge h-80">
  <div class="scroll-edge-content">
    <table class="w-full">
      <thead class="scroll-edge-header">
        <tr><th>Name</th><th>Value</th></tr>
      </thead>
      <tbody>
        @for (row of rows(); track row.id) {
          <tr><td>{{ row.name }}</td><td class="font-mono tabular-nums">{{ row.value }}</td></tr>
        }
      </tbody>
    </table>
  </div>
</div>
```

### Usage: a plain list

```html
<div class="scroll-edge h-96">
  <ul class="scroll-edge-content">
    <li class="scroll-edge-header">Group title</li>
    @for (item of items(); track item.id) {
      <li>{{ item.label }}</li>
    }
  </ul>
</div>
```

### The height rule

The wrapper sets the height of the scroll region. It needs a height from a class (`h-80`, `h-96`) or from its parent (`h-full min-h-0`, or `flex-1 min-h-0` inside a flex parent). Without a height the content collapses to zero (`T-014`).

### A note for Ionic apps

In an Ionic page, `ion-content` already scrolls the page. Use these classes only for nested scroll regions inside a page, never for the page itself.
