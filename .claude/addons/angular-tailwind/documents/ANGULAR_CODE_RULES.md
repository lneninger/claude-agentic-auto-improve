# Angular code rules

This is a rule document of the `angular-tailwind` add-on of the agentic-auto-improve plugin. The install skill copied it into your project. Do not edit it. The plugin replaces it when you update the add-on.

**What it holds, and what it does not.** This document holds the Angular code rules: components, templates, signals, state services, subscriptions and accessibility (rules `A-001` to `A-027`, except `A-025`). It does not hold the rules for Angular Material; those are in `ANGULAR_MATERIAL_RULES.md`. It does not hold the rules for Tailwind CSS and styling; those are in `TAILWINDCSS_RULES.md`. It does not hold `A-025` (loading, error and empty states, with their markup) or the patterns of the `P` series; those are in `UI-UX-PATTERNS.md`.

**Which rule wins.** The project's own instructions win over every rule document. A document the project wrote and lists in `review.documents` wins over this plugin document where they disagree. For what it checks, the guard's verdict is final.

## How to read this document

- A rule has a stable ID such as `A-003`. The guard, the tests and the other documents refer to a rule by that ID.
- The line "Enforced by" tells you what stops a violation. "Guard blocks" means the edit-time guard (`architecture-guard.py`) refuses the edit. "Guard warns" means it prints a warning and lets the edit through. "Not enforced" means only a reader or a reviewer can catch it.
- The edit-time guard blocks template and decorator violations and only warns on stylesheets. Get it right the first time. Do not trial-and-error against the guard.
- Some facts belong to your project, not to the plugin. They appear as placeholders in angle brackets:
  - `<frontend root>`: a path from the `frontend.roots` slot of your project profile (`.claude/project-profile.md`).
  - `<the success flag of the project's response envelope>`: the field your API puts on every response to say it worked. It is named in the project's own handbook, which you list in `review.documents`.
  - `<the project's design document>`: the design document you list in `review.documents`.

## Components and templates

### A-001 — Components are standalone

Every component is standalone. Do not write NgModules.

- Enforced by: not enforced.

### A-002 — OnPush change detection

Every component uses `ChangeDetectionStrategy.OnPush`.

- Enforced by: not enforced. Reason: the source project's pattern enforcer does not ship in this plugin.

### A-003 — Template and styles in separate files

Banned: inline template: / styles: in @Component() decorators. Always use templateUrl + styleUrl pointing at .component.html / .component.scss.

- Enforced by: guard blocks (`inline-component-template` and `inline-component-styles`). The guard reads `*.component.ts` and any other `.ts` file (never `.spec.ts` or `.d.ts`) whose text carries `@Component(`.
- Allowed exceptions: none.
- Example: `@Component({ selector: 'app-thing', templateUrl: './thing.component.html', styleUrl: './thing.component.scss' })`.

### A-004 — Use inject()

Get dependencies with `inject()`. Do not use constructor injection in components.

- Enforced by: not enforced. Reason: the source project's pattern enforcer does not ship in this plugin.
- Allowed exceptions: plain classes that are not components.

### A-005 — Signal inputs

Use signal inputs: `input()`, and `input.required()` for an input that must be given. Do not use the `@Input()` decorator.

- Enforced by: not enforced.

### A-006 — Template control flow

Use `@if`, `@for` (with `track`) and `@switch`. Never write `*ngIf` or `*ngFor`.

- Enforced by: not enforced. Reason: the source project's pattern enforcer does not ship in this plugin.
- Allowed exceptions: the Material directives in `M-015` keep their `*` syntax.

### A-007 — Every @for has a track expression

Every `@for` block has a `track` expression.

- Enforced by: not enforced. The Angular compiler itself requires it.

### A-008 — No ngSwitch

Do not use `[ngSwitch]`. Use `@switch`.

- Enforced by: not enforced.

## State and signals

