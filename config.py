"""
config.py — Constantes globais (Universal ScholarGPT v5.2)
===========================================================

Diferenças face à v5.1:
  ⭐ VISION_MODEL                — modelo NVIDIA NIM multimodal p/ OCR
  ⭐ MAX_RETRY_ATTEMPTS + delays — exponential backoff p/ 429/timeout
  ⭐ DEFAULT_DB_PATH             — caminho do SQLite (database.db)
"""

from typing import Dict, List

# ─────────────────────────────────────────────────────────────────────────────
# IDENTIDADE VISUAL — Paleta ISEL Bordeaux
# ─────────────────────────────────────────────────────────────────────────────
ISEL_PRIMARY     = "#9A3324"
ISEL_PRIMARY_DK  = "#7A271C"
ISEL_PRIMARY_LT  = "#C45A4A"
ISEL_GRAY_6      = "#A6A19E"
ISEL_GRAY_11     = "#6E6259"
ISEL_BG          = "#FAF7F4"
ISEL_SURFACE     = "#FFFFFF"
ISEL_BORDER      = "#E8E2DC"
ISEL_TEXT        = "#2A1F1A"
ISEL_SUCCESS     = "#5B7F4C"
ISEL_WARN        = "#C49A2E"
ISEL_DANGER      = "#B5443A"
ISEL_ACCENT      = "#4A6FA5"   # azul p/ "cached"

ISEL_LOGO_URL = (
    "https://www.isel.pt/themes/gavias_unix/images/"
    "01_ISEL-Logotipo-RGB_Horizontal-Principal-900.png"
)

APP_NAME = "Universal ScholarGPT"

# ─────────────────────────────────────────────────────────────────────────────
# PERSISTÊNCIA
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = "database.db"   # ⭐ v5.2

