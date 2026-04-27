# Bot Cockpit Experience: Attention And Navigation

Detailed behavioral contracts moved out of the top-level spec to keep the parent
document scannable and within fragmentation limits.

## 1. "Needs Attention" — Unified Definition

### Problem

Both the home dashboard and the discovery cockpit have a "Needs attention" concept,
defined independently with no shared contract. The home dashboard's count may be
inconsistent with what the discovery cockpit surfaces. The operator sees two different
"attention" signals with no clear relationship.

### Decision: unified count on home, breakdown in each section

The home dashboard `Needs attention` count is the **union** of engagement and discovery
failures. It answers: "is there anything broken that requires my input right now?"

Each section (Engagement → candidate list with `failed` status, Discovery → attention
screen) shows its own breakdown when the operator drills in.

### What counts as "Needs attention"

#### Engagement (always included)

| Condition | Example |
|---|---|
| Candidates with `failed` status | Draft generation failed, send failed |
| Communities whose last detect job failed | Worker error, account issue |
| Communities whose last join job failed | FloodWait unresolved, ban |

#### Discovery (included in home count from the start)

| Condition | Example |
|---|---|
| Searches with failed example checks | Private channel, not found |
| Searches with no usable examples | All examples failed |
| Collection jobs that failed for watched communities | Snapshot error |

### What does not count

- Candidates in `needs_review` status — these are normal work, shown in the Review count.
- Candidates in `approved` status — shown in the Send count.
- Candidates in `sent`, `rejected`, or `expired` status — terminal states, no action needed.
- Discovery candidates pending review — surfaced in Discovery, not as Needs attention.

### Home card format

```text
Operator cockpit

⚠ Review: 3 replies
📤 Ready to send: 2
⛔ Needs attention: 4     ← engagement (2) + discovery (2)
```

The count is a single number. The breakdown is visible only when the operator taps
into the relevant section. Discovery failures appear in `disc:attention`.
Engagement failures appear in the candidate list filtered to `failed` status.

### "Needs attention" tap routing

Tapping `Needs attention` on the home dashboard routes to whichever section has
the higher count. If engagement failures dominate, route to `eng:candidates failed 0`.
If discovery failures dominate, route to `disc:attention`. If equal, prefer engagement.

A `Home` back button is always present on the routed screen so the operator can
return without navigating back through the section.

### API contract

The home dashboard API call must return:

```json
{
  "needs_review": 3,
  "approved": 2,
  "attention_engagement": 2,
  "attention_discovery": 2
}
```

The bot sums `attention_engagement` and `attention_discovery` for the display count
and stores both to determine tap routing.

## 2. Navigation Footer Contract

### Problem

Back and Home buttons are added ad hoc to each screen. Different screens use different
back targets, some screens have no navigation footer at all, and new screens drift
from whatever implicit convention existed before.

### Navigation levels

Every screen belongs to one of four levels:

| Level | Examples |
|---|---|
| 0 — Home | `op:home` |
| 1 — Section home | `op:manage`, `disc:home`, `op:help`, `op:accounts` |
| 2 — List | Community list, topic list, candidate list, style rule list |
| 3 — Item card | Community card, candidate card, topic card, prompt card |
| Modal | Wizard steps, confirmation dialogs, config edit prompts |

### Footer rules

| Screen level | Back button | Home button |
|---|---|---|
| 0 — Home | None | None |
| 1 — Section home | None | `Home` → `op:home` |
| 2 — List | `Back` → parent level 1 | `Home` → `op:home` |
| 3 — Item card | `Back` → parent level 2 | `Home` → `op:home` |
| Modal | `Back` → previous modal step or entry point | None |

Rules:

- **Level 0** has no footer. It is the home.
- **Level 1** has `Home` only. Back is omitted because there is no meaningful parent
  below the home screen — pressing Home does the same thing.
- **Level 2** has both `Back` and `Home`. Back goes to the section that owns the list,
  not to the previous message in Telegram history.
- **Level 3** has both `Back` and `Home`. Back goes to the list that owns the item.
- **Modal** screens have `Back` only. `Home` is omitted from modals because abandoning
  a multi-step flow by jumping to home leaves partial state. The operator should use
  `/cancel_edit` or step back through the flow.

### Stable back targets

`Back` routes to a **stable, named parent**, not to a per-message history stack.
The target is determined by the screen's place in the hierarchy, not by how the
operator navigated there.

| Screen | Back target |
|---|---|
| Community list (`eng:targets`) | `op:manage` |
| Topic list (`eng:topic_list`) | `op:manage` |
| Style rule list (`eng:style`) | `op:manage` |
| Candidate list (`eng:candidates`) | `op:home` |
| Community card (`eng:target_open`) | `eng:targets 0` |
| Candidate card (`eng:candidate_open`) | `eng:candidates <status> 0` |
| Settings card (`eng:settings_open`) | Community card for that community |
| Topic card | `eng:topic_list 0` |
| Style rule card | `eng:style all - 0` |
| Prompt profile card | `eng:prompts 0` |
| Discovery list screens | `disc:home` |
| Discovery item cards | Parent discovery list |

### Wizard exception

Wizard steps are modals. Each step's `Back` button returns to the previous step, not
to the screen that launched the wizard. The wizard is exited via `/cancel_edit` or by
completing it.

On completion, the wizard lands the operator on the community settings card for the
newly configured community (level 3), with a standard `Back` → community list and
`Home` → `op:home` footer.

### Implementation notes

- `_with_navigation` in `bot/ui_common.py` accepts `back_action`, `back_parts`, and
  `home_action` parameters. Audit every call site to verify it matches the level rules
  above.
- Add a `home_action` default of `ACTION_OP_HOME` to `_with_navigation`. Screens that
  are level 0 or level 1 pass `include_home=False` explicitly.
- Modal screens pass `include_home=False`.
- The `Home` button label is always `🏠 Home` for consistency. `Back` is always `← Back`.

### Testing contract

- Unit test: every `*_markup()` function in `bot/ui_engagement.py` and `bot/ui_discovery.py`
  that represents a level-2 or level-3 screen includes both `Back` and `Home` buttons.
- Unit test: every level-1 markup includes `Home` and omits `Back`.
- Unit test: `operator_home_markup()` includes neither `Back` nor `Home`.
- Unit test: wizard step markups include `Back` and omit `Home`.
