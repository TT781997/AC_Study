"""
ui_components.py — Camada visual (Universal ScholarGPT v5.2)
=============================================================

Mudanças face à v5.1:
  ⭐ render_document_tab (genérico, substitui render_pdf_tab)
  ⭐ Cache badge "📦 Cached" + format pill (".pdf", ".docx", etc.)
  ⭐ View metadata expander (file_hash, ingestion warnings, OCR fallback)
  ⭐ Right Panel ⚙️ inclui Vision Model selector

Mantém da v5.1:
  • LoadingAnimator (timer + ETA + barra + mensagens divertidas)
  • render_sidebar com "How to use" 3-passos + API Key + Upload + BD
  • render_right_panel_settings via st.popover
  • render_debate_log_visual (cards estruturados em tempo real)
  • render_quiz_with_answers_toggle com st.expander
"""

from __future__ import annotations

import json
import random
import time
from typing import List, Optional

import streamlit as st

from config import (
    ISEL_LOGO_URL, AGENTS_ORDER, AGENT_ICONS,
    DEFAULT_MODELS, DEFAULT_SUMMARY_MODEL, MODEL_REGISTRY,
    CUSTOM_MODEL_SENTINEL, ANSWERS_SEPARATOR, NVIDIA_API_KEY_URL,
    VISION_MODEL_DEFAULT, VISION_MODEL_FALLBACKS,
)
from i18n import (
    LANGUAGES, LOADING_EMOJIS,
    t, agent_display, agent_role_description, random_fun_message,
)
from agents import split_quiz_and_answers, DebateLogEntry
from ingestion import SUPPORTED_FORMATS
import db


# ════════════════════════════════════════════════════════════════════════════
# LOADING ANIMATOR
# ════════════════════════════════════════════════════════════════════════════

class LoadingAnimator:
    """Timer + ETA + barra + mensagens divertidas. Render throttled a 2 fps."""

    def __init__(self, container, lang_code="pt", eta_seconds=None, model_label=""):
        self.container = container
        self.lang_code = lang_code
        self.eta_initial = eta_seconds
        self.model_label = model_label
        self.start = time.time()
        self.last_render = 0.0
        self.fun_msg = random_fun_message(lang_code)
        self.emoji = random.choice(LOADING_EMOJIS)
        try: self.placeholder = container.empty()
        except Exception: self.placeholder = None

    def update(self, current_text="", force=False):
        now = time.time()
        if not force and (now - self.last_render) < 0.5: return
        self.last_render = now
        elapsed = now - self.start

        eta_html = ""
        if self.eta_initial and self.eta_initial > 0:
            if elapsed < self.eta_initial:
                eta_html = f"<span class='eta'>· ⏳ ~{int(self.eta_initial - elapsed)}s {t('remaining')}</span>"
            else:
                eta_html = f"<span class='eta'>· +{int(elapsed - self.eta_initial)}s {t('over_estimate')}</span>"

        progress_html = ""
        if self.eta_initial and self.eta_initial > 0:
            pct = min(100, (elapsed / self.eta_initial) * 100)
            progress_html = f'<div class="progress-bar"><div class="progress-fill" style="width:{pct:.1f}%"></div></div>'

        meta_line = f"⏱ {int(elapsed)}s {t('elapsed')} {eta_html}"
        if self.model_label: meta_line += f" · {self.model_label}"

        html = (
            f'<div class="loading-fun">'
            f'<div class="big-emoji">{self.emoji}</div>'
            f'<div class="body">'
            f'<div class="msg">{self.fun_msg}</div>'
            f'<div class="meta">{meta_line}</div>'
            f'{progress_html}'
            f'</div></div>'
        )
        if self.placeholder is not None:
            try: self.placeholder.markdown(html, unsafe_allow_html=True)
            except Exception: pass

    def clear(self):
        if self.placeholder is not None:
            try: self.placeholder.empty()
            except Exception: pass


# ════════════════════════════════════════════════════════════════════════════
# TOP BANNER
# ════════════════════════════════════════════════════════════════════════════

