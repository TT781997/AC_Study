"""
app.py — Plataforma Universitária de Estudo Multi-Agente — v4.0
============================================================================

Refactor estrutural face à v3.0:

  • AGNÓSTICA À CADEIRA — funciona para QUALQUER disciplina universitária
    (Engenharia, Ciências, Humanidades, Saúde, Direito, Economia…). Prompts
    purgados de "Análise de Custos" e referências institucionais.

  • 4 AGENTES ESPECIALIZADOS (em vez de 3 genéricos):
      👑 Chefe Redator        — Autor do draft inicial
      🔬 Verificador Técnico  — Caça erros de cálculos / fórmulas / factos
      🎓 Verificador Pedagógico — Clareza, estrutura didáctica, ambiguidades
      🧑‍🎓 Aluno Crítico       — Perspectiva do utilizador final (dificuldade
                                  adequada, perguntas fora-de-âmbito)

  • DEBATE VEREDICT-FIRST — validadores começam OBRIGATORIAMENTE com
    `DECISION: APPROVE` ou `DECISION: REWRITE` na 1ª linha. Quem aprova
    gasta ~50 tokens (~3-5s); quem reescreve usa max_tokens completos.
    Marcador universal `--- REWRITTEN TEST ---` separa o veredicto do
    teste reescrito. Resultado: discussão muito mais rápida e assertiva.

  • COBERTURA TOTAL DO PDF — prompt do Catedrático com instrução explícita
    "COBRE INTEGRALMENTE TUDO" e secção `## 📋 Cobertura` no fim.
    Para PDFs multi-chunk: fase opcional de verificação de cobertura que
    detecta lacunas e expande o resumo (toggle na sidebar).

  • TIMER DINÂMICO — chamada LLM corre em worker thread; main thread faz
    polling com timeout=0.5s ⇒ o contador avança a cada meio segundo,
    mesmo enquanto se espera pelo primeiro chunk. ETA estimada por modelo
    + recalibração após receber chunks reais.

Dependências:  pip install streamlit openai PyMuPDF
Execução:      streamlit run app.py
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import streamlit as st
from openai import OpenAI, OpenAIError


# =============================================================================
# 1. PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="ISEL · Plataforma Universitária de Estudo",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# 2. PALETA ISEL OFICIAL (Bordeaux + Warm Gray)
# =============================================================================
ISEL_PRIMARY    = "#9A3324"   # Bordeaux (Pantone 484 C)
ISEL_PRIMARY_DK = "#7A271C"
ISEL_PRIMARY_LT = "#C45A4A"
ISEL_GRAY_6     = "#A6A19E"   # Warm Gray 6C
ISEL_GRAY_11    = "#6E6259"   # Warm Gray 11C
ISEL_BG         = "#FAF7F4"
ISEL_SURFACE    = "#FFFFFF"
ISEL_BORDER     = "#E8E2DC"
ISEL_TEXT       = "#2A1F1A"
ISEL_SUCCESS    = "#5B7F4C"
ISEL_WARN       = "#C49A2E"

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

.isel-logo-wrap {{
    background: {ISEL_SURFACE}; padding: 0.5rem 0.5rem 1rem 0.5rem;
    border-bottom: 2px solid {ISEL_PRIMARY}; margin-bottom: 1rem; text-align: center;
}}
.isel-logo-wrap img {{ max-width: 180px; height: auto; }}
.isel-logo-fallback {{
    color: {ISEL_PRIMARY}; font-weight: 800; font-size: 1.3rem;
    letter-spacing: 0.05em; padding: 0.5rem;
}}

.stButton > button, .stDownloadButton > button {{
    background-color: {ISEL_PRIMARY}; color: white !important; border: none;
    border-radius: 6px; padding: 0.55rem 1.4rem; font-weight: 600;
    transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(154, 51, 36, 0.20);
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
    border-radius: 10px; padding: 1rem 1.1rem; border-left: 4px solid {ISEL_PRIMARY};
}}
.agent-card .role {{ color: {ISEL_PRIMARY}; font-weight: 700; font-size: 0.95rem; }}
.agent-card .role-desc {{ color: {ISEL_GRAY_11}; font-size: 0.78rem; font-style: italic; margin: 0.15rem 0 0.3rem 0; }}
.agent-card .model {{ color: {ISEL_GRAY_11}; font-size: 0.75rem; font-family: ui-monospace, monospace; word-break: break-all; }}

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
.loading-fun .meta .eta {{ color: {ISEL_PRIMARY}; font-weight: 600; }}
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
# 4. REGISTRY DE MODELOS NVIDIA NIM (2026)
#    `est_seconds_4k` = estimativa empírica de tempo (segundos) para gerar
#    max_tokens=4000. Usada para ETA do LoadingAnimator.
# =============================================================================
MODEL_REGISTRY: Dict[str, Dict[str, object]] = {
    "nvidia/nemotron-3-super-120b-a12b": {
        "label": "🥇 NVIDIA Nemotron 3 Super 120B-A12B",
        "best_for": "Flagship NVIDIA. MoE 120B (12B activos), 1M de contexto, raciocínio agentic + RAG. Excelente como Chefe Redator e para resumos densos.",
        "est_seconds_4k": 90,
    },
    "minimaxai/minimax-m2.7": {
        "label": "💼 MiniMax M2.7 (230B)",
        "best_for": "Eng. de software, agentic longo, entrega profissional. Compete com Claude em coding. Ótimo Verificador Pedagógico.",
        "est_seconds_4k": 70,
    },
    "moonshotai/kimi-k2.6": {
        "label": "📚 Moonshot Kimi K2.6",
        "best_for": "Contexto extremamente longo, síntese de documentos. Ideal para resumir PDFs grandes ou validar coerência global.",
        "est_seconds_4k": 100,
    },
    "deepseek-ai/deepseek-v4-pro": {
        "label": "📐 DeepSeek V4 Pro",
        "best_for": "Top em matemática, código, raciocínio multi-passo. Excelente Verificador Técnico — apanha erros de cálculo.",
        "est_seconds_4k": 80,
    },
    "deepseek-ai/deepseek-v4-flash": {
        "label": "⚡ DeepSeek V4 Flash",
        "best_for": "Versão rápida do V4 Pro. Bom para validadores que precisam de boa qualidade mas latência baixa.",
        "est_seconds_4k": 40,
    },
    "z-ai/glm-5.1": {
        "label": "🛠️ Zhipu GLM-5.1",
        "best_for": "200K contexto, 128K output. Coding e execução agentic prolongada multi-tool. Bom para tarefas estruturadas complexas.",
        "est_seconds_4k": 75,
    },
    "google/gemma-4-31b-it": {
        "label": "🌐 Google Gemma 4 31B (IT)",
        "best_for": "Multimodal, multilingue, 256K contexto, Apache 2.0. Forte em PT-PT e outras línguas europeias. Bom equilíbrio.",
        "est_seconds_4k": 50,
    },
    "openai/gpt-oss-120b": {
        "label": "🧠 OpenAI GPT-OSS 120B",
        "best_for": "Open-weight da OpenAI. Sólido em raciocínio geral e conhecimento amplo. Bom Chefe alternativo se preferires estilo OpenAI.",
        "est_seconds_4k": 80,
    },
    "stepfun-ai/step-3.7-flash": {
        "label": "⚡ StepFun Step-3.7 Flash",
        "best_for": "Inferência muito rápida, qualidade decente. Validator-friendly. Ideal para Aluno Crítico (rápido, ágil).",
        "est_seconds_4k": 30,
    },
    "stepfun-ai/step-3.5-flash": {
        "label": "⚡ StepFun Step-3.5 Flash",
        "best_for": "Versão anterior do Step Flash. Use 3.7 se disponível na tua conta.",
        "est_seconds_4k": 30,
    },
    "google/gemma-3n-e2b-it": {
        "label": "📱 Google Gemma 3n E2B (IT) — ultra-leve",
        "best_for": "2B params efetivos via PLE. Edge/mobile. Só como validador de último recurso para minimizar custos.",
        "est_seconds_4k": 20,
    },
    "nvidia/llama-nemotron-embed-1b-v2": {
        "label": "⚠️ NVIDIA Nemotron Embed 1B v2 — NÃO USAR",
        "best_for": "❌ MODELO DE EMBEDDINGS (RAG), NÃO é de chat. Não consegue gerar resumos nem participar em debates. Não selecionar.",
        "warn": True,
        "est_seconds_4k": 0,
    },
}

CUSTOM_MODEL_SENTINEL = "✏️ Personalizado…"
DEFAULT_SPEED_ESTIMATE_4K = 60  # fallback se modelo não estiver no registry

# =============================================================================
# 5. AGENTES — 4 papéis especializados
# =============================================================================
AGENTS_ORDER: List[str] = [
    "Chefe",
    "Verificador Técnico",
    "Verificador Pedagógico",
    "Aluno Crítico",
]
AGENT_ICONS: Dict[str, str] = {
    "Chefe": "👑",
    "Verificador Técnico": "🔬",
    "Verificador Pedagógico": "🎓",
    "Aluno Crítico": "🧑‍🎓",
}

DEFAULT_MODELS: Dict[str, str] = {
    "Chefe":                  "nvidia/nemotron-3-super-120b-a12b",  # qualidade top no draft
    "Verificador Técnico":    "deepseek-ai/deepseek-v4-pro",         # matemática / precisão
    "Verificador Pedagógico": "minimaxai/minimax-m2.7",              # estrutura, multilingue
    "Aluno Crítico":          "stepfun-ai/step-3.7-flash",           # rápido, simula aluno
}
DEFAULT_SUMMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b"


# =============================================================================
# 6. CONSTANTES
# =============================================================================
APPROVAL_MARKER       = "DECISION: APPROVE"
REWRITE_MARKER        = "DECISION: REWRITE"
REWRITE_BLOCK_MARKER  = "--- REWRITTEN TEST ---"
LEGACY_APPROVAL_TOKEN = "[UNANIMIDADE]"  # backward-compat
COVERAGE_OK_MARKER    = "COVERAGE_OK"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MAX_CHARS_PER_SUMMARY_CHUNK = 60_000
MAX_CHARS_FOR_EVAL_INPUT    = 120_000
MAX_CHARS_FOR_COVERAGE      = 80_000
HARD_TRUNCATE_MARGIN        = 200


# =============================================================================
# 7. INTERNACIONALIZAÇÃO (i18n)
# =============================================================================
LANGUAGES: Dict[str, Dict[str, str]] = {
    "pt": {"label": "🇵🇹 Português",  "llm_name": "Português Europeu (PT-PT)"},
    "en": {"label": "🇬🇧 English",     "llm_name": "English"},
    "es": {"label": "🇪🇸 Español",     "llm_name": "Español"},
    "fr": {"label": "🇫🇷 Français",    "llm_name": "français"},
    "de": {"label": "🇩🇪 Deutsch",     "llm_name": "Deutsch"},
}

SECTION_LABELS_BY_LANG: Dict[str, Dict[str, str]] = {
    "pt": {"foco": "🎯 Foco Principal",     "conceitos": "🧠 Conceitos-Chave",      "formulas": "🧮 Fórmulas/Metodologias", "aplicacao": "🏭 Aplicação Prática",     "dica": "🎓 Dica do Professor",        "cobertura": "📋 Cobertura"},
    "en": {"foco": "🎯 Main Focus",         "conceitos": "🧠 Key Concepts",         "formulas": "🧮 Formulas/Methodologies", "aplicacao": "🏭 Practical Application", "dica": "🎓 Professor's Tip",         "cobertura": "📋 Coverage"},
    "es": {"foco": "🎯 Enfoque Principal",  "conceitos": "🧠 Conceptos Clave",      "formulas": "🧮 Fórmulas/Metodologías", "aplicacao": "🏭 Aplicación Práctica",   "dica": "🎓 Consejo del Profesor",     "cobertura": "📋 Cobertura"},
    "fr": {"foco": "🎯 Focus Principal",    "conceitos": "🧠 Concepts Clés",        "formulas": "🧮 Formules/Méthodologies", "aplicacao": "🏭 Application Pratique",  "dica": "🎓 Conseil du Professeur",    "cobertura": "📋 Couverture"},
    "de": {"foco": "🎯 Hauptfokus",         "conceitos": "🧠 Schlüsselkonzepte",    "formulas": "🧮 Formeln/Methoden",       "aplicacao": "🏭 Praktische Anwendung",  "dica": "🎓 Professorentipp",          "cobertura": "📋 Abdeckung"},
}

AGENT_DISPLAY_NAMES: Dict[str, Dict[str, str]] = {
    "pt": {"Chefe": "Chefe Redator",   "Verificador Técnico": "Verificador Técnico",    "Verificador Pedagógico": "Verificador Pedagógico", "Aluno Crítico": "Aluno Crítico"},
    "en": {"Chefe": "Lead Writer",      "Verificador Técnico": "Technical Reviewer",    "Verificador Pedagógico": "Pedagogical Reviewer",   "Aluno Crítico": "Critical Student"},
    "es": {"Chefe": "Redactor Principal","Verificador Técnico": "Revisor Técnico",      "Verificador Pedagógico": "Revisor Pedagógico",     "Aluno Crítico": "Estudiante Crítico"},
    "fr": {"Chefe": "Rédacteur Principal","Verificador Técnico": "Vérificateur Technique","Verificador Pedagógico": "Vérificateur Pédagogique","Aluno Crítico": "Étudiant Critique"},
    "de": {"Chefe": "Chefredakteur",     "Verificador Técnico": "Technischer Prüfer",    "Verificador Pedagógico": "Pädagogischer Prüfer",   "Aluno Crítico": "Kritischer Student"},
}

AGENT_ROLE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "pt": {"Chefe": "Cria o draft inicial",            "Verificador Técnico": "Cálculos, fórmulas, factos",          "Verificador Pedagógico": "Clareza e didáctica",           "Aluno Crítico": "Perspectiva do utilizador"},
    "en": {"Chefe": "Drafts the initial version",      "Verificador Técnico": "Calculations, formulas, facts",       "Verificador Pedagógico": "Clarity & teaching quality",    "Aluno Crítico": "End-user perspective"},
    "es": {"Chefe": "Crea el borrador inicial",        "Verificador Técnico": "Cálculos, fórmulas, hechos",          "Verificador Pedagógico": "Claridad y didáctica",          "Aluno Crítico": "Perspectiva del usuario"},
    "fr": {"Chefe": "Crée le brouillon initial",       "Verificador Técnico": "Calculs, formules, faits",            "Verificador Pedagógico": "Clarté et didactique",          "Aluno Crítico": "Perspective de l'utilisateur"},
    "de": {"Chefe": "Erstellt den Erstentwurf",        "Verificador Técnico": "Berechnungen, Formeln, Fakten",       "Verificador Pedagógico": "Klarheit & Didaktik",           "Aluno Crítico": "Perspektive des Nutzers"},
}

I18N: Dict[str, Dict[str, str]] = {
    "pt": {
        "app_title": "Plataforma Universitária de Estudo",
        "subtitle": "Resume qualquer PDF académico em qualquer língua · Avaliação por debate multi-agente",
        "badge_universal": "🎓 Qualquer disciplina",
        "badge_multilang": "🌐 5 idiomas",
        "badge_coverage": "📋 Cobertura total",
        "badge_4agents": "🤖 4 agentes",
        "language": "Idioma da interface",
        "language_help": "Os resumos e a avaliação serão produzidos NESTE idioma, qualquer que seja a língua dos PDFs.",
        "config": "⚙️ Configurações",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Obrigatória para resumos automáticos e avaliação.",
        "max_rounds": "🔁 Máximo de rondas (avaliação)",
        "summary_model_label": "🧠 Modelo do Professor (resumos)",
        "debate_models_label": "🤖 Modelos do debate (4 agentes)",
        "coverage_check_label": "🔍 Verificação de cobertura (PDFs grandes)",
        "coverage_check_help": "Após resumir PDFs multi-chunk, verifica se algum tópico ficou de fora e completa o resumo. Adiciona ~1-2 chamadas extra ao LLM.",
        "model_404_hint": "Erro 404? Muda aqui para um modelo a que a tua conta tenha acesso.",
        "custom_model_input": "Insere o ID exato do modelo NVIDIA NIM",
        "reset_models": "↺ Repor defaults",
        "key_loaded": "🔒 Chave carregada — IA ativa",
        "no_key": "Sem chave — IA inativa.",
        "upload_pdfs": "📁 Carregar PDFs",
        "upload_help": "Cada PDF é automaticamente resumido ao ser carregado, no idioma da interface.",
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
        "welcome_b2": "🧠 Pedir ao **Professor** que gere um resumo académico estruturado no idioma escolhido",
        "welcome_b3": "📚 Abrir uma **tab por PDF** com o resumo completo em scroll",
        "welcome_b4": "🎓 Disponibilizar uma **avaliação interativa** com debate entre 4 agentes especializados",
        "tab_eval": "🎓 Avaliação Interativa",
        "eval_title": "🎓 Avaliação Interativa",
        "eval_caption": "Os 4 agentes debatem em loop circular: o autor escreve, os outros 3 validam. Cada validador começa com `DECISION: APPROVE/REWRITE` (rápido e assertivo). Consenso = aprovação unânime dos 3 não-autores.",
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
        "checking_coverage": "🔍 A verificar cobertura do resumo…",
        "coverage_ok": "✅ Cobertura completa.",
        "coverage_gaps": "🩹 Detetadas lacunas — a expandir o resumo…",
        "coverage_expanded": "✨ Resumo expandido com tópicos em falta.",
        "material_too_big": "📏 Matéria muito extensa ({orig:,} chars). Truncada para {trunc:,} chars.",
        "round_of": "🔄 Ronda {i} de {n} · V{v} (autoria: {a})",
        "approved": "✅ **{v}** aprovou",
        "rewrote": "✏️ **{v}** reescreveu — nova V{n}. Próxima ronda: 3 outros validam.",
        "consensus_msg": "🎉 Consenso atingido na ronda {i}! V{v} de {a} aprovada por: {others}.",
        "no_consensus_msg": "⏱️ Limite de {n} rondas atingido. Versão final: V{v} (autoria de {a}).",
        "chefe_drafting": "👑 **Chefe Redator** a criar V1 do Teste",
        "validator_evaluating": "{icon} **{v}** a avaliar V{n} de **{a}**",
        "elapsed": "decorridos",
        "remaining": "restantes",
        "over_estimate": "+ além da estimativa",
        "model_speed": "velocidade",
    },
    "en": {
        "app_title": "University Study Platform",
        "subtitle": "Summarise any academic PDF in any language · Multi-agent peer review",
        "badge_universal": "🎓 Any discipline",
        "badge_multilang": "🌐 5 languages",
        "badge_coverage": "📋 Full coverage",
        "badge_4agents": "🤖 4 agents",
        "language": "Interface language",
        "language_help": "Summaries and evaluations will be produced in THIS language, regardless of the source PDFs' language.",
        "config": "⚙️ Settings",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Required for automatic summaries and evaluation.",
        "max_rounds": "🔁 Maximum debate rounds",
        "summary_model_label": "🧠 Professor's model (summaries)",
        "debate_models_label": "🤖 Debate models (4 agents)",
        "coverage_check_label": "🔍 Coverage check (large PDFs)",
        "coverage_check_help": "After summarising multi-chunk PDFs, verifies if any topic was missed and completes the summary. Adds ~1-2 extra LLM calls.",
        "model_404_hint": "404 error? Pick a model your account can access.",
        "custom_model_input": "Enter the exact NVIDIA NIM model ID",
        "reset_models": "↺ Reset defaults",
        "key_loaded": "🔒 Key loaded — AI active",
        "no_key": "No key — AI disabled.",
        "upload_pdfs": "📁 Upload PDFs",
        "upload_help": "Each PDF is automatically summarised on upload, in the UI language.",
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
        "welcome_b4": "🎓 Provide an **interactive evaluation** with debate between 4 specialised agents",
        "tab_eval": "🎓 Interactive Evaluation",
        "eval_title": "🎓 Interactive Evaluation",
        "eval_caption": "The 4 agents debate in a circular loop: author writes, the other 3 validate. Each validator starts with `DECISION: APPROVE/REWRITE` (fast and assertive). Consensus = unanimous approval of the 3 non-authors.",
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
        "checking_coverage": "🔍 Verifying summary coverage…",
        "coverage_ok": "✅ Full coverage.",
        "coverage_gaps": "🩹 Gaps detected — expanding summary…",
        "coverage_expanded": "✨ Summary expanded with missing topics.",
        "material_too_big": "📏 Material very large ({orig:,} chars). Truncated to {trunc:,} chars.",
        "round_of": "🔄 Round {i} of {n} · V{v} (author: {a})",
        "approved": "✅ **{v}** approved",
        "rewrote": "✏️ **{v}** rewrote — new V{n}. Next round: 3 others validate.",
        "consensus_msg": "🎉 Consensus reached in round {i}! V{v} by {a} approved by: {others}.",
        "no_consensus_msg": "⏱️ Round limit ({n}) reached. Final version: V{v} (by {a}).",
        "chefe_drafting": "👑 **Lead Writer** drafting V1 of the test",
        "validator_evaluating": "{icon} **{v}** evaluating V{n} by **{a}**",
        "elapsed": "elapsed",
        "remaining": "remaining",
        "over_estimate": "over estimate",
        "model_speed": "speed",
    },
    "es": {
        "app_title": "Plataforma Universitaria de Estudio",
        "subtitle": "Resume cualquier PDF académico en cualquier idioma · Evaluación por debate multi-agente",
        "badge_universal": "🎓 Cualquier disciplina",
        "badge_multilang": "🌐 5 idiomas",
        "badge_coverage": "📋 Cobertura total",
        "badge_4agents": "🤖 4 agentes",
        "language": "Idioma de la interfaz",
        "language_help": "Los resúmenes y la evaluación se producirán en ESTE idioma, sea cual sea el idioma de los PDFs.",
        "config": "⚙️ Configuración",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Necesaria para resúmenes automáticos y evaluación.",
        "max_rounds": "🔁 Máximo de rondas (evaluación)",
        "summary_model_label": "🧠 Modelo del Profesor (resúmenes)",
        "debate_models_label": "🤖 Modelos del debate (4 agentes)",
        "coverage_check_label": "🔍 Verificación de cobertura (PDFs grandes)",
        "coverage_check_help": "Tras resumir PDFs multi-bloque, verifica si algún tema quedó fuera y completa el resumen.",
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
        "welcome_b2": "🧠 Pedirá al **Profesor** que genere un resumen académico estructurado",
        "welcome_b3": "📚 Abrirá una **pestaña por PDF** con el resumen completo",
        "welcome_b4": "🎓 Ofrecerá una **evaluación interactiva** con debate entre 4 agentes especializados",
        "tab_eval": "🎓 Evaluación Interactiva",
        "eval_title": "🎓 Evaluación Interactiva",
        "eval_caption": "Los 4 agentes debaten en bucle circular: el autor escribe, los otros 3 validan. Consenso = aprobación unánime.",
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
        "big_pdf_split": "📚 `{name}` es grande — dividido en **{n} bloques**.",
        "chunk_progress": "🧠 Bloque {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ ¡`{name}` resumido con éxito!",
        "summary_fail": "❌ Fallo al procesar `{name}`.",
        "regen_progress": "🔄 Rehaciendo el resumen de **{name}**",
        "regen_done": "✅ ¡Resumen rehecho!",
        "regen_fail": "❌ Fallo al rehacer.",
        "checking_coverage": "🔍 Verificando cobertura del resumen…",
        "coverage_ok": "✅ Cobertura completa.",
        "coverage_gaps": "🩹 Lagunas detectadas — expandiendo el resumen…",
        "coverage_expanded": "✨ Resumen expandido con temas faltantes.",
        "material_too_big": "📏 Material muy extenso ({orig:,} chars). Truncado a {trunc:,} chars.",
        "round_of": "🔄 Ronda {i} de {n} · V{v} (autor: {a})",
        "approved": "✅ **{v}** aprobó",
        "rewrote": "✏️ **{v}** reescribió — nueva V{n}. Próxima ronda: 3 validan.",
        "consensus_msg": "🎉 ¡Consenso alcanzado en la ronda {i}! V{v} de {a} aprobada por: {others}.",
        "no_consensus_msg": "⏱️ Límite de {n} rondas alcanzado. Versión final: V{v} (de {a}).",
        "chefe_drafting": "👑 **Redactor Principal** redactando V1",
        "validator_evaluating": "{icon} **{v}** evaluando V{n} de **{a}**",
        "elapsed": "transcurridos",
        "remaining": "restantes",
        "over_estimate": "por encima de la estimación",
        "model_speed": "velocidad",
    },
    "fr": {
        "app_title": "Plateforme Universitaire d'Étude",
        "subtitle": "Résume tout PDF académique dans n'importe quelle langue · Évaluation par débat multi-agent",
        "badge_universal": "🎓 Toute discipline",
        "badge_multilang": "🌐 5 langues",
        "badge_coverage": "📋 Couverture totale",
        "badge_4agents": "🤖 4 agents",
        "language": "Langue de l'interface",
        "language_help": "Les résumés et l'évaluation seront produits dans CETTE langue.",
        "config": "⚙️ Paramètres",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Requise pour les résumés automatiques et l'évaluation.",
        "max_rounds": "🔁 Tours maximum (évaluation)",
        "summary_model_label": "🧠 Modèle du Professeur (résumés)",
        "debate_models_label": "🤖 Modèles du débat (4 agents)",
        "coverage_check_label": "🔍 Vérification de couverture (gros PDFs)",
        "coverage_check_help": "Après avoir résumé les PDFs multi-blocs, vérifie qu'aucun sujet n'a été oublié.",
        "model_404_hint": "Erreur 404 ? Choisis un modèle accessible à ton compte.",
        "custom_model_input": "Saisis l'ID exact du modèle NVIDIA NIM",
        "reset_models": "↺ Réinitialiser",
        "key_loaded": "🔒 Clé chargée — IA active",
        "no_key": "Pas de clé — IA inactive.",
        "upload_pdfs": "📁 Charger des PDFs",
        "upload_help": "Chaque PDF est automatiquement résumé au chargement.",
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
        "welcome_b1": "⛏️ Extraire le texte de chaque PDF",
        "welcome_b2": "🧠 Demander au **Professeur** un résumé structuré",
        "welcome_b3": "📚 Ouvrir un **onglet par PDF**",
        "welcome_b4": "🎓 Fournir une **évaluation interactive** avec 4 agents spécialisés",
        "tab_eval": "🎓 Évaluation Interactive",
        "eval_title": "🎓 Évaluation Interactive",
        "eval_caption": "Les 4 agents débattent en boucle circulaire : l'auteur écrit, les 3 autres valident. Consensus = unanimité.",
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
        "no_summary_yet": "Ce PDF n'a pas encore de résumé.",
        "processing": "📄 Traitement de **{name}**",
        "extracting": "⛏️ Extraction du texte (PyMuPDF)…",
        "extracted": "📑 {pages} pages · {chars:,} caractères extraits.",
        "empty_pdf_warn": "⚠️ `{name}` — texte vide (scan sans OCR ?).",
        "summarizing": "📝 Résumé de `{name}` ({chars:,} chars)…",
        "big_pdf_split": "📚 `{name}` est grand — divisé en **{n} blocs**.",
        "chunk_progress": "🧠 Bloc {i}/{n} ({chars:,} chars)",
        "summary_done": "✅ `{name}` résumé avec succès !",
        "summary_fail": "❌ Échec du traitement de `{name}`.",
        "regen_progress": "🔄 Régénération du résumé de **{name}**",
        "regen_done": "✅ Résumé régénéré !",
        "regen_fail": "❌ Échec.",
        "checking_coverage": "🔍 Vérification de la couverture…",
        "coverage_ok": "✅ Couverture complète.",
        "coverage_gaps": "🩹 Lacunes détectées — extension du résumé…",
        "coverage_expanded": "✨ Résumé étendu avec les sujets manquants.",
        "material_too_big": "📏 Matériel très volumineux ({orig:,} chars). Tronqué à {trunc:,}.",
        "round_of": "🔄 Tour {i}/{n} · V{v} (auteur : {a})",
        "approved": "✅ **{v}** a approuvé",
        "rewrote": "✏️ **{v}** a réécrit — V{n}. Tour suivant : 3 valident.",
        "consensus_msg": "🎉 Consensus au tour {i} ! V{v} de {a} approuvée par : {others}.",
        "no_consensus_msg": "⏱️ Limite de {n} tours atteinte. Version finale : V{v} (de {a}).",
        "chefe_drafting": "👑 **Rédacteur Principal** rédige V1",
        "validator_evaluating": "{icon} **{v}** évalue V{n} de **{a}**",
        "elapsed": "écoulées",
        "remaining": "restantes",
        "over_estimate": "au-delà de l'estimation",
        "model_speed": "vitesse",
    },
    "de": {
        "app_title": "Universitäre Lernplattform",
        "subtitle": "Fasse jedes akademische PDF in jeder Sprache zusammen · Multi-Agenten-Bewertung",
        "badge_universal": "🎓 Jede Disziplin",
        "badge_multilang": "🌐 5 Sprachen",
        "badge_coverage": "📋 Volle Abdeckung",
        "badge_4agents": "🤖 4 Agenten",
        "language": "Oberflächensprache",
        "language_help": "Zusammenfassungen und Bewertung werden IN DIESER Sprache erzeugt.",
        "config": "⚙️ Einstellungen",
        "api_key": "🔑 NVIDIA API Key",
        "api_key_help": "Erforderlich für automatische Zusammenfassungen und Bewertung.",
        "max_rounds": "🔁 Maximale Debattenrunden",
        "summary_model_label": "🧠 Professor-Modell (Zusammenfassungen)",
        "debate_models_label": "🤖 Debattenmodelle (4 Agenten)",
        "coverage_check_label": "🔍 Abdeckungsprüfung (große PDFs)",
        "coverage_check_help": "Nach Multi-Block-Zusammenfassungen prüfen, ob ein Thema fehlt.",
        "model_404_hint": "404-Fehler? Wähle ein zugängliches Modell.",
        "custom_model_input": "NVIDIA NIM Modell-ID eingeben",
        "reset_models": "↺ Standards wiederherstellen",
        "key_loaded": "🔒 Schlüssel geladen — KI aktiv",
        "no_key": "Kein Schlüssel — KI inaktiv.",
        "upload_pdfs": "📁 PDFs hochladen",
        "upload_help": "Jedes PDF wird beim Hochladen automatisch zusammengefasst.",
        "pdfs_loaded": "✅ {n} PDF(s) im Speicher",
        "total_meta": "📄 {pages} Seiten · {chars:,} Zeichen",
        "ai_section": "🤖 Multi-Agenten-KI",
        "ai_pill_eval": "🎓 Interaktive Bewertung",
        "ai_pill_help": "Tab immer verfügbar.",
        "db_section": "🗑️ Datenbank",
        "db_confirm": "ALLES LÖSCHEN bestätigen",
        "db_confirm_help": "Aktivieren um Button freizugeben.",
        "db_delete_btn": "🗑️ Zusammenfassungs-DB löschen",
        "db_deleted": "Datenbank gelöscht.",
        "db_empty": "(keine PDFs geladen)",
        "welcome_title": "👋 Willkommen",
        "welcome_body": "Lade deine PDFs in der Seitenleiste. Die Plattform wird automatisch:",
        "welcome_b1": "⛏️ Text aus jedem PDF extrahieren",
        "welcome_b2": "🧠 Den **Professor** um eine strukturierte Zusammenfassung bitten",
        "welcome_b3": "📚 Pro PDF einen **Tab** öffnen",
        "welcome_b4": "🎓 Eine **interaktive Bewertung** mit 4 spezialisierten Agenten bereitstellen",
        "tab_eval": "🎓 Interaktive Bewertung",
        "eval_title": "🎓 Interaktive Bewertung",
        "eval_caption": "Die 4 Agenten debattieren in Zirkelschleife: Autor schreibt, die anderen 3 validieren. Konsens = Einstimmigkeit.",
        "eval_select_pdfs": "📚 PDFs für die Bewertung",
        "eval_select_q": "Welche PDFs einbeziehen?",
        "eval_select_all": "✅ Alle auswählen",
        "eval_select_none": "🚫 Auswahl löschen",
        "btn_run_eval": "🚀 Multi-Agenten-Debatte starten",
        "btn_redo_eval": "🔄 Bewertung wiederholen",
        "btn_clear": "🗑️ Leeren",
        "warn_set_key": "Setze die NVIDIA API Key in **⚙️ Einstellungen**.",
        "warn_pick_pdf": "Wähle mindestens ein PDF oben aus.",
        "info_limit": "Aktuelles Limit: **{n} Runden** · PDFs: **{k}**.",
        "info_start_upload": "📁 Beginne mit dem Hochladen von PDFs.",
        "debate_in_progress": "🎬 Debatte läuft",
        "consensus_in": "Konsens in {n} Runde(n)",
        "limit_reached": "Rundenlimit ({n}) erreicht",
        "final_version": "Endversion",
        "final_authorship": "Endgültige Autorenschaft",
        "download_test": "📥 Test als Markdown",
        "debate_history": "🗂️ Debattenverlauf ({n} Beiträge)",
        "regen_summary": "🔄 Zusammenfassung neu erzeugen",
        "view_raw": "🔍 Extrahierten PDF-Text ansehen (debug)",
        "summary_auto": "🤖 Automatisch erzeugt",
        "summary_pending": "📝 Ausstehend",
        "pages_chars": "📑 <b>{pages}</b> Seiten · {chars:,} Zeichen · {badge}",
        "no_summary_yet": "Dieses PDF hat noch keine Zusammenfassung.",
        "processing": "📄 Verarbeite **{name}**",
        "extracting": "⛏️ Extrahiere PDF-Text (PyMuPDF)…",
        "extracted": "📑 {pages} Seiten · {chars:,} Zeichen extrahiert.",
        "empty_pdf_warn": "⚠️ `{name}` — leerer Text.",
        "summarizing": "📝 Fasse `{name}` zusammen ({chars:,} Zeichen)…",
        "big_pdf_split": "📚 `{name}` ist groß — **{n} Blöcke**.",
        "chunk_progress": "🧠 Block {i}/{n} ({chars:,} Zeichen)",
        "summary_done": "✅ `{name}` erfolgreich zusammengefasst!",
        "summary_fail": "❌ Verarbeitung fehlgeschlagen.",
        "regen_progress": "🔄 Erzeuge Zusammenfassung neu",
        "regen_done": "✅ Neu erzeugt!",
        "regen_fail": "❌ Fehlgeschlagen.",
        "checking_coverage": "🔍 Prüfe Abdeckung…",
        "coverage_ok": "✅ Vollständige Abdeckung.",
        "coverage_gaps": "🩹 Lücken erkannt — erweitere Zusammenfassung…",
        "coverage_expanded": "✨ Zusammenfassung um fehlende Themen erweitert.",
        "material_too_big": "📏 Material sehr umfangreich ({orig:,}). Gekürzt auf {trunc:,}.",
        "round_of": "🔄 Runde {i}/{n} · V{v} (Autor: {a})",
        "approved": "✅ **{v}** zugestimmt",
        "rewrote": "✏️ **{v}** überschrieben — V{n}. Nächste Runde: 3 validieren.",
        "consensus_msg": "🎉 Konsens in Runde {i}! V{v} von {a} bestätigt durch: {others}.",
        "no_consensus_msg": "⏱️ Rundenlimit ({n}) erreicht. Endversion: V{v} (von {a}).",
        "chefe_drafting": "👑 **Chefredakteur** erstellt V1",
        "validator_evaluating": "{icon} **{v}** prüft V{n} von **{a}**",
        "elapsed": "vergangen",
        "remaining": "übrig",
        "over_estimate": "über der Schätzung",
        "model_speed": "Geschwindigkeit",
    },
}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("ui_language", "pt")
    val = I18N.get(lang, I18N["pt"]).get(key, I18N["pt"].get(key, key))
    try:
        return val.format(**kwargs) if kwargs else val
    except Exception:
        return val


def agent_display(agent_key: str) -> str:
    """Devolve o nome do agente no idioma da UI."""
    lang = st.session_state.get("ui_language", "pt")
    return AGENT_DISPLAY_NAMES.get(lang, AGENT_DISPLAY_NAMES["pt"]).get(agent_key, agent_key)


def agent_role_description(agent_key: str) -> str:
    lang = st.session_state.get("ui_language", "pt")
    return AGENT_ROLE_DESCRIPTIONS.get(lang, AGENT_ROLE_DESCRIPTIONS["pt"]).get(agent_key, "")


def language_instruction(lang_code: str) -> str:
    lang_name = LANGUAGES.get(lang_code, LANGUAGES["pt"])["llm_name"]
    return (
        f"### LANGUAGE OVERRIDE\n"
        f"You MUST produce ALL output in **{lang_name}**, regardless of the language of the source material. "
        f"Do not switch languages mid-response. If the source PDF is in another language, "
        f"translate the content into {lang_name} while preserving technical terminology.\n"
    )


def section_labels_block(lang_code: str) -> str:
    sl = SECTION_LABELS_BY_LANG.get(lang_code, SECTION_LABELS_BY_LANG["pt"])
    return (
        f"### SECTION HEADERS (use these EXACT labels translated into {LANGUAGES.get(lang_code, LANGUAGES['pt'])['llm_name']}):\n"
        f"- {sl['foco']}\n- {sl['conceitos']}\n- {sl['formulas']}\n- {sl['aplicacao']}\n- {sl['dica']}\n"
        f"- Final coverage section: ## {sl['cobertura']}\n"
    )


# =============================================================================
# 8. LOADING — Mensagens divertidas por idioma
# =============================================================================
FUNNY_LOADING_MESSAGES_BY_LANG: Dict[str, List[str]] = {
    "pt": [
        "🐱 Os agentes a tomar café antes do debate académico…",
        "🦉 A coruja-verificadora a conferir fórmulas duas vezes…",
        "🦫 Os castores a construir o resumo, parágrafo a parágrafo…",
        "🐢 Devagar, mas com rigor de Professor…",
        "🐶 Agentes a ladrar uns aos outros sobre definições…",
        "🐧 Pinguins em reunião departamental — temperatura ideal!",
        "🦊 A raposa-técnica detetou um símbolo suspeito numa fórmula…",
        "🐼 Pandas a folhear notas. Devagar, mas certo.",
        "🦘 A saltar entre capítulos à procura do resumo perfeito…",
        "🐙 8 braços a escrever Markdown ao mesmo tempo…",
        "🦦 As lontras a polir as definições com paciência…",
        "🦝 O guaxinim crítico encontrou outra ambiguidade…",
    ],
    "en": [
        "🐱 The agents are sipping coffee before the academic debate…",
        "🦉 The reviewer owl is double-checking formulas…",
        "🦫 Beavers are building the summary, paragraph by paragraph…",
        "🐢 Slow, but with professorial rigour…",
        "🐶 Agents barking at each other about definitions…",
        "🐧 Penguins in a departmental meeting — perfect room temperature!",
        "🦊 Technical fox spotted a suspicious symbol in a formula…",
        "🐼 Pandas flipping through notes. Slowly, surely.",
        "🦘 Hopping between chapters in search of the perfect summary…",
        "🐙 Eight arms typing Markdown simultaneously…",
        "🦦 Otters polishing the definitions patiently…",
        "🦝 The critical raccoon found another ambiguity…",
    ],
    "es": [
        "🐱 Los agentes tomando café antes del debate académico…",
        "🦉 La lechuza-revisora verificando fórmulas dos veces…",
        "🦫 Los castores construyendo el resumen, párrafo a párrafo…",
        "🐢 Despacio, pero con rigor de Profesor…",
        "🐶 Agentes ladrando sobre definiciones…",
        "🐧 Pingüinos en reunión departamental — ¡temperatura ideal!",
        "🦊 El zorro-técnico detectó un símbolo sospechoso…",
        "🐼 Pandas hojeando apuntes.",
        "🦘 Saltando entre capítulos…",
        "🐙 8 brazos escribiendo Markdown a la vez…",
        "🦦 Las nutrias puliendo las definiciones…",
        "🦝 El mapache crítico encontró otra ambigüedad…",
    ],
    "fr": [
        "🐱 Les agents prennent un café avant le débat académique…",
        "🦉 La chouette-vérificatrice contrôle les formules deux fois…",
        "🦫 Les castors construisent le résumé, paragraphe par paragraphe…",
        "🐢 Lentement, mais avec la rigueur d'un Professeur…",
        "🐶 Agents qui aboient sur les définitions…",
        "🐧 Pingouins en réunion départementale — température idéale !",
        "🦊 Le renard technique a repéré un symbole suspect…",
        "🐼 Pandas qui feuillètent les notes.",
        "🦘 Sauts entre chapitres…",
        "🐙 8 bras qui tapent du Markdown en même temps…",
        "🦦 Loutres qui polissent les définitions…",
        "🦝 Le raton critique a trouvé une autre ambiguïté…",
    ],
    "de": [
        "🐱 Die Agenten trinken Kaffee vor der akademischen Debatte…",
        "🦉 Die Prüfer-Eule kontrolliert die Formeln zweimal…",
        "🦫 Die Biber bauen die Zusammenfassung, Absatz für Absatz…",
        "🐢 Langsam, aber mit professoraler Sorgfalt…",
        "🐶 Agenten bellen über Definitionen…",
        "🐧 Pinguine in der Abteilungssitzung — perfekte Temperatur!",
        "🦊 Der technische Fuchs hat ein verdächtiges Symbol entdeckt…",
        "🐼 Pandas blättern durch Notizen.",
        "🦘 Springt zwischen Kapiteln…",
        "🐙 Acht Arme tippen gleichzeitig Markdown…",
        "🦦 Otter polieren die Definitionen geduldig…",
        "🦝 Der kritische Waschbär fand eine weitere Mehrdeutigkeit…",
    ],
}

LOADING_EMOJIS = ["🧠", "📚", "⚙️", "🔬", "📊", "🎓", "💡", "🔍", "📝", "🏛️"]


def random_fun_message(lang_code: str) -> str:
    msgs = FUNNY_LOADING_MESSAGES_BY_LANG.get(lang_code, FUNNY_LOADING_MESSAGES_BY_LANG["pt"])
    return random.choice(msgs)


# =============================================================================
# 9. LoadingAnimator — UI dinâmica com timer/ETA
# =============================================================================
class LoadingAnimator:
    """
    Animação de loading que actualiza a UI mesmo sem chunks novos.
    Renderiza:
      • emoji grande com bounce + pulse-glow
      • mensagem divertida (roda a cada 15s)
      • contador `⏱ Xs decorridos`
      • ETA `⏳ ~Ys restantes`
      • barra de progresso visual
      • placeholder com últimos chunks do LLM streaming

    Usado em conjunto com `stream_call_threaded`: o main thread chama
    `.update()` em cada iteração do polling-loop (chunks novos ou tick).
    """

    MSG_ROTATE_SECONDS = 15.0

    def __init__(self, container, lang_code: str, eta_seconds: Optional[int] = None):
        self.container = container
        self.lang_code = lang_code
        self.eta_initial = eta_seconds if eta_seconds and eta_seconds > 0 else None
        self.start_time = time.time()
        self.last_msg_change = 0.0
        self.last_render = 0.0
        self.current_msg = random_fun_message(lang_code)
        self.current_emoji = random.choice(LOADING_EMOJIS)
        self.animator_slot = container.empty()
        self.text_slot = container.empty()
        self._render(current_text="")

    def update(self, current_text: str = "", force: bool = False) -> None:
        """Throttled a 2 fps por defeito; force=True para render imediato."""
        now = time.time()
        if not force and now - self.last_render < 0.5:
            return
        self.last_render = now
        elapsed = now - self.start_time

        if elapsed - self.last_msg_change >= self.MSG_ROTATE_SECONDS:
            self.current_msg = random_fun_message(self.lang_code)
            self.current_emoji = random.choice(LOADING_EMOJIS)
            self.last_msg_change = elapsed

        self._render(current_text)

    def _render(self, current_text: str) -> None:
        elapsed = time.time() - self.start_time
        chars = len(current_text)

        # ETA + progress
        if self.eta_initial:
            remaining = self.eta_initial - elapsed
            if remaining > 0:
                eta_html = f"· <span class='eta'>⏳ ~{int(remaining)}s {t('remaining')}</span>"
                progress_pct = min(95, int((elapsed / self.eta_initial) * 100))
            else:
                over = int(elapsed - self.eta_initial)
                eta_html = f"· <span class='eta'>⏳ +{over}s {t('over_estimate')}</span>"
                progress_pct = 95
        else:
            eta_html = ""
            progress_pct = min(95, int((elapsed / 60.0) * 100))

        html = (
            f"<div class='loading-fun'>"
            f"<span class='big-emoji'>{self.current_emoji}</span>"
            f"<div class='body'>"
            f"<div class='msg'>{self.current_msg}</div>"
            f"<div class='meta'>⏱ {int(elapsed)}s {t('elapsed')} · 📝 {chars:,} chars {eta_html}</div>"
            f"<div class='progress-bar'><div class='progress-fill' style='width: {progress_pct}%'></div></div>"
            f"</div></div>"
        )
        self.animator_slot.markdown(html, unsafe_allow_html=True)

        if current_text:
            tail = current_text[-1500:]
            self.text_slot.code(tail + "▌", language="markdown")

    def clear(self) -> None:
        self.animator_slot.empty()
        self.text_slot.empty()


def estimate_eta(model: str, max_tokens: int) -> int:
    """Devolve estimativa de segundos para gerar max_tokens com este modelo."""
    meta = MODEL_REGISTRY.get(model, {})
    base = meta.get("est_seconds_4k", DEFAULT_SPEED_ESTIMATE_4K)
    if not isinstance(base, (int, float)) or base <= 0:
        base = DEFAULT_SPEED_ESTIMATE_4K
    return max(5, int(base * (max_tokens / 4000.0)))


# =============================================================================
# 10. EXTRAÇÃO E CHUNKING DE PDFs
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
# 11. PROMPTS — Resumo + Cobertura
# =============================================================================
PROMPT_RESUMO_TEMPLATE = """Atua como Professor Universitário Sénior, especialista em sintetizar matéria académica de QUALQUER disciplina (Engenharia, Ciências, Humanidades, Saúde, Direito, Economia, Artes…).

