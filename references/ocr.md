# OCR + 本地题库匹配（免费版 MVP）

目标：把试卷照片先变成可搜索的题目块，再用本地题库找最佳候选，显示匹配度；
高匹配自动采用题库文本/答案，中低匹配人工确认。

> OCR 和匹配都是**构建期工具**，不是最终 HTML 的运行时依赖。最终 HTML 仍然离线、单文件。

## 1. 安装

```powershell
python -m pip install -r requirements-ocr.txt
```

`rapidocr_onnxruntime` 会把 ONNX 模型随 wheel 安装；运行时不联网。
中文/英文混排、印刷体照片比 Tesseract 更稳，Windows CPU 即可。

## 2. 从试卷图片提取 OCR

```powershell
python scripts/ocr_extract.py .\photos\p02.png .\photos\p03.png `
  --split -o work\ocr.json
```

- `--split`：把 4:3 双页展开图从中间切成左右两页；
- 输入可以是多个文件或目录；
- 输出 `ocr.json`，每行保留文本和四点坐标；
- 当前样例：3 张双页图 → 6 页、216 行。

## 3. 从已有 exam.json 建题库

```powershell
python scripts/build_bank.py data\hefei_october.json -o work\bank_hefei.json
```

题库结构：

```json
{
  "version": 1,
  "source": "2026 届...",
  "count": 45,
  "questions": [
    {
      "id": "reading-a-q21",
      "section": "reading-a",
      "sectionLabel": "阅读 A",
      "number": "21",
      "stem": "What will happen if ...",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "answer": "B",
      "answerSource": "key",
      "passageHash": "..."
    }
  ]
}
```

## 4. 匹配并生成报告

```powershell
python scripts/match_bank.py work\ocr.json `
  --bank work\bank_hefei.json `
  --out work\match.json `
  --report work\match_report.html
```

报告包含：

- OCR 题号、题干、选项；
- 题库最佳候选、答案；
- 匹配度 0–100%；
- Top 3 候选；
- 逐选项 OCR/题库相似度；
- 高 / 中 / 低匹配分级。

## 5. 匹配分

题干、选项、题号分层计算：

```text
有选项：
  score = 0.68 × 题干相似度
        + 0.27 × 选项集合相似度
        + 0.05 × 题号一致

无选项（七选五/语法填空）：
  score = 0.90 × 题干相似度
        + 0.10 × 题号一致
```

- 文本先做 NFKC、小写、去标点、去空白的 compact 归一化；
- 选项按**文本集合**比较，不依赖 A/B/C/D 顺序；
- 题干缺失但选项完整的孤立选项块，使用 `0.85 × 选项相似度` 恢复；
- 报告只显示题库匹配度，不显示 OCR 识别质量数据。

分级：

| 条件 | 状态 |
|---|---|
| ≥ 92% 且 Top1–Top2 ≥ 6% | 高匹配，可自动采用 |
| ≥ 75% | 需确认 |
| < 75% | 低匹配 / 题库无此题 |

## 6. 当前样例结果

用 2026 年 10 月合肥卷的 p02–p04（阅读 A–D）测试：

- OCR 题块：20 个；
- 高匹配：14 个；
- 需确认：1 个（Q24 题干 OCR 失败，但四个选项完整，按选项恢复为 85%）；
- 低匹配：5 个（听力 Q16–Q20，题库没有听力题）；
- 阅读 A–D 的 15 道题全部找到题库候选：14 道高匹配（其中 Q30 为 96%），Q24 题干 OCR 失败但选项完整，按选项恢复为 85%，需人工确认。

这说明“OCR + 题库匹配”可行，但**题干 OCR 失败时不能只靠题干**，选项恢复是必要兜底。

## 7. 已知限制

- 拍照倾斜、阴影、双页中缝会影响 OCR；当前样例使用 `--split`；
- 题号被截断时，靠选项块恢复，题号会显示为 `Q?`；
- 七选五的 A–G 选项不是题干选项，当前只保留 A–D 的孤立块，且低分孤立块会被丢弃；
- 手写体、公式、表格、复杂版面不在第一版范围；
- 题库含真实试卷时不要提交到公开仓库，放在本地 `work/` 或私有目录。

## 8. 后续接入

匹配报告和 `match.json` 只作为本地审核产物，不进入最终 HTML；`build_exam.py` 也会剥离
`match`、`matchScore`、`ocrConfidence` 等诊断字段。下一步可在高匹配时把题库的
`stem/options/answer` 回填到新的 `exam.json`，再交给
`build_exam.py` 生成 HTML；中低匹配进入人工确认页。当前 MVP 先输出独立报告，不直接修改
已有阅读页。
