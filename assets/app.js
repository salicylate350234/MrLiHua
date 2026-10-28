(() => {
  "use strict";

  const dataEl = document.getElementById("examData");
  if (!dataEl) return;

  let data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (err) {
    console.error("Invalid exam JSON", err);
    return;
  }

  const sections = Array.isArray(data.sections) ? data.sections : [];
  if (!sections.length) return;

  const sectionMap = new Map(sections.map((s) => [s.id, s]));
  const questionMap = new Map();
  const vocabMap = new Map();
  const complexMap = new Map();

  for (const section of sections) {
    for (const q of section.questions || []) {
      questionMap.set(String(q.id), { q, section });
    }
    for (const v of section.vocab || []) vocabMap.set(v.id, v);
    for (const c of section.complex || []) complexMap.set(c.id, c);
  }

  const state = {
    section: null,
    qid: null,
    opt: null,
    tab: "analysis",
  };

  const KIND_LABELS = {
    reading: "READING",
    seven: "SEVEN-CHOICE",
    cloze: "CLOZE",
    grammar: "GRAMMAR",
  };

  const isFinePointer = () => window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function currentSectionEl() {
    return state.section ? document.querySelector(`.exam-section[data-section="${state.section}"]`) : null;
  }

  function sectionWordCount(section) {
    const text = (section.passage && section.passage.blocks ? section.passage.blocks : [])
      .map((b) => b.text || "")
      .join(" ")
      .replace(/\{\{\d+\}\}/g, " ");
    const words = text.match(/[A-Za-z][A-Za-z'’\-]*/g);
    return words ? words.length : 0;
  }

  function updateSectionContext(section) {
    if (!section) return;
    const title = document.getElementById("contextTitle");
    const meta = document.getElementById("contextMeta");
    if (!title || !meta) return;
    title.textContent = section.topic || section.title || "";
    const genre = section.genre ? `${section.genre} · ` : "";
    meta.textContent = `${genre}${section.pages || ""} · 约 ${sectionWordCount(section)} 词 · ${(section.questions || []).length} 题`;
  }

  function setPressed(el, value) {
    if (el) el.setAttribute("aria-pressed", value ? "true" : "false");
  }

  function applyHighlight(qid, opt, options = {}) {
    const sectionEl = currentSectionEl();
    if (!sectionEl) return;
    const qEntry = questionMap.get(String(qid));
    if (!qEntry) return;
    const answer = String(qEntry.q.answer || "");
    const currentOpt = opt == null ? "" : String(opt);
    const card = sectionEl.querySelector(`.q-card[data-q="${qid}"]`);
    const revealed = Boolean(card && card.classList.contains("is-revealed"));

    // Options: only the option belonging to the active question may be active.
    $$(".option", sectionEl).forEach((el) => {
      const on = el.dataset.q === String(qid) && el.dataset.opt === currentOpt;
      el.classList.toggle("is-active", on);
      setPressed(el, on);
    });

    // Evidence spans: support/refute lists are space-separated.
    let anyOn = false;
    const evidence = $$(".ev", sectionEl);
    evidence.forEach((el) => {
      const sameQ = el.dataset.q === String(qid);
      const supports = (el.dataset.support || "").split(/\s+/).filter(Boolean);
      const refutes = (el.dataset.refute || "").split(/\s+/).filter(Boolean);
      let on = false;
      let refute = false;
      if (sameQ && revealed) {
        if (!currentOpt) {
          on = true;
        } else if (supports.includes(currentOpt) || refutes.includes(currentOpt)) {
          on = true;
          refute = refutes.includes(currentOpt);
        }
      }
      el.classList.toggle("is-on", on);
      el.classList.toggle("is-refute", on && refute);
      el.classList.remove("is-fallback");
      if (!on) {
        el.classList.remove("ev-awaiting", "ev-wipe");
      } else if (options.animateEvidence) {
        el.classList.add("ev-awaiting");
        el.classList.remove("ev-wipe");
      }
      if (on) anyOn = true;
    });

    // A wrong option may not have a direct "refutes" span.  In that case show
    // the key evidence for the correct answer in a lighter fallback style,
    // and explain why the highlight is not option-specific.
    let fallback = false;
    if (revealed && currentOpt && currentOpt !== answer && !anyOn) {
      evidence.forEach((el) => {
        if (el.dataset.q !== String(qid)) return;
        const supports = (el.dataset.support || "").split(/\s+/).filter(Boolean);
        if (!supports.length || supports.includes(answer)) {
          el.classList.add("is-on", "is-fallback");
          if (options.animateEvidence) {
            el.classList.add("ev-awaiting");
            el.classList.remove("ev-wipe");
          }
          anyOn = true;
          fallback = true;
        }
      });
    }

    // Gaps in the passage.
    $$(".gap", sectionEl).forEach((el) => {
      el.classList.toggle("is-active", el.dataset.gap === String(qid));
    });

    // Seven-choice option bank.
    $$(".bank-item", sectionEl).forEach((el) => {
      const on = el.dataset.gap === String(qid);
      el.classList.toggle("is-active", on);
      setPressed(el, on);
    });

    // Link chips inside the active card.
    $$(".link-chip", sectionEl).forEach((el) => {
      const on = el.dataset.q === String(qid) && el.dataset.opt === currentOpt;
      el.classList.toggle("is-current", on);
    });

    // Keep the active card's current answer state accessible.
    if (card) {
      card.dataset.currentOpt = currentOpt;
      card.dataset.answer = answer;
      const feedback = card.querySelector(".q-feedback");
      if (feedback) {
        if (fallback) {
          feedback.hidden = false;
          feedback.textContent = "该选项在原文中没有直接依据；下面以浅色显示本题正确项的关键依据，便于对照排除。";
        } else {
          feedback.hidden = true;
          feedback.textContent = "";
        }
      }
    }
  }

  function scrollEvidenceIntoView(onDone) {
    const sectionEl = currentSectionEl();
    if (!sectionEl) {
      if (onDone) onDone();
      return;
    }
    const pane = sectionEl.querySelector(".passage-pane");
    const ev = pane ? pane.querySelector(".ev.is-on") : null;
    if (!pane || !ev) {
      if (onDone) onDone();
      return;
    }

    // Scroll to the paragraph that contains the evidence, not to the inline
    // span itself.  This keeps the paragraph in context and lets the inline
    // highlight animate only after the smooth scroll has completely stopped.
    const block = ev.closest("[data-block]") || ev;
    const pr = pane.getBoundingClientRect();
    const br = block.getBoundingClientRect();
    const head = pane.querySelector(".pane-head");
    const headH = head ? head.getBoundingClientRect().height : 0;
    const needsScroll = br.top < pr.top + headH + 8 || br.bottom > pr.bottom - 24;

    if (!needsScroll) {
      if (onDone) requestAnimationFrame(onDone);
      return;
    }

    if (!onDone) {
      block.scrollIntoView({ block: "center", behavior: reduceMotion() ? "auto" : "smooth" });
      return;
    }

    let done = false;
    let quietTimer = null;
    let hardTimer = null;
    const finish = () => {
      if (done) return;
      done = true;
      if (quietTimer) clearTimeout(quietTimer);
      if (hardTimer) clearTimeout(hardTimer);
      pane.removeEventListener("scroll", onScroll);
      pane.removeEventListener("scrollend", finish);
      onDone();
    };
    const onScroll = () => {
      if (quietTimer) clearTimeout(quietTimer);
      quietTimer = setTimeout(finish, 140);
    };

    pane.addEventListener("scroll", onScroll, { passive: true });
    pane.addEventListener("scrollend", finish, { once: true });
    hardTimer = setTimeout(finish, 1200);

    const behavior = reduceMotion() ? "auto" : "smooth";
    block.scrollIntoView({ block: "center", behavior });
    if (behavior === "auto") requestAnimationFrame(finish);
  }

  function playEvidenceWipe(qid) {
    const sectionEl = currentSectionEl();
    if (!sectionEl) return;
    const spans = $$(`.ev[data-q="${String(qid)}"].is-on`, sectionEl);
    spans.forEach((el) => {
      el.classList.remove("ev-awaiting");
      el.classList.add("ev-wipe");
    });
  }

  function scrollCardIntoView(qid) {
    const sectionEl = currentSectionEl();
    if (!sectionEl) return;
    const card = sectionEl.querySelector(`.q-card[data-q="${qid}"]`);
    if (card) {
      card.scrollIntoView({ block: "nearest", behavior: reduceMotion() ? "auto" : "smooth" });
    }
  }

  function activate(qid, opt, options = {}) {
    const entry = questionMap.get(String(qid));
    if (!entry) return;
    state.qid = String(qid);
    // Grammar answers are words, not option keys.  Empty opt means "show all
    // evidence for this blank"; it must not be compared with option letters.
    state.opt = entry.section.kind === "grammar" ? "" : (opt == null ? "" : String(opt));

    const sectionEl = currentSectionEl();
    if (!sectionEl) return;

    $$(".q-card", sectionEl).forEach((el) => {
      el.classList.toggle("is-active", el.dataset.q === String(qid));
    });
    $$(".q-chip", sectionEl).forEach((el) => {
      const on = el.dataset.qjump === String(qid);
      el.setAttribute("aria-current", on ? "true" : "false");
    });

    applyHighlight(state.qid, state.opt, { animateEvidence: options.animateEvidence });

    if (options.scrollCard) scrollCardIntoView(state.qid);
    if (options.scrollEvidence !== false) {
      // Only scroll the passage when the user chose an option/gap, not when
      // switching sections (the pane is already at the top).
      if (options.scrollEvidence) scrollEvidenceIntoView();
    }
  }

  function showSection(id, options = {}) {
    const section = sectionMap.get(id);
    if (!section) return;
    closeWordlist(false);
    state.section = id;
    updateSectionContext(section);
    const select = document.getElementById("sectionSelect");
    if (select) select.value = id;

    $$(".exam-section").forEach((el) => {
      el.hidden = el.dataset.section !== id;
    });
    $$(".section-tab").forEach((el) => {
      el.setAttribute("aria-current", el.dataset.target === id ? "true" : "false");
    });

    const sectionEl = currentSectionEl();
    if (!sectionEl) return;
    $$(".pane", sectionEl).forEach((p) => { p.scrollTop = 0; });
    setTab(state.tab, { scroll: false });

    const first = (section.questions || [])[0];
    if (first) {
      activate(first.id, "", { scrollCard: false, scrollEvidence: false });
    }

    try {
      history.replaceState(null, "", `#/${id}`);
    } catch (_) { /* file:// can be strict; ignore */ }

    applyWorkspaceState();

    if (options.focusNav) {
      const tab = document.querySelector(`.section-tab[data-target="${id}"]`);
      if (tab) tab.focus({ preventScroll: true });
    }
  }

  /* ---------- split view ---------- */
  let splitRatio = 56;
  let collapsedSide = null;
  let splitDrag = null;

  function setSplitValue(value) {
    splitRatio = Math.max(20, Math.min(80, Number(value) || 56));
    document.documentElement.style.setProperty("--split", `${splitRatio}%`);
    $$(".splitter").forEach((sp) => sp.setAttribute("aria-valuenow", String(Math.round(splitRatio))));
  }

  function applyWorkspaceState() {
    $$(".workspace").forEach((ws) => {
      ws.classList.toggle("is-collapsed-passage", collapsedSide === "passage");
      ws.classList.toggle("is-collapsed-analysis", collapsedSide === "analysis");
    });
    $$(".splitter").forEach((sp) => sp.setAttribute("aria-valuenow", String(Math.round(splitRatio))));
  }

  function collapseWorkspaceSide(side) {
    if (side !== "passage" && side !== "analysis") return;
    collapsedSide = side;
    applyWorkspaceState();
    const rail = document.querySelector(`.collapsed-rail[data-expand="${side}"]`);
    if (rail) rail.focus({ preventScroll: true });
  }

  function expandWorkspaceSide() {
    collapsedSide = null;
    setSplitValue(56);
    applyWorkspaceState();
    const sectionEl = currentSectionEl();
    const splitter = sectionEl ? sectionEl.querySelector(".splitter") : null;
    if (splitter) splitter.focus({ preventScroll: true });
  }

  function splitFromEvent(event, workspace) {
    const rect = workspace.getBoundingClientRect();
    if (rect.width <= 0) return;
    setSplitValue(((event.clientX - rect.left) / rect.width) * 100);
  }

  function initSplitters() {
    $$(".splitter").forEach((splitter) => {
      splitter.addEventListener("pointerdown", (event) => {
        if (event.button !== undefined && event.button !== 0) return;
        if (collapsedSide) return;
        const workspace = splitter.closest(".workspace");
        if (!workspace) return;
        event.preventDefault();
        splitDrag = { workspace, pointerId: event.pointerId };
        try { splitter.setPointerCapture(event.pointerId); } catch (_) { /* ignore */ }
        document.body.classList.add("is-splitting");
        splitFromEvent(event, workspace);
      });

      splitter.addEventListener("pointermove", (event) => {
        if (!splitDrag || event.pointerId !== splitDrag.pointerId) return;
        splitFromEvent(event, splitDrag.workspace);
      });

      const finish = (event) => {
        if (!splitDrag || event.pointerId !== splitDrag.pointerId) return;
        document.body.classList.remove("is-splitting");
        try { splitter.releasePointerCapture(event.pointerId); } catch (_) { /* ignore */ }
        splitDrag = null;
        if (splitRatio >= 80) collapseWorkspaceSide("analysis");
        else if (splitRatio <= 20) collapseWorkspaceSide("passage");
      };
      splitter.addEventListener("pointerup", finish);
      splitter.addEventListener("pointercancel", finish);

      splitter.addEventListener("keydown", (event) => {
        if (collapsedSide) return;
        let next = null;
        if (event.key === "ArrowLeft") next = splitRatio - (event.shiftKey ? 5 : 2);
        else if (event.key === "ArrowRight") next = splitRatio + (event.shiftKey ? 5 : 2);
        else if (event.key === "Home") next = 20;
        else if (event.key === "End") next = 80;
        if (next === null) return;
        event.preventDefault();
        setSplitValue(next);
        if (splitRatio >= 80) collapseWorkspaceSide("analysis");
        else if (splitRatio <= 20) collapseWorkspaceSide("passage");
      });
    });
  }

  /* ---------- right-pane tabs + passage anchors ---------- */
  function setTab(name, options = {}) {
    const tab = name || "analysis";
    state.tab = tab;
    const secEl = currentSectionEl();
    if (!secEl) return;
    $$(".tab-btn", secEl).forEach((btn) => {
      const on = btn.dataset.tab === tab;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    $$(".tab-panel", secEl).forEach((panel) => {
      const on = panel.dataset.tabPanel === tab;
      panel.hidden = !on;
      panel.classList.toggle("is-active", on);
    });
    if (options.scroll) {
      const body = secEl.querySelector(".analysis-body");
      if (body) body.scrollTop = 0;
    }
  }

  $$(".analysis-tabs").forEach((bar) => {
    bar.addEventListener("click", (event) => {
      const btn = event.target.closest(".tab-btn");
      if (!btn) return;
      setTab(btn.dataset.tab, { scroll: true });
    });
  });

  let jumpTimer = null;
  function jumpToBlocks(value) {
    const ids = String(value || "").split(",").map((s) => s.trim()).filter(Boolean);
    if (!ids.length) return;
    const secEl = currentSectionEl();
    if (!secEl) return;
    const ws = secEl.querySelector(".workspace");
    if (ws && ws.classList.contains("is-collapsed-passage")) expandWorkspaceSide();
    const pane = secEl.querySelector(".passage-pane");
    if (!pane) return;
    const els = ids
      .map((id) => secEl.querySelector(`.passage-body [data-block="${id}"]`))
      .filter(Boolean);
    if (!els.length) return;
    $$(".passage-body [data-block].is-target", secEl).forEach((el) => el.classList.remove("is-target"));
    els.forEach((el) => el.classList.add("is-target"));
    const head = pane.querySelector(".pane-head");
    const headH = head ? head.getBoundingClientRect().height : 0;
    const pr = pane.getBoundingClientRect();
    const er = els[0].getBoundingClientRect();
    const top = Math.max(0, pane.scrollTop + er.top - pr.top - headH - 14);
    pane.scrollTo({ top, behavior: reduceMotion() ? "auto" : "smooth" });
    if (jumpTimer) clearTimeout(jumpTimer);
    jumpTimer = setTimeout(() => {
      els.forEach((el) => el.classList.remove("is-target"));
    }, 1900);
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-blocks]");
    if (!target || target.closest(".passage-body")) return;
    jumpToBlocks(target.dataset.blocks);
  });

  // Compatibility for older callers; the top tools no longer exist.
  function closeWordlist() {}

  /* ---------- toast ---------- */  /* ---------- toast ---------- */
  /* ---------- toast ---------- */
  let toastTimer = null;
  function toast(message) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("is-show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.classList.remove("is-show");
    }, 2600);
  }

  /* ---------- hover preview card (mouse only) ---------- */
  let hoverEl = null;
  let hoverTimer = null;

  function ensureHoverCard() {
    if (hoverEl) return hoverEl;
    hoverEl = document.createElement("div");
    hoverEl.className = "hovercard";
    hoverEl.hidden = true;
    document.body.appendChild(hoverEl);
    return hoverEl;
  }

  function hideHoverCard() {
    if (hoverTimer) {
      clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    if (!hoverEl) return;
    hoverEl.hidden = true;
    hoverEl.innerHTML = "";
  }

  function showHoverCard(target, html) {
    const el = ensureHoverCard();
    if (hoverTimer) clearTimeout(hoverTimer);
    el.innerHTML = html;
    el.hidden = false;

    const rect = target.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    const gap = 10;
    let left = rect.left + rect.width / 2 - box.width / 2;
    left = Math.max(12, Math.min(window.innerWidth - box.width - 12, left));
    let top = rect.bottom + gap;
    if (top + box.height > window.innerHeight - 12) {
      top = rect.top - box.height - gap;
    }
    top = Math.max(12, Math.min(window.innerHeight - box.height - 12, top));
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
  }

  function vocabPreview(v) {
    return `<div class="h-word">${esc(v.word)}</div>
      <div class="h-meta">${esc(v.ipa || "")} ${v.pos ? " · " + esc(v.pos) : ""}</div>
      <div class="h-meaning">${esc(v.meaning || "")}</div>
      <div class="h-hint">点按查看搭配与例句</div>`;
  }

  function complexPreview(c) {
    return `<div class="h-eyebrow">长难句</div>
      <div class="h-main">${esc(c.main || "")}</div>
      <div class="h-trans">${esc(c.translation || "")}</div>
      <div class="h-hint">点按查看分层结构</div>`;
  }

  /* ---------- drawer ---------- */
  const drawer = $("#drawer");
  const drawerBackdrop = $("#drawerBackdrop");
  const drawerClose = $("#drawerClose");
  const drawerTitle = $("#drawerTitle");
  const drawerEyebrow = $("#drawerEyebrow");
  const drawerBody = $("#drawerBody");
  let lastFocus = null;
  let drawerHideTimer = null;

  function openDrawer({ eyebrow, title, body }) {
    if (!drawer) return;
    lastFocus = document.activeElement;
    if (drawerHideTimer) {
      clearTimeout(drawerHideTimer);
      drawerHideTimer = null;
    }
    drawerEyebrow.textContent = eyebrow || "详情";
    drawerTitle.textContent = title || "—";
    drawerBody.innerHTML = body || "";
    drawerBody.scrollTop = 0;
    drawer.hidden = false;
    drawerBackdrop.hidden = false;
    drawer.setAttribute("aria-hidden", "false");
    document.body.classList.add("drawer-open");
    requestAnimationFrame(() => {
      drawer.classList.add("is-open");
      drawerBackdrop.classList.add("is-open");
      if (drawerClose) drawerClose.focus({ preventScroll: true });
    });
    hideHoverCard();
  }

  function closeDrawer() {
    if (!drawer || !drawer.classList.contains("is-open")) return;
    drawer.classList.remove("is-open");
    drawerBackdrop.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("drawer-open");
    drawerHideTimer = setTimeout(() => {
      drawer.hidden = true;
      drawerBackdrop.hidden = true;
    }, 240);
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus({ preventScroll: true });
    }
  }

  function drawerFocusables() {
    if (!drawer) return [];
    return $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', drawer)
      .filter((el) => !el.disabled && el.offsetParent !== null);
  }

  function trapDrawerFocus(e) {
    if (e.key !== "Tab" || !drawer || !drawer.classList.contains("is-open")) return;
    const list = drawerFocusables();
    if (!list.length) return;
    const first = list[0];
    const last = list[list.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function vocabDrawer(id) {
    const v = vocabMap.get(id);
    if (!v) return;
    const level = v.level === "beyond" ? "超纲 / 拓展" : "高考核心";
    const sec = sectionMap.get(state.section);
    const w = String(v.word || "").toLowerCase();
    const relatedPoints = ((sec && sec.examPoints) || []).filter((p) =>
      (p.words || []).some((x) => x.toLowerCase().includes(w) || w.includes(x.toLowerCase()))
    );
    const examHtml = relatedPoints.length
      ? `<div class="drawer-section-title">高考考点</div>` + relatedPoints.map((p) =>
          `<div class="drawer-exam"><div class="exam-kicker">${esc(p.kind || "高频考点")}</div><div class="exam-title">${esc(p.title || "")}</div><p class="exam-analysis">${esc(p.analysis || "")}</p></div>`
        ).join("")
      : "";
    const body = `
      <div class="vocab-ipa">${esc(v.ipa || "")}${v.pos ? " · " + esc(v.pos) : ""}</div>
      <div class="vocab-meaning">${esc(v.meaning || "")}</div>
      <div class="vocab-grid">
        <div class="vocab-cell"><span class="k">常见搭配</span><span class="v">${esc(v.collocation || "—")}</span></div>
        <div class="vocab-cell"><span class="k">难度标记</span><span class="v">${esc(level)}</span></div>
      </div>
      <div class="drawer-section-title">例句</div>
      <div class="drawer-trans">${esc(v.example || "—")}</div>
      <div class="drawer-section-title">本文语境</div>
      <blockquote class="drawer-quote">${esc(v.context || "")}</blockquote>
      ${examHtml}
    `;
    openDrawer({ eyebrow: "VOCABULARY / 词汇", title: v.word, body });
  }

  function complexDrawer(id) {
    const c = complexMap.get(id);
    if (!c) return;
    const layers = (c.layers || []).map((x) => `<li>${esc(x)}</li>`).join("");
    const body = `
      <blockquote class="drawer-quote">${esc(c.quote || "")}</blockquote>
      <div class="drawer-section-title">主句骨架</div>
      <div class="complex-main">${esc(c.main || "")}</div>
      <div class="drawer-section-title">结构层次</div>
      <ul class="layer-list">${layers}</ul>
      <div class="drawer-section-title">参考翻译</div>
      <div class="drawer-trans">${esc(c.translation || "")}</div>
      ${c.note ? `<div class="drawer-section-title">提示</div><div class="drawer-trans">${esc(c.note)}</div>` : ""}
    `;
    openDrawer({ eyebrow: "SENTENCE / 长难句", title: "结构分析", body });
  }

  /* ---------- legend help tooltip ---------- */
  const legendHelp = document.querySelector(".legend-help");
  if (legendHelp) {
    legendHelp.addEventListener("click", (event) => {
      event.stopPropagation();
      legendHelp.classList.toggle("is-open");
    });
    document.addEventListener("pointerdown", (event) => {
      if (!legendHelp.contains(event.target)) legendHelp.classList.remove("is-open");
    });
  }

  /* ---------- interaction wiring ---------- */

  // Section picker (single dropdown at the top)
  const sectionSelect = document.getElementById("sectionSelect");
  if (sectionSelect) {
    sectionSelect.addEventListener("change", () => {
      showSection(sectionSelect.value);
      closeDrawer();
    });
  }

  // Question chips
  $$(".q-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const entry = questionMap.get(String(chip.dataset.qjump));
      if (!entry) return;
      activate(entry.q.id, "", { scrollCard: true, scrollEvidence: true });
      closeDrawer();
    });
  });

  // Options (reading / cloze)
  $$(".option").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      activate(btn.dataset.q, btn.dataset.opt, { scrollCard: false, scrollEvidence: true });
    });

    btn.addEventListener("pointerenter", (e) => {
      if (e.pointerType !== "mouse") return;
      const card = btn.closest(".q-card");
      if (!card || card.dataset.q !== state.qid) return;
      applyHighlight(btn.dataset.q, btn.dataset.opt);
    });
    btn.addEventListener("pointerleave", () => {
      applyHighlight(state.qid, state.opt);
    });
  });

  // Question cards: clicking anywhere that is not an interactive child pins the answer
  $$(".q-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest("button, .vocab, .cx, .cx-mark, .link-chip, .gap")) return;
      const entry = questionMap.get(String(card.dataset.q));
      if (!entry) return;
      activate(entry.q.id, "", { scrollCard: false, scrollEvidence: true });
    });
  });

  // Bilingual passage toggle
  $$(".lang-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pane = btn.closest(".pane");
      const body = pane ? pane.querySelector(".passage-body") : null;
      if (!body) return;
      const on = !body.classList.contains("is-bilingual");
      body.classList.toggle("is-bilingual", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "中英" : "仅英文";
    });
  });

  // Per-question answer reveal
  $$(".q-reveal").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const qid = btn.dataset.reveal;
      const card = btn.closest(".q-card");
      const entry = questionMap.get(String(qid));
      if (!card || !entry) return;
      const on = !card.classList.contains("is-revealed");
      card.classList.toggle("is-revealed", on);
      btn.setAttribute("aria-expanded", on ? "true" : "false");
      btn.textContent = on ? "隐藏答案" : "显示答案";
      if (on) {
        const selected = card.querySelector(".option.is-active")?.dataset.opt;
        activate(qid, selected || entry.q.answer, {
          scrollCard: false,
          scrollEvidence: false,
          animateEvidence: true,
        });
        scrollEvidenceIntoView(() => playEvidenceWipe(qid));
      } else {
        activate(qid, "", { scrollCard: false, scrollEvidence: false });
      }
    });
  });

  // Gaps
  $$(".gap").forEach((gap) => {
    gap.addEventListener("click", () => {
      const entry = questionMap.get(String(gap.dataset.gap));
      if (!entry) return;
      const hasOption = (entry.q.options || []).some((o) => String(o.key) === String(entry.q.answer));
      const bankHas = entry.section.kind === "seven";
      const opt = hasOption || bankHas ? entry.q.answer : "";
      activate(entry.q.id, opt, { scrollCard: true, scrollEvidence: true });
    });
  });

  // Link chips
  $$(".link-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      activate(chip.dataset.q, chip.dataset.opt, { scrollCard: false, scrollEvidence: true });
    });
  });

  // Vocabulary / complex sentence: mouse hover preview + click drawer
  $$(".vocab").forEach((el) => {
    const id = el.dataset.vocab;
    el.addEventListener("pointerenter", (e) => {
      if (e.pointerType !== "mouse") return;
      const v = vocabMap.get(id);
      if (v) showHoverCard(el, vocabPreview(v));
    });
    el.addEventListener("pointerleave", () => hideHoverCard());
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      hideHoverCard();
      vocabDrawer(id);
    });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        hideHoverCard();
        vocabDrawer(id);
      }
    });
  });

  $$(".vocab-row").forEach((row) => {
    row.addEventListener("click", (event) => {
      event.stopPropagation();
      hideHoverCard();
      closeWordlist(false);
      vocabDrawer(row.dataset.vocab);
    });
  });

  $$(".cx, .cx-mark").forEach((el) => {
    const id = el.dataset.complex;
    el.addEventListener("pointerenter", (e) => {
      if (e.pointerType !== "mouse") return;
      const c = complexMap.get(id);
      if (c) showHoverCard(el, complexPreview(c));
    });
    el.addEventListener("pointerleave", () => hideHoverCard());
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      hideHoverCard();
      complexDrawer(id);
    });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        hideHoverCard();
        complexDrawer(id);
      }
    });
  });

  // Drawer close
  if (drawerClose) drawerClose.addEventListener("click", closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      hideHoverCard();
      closeWordlist(false);
      closeDrawer();
    }
    trapDrawerFocus(e);
  });
  window.addEventListener("scroll", hideHoverCard, { passive: true });
  $$(".pane").forEach((pane) => {
    pane.addEventListener("scroll", hideHoverCard, { passive: true });
  });

  // Font size
  const fontButtons = $$(".seg-btn[data-size]");
  function setFontSize(size) {
    const allowed = ["normal", "large", "xlarge"];
    const value = allowed.includes(size) ? size : "normal";
    document.documentElement.dataset.size = value;
    fontButtons.forEach((b) => {
      b.setAttribute("aria-pressed", b.dataset.size === value ? "true" : "false");
    });
    try {
      localStorage.setItem("exam-font-size", value);
    } catch (_) { /* ignore file:// storage restrictions */ }
  }
  fontButtons.forEach((b) => {
    b.addEventListener("click", () => setFontSize(b.dataset.size));
  });
  try {
    const saved = localStorage.getItem("exam-font-size");
    if (saved) setFontSize(saved);
  } catch (_) { /* ignore */ }

  // Fullscreen
  const fullscreenBtn = $("#fullscreenBtn");
  function updateFullscreenBtn() {
    if (!fullscreenBtn) return;
    const on = Boolean(document.fullscreenElement);
    fullscreenBtn.textContent = on ? "退出全屏" : "全屏";
    fullscreenBtn.classList.toggle("is-on", on);
  }
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener("click", async () => {
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else {
          await document.documentElement.requestFullscreen();
        }
      } catch (err) {
        toast("当前环境不允许全屏，请按 F11。");
      }
    });
  }
  document.addEventListener("fullscreenchange", updateFullscreenBtn);

  // Reset
  const resetBtn = $("#resetBtn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      const section = sectionMap.get(state.section);
      const first = section && section.questions && section.questions[0];
      if (first) {
        activate(first.id, "", { scrollCard: true, scrollEvidence: false });
        toast("已回到本节第一题。");
      }
      closeDrawer();
    });
  }

  // Collapsed rails + splitter
  $$(".collapsed-rail").forEach((rail) => {
    rail.addEventListener("click", () => expandWorkspaceSide());
  });
  initSplitters();
  applyWorkspaceState();

  // Initial section
  const hash = (location.hash || "").replace(/^#\/?/, "");
  const initial = sectionMap.has(hash) ? hash : sections[0].id;
  showSection(initial);
  closeWordlist(false);
  // If an old-style "#reading-a" link is opened, the browser may have scrolled
  // the section into view before the app boots.  Put the chrome back in view.
  window.scrollTo(0, 0);

  window.addEventListener("hashchange", () => {
    const id = (location.hash || "").replace(/^#\/?/, "");
    if (sectionMap.has(id) && id !== state.section) showSection(id);
  });

  window.addEventListener("resize", hideHoverCard);
})();
