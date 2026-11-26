# Changelog

All notable changes to MrLiHua / 李华同学 are documented here.

## [1.1.0] - 2026-11-26

### Presentation

- Added classroom presentation mode: structure → analysis → vocabulary.
- Structure steps auto-locate and persistently highlight the corresponding passage section.
- Analysis steps move through questions and automatically reveal each answer.
- Removed the bottom presentation bar; all common clicker keys (including arrows, Space, Enter, F5, N/P, Home/End and unknown single characters) step next/previous.
- `B` blacks out the screen; `Esc` closes the drawer / exits blackout / exits presentation.
- Presentation state is in-memory only; normal browsing keyboard behavior is unchanged.

### Vocabulary

- Restored the original 20–37 words per section (185 total) and added the 185-entry whole-paper library.
- Preserved the five category tags, 1/2/3-column layout, exam points, synonyms, derivations and example translations.

### OCR / matching

- Added optional local RapidOCR extraction, question-bank building and Top-3 matching.
- Added a separate review report with match scores; OCR confidence is not displayed.
- Delivery builds strip OCR/match diagnostics; the report is never embedded in the final HTML.

### Proofreading

- Added inline plain-text correction for passages, translations, question stems, options and evidence.
- Corrections auto-save locally; users can download a corrected HTML or export a correction JSON.

### Responsive / devices

- Automatic Seewo 4K touch detection with `xlarge` text, standard desktop mode, and automatic mobile single-column mode.
- Added mobile/landscape layout fixes and no horizontal overflow.

### Delivery

- Final HTML remains single-file, offline, no CDN/backend/network requests.
- Updated README, SKILL, design and security documentation.

## [1.0.0] - 2026-10-28

First formal release.

### Vocabulary

- Expanded each section from 8 to **12 words** (84 words total across 7 sections).
- Added five vocabulary categories:
  - core high-frequency words
  - words with uncommon/figurative meanings
  - synonym replacement pairs
  - phrases and collocations
  - derivations / part-of-speech changes
- Added colored capsule tags and tinted rows for the five categories.
- Added responsive 1 / 2 / 3-column vocabulary layout based on the right-pane width.
- Added per-word exam points, synonym replacement notes, derivation chains,
  example translations and related section exam points.
- Improved the vocabulary drawer with category, IPA, collocations, exam points,
  examples and Chinese translations.

### Documentation / project

- Added README with screenshots, quick start, local-only audit and privacy notes.
- Added `AI_DISCLOSURE.md`, `SECURITY.md`, MIT `LICENSE`, `VERSION` and this changelog.
- Published a synthetic 12-word demo; no real exam papers or student data are bundled.

## [0.2.0] - 2026-10-28 · pre-release

- Added category-based vocabulary layout and richer word drawer.
- Updated the public README and demo screenshots.

## [0.1.0] - 2026-10-28 · pre-release

- Initial public release: single-file offline HTML reader, answer reveal,
  evidence highlighting, bilingual passages, structure/main-idea/exam tabs,
  touch-first layout and synthetic demo.