A tua missão: produzir um Resumo Académico de Alto Nível sobre o material fornecido — completo, estruturado e ideal para preparação de exames universitários.

🎯 OBJETIVO CRÍTICO — COBERTURA INTEGRAL:
Cobre TODOS os tópicos do material. Se há 15 temas, o resumo aborda os 15. Não omitas nada relevante. Se um tema for breve no original, o resumo desse tema pode ser breve, mas DEVE estar lá.

ESTRUTURA POR TEMA (Markdown):

#### [Título do tema]
🎯 **Foco Principal:** uma frase cirúrgica sobre o objetivo central do tema.
🧠 **Conceitos-Chave:** definições rigorosas e detalhadas. Sub-bullets para sub-conceitos.
🧮 **Fórmulas/Metodologias:** *(apenas se aplicável — humanidades não terão)* equações em LaTeX (`$...$` inline, `$$...$$` display) + explicação das variáveis.
🏭 **Aplicação Prática:** exemplo concreto e tangível ao mundo real (caso, situação, problema).
🎓 **Dica do Professor:** erro comum a evitar, ligação a outro conceito, ou pista de exame.

NO FIM do resumo, adiciona uma secção `## 📋 Cobertura` com bullets curtos listando TODOS os temas/secções que abordaste. Isto permite verificar visualmente que nada ficou de fora.

