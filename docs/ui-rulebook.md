# UI Rulebook: How the Dashboard Looks and Behaves

> Rules every page follows, so the dashboard feels like one product. Code: `frontend/src/`.
> When you add a page, check it against this list.

## 1. Principles

1. **Explain, don't just alarm.** Every finding shows *why* (the explanation text), not only a red badge.
2. **The most urgent thing first.** Queues sort by most recent activity; Overview leads with active incidents.
3. **Never pretend.** No fake success messages; errors are shown as they are, with a "Try again" button.
4. **The backend decides security.** The UI hides actions you can't do, for convenience only.
5. **Readable by everyone.** Keyboard usable, visible focus, colour never the only signal.

## 2. Layout

- Left **sidebar**: brand, navigation (Overview, Incidents, Detections, Events, Simulator, Admin for admins), the logged-in user and **Log out**.
- **Page header**: title + one-line subtitle saying what the page is for; actions on the right.
- **Content** max width 1280 px. Cards with 16 px padding, 10 px radius, 1 px border.
- Under 860 px wide, the sidebar becomes a top bar and two-column layouts stack.

## 3. Colour (design tokens in `styles.css`)

- All colours are **CSS variables** (`--accent`, `--sev-high`…). Pages never hard-code a colour.
- **Dark mode** follows the operating system (`prefers-color-scheme`) by swapping token values.
- **Severity colours**, always together with the word:

| Severity | Meaning for the analyst |
|---|---|
| Critical | Several different signals for one account: look now |
| High | A likely compromise or powerful change |
| Medium | Suspicious, worth reviewing today |
| Low | Informational |

- **Status badges** are outlined (not filled), so they're never confused with severity:
  - open = red;
  - acknowledged / investigating = amber;
  - resolved / closed = green.
- **Source badges:** `Rule` (grey) or `ML · score` (accent). An analyst must always know whether a human-written rule or a statistical model raised it.

## 4. Components (reuse them; don't re-invent)

| Component | Use for |
|---|---|
| `SeverityBadge`, `StatusBadge`, `SourceBadge` | Any severity / status / origin |
| `PageHeader` | Top of every page |
| `Loading` | While the first data loads |
| `ErrorBox` | Any failed request (with a retry action when possible) |
| `Empty` | A list with nothing in it. Say *why* and what to do ("Try the Simulator") |
| `Pager` | Long lists (Newer / Older, with "Showing 1–25") |

## 5. Data states (every list must handle all four)

1. **Loading**: "Loading…".
2. **Error**: `ErrorBox` with the server's message.
3. **Empty**: `Empty` with a helpful sentence.
4. **Data**: table or list.

## 6. Forms and actions

- Labels above inputs; placeholders show an example, never replace the label.
- Disable the button while a request runs ("Signing in…", "Sending… 40%").
- Destructive or permanent actions say so before you click: "Notes are permanent", "Copy this key now. It will never be shown again".
- Only offer valid next steps. Incident status buttons follow the state machine; a closed incident shows no actions.

## 7. Text

- Plain words: "Mark investigating", "Assign to me", "Resolve…".
- Times: relative in lists ("5 min ago", exact time on hover), exact in timelines.
- Codes are humanized for display (`true_positive` → "True positive"), but rule codes stay as-is (`AUTH-001`), because analysts search for them.

## 8. Filters live in the URL

`/incidents?status=open&severity=high` can be bookmarked or shared, and Back works as expected.

## 9. Accessibility checklist

- [x] Every input has a label or `aria-label`
- [x] Visible focus outline on buttons, links and inputs
- [x] Severity and outcome are shown in **text** as well as colour
- [x] Errors use `role="alert"`, loading uses `role="status"`
- [ ] Automated accessibility test (axe) in CI: roadmap
