---
name: react-component
description: Use when adding or modifying a React component. Enforces functional + hooks style, Tailwind utilities, strict TS, accessibility basics.
---

# React + Tailwind component

## When to use

Adding a new component, modifying an existing one, or extracting a reusable piece.

## Layout

```
src/
  components/          # presentational, reusable
  features/<feature>/  # feature-scoped components + hooks
  hooks/               # cross-cutting hooks
  lib/                 # framework-agnostic utilities
```

## Rules

1. **Functional components only.** No class components.
2. **Strict TS.** Props typed, no `any`, no `as` casts unless commented why.
3. **Tailwind utilities.** No new `.css` files unless asked. Use `clsx` (or `cn` helper) for conditional classes.
4. **Accessibility**: every interactive element has a role / label. Images get `alt`. Forms label their inputs.
5. **No `dangerouslySetInnerHTML`** unless input is sanitized server-side AND a comment explains why.
6. **Effects**: list every dependency. Always return a cleanup if subscribing.
7. **Data fetching**: use the project's existing client (TanStack Query / SWR). Do not call `fetch` from inside a component.
8. **Server URLs come from config**, not hard-coded.
9. **i18n**: user-visible strings go through the i18n helper if the project has one.

## Template

```tsx
// src/components/UserCard.tsx
import { clsx } from "clsx";

type UserCardProps = {
  name: string;
  email: string;
  isActive: boolean;
  onSelect?: (email: string) => void;
  className?: string;
};

export function UserCard({ name, email, isActive, onSelect, className }: UserCardProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(email)}
      aria-label={`Select ${name}`}
      className={clsx(
        "flex w-full items-center gap-3 rounded-lg border p-3 text-left",
        "transition hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-blue-500",
        !isActive && "opacity-60",
        className,
      )}
    >
      <span className="font-medium">{name}</span>
      <span className="text-sm text-slate-500">{email}</span>
    </button>
  );
}
```

## Tests required

- One RTL test per visible state (e.g. active vs inactive).
- Click / keyboard interaction test where applicable.
- For data-loaded components, a loading + error state test using `msw`.
