"""
app.py — Plataforma Análise de Custos ISEL (Consenso Multi-Agente) — v3.0
============================================================================

Mudanças face à v2.0:
  • IDENTIDADE ISEL CORRETA — paleta Bordeaux oficial (#9A3324) + Warm Gray
    6C/11C, logo oficial do ISEL na sidebar.
  • SELECTOR DE MODELOS (dropdown) — registry curado dos modelos NVIDIA NIM
    2026 (Nemotron 3 Super, MiniMax M2.7, GLM-5.1, DeepSeek V4, Gemma 4,
    Kimi K2.6, Step-3.x, GPT-OSS 120B, etc.) com descrição "best for" cada.
    Opção "✏️ Personalizado…" para qualquer outro modelo.
  • MULTI-IDIOMA — UI em PT / EN / ES / FR / DE; o resumo e a avaliação são
    SEMPRE produzidos no idioma escolhido, qualquer que seja a língua do PDF.
  • LOADING INTERATIVO — emoji animado por CSS + mensagens divertidas que
    rodam de 15s em 15s + GIFs opcionais que rodam de 30s em 30s + contador
    de tempo decorrido. Sem bloquear a stream de saída do LLM.
  • Tudo o resto da v2.0 mantido: persistência estrita, chunking defensivo,
    consenso circular, base de dados apagável só por botão.

Dependências:
    pip install streamlit openai PyMuPDF

Execução:
    streamlit run app.py
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import streamlit as st
from openai import OpenAI, OpenAIError


# =============================================================================
# 1. PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="ISEL · Análise de Custos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# 2. PALETA ISEL OFICIAL (Bordeaux + Warm Gray)
# =============================================================================
# Fonte: Manual de Normas do ISEL — Bordeaux #9A3324 (Pantone 484 C).
# Cinzentos secundários: Pantone Warm Gray 6C e 11C.
ISEL_PRIMARY    = "#9A3324"   # Bordeaux institucional
ISEL_PRIMARY_DK = "#7A271C"   # Bordeaux escuro (hover)
ISEL_PRIMARY_LT = "#C45A4A"   # Bordeaux claro (acento)
ISEL_GRAY_6     = "#A6A19E"   # Warm Gray 6C (cinzento claro)
ISEL_GRAY_11    = "#6E6259"   # Warm Gray 11C (cinzento escuro / texto secundário)
ISEL_BG         = "#FAF7F4"   # Off-white quente
ISEL_SURFACE    = "#FFFFFF"
ISEL_BORDER     = "#E8E2DC"
ISEL_TEXT       = "#2A1F1A"   # Quase-preto quente
ISEL_SUCCESS    = "#5B7F4C"   # Verde sereno
ISEL_WARN       = "#C49A2E"   # Amarelo bordeaux-compatível

ISEL_LOGO_URL = "https://www.isel.pt/themes/gavias_unix/images/01_ISEL-Logotipo-RGB_Horizontal-Principal-900.png"

# =============================================================================
# 3. CSS — IDENTIDADE ISEL + ANIMAÇÕES DE LOADING
# =============================================================================
CUSTOM_CSS = f"""
<style>
.stApp {{ background-color: {ISEL_BG}; }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}

h1, h2, h3, h4 {{ color: {ISEL_PRIMARY} !important; font-weight: 700; }}
h1 {{ letter-spacing: -0.02em; }}

[data-testid="stSidebar"] {{ background-color: {ISEL_SURFACE}; border-right: 1px solid {ISEL_BORDER}; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {ISEL_PRIMARY} !important; }}

/* Logo ISEL no topo da sidebar */
.isel-logo-wrap {{
    background: {ISEL_SURFACE}; padding: 0.5rem 0.5rem 1rem 0.5rem;
    border-bottom: 2px solid {ISEL_PRIMARY}; margin-bottom: 1rem;
    text-align: center;
}}
.isel-logo-wrap img {{ max-width: 180px; height: auto; }}
.isel-logo-fallback {{
    color: {ISEL_PRIMARY}; font-weight: 800; font-size: 1.3rem;
    letter-spacing: 0.05em; padding: 0.5rem;
}}

.stButton > button, .stDownloadButton > button {{
    background-color: {ISEL_PRIMARY}; color: white !important;
    border: none; border-radius: 6px; padding: 0.55rem 1.4rem;
    font-weight: 600; transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(154, 51, 36, 0.20);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    background-color: {ISEL_PRIMARY_DK}; transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(154, 51, 36, 0.30); color: white !important;
}}
.stButton > button:disabled {{ background-color: {ISEL_GRAY_6}; color: white !important; transform: none; cursor: not-allowed; }}

.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background-color: {ISEL_SURFACE}; padding: 6px;
    border-radius: 10px; border: 1px solid {ISEL_BORDER}; overflow-x: auto;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: transparent; border-radius: 7px;
    padding: 0.45rem 1rem; color: {ISEL_TEXT}; font-weight: 500;
}}
.stTabs [data-baseweb="tab"]:hover {{ background-color: rgba(154, 51, 36, 0.07); }}
.stTabs [aria-selected="true"] {{ background-color: {ISEL_PRIMARY} !important; color: white !important; }}

.stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
    border-radius: 6px; border: 1px solid {ISEL_BORDER};
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {ISEL_PRIMARY}; box-shadow: 0 0 0 2px rgba(154, 51, 36, 0.18);
}}

.stExpander {{ border-radius: 8px; border: 1px solid {ISEL_BORDER}; background-color: {ISEL_SURFACE}; }}

.isel-banner {{
    background: linear-gradient(135deg, {ISEL_PRIMARY} 0%, {ISEL_PRIMARY_DK} 100%);
    color: white; padding: 1.5rem 2rem; border-radius: 12px;
    margin-bottom: 1.5rem; box-shadow: 0 4px 14px rgba(154, 51, 36, 0.25);
}}
.isel-banner h1 {{ color: white !important; margin: 0; font-size: 1.9rem; }}
.isel-banner .subtitle {{ margin: 0.3rem 0 0 0; opacity: 0.92; font-size: 0.95rem; }}
.isel-banner .badge {{
    display: inline-block; background: rgba(255,255,255,0.18);
    padding: 2px 10px; border-radius: 12px; font-size: 0.8rem;
    margin-right: 6px; margin-top: 0.5rem;
}}

.section-title {{
    color: {ISEL_PRIMARY}; font-weight: 700; font-size: 1.05rem;
    margin: 1.25rem 0 0.6rem 0; display: flex; align-items: center; gap: 0.5rem;
}}
.section-title::before {{
    content: ""; width: 4px; height: 18px; background: {ISEL_PRIMARY}; border-radius: 2px;
}}

.agent-card {{
    background-color: {ISEL_SURFACE}; border: 1px solid {ISEL_BORDER};
    border-radius: 10px; padding: 1rem 1.1rem;
    border-left: 4px solid {ISEL_PRIMARY};
}}
.agent-card .role {{ color: {ISEL_PRIMARY}; font-weight: 700; }}
.agent-card .model {{ color: {ISEL_GRAY_11}; font-size: 0.82rem; font-family: ui-monospace, monospace; word-break: break-all; }}

.round-tag {{
    display: inline-block; background: {ISEL_PRIMARY}; color: white;
    padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;
    margin-bottom: 0.5rem;
}}
.consensus-banner {{
    background: linear-gradient(135deg, {ISEL_SUCCESS} 0%, #426d36 100%);
    color: white; padding: 1rem 1.3rem; border-radius: 10px;
    font-weight: 600; margin: 1rem 0;
}}
.no-consensus-banner {{
    background: linear-gradient(135deg, {ISEL_WARN} 0%, #9c7a24 100%);
    color: white; padding: 1rem 1.3rem; border-radius: 10px;
    font-weight: 600; margin: 1rem 0;
}}

.pdf-meta {{
    color: {ISEL_GRAY_11}; font-size: 0.85rem; margin-bottom: 1rem;
    padding: 0.6rem 0.9rem; background: {ISEL_BG};
    border-left: 3px solid {ISEL_PRIMARY}; border-radius: 4px;
}}

/* ============= LOADING INTERATIVO ============= */
@keyframes bounce-rotate {{
  0%   {{ transform: translateY(0) rotate(-8deg) scale(1.0); }}
  25%  {{ transform: translateY(-14px) rotate(0deg) scale(1.1); }}
  50%  {{ transform: translateY(0) rotate(8deg) scale(1.0); }}
  75%  {{ transform: translateY(-7px) rotate(0deg) scale(1.05); }}
  100% {{ transform: translateY(0) rotate(-8deg) scale(1.0); }}
}}
@keyframes pulse-glow {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(154, 51, 36, 0.35); }}
  50%      {{ box-shadow: 0 0 0 18px rgba(154, 51, 36, 0.0); }}
}}
.loading-fun {{
    display: flex; align-items: center; gap: 1.0rem;
    padding: 1.1rem 1.3rem; background: {ISEL_SURFACE};
    border: 1px solid {ISEL_BORDER}; border-left: 5px solid {ISEL_PRIMARY};
    border-radius: 10px; margin: 0.6rem 0;
    animation: pulse-glow 2.5s infinite;
}}
.loading-fun .big-emoji {{
    font-size: 3.0rem; line-height: 1;
    animation: bounce-rotate 1.8s infinite ease-in-out;
    display: inline-block;
}}
.loading-fun .body {{ flex: 1; }}
.loading-fun .msg {{ font-weight: 700; color: {ISEL_TEXT}; font-size: 1.0rem; }}
.loading-fun .meta {{ color: {ISEL_GRAY_11}; font-size: 0.82rem; margin-top: 0.2rem; }}
.loading-fun .progress-bar {{
    height: 6px; background: {ISEL_BORDER}; border-radius: 3px;
    margin-top: 0.5rem; overflow: hidden;
}}
.loading-fun .progress-fill {{
    height: 100%; background: linear-gradient(90deg, {ISEL_PRIMARY_LT}, {ISEL_PRIMARY});
    border-radius: 3px; transition: width 0.4s ease;
}}

.sidebar-pill {{
    display: block; background: {ISEL_BG}; border: 1px solid {ISEL_BORDER};
    border-left: 3px solid {ISEL_PRIMARY};
    padding: 0.55rem 0.85rem; border-radius: 6px;
    margin-bottom: 0.4rem; font-weight: 600; color: {ISEL_PRIMARY}; font-size: 0.9rem;
}}

