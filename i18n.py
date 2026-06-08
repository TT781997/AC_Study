"""
i18n.py — Internacionalização (v5.2)
=====================================

Chaves NOVAS v5.2:
  • cache_hit / cache_hit_caption    — instant load from DB
  • retry_attempt / rate_limit_backoff — exponential backoff feedback
  • processing_format / ingestion_warning — multi-formato
  • db_storing / db_stored / db_loaded — persistence feedback
  • upload_help_v52 — help renovada para multi-formato
"""

import random
from typing import Dict, List

import streamlit as st


LANGUAGES: Dict[str, Dict[str, str]] = {
    "pt": {"label": "🇵🇹 Português",  "llm_name": "Português Europeu (PT-PT)"},
    "en": {"label": "🇬🇧 English",     "llm_name": "English"},
    "es": {"label": "🇪🇸 Español",     "llm_name": "Español"},
    "fr": {"label": "🇫🇷 Français",    "llm_name": "français"},
    "de": {"label": "🇩🇪 Deutsch",     "llm_name": "Deutsch"},
}

SECTION_LABELS_BY_LANG: Dict[str, Dict[str, str]] = {
    "pt": {"foco": "🎯 Foco Principal",    "conceitos": "🧠 Conceitos-Chave",   "formulas": "🧮 Fórmulas/Metodologias", "aplicacao": "🏭 Aplicação Prática",     "dica": "🎓 Dica do Professor",       "cobertura": "📋 Cobertura"},
    "en": {"foco": "🎯 Main Focus",        "conceitos": "🧠 Key Concepts",      "formulas": "🧮 Formulas/Methodologies","aplicacao": "🏭 Practical Application", "dica": "🎓 Professor's Tip",        "cobertura": "📋 Coverage"},
    "es": {"foco": "🎯 Enfoque Principal", "conceitos": "🧠 Conceptos Clave",   "formulas": "🧮 Fórmulas/Metodologías", "aplicacao": "🏭 Aplicación Práctica",   "dica": "🎓 Consejo del Profesor",   "cobertura": "📋 Cobertura"},
    "fr": {"foco": "🎯 Focus Principal",   "conceitos": "🧠 Concepts Clés",     "formulas": "🧮 Formules/Méthodologies","aplicacao": "🏭 Application Pratique",  "dica": "🎓 Conseil du Professeur",  "cobertura": "📋 Couverture"},
    "de": {"foco": "🎯 Hauptfokus",        "conceitos": "🧠 Schlüsselkonzepte", "formulas": "🧮 Formeln/Methoden",      "aplicacao": "🏭 Praktische Anwendung",  "dica": "🎓 Professorentipp",        "cobertura": "📋 Abdeckung"},
}

AGENT_DISPLAY_NAMES: Dict[str, Dict[str, str]] = {
    "pt": {"Chefe": "Chefe Redator",    "Verificador Técnico": "Verificador Técnico",     "Verificador Pedagógico": "Verificador Pedagógico",  "Aluno Crítico": "Aluno Crítico"},
    "en": {"Chefe": "Lead Writer",       "Verificador Técnico": "Technical Reviewer",     "Verificador Pedagógico": "Pedagogical Reviewer",    "Aluno Crítico": "Critical Student"},
    "es": {"Chefe": "Redactor Principal","Verificador Técnico": "Revisor Técnico",        "Verificador Pedagógico": "Revisor Pedagógico",      "Aluno Crítico": "Estudiante Crítico"},
    "fr": {"Chefe": "Rédacteur Principal","Verificador Técnico":"Vérificateur Technique","Verificador Pedagógico": "Vérificateur Pédagogique","Aluno Crítico": "Étudiant Critique"},
    "de": {"Chefe": "Chefredakteur",     "Verificador Técnico": "Technischer Prüfer",     "Verificador Pedagógico": "Pädagogischer Prüfer",    "Aluno Crítico": "Kritischer Student"},
}

