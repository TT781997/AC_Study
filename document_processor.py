"""
document_processor.py — Pipeline completo (Universal ScholarGPT v5.2)
======================================================================

Refactor major face à v5.1:
  ⭐ NOVA process_document_pipeline() — orquestra ingest → DB lookup →
     resumo → debate → persist numa única chamada.
  ⭐ Aceita QUALQUER formato suportado (delega a ingestion.ingest_file).
  ⭐ DB lookup por file_hash: cache hit serve instantaneamente de SQLite.
  ⭐ Persiste {summary_json, quiz_json, debate_log_json} em Analyses.
  ⭐ vision_callback injectada para PDFs digitalizados e imagens.

Mantém da v5.1:
  • Pipeline 4 fases: Índice Tópicos → Resumo → Auditoria → Gap-fill cirúrgico
  • COVERAGE_GAPS_MARKER + injecção antes da secção '📋 Cobertura'
  • Map-Reduce orientado pelo índice
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st

import db
import ingestion
from agents import run_consensus_loop
from config import (
    MAX_CHARS_PER_SUMMARY_CHUNK, MAX_CHARS_FOR_COVERAGE,
    HARD_TRUNCATE_MARGIN, COVERAGE_OK_MARKER,
    DEFAULT_SUMMARY_MODEL, ANSWERS_SEPARATOR,
)
from i18n import t, language_instruction, section_labels_block

COVERAGE_GAPS_MARKER = "COVERAGE_GAPS"


# ════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ════════════════════════════════════════════════════════════════════════════

PROMPT_TOPIC_INDEX = """És um **Indexador Académico**. Lista de forma ENXUTA todos os tópicos
cobertos pelo documento fornecido.

INSTRUÇÕES:
1. Lê o documento por completo.
2. Devolve lista Markdown com 5-15 tópicos principais.
3. Cada tópico: `- **Nome do Tópico**: descrição curta (1 frase).`
4. Cobre TODO o documento. Usa terminologia EXATA do documento.

FORMATO — APENAS a lista. Sem preâmbulos.
"""

PROMPT_RESUMO_TEMPLATE = """És **O Professor** — académico universitário sénior. Produzes RESUMO
ESTRUTURADO E COMPLETO da matéria fornecida, no idioma do LANGUAGE OVERRIDE.

🎯 OBJETIVO CRÍTICO — COBERTURA INTEGRAL: cobre TODOS os tópicos do
ÍNDICE DE TÓPICOS fornecido. Esta é a prioridade máxima.

ESTRUTURA:
{section_labels}

DIRECTRIZES:
- Aplicável a QUALQUER disciplina.
- Markdown limpo. LaTeX: `$x$` inline, `$$x$$` display.
- A última secção `## 📋 Cobertura` lista TODOS os tópicos cobertos.

LATEX:
✅ `$x = y$` ✅ `$$\\Sigma$$` ✅ `$\\frac{{a}}{{b}}$` ✅ `$P = 100$ W`
❌ `\\(`, `\\[` ❌ `**$x$**`
"""

PROMPT_COVERAGE_AUDIT = """És o **Auditor de Cobertura**. Comparas um ÍNDICE DE TÓPICOS contra um
RESUMO e identificas tópicos do índice que NÃO aparecem no resumo.

FORMATO — uma das duas opções:

→ Cobertura completa:
   `{ok_marker}`
   (NADA MAIS.)

→ Há tópicos em FALTA:
   `{gaps_marker}`
   Linhas seguintes: bullets `-` com NOMES EXATOS dos tópicos em falta.

POLÍTICA: Aprova se o resumo aborda o tópico, mesmo brevemente.
Diferenças de fraseado/ordem NÃO são lacunas.
"""

PROMPT_MISSING_SECTIONS = """És **O Professor**. Gera SECÇÕES ADICIONAIS apenas para os tópicos em
falta — NÃO regeneres o resumo inteiro.

INSTRUÇÕES:
1. Para cada tópico em falta, produz secção com header `### {{topic_name}}`.
2. Conteúdo: 2-4 parágrafos densos com info do material original.
3. NÃO repitas conteúdo já no resumo.
4. NÃO incluas preâmbulos. Devolve APENAS as secções novas.

MATERIAL ORIGINAL:
```
{material}
```

RESUMO ACTUAL (não repitas):
```
{summary}
```