.model-help {{
    background: {ISEL_BG}; border-radius: 5px; padding: 0.5rem 0.7rem;
    font-size: 0.82rem; color: {ISEL_GRAY_11}; margin-top: 0.3rem;
    border-left: 2px solid {ISEL_PRIMARY_LT};
}}
.model-warn {{
    background: #fff3cd; border-radius: 5px; padding: 0.5rem 0.7rem;
    font-size: 0.82rem; color: #856404; margin-top: 0.3rem;
    border-left: 2px solid #f0ad4e;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =============================================================================
# 4. REGISTRY DE MODELOS NVIDIA NIM (2026) — com descrições "best for"
# =============================================================================
MODEL_REGISTRY: Dict[str, Dict[str, str]] = {
    "nvidia/nemotron-3-super-120b-a12b": {
        "label": "🥇 NVIDIA Nemotron 3 Super 120B-A12B",
        "best_for": "Flagship NVIDIA. MoE 120B (12B activos), 1M de contexto, raciocínio agentic + RAG + tarefas longas. Excelente como Chefe e para resumos densos.",
    },
    "minimaxai/minimax-m2.7": {
        "label": "💼 MiniMax M2.7 (230B)",
        "best_for": "Especialista em engenharia de software, tarefas agentic longas, entrega profissional de documentos. Compete com Claude em coding. Ótimo como validador rigoroso.",
    },
    "moonshotai/kimi-k2.6": {
        "label": "📚 Moonshot Kimi K2.6",
        "best_for": "Especialista em compreensão de contexto extremamente longo e síntese de documentos. Ideal para resumir PDFs grandes ou para validar coerência global.",
    },
    "deepseek-ai/deepseek-v4-pro": {
        "label": "📐 DeepSeek V4 Pro",
        "best_for": "Top em matemática, código, raciocínio multi-passo. Forte na verificação de cálculos dos exercícios práticos da avaliação.",
    },
    "deepseek-ai/deepseek-v4-flash": {
        "label": "⚡ DeepSeek V4 Flash",
        "best_for": "Versão rápida do V4 Pro. Boa qualidade mas muito mais barato em latência — perfeito para validadores rápidos.",
    },
    "z-ai/glm-5.1": {
        "label": "🛠️ Zhipu GLM-5.1",
        "best_for": "200K contexto, 128K output máximo. Coding e execução agentic prolongada (multi-tool, várias horas). Ótimo para tarefas estruturadas complexas.",
    },
    "google/gemma-4-31b-it": {
        "label": "🌐 Google Gemma 4 31B (IT)",
        "best_for": "Multimodal (texto+imagem+vídeo), multilingue, 256K contexto, Apache 2.0. Bom equilíbrio qualidade/custo. Forte em PT-PT e outras línguas europeias.",
    },
    "openai/gpt-oss-120b": {
        "label": "🧠 OpenAI GPT-OSS 120B",
        "best_for": "Open-weight da OpenAI. Sólido em raciocínio geral e conhecimento amplo. Bom como Chefe alternativo se preferires o estilo da casa.",
    },
    "stepfun-ai/step-3.7-flash": {
        "label": "⚡ StepFun Step-3.7 Flash",
        "best_for": "Inferência muito rápida, qualidade decente. Validador-friendly para ciclos rápidos aprovar/rejeitar.",
    },
    "stepfun-ai/step-3.5-flash": {
        "label": "⚡ StepFun Step-3.5 Flash",
        "best_for": "Versão anterior do Step Flash, ligeiramente mais rápida. Use 3.7 se disponível.",
    },
    "google/gemma-3n-e2b-it": {
        "label": "📱 Google Gemma 3n E2B (IT) — ultra-leve",
        "best_for": "Modelo compacto (2B params efetivos via PLE). Edge/mobile. Use só como validador B se quiseres minimizar custos.",
    },
    "nvidia/llama-nemotron-embed-1b-v2": {
        "label": "⚠️ NVIDIA Nemotron Embed 1B v2 — NÃO USAR",
        "best_for": "❌ ESTE É UM MODELO DE EMBEDDINGS (vetorização para RAG), NÃO de chat. Não consegue gerar resumos nem participar em debates. Não selecionar.",
        "warn": True,
    },
}

CUSTOM_MODEL_SENTINEL = "✏️ Personalizado…"

AGENTS_ORDER = ["Chefe", "Validador A", "Validador B"]
AGENT_ICONS: Dict[str, str] = {"Chefe": "👑", "Validador A": "🅰️", "Validador B": "🅱️"}

# Defaults bem balanceados para 2026
DEFAULT_MODELS: Dict[str, str] = {
    "Chefe":       "nvidia/nemotron-3-super-120b-a12b",
    "Validador A": "minimaxai/minimax-m2.7",
    "Validador B": "deepseek-ai/deepseek-v4-flash",
}
DEFAULT_SUMMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b"

UNANIMITY_TOKEN = "[UNANIMIDADE]"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MAX_CHARS_PER_SUMMARY_CHUNK = 60_000
MAX_CHARS_FOR_EVAL_INPUT    = 120_000
HARD_TRUNCATE_MARGIN        = 200


# =============================================================================
# 5. INTERNACIONALIZAÇÃO (i18n) — UI + output dos LLMs
# =============================================================================
LANGUAGES: Dict[str, Dict[str, str]] = {
    "pt": {"label": "🇵🇹 Português",     "llm_name": "Português Europeu (PT-PT)"},
    "en": {"label": "🇬🇧 English",        "llm_name": "English"},
    "es": {"label": "🇪🇸 Español",        "llm_name": "Español"},
    "fr": {"label": "🇫🇷 Français",       "llm_name": "français"},
    "de": {"label": "🇩🇪 Deutsch",        "llm_name": "Deutsch"},
}

# Etiquetas das 5 secções, traduzidas por idioma — para o LLM usar nos resumos
SECTION_LABELS_BY_LANG: Dict[str, Dict[str, str]] = {
    "pt": {"foco": "🎯 Foco Principal",      "conceitos": "🧠 Conceitos-Chave",        "formulas": "🧮 Fórmulas e Metodologias", "aplicacao": "🏭 Aplicação Prática",   "dica": "🎓 Dica do Catedrático"},
    "en": {"foco": "🎯 Main Focus",          "conceitos": "🧠 Key Concepts",           "formulas": "🧮 Formulas and Methodologies", "aplicacao": "🏭 Practical Application", "dica": "🎓 Professor's Tip"},
    "es": {"foco": "🎯 Enfoque Principal",   "conceitos": "🧠 Conceptos Clave",        "formulas": "🧮 Fórmulas y Metodologías", "aplicacao": "🏭 Aplicación Práctica", "dica": "🎓 Consejo del Catedrático"},
    "fr": {"foco": "🎯 Focus Principal",     "conceitos": "🧠 Concepts Clés",          "formulas": "🧮 Formules et Méthodologies", "aplicacao": "🏭 Application Pratique", "dica": "🎓 Conseil du Professeur"},
    "de": {"foco": "🎯 Hauptfokus",          "conceitos": "🧠 Schlüsselkonzepte",      "formulas": "🧮 Formeln und Methoden",     "aplicacao": "🏭 Praktische Anwendung", "dica": "🎓 Professorentipp"},
}

# Strings da UI por idioma
I18N: Dict[str, Dict[str, str]] = {
    "pt": {
        "app_title": "Análise de Custos",
        "subtitle": "Plataforma de Estudo Interativa · Instituto Superior de Engenharia de Lisboa",
        "language": "Idioma da interface",
        "language_help": "Os resumos e a avaliação serão produzidos NESTE idioma, qualquer que seja a língua dos PDFs.",
        "config": "⚙️ Configurações",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Obrigatória para resumos automáticos e avaliação.",
        "max_rounds": "🔁 Máximo de rondas (avaliação)",
        "summary_model_label": "🧠 Modelo do Catedrático (resumos)",
        "debate_models_label": "🤖 Modelos do debate (avaliação)",
        "model_404_hint": "Erro 404? Muda aqui para um modelo a que a tua conta tenha acesso.",
        "custom_model_input": "Insere o ID exato do modelo NVIDIA NIM",
        "reset_models": "↺ Repor defaults",
        "key_loaded": "🔒 Chave carregada — IA ativa",
        "no_key": "Sem chave — IA inativa.",
        "upload_pdfs": "📁 Carregar PDFs",
        "upload_help": "Cada PDF é automaticamente resumido pelo Catedrático ao ser carregado.",
        "pdfs_loaded": "✅ {n} PDF(s) em memória",
        "total_meta": "📄 {pages} páginas · {chars:,} caracteres no total",
        "ai_section": "🤖 IA Multi-Agente",
        "ai_pill_eval": "🎓 Avaliação Interativa",
        "ai_pill_help": "Tab sempre disponível no painel principal.",
        "db_section": "🗑️ Base de Dados",
        "db_confirm": "Confirmar apagar TUDO",
        "db_confirm_help": "Marca esta caixa para libertar o botão.",
        "db_delete_btn": "🗑️ Apagar Base de Dados de Resumos",
        "db_deleted": "Base de dados apagada.",
        "db_empty": "(sem PDFs carregados)",
        "welcome_title": "👋 Bem-vindo",
        "welcome_body": "Carrega os teus PDFs na barra lateral. A plataforma irá automaticamente:",
        "welcome_b1": "⛏️ Extrair o texto de cada PDF (via PyMuPDF)",
        "welcome_b2": "🧠 Pedir ao **Catedrático** que gere um resumo académico estruturado no idioma escolhido",
        "welcome_b3": "📚 Abrir uma **tab por PDF** com o resumo completo em scroll",
        "welcome_b4": "🎓 Disponibilizar uma **avaliação interativa** com debate multi-agente",
        "tab_eval": "🎓 Avaliação Interativa",
        "eval_title": "🎓 Avaliação Interativa",
        "eval_caption": "Os três agentes debatem em loop circular estrito até que os dois não-autores aprovem unanimemente o teste (ou se atinja o limite de rondas).",
        "eval_select_pdfs": "📚 PDFs a incluir na avaliação",
        "eval_select_q": "Que PDFs queres incluir?",
        "eval_select_all": "✅ Selecionar todos",
        "eval_select_none": "🚫 Limpar seleção",
        "btn_run_eval": "🚀 Iniciar Debate Multi-Agente",
        "btn_redo_eval": "🔄 Refazer Avaliação",
        "btn_clear": "🗑️ Limpar",
        "warn_set_key": "Define a NVIDIA API Key em **⚙️ Configurações**.",
        "warn_pick_pdf": "Seleciona pelo menos um PDF acima.",
        "info_limit": "Limite atual: **{n} rondas** · PDFs selecionados: **{k}**.",
        "info_start_upload": "📁 Começa por carregar PDFs na barra lateral.",
        "debate_in_progress": "🎬 Debate em curso",
        "consensus_in": "Consenso em {n} ronda(s)",
        "limit_reached": "Limite de {n} rondas atingido",
        "final_version": "Versão Final",
        "final_authorship": "Autoria final",
        "download_test": "📥 Descarregar teste em Markdown",
        "debate_history": "🗂️ Histórico do debate ({n} intervenções)",
        "regen_summary": "🔄 Refazer resumo",
        "view_raw": "🔍 Ver texto extraído do PDF (debug)",
        "summary_auto": "🤖 Resumo gerado automaticamente",
        "summary_pending": "📝 Resumo pendente",
        "pages_chars": "📑 <b>{pages}</b> páginas · {chars:,} caracteres extraídos · {badge}",
        "no_summary_yet": "Este PDF ainda não tem resumo. Carrega em **🔄 Refazer resumo** acima.",
        "processing": "📄 A processar **{name}**",
        "extracting": "⛏️ A extrair texto do PDF (PyMuPDF)…",
        "extracted": "📑 {pages} páginas · {chars:,} caracteres extraídos.",
        "empty_pdf_warn": "⚠️ `{name}` — texto vazio (digitalização sem OCR?).",
        "summarizing": "📝 A resumir `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` é grande — dividido em **{n} blocos** para evitar limite de contexto.",
        "chunk_progress": "🧠 Bloco {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ `{name}` resumido com sucesso!",
        "summary_fail": "❌ Falha ao processar `{name}`.",
        "regen_progress": "🔄 A refazer o resumo de **{name}**",
        "regen_done": "✅ Resumo de `{name}` refeito!",
        "regen_fail": "❌ Falha ao refazer resumo.",
        "material_too_big": "📏 Matéria muito extensa ({orig:,} chars). Truncada para {trunc:,} chars.",
        "round_of": "🔄 Ronda {i} de {n} · V{v} (autoria: {a})",
        "approved": "✅ **{v}** aprovou ({tok})",
        "rewrote": "✏️ **{v}** reescreveu — nova V{n}. Próxima ronda: validadores são os outros 2.",
        "consensus_msg": "🎉 Consenso atingido na ronda {i}! V{v} de {a} aprovada por {others}.",
        "no_consensus_msg": "⏱️ Limite de {n} rondas atingido. Versão final: V{v} (autoria de {a}).",
        "chefe_drafting": "👑 **Chefe** a criar V1 do Teste",
        "validator_evaluating": "{icon} **{v}** a avaliar V{n} de **{a}**",
        "elapsed": "decorridos",
    },
    "en": {
        "app_title": "Cost Analysis",
        "subtitle": "Interactive Study Platform · Lisbon School of Engineering (ISEL)",
        "language": "Interface language",
        "language_help": "Summaries and evaluations will be produced in THIS language, regardless of the source PDFs' language.",
        "config": "⚙️ Settings",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Required for automatic summaries and evaluation.",
        "max_rounds": "🔁 Maximum debate rounds",
        "summary_model_label": "🧠 Professor's model (summaries)",
        "debate_models_label": "🤖 Debate models (evaluation)",
        "model_404_hint": "404 error? Pick a model your account can access.",
        "custom_model_input": "Enter the exact NVIDIA NIM model ID",
        "reset_models": "↺ Reset defaults",
        "key_loaded": "🔒 Key loaded — AI active",
        "no_key": "No key — AI disabled.",
        "upload_pdfs": "📁 Upload PDFs",
        "upload_help": "Each PDF is automatically summarised by the Professor on upload.",
        "pdfs_loaded": "✅ {n} PDF(s) in memory",
        "total_meta": "📄 {pages} pages · {chars:,} characters total",
        "ai_section": "🤖 Multi-Agent AI",
        "ai_pill_eval": "🎓 Interactive Evaluation",
        "ai_pill_help": "Tab always available in the main panel.",
        "db_section": "🗑️ Database",
        "db_confirm": "Confirm DELETE ALL",
        "db_confirm_help": "Tick this box to enable the button.",
        "db_delete_btn": "🗑️ Delete summary database",
        "db_deleted": "Database deleted.",
        "db_empty": "(no PDFs loaded)",
        "welcome_title": "👋 Welcome",
        "welcome_body": "Upload your PDFs in the sidebar. The platform will automatically:",
        "welcome_b1": "⛏️ Extract text from each PDF (via PyMuPDF)",
        "welcome_b2": "🧠 Ask the **Professor** to generate a structured academic summary in the chosen language",
        "welcome_b3": "📚 Open one **tab per PDF** with the full summary scrolling",
        "welcome_b4": "🎓 Provide an **interactive evaluation** with multi-agent debate",
        "tab_eval": "🎓 Interactive Evaluation",
        "eval_title": "🎓 Interactive Evaluation",
        "eval_caption": "The three agents debate in a strict circular loop until the two non-authors unanimously approve the test (or the round limit is reached).",
        "eval_select_pdfs": "📚 PDFs to include in the evaluation",
        "eval_select_q": "Which PDFs should be included?",
        "eval_select_all": "✅ Select all",
        "eval_select_none": "🚫 Clear selection",
        "btn_run_eval": "🚀 Start multi-agent debate",
        "btn_redo_eval": "🔄 Redo evaluation",
        "btn_clear": "🗑️ Clear",
        "warn_set_key": "Set the NVIDIA API Key in **⚙️ Settings**.",
        "warn_pick_pdf": "Select at least one PDF above.",
        "info_limit": "Current limit: **{n} rounds** · Selected PDFs: **{k}**.",
        "info_start_upload": "📁 Start by uploading PDFs in the sidebar.",
        "debate_in_progress": "🎬 Debate in progress",
        "consensus_in": "Consensus in {n} round(s)",
        "limit_reached": "Round limit ({n}) reached",
        "final_version": "Final Version",
        "final_authorship": "Final authorship",
        "download_test": "📥 Download test in Markdown",
        "debate_history": "🗂️ Debate history ({n} interventions)",
        "regen_summary": "🔄 Regenerate summary",
        "view_raw": "🔍 View extracted PDF text (debug)",
        "summary_auto": "🤖 Auto-generated summary",
        "summary_pending": "📝 Summary pending",
        "pages_chars": "📑 <b>{pages}</b> pages · {chars:,} characters extracted · {badge}",
        "no_summary_yet": "This PDF has no summary yet. Click **🔄 Regenerate summary** above.",
        "processing": "📄 Processing **{name}**",
        "extracting": "⛏️ Extracting PDF text (PyMuPDF)…",
        "extracted": "📑 {pages} pages · {chars:,} characters extracted.",
        "empty_pdf_warn": "⚠️ `{name}` — empty text (scanned without OCR?).",
        "summarizing": "📝 Summarising `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` is large — split into **{n} chunks** to avoid context overflow.",
        "chunk_progress": "🧠 Chunk {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ `{name}` summarised successfully!",
        "summary_fail": "❌ Failed to process `{name}`.",
        "regen_progress": "🔄 Regenerating summary of **{name}**",
        "regen_done": "✅ Summary of `{name}` regenerated!",
        "regen_fail": "❌ Failed to regenerate summary.",
        "material_too_big": "📏 Material very large ({orig:,} chars). Truncated to {trunc:,} chars.",
        "round_of": "🔄 Round {i} of {n} · V{v} (author: {a})",
        "approved": "✅ **{v}** approved ({tok})",
        "rewrote": "✏️ **{v}** rewrote — new V{n}. Next round: validators are the other 2.",
        "consensus_msg": "🎉 Consensus reached in round {i}! V{v} by {a} approved by {others}.",
        "no_consensus_msg": "⏱️ Round limit ({n}) reached. Final version: V{v} (by {a}).",
        "chefe_drafting": "👑 **Chefe** drafting V1 of the test",
        "validator_evaluating": "{icon} **{v}** evaluating V{n} by **{a}**",
        "elapsed": "elapsed",
    },
    "es": {
        "app_title": "Análisis de Costes",
        "subtitle": "Plataforma de Estudio Interactiva · ISEL Lisboa",
        "language": "Idioma de la interfaz",
        "language_help": "Los resúmenes y la evaluación se producirán en ESTE idioma, sea cual sea el idioma de los PDFs.",
        "config": "⚙️ Configuración",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Necesaria para resúmenes automáticos y evaluación.",
        "max_rounds": "🔁 Máximo de rondas (evaluación)",
        "summary_model_label": "🧠 Modelo del Catedrático (resúmenes)",
        "debate_models_label": "🤖 Modelos del debate (evaluación)",
        "model_404_hint": "¿Error 404? Cambia aquí por un modelo al que tu cuenta tenga acceso.",
        "custom_model_input": "Introduce el ID exacto del modelo NVIDIA NIM",
        "reset_models": "↺ Restaurar por defecto",
        "key_loaded": "🔒 Clave cargada — IA activa",
        "no_key": "Sin clave — IA inactiva.",
        "upload_pdfs": "📁 Cargar PDFs",
        "upload_help": "Cada PDF se resume automáticamente al cargarse.",
        "pdfs_loaded": "✅ {n} PDF(s) en memoria",
        "total_meta": "📄 {pages} páginas · {chars:,} caracteres en total",
        "ai_section": "🤖 IA Multi-Agente",
        "ai_pill_eval": "🎓 Evaluación Interactiva",
        "ai_pill_help": "Pestaña siempre disponible en el panel principal.",
        "db_section": "🗑️ Base de Datos",
        "db_confirm": "Confirmar BORRAR TODO",
        "db_confirm_help": "Marca esta casilla para activar el botón.",
        "db_delete_btn": "🗑️ Borrar base de datos de resúmenes",
        "db_deleted": "Base de datos borrada.",
        "db_empty": "(sin PDFs cargados)",
        "welcome_title": "👋 Bienvenido",
        "welcome_body": "Carga tus PDFs en la barra lateral. La plataforma automáticamente:",
        "welcome_b1": "⛏️ Extraerá el texto de cada PDF (vía PyMuPDF)",
        "welcome_b2": "🧠 Pedirá al **Catedrático** que genere un resumen académico estructurado en el idioma elegido",
        "welcome_b3": "📚 Abrirá una **pestaña por PDF** con el resumen completo en scroll",
        "welcome_b4": "🎓 Ofrecerá una **evaluación interactiva** con debate multi-agente",
        "tab_eval": "🎓 Evaluación Interactiva",
        "eval_title": "🎓 Evaluación Interactiva",
        "eval_caption": "Los tres agentes debaten en bucle circular estricto hasta que los dos no-autores aprueben unánimemente el test (o se alcance el límite de rondas).",
        "eval_select_pdfs": "📚 PDFs a incluir en la evaluación",
        "eval_select_q": "¿Qué PDFs incluir?",
        "eval_select_all": "✅ Seleccionar todos",
        "eval_select_none": "🚫 Limpiar selección",
        "btn_run_eval": "🚀 Iniciar debate multi-agente",
        "btn_redo_eval": "🔄 Rehacer evaluación",
        "btn_clear": "🗑️ Limpiar",
        "warn_set_key": "Configura la NVIDIA API Key en **⚙️ Configuración**.",
        "warn_pick_pdf": "Selecciona al menos un PDF arriba.",
        "info_limit": "Límite actual: **{n} rondas** · PDFs seleccionados: **{k}**.",
        "info_start_upload": "📁 Empieza cargando PDFs en la barra lateral.",
        "debate_in_progress": "🎬 Debate en curso",
        "consensus_in": "Consenso en {n} ronda(s)",
        "limit_reached": "Límite de {n} rondas alcanzado",
        "final_version": "Versión Final",
        "final_authorship": "Autoría final",
        "download_test": "📥 Descargar test en Markdown",
        "debate_history": "🗂️ Historial del debate ({n} intervenciones)",
        "regen_summary": "🔄 Rehacer resumen",
        "view_raw": "🔍 Ver texto extraído del PDF (debug)",
        "summary_auto": "🤖 Resumen generado automáticamente",
        "summary_pending": "📝 Resumen pendiente",
        "pages_chars": "📑 <b>{pages}</b> páginas · {chars:,} caracteres extraídos · {badge}",
        "no_summary_yet": "Este PDF aún no tiene resumen. Pulsa **🔄 Rehacer resumen** arriba.",
        "processing": "📄 Procesando **{name}**",
        "extracting": "⛏️ Extrayendo texto del PDF (PyMuPDF)…",
        "extracted": "📑 {pages} páginas · {chars:,} caracteres extraídos.",
        "empty_pdf_warn": "⚠️ `{name}` — texto vacío (¿escaneado sin OCR?).",
        "summarizing": "📝 Resumiendo `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` es grande — dividido en **{n} bloques** para evitar el límite de contexto.",
        "chunk_progress": "🧠 Bloque {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ ¡`{name}` resumido con éxito!",
        "summary_fail": "❌ Fallo al procesar `{name}`.",
        "regen_progress": "🔄 Rehaciendo el resumen de **{name}**",
        "regen_done": "✅ ¡Resumen de `{name}` rehecho!",
        "regen_fail": "❌ Fallo al rehacer el resumen.",
        "material_too_big": "📏 Material muy extenso ({orig:,} chars). Truncado a {trunc:,} chars.",
        "round_of": "🔄 Ronda {i} de {n} · V{v} (autor: {a})",
        "approved": "✅ **{v}** aprobó ({tok})",
        "rewrote": "✏️ **{v}** reescribió — nueva V{n}. Próxima ronda: validadores son los otros 2.",
        "consensus_msg": "🎉 ¡Consenso alcanzado en la ronda {i}! V{v} de {a} aprobada por {others}.",
        "no_consensus_msg": "⏱️ Límite de {n} rondas alcanzado. Versión final: V{v} (de {a}).",
        "chefe_drafting": "👑 **Chefe** redactando V1 del test",
        "validator_evaluating": "{icon} **{v}** evaluando V{n} de **{a}**",
        "elapsed": "transcurridos",
    },
    "fr": {
        "app_title": "Analyse de Coûts",
        "subtitle": "Plateforme d'Étude Interactive · ISEL Lisbonne",
        "language": "Langue de l'interface",
        "language_help": "Les résumés et l'évaluation seront produits dans CETTE langue, quelle que soit la langue des PDFs.",
        "config": "⚙️ Paramètres",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Requise pour les résumés automatiques et l'évaluation.",
        "max_rounds": "🔁 Tours maximum (évaluation)",
        "summary_model_label": "🧠 Modèle du Professeur (résumés)",
        "debate_models_label": "🤖 Modèles du débat (évaluation)",
        "model_404_hint": "Erreur 404 ? Choisis un modèle accessible à ton compte.",
        "custom_model_input": "Saisis l'ID exact du modèle NVIDIA NIM",
        "reset_models": "↺ Réinitialiser",
        "key_loaded": "🔒 Clé chargée — IA active",
        "no_key": "Pas de clé — IA inactive.",
        "upload_pdfs": "📁 Charger des PDFs",
        "upload_help": "Chaque PDF est automatiquement résumé par le Professeur au chargement.",
        "pdfs_loaded": "✅ {n} PDF(s) en mémoire",
        "total_meta": "📄 {pages} pages · {chars:,} caractères au total",
        "ai_section": "🤖 IA Multi-Agent",
        "ai_pill_eval": "🎓 Évaluation Interactive",
        "ai_pill_help": "Onglet toujours disponible.",
        "db_section": "🗑️ Base de données",
        "db_confirm": "Confirmer TOUT EFFACER",
        "db_confirm_help": "Coche pour activer le bouton.",
        "db_delete_btn": "🗑️ Effacer la base de résumés",
        "db_deleted": "Base effacée.",
        "db_empty": "(aucun PDF chargé)",
        "welcome_title": "👋 Bienvenue",
        "welcome_body": "Charge tes PDFs dans la barre latérale. La plateforme va automatiquement :",
        "welcome_b1": "⛏️ Extraire le texte de chaque PDF (via PyMuPDF)",
        "welcome_b2": "🧠 Demander au **Professeur** un résumé académique structuré dans la langue choisie",
        "welcome_b3": "📚 Ouvrir un **onglet par PDF** avec le résumé complet en scroll",
        "welcome_b4": "🎓 Fournir une **évaluation interactive** avec débat multi-agent",
        "tab_eval": "🎓 Évaluation Interactive",
        "eval_title": "🎓 Évaluation Interactive",
        "eval_caption": "Les trois agents débattent en boucle circulaire stricte jusqu'à approbation unanime des deux non-auteurs (ou atteinte de la limite).",
        "eval_select_pdfs": "📚 PDFs à inclure dans l'évaluation",
        "eval_select_q": "Quels PDFs inclure ?",
        "eval_select_all": "✅ Tout sélectionner",
        "eval_select_none": "🚫 Effacer la sélection",
        "btn_run_eval": "🚀 Lancer le débat multi-agent",
        "btn_redo_eval": "🔄 Refaire l'évaluation",
        "btn_clear": "🗑️ Effacer",
        "warn_set_key": "Configure la NVIDIA API Key dans **⚙️ Paramètres**.",
        "warn_pick_pdf": "Sélectionne au moins un PDF ci-dessus.",
        "info_limit": "Limite actuelle : **{n} tours** · PDFs sélectionnés : **{k}**.",
        "info_start_upload": "📁 Commence par charger des PDFs.",
        "debate_in_progress": "🎬 Débat en cours",
        "consensus_in": "Consensus en {n} tour(s)",
        "limit_reached": "Limite de {n} tours atteinte",
        "final_version": "Version Finale",
        "final_authorship": "Autorité finale",
        "download_test": "📥 Télécharger le test en Markdown",
        "debate_history": "🗂️ Historique du débat ({n} interventions)",
        "regen_summary": "🔄 Refaire le résumé",
        "view_raw": "🔍 Voir le texte extrait (debug)",
        "summary_auto": "🤖 Résumé généré automatiquement",
        "summary_pending": "📝 Résumé en attente",
        "pages_chars": "📑 <b>{pages}</b> pages · {chars:,} caractères extraits · {badge}",
        "no_summary_yet": "Ce PDF n'a pas encore de résumé. Clique sur **🔄 Refaire le résumé**.",
        "processing": "📄 Traitement de **{name}**",
        "extracting": "⛏️ Extraction du texte du PDF (PyMuPDF)…",
        "extracted": "📑 {pages} pages · {chars:,} caractères extraits.",
        "empty_pdf_warn": "⚠️ `{name}` — texte vide (scan sans OCR ?).",
        "summarizing": "📝 Résumé de `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` est grand — divisé en **{n} blocs**.",
        "chunk_progress": "🧠 Bloc {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ `{name}` résumé avec succès !",
        "summary_fail": "❌ Échec du traitement de `{name}`.",
        "regen_progress": "🔄 Régénération du résumé de **{name}**",
        "regen_done": "✅ Résumé de `{name}` régénéré !",
        "regen_fail": "❌ Échec de la régénération.",
        "material_too_big": "📏 Matériel très volumineux ({orig:,} chars). Tronqué à {trunc:,} chars.",
        "round_of": "🔄 Tour {i} sur {n} · V{v} (auteur : {a})",
        "approved": "✅ **{v}** a approuvé ({tok})",
        "rewrote": "✏️ **{v}** a réécrit — nouvelle V{n}. Tour suivant : les 2 autres valident.",
        "consensus_msg": "🎉 Consensus au tour {i} ! V{v} de {a} approuvée par {others}.",
        "no_consensus_msg": "⏱️ Limite de {n} tours atteinte. Version finale : V{v} (de {a}).",
        "chefe_drafting": "👑 **Chefe** rédige la V1 du test",
        "validator_evaluating": "{icon} **{v}** évalue la V{n} de **{a}**",
        "elapsed": "écoulées",
    },
    "de": {
        "app_title": "Kostenanalyse",
        "subtitle": "Interaktive Lernplattform · ISEL Lissabon",
        "language": "Oberflächensprache",
        "language_help": "Zusammenfassungen und Bewertung werden IN DIESER Sprache erzeugt, unabhängig von der PDF-Sprache.",
        "config": "⚙️ Einstellungen",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Erforderlich für automatische Zusammenfassungen und Bewertung.",
        "max_rounds": "🔁 Maximale Debattenrunden",
        "summary_model_label": "🧠 Professor-Modell (Zusammenfassungen)",
        "debate_models_label": "🤖 Debattenmodelle (Bewertung)",
        "model_404_hint": "404-Fehler? Wähle ein Modell, auf das dein Konto Zugriff hat.",
        "custom_model_input": "Gib die exakte NVIDIA NIM Modell-ID ein",
        "reset_models": "↺ Standards wiederherstellen",
        "key_loaded": "🔒 Schlüssel geladen — KI aktiv",
        "no_key": "Kein Schlüssel — KI inaktiv.",
        "upload_pdfs": "📁 PDFs hochladen",
        "upload_help": "Jedes PDF wird beim Hochladen automatisch zusammengefasst.",
        "pdfs_loaded": "✅ {n} PDF(s) im Speicher",
        "total_meta": "📄 {pages} Seiten · {chars:,} Zeichen insgesamt",
        "ai_section": "🤖 Multi-Agenten-KI",
        "ai_pill_eval": "🎓 Interaktive Bewertung",
        "ai_pill_help": "Tab immer verfügbar.",
        "db_section": "🗑️ Datenbank",
        "db_confirm": "ALLES LÖSCHEN bestätigen",
        "db_confirm_help": "Aktivieren, um den Button freizugeben.",
        "db_delete_btn": "🗑️ Zusammenfassungs-Datenbank löschen",
        "db_deleted": "Datenbank gelöscht.",
        "db_empty": "(keine PDFs geladen)",
        "welcome_title": "👋 Willkommen",
        "welcome_body": "Lade deine PDFs in der Seitenleiste. Die Plattform wird automatisch:",
        "welcome_b1": "⛏️ Text aus jedem PDF extrahieren (via PyMuPDF)",
        "welcome_b2": "🧠 Den **Professor** bitten, eine strukturierte akademische Zusammenfassung in der gewählten Sprache zu erstellen",
        "welcome_b3": "📚 Pro PDF einen **Tab** mit voller Zusammenfassung öffnen",
        "welcome_b4": "🎓 Eine **interaktive Bewertung** mit Multi-Agenten-Debatte bereitstellen",
        "tab_eval": "🎓 Interaktive Bewertung",
        "eval_title": "🎓 Interaktive Bewertung",
        "eval_caption": "Die drei Agenten debattieren in strenger Zirkelschleife, bis die beiden Nicht-Autoren einstimmig zustimmen (oder das Limit erreicht ist).",
        "eval_select_pdfs": "📚 PDFs für die Bewertung",
        "eval_select_q": "Welche PDFs einbeziehen?",
        "eval_select_all": "✅ Alle auswählen",
        "eval_select_none": "🚫 Auswahl löschen",
        "btn_run_eval": "🚀 Multi-Agenten-Debatte starten",
        "btn_redo_eval": "🔄 Bewertung wiederholen",
        "btn_clear": "🗑️ Leeren",
        "warn_set_key": "Setze die NVIDIA API Key in **⚙️ Einstellungen**.",
        "warn_pick_pdf": "Wähle mindestens ein PDF oben aus.",
        "info_limit": "Aktuelles Limit: **{n} Runden** · Ausgewählte PDFs: **{k}**.",
        "info_start_upload": "📁 Beginne mit dem Hochladen von PDFs in der Seitenleiste.",
        "debate_in_progress": "🎬 Debatte läuft",
        "consensus_in": "Konsens in {n} Runde(n)",
        "limit_reached": "Rundenlimit ({n}) erreicht",
        "final_version": "Endversion",
        "final_authorship": "Endgültige Autorenschaft",
        "download_test": "📥 Test als Markdown herunterladen",
        "debate_history": "🗂️ Debattenverlauf ({n} Beiträge)",
        "regen_summary": "🔄 Zusammenfassung neu erzeugen",
        "view_raw": "🔍 Extrahierten PDF-Text ansehen (debug)",
        "summary_auto": "🤖 Automatisch erzeugte Zusammenfassung",
        "summary_pending": "📝 Zusammenfassung ausstehend",
        "pages_chars": "📑 <b>{pages}</b> Seiten · {chars:,} Zeichen extrahiert · {badge}",
        "no_summary_yet": "Dieses PDF hat noch keine Zusammenfassung. Klicke oben auf **🔄 Zusammenfassung neu erzeugen**.",
        "processing": "📄 Verarbeite **{name}**",
        "extracting": "⛏️ Extrahiere PDF-Text (PyMuPDF)…",
        "extracted": "📑 {pages} Seiten · {chars:,} Zeichen extrahiert.",
        "empty_pdf_warn": "⚠️ `{name}` — leerer Text (Scan ohne OCR?).",
        "summarizing": "📝 Fasse `{name}` zusammen ({chars:,} Zeichen)…",
        "big_pdf_split": "📚 `{name}` ist groß — in **{n} Blöcke** geteilt.",
        "chunk_progress": "🧠 Block {i}/{n} ({chars:,} Zeichen)",
        "summary_done": "✅ `{name}` erfolgreich zusammengefasst!",
        "summary_fail": "❌ Verarbeitung von `{name}` fehlgeschlagen.",
        "regen_progress": "🔄 Erzeuge Zusammenfassung von **{name}** neu",
        "regen_done": "✅ Zusammenfassung von `{name}` neu erzeugt!",
        "regen_fail": "❌ Neuerzeugung fehlgeschlagen.",
        "material_too_big": "📏 Material sehr umfangreich ({orig:,} Zeichen). Auf {trunc:,} Zeichen gekürzt.",
        "round_of": "🔄 Runde {i} von {n} · V{v} (Autor: {a})",
        "approved": "✅ **{v}** zugestimmt ({tok})",
        "rewrote": "✏️ **{v}** überschrieben — neue V{n}. Nächste Runde: die anderen 2 validieren.",
        "consensus_msg": "🎉 Konsens in Runde {i} erreicht! V{v} von {a} zugestimmt durch {others}.",
        "no_consensus_msg": "⏱️ Rundenlimit ({n}) erreicht. Endversion: V{v} (von {a}).",
        "chefe_drafting": "👑 **Chefe** erstellt V1 des Tests",
        "validator_evaluating": "{icon} **{v}** bewertet V{n} von **{a}**",
        "elapsed": "vergangen",
    },
}


def t(key: str, **kwargs) -> str:
    """Tradutor: devolve a string i18n no idioma atual, formatada com kwargs."""
    lang = st.session_state.get("ui_language", "pt")
    val = I18N.get(lang, I18N["pt"]).get(key, I18N["pt"].get(key, key))
    try:
        return val.format(**kwargs) if kwargs else val
    except Exception:
        return val


def language_instruction(lang_code: str) -> str:
    """
    Bloco system que FORÇA o LLM a produzir output no idioma escolhido,
    independentemente da língua do material fonte.
    """
    lang_name = LANGUAGES.get(lang_code, LANGUAGES["pt"])["llm_name"]
    return (
        f"### LANGUAGE OVERRIDE\n"
        f"You MUST produce ALL output in **{lang_name}**, regardless of "
        f"the language of the source material or any language mentioned in the user prompt. "
        f"Do not switch languages mid-response. If the source PDF is in another language, "
        f"translate the content into {lang_name} while preserving technical terminology.\n"
    )


def section_labels_block(lang_code: str) -> str:
    """Etiquetas das 5 secções para o LLM, no idioma escolhido."""
    sl = SECTION_LABELS_BY_LANG.get(lang_code, SECTION_LABELS_BY_LANG["pt"])
    return (
        f"### SECTION HEADERS (use these EXACT labels in {LANGUAGES[lang_code]['llm_name']}):\n"
        f"- {sl['foco']}\n"
        f"- {sl['conceitos']}\n"
        f"- {sl['formulas']}\n"
        f"- {sl['aplicacao']}\n"
        f"- {sl['dica']}\n"
    )


# =============================================================================
# 6. LOADING — Mensagens divertidas por idioma + GIFs opcionais
# =============================================================================
FUNNY_LOADING_MESSAGES_BY_LANG: Dict[str, List[str]] = {
    "pt": [
        "🐱 Os agentes a tomar café antes do debate académico…",
        "🦉 A coruja-validadora a verificar fórmulas duas vezes…",
        "🦫 Os castores a construir o resumo, parágrafo a parágrafo…",
        "🐢 Devagar, mas com rigor de catedrático…",
        "🐶 Agentes a ladrar uns aos outros sobre custos fixos…",
        "🐧 Pinguins em reunião departamental — temperatura ideal!",
        "🦊 A raposa-A detetou uma fórmula suspeita na V1…",
        "🐼 Pandas a folhear notas. Devagar, mas certo.",
        "🦘 A saltar entre capítulos à procura do resumo perfeito…",
        "🐙 8 braços a escrever Markdown ao mesmo tempo…",
        "🦦 As lontras a polir as definições com paciência…",
        "🦝 O guaxinim revisor encontrou outra contradição…",
    ],
    "en": [
        "🐱 The agents are sipping coffee before the academic debate…",
        "🦉 The validator owl is double-checking formulas…",
        "🦫 Beavers are building the summary, paragraph by paragraph…",
        "🐢 Slow, but with professorial rigour…",
        "🐶 Agents barking at each other about fixed costs…",
        "🐧 Penguins in a departmental meeting — perfect room temperature!",
        "🦊 Fox-A spotted a suspicious formula in V1…",
        "🐼 Pandas flipping through notes. Slowly, surely.",
        "🦘 Hopping between chapters in search of the perfect summary…",
        "🐙 Eight arms typing Markdown simultaneously…",
        "🦦 Otters polishing the definitions patiently…",
        "🦝 The raccoon reviewer found another contradiction…",
    ],
    "es": [
        "🐱 Los agentes tomando café antes del debate académico…",
        "🦉 La lechuza-validadora verificando fórmulas dos veces…",
        "🦫 Los castores construyendo el resumen, párrafo a párrafo…",
        "🐢 Despacio, pero con rigor de catedrático…",
        "🐶 Agentes ladrando sobre costes fijos…",
        "🐧 Pingüinos en reunión departamental — ¡temperatura ideal!",
        "🦊 El zorro-A detectó una fórmula sospechosa en la V1…",
        "🐼 Pandas hojeando apuntes. Lento pero seguro.",
        "🦘 Saltando entre capítulos en busca del resumen perfecto…",
        "🐙 8 brazos escribiendo Markdown a la vez…",
    ],
    "fr": [
        "🐱 Les agents prennent un café avant le débat académique…",
        "🦉 La chouette-validatrice vérifie les formules deux fois…",
        "🦫 Les castors construisent le résumé, paragraphe par paragraphe…",
        "🐢 Lentement, mais avec rigueur de professeur…",
        "🐶 Agents qui aboient sur les coûts fixes…",
        "🐧 Pingouins en réunion départementale — température idéale !",
        "🦊 Le renard-A a repéré une formule suspecte dans V1…",
        "🐼 Pandas qui feuillètent les notes. Lentement mais sûrement.",
        "🦘 Sauts entre chapitres à la recherche du résumé parfait…",
        "🐙 8 bras qui tapent du Markdown en même temps…",
    ],
    "de": [
        "🐱 Die Agenten trinken Kaffee vor der akademischen Debatte…",
        "🦉 Die Validator-Eule prüft die Formeln zweimal…",
        "🦫 Die Biber bauen die Zusammenfassung, Absatz für Absatz…",
        "🐢 Langsam, aber mit professoraler Sorgfalt…",
        "🐶 Agenten bellen sich über Fixkosten an…",
        "🐧 Pinguine in der Abteilungssitzung — perfekte Temperatur!",
        "🦊 Fuchs-A hat eine verdächtige Formel in V1 entdeckt…",
        "🐼 Pandas blättern durch Notizen. Langsam, aber sicher.",
        "🦘 Springt zwischen Kapiteln auf der Suche nach der perfekten Zusammenfassung…",
        "🐙 Acht Arme tippen gleichzeitig Markdown…",
    ],
}

LOADING_EMOJIS = ["🧠", "📚", "⚙️", "🔬", "📊", "🎓", "💡", "🔍", "📝", "🏛️"]

# GIFs opcionais — preenche com URLs estáveis (Giphy/Tenor) se quiseres
# enriquecer o loading visual. Lista vazia → só emoji animado por CSS.
# Exemplos (verifica antes de usar):
#   "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif"
LOADING_GIF_URLS: List[str] = []


def random_fun_message(lang_code: str) -> str:
    msgs = FUNNY_LOADING_MESSAGES_BY_LANG.get(lang_code, FUNNY_LOADING_MESSAGES_BY_LANG["pt"])
    return random.choice(msgs)


# =============================================================================
# 7. LoadingAnimator — UI dinâmica durante streaming
# =============================================================================
class LoadingAnimator:
    """
    Anima o loading num `st.container`/`st.status`:
      • mensagem divertida que troca a cada 15s
      • emoji grande animado por CSS (bounce + glow)
      • GIF opcional que troca a cada 30s
      • contador de tempo decorrido
      • placeholder separado para o streaming text do LLM

    Usado dentro do callback de streaming — cada chunk chama .update().
    """
    MSG_ROTATE_SECONDS = 15.0
    GIF_ROTATE_SECONDS = 30.0

    def __init__(self, container, lang_code: str, total_chunks: Optional[int] = None):
        self.container = container
        self.lang_code = lang_code
        self.total_chunks = total_chunks
        self.start_time = time.time()
        self.last_msg_change = 0.0
        self.last_gif_change = 0.0
        self.last_render = 0.0
        self.current_msg = random_fun_message(lang_code)
        self.current_emoji = random.choice(LOADING_EMOJIS)
        self.current_gif_idx = 0
        # Placeholders
        self.animator_slot = container.empty()
        self.text_slot = container.empty()
        self._render(current_text="")

    def update(self, current_text: str = "", force: bool = False) -> None:
        """Chamado dentro do loop de streaming. Throttled a 4 fps."""
        now = time.time()
        # Throttle UI updates (chunks chegam muito rápido)
        if not force and now - self.last_render < 0.25:
            return
        self.last_render = now

        elapsed = now - self.start_time

        # Roda a mensagem a cada 15s
        if elapsed - self.last_msg_change >= self.MSG_ROTATE_SECONDS:
            self.current_msg = random_fun_message(self.lang_code)
            self.current_emoji = random.choice(LOADING_EMOJIS)
            self.last_msg_change = elapsed

        # Roda o GIF a cada 30s
        if LOADING_GIF_URLS and elapsed - self.last_gif_change >= self.GIF_ROTATE_SECONDS:
            self.current_gif_idx = (self.current_gif_idx + 1) % len(LOADING_GIF_URLS)
            self.last_gif_change = elapsed

        self._render(current_text)

    def _render(self, current_text: str) -> None:
        elapsed = int(time.time() - self.start_time)
        chars_out = len(current_text)
        elapsed_word = t("elapsed")

        # Barra de progresso baseada em tempo (visual; aprox 60s = "full")
        progress_pct = min(100, int((elapsed / 60.0) * 100))

        html_parts = [
            f"<div class='loading-fun'>",
            f"  <span class='big-emoji'>{self.current_emoji}</span>",
            f"  <div class='body'>",
            f"    <div class='msg'>{self.current_msg}</div>",
            f"    <div class='meta'>⏱ {elapsed}s {elapsed_word} · 📝 {chars_out:,} chars</div>",
            f"    <div class='progress-bar'><div class='progress-fill' style='width: {progress_pct}%'></div></div>",
            f"  </div>",
            f"</div>",
        ]
        self.animator_slot.markdown("".join(html_parts), unsafe_allow_html=True)

        if LOADING_GIF_URLS:
            try:
                self.animator_slot.image(LOADING_GIF_URLS[self.current_gif_idx], width=240)
            except Exception:
                pass  # graceful degradation

        # Streaming text (últimos 1500 chars)
        if current_text:
            tail = current_text[-1500:]
            self.text_slot.code(tail + "▌", language="markdown")

    def clear(self) -> None:
        self.animator_slot.empty()
        self.text_slot.empty()


# =============================================================================
# 8. EXTRAÇÃO E CHUNKING DE PDFs
# =============================================================================
def extract_pdf_text(pdf_bytes: bytes) -> Dict[str, object]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        parts: List[str] = []
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            parts.append(f"\n--- [Página {page_num}] ---\n{page_text.strip()}")
        full_text = "\n".join(parts).strip()
        return {"text": full_text, "pages": len(doc), "chars": len(full_text)}
    finally:
        doc.close()


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_SUMMARY_CHUNK) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    paragraphs = text.split("\n\n")
    current = ""
    for p in paragraphs:
        if len(p) > max_chars:
            if current.strip():
                chunks.append(current.strip()); current = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i:i + max_chars])
            continue
        if len(current) + len(p) + 2 <= max_chars:
            current = (current + "\n\n" + p) if current else p
        else:
            if current.strip():
                chunks.append(current.strip())
            current = p
    if current.strip():
        chunks.append(current.strip())
    return chunks