REGRAS:
- Markdown limpo. Sem preâmbulos, sem despedidas, sem meta-comentários.
- Cabeçalho `####` para cada tema.
- NÃO inventes conteúdo fora do material.
- Linguagem técnica é preservada; resto é traduzido conforme system prompt.
- Usa as etiquetas das 5 secções TRADUZIDAS para o idioma do system prompt (ver SECTION HEADERS).

MATERIAL DE ESTUDO:

{material}
"""

PROMPT_COVERAGE_CHECK = """Avalia se o resumo cobre todos os TÓPICOS ESTRUTURAIS do material original.

FORMATO DE RESPOSTA OBRIGATÓRIO:

LINHA 1: `{ok_marker}` (se tudo está coberto) OU `GAPS_FOUND` (se faltam tópicos).

Se GAPS_FOUND, a partir da linha 2 lista os tópicos omitidos:
- [Título do tópico em falta]: 1 frase a descrever, referindo aproximadamente onde aparece no material.

REGRAS:
- Só assinala omissões ESTRUTURAIS (temas/conceitos inteiros). Detalhes secundários ou exemplos não contam.
- Sê justo: PDFs longos com 50 temas naturalmente têm resumos densos; não exijas paráfrase exaustiva.
- Máximo 10 lacunas. Foca nas mais importantes.