# ─────────────────────────────────────────────────────────────────────────────
# CSS (com novas classes v5.2: .cached-badge, .format-icon, .retry-banner)
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = f"""
<style>
.stApp {{ background-color: {ISEL_BG}; }}
.block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px; }}

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

.scholar-banner {{
    background: linear-gradient(135deg, {ISEL_PRIMARY} 0%, {ISEL_PRIMARY_DK} 100%);
    color: white; padding: 1.3rem 1.7rem; border-radius: 12px;
    margin-bottom: 1rem; box-shadow: 0 4px 14px rgba(154, 51, 36, 0.25);
}}
.scholar-banner h1 {{ color: white !important; margin: 0; font-size: 1.8rem; }}
.scholar-banner .subtitle {{ margin: 0.3rem 0 0 0; opacity: 0.92; font-size: 0.92rem; }}
.scholar-banner .badge {{
    display: inline-block; background: rgba(255,255,255,0.18);
    padding: 2px 10px; border-radius: 12px; font-size: 0.78rem;
    margin-right: 6px; margin-top: 0.5rem;
}}

.agent-card {{
    background-color: {ISEL_SURFACE}; border: 1px solid {ISEL_BORDER};
    border-radius: 10px; padding: 0.9rem 1.1rem; border-left: 4px solid {ISEL_PRIMARY};
}}
.agent-card .role {{ color: {ISEL_PRIMARY}; font-weight: 700; font-size: 0.95rem; }}
.agent-card .role-desc {{ color: {ISEL_GRAY_11}; font-size: 0.78rem; font-style: italic; margin: 0.15rem 0 0.3rem 0; }}

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

/* ⭐ v5.2 — Cached badge */
.cached-badge {{
    display: inline-block; background: {ISEL_ACCENT}; color: white;
    padding: 2px 9px; border-radius: 10px; font-size: 0.72rem;
    font-weight: 700; margin-left: 0.4rem;
}}

/* ⭐ v5.2 — Format icon pill */
.format-pill {{
    display: inline-block; background: {ISEL_BG}; color: {ISEL_PRIMARY};
    padding: 1px 8px; border-radius: 8px; font-size: 0.74rem;
    font-weight: 600; margin-right: 0.4rem;
    border: 1px solid {ISEL_BORDER};
}}

/* ⭐ v5.2 — Retry banner */
.retry-banner {{
    background: linear-gradient(90deg, rgba(196, 154, 46, 0.20) 0%, rgba(196, 154, 46, 0.05) 100%);
    border-left: 4px solid {ISEL_WARN};
    padding: 0.7rem 1rem; border-radius: 6px;
    font-size: 0.9rem; color: {ISEL_TEXT};
}}

.quiz-try-first {{
    background: linear-gradient(90deg, rgba(196, 154, 46, 0.15) 0%, rgba(196, 154, 46, 0.05) 100%);
    border-left: 4px solid {ISEL_WARN};
    padding: 0.85rem 1.1rem; border-radius: 6px; margin: 1rem 0 0.6rem 0;
    color: {ISEL_TEXT}; font-size: 0.92rem;
}}
.answers-revealed {{
    background: linear-gradient(90deg, rgba(91, 127, 76, 0.15) 0%, rgba(91, 127, 76, 0.05) 100%);
    border-left: 4px solid {ISEL_SUCCESS};
    padding: 0.85rem 1.1rem; border-radius: 6px; margin: 1rem 0 0.6rem 0;
    color: {ISEL_TEXT}; font-size: 0.92rem;
}}

.debate-log-entry {{
    background: {ISEL_BG}; border-radius: 8px;
    padding: 0.7rem 0.95rem; margin-bottom: 0.55rem;
    border-left: 4px solid {ISEL_GRAY_6};
    font-size: 0.88rem;
}}
.debate-log-entry.draft {{ border-left-color: {ISEL_PRIMARY}; }}
.debate-log-entry.approve {{ border-left-color: {ISEL_SUCCESS}; background: rgba(91, 127, 76, 0.06); }}
.debate-log-entry.rewrite {{ border-left-color: {ISEL_WARN};   background: rgba(196, 154, 46, 0.07); }}
.debate-log-entry .head {{ color: {ISEL_TEXT}; font-weight: 600; margin-bottom: 0.2rem; }}
.debate-log-entry .decision-badge {{
    display: inline-block; padding: 1px 8px; border-radius: 10px;
    font-size: 0.75rem; font-weight: 700; margin-left: 0.4rem;
}}
.debate-log-entry .decision-badge.approve {{ background: {ISEL_SUCCESS}; color: white; }}
.debate-log-entry .decision-badge.rewrite {{ background: {ISEL_WARN}; color: white; }}
.debate-log-entry .decision-badge.draft   {{ background: {ISEL_PRIMARY}; color: white; }}
.debate-log-entry .reason {{
    color: {ISEL_GRAY_11}; font-size: 0.82rem; font-style: italic;
    margin-top: 0.25rem; line-height: 1.4;
}}

.coverage-badge {{
    display: inline-block; padding: 2px 9px; border-radius: 10px;
    font-size: 0.72rem; font-weight: 600; margin-left: 0.4rem;
}}
.coverage-badge.ok           {{ background: {ISEL_SUCCESS}; color: white; }}
.coverage-badge.gaps_filled  {{ background: {ISEL_PRIMARY}; color: white; }}
.coverage-badge.skipped      {{ background: {ISEL_GRAY_6};  color: white; }}
.coverage-badge.pending      {{ background: {ISEL_WARN};    color: white; }}

.how-to-use {{
    background: linear-gradient(135deg, rgba(154, 51, 36, 0.06) 0%, rgba(154, 51, 36, 0.02) 100%);
    border: 1px solid {ISEL_BORDER};
    border-left: 4px solid {ISEL_PRIMARY};
    padding: 0.85rem 1rem; border-radius: 8px; margin: 0.6rem 0 1rem 0;
}}
.how-to-use .h2u-title {{
    color: {ISEL_PRIMARY}; font-weight: 700; font-size: 1.0rem;
    margin-bottom: 0.5rem;
}}
.how-to-use ol {{ margin: 0; padding-left: 1.4rem; color: {ISEL_TEXT}; font-size: 0.88rem; }}
.how-to-use ol li {{ margin-bottom: 0.35rem; }}
.how-to-use a {{ color: {ISEL_PRIMARY}; font-weight: 600; text-decoration: underline; }}

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

# ─────────────────────────────────────────────────────────────────────────────
# NVIDIA NIM
# ─────────────────────────────────────────────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODEL_REGISTRY: Dict[str, Dict[str, object]] = {
    "nvidia/nemotron-3-super-120b-a12b": {
        "label": "🥇 NVIDIA Nemotron 3 Super 120B-A12B",
        "best_for": "Flagship NVIDIA. MoE 120B (12B activos), 1M de contexto. Excelente Chefe Redator.",
        "est_seconds_4k": 90,
    },
    "minimaxai/minimax-m2.7": {
        "label": "💼 MiniMax M2.7 (230B)",
        "best_for": "Eng. de software, agentic longo. Ótimo Verificador Pedagógico.",
        "est_seconds_4k": 70,
    },
    "moonshotai/kimi-k2.6": {
        "label": "📚 Moonshot Kimi K2.6",
        "best_for": "Contexto enorme, síntese de documentos. Ideal para PDFs grandes.",
        "est_seconds_4k": 100,
    },
    "deepseek-ai/deepseek-v4-pro": {
        "label": "📐 DeepSeek V4 Pro",
        "best_for": "Top em matemática, código. Excelente Verificador Técnico.",
        "est_seconds_4k": 80,
    },
    "deepseek-ai/deepseek-v4-flash": {
        "label": "⚡ DeepSeek V4 Flash",
        "best_for": "Versão rápida do V4 Pro. Boa qualidade, latência baixa.",
        "est_seconds_4k": 40,
    },
    "z-ai/glm-5.1": {
        "label": "🛠️ Zhipu GLM-5.1",
        "best_for": "200K contexto, 128K output. Coding agentic.",
        "est_seconds_4k": 75,
    },
    "google/gemma-4-31b-it": {
        "label": "🌐 Google Gemma 4 31B (IT)",
        "best_for": "Multimodal, multilingue, 256K contexto. Forte em PT-PT.",
        "est_seconds_4k": 50,
    },
    "openai/gpt-oss-120b": {
        "label": "🧠 OpenAI GPT-OSS 120B",
        "best_for": "Open-weight da OpenAI. Sólido em raciocínio geral.",
        "est_seconds_4k": 80,
    },
    "stepfun-ai/step-3.7-flash": {
        "label": "⚡ StepFun Step-3.7 Flash",
        "best_for": "Inferência muito rápida. Ideal para Aluno Crítico.",
        "est_seconds_4k": 30,
    },
    "stepfun-ai/step-3.5-flash": {
        "label": "⚡ StepFun Step-3.5 Flash",
        "best_for": "Versão anterior do Step Flash.",
        "est_seconds_4k": 30,
    },
    "google/gemma-3n-e2b-it": {
        "label": "📱 Google Gemma 3n E2B (IT) — ultra-leve",
        "best_for": "2B params via PLE. Validador de último recurso.",
        "est_seconds_4k": 20,
    },
    "nvidia/llama-nemotron-embed-1b-v2": {
        "label": "⚠️ Nemotron Embed 1B v2 — NÃO USAR",
        "best_for": "❌ MODELO DE EMBEDDINGS. Não consegue gerar texto.",
        "warn": True,
        "est_seconds_4k": 0,
    },
}

CUSTOM_MODEL_SENTINEL     = "✏️ Personalizado…"
DEFAULT_SPEED_ESTIMATE_4K = 60

# ─────────────────────────────────────────────────────────────────────────────
# ⭐ v5.2 — Vision LLM (multimodal p/ OCR de PDFs digitalizados/imagens)
# ─────────────────────────────────────────────────────────────────────────────
# Modelo NVIDIA NIM multimodal. Verifica no teu catálogo NVIDIA quais estão
# disponíveis (alguns dos comuns: microsoft/phi-3-vision-128k-instruct,
# meta/llama-3.2-90b-vision-instruct, google/gemma-3-27b-it-vision).
VISION_MODEL_DEFAULT = "meta/llama-3.2-90b-vision-instruct"
VISION_MODEL_FALLBACKS = [
    "microsoft/phi-3-vision-128k-instruct",
    "google/gemma-3-27b-it-vision",
]
VISION_MAX_TOKENS = 2000
VISION_TEMPERATURE = 0.1

# ─────────────────────────────────────────────────────────────────────────────
# ⭐ v5.2 — Retry com Exponential Backoff (spec §1)
# ─────────────────────────────────────────────────────────────────────────────
MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0       # segundos; dobra a cada tentativa (2, 4, 8…)
RETRY_MAX_DELAY = 30.0       # cap por tentativa
RETRY_ON_PATTERNS = (        # substrings em str(exc) que disparam retry
    "429", "rate limit", "too many requests", "quota",
    "timeout", "timed out", "connection",
    "503", "502", "504", "service unavailable",
)

# ─────────────────────────────────────────────────────────────────────────────
# 4 AGENTES
# ─────────────────────────────────────────────────────────────────────────────
AGENTS_ORDER: List[str] = [
    "Chefe", "Verificador Técnico", "Verificador Pedagógico", "Aluno Crítico",
]

AGENT_ICONS: Dict[str, str] = {
    "Chefe":                  "👑",
    "Verificador Técnico":    "🔬",
    "Verificador Pedagógico": "🎓",
    "Aluno Crítico":          "🧑‍🎓",
}

DEFAULT_MODELS: Dict[str, str] = {
    "Chefe":                  "nvidia/nemotron-3-super-120b-a12b",
    "Verificador Técnico":    "deepseek-ai/deepseek-v4-pro",
    "Verificador Pedagógico": "minimaxai/minimax-m2.7",
    "Aluno Crítico":          "stepfun-ai/step-3.7-flash",
}
DEFAULT_SUMMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# ─────────────────────────────────────────────────────────────────────────────
# MARCADORES UNIVERSAIS
# ─────────────────────────────────────────────────────────────────────────────
APPROVAL_MARKER       = "DECISION: APPROVE"
REWRITE_MARKER        = "DECISION: REWRITE"
REWRITE_BLOCK_MARKER  = "--- REWRITTEN TEST ---"
LEGACY_APPROVAL_TOKEN = "[UNANIMIDADE]"
COVERAGE_OK_MARKER    = "COVERAGE_OK"
COVERAGE_GAPS_MARKER  = "COVERAGE_GAPS"
ANSWERS_SEPARATOR     = "=== RESPOSTAS ==="

# ─────────────────────────────────────────────────────────────────────────────
# LIMITES
# ─────────────────────────────────────────────────────────────────────────────
MAX_CHARS_PER_SUMMARY_CHUNK = 60_000
MAX_CHARS_FOR_EVAL_INPUT    = 120_000
MAX_CHARS_FOR_COVERAGE      = 80_000
HARD_TRUNCATE_MARGIN        = 200
DEFAULT_MAX_ITERATIONS      = 4

# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING
# ─────────────────────────────────────────────────────────────────────────────
NVIDIA_API_KEY_URL = "https://build.nvidia.com/explore/discover"