def safe_truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - HARD_TRUNCATE_MARGIN] + "\n\n[... truncated by context limit ...]"


# =============================================================================
# 9. PROMPT OFICIAL DO CATEDRÁTICO (resumos)
# =============================================================================
# Texto entre [INÍCIO/FIM TEXTO PROVIDENCIADO] = fornecido pelo utilizador.
# A continuação foi completada porque o original estava truncado.

PROMPT_RESUMO_TEMPLATE = """Atua como um Professor Catedrático e Coordenador de Mestrado com mais de 20 anos de experiência académica e pedagógica. A tua missão é transformar o material de estudo fornecido num Resumo Académico de Alto Nível, ideal para estudantes de pós-graduação que necessitam de profundidade, rigor técnico e clareza conceptual para preparação de exames.

Adota um tom pedagógico que seja simultaneamente claro, conciso, objetivo e profundamente explicativo. Não te limites a listar definições superficiais; vai ao pormenor, explica o "porquê" e o "como" dos mecanismos e teorias.

Garante que a estrutura do resumo respeita os seguintes critérios obrigatórios:

1. ESTRUTURA DOS CAPÍTULOS / BLOCOS TEMÁTICOS:
Para cada tema ou capítulo identificado no texto, cria uma secção estruturada exatamente com as seguintes marcações em Markdown:
   * **🎯 Foco Principal:** Uma frase cirúrgica e concisa que resuma o objetivo central ou a utilidade estratégica do capítulo.
   * **🧠 Conceitos-Chave:** Explicações detalhadas, aprofundadas e pormenorizadas dos termos técnicos e teorias fundamentais. Usa sub-tópicos se necessário para dissecar sub-conceitos.
   * **🧮 Fórmulas e Metodologias (se aplicável):** Apresenta todas as equações matemáticas, deduções ou frameworks
# === FIM DO TEXTO PROVIDENCIADO PELO UTILIZADOR ===
# === CONTINUAÇÃO COERENTE — substitui quando tiveres o prompt completo ===
 relevantes em LaTeX (`$...$` inline e `$$...$$` em display). Acompanha cada fórmula de uma explicação sucinta das variáveis e do contexto em que se aplica.
   * **🏭 Aplicação Prática:** Um cenário concreto (empresa industrial, decisão de gestão, contexto fabril) que mostre como o conceito é usado no mundo real.
   * **🎓 Dica do Catedrático:** Uma pista de exame, um erro comum a evitar, ou uma ligação a outro conceito da matéria. Curto e perspicaz.

2. REGRAS DE FORMATAÇÃO:
   - Cabeçalhos `####` para o título de cada capítulo.
   - Markdown limpo. Sem preâmbulos, sem despedidas, sem meta-comentários.
   - Se o texto for um fragmento, resume APENAS o que está presente — não inventes conteúdo.

NOTA: As etiquetas das 5 secções acima devem ser usadas TRADUZIDAS para o idioma indicado no system prompt (ver SECTION HEADERS).

---

MATERIAL DE ESTUDO A RESUMIR:

{material}
"""


