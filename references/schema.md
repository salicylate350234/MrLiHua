# Exam JSON Schema

`exam.json` 是唯一数据源。HTML 只由 `scripts/build_exam.py` 从它生成。

## 顶层

```json
{
  "schemaVersion": 1,
  "meta": {
    "title": "英语试卷 · 交互解析",
    "subtitle": "阅读 A–D · 七选五 · 完形填空 · 语法填空",
    "exam": "样卷（手机拍摄，第 2–8 页）",
    "source": "用户提供的 7 页试卷照片",
    "answerSource": "inferred",
    "answerNote": "没有答案页，答案由当前文本推导。",
    "generatedAt": "2026-10-27"
  },
  "sections": []
}
```

- `answerSource`：`"key"` 或 `"inferred"`，控制每题卡片的来源标签。题目级可覆盖。
- 不要在 `meta` 写地区、学校、年级、考试年份等未经用户确认的信息。

## Section

```json
{
  "id": "reading-a",
  "kind": "reading",
  "label": "阅读 A",
  "title": "阅读理解 A",
  "topic": "气候类型",
  "genre": "说明文",
  "pages": "第 2–3 页",
  "intro": "阅读下列短文……",
  "passage": { "blocks": [] },
  "questions": [],
  "vocab": [],
  "complex": []
}
```

`kind` 只能是：

- `reading`：阅读 A–D；
- `seven`：七选五；
- `cloze`：完形填空；
- `grammar`：语法填空。

`topic` 是中文短标题，`genre` 是文体，`pages` 是图片页码（只写用户图片事实，不写考试来源）。

## Passage block

### 普通段落 / 标题 / 项目符号

```json
{ "id": "A-p2", "kind": "paragraph", "text": "Temperate climates lie in ...", "zh": "温带气候位于……" }
{ "id": "A-h1", "kind": "heading", "text": "Temperate Climate" }
{ "id": "S-h1", "kind": "bullet-heading", "text": "Keep a diary." }
{ "id": "S-h4", "kind": "bullet-gap", "text": "{{40}}" }
```

- 所有空格都写成 `{{41}}`（双花括号 + 题号），每个编号只出现一次。
- 七选五的“• 40”用 `bullet-gap`。
- 语法提示保留在正文：`{{57}} (continue)`。

### 图表

```json
{
  "id": "A-fig1",
  "kind": "figure",
  "src": "data:image/webp;base64,...",
  "alt": "阅读 A 中的气候分布图"
}
```

- `src` 必须是内嵌 `data:image/...`；
- 图表是题目信息的一部分，不能用文字描述替代；
- 压缩到合理大小，避免 HTML 过大。

## Question

```json
{
  "id": "21",
  "stem": "Which one has four clear seasons?",
  "options": [
    { "key": "A", "text": "The equatorial climate." },
    { "key": "B", "text": "The temperate climate." },
    { "key": "C", "text": "The polar climate." },
    { "key": "D", "text": "The tropical climate." }
  ],
  "answer": "B",
  "answerSource": "inferred",
  "confidence": 0.97,
  "type": "detail",
  "typeLabel": "细节理解",
  "evidence": [],
  "links": [],
  "optionNotes": {},
  "takeaway": "先锁定题干关键词，再回原文定位。"
}
```

- `type` 是内部枚举，`typeLabel` 是中文展示。
- `confidence` 仅对 `inferred` 有意义；`key` 不需要。
- `optionNotes` 的 key 是选项字母；至少写错误选项的具体错因。
- 七选五的 `options` 留空，选项放在 section 的 `optionBank`。
- 语法填空 `options` 留空，`answer` 是字符串，另加 `grammar`。

### 七选五

```json
{
  "id": "36",
  "stem": "第 36 空",
  "options": [],
  "answer": "C",
  "evidence": [],
  "links": [],
  "optionNotes": {}
}
```

section 顶层：

```json
"optionBank": [
  { "key": "A", "text": "Ask others about yourself." }
]
```

### 语法填空

```json
{
  "id": "56",
  "stem": "第 56 空",
  "options": [],
  "answer": "in",
  "type": "grammar",
  "typeLabel": "介词搭配",
  "grammar": {
    "point": "介词搭配",
    "cue": "interest ___ the language",
    "rule": "interest in sth 是固定搭配……",
    "translation": "她对这门语言的兴趣始于小学。"
  },
  "evidence": []
}
```

