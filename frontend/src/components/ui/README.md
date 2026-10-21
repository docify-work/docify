# UI kit

Pages compose **only** these components (import from `@/components/ui`). Styling comes from the design tokens in
`src/styles/tokens.css` (semantic colours that flip with `prefers-color-scheme`, compact type scale, radii, shadows,
motion). Visual review: run `npm run dev` and open **`/dev/ui`** (dev builds only).

Rules: keep copy terse; put explanations in `info` props (ⓘ tooltip) instead of paragraphs; every list/table has
loading (skeleton), empty and error states.

| Component | File | Notes |
| --- | --- | --- |
| `Button` | Button.tsx | `variant` primary · secondary · ghost · subtle · danger; `size` xs · sm · md; `loading`, `icon`, `iconRight`, `asChild` (wrap a router `<Link>`/`<a>`) |
| `IconButton` | IconButton.tsx | Square icon button; `label` = aria-label + tooltip |
| `Input`, `Textarea`, `Select` | Field.tsx | `label`, `info` (ⓘ), `error` (animated), `aside` (e.g. "Forgot?"); `Select` is a styled native select |
| `Field` | Field.tsx | Label row + control + error, for custom controls |
| `Switch`, `Checkbox` | Switch.tsx | Radix; `label`, `info` |
| `Card`, `CardHeader`, `CardBody` | Card.tsx | One-line header: icon · title · ⓘ · meta … actions |
| `Row` | Card.tsx | Settings row inside a card: label (+ⓘ) left, control right |
| `Stat` | Card.tsx | KPI tile with tabular number |
| `KeyValues` | Card.tsx | Compact fact strip (branch, commit, …) |
| `DataTable` | Table.tsx | Typed columns, sticky header, row hover/click/keyboard, skeleton rows, empty slot, staggered first paint |
| `List`, `ListItem` | List.tsx | Divided rows; `to`/`href` makes the row a link; `meta` and `actions` slots |
| `Badge`, `StatusPill` | Badge.tsx | Tones; `StatusPill` maps repo / job / version statuses to colour + icon + hint tooltip |
| `Tooltip`, `InfoTip`, `TooltipProvider` | Tooltip.tsx | Radix tooltip; `InfoTip` is the ⓘ helper |
| `Popover`, `DropdownMenu`, `MenuItem`, `MenuLabel`, `MenuSeparator` | Menu.tsx | Radix; animated in/out |
| `Dialog`, `ConfirmDialog`, `Drawer` | Dialog.tsx | Radix dialog; `ConfirmDialog` supports type-to-confirm (`confirmText`); `Drawer` = side sheet |
| `Tabs` | Tabs.tsx | Controlled; `pills` (segmented) or `underline`; animated indicator |
| `ToastProvider`, `useToast` | Toast.tsx, toast-context.ts | `toast.success/error(title, description?)`; slides in, auto-dismiss |
| `Callout` | Callout.tsx | One-line inline notice (info · success · warning · danger), optional action/dismiss |
| `Skeleton`, `SkeletonText`, `SkeletonRows` | Skeleton.tsx | Shimmer placeholders |
| `Spinner`, `PageSpinner` | Spinner.tsx | |
| `EmptyState`, `ErrorState` | EmptyState.tsx | Icon + short title + ⓘ + action; `ErrorState` shows the API `detail` and a Retry button |
| `PageHeader` | Misc.tsx | One-line page title · ⓘ · meta … actions |
| `Breadcrumbs` | Misc.tsx | Rendered in the top bar via `usePageMeta()` |
| `Avatar`, `Kbd`, `CopyButton`, `RelativeTime`, `TextLink` | Misc.tsx | `RelativeTime` shows "3m ago" with the full timestamp in a tooltip |

Motion: CSS keyframes in `src/styles/motion.css` (`.ui-pop`, `.ui-dialog`, `.ui-drawer-*`, `.ui-stagger`,
`.ui-skeleton`, `.ui-caret`) plus `motion/react` for route transitions, tab indicators, toasts and chat messages.
`prefers-reduced-motion` disables all of it (`MotionConfig reducedMotion="user"` + a CSS override).