### A-009 — State services expose read-only signals

A state service keeps its writable signals private and exposes them with `.asReadonly()`. Never expose a writable signal publicly.

- Enforced by: not enforced.
- Folder names for state and services belong to your project. Use the ones in `<the project's own handbook>`.

### A-010 — State changes go through service methods

Change state only through state-service methods. Compute derived values with `computed()`, not with an effect.

- Enforced by: not enforced.

### A-011 — Clean up subscriptions

End every subscription with `takeUntilDestroyed(destroyRef)` or `destroyRef.onDestroy`.

- Enforced by: not enforced. Reason: the source project's pattern enforcer does not ship in this plugin.

### A-012 — No async pipe

Do not use the `async` pipe. Bridge an observable to a signal with `toSignal()`. Give it an initial value, or pass `requireSync`.

- Enforced by: not enforced. Reason: the source project's pattern enforcer does not ship in this plugin.

### A-013 — No any

Do not use `any`. Use `unknown` and narrow it with type guards.

- Enforced by: not enforced.

### A-014 — Clean up timers

Clean up `setInterval` and `setTimeout` with `destroyRef.onDestroy`.

- Enforced by: not enforced.

### A-015 — Effects

An effect tracks every signal it relies on. An effect that creates a subscription returns a cleanup function. Do not use an effect to sync state; use `computed()`.

- Enforced by: not enforced.

### A-016 — viewChild targets that mount late

A `viewChild` target may not exist yet when a conditional `@if` delays mounting. Do not use `ngAfterViewInit` for such a target. Use an effect that tracks the viewport instead.

- Enforced by: not enforced.

### A-017 — CDK virtual scroll

`scrollToIndex` needs `*cdkVirtualFor`. `scrollToOffset` always works.

- Enforced by: not enforced.
- Allowed exceptions: `*cdkVirtualFor` keeps its `*` syntax. It is a CDK directive, like those in `M-015`.

## Security, performance and types

### A-018 — Template security

Do not call `bypassSecurityTrustHtml` or `bypassSecurityTrustUrl` without a written justification. Do not keep tokens or keys in `localStorage` or in component state. Do not bind unsanitised `innerHTML`.

- Enforced by: not enforced.

### A-019 — Template performance

Do not call a function in a template when it would run on every change detection. Use `@defer` or virtual scrolling for large lists. Give images explicit dimensions.

- Enforced by: not enforced.

### A-020 — Template type safety

Do not rely on implicit type coercion. Handle every member of a union type in `@switch`.

- Enforced by: not enforced.
- Example: check `<the success flag of the project's response envelope>` before you read the value in the response.

## Accessibility

### A-021 — Icon buttons have a label

Every `mat-icon-button` has `[attr.aria-label]`.

- Enforced by: not enforced.
- Example: `<button mat-icon-button [attr.aria-label]="'Delete ' + item().name"><mat-icon>delete</mat-icon></button>`

### A-022 — Keyboard operation

An interactive element that is not a button has `role="button"`, `tabindex="0"`, `(keyup.enter)` and `(keyup.space)`. Everything can be used with the keyboard, in a logical tab order.

- Enforced by: not enforced.

### A-023 — Colour never carries state alone

Never rely on colour alone to show a state. Pair it with an icon, text or a shape.

- Enforced by: not enforced.

### A-024 — Visible focus and hover

Focus and hover states are visible and look the same everywhere.

- Enforced by: not enforced.

### A-026 — Contrast

Contrast meets WCAG 2.1 level AA. Body text needs at least 4.5 to 1. Large text and interface components need at least 3 to 1.

- Enforced by: not enforced.

### A-027 — Live regions

Data that updates in real time uses `aria-live="polite" aria-atomic="true"`, inside a wrapper that only screen readers see.

- Enforced by: not enforced.
- Example: `<span class="sr-only" aria-live="polite" aria-atomic="true">{{ announcement() }}</span>`
