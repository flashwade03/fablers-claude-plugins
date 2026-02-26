# fablers-claude-harness

Claude Code를 위한 개인 하네스 셋 — 설계 방법론, 리뷰 스코어링, 세션 스킬 추출.

**Languages**: [English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

## 이게 뭔가요?

소프트웨어 설계와 스킬 관리를 위한 구조화된 워크플로우를 제공하는 Claude Code 플러그인입니다. 즉흥적인 프롬프팅 대신, 검증된 방법론을 재사용 가능한 스킬로 인코딩합니다.

## 스킬

### vibe-design

바이브 코딩에 딱 맞는 수준의 설계 문서를 만들어주는 가이드. 과잉 설계와 과소 설계 모두를 방지합니다.

- 스코프 체크: 설계 문서가 필요한 수준인지 판단
- 사용자 대화: 구조화된 질문으로 핵심 결정 확정
- 결정 성숙도: 확정 결정과 후보 항목 분리
- 도메인 체크리스트: 빠진 결정 없는지 확인

**트리거**: "설계해줘", "아키텍처 잡아줘", "설계 범위 정해줘", "design a feature"

### design-review

설계 문서를 6개 축으로 평가하여 등급(S~F), 점수(0-100), 구체적 피드백을 출력합니다.

| 축 | 평가 내용 |
|----|----------|
| Decision Purity | 결정만 있는가, 구현 디테일은 없는가 |
| Rationale Presence | 모든 결정에 "왜"가 있는가 |
| Decision Maturity | 확정/후보가 분리되어 있는가 |
| Context Budget | ~200-300줄에 들어오는가 |
| Constraint Quality | 경계인가, 처방인가 |
| CLAUDE.md Alignment | 링크가 적절하고 내용 복제가 없는가 |

**트리거**: "설계 리뷰해줘", "설계 평가해줘", "이 설계 괜찮아?", "review my design"

### session-skill-extractor

현재 세션 대화를 분석해서 반복 가능한 워크플로우, 도메인 지식, 다단계 절차를 찾아 스킬로 만들어줍니다.

- 6가지 신호 카테고리로 대화 스캔 (반복 워크플로우, 결정 프레임워크, 품질 게이트 등)
- 재사용성, 복잡도, 고유성으로 후보 점수 매기기
- 사용자 승인 후에만 스킬 생성
- 대화 → 스킬 변환 가이드 포함

**트리거**: "대화에서 스킬 추출해줘", "이 세션에서 스킬 만들 게 있어?", "extract skill from conversation"

## 설치

```bash
claude plugin add flashwade03/fablers-claude-harness
```

로컬 개발 시:

```bash
claude --plugin-dir /path/to/fablers-claude-harness
```

## 프로젝트 구조

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

## 라이선스

MIT