MATERIAL ORIGINAL:

{material}

---

RESUMO A AVALIAR:

{summary}
"""

PROMPT_GAP_FILLING = """O resumo anterior tem lacunas. A tua tarefa: ADICIONAR secções que cubram os tópicos em falta.

Para cada tópico em falta, cria uma secção no MESMO FORMATO do resumo original:

#### [Título do tema]
🎯 **Foco Principal:** ...
🧠 **Conceitos-Chave:** ...
🧮 **Fórmulas/Metodologias:** (se aplicável)
🏭 **Aplicação Prática:** ...
🎓 **Dica do Professor:** ...

REGRAS:
- Devolve APENAS as novas secções, em Markdown limpo.
- Sem preâmbulo, sem despedida.
- Não repitas o que já está no resumo atual.
- Usa as etiquetas das 5 secções no idioma do system prompt.

MATERIAL ORIGINAL:

{material}

---

RESUMO ATUAL (já cobre outros tópicos):

{summary}

---

TÓPICOS A ADICIONAR:

{gaps}
"""


# =============================================================================
# 12. PROMPTS — Avaliação (4 agentes, veredict-first)
# =============================================================================
EVAL_INITIAL_SYSTEM = """És o **Chefe Redator** — Professor Universitário Sénior. Crias testes de revisão de alta qualidade sobre qualquer disciplina académica.

