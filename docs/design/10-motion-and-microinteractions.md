# PharmaCore — Motion & Micro-interactions

Motion in PharmaCore **orients and confirms** — it never entertains. In a high-volume,
high-stakes tool, animation that draws attention to itself is a defect. The rule of
thumb: if a user *notices* the animation instead of the result, it's too much.

---

## 1. Principles
1. **Fast & subtle.** Nothing animates longer than 300ms; most is 150–200ms.
2. **Purposeful only.** Motion exists to (a) show where something came from/went,
   (b) confirm an action happened, or (c) direct the eye to what changed. No
   decorative loops, no parallax, no bouncing.
3. **Respect the system.** All motion is disabled under `prefers-reduced-motion:
   reduce` — replaced by instant state changes (never by "nothing happened").
4. **Consistent physics.** The same kind of element always moves the same way — a
   drawer always slides from the right at the same speed. Predictability = calm.
5. **Never block work.** Animation never delays the user's ability to act; the UI is
   interactive immediately, motion plays alongside.

---

## 2. The motion tokens (from [01-design-tokens.md](01-design-tokens.md))
| Token | Duration · easing | Applied to |
|---|---|---|
| `--motion-fast` | **150ms** ease-out | hover, focus ring, small state (checkbox, toggle) |
| `--motion-base` | **200ms** ease-out | dropdowns, popovers, tabs, toasts |
| `--motion-panel` | **250ms** cubic-bezier(.2,.8,.2,1) | drawers, modals, command palette |
| (reduced) | **0ms** / opacity-only | when `prefers-reduced-motion` |

Easing: **ease-out** for enters (decelerate into place — feels responsive);
**ease-in** for exits; the panel curve for larger surfaces (a gentle overshoot-free settle).

---

## 3. Micro-interaction catalog (canonical behaviors)

| Interaction | Motion |
|---|---|
| **Button hover** | background darkens 1 step over 150ms; `cursor-pointer` |
| **Button press** | scale 0.98 / inset feel, instant; release springs back 100ms |
| **Button loading** | label stays, inline spinner fades in; button non-interactive |
| **Focus** | 2px focus ring fades in 150ms (never removed for mouse users) |
| **Popover / dropdown open** | fade + 4px rise, 200ms ease-out, from the trigger |
| **Context drawer** | slides in from right 250ms; backdrop dim 0→ for non-blocking is subtle |
| **Modal** | backdrop fades 200ms; dialog fades + 8px rise 250ms; focus trap engages |
| **Toast** | slides up + fades in from bottom-right 200ms; auto-dismiss fades out |
| **Row hover (table)** | background tint 100ms — must be near-instant for scanning |
| **Row select** | left accent bar wipes in 150ms + tint |
| **Tab change** | content cross-fades 150ms; active underline slides to new tab 200ms |
| **Accordion / expand** | height + opacity 200ms ease-out |
| **Inline edit commit** | field flashes a subtle success tint 300ms then settles |
| **Delete/void row** | row collapses (height→0) 200ms after confirm, not before |
| **Skeleton loading** | gentle shimmer 1.2s loop (the one allowed loop; stops on load) |
| **Number/KPI update** | count-up tween ≤400ms only on dashboards (off under reduced-motion) |
| **Nav collapse/expand** | width 200ms; labels fade to avoid text reflow flash |

---

## 4. Domain-specific feedback (where motion carries real meaning)
These are the moments where a confirming animation genuinely reduces error:

- **Add to cart (POS):** the picked item animates a short 200ms slide into the cart
  panel — a clear "it landed" cue for a fast cashier. The cart total ticks up.
- **Batch picked (FEFO):** the selected batch row briefly highlights in the popover
  before it closes, confirming *which* batch was chosen.
- **Payment success:** a single, calm success check draws in (200ms) on the receipt
  panel; then the cart resets with a quick clear. No confetti — this is a pharmacy.
- **GRN line verified:** each scanned/entered line gets a quick check-tint; a
  discrepancy line pulses the warning color **once** (not repeatedly).
- **Sync / offline:** an unobtrusive status chip animates between states
  (offline → syncing spinner → "12 synced" ✓). This is informative, always visible,
  never a blocking spinner over the counter.
- **EBM fiscalized:** a toast slides in ("Fiscal receipt received") — async success,
  no interruption.
- **Void / reversal:** the record gets a `VOID` stamp that fades in — deliberate and
  visible, because the consequence must be seen.

---

## 5. Loading & progress states (choosing the right one)
| Situation | Pattern |
|---|---|
| Content loading (list, detail) | **skeleton** of the real layout (not a spinner) |
| Button action in flight | **inline spinner** in the button |
| Known-length work (PDF batch, import) | **determinate bar** with count |
| Background job (EBM, sync) | **status chip / toast**, never a blocking overlay |
| Empty result | designed **empty state** (icon + message + primary action), not a spinner |

Rule: **never a full-screen blocking spinner** on the POS — it must always stay
operable. Long work goes to the background and reports via chip/toast.

---

## 6. Accessibility & performance
- `prefers-reduced-motion: reduce` → replace movement with instant opacity/state
  changes; keep the *information* (a toast still appears, it just doesn't slide).
- Animate only **transform** and **opacity** (GPU-cheap); avoid animating layout
  properties (width/height) except for short, contained reveals.
- No animation may trap focus or delay input handling.
- Motion is never the *only* signal of a state change — it accompanies a durable
  visual change (color, icon, text), never replaces it.

## 7. Do / Don't
| ✅ Do | ❌ Don't |
|---|---|
| 150–250ms, ease-out, transform+opacity | Long, springy, bouncy, or looping motion |
| One calm confirm per action | Confetti / celebratory effects in the workspace |
| Skeletons for content, chips for background work | Full-screen blocking spinners on the POS |
| Disable under reduced-motion (keep the info) | Remove the feedback entirely under reduced-motion |
| Same element → same motion everywhere | Different drawer speeds/directions per screen |
