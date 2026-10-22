# Application patterns

The data-dense product-screen layer. It sits on top of the design foundation (`../../website-design/references/foundation.md`) and never restates it. The wording and examples below are trading-terminal guidance; where the project is not a trading one, read "profit/loss" as the project's own positive/negative pair.

## Design Philosophy

1. **Information density first**: Trading UIs must show as much relevant data as possible without clutter. Every pixel earns its place.

## Chart colours

Palette hex values go into typed `core/models/charts/` constants consumed by chart configs — never into `.html` templates or `.scss`. **Chart-config colours only — never Material theme token replacements.**

## Compact Density

For dense forms (panels, sidebars), use the global `compact-field` class or component-level CSS custom properties:

```scss
// Component-level density overrides
:host {
  --mat-form-field-container-height: 36px;
  --mdc-list-list-item-one-line-height: 32px;
}
```

## TailwindCSS 4 Design Patterns

> **Full reference:** read the design-pattern document named by the `review.documents` slot for the complete pattern catalog. This section is a quick reference.

### Typography Scale for Trading UI
```html
<!-- Large metric value (use -700 for light theme, -400 for dark) -->
<span class="text-2xl font-mono font-semibold tabular-nums text-green-700">+$1,247.50</span>

<!-- Label -->
<span class="text-xs font-medium uppercase tracking-wide text-on-surface-variant">Daily P&L</span>

<!-- Table cell value -->
<span class="text-sm font-mono tabular-nums text-on-surface">$428.15</span>

<!-- Status text -->
<span class="text-xs font-medium text-amber-700">PENDING</span>
```

### Grid Layouts for Data Panels
```html
<!-- Metrics grid (consistent across dashboard) -->
<div class="grid grid-cols-2 gap-px bg-outline-variant/30 rounded-lg overflow-hidden
            sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
  @for (metric of metrics(); track metric.key) {
    <div class="flex flex-col gap-1 p-3 bg-surface-container">
      <span class="text-xs text-on-surface-variant truncate">{{ metric.label }}</span>
      <span class="text-lg font-mono tabular-nums font-semibold"
            [class.text-green-700]="metric.value > 0"
            [class.text-red-700]="metric.value < 0"
            [class.text-on-surface]="metric.value === 0">
        {{ metric.value | number:'1.2-2' }}
      </span>
    </div>
  }
</div>
```

### Status Badges (theme-adaptive)
```html
<!-- Light theme: -100 bg, -700 text. Dark theme: -500/15 bg, -400 text -->
<!-- an app whose frontend.theme-polarity is `light` -->
<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      [ngClass]="{
        'bg-green-100 text-green-700': status() === 'Active',
        'bg-red-100 text-red-700': status() === 'Error',
        'bg-amber-100 text-amber-700': status() === 'Pending',
        'bg-blue-100 text-blue-700': status() === 'Running',
        'bg-surface-variant text-on-surface-variant': status() === 'Stopped'
      }">
  <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
  {{ status() }}
</span>
```

## Reusable Component Patterns

### Metric Card
```html
<div class="flex flex-col gap-2 p-4 rounded-xl bg-surface-container border border-outline/20
            hover:border-outline/40 transition-colors">
  <div class="flex items-center justify-between">
    <span class="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
      {{ label() }}
    </span>
    <mat-icon class="text-base" [class]="iconColor()">{{ icon() }}</mat-icon>
  </div>
  <div class="flex items-end gap-2">
    <span class="text-2xl font-mono tabular-nums font-bold"
          [class.text-green-700]="isPositive()"
          [class.text-red-700]="isNegative()">
      {{ formattedValue() }}
    </span>
    @if (delta()) {
      <span class="text-xs pb-0.5 font-mono"
            [class.text-green-700]="delta()! > 0"
            [class.text-red-700]="delta()! < 0">
        {{ delta()! > 0 ? '+' : '' }}{{ delta() | number:'1.2-2' }}%
      </span>
    }
  </div>
</div>
```

### Loading Skeleton
```html
<!-- Match the skeleton to the actual content structure -->
@if (loading()) {
  <div class="animate-pulse space-y-2">
    @for (i of [1,2,3,4,5]; track i) {
      <div class="h-10 bg-surface-variant/50 rounded"></div>
    }
  </div>
} @else {
  <!-- actual content -->
}
```

### Empty State
```html
@if (!loading() && items().length === 0) {
  <div class="flex flex-col items-center justify-center gap-3 py-16 text-on-surface-variant">
    <mat-icon class="text-5xl opacity-30">{{ emptyIcon() }}</mat-icon>
    <p class="text-sm">{{ emptyMessage() }}</p>
    @if (showAction()) {
      <button mat-stroked-button (click)="onAction.emit()">
        <mat-icon>add</mat-icon> {{ actionLabel() }}
      </button>
    }
  </div>
}
```

### Real-Time Value Flash (price updates)
```scss
// In component styles
@keyframes flash-green {
  0%, 100% { background: transparent; }
  50% { background: rgb(74 222 128 / 0.15); }
}

@keyframes flash-red {
  0%, 100% { background: transparent; }
  50% { background: rgb(248 113 113 / 0.15); }
}

.flash-green { animation: flash-green 0.4s ease; }
.flash-red { animation: flash-red 0.4s ease; }
```

```typescript
// Apply flash class reactively
effect(() => {
  const price = this.price();
  const prev = this.prevPrice();
  if (price > prev) this.flashClass.set('flash-green');
  else if (price < prev) this.flashClass.set('flash-red');
  setTimeout(() => this.flashClass.set(''), 400);
});
```

### Screen Reader Live Regions
```html
<!-- For real-time data that updates -->
<div aria-live="polite" aria-atomic="true" class="sr-only">
  @if (lastUpdate()) {
    Last update: {{ lastUpdate() | date:'HH:mm:ss' }}
  }
</div>
```

## Responsive Design

```html
<!-- Mobile-friendly sidebar + content layout -->
<div class="flex h-screen overflow-hidden">
  <!-- Sidebar: hidden on mobile, visible on lg+ -->
  <aside class="hidden lg:flex w-64 flex-col border-r border-outline/20 bg-surface-container-low">
    <!-- nav -->
  </aside>

  <!-- Main content -->
  <main class="flex-1 overflow-auto p-4 md:p-6">
    <!-- On mobile: stack, on desktop: grid -->
    <div class="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
      <!-- cards -->
    </div>
  </main>
</div>
```

## Visual Design Checklist (application items)

Before delivering any UI work:
- [ ] Uses `tabular-nums` on all numeric values for proper column alignment
- [ ] Loading, error, and empty states all designed and implemented
- [ ] Font sizes follow scale: `text-xs` for labels, `text-sm` for body, `text-lg/2xl` for metrics

(The remaining checklist items are in the foundation file.)

## What You Must Never Do (application items)
- Never make text smaller than `text-xs` (10px) — illegible on trading monitors

(The remaining never-do items are in the foundation file.)