TÓPICOS EM FALTA:
{missing_topics}
"""


def _build_summary_system(lang_code: str) -> str:
    return (
        PROMPT_RESUMO_TEMPLATE.format(section_labels=section_labels_block(lang_code))
        + "\n\n" + language_instruction(lang_code)
    )


# ════════════════════════════════════════════════════════════════════════════
# CHUNKING
# ════════════════════════════════════════════════════════════════════════════

def safe_truncate(text: str, max_chars: int) -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    marker = "\n\n[... truncated by context limit ...]"
    return text[: max_chars - len(marker) - HARD_TRUNCATE_MARGIN] + marker


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_SUMMARY_CHUNK) -> List[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    paragraphs = text.split("\n\n")
    buffer = ""
    for para in paragraphs:
        if len(para) > max_chars:
            if buffer:
                chunks.append(buffer.strip()); buffer = ""
            for i in range(0, len(para), max_chars):
                chunks.append(para[i : i + max_chars])
            continue
        candidate = (buffer + "\n\n" + para) if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            if buffer: chunks.append(buffer.strip())
            buffer = para
    if buffer: chunks.append(buffer.strip())
    return chunks


# ════════════════════════════════════════════════════════════════════════════
# FASES 0-3 (mantém da v5.1)
# ════════════════════════════════════════════════════════════════════════════

def extract_topic_index(client, pdf_text, status_container, lang_code, *, stream_fn, model):
    status_container.write(t("extracting_topic_index"))
    material = safe_truncate(pdf_text, MAX_CHARS_FOR_COVERAGE)
    system = PROMPT_TOPIC_INDEX + "\n\n" + language_instruction(lang_code)
    user = f"DOCUMENTO:\n\n{material}"
    return stream_fn(client, model, system, user, status_container,
                     temperature=0.1, max_tokens=1200, lang_code=lang_code)


def _generate_summary(client, pdf_text, topic_index, pdf_name, status_container,
                     lang_code, *, stream_fn, model):
    system_prompt = _build_summary_system(lang_code)
    index_block = f"ÍNDICE DE TÓPICOS A COBRIR OBRIGATORIAMENTE:\n\n{topic_index}\n\n---\n\n"
    chunks = chunk_text(pdf_text)
    n_chunks = len(chunks)

    if n_chunks == 1:
        status_container.write(t("summarizing", name=pdf_name, chars=len(pdf_text)))
        user = index_block + f"MATERIAL DE ESTUDO:\n\n{pdf_text}"
        return stream_fn(client, model, system_prompt, user, status_container,
                         temperature=0.3, max_tokens=4500, lang_code=lang_code)

    status_container.write(t("big_pdf_split", name=pdf_name, n=n_chunks))
    partials = []
    for i, chunk in enumerate(chunks, start=1):
        status_container.write(t("chunk_progress", i=i, n=n_chunks, chars=len(chunk)))
        user = index_block + f"BLOCO {i}/{n_chunks}:\n\n{chunk}"
        partial = stream_fn(client, model, system_prompt, user, status_container,
                            temperature=0.3, max_tokens=3500, lang_code=lang_code)
        partials.append(f"### Bloco {i}/{n_chunks}\n{partial}")

    status_container.write("🧩 A consolidar resumos parciais...")
    reduce_instr = (
        "Recebeste resumos PARCIAIS de blocos consecutivos. Produz UM ÚNICO "
        "resumo consolidado, mantendo a estrutura, SEM duplicar e SEM PERDER "
        "tópicos do índice. Termina com `## 📋 Cobertura` listando TODOS os "
        "tópicos abordados."
    )
    user = reduce_instr + "\n\n" + index_block + "RESUMOS PARCIAIS:\n\n" + "\n\n".join(partials)
    return stream_fn(client, model, system_prompt, user, status_container,
                     temperature=0.3, max_tokens=5500, lang_code=lang_code)


def _audit_coverage_against_index(client, topic_index, summary, status_container,
                                  lang_code, *, stream_fn, model):
    status_container.write(t("checking_coverage"))
    system = PROMPT_COVERAGE_AUDIT.format(
        ok_marker=COVERAGE_OK_MARKER, gaps_marker=COVERAGE_GAPS_MARKER,
    ) + "\n\n" + language_instruction(lang_code)
    user = f"ÍNDICE:\n```\n{topic_index}\n```\n\nRESUMO:\n```\n{summary}\n```"
    response = stream_fn(client, model, system, user, status_container,
                         temperature=0.1, max_tokens=600, lang_code=lang_code)

    first_line = response.strip().split("\n", 1)[0].strip().upper()
    if first_line.startswith(COVERAGE_OK_MARKER.upper()):
        return True, []

    body = response
    if first_line.startswith(COVERAGE_GAPS_MARKER.upper()):
        body = response.split("\n", 1)[1] if "\n" in response else ""

    missing = []
    for line in body.split("\n"):
        if line.strip().startswith(("-", "*", "•")):
            cleaned = line.lstrip("-*• ").strip().lstrip("*").rstrip("*").strip()
            if cleaned: missing.append(cleaned[:120])
    return False, missing


def _generate_missing_sections(client, pdf_text, summary, missing_topics,
                               status_container, lang_code, *, stream_fn, model):
    if not missing_topics:
        return ""
    status_container.write(t("coverage_gaps_filling", n=len(missing_topics)))
    material = safe_truncate(pdf_text, MAX_CHARS_FOR_COVERAGE)
    topics_block = "\n".join(f"- {t_}" for t_ in missing_topics)
    system = (
        PROMPT_MISSING_SECTIONS.format(material=material, summary=summary,
                                       missing_topics=topics_block)
        + "\n\n" + language_instruction(lang_code)
    )
    user = "Gera agora as secções para os tópicos em falta. Apenas as secções novas."
    return stream_fn(client, model, system, user, status_container,
                     temperature=0.3, max_tokens=2500, lang_code=lang_code)


def _inject_sections_into_summary(summary, new_sections):
    if not new_sections.strip():
        return summary
    lines = summary.split("\n")
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and "📋" in line:
            insert_at = i; break
    if insert_at is None:
        return summary.rstrip() + "\n\n" + new_sections.strip() + "\n"
    before = "\n".join(lines[:insert_at]).rstrip()
    after = "\n".join(lines[insert_at:])
    return before + "\n\n" + new_sections.strip() + "\n\n" + after


def summarize_pdf_robust(client, pdf_name, pdf_text, status_container,
                         lang_code, do_coverage_check, *, stream_fn) -> Tuple[str, str, str]:
    """Pipeline 4 fases. Devolve (topic_index, summary, coverage_status)."""
    model = st.session_state.get("summary_model", DEFAULT_SUMMARY_MODEL) \
        if hasattr(st, "session_state") else DEFAULT_SUMMARY_MODEL

    topic_index = extract_topic_index(
        client, pdf_text, status_container, lang_code, stream_fn=stream_fn, model=model,
    )
    summary = _generate_summary(
        client, pdf_text, topic_index, pdf_name, status_container, lang_code,
        stream_fn=stream_fn, model=model,
    )
    if not do_coverage_check:
        return topic_index, summary, "skipped"

    is_ok, missing = _audit_coverage_against_index(
        client, topic_index, summary, status_container, lang_code,
        stream_fn=stream_fn, model=model,
    )
    if is_ok:
        status_container.write(t("coverage_ok"))
        return topic_index, summary, "ok"

    status_container.write(t("coverage_gaps_detected", n=len(missing)))
    new_sections = _generate_missing_sections(
        client, pdf_text, summary, missing, status_container, lang_code,
        stream_fn=stream_fn, model=model,
    )
    final_summary = _inject_sections_into_summary(summary, new_sections)
    status_container.write(t("coverage_expanded"))
    return topic_index, final_summary, "gaps_filled"


# ════════════════════════════════════════════════════════════════════════════
# ⭐ v5.2 — PIPELINE COMPLETO (orquestração end-to-end)
# ════════════════════════════════════════════════════════════════════════════

def process_document_pipeline(
    file: Any,
    *,
    conn: sqlite3.Connection,
    client,
    stream_fn: Callable,
    vision_callback: Optional[Callable[[bytes], str]] = None,
    ui_container,
    lang_code: str = "pt",
    max_rounds: int = 4,
    coverage_check: bool = True,
    force_rerun: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline end-to-end de um ficheiro (qualquer formato suportado).

    Fluxo (spec §6):
      1. Lê bytes + calcula file_hash (SHA-256)
      2. Lookup na BD por hash:
         • Se existir Document + última Analysis → CACHE HIT (devolve)
      3. Caso contrário:
         a. ingest_file (com vision_callback opcional)
         b. Insert Document na BD
         c. summarize_pdf_robust (índice → resumo → auditoria → gap-fill)
         d. run_consensus_loop (debate 4 agentes)
         e. Insert Analysis (JSONs)
      4. Devolve dict completo com tudo o que a UI precisa.

    Returns:
        {
            "cached": bool,
            "document_id": int,
            "file_name": str,
            "file_type": str,
            "file_hash": str,
            "metadata": dict,             # da ingestion
            "raw_text": str,
            "ocr_text": str,
            "topic_index": str,
            "summary": str,
            "coverage_status": str,
            "quiz_text": str,
            "debate_log": list,
            "final_author": str,
            "final_version": int,
            "consensus_reached": bool,
            "rounds_used": int,
        }
    """
    # ─── 1. Lê bytes + hash ──────────────────────────────────────────────
    if hasattr(file, "getvalue"):
        file_bytes = file.getvalue()
        file_name = getattr(file, "name", "unknown")
    elif isinstance(file, (bytes, bytearray)):
        file_bytes = bytes(file); file_name = "unknown"
    else:
        raise TypeError(f"Tipo de input não suportado: {type(file).__name__}")

    file_hash = db.compute_file_hash(file_bytes)
    file_type = ingestion._detect_extension(file_name)

    # ─── 2. DB LOOKUP por hash ───────────────────────────────────────────
    if not force_rerun:
        existing = db.get_document_by_hash(conn, file_hash)
        if existing is not None:
            analysis = db.get_latest_analysis(conn, int(existing["id"]))
            if analysis is not None:
                # CACHE HIT — serve instantaneamente
                ui_container.success(t("cache_hit", name=file_name))
                ui_container.caption(t("cache_hit_caption"))
                return _build_result_from_cache(existing, analysis)

    # ─── 3a. Ingestão ────────────────────────────────────────────────────
    with ui_container.status(t("processing_format", name=file_name, format=file_type),
                             expanded=True) as status:
        status.write(t("ingest_routing", ext=file_type))
        try:
            ing = ingestion.ingest_file(file, vision_callback=vision_callback)
        except Exception as e:
            status.update(label=f"❌ Falha na ingestão: {e}", state="error", expanded=False)
            return _empty_result(file_name, file_type, file_hash,
                                 warnings=[f"Erro de ingestão: {e}"])

        text = ing["text"]
        metadata = ing["metadata"]
        sources = ing["sources"]

        if metadata["ingestion_warnings"]:
            status.write(f"⚠️ {len(metadata['ingestion_warnings'])} aviso(s) na ingestão.")
            for w in metadata["ingestion_warnings"]:
                status.write(f"  • {w}")

        if not text.strip():
            status.update(label=t("ingest_no_text"), state="error", expanded=False)
            return _empty_result(file_name, file_type, file_hash,
                                 warnings=metadata["ingestion_warnings"])

        status.write(t("ingest_extracted", chars=len(text)))

        # ─── 3b. Insert Document ────────────────────────────────────────
        try:
            doc_id, is_new = db.get_or_insert_document(
                conn,
                file_name=metadata["file_name"],
                file_hash=metadata["file_hash"],
                file_type=metadata["file_type"],
                raw_text=sources.get("raw", ""),
                ocr_text=sources.get("ocr", ""),
                language=lang_code,
            )
        except Exception as e:
            status.update(label=f"❌ Falha a guardar Document: {e}",
                          state="error", expanded=False)
            return _empty_result(file_name, file_type, file_hash,
                                 warnings=[f"DB insert: {e}"])

        # ─── 3c. Pipeline de resumo ──────────────────────────────────────
        try:
            topic_index, summary, coverage_status = summarize_pdf_robust(
                client, file_name, text, status, lang_code, coverage_check,
                stream_fn=stream_fn,
            )
        except Exception as e:
            status.update(label=f"❌ Falha no resumo: {e}", state="error", expanded=False)
            return _empty_result(file_name, file_type, file_hash,
                                 warnings=[f"Resumo: {e}"], document_id=doc_id)

        # ─── 3d. Debate multi-agente ─────────────────────────────────────
        full_material = (
            f"### 📄 {file_name}\n\n"
            f"**ÍNDICE DE TÓPICOS:**\n{topic_index}\n\n"
            f"**RESUMO:**\n{summary}\n\n"
            f"**EXCERTO TEXTO BRUTO (até 30k chars):**\n{text[:30_000]}"
        )

        try:
            debate_result = run_consensus_loop(
                client=client, full_material=full_material,
                max_rounds=max_rounds, ui_container=status,
                lang_code=lang_code, stream_fn=stream_fn,
            )
        except Exception as e:
            status.update(label=f"❌ Falha no debate: {e}", state="error", expanded=False)
            return _empty_result(file_name, file_type, file_hash,
                                 warnings=[f"Debate: {e}"], document_id=doc_id,
                                 topic_index=topic_index, summary=summary,
                                 coverage_status=coverage_status)

        # ─── 3e. Persistir Analysis ──────────────────────────────────────
        status.write(t("db_storing"))
        summary_payload = {
            "topic_index": topic_index,
            "summary": summary,
            "coverage_status": coverage_status,
            "metadata": metadata,
        }
        quiz_payload = {
            "text": debate_result.final_content,
            "final_author": debate_result.final_author,
            "final_version": debate_result.final_version,
            "consensus_reached": debate_result.consensus_reached,
            "rounds_used": debate_result.rounds_used,
        }
        debate_log_payload = [
            {
                "round_num": e.round_num, "author": e.author,
                "validator": e.validator, "decision": e.decision,
                "version": e.version, "brief_reason": e.brief_reason,
                "kind": e.kind,
            }
            for e in debate_result.debate_log
        ]
        try:
            analysis_id = db.insert_analysis(
                conn, document_id=doc_id,
                summary_json=summary_payload,
                quiz_json=quiz_payload,
                debate_log_json=debate_log_payload,
            )
            status.write(t("db_stored", id=doc_id, aid=analysis_id))
        except Exception as e:
            status.write(f"⚠️ Análise não persistida: {e}")

        status.update(label=t("summary_done", name=file_name),
                      state="complete", expanded=False)

    # ─── 4. Result completo ──────────────────────────────────────────────
    return {
        "cached": False,
        "document_id": doc_id,
        "file_name": file_name,
        "file_type": file_type,
        "file_hash": file_hash,
        "metadata": metadata,
        "raw_text": sources.get("raw", ""),
        "ocr_text": sources.get("ocr", ""),
        "topic_index": topic_index,
        "summary": summary,
        "coverage_status": coverage_status,
        "quiz_text": debate_result.final_content,
        "debate_log": debate_log_payload,
        "final_author": debate_result.final_author,
        "final_version": debate_result.final_version,
        "consensus_reached": debate_result.consensus_reached,
        "rounds_used": debate_result.rounds_used,
    }