A tua tarefa: produzir um Teste de Revisão completo sobre a matéria fornecida, cobrindo-a TRANSVERSALMENTE.

ESTRUTURA OBRIGATÓRIA:

## Parte I — Escolha Múltipla (10 questões)
Cada questão:
- Enunciado claro, sem ambiguidades.
- 4 opções: a), b), c), d).
- Linha **Resposta: x)** após as opções.
- Justificação curta (1-2 frases).

## Parte II — Exercícios Práticos (2 exercícios)
- Enunciado realista, com dados quantitativos coerentes quando aplicável.
- 3-5 alíneas de complexidade crescente.
- Resolução passo-a-passo com cálculos visíveis.
- Resultado final destacado em **negrito**.

REGRAS:
- COBERTURA TRANSVERSAL: as 10 perguntas distribuem-se por TÓPICOS DIFERENTES.
- Valores realistas; cálculos que fechem.
- LaTeX para fórmulas (`$...$` inline, `$$...$$` display).
- Sem preâmbulos, sem meta-comentários.
- CONCISO mas COMPLETO.
"""

# Validators: VEREDICT-FIRST. First line is ALWAYS one of two English markers.
# This makes parsing trivial and reduces ambiguity in any language.
EVAL_VALIDATION_SYSTEMS: Dict[str, str] = {
    "Verificador Técnico": """És o **Verificador Técnico**. Verificas RIGOR técnico-científico.