# =============================================================================
# 10. PROMPTS — Avaliação
# =============================================================================
EVAL_INITIAL_SYSTEM = """És o **Chefe** — Professor Catedrático de Análise de Custos do ISEL.
A tua tarefa: criar um Teste de Revisão completo sobre a matéria fornecida.

ESTRUTURA OBRIGATÓRIA:

## Parte I — Escolha Múltipla (10 questões)
Para cada questão:
- Enunciado claro, sem ambiguidade.
- 4 opções rotuladas a), b), c), d).
- Identifica a opção correta com **"Resposta: x)"**.
- Justificação curta (1–2 frases).

## Parte II — Exercícios Práticos (2 exercícios)
- Enunciado realista (empresa industrial fictícia, dados quantitativos coerentes).
- 3 a 5 alíneas com complexidade crescente.
- Resolução passo-a-passo com cálculos visíveis.
- Resultado final destacado.

REGRAS:
- Cobre TRANSVERSALMENTE toda a matéria.
- Valores realistas; cálculos que fechem exatamente.
- LaTeX `$...$` / `$$...$$` para fórmulas.
- Markdown limpo, sem preâmbulos.
"""

EVAL_VALIDATION_SYSTEM = """És **{validator}**, revisor académico rigoroso de Análise de Custos (ISEL).

⚠️ REGRA DE OURO: avalias o teste produzido por **{author}**. NUNCA avalies a tua própria autoria.

Verifica rapidamente:
1. Cálculos certos.
2. Cada escolha múltipla tem UMA resposta única e correta.
3. Sem ambiguidades.
4. Cobertura razoável, sem invenções.

DECISÃO BINÁRIA — sê EXTREMAMENTE conciso:

▶ APROVAR (sem alterações):
   Responde EXATAMENTE com a linha: {token}
   Seguido de NO MÁXIMO 1 frase. NADA MAIS.

▶ REESCREVER (só se houver falha REAL):
   - NÃO uses {token}.
   - Devolve o teste COMPLETO reescrito em Markdown (Parte I + Parte II + soluções).
   - Apenas o teste, sem comentários.

Sê implacável só com erros que importam — preferências estilísticas NÃO justificam reescrita.
"""