## Evidence

```json
{
  "id": "21-E1",
  "block": "A-p2",
  "quote": "They have four clear seasons (winter, spring, autumn, summer) and frequent weather changes because of storms.",
  "supports": ["B"],
  "refutes": [],
  "note": "题干 four clear seasons 与原文直接对应。",
  "translation": "它们有四个分明的季节……"
}
```

- `quote` 必须是 `block.text` 的精确子串（`{{41}}` 也算一个字符）。
- `supports`：这句话支持哪些选项；
- `refutes`：这句话与哪些选项冲突；
- 一个空数组表示“只作为该题的整体依据”，不区分选项（语法填空常用）。
- 一个题可以有多条 evidence；每条都会在原文中高亮。

## Links

```json
{
  "optionKey": "B",
  "optionPhrase": "The temperate climate",
  "sourcePhrase": "Temperate climates",
  "type": "paraphrase",
  "note": "选项用单数指代整类气候。"
}
```

`type` 建议使用：

- `synonym`：同义；
- `paraphrase`：改写/转述；
- `antonym`：反义/转折；
- `logic`：逻辑衔接（however、therefore 等）；
- `collocation`：固定搭配；
- `inference`：需要一步推断；
- `reference`：代词/指代。

`sourcePhrase` 可以是多个片段，用 ` ... ` 分隔；每一段都必须能在原文/证据中找到。不要为了好看硬造同义词。

## Structure & Exam Points

Section 可以带两份课堂数据：

```json
"structure": {
  "type": "说明文",
  "overview": "总—分结构……",
  "parts": [
    {"label": "第1段", "function": "引入", "main": "……", "blocks": ["A-p1"]}
  ],
  "logic": "……",
  "examFocus": "……"
},
"mainIdeaChain": [
  {"label": "总起", "idea": "……", "blocks": ["A-p1"]}
],
"mainIdea": {
  "statement": "一句话主旨……",
  "purpose": "写作目的……",
  "theme": "主题……",
  "tone": "语气……"
},
"examPoints": [
  {
    "title": "loss aversion",
    "kind": "术语猜词",
    "words": ["aversion", "loss"],
    "analysis": "……",
    "questions": ["25"]
  }
]
```

- `structure` / `mainIdeaChain` 用于右栏“结构”选项卡；
- `mainIdea` 并入右栏“结构”选项卡的“一句话主旨”；
- `parts[].blocks`、`mainIdeaChain[].blocks` 和 `examPoints[].questions` 共同生成原文锚点；
- 两者都是**当前篇**内容，不跨篇混排。

## Vocabulary

```json
{
  "id": "v-temperate",
  "word": "temperate",
  "block": "A-p2",
  "context": "Temperate climates lie in temperate latitudes ...",
  "ipa": "/ˈtempərət/",
  "pos": "adj.",
  "meaning": "温带的；气候温和的",
  "collocation": "temperate climate / temperate zone",
  "example": "These plants grow well in a temperate climate.",
  "level": "core",
  "wordlist": true
}
```

- `context` 必须是原文精确子串；
- `word` 必须在 `context` 中；
- `level`：`core`（高考 3500 基线）或 `beyond`（超纲/拓展）；
- `wordlist`（可选）：`true` 表示进入顶部全卷单词清单；`false` 表示只做行内注释、不进清单；
- 顶部全局单词清单优先读取 `wordlist: true` 且 `level: core` 的词；如果没有 `wordlist` 字段，才回退到 `core` 并排除低频专有/技术词；
- 每篇 8–12 个，不要把所有生词都标上。

## Complex sentence

```json
{
  "id": "A-c1",
  "block": "A-p2",
  "quote": "Temperate climates lie in temperate latitudes ...",
  "main": "Temperate climates lie in temperate latitudes.",
  "layers": ["括号内容说明范围。", "north and south of ... 限定位置。"],
  "translation": "温带气候位于温带纬度地区……"
}
```

- `quote` 必须是原文精确子串；
- `main` 是主句骨架；
- `layers` 是 2–4 条结构层次；
- `translation` 是中文参考翻译；
- 每篇 2–4 个，不要全文逐句分析。

## 校验

```powershell
python scripts/validate_exam.py data/your_exam.json
```

任何 quote、选项、空格、词汇、长难句锚点不匹配都会报错。先修数据，再构建。