⚠️ REGRA DE OURO: avalias o teste produzido por **{author}**. NUNCA reescreves a tua própria autoria.

VERIFICA:
1. Cálculos exatos (refaz mentalmente).
2. Fórmulas corretas, com unidades consistentes.
3. Cada questão de escolha múltipla com UMA E SÓ UMA resposta correta.
4. Factos verdadeiros.

⚠️ FORMATO DE RESPOSTA — MARCADORES UNIVERSAIS (em INGLÊS, INVARIÁVEIS):

LINHA 1: `{approve_marker}` OU `{rewrite_marker}`

→ Se aprovas:
   Linha 2 (opcional): 1 frase com o que ficou bem.
   PARA. NADA MAIS.

→ Se reescreves:
   Linhas seguintes: 1 bullet curto por cada ERRO TÉCNICO encontrado.
   Depois: linha `{block_marker}`
   Em seguida: teste COMPLETO corrigido (Parte I + Parte II + soluções).

⚠️ POLÍTICA DE TOLERÂNCIA: aprova se não há erros técnicos REAIS. Preferências estilísticas, frases que poderiam ser mais elegantes, ou variantes de notação NÃO justificam reescrita. Reescreve apenas se há um erro que estraga o teste.

O conteúdo (razão, teste reescrito) é no idioma indicado no system prompt LANGUAGE OVERRIDE.
""",

    "Verificador Pedagógico": """És o **Verificador Pedagógico**. Verificas CLAREZA e DIDÁCTICA.

⚠️ REGRA DE OURO: avalias o teste produzido por **{author}**. NUNCA reescreves a tua própria autoria.

VERIFICA:
1. Enunciados claros e SEM ambiguidades.
2. Estrutura pedagógica sólida (do simples ao complexo).
3. Cobertura transversal da matéria.
4. Markdown limpo, sem ruído visual.

⚠️ FORMATO DE RESPOSTA — MARCADORES UNIVERSAIS (em INGLÊS, INVARIÁVEIS):

LINHA 1: `{approve_marker}` OU `{rewrite_marker}`

→ Se aprovas:
   Linha 2 (opcional): 1 frase.
   PARA.

→ Se reescreves:
   Bullets curtos com cada problema PEDAGÓGICO real.
   Depois: linha `{block_marker}`
   Teste COMPLETO corrigido.

⚠️ POLÍTICA DE TOLERÂNCIA: reescreve só se há ambiguidades reais ou má estrutura. Variações de estilo NÃO justificam.

O conteúdo é no idioma do LANGUAGE OVERRIDE.
""",

    "Aluno Crítico": """És o **Aluno Crítico**. Representas o aluno universitário que VAI USAR este teste para estudar.

⚠️ REGRA DE OURO: avalias o teste produzido por **{author}**. NUNCA reescreves a tua própria autoria.

PERGUNTA-TE:
1. Conseguiria responder com APENAS a matéria fornecida? Há armadilhas injustas?
2. O nível de dificuldade é adequado a exame universitário (nem trivial, nem impossível)?
3. Algum exercício está FORA do âmbito do material fornecido?
4. As perguntas refletem o que tipicamente é avaliado em exame?

⚠️ FORMATO DE RESPOSTA — MARCADORES UNIVERSAIS (em INGLÊS, INVARIÁVEIS):

LINHA 1: `{approve_marker}` OU `{rewrite_marker}`

→ Se aprovas:
   Linha 2 (opcional): 1 frase do ponto de vista de aluno.
   PARA.

→ Se reescreves:
   Bullets curtos com cada problema do ponto de vista de aluno.
   Depois: linha `{block_marker}`
   Teste COMPLETO corrigido.

⚠️ POLÍTICA DE TOLERÂNCIA: reescreve só se há perguntas REALMENTE injustas ou fora-de-âmbito. Dificuldade variada é OK.

