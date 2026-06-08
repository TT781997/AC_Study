"""
app.py — Entry point Universal ScholarGPT v5.2
================================================

Wiring final:
  ⭐ @st.cache_resource para conn da BD (uma conexão por sessão)
  ⭐ init_db() no arranque (idempotente, silencioso — spec §3)
  ⭐ processed_files: dict[file_hash, document_id] (spec §2)
  ⭐ pipeline_results: dict[document_id, full_result] (cache local)
  ⭐ Para cada upload novo: process_document_pipeline (cache hit OU pipeline)
  ⭐ Vision callback construído via make_vision_callback(client)

Como correr:
    pip install streamlit openai PyMuPDF python-docx python-pptx openpyxl \\
                pandas beautifulsoup4 pdf2image pytesseract Pillow
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Universal ScholarGPT",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

import db
from config import (
    CUSTOM_CSS, AGENTS_ORDER, DEFAULT_MODELS, DEFAULT_SUMMARY_MODEL,
    DEFAULT_DB_PATH, VISION_MODEL_DEFAULT,
)
from llm_client import (
    stream_call_threaded, get_nvidia_client, make_vision_callback,
)
from document_processor import process_document_pipeline
from ui_components import (
    render_top_banner, render_sidebar, render_welcome,
    render_document_tab, render_right_panel_settings,
)
from i18n import t

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# DB Connection (cached resource — uma só conexão por sessão)
# ════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def get_db_connection():
    """
    @st.cache_resource garante UMA conexão SQLite por sessão.
    init_db() é idempotente: corre no arranque, cria tabelas se faltam.

    Aviso da spec: SQLite efémero em cloud — sempre inicializar.
    """
    return db.init_db(DEFAULT_DB_PATH)


# ════════════════════════════════════════════════════════════════════════════
# Session state
# ════════════════════════════════════════════════════════════════════════════

def _init_session_state():
    ss = st.session_state
    ss.setdefault("ui_language", "pt")
    ss.setdefault("output_language", "pt")
    ss.setdefault("api_key", "")
    ss.setdefault("client", None)

    ss.setdefault("summary_model", DEFAULT_SUMMARY_MODEL)
    ss.setdefault("vision_model", VISION_MODEL_DEFAULT)
    ss.setdefault("max_rounds", 4)
    ss.setdefault("coverage_check", True)

    # ⭐ v5.2 — spec §2: processed_files = dict {file_hash: document_id}
    ss.setdefault("processed_files", {})
    # Cache local em memória: document_id → full pipeline result
    ss.setdefault("pipeline_results", {})
    ss.setdefault("_pending_upload", None)

    # Migração v3/v4 → v5
    current_models = ss.get("agent_models", {})
    if (not current_models
        or any(k in current_models for k in ("Validador A", "Validador B"))
        or set(current_models.keys()) != set(AGENTS_ORDER)):
        ss["agent_models"] = DEFAULT_MODELS.copy()

    if ss["api_key"] and ss["client"] is None:
        ss["client"] = get_nvidia_client(ss["api_key"])


_init_session_state()

# Conn da BD (cached) — disponível em todo o lado via session_state
conn = get_db_connection()
st.session_state["db_conn"] = conn


# ════════════════════════════════════════════════════════════════════════════
# Bootstrap from DB — recupera documents persistidos em sessões anteriores
# ════════════════════════════════════════════════════════════════════════════

def _bootstrap_from_db():
    """
    No arranque, lista Documents da BD e popula processed_files
    (sem carregar resultados completos — lazy load on demand).
    """
    processed = st.session_state["processed_files"]
    try:
        for doc_row in db.list_all_documents(conn):
            file_hash = doc_row["file_hash"]
            if file_hash not in processed:
                processed[file_hash] = int(doc_row["id"])
    except Exception:
        pass   # BD vazia ou recém-criada — OK


_bootstrap_from_db()


# ════════════════════════════════════════════════════════════════════════════
# TOP LAYOUT
# ════════════════════════════════════════════════════════════════════════════

top_cols = st.columns([9, 1])
with top_cols[0]:
    render_top_banner()
with top_cols[1]:
    render_right_panel_settings()

render_sidebar()


# ════════════════════════════════════════════════════════════════════════════
# Pipeline automático para uploads novos
# ════════════════════════════════════════════════════════════════════════════

def _process_uploaded_files(uploaded_files):
    """Para cada ficheiro novo, corre process_document_pipeline (com DB lookup)."""
    if not uploaded_files:
        return

    client = st.session_state.get("client")
    if client is None:
        st.warning(t("warn_set_key"))
        return

    vision_cb = make_vision_callback(client)
    processed = st.session_state["processed_files"]
    results = st.session_state["pipeline_results"]
    lang = st.session_state.get("output_language",
                                st.session_state.get("ui_language", "pt"))

    container = st.container()

    for f in uploaded_files:
        # Calcula hash sem reabrir o ficheiro
        file_bytes = f.getvalue()
        file_hash = db.compute_file_hash(file_bytes)

        # Já processado nesta sessão? skip silencioso
        if file_hash in processed and processed[file_hash] in results:
            continue

        try:
            result = process_document_pipeline(
                f, conn=conn, client=client,
                stream_fn=stream_call_threaded,
                vision_callback=vision_cb,
                ui_container=container,
                lang_code=lang,
                max_rounds=st.session_state.get("max_rounds", 4),
                coverage_check=st.session_state.get("coverage_check", True),
            )
            processed[file_hash] = result["document_id"]
            results[result["document_id"]] = result

        except Exception as e:
            container.error(f"❌ Erro a processar `{f.name}`: {e}")


pending = st.session_state.pop("_pending_upload", None)
if pending:
    _process_uploaded_files(pending)


# ════════════════════════════════════════════════════════════════════════════
# Carregamento lazy de results para tabs (cache hits da BD)
# ════════════════════════════════════════════════════════════════════════════

def _ensure_result_loaded(document_id: int):
    """Lazy-load: se o result não está em memória, carrega da BD."""
    if document_id in st.session_state["pipeline_results"]:
        return
    doc_row = db.get_document_by_id(conn, document_id)
    if doc_row is None:
        return
    analysis = db.get_latest_analysis(conn, document_id)
    if analysis is None:
        return

    from document_processor import _build_result_from_cache
    st.session_state["pipeline_results"][document_id] = \
        _build_result_from_cache(doc_row, analysis)


# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════

processed_files = st.session_state["processed_files"]

if not processed_files:
    render_welcome()
else:
    # Tab por documento (ordenado por nome para estabilidade)
    doc_entries = sorted(processed_files.items(),
                         key=lambda kv: kv[1])   # por document_id
    doc_ids = [doc_id for _, doc_id in doc_entries]

    # Lazy load para gerar labels
    tab_labels = []
    for doc_id in doc_ids:
        _ensure_result_loaded(doc_id)
        result = st.session_state["pipeline_results"].get(doc_id)
        if result:
            name = result["file_name"]
            ftype = result.get("file_type", "")
            badge = " 📦" if result.get("cached") else ""
            label = f"📄 {name[:25]}{badge}"
        else:
            label = f"📄 doc#{doc_id}"
        tab_labels.append(label)

    tabs = st.tabs(tab_labels)

    for i, doc_id in enumerate(doc_ids):
        with tabs[i]:
            result = st.session_state["pipeline_results"].get(doc_id)
            if result is None:
                st.warning("⚠️ Sem dados em memória nem na BD para este documento.")
                continue

            def _make_regenerator(d_id):
                """Cria callback para refazer análise (força bypass do cache)."""
                def _regen():
                    res = st.session_state["pipeline_results"].get(d_id, {})
                    raw = res.get("raw_text", "")
                    if not raw:
                        st.warning(t("regen_fail"))
                        return
                    # Simula re-upload: reusar bytes do raw_text não é possível
                    # (não temos os bytes originais). Em vez disso, refaz só
                    # o resumo + debate a partir do raw_text persistido.
                    client = st.session_state.get("client")
                    if client is None:
                        st.warning(t("warn_set_key"))
                        return
                    _regenerate_in_place(d_id, res, client)
                return _regen

            try:
                render_document_tab(result, on_regenerate=_make_regenerator(doc_id))
            except Exception as e:
                st.warning(f"⚠️ Erro a renderizar tab: {e}")


def _regenerate_in_place(document_id, current_result, client):
    """
    Refaz a análise reusando o raw_text já em DB (sem voltar a fazer ingestão).
    Util para mudar idioma, modelo ou rondas sem novo upload.
    """
    from document_processor import summarize_pdf_robust
    from agents import run_consensus_loop

    raw = current_result.get("raw_text", "")
    file_name = current_result["file_name"]
    lang = st.session_state.get("output_language",
                                st.session_state.get("ui_language", "pt"))

    container = st.container()
    with container.status(t("regen_progress", name=file_name), expanded=True) as status:
        try:
            topic_index, summary, coverage_status = summarize_pdf_robust(
                client, file_name, raw, status, lang,
                st.session_state.get("coverage_check", True),
                stream_fn=stream_call_threaded,
            )
            full_material = (
                f"### 📄 {file_name}\n\n"
                f"**ÍNDICE:**\n{topic_index}\n\n"
                f"**RESUMO:**\n{summary}\n\n"
                f"**EXCERTO:**\n{raw[:30_000]}"
            )
            debate = run_consensus_loop(
                client=client, full_material=full_material,
                max_rounds=st.session_state.get("max_rounds", 4),
                ui_container=status, lang_code=lang,
                stream_fn=stream_call_threaded,
            )

            # Update result + persist nova Analysis na BD
            current_result.update({
                "topic_index": topic_index,
                "summary": summary,
                "coverage_status": coverage_status,
                "quiz_text": debate.final_content,
                "final_author": debate.final_author,
                "final_version": debate.final_version,
                "consensus_reached": debate.consensus_reached,
                "rounds_used": debate.rounds_used,
                "debate_log": [
                    {"round_num": e.round_num, "author": e.author,
                     "validator": e.validator, "decision": e.decision,
                     "version": e.version, "brief_reason": e.brief_reason,
                     "kind": e.kind}
                    for e in debate.debate_log
                ],
                "cached": False,
            })

            try:
                db.insert_analysis(
                    conn, document_id=document_id,
                    summary_json={"topic_index": topic_index, "summary": summary,
                                  "coverage_status": coverage_status,
                                  "metadata": current_result.get("metadata", {})},
                    quiz_json={"text": debate.final_content,
                               "final_author": debate.final_author,
                               "final_version": debate.final_version,
                               "consensus_reached": debate.consensus_reached,
                               "rounds_used": debate.rounds_used},
                    debate_log_json=current_result["debate_log"],
                )
            except Exception as e:
                status.write(f"⚠️ Persistência: {e}")

            status.update(label=t("regen_done"), state="complete", expanded=False)
            st.rerun()

        except Exception as e:
            status.update(label=f"{t('regen_fail')} — {e}",
                          state="error", expanded=False)