# =============================================================================
# 11. API NVIDIA
# =============================================================================
def get_nvidia_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def stream_call_animated(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    container,
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    lang_code: str = "pt",
) -> str:
    """
    Chama o modelo em streaming e usa LoadingAnimator para mostrar mensagens
    divertidas + GIFs + contador + streaming text em paralelo.
    """
    animator = LoadingAnimator(container, lang_code=lang_code)
    accumulated = ""
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (IndexError, AttributeError):
                delta = None
            if delta:
                accumulated += delta
                animator.update(current_text=accumulated)
        animator.update(current_text=accumulated, force=True)
    finally:
        animator.clear()
    return accumulated.strip()


def friendly_api_error(err: Exception) -> str:
    msg = str(err)
    lower = msg.lower()
    if "404" in msg or "not found" in lower:
        return (
            "❌ **Modelo não encontrado na tua conta NVIDIA.**\n\n"
            "Vai à sidebar → **⚙️ Configurações → 🤖 Modelos** e escolhe outro do "
            "dropdown. Cuidado: nem todas as contas têm acesso a todos os modelos.\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "401" in msg or "unauthorized" in lower:
        return (
            "❌ **Chave NVIDIA inválida ou expirada.** Verifica em ⚙️ Configurações.\n\n"
            f"_Detalhe:_ `{msg[:300]}`"
        )
    if "429" in msg or "rate" in lower:
        return f"⏱️ **Limite de pedidos atingido.** Aguarda e tenta de novo.\n\n_Detalhe:_ `{msg[:300]}`"
    if "context" in lower or "length" in lower:
        return f"📏 **Contexto excedido.** Reduz PDFs selecionados.\n\n_Detalhe:_ `{msg[:300]}`"
    return f"❌ Erro da API NVIDIA: {msg}"


def get_model(name: str) -> str:
    return st.session_state.agent_models.get(name, DEFAULT_MODELS[name])


def get_summary_model() -> str:
    return st.session_state.get("summary_model", DEFAULT_SUMMARY_MODEL)


# =============================================================================
# 12. GERAÇÃO DE RESUMOS (auto + manual)
# =============================================================================
def summarize_pdf(client, pdf_name: str, pdf_text: str, status_container, lang_code: str) -> str:
    chunks = chunk_text(pdf_text, max_chars=MAX_CHARS_PER_SUMMARY_CHUNK)
    summary_model = get_summary_model()

    # System prompt = role + language override + section labels translation
    base_system = "You are a Professor Catedrático producing rigorous academic summaries."
    full_system = (
        base_system + "\n\n"
        + language_instruction(lang_code) + "\n"
        + section_labels_block(lang_code)
    )

    if len(chunks) == 1:
        status_container.write(t("summarizing", name=pdf_name, chars=len(chunks[0])))
        user_prompt = PROMPT_RESUMO_TEMPLATE.format(material=chunks[0])
        return stream_call_animated(
            client, model=summary_model,
            system_prompt=full_system, user_prompt=user_prompt,
            container=status_container, temperature=0.4, max_tokens=6000,
            lang_code=lang_code,
        )

    status_container.write(t("big_pdf_split", name=pdf_name, n=len(chunks)))
    parts: List[str] = []
    for i, ck in enumerate(chunks, start=1):
        status_container.write(t("chunk_progress", i=i, n=len(chunks), chars=len(ck))
                               + " — " + random_fun_message(lang_code))
        chunk_system = (
            base_system + " "
            f"This text is part of a larger document — summarise ONLY this block ({i}/{len(chunks)})."
            "\n\n" + language_instruction(lang_code) + "\n" + section_labels_block(lang_code)
        )
        user_prompt = PROMPT_RESUMO_TEMPLATE.format(material=ck)
        partial = stream_call_animated(
            client, model=summary_model,
            system_prompt=chunk_system, user_prompt=user_prompt,
            container=status_container, temperature=0.4, max_tokens=6000,
            lang_code=lang_code,
        )
        parts.append(f"<!-- Block {i}/{len(chunks)} -->\n\n{partial}")

    return "\n\n---\n\n".join(parts)


def auto_process_uploaded_pdfs(uploaded_files) -> None:
    api_key = st.session_state.nvidia_api_key
    lang_code = st.session_state.get("ui_language", "pt")
    if not api_key:
        st.warning(t("warn_set_key"), icon="⚠️")
    client = get_nvidia_client(api_key) if api_key else None
    new_files = [f for f in uploaded_files if f.name not in st.session_state.pdf_database]
    if not new_files:
        return
    for f in new_files:
        with st.status(t("processing", name=f.name), expanded=True) as s:
            try:
                s.write(t("extracting"))
                meta = extract_pdf_text(f.getvalue())
                raw_text: str = meta["text"]   # type: ignore[assignment]
                n_pages: int = meta["pages"]   # type: ignore[assignment]
                n_chars: int = meta["chars"]   # type: ignore[assignment]
                s.write(t("extracted", pages=n_pages, chars=n_chars))

                if not raw_text.strip():
                    st.session_state.pdf_database[f.name] = {
                        "raw_text": "", "summary": "_(empty PDF — likely a scan without OCR)_",
                        "pages": n_pages, "chars": 0, "auto_generated": False,
                        "language": lang_code,
                    }
                    s.update(label=t("empty_pdf_warn", name=f.name), state="error", expanded=True)
                    continue

                if client is None:
                    st.session_state.pdf_database[f.name] = {
                        "raw_text": raw_text,
                        "summary": "_(API key missing — click 🔄 to generate)_",
                        "pages": n_pages, "chars": n_chars, "auto_generated": False,
                        "language": lang_code,
                    }
                    s.update(label=f"✅ {f.name} — text extracted (summary pending)",
                             state="complete", expanded=False)
                    continue

                summary_md = summarize_pdf(client, f.name, raw_text, s, lang_code)
                st.session_state.pdf_database[f.name] = {
                    "raw_text": raw_text, "summary": summary_md,
                    "pages": n_pages, "chars": n_chars,
                    "auto_generated": True, "language": lang_code,
                }
                s.update(label=t("summary_done", name=f.name), state="complete", expanded=False)
            except OpenAIError as e:
                s.markdown(friendly_api_error(e))
                s.update(label=t("summary_fail", name=f.name), state="error", expanded=True)
            except Exception as e:
                s.error(f"❌ {e}")
                s.update(label=t("summary_fail", name=f.name), state="error", expanded=True)


def regenerate_summary(pdf_name: str) -> None:
    api_key = st.session_state.nvidia_api_key
    lang_code = st.session_state.get("ui_language", "pt")
    if not api_key:
        st.warning(t("warn_set_key"))
        return
    if pdf_name not in st.session_state.pdf_database:
        return
    entry = st.session_state.pdf_database[pdf_name]
    raw_text = entry.get("raw_text", "")
    if not raw_text:
        st.error("No extracted text.")
        return
    client = get_nvidia_client(api_key)
    with st.status(t("regen_progress", name=pdf_name), expanded=True) as s:
        try:
            new_summary = summarize_pdf(client, pdf_name, raw_text, s, lang_code)
            entry["summary"] = new_summary
            entry["auto_generated"] = True
            entry["language"] = lang_code
            st.session_state.pdf_database[pdf_name] = entry
            s.update(label=t("regen_done", name=pdf_name), state="complete", expanded=False)
        except OpenAIError as e:
            s.markdown(friendly_api_error(e))
            s.update(label=t("regen_fail"), state="error", expanded=True)


# =============================================================================
# 13. LOOP DE CONSENSO CIRCULAR — AVALIAÇÃO
# =============================================================================
@dataclass
class DebateEntry:
    iteration: int
    author: str
    target_author: Optional[str]
    content: str
    kind: str  # "draft" | "approval" | "rewrite"


@dataclass
class DebateResult:
    final_content: str
    final_author: str
    history: List[DebateEntry] = field(default_factory=list)
    consensus_reached: bool = False
    iterations_used: int = 0


def is_approval(response: str) -> bool:
    return UNANIMITY_TOKEN.upper() in response.strip()[:300].upper()


def run_eval_consensus(client, full_material: str, *, max_iterations: int, ui_container, lang_code: str) -> DebateResult:
    history: List[DebateEntry] = []

    # Language override aplicado a TODAS as chamadas do debate
    lang_block = language_instruction(lang_code)

    # FASE 0 — Chefe V1
    with ui_container.status(
        t("chefe_drafting") + f" — {random_fun_message(lang_code)}", expanded=True,
    ) as s:
        chefe_model = get_model("Chefe")
        s.write(f"Modelo: `{chefe_model}`")
        system_prompt = EVAL_INITIAL_SYSTEM + "\n\n" + lang_block
        user_prompt = (
            "MATÉRIA DE ESTUDO COMPLETA:\n\n"
            f"{full_material}\n\n---\n\nProduz agora o Teste de Revisão."
        )
        initial_draft = stream_call_animated(
            client, model=chefe_model,
            system_prompt=system_prompt, user_prompt=user_prompt,
            container=s, temperature=0.35, max_tokens=5500, lang_code=lang_code,
        )
        s.update(label="✅ Chefe → V1", state="complete", expanded=False)

    history.append(DebateEntry(0, "Chefe", None, initial_draft, "draft"))

    current_author, current_content, version_number = "Chefe", initial_draft, 1

    for iteration in range(1, max_iterations + 1):
        ui_container.markdown(
            f"<div class='round-tag'>{t('round_of', i=iteration, n=max_iterations, v=version_number, a=current_author)}</div>",
            unsafe_allow_html=True,
        )
        validators_this_round = [a for a in AGENTS_ORDER if a != current_author]
        approvals_this_round: List[str] = []
        rewrite_happened = False

        for validator_name in validators_this_round:
            label = (t("validator_evaluating",
                       icon=AGENT_ICONS[validator_name], v=validator_name,
                       n=version_number, a=current_author)
                     + f" — {random_fun_message(lang_code)}")
            with ui_container.status(label, expanded=True) as s:
                v_model = get_model(validator_name)
                s.write(f"Modelo: `{v_model}`")
                system_prompt = (
                    EVAL_VALIDATION_SYSTEM.format(
                        validator=validator_name, author=current_author, token=UNANIMITY_TOKEN
                    ) + "\n\n" + lang_block
                )
                user_prompt = (
                    "MATÉRIA ORIGINAL:\n\n"
                    f"{full_material}\n\n---\n\n"
                    f"TESTE A AVALIAR (autoria: {current_author}, V{version_number}):\n\n"
                    f"{current_content}\n\n---\n\n"
                    f"DECIDE: aprovar com `{UNANIMITY_TOKEN}` ou reescrever o teste completo."
                )
                response = stream_call_animated(
                    client, model=v_model,
                    system_prompt=system_prompt, user_prompt=user_prompt,
                    container=s, temperature=0.2, max_tokens=3000, lang_code=lang_code,
                )

                if is_approval(response):
                    approvals_this_round.append(validator_name)
                    history.append(DebateEntry(iteration, validator_name, current_author, response, "approval"))
                    s.update(label=t("approved", v=validator_name, tok=UNANIMITY_TOKEN),
                             state="complete", expanded=False)
                else:
                    history.append(DebateEntry(iteration, validator_name, current_author, response, "rewrite"))
                    version_number += 1
                    s.update(label=t("rewrote", v=validator_name, n=version_number),
                             state="complete", expanded=False)
                    current_author, current_content = validator_name, response
                    rewrite_happened = True
                    break

        if not rewrite_happened and len(approvals_this_round) == len(validators_this_round):
            others = ", ".join(validators_this_round)
            ui_container.markdown(
                f"<div class='consensus-banner'>{t('consensus_msg', i=iteration, v=version_number, a=current_author, others=others)}</div>",
                unsafe_allow_html=True,
            )
            return DebateResult(
                final_content=current_content, final_author=current_author,
                history=history, consensus_reached=True, iterations_used=iteration,
            )

    ui_container.markdown(
        f"<div class='no-consensus-banner'>{t('no_consensus_msg', n=max_iterations, v=version_number, a=current_author)}</div>",
        unsafe_allow_html=True,
    )
    return DebateResult(
        final_content=current_content, final_author=current_author,
        history=history, consensus_reached=False, iterations_used=max_iterations,
    )


# =============================================================================
# 14. SESSION STATE
# =============================================================================
DEFAULT_MAX_ITER = 4

st.session_state.setdefault("ui_language", "pt")
st.session_state.setdefault("nvidia_api_key", "")
st.session_state.setdefault("max_iterations", DEFAULT_MAX_ITER)
st.session_state.setdefault("agent_models", DEFAULT_MODELS.copy())
st.session_state.setdefault("summary_model", DEFAULT_SUMMARY_MODEL)
st.session_state.setdefault("pdf_database", {})
st.session_state.setdefault("eval_selected_pdfs", [])
st.session_state.setdefault("eval_result", None)
st.session_state.setdefault("_processed_signatures", set())

if not st.session_state.nvidia_api_key:
    try:
        secret_key = st.secrets.get("NVIDIA_API_KEY", "")
        if secret_key:
            st.session_state.nvidia_api_key = secret_key
    except Exception:
        pass


# =============================================================================
# 15. SIDEBAR
# =============================================================================
def model_selectbox(label: str, current_value: str, key: str) -> str:
    """
    Renderiza um selectbox de modelos baseado no MODEL_REGISTRY, com
    fallback "✏️ Personalizado…" que abre um text_input.
    """
    registry_keys = list(MODEL_REGISTRY.keys())
    options = registry_keys + [CUSTOM_MODEL_SENTINEL]

    # Determina índice atual
    if current_value in MODEL_REGISTRY:
        idx = registry_keys.index(current_value)
    else:
        idx = len(registry_keys)  # = custom

    def _fmt(k: str) -> str:
        if k == CUSTOM_MODEL_SENTINEL:
            return CUSTOM_MODEL_SENTINEL
        return MODEL_REGISTRY[k]["label"]

    chosen = st.selectbox(label, options=options, index=idx, format_func=_fmt, key=key + "_sel")

    if chosen == CUSTOM_MODEL_SENTINEL:
        custom_val = st.text_input(
            t("custom_model_input"),
            value=current_value if current_value not in MODEL_REGISTRY else "",
            placeholder="vendor/model-id",
            key=key + "_custom",
        )
        return custom_val.strip() or current_value
    else:
        meta = MODEL_REGISTRY[chosen]
        css_class = "model-warn" if meta.get("warn") else "model-help"
        st.markdown(
            f"<div class='{css_class}'>{meta['best_for']}</div>",
            unsafe_allow_html=True,
        )
        return chosen


with st.sidebar:
    # --- Logo ISEL ----------------------------------------------------------
    st.markdown(
        f"""
        <div class='isel-logo-wrap'>
            <img src='{ISEL_LOGO_URL}' alt='ISEL'
                 onerror="this.outerHTML='<div class=isel-logo-fallback>ISEL</div>';">
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Análise de Custos · Multi-Agent AI")

    # --- 🌐 Idioma -----------------------------------------------------------
    lang_options = list(LANGUAGES.keys())
    current_lang_idx = lang_options.index(st.session_state.ui_language) if st.session_state.ui_language in lang_options else 0
    new_lang = st.selectbox(
        t("language"),
        options=lang_options,
        index=current_lang_idx,
        format_func=lambda c: LANGUAGES[c]["label"],
        help=t("language_help"),
        key="lang_select",
    )
    if new_lang != st.session_state.ui_language:
        st.session_state.ui_language = new_lang
        st.rerun()

    st.divider()

    # --- ⚙️ Configurações ---------------------------------------------------
    with st.expander(t("config"), expanded=not st.session_state.nvidia_api_key):
        api_key_input = st.text_input(
            t("api_key"),
            value=st.session_state.nvidia_api_key, type="password",
            placeholder="nvapi-…", help=t("api_key_help"),
        )
        if api_key_input != st.session_state.nvidia_api_key:
            st.session_state.nvidia_api_key = api_key_input
            st.rerun()

        max_iter_input = st.slider(
            t("max_rounds"), min_value=2, max_value=10, value=st.session_state.max_iterations,
        )
        if max_iter_input != st.session_state.max_iterations:
            st.session_state.max_iterations = max_iter_input

        st.markdown(f"**{t('summary_model_label')}**")
        new_sm = model_selectbox("", st.session_state.summary_model, "summary_model")
        if new_sm and new_sm != st.session_state.summary_model:
            st.session_state.summary_model = new_sm

        st.markdown(f"**{t('debate_models_label')}**")
        st.caption(t("model_404_hint"))
        for agent_name in AGENTS_ORDER:
            st.markdown(f"**{AGENT_ICONS[agent_name]} {agent_name}**")
            new_val = model_selectbox(
                "",
                st.session_state.agent_models.get(agent_name, DEFAULT_MODELS[agent_name]),
                f"agent_{agent_name}",
            )
            if new_val:
                st.session_state.agent_models[agent_name] = new_val

        if st.button(t("reset_models"), use_container_width=True, key="reset_models"):
            st.session_state.agent_models = DEFAULT_MODELS.copy()
            st.session_state.summary_model = DEFAULT_SUMMARY_MODEL
            st.rerun()

        if st.session_state.nvidia_api_key:
            st.success(t("key_loaded"), icon="✅")
        else:
            st.warning(t("no_key"), icon="⚠️")

    st.divider()

    # --- 📁 Upload de PDFs --------------------------------------------------
    st.markdown(f"##### {t('upload_pdfs')}")
    uploaded_files = st.file_uploader(
        t("upload_pdfs"), type=["pdf"], accept_multiple_files=True,
        label_visibility="collapsed", help=t("upload_help"),
    )

    if uploaded_files:
        new_signatures = set((f.name, f.size) for f in uploaded_files)
        unseen = new_signatures - st.session_state._processed_signatures
        if unseen:
            auto_process_uploaded_pdfs(uploaded_files)
            st.session_state._processed_signatures |= new_signatures
            st.session_state.eval_selected_pdfs = list(st.session_state.pdf_database.keys())
            st.rerun()

    db = st.session_state.pdf_database
    if db:
        st.success(t("pdfs_loaded", n=len(db)))
        total_chars = sum(int(e.get("chars", 0)) for e in db.values())
        total_pages = sum(int(e.get("pages", 0)) for e in db.values())
        st.caption(t("total_meta", pages=total_pages, chars=total_chars))

    st.divider()

    # --- 🤖 Atalho IA --------------------------------------------------------
    st.markdown(f"##### {t('ai_section')}")
    st.markdown(f"<div class='sidebar-pill'>{t('ai_pill_eval')}</div>", unsafe_allow_html=True)
    st.caption(t("ai_pill_help"))

    st.divider()

    # --- 🗑️ Base de Dados --------------------------------------------------
    st.markdown(f"##### {t('db_section')}")
    if db:
        confirm_delete = st.checkbox(t("db_confirm"), key="confirm_delete_db", help=t("db_confirm_help"))
        if st.button(t("db_delete_btn"), disabled=not confirm_delete,
                     use_container_width=True, type="secondary", key="delete_db_btn"):
            st.session_state.pdf_database = {}
            st.session_state._processed_signatures = set()
            st.session_state.eval_result = None
            st.session_state.eval_selected_pdfs = []
            st.session_state.confirm_delete_db = False
            st.success(t("db_deleted"))
            time.sleep(0.4)
            st.rerun()
    else:
        st.caption(t("db_empty"))


# =============================================================================
# 16. CABEÇALHO PRINCIPAL
# =============================================================================
st.markdown(
    f"""
    <div class="isel-banner">
        <h1>📊 {t('app_title')}</h1>
        <p class="subtitle">{t('subtitle')}</p>
        <div>
            <span class="badge">🧠 Auto-summaries</span>
            <span class="badge">🎓 Multi-agent eval</span>
            <span class="badge">📄 Native PDF</span>
            <span class="badge">🌐 5 languages</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 17. RENDERIZADORES
# =============================================================================
def render_agent_panel() -> None:
    c1, c2, c3 = st.columns(3)
    for col, name in zip([c1, c2, c3], AGENTS_ORDER):
        with col:
            st.markdown(
                f"<div class='agent-card'><div class='role'>{AGENT_ICONS[name]} {name}</div>"
                f"<div class='model'>{get_model(name)}</div></div>",
                unsafe_allow_html=True,
            )


def render_pdf_tab(pdf_name: str, entry: Dict) -> None:
    st.markdown(f"## 📄 {pdf_name}")
    pages = entry.get("pages", "?")
    chars = int(entry.get("chars", 0))
    auto = entry.get("auto_generated", False)
    badge = t("summary_auto") if auto else t("summary_pending")
    summary_lang = entry.get("language", "pt")
    lang_label = LANGUAGES.get(summary_lang, LANGUAGES["pt"])["label"]
    st.markdown(
        f"<div class='pdf-meta'>"
        + t("pages_chars", pages=pages, chars=chars, badge=badge)
        + f" · 🌐 {lang_label}</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 1, 1, 3])
    with cols[0]:
        if st.button(t("regen_summary"), key=f"regen_{pdf_name}", use_container_width=True):
            regenerate_summary(pdf_name)
            st.rerun()
    with cols[1]:
        st.download_button("📥 .md", data=entry.get("summary", ""),
                           file_name=f"{pdf_name}.summary.md", mime="text/markdown",
                           key=f"dl_summary_{pdf_name}", use_container_width=True)
    with cols[2]:
        st.download_button("📥 raw", data=entry.get("raw_text", ""),
                           file_name=f"{pdf_name}.raw.txt", mime="text/plain",
                           key=f"dl_raw_{pdf_name}", use_container_width=True)

    st.divider()
    summary = entry.get("summary", "")
    if summary:
        st.markdown(summary)
    else:
        st.warning(t("no_summary_yet"))

    with st.expander(t("view_raw"), expanded=False):
        raw = entry.get("raw_text", "")
        st.text(raw[:50_000] + ("\n\n[... truncated ...]" if len(raw) > 50_000 else ""))


def render_debate_history(result: DebateResult) -> None:
    with st.expander(t("debate_history", n=len(result.history))):
        for entry in result.history:
            icon = AGENT_ICONS[entry.author]
            if entry.kind == "draft":
                tag = "📝 V1"
            elif entry.kind == "approval":
                tag = f"✅ → {entry.target_author}"
            else:
                tag = f"✏️ → {entry.target_author}"
            st.markdown(f"**R{entry.iteration} · {icon} {entry.author}** — {tag}")
            with st.container(border=True):
                if entry.kind == "approval":
                    st.code(entry.content[:1500], language="markdown")
                else:
                    st.markdown(entry.content)
            st.write("")


def render_evaluation_tab() -> None:
    st.markdown(f"### {t('eval_title')}")
    st.caption(t("eval_caption"))
    st.write("")

    db = st.session_state.pdf_database
    if not db:
        st.info(t("info_start_upload"))
        return

    st.markdown(f"<div class='section-title'>{t('eval_select_pdfs')}</div>", unsafe_allow_html=True)
    valid_sel = [n for n in st.session_state.eval_selected_pdfs if n in db]
    if valid_sel != st.session_state.eval_selected_pdfs:
        st.session_state.eval_selected_pdfs = valid_sel
    chosen = st.multiselect(
        t("eval_select_q"), options=list(db.keys()),
        default=st.session_state.eval_selected_pdfs, key="eval_multiselect",
    )
    if chosen != st.session_state.eval_selected_pdfs:
        st.session_state.eval_selected_pdfs = chosen

    cols_sel = st.columns(2)
    with cols_sel[0]:
        if st.button(t("eval_select_all"), use_container_width=True, key="sel_all_eval"):
            st.session_state.eval_selected_pdfs = list(db.keys()); st.rerun()
    with cols_sel[1]:
        if st.button(t("eval_select_none"), use_container_width=True, key="sel_none_eval"):
            st.session_state.eval_selected_pdfs = []; st.rerun()

    st.write("")
    render_agent_panel()
    st.write("")

    api_key = st.session_state.nvidia_api_key
    max_iter = st.session_state.max_iterations
    selected = st.session_state.eval_selected_pdfs
    can_run = bool(api_key) and bool(selected)

    cols = st.columns([3, 1])
    with cols[0]:
        existing = st.session_state.get("eval_result")
        btn_label = t("btn_redo_eval") if existing else t("btn_run_eval")
        run = st.button(btn_label, type="primary", disabled=not can_run,
                        use_container_width=True, key="run_eval")
    with cols[1]:
        if st.session_state.get("eval_result"):
            if st.button(t("btn_clear"), use_container_width=True, key="clear_eval"):
                st.session_state.eval_result = None; st.rerun()

    if not api_key:
        st.warning(t("warn_set_key"))
    elif not selected:
        st.warning(t("warn_pick_pdf"))
    else:
        st.caption(t("info_limit", n=max_iter, k=len(selected)))

    if run and can_run:
        st.session_state.eval_result = None
        debate_container = st.container()
        debate_container.markdown(f"#### {t('debate_in_progress')}")
        try:
            client = get_nvidia_client(api_key)
            material_parts: List[str] = []
            for pdf_name in selected:
                entry = db.get(pdf_name, {})
                src = entry.get("summary") or entry.get("raw_text", "")
                material_parts.append(f"\n=== PDF: {pdf_name} ===\n\n{src}")
            full_material = "\n\n".join(material_parts).strip()

            original_len = len(full_material)
            full_material = safe_truncate(full_material, MAX_CHARS_FOR_EVAL_INPUT)
            if len(full_material) < original_len:
                debate_container.info(t("material_too_big", orig=original_len, trunc=len(full_material)))

            result = run_eval_consensus(
                client=client, full_material=full_material,
                max_iterations=max_iter, ui_container=debate_container,
                lang_code=st.session_state.ui_language,
            )
            st.session_state.eval_result = result
        except OpenAIError as e:
            debate_container.markdown(friendly_api_error(e))
        except Exception as e:
            debate_container.error(f"❌ {e}")

    result: Optional[DebateResult] = st.session_state.get("eval_result")
    if result:
        st.divider()
        status_emoji = "🎉" if result.consensus_reached else "⏱️"
        status_text = (t("consensus_in", n=result.iterations_used) if result.consensus_reached
                       else t("limit_reached", n=result.iterations_used))
        st.markdown(f"## {status_emoji} {t('final_version')} · {status_text}")
        st.caption(f"{t('final_authorship')}: **{AGENT_ICONS[result.final_author]} {result.final_author}**")
        with st.container(border=True):
            st.markdown(result.final_content)
        st.download_button(t("download_test"), data=result.final_content,
                           file_name="evaluation_test.md", mime="text/markdown", key="dl_eval_result")
        render_debate_history(result)


# =============================================================================
# 18. TABS PRINCIPAIS
# =============================================================================
db = st.session_state.pdf_database

if not db:
    with st.container(border=True):
        st.markdown(f"### {t('welcome_title')}")
        st.write(t("welcome_body"))
        st.markdown(
            f"- {t('welcome_b1')}\n"
            f"- {t('welcome_b2')}\n"
            f"- {t('welcome_b3')}\n"
            f"- {t('welcome_b4')}"
        )
    tab = st.tabs([t("tab_eval")])
    with tab[0]:
        render_evaluation_tab()
else:
    pdf_names = list(db.keys())
    tab_labels: List[str] = []
    for name in pdf_names:
        label = name if len(name) <= 50 else name[:47] + "…"
        tab_labels.append(f"📄 {label}")
    tab_labels.append(t("tab_eval"))

    tabs = st.tabs(tab_labels)
    for i, pdf_name in enumerate(pdf_names):
        with tabs[i]:
            render_pdf_tab(pdf_name, db[pdf_name])
    with tabs[-1]:
        render_evaluation_tab()