def render_top_banner():
    badges = "".join(
        f'<span class="badge">{t(k)}</span>' for k in [
            "badge_universal", "badge_multilang", "badge_coverage",
            "badge_4agents", "badge_persistence", "badge_multimodal",
        ]
    )
    st.markdown(
        f'<div class="scholar-banner">'
        f'<h1>🎓 {t("app_title")}</h1>'
        f'<div class="subtitle">{t("subtitle")}</div>'
        f'<div>{badges}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL ⚙️
# ════════════════════════════════════════════════════════════════════════════

def render_right_panel_settings():
    """⚙️ no top-right via st.popover. API Key NUNCA aqui (spec §4)."""
    popover = st.popover(t("right_panel_open"), help=t("right_panel_help"),
                         use_container_width=True)
    with popover:
        st.markdown(f"### {t('right_panel_title')}")

        # Idioma de saída
        lang_codes = list(LANGUAGES.keys())
        current_out = st.session_state.get("output_language",
                                           st.session_state.get("ui_language", "pt"))
        try: out_idx = lang_codes.index(current_out)
        except ValueError: out_idx = 0
        st.session_state["output_language"] = st.selectbox(
            t("output_language"), options=lang_codes, index=out_idx,
            format_func=lambda c: LANGUAGES[c]["label"],
            help=t("output_language_help"), key="output_lang_sel",
        )
        st.markdown("---")

        # max_rounds + coverage
        st.session_state["max_rounds"] = st.slider(
            t("max_rounds"), min_value=1, max_value=8,
            value=st.session_state.get("max_rounds", 4), key="rp_rounds",
        )
        st.session_state["coverage_check"] = st.checkbox(
            t("coverage_check_label"),
            value=st.session_state.get("coverage_check", True),
            help=t("coverage_check_help"), key="rp_coverage",
        )
        st.markdown("---")

        # ⭐ v5.2: Vision Model
        st.markdown(f"**{t('vision_model_label')}**")
        vision_options = [VISION_MODEL_DEFAULT] + VISION_MODEL_FALLBACKS + [CUSTOM_MODEL_SENTINEL]
        current_vision = st.session_state.get("vision_model", VISION_MODEL_DEFAULT)
        try: v_idx = vision_options.index(current_vision)
        except ValueError: v_idx = len(vision_options) - 1
        sel_v = st.selectbox(
            " ", options=vision_options, index=v_idx,
            key="rp_vision", label_visibility="collapsed",
        )
        if sel_v == CUSTOM_MODEL_SENTINEL:
            custom_v = st.text_input(
                t("custom_model_input"),
                value=current_vision if current_vision not in vision_options else "",
                key="rp_vision_custom",
            )
            if custom_v.strip():
                st.session_state["vision_model"] = custom_v.strip()
        else:
            st.session_state["vision_model"] = sel_v
        st.caption(t("vision_model_help"))
        st.markdown("---")

        # Modelo do Professor
        st.markdown(f"**{t('summary_model_label')}**")
        _model_selector(state_key="summary_model", default=DEFAULT_SUMMARY_MODEL,
                        widget_id="rp_summary")
        st.markdown("---")

        # 4 agentes
        st.markdown(f"**{t('debate_models_label')}**")
        for agent_name in AGENTS_ORDER:
            icon = AGENT_ICONS[agent_name]
            disp = agent_display(agent_name)
            desc = agent_role_description(agent_name)
            st.markdown(
                f"<div class='agent-card' style='margin-top:0.45rem'>"
                f"<div class='role'>{icon} {disp}</div>"
                f"<div class='role-desc'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            _agent_model_selector(agent_name, widget_prefix="rp")

        if st.button(t("reset_models"), key="rp_reset", use_container_width=True):
            st.session_state["agent_models"] = DEFAULT_MODELS.copy()
            st.session_state["summary_model"] = DEFAULT_SUMMARY_MODEL
            st.session_state["vision_model"] = VISION_MODEL_DEFAULT
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR ESQUERDA — onboarding "How to use"
# ════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    from llm_client import get_nvidia_client

    with st.sidebar:
        st.markdown(
            f'<div class="isel-logo-wrap">'
            f'<img src="{ISEL_LOGO_URL}" alt="ISEL" '
            f'onerror="this.style.display=\'none\'; '
            f'this.nextElementSibling.style.display=\'block\'">'
            f'<div class="isel-logo-fallback" style="display:none">ISEL</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Idioma da UI
        lang_codes = list(LANGUAGES.keys())
        current_lang = st.session_state.get("ui_language", "pt")
        try: lang_idx = lang_codes.index(current_lang)
        except ValueError: lang_idx = 0
        new_lang = st.selectbox(
            t("language"), options=lang_codes, index=lang_idx,
            format_func=lambda c: LANGUAGES[c]["label"],
            help=t("language_help"), key="ui_lang_sel",
        )
        if new_lang != current_lang:
            st.session_state["ui_language"] = new_lang
            st.rerun()

        # Onboarding
        st.markdown(
            f'<div class="how-to-use">'
            f'<div class="h2u-title">{t("how_to_use_title")}</div>'
            f'<ol>'
            f'<li>{t("how_to_use_step1", url=NVIDIA_API_KEY_URL)}</li>'
            f'<li>{t("how_to_use_step2")}</li>'
            f'<li>{t("how_to_use_step3")}</li>'
            f'</ol>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # API Key
        new_key = st.text_input(
            t("api_key"),
            value=st.session_state.get("api_key", ""),
            type="password", help=t("api_key_help"),
            key="sidebar_api_key",
        )
        if new_key != st.session_state.get("api_key", ""):
            st.session_state["api_key"] = new_key
            st.session_state["client"] = get_nvidia_client(new_key) if new_key else None
            st.rerun()

        if st.session_state.get("client") is not None:
            st.success(t("key_loaded"))
        elif new_key:
            st.warning(t("no_key"))

        # Uploader multi-formato
        uploaded = st.file_uploader(
            t("upload_files"),
            type=SUPPORTED_FORMATS,
            accept_multiple_files=True,
            help=t("upload_help_v52"),
            key="file_uploader",
        )
        if uploaded:
            st.session_state["_pending_upload"] = uploaded

        # Stats da BD
        conn = st.session_state.get("db_conn")
        if conn is not None:
            try:
                stats = db.db_stats(conn)
                st.caption(t("db_stats", docs=stats["documents"],
                             analyses=stats["analyses"]))
            except Exception:
                st.caption(t("db_empty"))
        else:
            st.caption(t("db_empty"))

        # BD section
        st.markdown("---")
        st.markdown(f"### {t('db_section')}")
        confirm_delete = st.checkbox(
            t("db_confirm"), help=t("db_confirm_help"), key="confirm_delete_db",
        )
        if st.button(
            t("db_delete_btn"), disabled=not confirm_delete,
            key="delete_db_btn", use_container_width=True,
        ):
            if conn is not None:
                try:
                    n_deleted = db.delete_all_documents(conn)
                    st.session_state["processed_files"] = {}
                    st.session_state["pipeline_results"] = {}
                    st.success(t("db_deleted", n=n_deleted))
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")


def _model_selector(state_key, default, widget_id):
    current = st.session_state.get(state_key, default)
    options = list(MODEL_REGISTRY.keys()) + [CUSTOM_MODEL_SENTINEL]
    if current in MODEL_REGISTRY: idx = options.index(current)
    else: idx = options.index(CUSTOM_MODEL_SENTINEL)
    selected = st.selectbox(
        " ", options=options, index=idx,
        format_func=lambda m: MODEL_REGISTRY.get(m, {}).get("label", m),
        key=f"sel_{widget_id}", label_visibility="collapsed",
    )
    if selected == CUSTOM_MODEL_SENTINEL:
        custom = st.text_input(t("custom_model_input"),
                               value=current if current not in MODEL_REGISTRY else "",
                               key=f"custom_{widget_id}")
        if custom.strip(): st.session_state[state_key] = custom.strip()
    else:
        st.session_state[state_key] = selected
        meta = MODEL_REGISTRY[selected]
        cls = "model-warn" if meta.get("warn") else "model-help"
        st.markdown(f'<div class="{cls}">{meta.get("best_for", "")}</div>',
                    unsafe_allow_html=True)
    st.caption(t("model_404_hint"))


def _agent_model_selector(agent_name, widget_prefix=""):
    models = st.session_state.setdefault("agent_models", DEFAULT_MODELS.copy())
    current = models.get(agent_name, DEFAULT_MODELS[agent_name])
    options = list(MODEL_REGISTRY.keys()) + [CUSTOM_MODEL_SENTINEL]
    if current in MODEL_REGISTRY: idx = options.index(current)
    else: idx = options.index(CUSTOM_MODEL_SENTINEL)
    safe = agent_name.replace(" ", "_")
    selected = st.selectbox(
        " ", options=options, index=idx,
        format_func=lambda m: MODEL_REGISTRY.get(m, {}).get("label", m),
        key=f"{widget_prefix}_sel_agent_{safe}", label_visibility="collapsed",
    )
    if selected == CUSTOM_MODEL_SENTINEL:
        custom = st.text_input(t("custom_model_input"),
                               value=current if current not in MODEL_REGISTRY else "",
                               key=f"{widget_prefix}_custom_agent_{safe}")
        if custom.strip(): models[agent_name] = custom.strip()
    else:
        models[agent_name] = selected
        meta = MODEL_REGISTRY[selected]
        cls = "model-warn" if meta.get("warn") else "model-help"
        st.markdown(f'<div class="{cls}">{meta.get("best_for", "")}</div>',
                    unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# WELCOME
# ════════════════════════════════════════════════════════════════════════════

def render_welcome():
    st.markdown(f"### {t('welcome_title')}")
    st.markdown(t("welcome_body"))
    for key in ["welcome_b1", "welcome_b2", "welcome_b3", "welcome_b4", "welcome_b5"]:
        st.markdown(f"- {t(key)}")


# ════════════════════════════════════════════════════════════════════════════
# ⭐ v5.2 — DOCUMENT TAB (genérico, multi-formato)
# ════════════════════════════════════════════════════════════════════════════

COVERAGE_STATUS_TO_KEY = {
    "ok":          ("coverage_status_ok", "ok"),
    "gaps_filled": ("coverage_status_gaps_filled", "gaps_filled"),
    "skipped":     ("coverage_status_skipped", "skipped"),
    "pending":     ("coverage_status_pending", "pending"),
}


def render_document_tab(result: dict, *, on_regenerate=None):
    """
    Tab por documento. Mostra:
      • Header com format pill + cached badge + meta
      • Botão Refazer
      • Topic Index (expander)
      • Resumo
      • Raw text (expander)
      • OCR text (expander, se houver)
      • Metadata expander
    """
    file_name = result.get("file_name", "?")
    file_type = result.get("file_type", "")
    cached = result.get("cached", False)
    raw = result.get("raw_text", "") or ""
    ocr = result.get("ocr_text", "") or ""
    summary = result.get("summary", "") or ""
    topic_index = result.get("topic_index", "") or ""
    coverage_status = result.get("coverage_status", "pending")
    metadata = result.get("metadata", {}) or {}

    pages = metadata.get("page_count")
    pages_disp = pages if pages is not None else t("n_a")
    page_label = t("page_label_singular") if pages == 1 else t("page_label_plural")

    cov_key, cov_css = COVERAGE_STATUS_TO_KEY.get(coverage_status,
                                                  ("coverage_status_pending", "pending"))
    cov_html = f'<span class="coverage-badge {cov_css}">{t(cov_key)}</span>'

    if cached:
        badge_html = f'<span class="cached-badge">{t("summary_cached")}</span>'
    elif summary:
        badge_html = t("summary_auto")
    else:
        badge_html = t("summary_pending")

    format_pill = f'<span class="format-pill">.{file_type}</span>' if file_type else ""

    st.markdown(
        f'<div class="pdf-meta">'
        + format_pill
        + t("pages_chars", pages=pages_disp, page_label=page_label,
            chars=len(raw) + len(ocr), badge=badge_html, cov=cov_html)
        + '</div>',
        unsafe_allow_html=True,
    )

    # Botão refazer
    cols = st.columns([1, 4])
    with cols[0]:
        if st.button(
            t("regen_summary"),
            key=f"regen_{result.get('document_id', file_name)}",
            disabled=(st.session_state.get("client") is None or on_regenerate is None),
            use_container_width=True,
        ):
            if on_regenerate is not None:
                on_regenerate()

    # Resumo
    if summary:
        st.markdown(summary)
    else:
        st.warning(t("no_summary_yet"))

    # Quiz (se houver)
    quiz_text = result.get("quiz_text", "")
    if quiz_text:
        st.markdown("---")
        render_quiz_with_answers_toggle(
            quiz_text, quiz_id=str(result.get("document_id", file_name)),
        )

    # Log Visual (se houver)
    debate_log = result.get("debate_log", [])
    if debate_log:
        st.markdown("---")
        # Reconstrói DebateLogEntry a partir do JSON serializado
        entries = [
            DebateLogEntry(
                round_num=e.get("round_num", 0),
                author=e.get("author", "?"),
                validator=e.get("validator"),
                decision=e.get("decision"),
                version=e.get("version", 1),
                brief_reason=e.get("brief_reason", ""),
                content="",
                kind=e.get("kind", "draft"),
            )
            for e in debate_log
        ]
        render_debate_log_visual(entries, expanded=False)

    # Expanders auxiliares
    if topic_index:
        with st.expander(t("view_topic_index")):
            st.markdown(topic_index)

    if raw.strip():
        with st.expander(t("view_raw")):
            st.text_area("raw", value=raw[:50_000], height=250,
                         label_visibility="collapsed", disabled=True,
                         key=f"raw_{result.get('document_id', file_name)}")

    if ocr.strip():
        with st.expander(t("view_ocr")):
            st.text_area("ocr", value=ocr[:50_000], height=250,
                         label_visibility="collapsed", disabled=True,
                         key=f"ocr_{result.get('document_id', file_name)}")

    if metadata:
        with st.expander(t("view_metadata")):
            st.json(metadata)


# Backward-compat alias
render_pdf_tab = render_document_tab


# ════════════════════════════════════════════════════════════════════════════
# LOG VISUAL DO DEBATE
# ════════════════════════════════════════════════════════════════════════════

def render_debate_log_visual(debate_log: List[DebateLogEntry], expanded: bool = True):
    if not debate_log:
        st.info(t("debate_log_empty"))
        return
    with st.expander(t("debate_log_title"), expanded=expanded):
        for entry in debate_log:
            _render_debate_log_entry(entry)


def _render_debate_log_entry(entry: DebateLogEntry):
    author_icon = AGENT_ICONS.get(entry.author, "")
    author_disp = agent_display(entry.author)

    if entry.kind == "draft":
        css = "debate-log-entry draft"
        badge = f'<span class="decision-badge draft">{t("debate_log_draft")}</span>'
        head = t("debate_log_authored", author_icon=author_icon, author=author_disp)
    elif entry.decision == "APPROVE":
        css = "debate-log-entry approve"
        badge = f'<span class="decision-badge approve">{t("debate_log_approve_badge")}</span>'
        v_icon = AGENT_ICONS.get(entry.validator or "", "")
        v_disp = agent_display(entry.validator) if entry.validator else ""
        head = t("debate_log_by", validator_icon=v_icon, validator=v_disp,
                 author_icon=author_icon, author=author_disp)
    else:
        css = "debate-log-entry rewrite"
        badge = f'<span class="decision-badge rewrite">{t("debate_log_rewrite_badge", v=entry.version)}</span>'
        v_icon = AGENT_ICONS.get(entry.validator or "", "")
        v_disp = agent_display(entry.validator) if entry.validator else ""
        head = t("debate_log_by", validator_icon=v_icon, validator=v_disp,
                 author_icon=author_icon, author=author_disp)

    round_label = t("debate_log_round", n=entry.round_num)
    version_label = t("debate_log_version", v=entry.version)
    reason = entry.brief_reason or t("debate_log_no_reason")
    st.markdown(
        f'<div class="{css}">'
        f'<div class="head"><b>{round_label}</b> · <b>{version_label}</b> · {head} {badge}</div>'
        f'<div class="reason">"{reason}"</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# QUIZ COM st.expander (spec §2)
# ════════════════════════════════════════════════════════════════════════════

def render_quiz_with_answers_toggle(final_content: str, quiz_id: str):
    questions, answers = split_quiz_and_answers(final_content)

    st.markdown(f"### {t('quiz_questions_title')}")
    if questions: st.markdown(questions)
    else: st.info("(quiz vazio)")

    if answers is None:
        st.warning(t("no_separator_warning"))
        _render_download_buttons(questions, None, quiz_id)
        return

    st.markdown(f'<div class="quiz-try-first">{t("quiz_try_first")}</div>',
                unsafe_allow_html=True)

    with st.expander(t("show_answers_btn"), expanded=False):
        st.markdown(f'<div class="answers-revealed">{t("answers_revealed_info")}</div>',
                    unsafe_allow_html=True)
        st.markdown(f"### {t('answers_section_title')}")
        st.markdown(answers)

    st.markdown("---")
    _render_download_buttons(questions, answers, quiz_id)


def _render_download_buttons(questions, answers, quiz_id):
    if answers is None:
        st.download_button(t("download_questions"), data=questions or "",
                           file_name=f"quiz_{quiz_id}.md", mime="text/markdown",
                           key=f"dl_q_{quiz_id}")
        return
    full = f"{questions}\n\n{ANSWERS_SEPARATOR}\n\n{answers}"
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(t("download_questions"), data=questions or "",
                           file_name=f"quiz_{quiz_id}_questions.md", mime="text/markdown",
                           key=f"dl_q_{quiz_id}")
    with c2:
        st.download_button(t("download_full"), data=full,
                           file_name=f"quiz_{quiz_id}_full.md", mime="text/markdown",
                           key=f"dl_full_{quiz_id}")