def _build_result_from_cache(document_row: dict, analysis: dict) -> Dict[str, Any]:
    """Constrói o dict de resultado a partir de uma cache hit da BD."""
    summary_data = analysis.get("summary_json") or {}
    quiz_data = analysis.get("quiz_json") or {}
    debate_log = analysis.get("debate_log_json") or []

    if not isinstance(summary_data, dict): summary_data = {}
    if not isinstance(quiz_data, dict): quiz_data = {}
    if not isinstance(debate_log, list): debate_log = []

    return {
        "cached": True,
        "document_id": int(document_row["id"]),
        "file_name": document_row["file_name"],
        "file_type": document_row["file_type"],
        "file_hash": document_row["file_hash"],
        "metadata": summary_data.get("metadata", {}),
        "raw_text": document_row.get("raw_text") or "",
        "ocr_text": document_row.get("ocr_text") or "",
        "topic_index": summary_data.get("topic_index", ""),
        "summary": summary_data.get("summary", ""),
        "coverage_status": summary_data.get("coverage_status", "skipped"),
        "quiz_text": quiz_data.get("text", ""),
        "debate_log": debate_log,
        "final_author": quiz_data.get("final_author", "Chefe"),
        "final_version": quiz_data.get("final_version", 1),
        "consensus_reached": quiz_data.get("consensus_reached", False),
        "rounds_used": quiz_data.get("rounds_used", 0),
    }


def _empty_result(
    file_name: str, file_type: str, file_hash: str,
    *, warnings: List[str], document_id: int = -1,
    topic_index: str = "", summary: str = "", coverage_status: str = "pending",
) -> Dict[str, Any]:
    return {
        "cached": False,
        "document_id": document_id,
        "file_name": file_name,
        "file_type": file_type,
        "file_hash": file_hash,
        "metadata": {"ingestion_warnings": warnings},
        "raw_text": "", "ocr_text": "",
        "topic_index": topic_index, "summary": summary,
        "coverage_status": coverage_status,
        "quiz_text": "", "debate_log": [],
        "final_author": "Chefe", "final_version": 1,
        "consensus_reached": False, "rounds_used": 0,
    }
