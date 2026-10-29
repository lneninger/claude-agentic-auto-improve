# Angular Material rules

This is a rule document of the `angular-tailwind` add-on of the agentic-auto-improve plugin. The install skill copied it into your project. Do not edit it. The plugin replaces it when you update the add-on.

**What it holds, and what it does not.** This document holds the Angular Material rules: how to import, style and fix the Material components (rules `M-001` to `M-016`). It does not hold the Angular code rules; those are in `ANGULAR_CODE_RULES.md`. It does not hold the rules for Tailwind CSS and styling in general; those are in `TAILWINDCSS_RULES.md`. It does not hold the states and error-banner patterns; those are in `UI-UX-PATTERNS.md`.

**Which rule wins.** The project's own instructions win over every rule document. A document the project wrote and lists in `review.documents` wins over this plugin document where they disagree. For what it checks, the guard's verdict is final.

## How to read this document

- A rule has a stable ID such as `M-003`. The guard, the tests and the other documents refer to a rule by that ID.
- The line "Enforced by" tells you what stops a violation. "Not enforced" means only a reader or a reviewer can catch it.
- Material colours reach Tailwind through a theme bridge: a `@theme` block that maps the Material tokens to Tailwind utilities. The file that holds it is `<theme bridge file>`. It lives in the global stylesheet of each app under `<frontend root>`.
- A project may also have its own Material document. It is named in `review.documents` as `<the project's own Material document>`. Where it disagrees with this document, it wins.
- The `!` prefix in Tailwind (for example `!py-2`) makes a utility win over a rule that has higher specificity. Material's own styles are such rules. This document shows where the prefix is allowed (`M-003`).

## Rules

### M-001 — Import Material modules one by one

Import each Material module on its own, so unused code can be removed from the build (tree-shaking).

- Enforced by: not enforced.

### M-002 — Who does what

Use Material for interactive elements: buttons, form fields, dialogs, tables, chips, toggles and menus. Use Tailwind for layout and spacing. Use theme tokens for colours.

- Enforced by: not enforced.

### M-003 — Override Material with the ! prefix

To change a Material style, put the Tailwind `!` prefix on the utility, for example `!py-2`. Material's host styles win on specificity, so a plain utility loses.

- Enforced by: not enforced.
- Allowed exceptions: the `!` prefix is allowed only on an element a third-party library renders (Material). It is never allowed on the project's own elements. This is the same boundary as `T-018`: `!important` in a stylesheet is only for overriding a third-party library.

### M-004 — mat-icon size

To size a `mat-icon`, write `!text-base !w-4 !h-4 !leading-4` on it.

- Enforced by: not enforced.
- Allowed exceptions: the `!` prefix is allowed here because Material renders the icon (see `M-003`).

### M-005 — Form-field density

Set the density of form fields with a global class or with component-level CSS custom properties, for example `--mat-form-field-container-height: 36px`.

- Enforced by: not enforced.
- Allowed exceptions: this is a Material token value, not a layout size. The pixel rule `T-019` does not apply to it.

### M-006 — Where Material internals are overridden

An override that serves one component goes in that component's stylesheet. Under `:host ::ng-deep` for an encapsulated component. Under the element selector for a component with `ViewEncapsulation.None`. An override that more than one component uses goes in the global stylesheet, scoped by a wrapper class, because component styles are encapsulated. This is the same rule as `T-011`.

- Enforced by: guard warns (`scss-warn:dead-host`) when `:host` is used in a `ViewEncapsulation.None` component.
- Example: `.my-dense-table .mat-mdc-cell { ... }` in the global stylesheet, with `my-dense-table` on the wrapper.

### M-007 — Dynamic subscript sizing

Form fields use `subscriptSizing="dynamic"`, so they do not reserve space for a hint that is not shown.

- Enforced by: not enforced.

### M-009 — Dialog action bar border

The dialog action bar has a top border: `border-t border-outline-variant`.

- Enforced by: not enforced.

### M-011 — Compact icon button

A compact `mat-icon-button` needs `!p-0 !flex !items-center !justify-center` on the button and `!w-4 !h-4 !leading-4` on the icon. Without them the icon drifts off centre.

- Enforced by: not enforced.
- Allowed exceptions: the `!` prefix is allowed here because Material renders both elements (see `M-003`).

### M-012 — Detail rows in mat-table

`mat-table` uses a flex layout, so `colspan` on an expanded detail row is ignored. Fix it with `display: inline-table` on the detail row. Do not use flex hacks.

- Enforced by: not enforced.

### M-013 — mat-icon inside a Material button

Never put a `mat-icon` inside an `@if` or `@else` block that has several root nodes, inside a Material button. Content projection fails. Move the control flow outside the button.

- Enforced by: not enforced.

### M-014 — Spinner inside a button

A `mat-spinner` inside a button is `display: block`. Wrap the spinner and the text in `<span class="flex items-center gap-1">`.

- Enforced by: not enforced.

### M-015 — Material structural directives

`*matHeaderCellDef` and `*matCellDef` are Material structural directives. They are not control-flow violations of `A-006`. Keep the `*` syntax.

- Enforced by: not enforced. The rule is not applicable to a check; it only stops a wrong "fix".

### M-016 — No colour overrides on chips

Do not put utility colour overrides such as `!bg-blue-100` on Material chips. Use the chip's own colour settings.

- Enforced by: not enforced.
