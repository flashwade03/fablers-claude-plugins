# 5 Design Principles for Vibe Coding

## Principle 1: Decisions Only

Record WHAT was decided and WHY. Never HOW to implement it.

### Good Examples

```
- State machine: waiting → creating → playable ↔ modifying.
  Error state is only reachable from creating.
  Reason: modifying always has a fallback (previous working version).

- 2-layer architecture: Service Agent (conversation) ↔ Claude Code (coding).
  Reason: separates cheap/fast intent parsing from expensive/slow code generation.

- Ports allocated dynamically from range 5173-5199.
  Reason: multiple projects run simultaneously, static ports would conflict.
```

### Bad Examples (Implementation Masquerading as Design)

```
// This is CODE, not design:
const VALID_TRANSITIONS = {
  waiting: ['creating'],
  creating: ['playable', 'error', 'waiting'],
  playable: ['modifying', 'creating'],
  modifying: ['playable'],
  error: ['creating', 'waiting'],
};

function validateTransition(from, to) {
  if (!VALID_TRANSITIONS[from]?.includes(to)) {
    throw new Error(`Invalid transition: ${from} → ${to}`);
  }
}
```

The state machine decision (what states exist, what transitions are valid) is design.
The validation function is implementation. AI writes this from the decision.

### Test

For every line in the design document, ask: "Is this a decision, or is this telling the AI how to write code?" If the latter, delete it.

---

## Principle 2: Why, Not How

The "why" enables AI to make correct implementation decisions in cases the design didn't anticipate. The "how" constrains AI to a single implementation path that may not be optimal.

### Good Examples

```
- Dev server managed by service layer, not by Claude Code.
  Why: Claude Code runs in isolated subprocess with no access to shared port state.

- WebSocket for client-server communication, not REST polling.
  Why: real-time streaming of Claude Code output to browser.

- Boilerplate copied per project, not shared.
  Why: Claude Code modifies files in place; shared boilerplate would cause cross-contamination.
```

### Bad Examples

```
- Use Express middleware with http-proxy to forward requests to Vite dev servers.
  Register proxy with registerProxy(projectId, port) and unregister with unregisterProxy(projectId).
  Store in proxies Map<string, HttpProxy>.

- Use allocatePort() that checks reservedPorts Set, tries net.createServer().listen(),
  and returns the first available port. Call releasePortReservation() after DB commit.
```

These specify the exact implementation mechanism. An AI reading the "why" (dynamic port allocation for concurrent projects) would arrive at an equivalent or better implementation on its own.

### The Cascading Consistency Problem

When "how" is specified in design, every detail must be consistent with every other detail. In a real case study, specifying function signatures and resource management patterns in design documents led to 115 cross-reference bugs across 16 review rounds. These bugs would not have existed if only decisions were specified.

---

## Principle 3: Context Window Budget

In vibe coding, the design document is part of AI's working context. Every line of design competes with code, conversation history, and tool output for context space.

### Budget Guidelines

| Content | Budget | Location |
|---------|--------|----------|
| Core architecture decisions | ~200-300 lines | CLAUDE.md or inline |
| Constraint list | ~20-50 lines | Same document |
| Milestone scope | ~10-20 lines | Same document |
| Detailed reference (if needed) | Unlimited | Separate file, loaded on demand |

### Practical Test

If the design document, when prepended to a coding prompt, would push the conversation past 50% of context window before any code is written — it's too long.

### What This Means

A system with 7 tools, 5 state transitions, 6 shared data structures, dynamic port allocation, proxy management, health monitoring, crash recovery, and graceful shutdown — all of this can be described in ~200 lines of decisions and constraints. The 4,500-line version with pseudocode is 20x over budget.

---

## Principle 4: Milestone-Scoped

Design only what the NEXT implementation milestone requires. Designing future milestones prematurely:

1. Creates decisions based on assumptions that may change
2. Prevents incremental development (can't build v0 without implementing v2's error handling)
3. Bloats the design with details that compete for context space

### The Milestone Test

For each decision in the design, ask: "If I remove this, can I still build and demo the current milestone?"

If yes → defer to a later milestone.

### Example: Game Proto Agent

**v0 decisions (required to build the basic flow):**
- Express + WebSocket server
- Claude Code invoked via `claude -p` subprocess
- Projects stored in `protos/<userId>/<projectId>/`
- Boilerplate copied to project directory
- Single hardcoded port for dev server

**v0 does NOT need:**
- Dynamic port allocation (only one project at a time in v0)
- State machine (only one operation: create)
- Cancel mechanism (just wait for completion)
- Health monitoring (no concurrent projects to monitor)
- Crash recovery (restart the server)
- Proxy registration (single port, static route)

Each of these deferred items becomes a v1 or v2 decision, designed when that milestone begins.

---

## Principle 5: Constraints Over Prescriptions

Constraints define the boundary. Everything inside the boundary is AI's decision space.

### Effective Constraints

```
- Claude Code must NOT start dev servers (service layer manages ports)
- State transitions must go through a validation function (no direct DB updates)
- One Claude Code process per project at a time (no concurrent modifications)
- Boilerplate directory is read-only (always copy, never modify in place)
- Dev server ports must be released when project is deleted
```

### Ineffective Prescriptions (Disguised as Constraints)

```
- Must use http-proxy library for proxying  → This is a library choice, not a constraint
- Must store ports in SQLite with column type INTEGER  → This is a schema detail
- Must use Map<string, ChildProcess> for process tracking  → This is a data structure choice
- Must call releasePortReservation() in finally block  → This is an implementation pattern
```

### Why Constraints Work Better

AI operating within constraints exercises judgment. AI following prescriptions exercises compliance. When something unexpected happens during implementation (a library doesn't work, a pattern doesn't fit), constraint-guided AI adapts. Prescription-following AI either breaks the prescription or gets stuck.
