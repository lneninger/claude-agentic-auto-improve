# UI and UX patterns

This is a rule document of the `angular-tailwind` add-on of the agentic-auto-improve plugin. The install skill copied it into your project. Do not edit it. The plugin replaces it when you update the add-on.

**What it holds, and what it does not.** This document holds the generic patterns that need markup: the loading, error and empty states of a view (`A-025`), the error banner (`P-001`), and the table column alignment (`P-002`). It does not hold the Angular code rules; those are in `ANGULAR_CODE_RULES.md`. It does not hold the rules for Angular Material components; those are in `ANGULAR_MATERIAL_RULES.md`. It does not hold the rules for Tailwind CSS and styling, or the scroll container pattern; those are in `TAILWINDCSS_RULES.md`. Its name differs from a project's own design document on purpose, so the two never collide.

**Which rule wins.** The project's own instructions win over every rule document. A document the project wrote and lists in `review.documents` wins over this plugin document where they disagree. For what it checks, the guard's verdict is final.

## How to read this document

- A rule has a stable ID. `A-025` comes from the shared catalogue of Angular rules. `P-001` belongs to the `P` series: patterns this plugin owns, which no catalogue rule already states. A `P` rule never restates a catalogue rule.
- "Enforced by: not enforced" means only a reader or a reviewer can catch a violation.
- The markup uses token utilities such as `text-on-surface-variant`. These come from the project's theme bridge (a `@theme` block in `<theme bridge file>`, under `<frontend root>`). Colours, wording and product names in the examples are placeholders. Use your own.
- For the layout of a whole screen, two plugin skills can advise you: `agentic-auto-improve:application-design` for application screens and `agentic-auto-improve:website-design` for website pages. They are advisory, not authoritative. When they disagree with `review.documents` or with `<the project's design document>`, the project file wins. If the skills are not installed, carry on without them.

## Patterns

### A-025 — Loading, error and empty states

Every view that loads data designs and builds all three states: loading, error and empty. A view that only handles the data case shows a blank page when the data is late, missing or failed.

- Enforced by: not enforced.
- The three states:
  - **Loading**: show a skeleton of the final layout, not a bare spinner. Mark the region busy with `aria-busy="true"`.
  - **Error**: say what failed in plain words and give a way to try again. Announce it with `role="alert"`. Pair the colour with an icon and text (`A-023`).
  - **Empty**: say that there is nothing to show, and what the user can do next.
- Example:

```html
@if (status() === 'loading') {
  <div class="flex flex-col gap-2" aria-busy="true">
    <span class="sr-only">Loading</span>
    @for (n of [1, 2, 3]; track n) {
      <div class="h-8 rounded bg-surface-variant animate-pulse"></div>
    }
  </div>
} @else if (status() === 'error') {
  <div class="flex items-center gap-2 text-error" role="alert">
    <mat-icon>error</mat-icon>
    <span>The data could not be loaded.</span>
    <button mat-button (click)="reload()">Try again</button>
  </div>
} @else if (items().length === 0) {
  <div class="flex flex-col items-center gap-2 p-6 text-on-surface-variant">
    <mat-icon>inbox</mat-icon>
    <span>Nothing to show yet.</span>
  </div>
} @else {
  @for (item of items(); track item.id) {
    <div>{{ item.label }}</div>
  }
}
```

### P-001 — Error banner

An error that affects a whole page, or a whole section, shows as a banner at the top of that area. The banner has an icon, a short message and, when it helps, an action. It is announced with `role="alert"`. It uses the error tokens, so it follows the theme. It is not the in-place error state of one view; that is `A-025`.

- Enforced by: not enforced.
- Allowed exceptions: a field-level validation error belongs in the form field (`mat-error`), not in a banner.
- Example:

```html
<div class="flex items-start gap-3 rounded border border-error bg-error-container p-3 text-on-surface"
     role="alert">
  <mat-icon class="text-error">error</mat-icon>
  <div class="flex-1">
    <p class="font-medium">{{ title() }}</p>
    <p class="text-sm text-on-surface-variant">{{ detail() }}</p>
  </div>
  <button mat-button (click)="dismiss()">Dismiss</button>
</div>
```

### P-002 — Table column alignment

In a table, numeric columns and their headers are right-aligned, and text columns are left-aligned. Each header aligns the same way as the cells below it. Right-aligned numbers put the digits in line, so a reader can compare them by size. The `font-mono tabular-nums` rule in `TAILWINDCSS_RULES.md` sets the digit width; this rule sets the side.

- Enforced by: not enforced.
- Example:

```html
<table class="w-full">
  <thead>
    <tr>
      <th class="text-left">Name</th>
      <th class="text-right">Amount</th>
    </tr>
  </thead>
  <tbody>
    @for (row of rows(); track row.id) {
      <tr>
        <td class="text-left">{{ row.name }}</td>
        <td class="text-right font-mono tabular-nums">{{ row.amount }}</td>
      </tr>
    }
  </tbody>
</table>
```

## Patterns this plugin does not ship

These candidates were considered and rejected. A project that wants one writes its own.

- **Status badge**: its states and colours are product data, and the `agentic-auto-improve:application-design` skill has an advisory one.
- **Card surface**: it is the product's look and feel.
- **Constrained panel**: it is a project class name; `T-014` and the scroll container already bound height.
