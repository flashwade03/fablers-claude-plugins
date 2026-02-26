# fablers-claude-harness

Personal harness set for Claude Code — design methodology, review scoring, and session skill extraction.

**Languages**: [English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

## What is this?

A Claude Code plugin that provides structured workflows for software design and skill management. Instead of relying on ad-hoc prompting, this plugin encodes proven methodologies as reusable skills.

## Skills

### vibe-design

Guides the design process to produce exactly the right amount of specification for vibe coding. Prevents both over-specification and under-specification.

- Scope check: determines if a design document is even needed
- User dialogue: clarifies key decisions through structured conversation
- Decision maturity: separates confirmed decisions from candidates
- Domain checklists: ensures no critical decisions are missed

**Trigger**: "design a feature", "create architecture", "설계해줘", "아키텍처 잡아줘"

### design-review

Scores design documents against 6 vibe coding axes and outputs Grade (S~F), Score (0-100), and actionable feedback.

| Axis | What it checks |
|------|---------------|
| Decision Purity | Decisions only, no implementation details |
| Rationale Presence | Every decision has a "why" |
| Decision Maturity | Confirmed vs candidate items separated |
| Context Budget | Fits in ~200-300 lines |
| Constraint Quality | Boundaries, not prescriptions |
| CLAUDE.md Alignment | Proper linking, no content duplication |

**Trigger**: "review my design", "score this design", "설계 리뷰해줘"

### session-skill-extractor

Analyzes the current session conversation to identify repeatable workflows, domain knowledge, or multi-step procedures worth turning into reusable skills.

- Scans conversation for 6 signal categories (repeated workflows, decision frameworks, quality gates, etc.)
- Scores candidates by reusability, complexity, and distinctness
- Presents proposals for user approval before creating
- Includes a transformation guide for converting raw conversation into structured skills

**Trigger**: "extract skill from conversation", "대화에서 스킬 추출해줘", "이 세션에서 스킬 만들 게 있어?"

## Installation

```bash
claude plugin add flashwade03/fablers-claude-harness
```

Or for local development:

```bash
claude --plugin-dir /path/to/fablers-claude-harness
```

## Project Structure

```
fablers-claude-harness/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
└── skills/
    ├── vibe-design/
    │   ├── SKILL.md
    │   └── references/
    ├── design-review/
    │   ├── SKILL.md
    │   ├── references/
    │   └── examples/
    └── session-skill-extractor/
        ├── SKILL.md
        └── references/
```

## License

MIT
