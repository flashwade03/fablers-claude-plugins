# fablers-claude-harness

Claude Code用パーソナルハーネスセット — 設計方法論、レビュースコアリング、セッションスキル抽出。

**Languages**: [English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

## これは何ですか？

ソフトウェア設計とスキル管理のための構造化されたワークフローを提供するClaude Codeプラグインです。場当たり的なプロンプティングの代わりに、実証済みの方法論を再利用可能なスキルとしてエンコードします。

## スキル

### vibe-design

バイブコーディングに最適なレベルの設計ドキュメントを作成するガイド。過剰設計と過少設計の両方を防止します。

- スコープチェック：設計ドキュメントが必要なレベルかどうかを判断
- ユーザー対話：構造化された質問で重要な決定を確定
- 決定成熟度：確定した決定と候補項目を分離
- ドメインチェックリスト：見落とした決定がないか確認

**トリガー**: "設計して", "アーキテクチャを決めて", "design a feature", "설계해줘"

### design-review

設計ドキュメントを6つの軸で評価し、グレード（S〜F）、スコア（0-100）、具体的なフィードバックを出力します。

| 軸 | 評価内容 |
|----|---------|
| Decision Purity | 決定のみか、実装の詳細はないか |
| Rationale Presence | すべての決定に「なぜ」があるか |
| Decision Maturity | 確定/候補が分離されているか |
| Context Budget | 約200-300行に収まるか |
| Constraint Quality | 境界か、処方か |
| CLAUDE.md Alignment | リンクが適切で、内容の重複がないか |

**トリガー**: "設計をレビューして", "設計を評価して", "review my design", "설계 리뷰해줘"

### session-skill-extractor

現在のセッション会話を分析して、繰り返し可能なワークフロー、ドメイン知識、マルチステップ手順を見つけてスキルとして作成します。

- 6つのシグナルカテゴリで会話をスキャン（繰り返しワークフロー、決定フレームワーク、品質ゲートなど）
- 再利用性、複雑さ、独自性で候補をスコアリング
- ユーザー承認後にのみスキルを作成
- 会話→スキル変換ガイドを含む

**トリガー**: "会話からスキルを抽出して", "このセッションでスキルにできるものはある？", "extract skill from conversation"

## インストール

```bash
claude plugin add flashwade03/fablers-claude-harness
```

ローカル開発の場合：

```bash
claude --plugin-dir /path/to/fablers-claude-harness
```

## プロジェクト構造

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

## ライセンス

MIT
