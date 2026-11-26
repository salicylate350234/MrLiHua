# -*- coding: utf-8 -*-
"""Build a local question-bank JSON from an existing exam JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def compact(text: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9]+", "", s)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a question bank from exam.json")
    ap.add_argument("exam")
    ap.add_argument("-o", "--out", default="bank.json")
    ap.add_argument("--source", default="", help="source label; defaults to meta.exam")
    args = ap.parse_args()

    exam = json.loads(Path(args.exam).read_text(encoding="utf-8"))
    meta = exam.get("meta", {})
    source = args.source or meta.get("exam", "") or Path(args.exam).stem
    questions = []
    for sec in exam.get("sections", []):
        passage = " ".join(b.get("text", "") for b in sec.get("passage", {}).get("blocks", []))
        passage_hash = hashlib.sha1(compact(passage).encode("utf-8")).hexdigest()[:16]
        for q in sec.get("questions", []):
            questions.append({
                "id": f"{sec.get('id')}-{q.get('id')}",
                "source": source,
                "section": sec.get("id"),
                "sectionLabel": sec.get("label") or sec.get("title") or "",
                "number": str(q.get("id", "")),
                "stem": q.get("stem", ""),
                "options": {o.get("key", ""): o.get("text", "") for o in q.get("options", [])},
                "answer": q.get("answer", ""),
                "answerSource": q.get("answerSource") or sec.get("answerSource") or meta.get("answerSource", ""),
                "passageHash": passage_hash,
                "topic": sec.get("topic", ""),
            })
    bank = {
        "version": 1,
        "source": source,
        "count": len(questions),
        "questions": questions,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"bank wrote {out} questions={len(questions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