AGENT_ROLE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "pt": {"Chefe": "Cria o draft inicial",       "Verificador Técnico": "Cálculos, fórmulas, factos",     "Verificador Pedagógico": "Clareza e didáctica",         "Aluno Crítico": "Perspectiva do utilizador"},
    "en": {"Chefe": "Drafts the initial version", "Verificador Técnico": "Calculations, formulas, facts",  "Verificador Pedagógico": "Clarity & teaching quality",  "Aluno Crítico": "End-user perspective"},
    "es": {"Chefe": "Crea el borrador inicial",   "Verificador Técnico": "Cálculos, fórmulas, hechos",     "Verificador Pedagógico": "Claridad y didáctica",        "Aluno Crítico": "Perspectiva del usuario"},
    "fr": {"Chefe": "Crée le brouillon initial",  "Verificador Técnico": "Calculs, formules, faits",       "Verificador Pedagógico": "Clarté et didactique",        "Aluno Crítico": "Perspective de l'utilisateur"},
    "de": {"Chefe": "Erstellt den Erstentwurf",   "Verificador Técnico": "Berechnungen, Formeln, Fakten",  "Verificador Pedagógico": "Klarheit & Didaktik",         "Aluno Crítico": "Perspektive des Nutzers"},
}


I18N: Dict[str, Dict[str, str]] = {
    # ═══════════════════════════════════════════════════════════════════════
    # PORTUGUÊS
    # ═══════════════════════════════════════════════════════════════════════
    "pt": {
        "app_title": "Universal ScholarGPT",
        "subtitle": "Multi-formato (PDF/DOCX/PPTX/XLSX/HTML/MD/TXT/Imagens) · Debate de 4 agentes · Persistência SQLite · Vision LLM OCR",
        "badge_universal": "🎓 Qualquer disciplina",
        "badge_multilang": "🌐 5 idiomas",
        "badge_coverage": "📋 Cobertura via Índice",
        "badge_4agents": "🤖 4 agentes",
        "badge_persistence": "💾 Persistência SQLite",
        "badge_multimodal": "🖼️ Vision OCR",

        "how_to_use_title": "How to use",
        "how_to_use_step1": "Get your NVIDIA API key [here]({url}) 🔑",
        "how_to_use_step2": "Enter your API key below ⬇️",
        "how_to_use_step3": "Upload a file (PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG) 📄",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Obrigatória. Modelos e definições no painel ⚙️ no canto superior direito.",
        "key_loaded": "🔒 Chave carregada — IA ativa",
        "no_key": "Sem chave — IA inativa.",
        "upload_files": "📁 Carregar Ficheiros",
        "upload_help_v52": "Suporta PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG. Cada ficheiro é processado uma única vez (hash SHA-256 → cache na BD).",
        "files_loaded": "✅ {n} ficheiro(s) na BD",
        "language": "Idioma da interface",
        "language_help": "Idioma de toda a UI. Output do LLM configurável separadamente em ⚙️.",
        "db_section": "🗑️ Base de Dados",
        "db_confirm": "Confirmar apagar TUDO",
        "db_confirm_help": "Marca para libertar o botão.",
        "db_delete_btn": "🗑️ Apagar Base de Dados",
        "db_deleted": "Base de dados apagada ({n} documentos).",
        "db_empty": "(BD vazia)",
        "db_stats": "📊 {docs} documentos · {analyses} análises",

        "right_panel_open": "⚙️",
        "right_panel_help": "Configurações avançadas",
        "right_panel_title": "⚙️ Configurações Avançadas",
        "output_language": "🌍 Idioma de saída (LLM)",
        "output_language_help": "Idioma em que o LLM produz output. Pode diferir da UI.",
        "max_rounds": "🔁 Máximo de rondas (debate)",
        "summary_model_label": "🧠 Modelo do Professor (resumos)",
        "debate_models_label": "🤖 Modelos do debate (4 agentes)",
        "coverage_check_label": "🔍 Verificação de cobertura",
        "coverage_check_help": "Auditoria contra Índice de Tópicos. +1-2 chamadas LLM.",
        "model_404_hint": "Erro 404? Muda aqui para um modelo a que tenhas acesso.",
        "custom_model_input": "ID exato do modelo NVIDIA NIM",
        "reset_models": "↺ Repor defaults",
        "vision_model_label": "🖼️ Modelo Vision (OCR de PDFs digitalizados/imagens)",
        "vision_model_help": "Usado quando o PDF não tem texto extraível ou para imagens (PNG/JPG).",

        "welcome_title": "👋 Bem-vindo ao Universal ScholarGPT v5.2",
        "welcome_body": "Segue os 3 passos na barra lateral esquerda. A plataforma irá automaticamente:",
        "welcome_b1": "📦 Verificar na BD se o ficheiro já foi processado (instantâneo se sim)",
        "welcome_b2": "📑 Extrair texto (PyMuPDF, python-docx, etc.) + Vision OCR se necessário",
        "welcome_b3": "🧠 Gerar Índice de Tópicos → Resumo Map-Reduce → Auditoria de Cobertura",
        "welcome_b4": "🎓 Debate de 4 agentes → Quiz com respostas escondidas (`👀 Ver Respostas`)",
        "welcome_b5": "💾 Persistir tudo na BD SQLite para acesso futuro instantâneo",

        # ⭐ v5.2 — cache + retry
        "cache_hit": "📦 **{name}** carregado da BD (cache hit, instantâneo)",
        "cache_hit_caption": "Hash SHA-256 coincide com análise anterior. Para refazer, usa **🔄 Refazer**.",
        "retry_attempt": "🔄 Tentativa {n}/{total} após {sec}s (retry exponential backoff)…",
        "rate_limit_backoff": "⏳ Rate limit detectado; a aguardar {sec}s antes da tentativa {n}…",
        "retry_giving_up": "❌ Esgotadas {n} tentativas. Última: {err}",

        # ⭐ v5.2 — ingestão + processamento
        "processing_format": "📄 A processar **{name}** ({format})",
        "ingest_routing": "🔀 Roteamento por formato: `.{ext}`",
        "ingest_extracted": "📝 Texto extraído: {chars:,} caracteres",
        "ingest_no_text": "⚠️ Não foi possível extrair texto deste ficheiro.",
        "ingest_warnings_title": "Avisos de ingestão:",
        "ingest_ocr_triggered": "📷 Fallback OCR accionado: {reason}",
        "ingest_vision_call": "👁️ Chamando Vision LLM para imagem (página {page})…",
        "ingest_tesseract_call": "🔤 Usando Tesseract local (página {page})…",

        # ⭐ v5.2 — DB
        "db_lookup": "🔍 A verificar BD por hash {hash}...",
        "db_storing": "💾 A guardar análise na BD...",
        "db_stored": "✅ Persistido (document_id={id}, analysis_id={aid})",
        "db_loaded_from_cache": "📦 Carregado da BD (cache local + persistente)",

        # PDF/document tab
        "regen_summary": "🔄 Refazer análise (nova chamada LLM)",
        "view_raw": "🔍 Texto extraído (raw)",
        "view_ocr": "📷 Texto OCR (Vision/Tesseract)",
        "view_topic_index": "📑 Índice de Tópicos",
        "view_metadata": "🔬 Metadados de ingestão",
        "summary_auto": "🤖 Auto-gerado",
        "summary_pending": "📝 Pendente",
        "summary_cached": "📦 Cached",
        "pages_chars": "📑 <b>{pages}</b> {page_label} · {chars:,} caracteres · {badge} · cobertura: {cov}",
        "page_label_singular": "página",
        "page_label_plural": "páginas",
        "n_a": "N/A",
        "no_summary_yet": "Sem resumo. Carrega em **🔄 Refazer análise**.",

        # Processing status
        "extracting_topic_index": "📑 A extrair Índice de Tópicos…",
        "summarizing": "📝 A resumir `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` é grande — **{n} blocos**.",
        "chunk_progress": "🧠 Bloco {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ `{name}` processado!",
        "summary_fail": "❌ Falha ao processar `{name}`.",
        "regen_progress": "🔄 A refazer análise de **{name}**",
        "regen_done": "✅ Análise refeita!",
        "regen_fail": "❌ Falha ao refazer.",
        "checking_coverage": "🔍 A auditar cobertura contra o Índice…",
        "coverage_ok": "✅ Cobertura completa.",
        "coverage_gaps_detected": "🩹 Detectadas **{n} lacunas**.",
        "coverage_gaps_filling": "✏️ A gerar **{n} secções** em falta…",
        "coverage_expanded": "✨ Secções injetadas no resumo.",

        "coverage_status_ok":          "✅ OK",
        "coverage_status_gaps_filled": "🩹 Lacunas preenchidas",
        "coverage_status_skipped":     "⏭️ Saltada",
        "coverage_status_pending":     "⏳ Pendente",

        # Eval tab
        "tab_eval": "🎓 Avaliação",
        "eval_title": "🎓 Avaliação Interactiva",
        "eval_caption": "Os 4 agentes debatem em loop circular. Consenso unânime = 3 APPROVE na MESMA ronda. Soluções escondidas até **👀 Ver Respostas**.",
        "eval_select_pdfs": "📚 Ficheiros a incluir",
        "eval_select_q": "Quais ficheiros?",
        "eval_select_all": "✅ Todos",
        "eval_select_none": "🚫 Limpar",
        "btn_run_eval": "🚀 Iniciar Debate",
        "btn_redo_eval": "🔄 Refazer",
        "btn_clear": "🗑️ Limpar",
        "warn_set_key": "Define a NVIDIA API Key na barra lateral esquerda.",
        "warn_pick_pdf": "Seleciona pelo menos um ficheiro acima.",
        "info_limit": "Limite actual: **{n} rondas** · Selecionados: **{k}**.",
        "info_start_upload": "📁 Começa por carregar ficheiros na barra lateral.",
        "debate_in_progress": "🎬 Debate em curso…",

        "consensus_in": "🎉 Consenso unânime na ronda {n}",
        "consensus_msg": "🎉 Consenso unânime na ronda {i}! V{v} de {a} aprovada por: {others}.",
        "consensus_partial": "⏱️ Consenso parcial atingido após {n} rodadas. Versão actual: V{v} (de {a}).",
        "limit_reached": "⏱️ Consenso parcial atingido após {n} rodadas",
        "final_version": "🏁 Versão Final",
        "final_authorship": "Autoria final",
        "download_test": "📥 Descarregar teste (Markdown)",

        "round_of": "🔄 Ronda {i}/{n} · V{v} (autor: {a})",
        "approved": "✅ **{v}** aprovou",
        "rewrote": "✏️ **{v}** reescreveu — V{n}.",
        "chefe_drafting": "👑 **Chefe Redator** a criar V1",
        "validator_evaluating": "{icon} **{v}** a avaliar V{n} de **{a}**",

        "elapsed": "decorridos",
        "remaining": "restantes",
        "over_estimate": "+ além da estimativa",
        "model_speed": "velocidade",

        "debate_log_title": "🎬 Log Visual do Debate (tempo real)",
        "debate_log_empty": "(o log aparecerá aqui)",
        "debate_log_round": "Ronda {n}",
        "debate_log_version": "V{v}",
        "debate_log_draft": "📝 DRAFT",
        "debate_log_approve_badge": "✅ APPROVE",
        "debate_log_rewrite_badge": "✏️ REWRITE → V{v}",
        "debate_log_by": "{validator_icon} {validator} avaliou {author_icon} {author}",
        "debate_log_authored": "{author_icon} {author} (autor)",
        "debate_log_no_reason": "(sem motivo explícito)",

        "quiz_questions_title": "📝 Enunciados do Quiz",
        "answers_section_title": "✅ Soluções",
        "show_answers_btn": "👀 Ver Respostas",
        "quiz_try_first": "💡 **Tenta resolver primeiro!** Soluções escondidas no expander abaixo.",
        "answers_revealed_info": "👁️ Soluções reveladas.",
        "no_separator_warning": "⚠️ O modelo não usou o separador `=== RESPOSTAS ===`. Mostro tudo junto.",
        "download_questions": "📥 Só enunciados (.md)",
        "download_full": "📥 Quiz completo (.md)",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # ENGLISH
    # ═══════════════════════════════════════════════════════════════════════
    "en": {
        "app_title": "Universal ScholarGPT",
        "subtitle": "Multi-format (PDF/DOCX/PPTX/XLSX/HTML/MD/TXT/Images) · 4-agent debate · SQLite persistence · Vision LLM OCR",
        "badge_universal": "🎓 Any discipline", "badge_multilang": "🌐 5 languages",
        "badge_coverage": "📋 Index-based coverage", "badge_4agents": "🤖 4 agents",
        "badge_persistence": "💾 SQLite persistence", "badge_multimodal": "🖼️ Vision OCR",

        "how_to_use_title": "How to use",
        "how_to_use_step1": "Get your NVIDIA API key [here]({url}) 🔑",
        "how_to_use_step2": "Enter your API key below ⬇️",
        "how_to_use_step3": "Upload a file (PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG) 📄",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Required. Models and settings are in the ⚙️ panel at top-right.",
        "key_loaded": "🔒 Key loaded — AI active",
        "no_key": "No key — AI disabled.",
        "upload_files": "📁 Upload Files",
        "upload_help_v52": "Supports PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG. Each file is processed once (SHA-256 hash → DB cache).",
        "files_loaded": "✅ {n} file(s) in DB",
        "language": "Interface language",
        "language_help": "Language of the entire UI. LLM output language is configurable in ⚙️.",
        "db_section": "🗑️ Database",
        "db_confirm": "Confirm DELETE ALL",
        "db_confirm_help": "Tick to enable.",
        "db_delete_btn": "🗑️ Delete Database",
        "db_deleted": "Database deleted ({n} documents).",
        "db_empty": "(DB empty)",
        "db_stats": "📊 {docs} documents · {analyses} analyses",

        "right_panel_open": "⚙️", "right_panel_help": "Advanced settings",
        "right_panel_title": "⚙️ Advanced Settings",
        "output_language": "🌍 Output language (LLM)",
        "output_language_help": "LLM output language. Can differ from UI.",
        "max_rounds": "🔁 Max debate rounds",
        "summary_model_label": "🧠 Professor's model (summaries)",
        "debate_models_label": "🤖 Debate models (4 agents)",
        "coverage_check_label": "🔍 Coverage check",
        "coverage_check_help": "Audits against Topic Index. +1-2 LLM calls.",
        "model_404_hint": "404? Pick a model your account can access.",
        "custom_model_input": "Exact NVIDIA NIM model ID",
        "reset_models": "↺ Reset defaults",
        "vision_model_label": "🖼️ Vision model (OCR for scanned PDFs / images)",
        "vision_model_help": "Used when PDF has no extractable text or for images (PNG/JPG).",

        "welcome_title": "👋 Welcome to Universal ScholarGPT v5.2",
        "welcome_body": "Follow the 3 steps in the left sidebar. The platform will automatically:",
        "welcome_b1": "📦 Check the DB if the file was already processed (instant if yes)",
        "welcome_b2": "📑 Extract text (PyMuPDF, python-docx, etc.) + Vision OCR if needed",
        "welcome_b3": "🧠 Generate Topic Index → Map-Reduce Summary → Coverage Audit",
        "welcome_b4": "🎓 4-agent debate → Quiz with hidden answers (`👀 Show Answers`)",
        "welcome_b5": "💾 Persist everything to SQLite for instant future access",

        "cache_hit": "📦 **{name}** loaded from DB (cache hit, instant)",
        "cache_hit_caption": "SHA-256 hash matches a previous analysis. Use **🔄 Redo** to regenerate.",
        "retry_attempt": "🔄 Attempt {n}/{total} after {sec}s (exponential backoff)…",
        "rate_limit_backoff": "⏳ Rate limit detected; waiting {sec}s before attempt {n}…",
        "retry_giving_up": "❌ Exhausted {n} attempts. Last error: {err}",

        "processing_format": "📄 Processing **{name}** ({format})",
        "ingest_routing": "🔀 Routing by format: `.{ext}`",
        "ingest_extracted": "📝 Text extracted: {chars:,} characters",
        "ingest_no_text": "⚠️ Could not extract text from this file.",
        "ingest_warnings_title": "Ingestion warnings:",
        "ingest_ocr_triggered": "📷 OCR fallback triggered: {reason}",
        "ingest_vision_call": "👁️ Calling Vision LLM for image (page {page})…",
        "ingest_tesseract_call": "🔤 Using local Tesseract (page {page})…",

        "db_lookup": "🔍 Checking DB by hash {hash}...",
        "db_storing": "💾 Saving analysis to DB...",
        "db_stored": "✅ Persisted (document_id={id}, analysis_id={aid})",
        "db_loaded_from_cache": "📦 Loaded from DB (local + persistent cache)",

        "regen_summary": "🔄 Redo analysis (new LLM call)",
        "view_raw": "🔍 Extracted text (raw)",
        "view_ocr": "📷 OCR text (Vision/Tesseract)",
        "view_topic_index": "📑 Topic Index",
        "view_metadata": "🔬 Ingestion metadata",
        "summary_auto": "🤖 Auto-generated",
        "summary_pending": "📝 Pending",
        "summary_cached": "📦 Cached",
        "pages_chars": "📑 <b>{pages}</b> {page_label} · {chars:,} characters · {badge} · coverage: {cov}",
        "page_label_singular": "page",
        "page_label_plural": "pages",
        "n_a": "N/A",
        "no_summary_yet": "No summary. Click **🔄 Redo analysis**.",

        "extracting_topic_index": "📑 Extracting Topic Index…",
        "summarizing": "📝 Summarising `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` is large — **{n} chunks**.",
        "chunk_progress": "🧠 Chunk {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ `{name}` processed!",
        "summary_fail": "❌ Failed to process `{name}`.",
        "regen_progress": "🔄 Redoing analysis of **{name}**",
        "regen_done": "✅ Analysis redone!",
        "regen_fail": "❌ Failed to redo.",
        "checking_coverage": "🔍 Auditing coverage against Index…",
        "coverage_ok": "✅ Full coverage.",
        "coverage_gaps_detected": "🩹 Detected **{n} gaps**.",
        "coverage_gaps_filling": "✏️ Generating **{n} missing sections**…",
        "coverage_expanded": "✨ Sections injected into summary.",

        "coverage_status_ok": "✅ OK", "coverage_status_gaps_filled": "🩹 Gaps filled",
        "coverage_status_skipped": "⏭️ Skipped", "coverage_status_pending": "⏳ Pending",

        "tab_eval": "🎓 Evaluation", "eval_title": "🎓 Interactive Evaluation",
        "eval_caption": "The 4 agents debate in a circular loop. Unanimous consensus = 3 APPROVE in the SAME round.",
        "eval_select_pdfs": "📚 Files to include", "eval_select_q": "Which files?",
        "eval_select_all": "✅ All", "eval_select_none": "🚫 Clear",
        "btn_run_eval": "🚀 Start Debate", "btn_redo_eval": "🔄 Redo",
        "btn_clear": "🗑️ Clear",
        "warn_set_key": "Set the NVIDIA API Key in the left sidebar.",
        "warn_pick_pdf": "Select at least one file.",
        "info_limit": "Current limit: **{n} rounds** · Selected: **{k}**.",
        "info_start_upload": "📁 Start by uploading files in the left sidebar.",
        "debate_in_progress": "🎬 Debate in progress…",

        "consensus_in": "🎉 Unanimous consensus in round {n}",
        "consensus_msg": "🎉 Unanimous consensus in round {i}! V{v} by {a} approved by: {others}.",
        "consensus_partial": "⏱️ Partial consensus reached after {n} rounds. Current version: V{v} (by {a}).",
        "limit_reached": "⏱️ Partial consensus reached after {n} rounds",
        "final_version": "🏁 Final Version", "final_authorship": "Final authorship",
        "download_test": "📥 Download test (Markdown)",

        "round_of": "🔄 Round {i}/{n} · V{v} (author: {a})",
        "approved": "✅ **{v}** approved", "rewrote": "✏️ **{v}** rewrote — V{n}.",
        "chefe_drafting": "👑 **Lead Writer** drafting V1",
        "validator_evaluating": "{icon} **{v}** evaluating V{n} by **{a}**",

        "elapsed": "elapsed", "remaining": "remaining",
        "over_estimate": "over estimate", "model_speed": "speed",

        "debate_log_title": "🎬 Debate Log (live)",
        "debate_log_empty": "(log will appear here)",
        "debate_log_round": "Round {n}", "debate_log_version": "V{v}",
        "debate_log_draft": "📝 DRAFT", "debate_log_approve_badge": "✅ APPROVE",
        "debate_log_rewrite_badge": "✏️ REWRITE → V{v}",
        "debate_log_by": "{validator_icon} {validator} evaluated {author_icon} {author}",
        "debate_log_authored": "{author_icon} {author} (author)",
        "debate_log_no_reason": "(no explicit reason)",

        "quiz_questions_title": "📝 Quiz Questions", "answers_section_title": "✅ Solutions",
        "show_answers_btn": "👀 Show Answers",
        "quiz_try_first": "💡 **Try solving first!** Solutions hidden in expander.",
        "answers_revealed_info": "👁️ Solutions revealed.",
        "no_separator_warning": "⚠️ Model didn't use the separator.",
        "download_questions": "📥 Questions only (.md)", "download_full": "📥 Full quiz (.md)",
    },

    # ═══════════════════════════════════════════════════════════════════════
    # ESPAÑOL / FRANÇAIS / DEUTSCH (compactos — só chaves essenciais novas v5.2,
    # reusam estruturas v5.1 para o resto)
    # ═══════════════════════════════════════════════════════════════════════
}


def _build_es_fr_de_from_en() -> None:
    """
    Para ES/FR/DE, populamos a partir de EN para garantir que TODAS as chaves
    existem. Strings críticas v5.2 são depois sobrescritas.
    """
    base_en = I18N["en"]
    for lang in ("es", "fr", "de"):
        if lang not in I18N:
            I18N[lang] = dict(base_en)


_build_es_fr_de_from_en()

# ── Overrides Español ─────────────────────────────────────────────────────
I18N["es"].update({
    "subtitle": "Multi-formato · Debate de 4 agentes · Persistencia SQLite · Vision LLM OCR",
    "language": "Idioma de la interfaz", "language_help": "Idioma de toda la UI.",
    "upload_files": "📁 Cargar Ficheros",
    "upload_help_v52": "Soporta PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG. Hash SHA-256 → cache.",
    "files_loaded": "✅ {n} fichero(s) en BD",
    "cache_hit": "📦 **{name}** cargado de la BD (cache hit, instantáneo)",
    "cache_hit_caption": "Hash SHA-256 coincide con análisis anterior. Usa **🔄 Rehacer** para regenerar.",
    "retry_attempt": "🔄 Intento {n}/{total} tras {sec}s (backoff exponencial)…",
    "rate_limit_backoff": "⏳ Rate limit detectado; esperando {sec}s antes del intento {n}…",
    "retry_giving_up": "❌ Agotados {n} intentos. Último error: {err}",
    "processing_format": "📄 Procesando **{name}** ({format})",
    "ingest_no_text": "⚠️ No fue posible extraer texto.",
    "db_storing": "💾 Guardando análisis en BD...",
    "db_stored": "✅ Persistido (document_id={id}, analysis_id={aid})",
    "consensus_partial": "⏱️ Consenso parcial alcanzado tras {n} rondas. Versión: V{v} (de {a}).",
    "show_answers_btn": "👀 Ver Respuestas",
    "welcome_title": "👋 Bienvenido a Universal ScholarGPT v5.2",
})

# ── Overrides Français ────────────────────────────────────────────────────
I18N["fr"].update({
    "subtitle": "Multi-format · Débat 4 agents · Persistance SQLite · Vision LLM OCR",
    "language": "Langue de l'interface", "language_help": "Langue de toute l'UI.",
    "upload_files": "📁 Charger Fichiers",
    "upload_help_v52": "Supporte PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG. Hash SHA-256 → cache.",
    "files_loaded": "✅ {n} fichier(s) en BD",
    "cache_hit": "📦 **{name}** chargé depuis la BD (cache hit, instantané)",
    "cache_hit_caption": "Hash SHA-256 correspond à une analyse antérieure. Utilise **🔄 Refaire**.",
    "retry_attempt": "🔄 Tentative {n}/{total} après {sec}s (backoff exponentiel)…",
    "rate_limit_backoff": "⏳ Rate limit détecté; attente {sec}s avant tentative {n}…",
    "retry_giving_up": "❌ {n} tentatives épuisées. Dernière erreur : {err}",
    "processing_format": "📄 Traitement de **{name}** ({format})",
    "ingest_no_text": "⚠️ Impossible d'extraire le texte.",
    "db_storing": "💾 Enregistrement de l'analyse en BD...",
    "db_stored": "✅ Persisté (document_id={id}, analysis_id={aid})",
    "consensus_partial": "⏱️ Consensus partiel atteint après {n} tours. Version : V{v} (de {a}).",
    "show_answers_btn": "👀 Voir les Réponses",
    "welcome_title": "👋 Bienvenue dans Universal ScholarGPT v5.2",
})

# ── Overrides Deutsch ─────────────────────────────────────────────────────
I18N["de"].update({
    "subtitle": "Multi-Format · 4-Agenten-Debatte · SQLite-Persistenz · Vision LLM OCR",
    "language": "Oberflächensprache", "language_help": "UI-Sprache.",
    "upload_files": "📁 Dateien hochladen",
    "upload_help_v52": "Unterstützt PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG. SHA-256 → Cache.",
    "files_loaded": "✅ {n} Datei(en) in DB",
    "cache_hit": "📦 **{name}** aus DB geladen (Cache-Hit, sofort)",
    "cache_hit_caption": "SHA-256-Hash stimmt mit früherer Analyse überein. Nutze **🔄 Wiederholen**.",
    "retry_attempt": "🔄 Versuch {n}/{total} nach {sec}s (Exponential Backoff)…",
    "rate_limit_backoff": "⏳ Rate Limit erkannt; warte {sec}s vor Versuch {n}…",
    "retry_giving_up": "❌ {n} Versuche erschöpft. Letzter Fehler: {err}",
    "processing_format": "📄 Verarbeite **{name}** ({format})",
    "ingest_no_text": "⚠️ Konnte keinen Text extrahieren.",
    "db_storing": "💾 Speichere Analyse in DB...",
    "db_stored": "✅ Gespeichert (document_id={id}, analysis_id={aid})",
    "consensus_partial": "⏱️ Teilkonsens erreicht nach {n} Runden. Version: V{v} (von {a}).",
    "show_answers_btn": "👀 Antworten zeigen",
    "welcome_title": "👋 Willkommen bei Universal ScholarGPT v5.2",
})


FUNNY_LOADING_MESSAGES_BY_LANG: Dict[str, List[str]] = {
    "pt": ["🐱 Agentes a tomar café…", "🦉 Coruja a conferir fórmulas…",
           "🦫 Castores a construir o resumo…", "🐢 Devagar com rigor…",
           "🐧 Pinguins em reunião…", "🦊 Raposa-técnica em alerta…",
           "🐙 8 braços a escrever Markdown…", "🦦 Lontras a polir definições…"],
    "en": ["🐱 Agents sipping coffee…", "🦉 Reviewer owl checking formulas…",
           "🦫 Beavers building the summary…", "🐢 Slow with rigour…",
           "🐧 Penguins in a meeting…", "🦊 Technical fox on alert…",
           "🐙 Eight arms typing Markdown…", "🦦 Otters polishing definitions…"],
    "es": ["🐱 Agentes tomando café…", "🦉 Búho revisando fórmulas…",
           "🦫 Castores construyendo el resumen…", "🐢 Despacio con rigor…",
           "🐧 Pingüinos en reunión…", "🦊 Zorro técnico en alerta…",
           "🐙 8 brazos escribiendo Markdown…", "🦦 Nutrias puliendo definiciones…"],
    "fr": ["🐱 Agents prenant un café…", "🦉 Chouette vérifiant les formules…",
           "🦫 Castors construisant le résumé…", "🐢 Lentement avec rigueur…",
           "🐧 Pingouins en réunion…", "🦊 Renard technique en alerte…",
           "🐙 8 bras tapant du Markdown…", "🦦 Loutres polissant les définitions…"],
    "de": ["🐱 Agenten trinken Kaffee…", "🦉 Eule prüft Formeln…",
           "🦫 Biber bauen die Zusammenfassung…", "🐢 Langsam mit Sorgfalt…",
           "🐧 Pinguine in einer Sitzung…", "🦊 Technischer Fuchs in Alarmbereitschaft…",
           "🐙 Acht Arme tippen Markdown…", "🦦 Otter polieren Definitionen…"],
}

LOADING_EMOJIS = ["🧠", "📚", "⚙️", "🔬", "📊", "🎓", "💡", "🔍", "📝", "🏛️"]


def t(key: str, **kwargs) -> str:
    """Traduz uma chave para o idioma actual da UI."""
    lang = st.session_state.get("ui_language", "pt") if hasattr(st, "session_state") else "pt"
    try:
        val = I18N.get(lang, I18N["pt"]).get(key, I18N["pt"].get(key, key))
    except Exception:
        val = key
    try:
        return val.format(**kwargs) if kwargs else val
    except Exception:
        return val


def agent_display(agent_key: str) -> str:
    lang = st.session_state.get("ui_language", "pt") if hasattr(st, "session_state") else "pt"
    return AGENT_DISPLAY_NAMES.get(lang, AGENT_DISPLAY_NAMES["pt"]).get(agent_key, agent_key)


def agent_role_description(agent_key: str) -> str:
    lang = st.session_state.get("ui_language", "pt") if hasattr(st, "session_state") else "pt"
    return AGENT_ROLE_DESCRIPTIONS.get(lang, AGENT_ROLE_DESCRIPTIONS["pt"]).get(agent_key, "")


def language_instruction(lang_code: str) -> str:
    lang_name = LANGUAGES.get(lang_code, LANGUAGES["pt"])["llm_name"]
    return (
        f"### LANGUAGE OVERRIDE\n"
        f"You MUST produce ALL output in **{lang_name}**, regardless of the language of the source. "
        f"Do not switch languages mid-response.\n"
    )


def section_labels_block(lang_code: str) -> str:
    sl = SECTION_LABELS_BY_LANG.get(lang_code, SECTION_LABELS_BY_LANG["pt"])
    lang_name = LANGUAGES.get(lang_code, LANGUAGES['pt'])['llm_name']
    return (
        f"### SECTION HEADERS (use these EXACT labels translated into {lang_name}):\n"
        f"- {sl['foco']}\n- {sl['conceitos']}\n- {sl['formulas']}\n"
        f"- {sl['aplicacao']}\n- {sl['dica']}\n"
        f"- Final coverage section: ## {sl['cobertura']}\n"
    )


def random_fun_message(lang_code: str) -> str:
    msgs = FUNNY_LOADING_MESSAGES_BY_LANG.get(lang_code, FUNNY_LOADING_MESSAGES_BY_LANG["pt"])
    return random.choice(msgs)