O conteúdo é no idioma do LANGUAGE OVERRIDE.
""",
}


# =============================================================================
# 13. API NVIDIA — Stream com threading (timer dinâmico)
# =============================================================================
def get_nvidia_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def stream_call_threaded(
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
    Faz a chamada streaming num worker thread; o main thread faz polling
    com timeout=0.5s para que o LoadingAnimator avance mesmo enquanto
    espera pelo primeiro chunk.
    """
    chunk_queue: Queue = Queue()
    done_event = threading.Event()
    error_holder: List[Optional[Exception]] = [None]

    def worker() -> None:
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
                    chunk_queue.put(delta)
        except Exception as e:
            error_holder[0] = e
        finally:
            done_event.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    eta = estimate_eta(model, max_tokens)
    animator = LoadingAnimator(container, lang_code=lang_code, eta_seconds=eta)
    accumulated = ""

    try:
        while True:
            try:
                delta = chunk_queue.get(timeout=0.5)
                accumulated += delta
                animator.update(current_text=accumulated)
            except Empty:
                animator.update(current_text=accumulated, force=True)  # tick
                if done_event.is_set() and chunk_queue.empty():
                    break
        animator.update(current_text=accumulated, force=True)
    finally:
        animator.clear()

    thread.join(timeout=2.0)

    if error_holder[0]:
        raise error_holder[0]

    return accumulated.strip()


def friendly_api_error(err: Exception) -> str:
    msg = str(err)
    lower = msg.lower()
    if "404" in msg or "not found" in lower:
        return (
            "❌ **Modelo não encontrado na tua conta NVIDIA.**\n\n"
            "Vai à sidebar → **⚙️ Configurações → 🤖 Modelos** e escolhe outro do "
            "dropdown.\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "401" in msg or "unauthorized" in lower:
        return f"❌ **Chave NVIDIA inválida ou expirada.** Verifica em ⚙️ Configurações.\n\n_Detalhe:_ `{msg[:300]}`"
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
# 14. PARSING DOS VEREDITOS
# =============================================================================
def is_approval(response: str) -> bool:
    """First-line veredict check + backward-compat fallback."""
    if not response:
        return False
    first_line = response.strip().split("\n", 1)[0].strip().upper()
    if first_line.startswith(APPROVAL_MARKER.upper()):
        return True
    if first_line.startswith(REWRITE_MARKER.upper()):
        return False
    # Legacy fallback
    return LEGACY_APPROVAL_TOKEN.upper() in response.strip()[:300].upper()


def extract_rewrite(response: str) -> str:
    """Extract the rewritten test after the universal block marker."""
    if REWRITE_BLOCK_MARKER in response:
        return response.split(REWRITE_BLOCK_MARKER, 1)[1].strip()
    # Try a few variants (LLMs sometimes translate)
    for variant in ["--- TESTE REESCRITO ---", "--- TEST REWRITTEN ---", "--- NEW TEST ---"]:
        if variant in response:
            return response.split(variant, 1)[1].strip()
    # No marker: assume everything after the first line is the rewrite
    return response.strip().split("\n", 1)[-1].strip() if "\n" in response else response.strip()


# =============================================================================
# 15. RESUMO ROBUSTO (com cobertura)
# =============================================================================
def _build_summary_system(lang_code: str, extra: str = "") -> str:
    base = "You are a Senior University Professor producing rigorous academic summaries for university students preparing exams. The material can be from any discipline."
    parts = [base, language_instruction(lang_code), section_labels_block(lang_code)]
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def summarize_pdf_robust(
    client: OpenAI,
    pdf_name: str,
    pdf_text: str,
    status_container,
    lang_code: str,
    do_coverage_check: bool = True,
) -> str:
    """
    Gera resumo:
      • PDF pequeno (1 chunk): 1 chamada LLM
      • PDF grande (N chunks): N chamadas LLM (resume cada bloco)
      • Coverage check opcional (multi-chunk apenas):
          verifica se há lacunas e expande o resumo com tópicos em falta
    """
    chunks = chunk_text(pdf_text, max_chars=MAX_CHARS_PER_SUMMARY_CHUNK)
    summary_model = get_summary_model()
    full_system = _build_summary_system(lang_code)

    # SINGLE CHUNK ----------------------------------------------------------
    if len(chunks) == 1:
        status_container.write(t("summarizing", name=pdf_name, chars=len(chunks[0])))
        user_prompt = PROMPT_RESUMO_TEMPLATE.format(material=chunks[0])
        return stream_call_threaded(
            client, model=summary_model,
            system_prompt=full_system, user_prompt=user_prompt,
            container=status_container, temperature=0.4, max_tokens=6000,
            lang_code=lang_code,
        )

    # MULTI CHUNK -----------------------------------------------------------
    status_container.write(t("big_pdf_split", name=pdf_name, n=len(chunks)))
    parts: List[str] = []
    for i, ck in enumerate(chunks, start=1):
        status_container.write(
            t("chunk_progress", i=i, n=len(chunks), chars=len(ck))
            + " — " + random_fun_message(lang_code)
        )
        chunk_system = _build_summary_system(
            lang_code,
            extra=f"This text is part {i}/{len(chunks)} of a larger document. "
                  f"Summarise ONLY this block, exhaustively (do not omit anything from this block).",
        )
        user_prompt = PROMPT_RESUMO_TEMPLATE.format(material=ck)
        partial = stream_call_threaded(
            client, model=summary_model,
            system_prompt=chunk_system, user_prompt=user_prompt,
            container=status_container, temperature=0.4, max_tokens=5500,
            lang_code=lang_code,
        )
        parts.append(f"<!-- Block {i}/{len(chunks)} -->\n\n{partial}")

    combined = "\n\n---\n\n".join(parts)

    # COVERAGE CHECK (opcional) --------------------------------------------
    if not do_coverage_check:
        return combined

    status_container.write(t("checking_coverage") + " — " + random_fun_message(lang_code))
    coverage_prompt = PROMPT_COVERAGE_CHECK.format(
        ok_marker=COVERAGE_OK_MARKER,
        material=safe_truncate(pdf_text, MAX_CHARS_FOR_COVERAGE),
        summary=combined,
    )
    coverage_resp = stream_call_threaded(
        client, model=summary_model,
        system_prompt=full_system, user_prompt=coverage_prompt,
        container=status_container, temperature=0.15, max_tokens=2000,
        lang_code=lang_code,
    )

    first_line = coverage_resp.strip().split("\n", 1)[0].strip().upper()
    if first_line.startswith(COVERAGE_OK_MARKER):
        status_container.write(t("coverage_ok"))
        return combined

    # GAPS FOUND — expand ---------------------------------------------------
    status_container.write(t("coverage_gaps"))
    gaps = coverage_resp.strip().split("\n", 1)[-1].strip() if "\n" in coverage_resp else coverage_resp
    extension_prompt = PROMPT_GAP_FILLING.format(
        material=safe_truncate(pdf_text, MAX_CHARS_FOR_COVERAGE),
        summary=combined,
        gaps=gaps,
    )
    extension = stream_call_threaded(
        client, model=summary_model,
        system_prompt=full_system, user_prompt=extension_prompt,
        container=status_container, temperature=0.35, max_tokens=4000,
        lang_code=lang_code,
    )
    status_container.write(t("coverage_expanded"))
    sl = SECTION_LABELS_BY_LANG.get(lang_code, SECTION_LABELS_BY_LANG["pt"])
    return combined + f"\n\n---\n\n## ✨ {sl['cobertura']} (extended)\n\n" + extension


# =============================================================================
# 16. AUTO-PROCESSAMENTO DE UPLOADS
# =============================================================================
def auto_process_uploaded_pdfs(uploaded_files) -> None:
    api_key = st.session_state.nvidia_api_key
    lang_code = st.session_state.get("ui_language", "pt")
    do_cov = bool(st.session_state.get("coverage_check", True))
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

                summary_md = summarize_pdf_robust(client, f.name, raw_text, s, lang_code, do_coverage_check=do_cov)
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
    do_cov = bool(st.session_state.get("coverage_check", True))
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
            new_summary = summarize_pdf_robust(client, pdf_name, raw_text, s, lang_code, do_coverage_check=do_cov)
            entry["summary"] = new_summary
            entry["auto_generated"] = True
            entry["language"] = lang_code
            st.session_state.pdf_database[pdf_name] = entry
            s.update(label=t("regen_done", name=pdf_name), state="complete", expanded=False)
        except OpenAIError as e:
            s.markdown(friendly_api_error(e))
            s.update(label=t("regen_fail"), state="error", expanded=True)


# =============================================================================
# 17. CONSENSUS LOOP — 4 AGENTES, VEREDICT-FIRST
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


def run_eval_consensus(
    client: OpenAI,
    full_material: str,
    *,
    max_iterations: int,
    ui_container,
    lang_code: str,
) -> DebateResult:
    history: List[DebateEntry] = []
    lang_block = language_instruction(lang_code)

    # FASE 0 — Chefe V1 ----------------------------------------------------
    with ui_container.status(
        t("chefe_drafting") + " — " + random_fun_message(lang_code), expanded=True,
    ) as s:
        chefe_model = get_model("Chefe")
        s.write(f"`{chefe_model}`")
        system_prompt = EVAL_INITIAL_SYSTEM + "\n\n" + lang_block
        user_prompt = (
            "MATERIAL DE ESTUDO COMPLETO:\n\n"
            f"{full_material}\n\n---\n\nProduz agora o Teste de Revisão completo."
        )
        initial_draft = stream_call_threaded(
            client, model=chefe_model,
            system_prompt=system_prompt, user_prompt=user_prompt,
            container=s, temperature=0.35, max_tokens=5500, lang_code=lang_code,
        )
        s.update(label="✅ Chefe → V1", state="complete", expanded=False)

    history.append(DebateEntry(0, "Chefe", None, initial_draft, "draft"))

    current_author, current_content, version_number = "Chefe", initial_draft, 1

    # LOOP DE CONSENSO -----------------------------------------------------
    for iteration in range(1, max_iterations + 1):
        ui_container.markdown(
            f"<div class='round-tag'>{t('round_of', i=iteration, n=max_iterations, v=version_number, a=agent_display(current_author))}</div>",
            unsafe_allow_html=True,
        )
        validators_this_round = [a for a in AGENTS_ORDER if a != current_author]
        approvals_this_round: List[str] = []
        rewrite_happened = False

        for validator_name in validators_this_round:
            label = (t("validator_evaluating",
                       icon=AGENT_ICONS[validator_name], v=agent_display(validator_name),
                       n=version_number, a=agent_display(current_author))
                     + " — " + random_fun_message(lang_code))
            with ui_container.status(label, expanded=True) as s:
                v_model = get_model(validator_name)
                s.write(f"`{v_model}`")
                system_prompt = (
                    EVAL_VALIDATION_SYSTEMS[validator_name].format(
                        author=agent_display(current_author),
                        approve_marker=APPROVAL_MARKER,
                        rewrite_marker=REWRITE_MARKER,
                        block_marker=REWRITE_BLOCK_MARKER,
                    ) + "\n\n" + lang_block
                )
                user_prompt = (
                    "MATERIAL ORIGINAL:\n\n"
                    f"{full_material}\n\n---\n\n"
                    f"TESTE A AVALIAR (autoria: {agent_display(current_author)}, V{version_number}):\n\n"
                    f"{current_content}\n\n---\n\n"
                    f"DECIDE: começa por `{APPROVAL_MARKER}` ou `{REWRITE_MARKER}`."
                )
                response = stream_call_threaded(
                    client, model=v_model,
                    system_prompt=system_prompt, user_prompt=user_prompt,
                    container=s, temperature=0.1, max_tokens=5500, lang_code=lang_code,
                )

                if is_approval(response):
                    approvals_this_round.append(validator_name)
                    history.append(DebateEntry(iteration, validator_name, current_author, response, "approval"))
                    s.update(label=t("approved", v=agent_display(validator_name)),
                             state="complete", expanded=False)
                else:
                    rewritten = extract_rewrite(response)
                    history.append(DebateEntry(iteration, validator_name, current_author, response, "rewrite"))
                    version_number += 1
                    s.update(label=t("rewrote", v=agent_display(validator_name), n=version_number),
                             state="complete", expanded=False)
                    current_author, current_content = validator_name, rewritten
                    rewrite_happened = True
                    break  # próxima ronda começa com o novo autor

        if not rewrite_happened and len(approvals_this_round) == len(validators_this_round):
            others = ", ".join(agent_display(v) for v in validators_this_round)
            ui_container.markdown(
                f"<div class='consensus-banner'>{t('consensus_msg', i=iteration, v=version_number, a=agent_display(current_author), others=others)}</div>",
                unsafe_allow_html=True,
            )
            return DebateResult(
                final_content=current_content, final_author=current_author,
                history=history, consensus_reached=True, iterations_used=iteration,
            )

    ui_container.markdown(
        f"<div class='no-consensus-banner'>{t('no_consensus_msg', n=max_iterations, v=version_number, a=agent_display(current_author))}</div>",
        unsafe_allow_html=True,
    )
    return DebateResult(
        final_content=current_content, final_author=current_author,
        history=history, consensus_reached=False, iterations_used=max_iterations,
    )


# =============================================================================
# 18. SESSION STATE
# =============================================================================
DEFAULT_MAX_ITER = 4

st.session_state.setdefault("ui_language", "pt")
st.session_state.setdefault("nvidia_api_key", "")
st.session_state.setdefault("max_iterations", DEFAULT_MAX_ITER)
st.session_state.setdefault("agent_models", DEFAULT_MODELS.copy())
st.session_state.setdefault("summary_model", DEFAULT_SUMMARY_MODEL)
st.session_state.setdefault("coverage_check", True)
st.session_state.setdefault("pdf_database", {})
st.session_state.setdefault("eval_selected_pdfs", [])
st.session_state.setdefault("eval_result", None)
st.session_state.setdefault("_processed_signatures", set())

# Migrate state from v3.0 (3 agents → 4 agents)
_old_models = st.session_state.agent_models
if "Validador A" in _old_models or "Validador B" in _old_models or set(_old_models.keys()) != set(AGENTS_ORDER):
    st.session_state.agent_models = DEFAULT_MODELS.copy()

if not st.session_state.nvidia_api_key:
    try:
        secret_key = st.secrets.get("NVIDIA_API_KEY", "")
        if secret_key:
            st.session_state.nvidia_api_key = secret_key
    except Exception:
        pass


# =============================================================================
# 19. SIDEBAR
# =============================================================================
def model_selectbox(label: str, current_value: str, key: str) -> str:
    registry_keys = list(MODEL_REGISTRY.keys())
    options = registry_keys + [CUSTOM_MODEL_SENTINEL]
    if current_value in MODEL_REGISTRY:
        idx = registry_keys.index(current_value)
    else:
        idx = len(registry_keys)

    def _fmt(k: str) -> str:
        if k == CUSTOM_MODEL_SENTINEL:
            return CUSTOM_MODEL_SENTINEL
        return str(MODEL_REGISTRY[k]["label"])

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
        speed_4k = meta.get("est_seconds_4k", DEFAULT_SPEED_ESTIMATE_4K)
        speed_txt = f"<br>⏱ ~{speed_4k}s {t('model_speed')}/4k tok" if speed_4k else ""
        st.markdown(
            f"<div class='{css_class}'>{meta['best_for']}{speed_txt}</div>",
            unsafe_allow_html=True,
        )
        return str(chosen)


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
    st.caption("Plataforma Universitária · Multi-Agent AI")

    # --- Idioma -------------------------------------------------------------
    lang_options = list(LANGUAGES.keys())
    current_lang_idx = lang_options.index(st.session_state.ui_language) if st.session_state.ui_language in lang_options else 0
    new_lang = st.selectbox(
        t("language"), options=lang_options, index=current_lang_idx,
        format_func=lambda c: LANGUAGES[c]["label"],
        help=t("language_help"), key="lang_select",
    )
    if new_lang != st.session_state.ui_language:
        st.session_state.ui_language = new_lang
        st.rerun()

    st.divider()

    # --- ⚙️ Configurações --------------------------------------------------
    with st.expander(t("config"), expanded=not st.session_state.nvidia_api_key):
        api_key_input = st.text_input(
            t("api_key"), value=st.session_state.nvidia_api_key, type="password",
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

        coverage_input = st.checkbox(
            t("coverage_check_label"),
            value=st.session_state.coverage_check,
            help=t("coverage_check_help"),
        )
        if coverage_input != st.session_state.coverage_check:
            st.session_state.coverage_check = coverage_input

        st.markdown(f"**{t('summary_model_label')}**")
        new_sm = model_selectbox("", st.session_state.summary_model, "summary_model")
        if new_sm and new_sm != st.session_state.summary_model:
            st.session_state.summary_model = new_sm

        st.markdown(f"**{t('debate_models_label')}**")
        st.caption(t("model_404_hint"))
        for agent_name in AGENTS_ORDER:
            st.markdown(
                f"**{AGENT_ICONS[agent_name]} {agent_display(agent_name)}** "
                f"<span style='color:{ISEL_GRAY_11}; font-size:0.8rem'>· _{agent_role_description(agent_name)}_</span>",
                unsafe_allow_html=True,
            )
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
# 20. CABEÇALHO PRINCIPAL
# =============================================================================
st.markdown(
    f"""
    <div class="isel-banner">
        <h1>🎓 {t('app_title')}</h1>
        <p class="subtitle">{t('subtitle')}</p>
        <div>
            <span class="badge">{t('badge_universal')}</span>
            <span class="badge">{t('badge_multilang')}</span>
            <span class="badge">{t('badge_coverage')}</span>
            <span class="badge">{t('badge_4agents')}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 21. RENDERIZADORES
# =============================================================================
def render_agent_panel() -> None:
    cols = st.columns(4)
    for col, name in zip(cols, AGENTS_ORDER):
        with col:
            st.markdown(
                f"<div class='agent-card'>"
                f"<div class='role'>{AGENT_ICONS[name]} {agent_display(name)}</div>"
                f"<div class='role-desc'>{agent_role_description(name)}</div>"
                f"<div class='model'>{get_model(name)}</div>"
                f"</div>",
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
                tag = f"✅ → {agent_display(entry.target_author)}" if entry.target_author else "✅"
            else:
                tag = f"✏️ → {agent_display(entry.target_author)}" if entry.target_author else "✏️"
            st.markdown(f"**R{entry.iteration} · {icon} {agent_display(entry.author)}** — {tag}")
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
        st.caption(f"{t('final_authorship')}: **{AGENT_ICONS[result.final_author]} {agent_display(result.final_author)}**")
        with st.container(border=True):
            st.markdown(result.final_content)
        st.download_button(t("download_test"), data=result.final_content,
                           file_name="evaluation_test.md", mime="text/markdown", key="dl_eval_result")
        render_debate_history(result)


# =============================================================================
# 22. TABS PRINCIPAIS
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
