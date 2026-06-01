# --------------------------------------------------------------
# app.py – ISEL Análise de Custos (Multi‑Agent Consensus)
# --------------------------------------------------------------
# Author: Senior Software Engineer – Python / Streamlit / LLM Prompt Engineering
# --------------------------------------------------------------

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import streamlit as st
import fitz                     # <-- PyMuPDF (fitz) instead of pypdf
from openai import OpenAI, OpenAIError

# =============================================================================
# 1. CONSTANTS & PROMPTS
# =============================================================================
ISEL_PRIMARY   = "#004b87"   # Azul institucional
ISEL_BG        = "#f5f7fa"   # Fundo claro
ISEL_SURFACE   = "#ffffff"   # Superfície branca
ISEL_LOGO_URL  = "https://www.isel.pt/sites/default/files/logo_ISEL_0.png"

# ----- Prompt for automatic summaries (one per PDF chunk) -----
PROMPT_RESUMO = """Atua como um Professor Catedrático, Investigador e Coordenador de Mestrado com mais de 20 anos de experiência académica e pedagógica rigorosa. A tua missão é transformar o material técnico fornecido num Resumo Académico de Alto Nível, desenhado especificamente para estudantes de pós-graduação que exigem profundidade analítica, pormenorização metodológica e precisão conceptual absoluta para preparação de exames complexos.

Adota um tom pedagógico que seja simultaneamente ultra-claro, conciso, objetivo e profundamente explicativo. Não omitas detalhes técnicos, premissas latentes ou passos lógicos. Explica exaustivamente o "porquê", o "como" e o nexo de causalidade de cada mecanismo, modelo ou teoria económica/industrial.

Garante que a estrutura do resumo respeita estritamente os seguintes critérios de formatação em Markdown:

1. ESTRUTURA DOS CAPÍTULOS / BLOCOS TEMÁTICOS:
Para cada tema, capítulo ou secção identificável no texto, gera uma secção estruturada exatamente com as seguintes marcações:

   * **🎯 Foco Principal:** Uma frase cirúrgica, densa e altamente condensada que defina o objetivo central, a utilidade estratégica ou o problema fundamental que o capítulo se propõe resolver.

   * **🧠 Conceitos-Chave e Dissecção Teórica:** Explicações pormenorizadas e profundas de todos os termos técnicos, premissas, teoremas ou perspetivas teóricas. Utiliza uma taxonomia hierárquica rigorosa com sub‑tópicos (bullets encadeados) para dissecar sub‑conceitos, analisar trade‑offs, limitações das teorias e impactos operacionais. Não uses resumos generalists; vai ao detalhe anatómico do conceito.

   * **🧮 Fórmulas, Metodologias e Deduções:** Apresenta todas as equações matemáticas, algoritmos, matrizes ou frameworks de cálculo de forma explícita. É OBRIGATÓRIO o uso de sintaxe LaTeX: usa $...$ para equações na linha de texto e $$...$$ para blocos de equações isolados e destacados. Logo após a fórmula, define detalhadamente o significado científico e a unidade de cada variável matemática utilizada. Se o texto original descrever uma relação quantitativa de forma textual, traduz essa relação numa fórmula matemática formal em LaTeX.

   * **🏭 Aplicação Prática e Estudos de Caso:** Cria ou extrai um cenário detalhado do mundo real (contexto industrial, empresarial, de engenharia ou caso de estudo económico‑financeiro) que demonstre a aplicação prática e exata da teoria e das fórmulas explicadas acima, apresentando valores numéricos ilustrativos coerentes sempre que aplicável.

   * **🎓 Dica do Catedrático (Rigor de Exame):** Um insight académico crítico, um "pulo do gato" metodológico, ou um alerta severo e explícito para as armadilhas conceituais e os erros mais comuns que os alunos de Mestrado cometem em ambiente de exame ao resolver problemas sobre esta matéria.

2. REGRAS DE CONTEXTO, IDIOMA E FORMATO:
- Linguagem: Escreve exclusivamente em Português Europeu (PT‑PT) formal, técnico e de nível universitário avançado.
- Densidade de Informação Absoluta: Rejeita qualquer tipo de "palha", preâmbulos introdutórios (ex: "Aqui está o resumo solicitado...") ou conclusões genéricos. Entrega diretamente o código Markdown puro do resumo estruturado.
- Cobertura Inclusiva: Garante que 100% dos dados relevantes, nuances e variáveis presentes no texto de input sejam totalmente mapeados e expandidos no output, sem simplificações preguiçosas."""
# --------------------------------------------------------------
# Prompts for the evaluation test (Chief + Validators)
# --------------------------------------------------------------
CHIEF_TEST_PROMPT = """Você é o **Chefe** – Professor Catedrático de Análise de Custos do ISEL.
Com base exclusivamente no material abaixo, gere:
- 10 questões de múltipla escolha (cada uma com 4 alternativas e a indicação da correta)
- 2 exercícios práticos de desenvolvimento, com resolução passo‑a‑passo e todos os cálculos explícitos.

Seja objetivo, direto e não introduza texto explicativo além do necessário para a formulação das questões e dos exercícios.
Use a língua portuguesa de Portugal (PT‑PT).

MATERIAL:
---
{material}
---
"""

VALIDATOR_PROMPT = """Você é **{validator}**, um revisor académico extremamente rigoroso de Análise de Custos do ISEL.

⚠️ REGRA DE OURO: vais avaliar um Teste de Revisão produzido por **{author}**. Este NÃO é o teu trabalho. NUNCA podes avaliar uma versão da tua autoria.

A TUA DECISÃO É BINÁRIA:

▶ OPÇÃO 1 – APROVAR:
   Se o teste está à prova de bala – cálculos certos, sem ambiguidades, cobertura adequada – responde EXATAMENTE com a linha:
   {token}
   Seguido de 1 a 3 frases a justificar a aprovação.
   NÃO incluas mais nada.

▶ OPÇÃO 2 – REESCREVER:
   Se houver QUALQUER falha (erro de cálculo, ambiguidade, enunciado pouco claro, distrator inadequado):
   - NÃO uses a palavra {token} em lado nenhum.
   - Reescreve o teste COMPLETO em Markdown, mantendo a mesma estrutura (Parte I + Parte II + soluções) e aplicando as tuas correções.
   - Devolve APENAS o teste reescrito, sem comentários.

Português Europeu. Sê implacável com erros matemáticos.

MATERIAL DE REFERÊNCIA (para caso precises de conferir dados):
---
{material}
---

TESTE A AVALIAR:
---
{test}
---
"""

UNANIMITY_TOKEN = "[UNANIMIDADE]"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# --------------------------------------------------------------
# 2. HELPER FUNCTIONS
# =============================================================================
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts raw text from a PDF using PyMuPDF (fitz)."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = []
    for page in doc:
        text.append(page.get_text())
    return "\n".join(text)


def chunk_text(text: str, max_chars: int = 3000) -> List[str]:
    """
    Splits text into chunks of <= max_chars characters,
    trying to break on whitespace or new‑line to avoid cutting words.
    """
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        # try to find a space or newline near the end
        if end < n:
            cut = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if cut <= start:          # no suitable break → cut hard
                cut = end
        else:
            cut = end
        chunk = text[start:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = cut
        # skip leading whitespace of next chunk
        while start < n and text[start] in " \n\r\t":
            start += 1
    return chunks


def get_nvidia_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def call_llm(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """Synchronous call to the NVIDIA NIM (OpenAI‑compatible) API."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def friendly_api_error(err: Exception) -> str:
    """Turns NVIDIA API errors into user‑friendly messages."""
    msg = str(err)
    lower = msg.lower()
    if "404" in msg or "not found" in lower:
        return (
            "❌ **Modelo não encontrado na tua conta NVIDIA.**\n"
            "Verifica o nome do modelo nas **⚙️ Configurações → 🤖 Modelos dos Agentes**. "
            "Exemplos que geralmente funcionam:\n"
            "- `meta/llama-3.3-70b-instruct`\n"
            "- `meta/llama-3.1-70b-instruct`\n"
            "- `mistralai/mistral-large-2-instruct`\n"
            "- `meta/llama-3.1-8b-instruct`\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "401" in msg or "unauthorized" in lower:
        return (
            "❌ **Chave NVIDIA inválida ou expirada.**\n"
            "Confere a chave em **⚙️ Configurações** (deve começar por `nvapi-`).\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "429" in msg or "rate" in lower:
        return (
            "⏱️ **Limite de pedidos atingido.** Aguarda alguns segundos e tenta de novo.\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    return f"❌ Erro da API NVIDIA: {msg}"


# =============================================================================
# 3. DATA MODELS & CONSENSUS LOGIC
# =============================================================================
@dataclass
class PDFDoc:
    name: str
    raw_text: str
    summary: str   # concatenated summary of all chunks


@dataclass
class DebateEntry:
    iteration: int          # 0 = initial draft
    author: str             # who produced this content
    target_author: Optional[str]  # whose version is being judged
    content: str
    kind: str               # "draft" | "approval" | "rewrite"


@dataclass
class DebateResult:
    final_content: str
    final_author: str
    history: List[DebateEntry] = field(default_factory=list)
    consensus_reached: bool = False
    iterations_used: int = 0


def is_approval(response: str) -> bool:
    return UNANIMITY_TOKEN.upper() in response.strip().upper()[:300]


def run_consensus_loop(
    client: OpenAI,
    material: str,
    *,
    task: str,
    max_iterations: int,
    status_container,
) -> DebateResult:
    """
    Generic consensus loop used for both summary and evaluation.
    For summary we use PROMPT_RESUMO per chunk (handled elsewhere);
    for evaluation we use CHIEF_TEST_PROMPT / VALIDATOR_PROMPT.
    """
    if task == "summary":
        # This path is not used – summaries are generated chunk‑wise before consensus.
        raise ValueError("Summary consensus is handled outside this function.")
    elif task == "evaluation":
        initial_system = "Você é um professor que gera provas objetivas e claras."
        validation_system_tpl = VALIDATOR_PROMPT
        task_label = "Teste de Revisão"
    else:
        raise ValueError(f"Unknown task: {task}")

    history: List[DebateEntry] = []

    # ----- CHIEF creates initial draft -----
    with status_container.status(
        f"👑 **Chefe** a criar o rascunho inicial de **{task_label}**…",
        expanded=True,
    ) as s:
        chief_model = st.session_state.agent_models["Chefe"]
        s.write(f"Modelo: `{chief_model}`")
        user_prompt = CHIEF_TEST_PROMPT.format(material=material)
        draft = call_llm(
            client,
            model=chief_model,
            system_prompt=initial_system,
            user_prompt=user_prompt,
            temperature=0.35,
            max_tokens=2000,
        )
        s.update(label="✅ **Chefe** entregou o rascunho V1", state="complete", expanded=False)

    history.append(
        DebateEntry(iteration=0, author="Chefe", target_author=None, content=draft, kind="draft")
    )

    current_author = "Chefe"
    current_content = draft
    version_number = 1

    # ----- Iterative validation rounds -----
    for it in range(1, max_iterations + 1):
        status_container.markdown(
            f"<div class='round-tag'>🔄 Ronda {it} de {max_iterations}</div>",
            unsafe_allow_html=True,
        )
        validators = [a for a in ["Chefe", "Validador A", "Validador B"] if a != current_author]
        approvals: List[str] = []
        rewrite_happened = False

        for validator_name in validators:
            with status_container.status(
                f"{'🅰️' if validator_name == 'Validador A' else '🅱️' if validator_name == 'Validador B' else '👑'} "
                f" **{validator_name}** a avaliar V{version_number} de **{current_author}**…",
                expanded=True,
            ) as s:
                validator_model = st.session_state.agent_models[validator_name]
                s.write(f"Modelo: `{validator_model}`")
                system_prompt = validation_system_tpl.format(
                    validator=validator_name,
                    author=current_author,
                    token=UNANIMITY_TOKEN,
                    material=material,
                    test=current_content,
                )
                user_prompt = ""  # already included in system_prompt for clarity
                response = call_llm(
                    client,
                    model=validator_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    max_tokens=512,   # keep validation short
                )
                if is_approval(response):
                    approvals.append(validator_name)
                    history.append(
                        DebateEntry(
                            iteration=it,
                            author=validator_name,
                            target_author=current_author,
                            content=response,
                            kind="approval",
                        )
                    )
                    s.update(
                        label=f"✅ **{validator_name}** aprovou ({UNANIMITY_TOKEN})",
                        state="complete",
                        expanded=False,
                    )
                else:
                    history.append(
                        DebateEntry(
                            iteration=it,
                            author=validator_name,
                            target_author=current_author,
                            content=response,
                            kind="rewrite",
                        )
                    )
                    version_number += 1
                    s.update(
                        label=(
                            f"✏️ **{validator_name}** propôs alterações "
                            f"(nova versão V{version_number})"
                        ),
                        state="complete",
                        expanded=False,
                    )
                    current_author = validator_name
                    current_content = response
                    rewrite_happened = True
                    break  # break validator loop – we have a new author

        if not rewrite_happened and len(approvals) == len(validators):
            status_container.markdown(
                f"<div class='consensus-banner'>🎉 Consenso atingido na ronda {it}! "
                f"V{version_number} de {current_author} foi unanimemente aprovada por "
                f"{', '.join(validators)}.</div>",
                unsafe_allow_html=True,
            )
            return DebateResult(
                final_content=current_content,
                final_author=current_author,
                history=history,
                consensus_reached=True,
                iterations_used=it,
            )

    # max iterations reached without consensus
    status_container.markdown(
        f"<div class='no-consensus-banner'>⏱️ Limite de {max_iterations} rondas atingido sem consenso. "
        f"Devolvida a última versão (V{version_number}, autoria de {current_author}).</div>",
        unsafe_allow_html=True,
    )
    return DebateResult(
        final_content=current_content,
        final_author=current_author,
        history=history,
        consensus_reached=False,
        iterations_used=max_iterations,
    )


# =============================================================================
# 4. SESSION STATE INITIALISATION
# =============================================================================
def init_session_state():
    if "pdf_docs" not in st.session_state:
        st.session_state.pdf_docs: List[PDFDoc] = []   # stored PDFs
    if "nvidia_api_key" not in st.session_state:
        st.session_state.nvidia_api_key = ""
    if "max_iterations" not in st.session_state:
        st.session_state.max_iterations = 4
    if "agent_models" not in st.session_state:
        st.session_state.agent_models = {
            "Chefe":       "meta/llama-3.3-70b-instruct",
            "Validador A": "mistralai/mistral-large-2-instruct",
            "Validador B": "meta/llama-3.1-70b-instruct",
        }
    if "summary_result" not in st.session_state:
        st.session_state.summary_result = None  # not used (summaries are per PDF)
    if "eval_result" not in st.session_state:
        st.session_state.eval_result = None
    # Try to load key from secrets
    if not st.session_state.nvidia_api_key:
        try:
            sk = st.secrets.get("NVIDIA_API_KEY", "")
            if sk:
                st.session_state.nvidia_api_key = sk
        except Exception:
            pass


init_session_state()


# =============================================================================
# 5. PAGE CONFIG & CUSTOM CSS (ISEL identity)
# =============================================================================
st.set_page_config(
    page_title="Análise de Custos | ISEL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = f"""
<style>
/* Base */
.stApp {{ background-color: {ISEL_BG}; }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}

/* Typography */
h1, h2, h3, h4 {{ color: {ISEL_PRIMARY} !important; font-weight: 700; }}
h1 {{ letter-spacing: -0.02em; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background-color: {ISEL_SURFACE}; border-right: 1px solid #e0e6ed; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {ISEL_PRIMARY} !important; }}

/* Buttons */
.stButton > button, .stDownloadButton > button {{
    background-color: {ISEL_PRIMARY}; color: white !important;
    border: none; border-radius: 6px; padding: 0.55rem 1.4rem;
    font-weight: 600; transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(0, 75, 135, 0.15);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    background-color: {ISEL_PRIMARY}00; /* slightly darker */
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 75, 135, 0.25); color: white !important;
}}
.stButton > button:disabled {{ background-color: #b0bcc8; color: white !important; transform: none; cursor: not-allowed; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background-color: {ISEL_SURFACE}; padding: 6px;
    border-radius: 10px; border: 1px solid #e0e6ed; overflow-x: auto;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: transparent; border-radius: 7px;
    padding: 0.45rem 1rem; color: #1a2332; font-weight: 500;
}}
.stTabs [data-baseweb="tab"]:hover {{ background-color: rgba(0,75,135,0.06); }}
.stTabs [aria-selected="true"] {{ background-color: {ISEL_PRIMARY} !important; color: white !important; }}

/* Inputs */
.stTextInput input, .stTextArea textarea {{
    border-radius: 6px; border: 1px solid #e0e6ed;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {ISEL_PRIMARY}; box-shadow: 0 0 0 2px rgba(0,75,135,0.15);
}}

/* Expander */
.stExpander {{ border-radius: 8px; border: 1px solid #e0e6ed; background-color: {ISEL_SURFACE}; }}

/* Banner ISEL */
.isel-banner {{
    background: linear-gradient(135deg, {ISEL_PRIMARY} 0%, {ISEL_PRIMARY}00 100%);
    color: white; padding: 1.5rem 2rem; border-radius: 12px;
    margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(0,75,135,0.2);
}}
.isel-banner h1 {{ color: white !important; margin: 0; font-size: 1.9rem; }}
.isel-banner p {{ margin: 0.25rem 0 0 0; opacity: 0.92; font-size: 0.95rem; }}

/* Section title (small accent bar) */
.section-title {{
    color: {ISEL_PRIMARY}; font-weight: 700; font-size: 1.05rem;
    margin: 1.25rem 0 0.6rem 0; display: flex; align-items: center; gap: 0.5rem;
}}
.section-title::before {{
    content: ""; width: 4px; height: 18px; background: {ISEL_PRIMARY}; border-radius: 2px;
}}

/* Agent cards */
.agent-card {{
    background-color: {ISEL_SURFACE}; border: 1px solid #e0e6ed;
    border-radius: 10px; padding: 1rem 1.1rem;
    border-left: 4px solid {ISEL_PRIMARY};
}}
.agent-card .role {{ color: {ISEL_PRIMARY}; font-weight: 700; }}
.agent-card .model {{ color: #6c757d; font-size: 0.82rem; font-family: ui-monospace, monospace; word-break: break-all; }}

.round-tag {{
    display: inline-block; background: {ISEL_PRIMARY}; color: white;
    padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;
    margin-bottom: 0.5rem;
}}
.consensus-banner {{
    background: linear-gradient(135deg, #198754 0%, #146c43 100%);
    color: white; padding: 1rem 1.3rem; border-radius: 10px;
    font-weight: 600; margin: 1rem 0;
}}
.no-consensus-banner {{
    background: linear-gradient(135deg, #e0a800 0%, #b88a00 100%);
    color: white; padding: 1rem 1.3rem; border-radius: 10px;
    font-weight: 600; margin: 1rem 0;
}}

/* Sidebar pill (shortcut to IA tabs) */
.sidebar-pill {{
    display: block; background: {ISEL_BG}; border: 1px solid #e0e6ed;
    border-left: 3px solid {ISEL_PRIMARY};
    padding: 0.55rem 0.85rem; border-radius: 6px;
    margin-bottom: 0.4rem; font-weight: 600; color: {ISEL_PRIMARY};
    font-size: 0.9rem;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =============================================================================
# 6. HEADER
# =============================================================================
st.markdown(
    f"""
    <div class="isel-banner">
        <h1>📊 Análise de Custos</h1>
        <p>Plataforma de estudo interativa · Instituto Superior de Engenharia de Lisboa</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 7. SIDEBAR
# =============================================================================
with st.sidebar:
    st.markdown(
        f"<h2 style='color:{ISEL_PRIMARY};margin-top:0'>📊 Análise de Custos</h2>"
        f"<p style='color:#6c757d;margin-top:-0.5rem;font-size:0.9rem'>"
        f"ISEL · Plataforma de Estudo</p>",
        unsafe_allow_html=True,
    )

    # ---- Configuration ----------------------------------------------------
    with st.expander("⚙️ Configurações", expanded=not st.session_state.nvidia_api_key):
        api_key_input = st.text_input(
            "🔑 NVIDIA API Key",
            value=st.session_state.nvidia_api_key,
            type="password",
            placeholder="nvapi-…",
            help="Chave obtida em https://build.nvidia.com",
        )
        if api_key_input != st.session_state.nvidia_api_key:
            st.session_state.nvidia_api_key = api_key_input

        max_iter_input = st.slider(
            "🔁 Máximo de rondas de debate",
            min_value=2,
            max_value=10,
            value=st.session_state.max_iterations,
            help="Número máximo de iterações no loop de consenso entre os agentes.",
        )
        if max_iter_input != st.session_state.max_iterations:
            st.session_state.max_iterations = max_iter_input

        # Model selectors
        st.markdown("**🤖 Modelos dos Agentes**")
        st.caption(
            "Se aparecer um erro 404, altere aqui para um modelo disponível na tua conta."
        )
        for agent in ["Chefe", "Validador A", "Validador B"]:
            new_val = st.text_input(
                f"{'👑' if agent == 'Chefe' else '🅰️' if agent == 'Validador A' else '🅱️'} {agent}",
                value=st.session_state.agent_models[agent],
                key=f"model_input_{agent}",
                help=f"Modelo NVIDIA NIM para o agente {agent}.",
            )
            st.session_state.agent_models[agent] = new_val.strip()

        col_rst1, col_rst2 = st.columns(2)
        with col_rst1:
            if st.button("↺ Repor defaults", use_container_width=True, key="reset_models"):
                st.session_state.agent_models = {
                    "Chefe":       "meta/llama-3.3-70b-instruct",
                    "Validador A": "mistralai/mistral-large-2-instruct",
                    "Validador B": "meta/llama-3.1-70b-instruct",
                }
                st.rerun()
        with col_rst2:
            st.caption(" ")

        if st.session_state.nvidia_api_key:
            st.success("🔒 Chave carregada – IA ativa", icon="✅")
        else:
            st.warning("Sem chave – Tabs de IA estão desativadas.", icon="⚠️")

    st.divider()

    # ---- PDF Upload -------------------------------------------------------
    st.markdown("##### 📁 Upload de PDFs")
    uploaded_files = st.file_uploader(
        "Arraste ou selecione um ou mais PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        signature = tuple((f.name, f.size) for f in uploaded_files)
        if signature != st.session_state.get("files_signature"):
            # Process each newly uploaded file
            for up_file in uploaded_files:
                # Avoid reprocessing same file (by name)
                if any(doc.name == up_file.name for doc in st.session_state.pdf_docs):
                    continue
                with st.status(f"📥 Processando **{up_file.name}** …", expanded=True) as status:
                    try:
                        bytes_data = up_file.read()
                        status.update(label="🔎 Extraindo texto do PDF …")
                        raw_text = extract_text_from_pdf(bytes_data)
                        status.update(label="✂️ Dividindo em blocos seguros …")
                        chunks = chunk_text(raw_text)
                        status.update(label="🧠 Gerando resumos com IA …")
                        summaries: List[str] = []
                        for idx, chunk in enumerate(chunks, start=1):
                            prompt = PROMPT_RESUMO.format(chunk_texto_extraido_do_pdf=chunk)
                            try:
                                part = call_llm(
                                    client=get_nvidia_client(st.session_state.nvidia_api_key),
                                    model=st.session_state.agent_models["Chefe"],
                                    system_prompt="Você é um assistente que segue instruções à risca.",
                                    user_prompt=prompt,
                                    temperature=0.2,
                                    max_tokens=1024,
                                )
                            except Exception as e:
                                st.warning(
                                    f"⚠️ Falha ao resumir bloco {idx}/{len(chunks)}: {friendly_api_error(e)}"
                                )
                                part = ""  # continue with empty to avoid breaking flow
                            summaries.append(part)
                        full_summary = "\n\n---\n\n".join([s for s in summaries if s])
                        # Store
                        st.session_state.pdf_docs.append(
                            PDFDoc(name=up_file.name, raw_text=raw_text, summary=full_summary)
                        )
                        status.update(
                            label=f"✅ **{up_file.name}** processado com sucesso!",
                            state="complete",
                        )
                    except Exception as e:
                        status.update(label=f"❌ Falha ao processar {up_file.name}", state="error")
                        st.error(friendly_api_error(e))

            # remember which files we have processed
            st.session_state.files_signature = signature
            # Reset any previous evaluation result (since material changed)
            st.session_state.eval_result = None

    data = st.session_state.pdf_docs
    if data:
        n_docs = len(data)
        n_chars = sum(len(doc.raw_text) for doc in data)
        st.success(f"✅ {n_docs} documento(s) · {n_chars:,} caracteres extraídos")

    st.divider()

    # ---- List of loaded PDFs (to open as tabs) ---------------------------
    if data:
        st.markdown("##### 📚 Documentos")
        st.caption("Seleciona os documentos a abrir como tabs no painel principal.")
        current_visible = [d.name for d in st.session_state.pdf_docs if d.name in st.session_state.get("visible_docs", [])]
        # Ensure we have a list in session_state
        if "visible_docs" not in st.session_state:
            st.session_state.visible_docs = []

        selected = st.multiselect(
            "Documentos abertos",
            options=[doc.name for doc in data],
            default=st.session_state.visible_docs,
            label_visibility="collapsed",
            key="docs_multiselect",
        )
        if selected != st.session_state.visible_docs:
            st.session_state.visible_docs = selected
            st.rerun()

        col_all, col_none = st.columns(2)
        with col_all:
            if st.button("✅ Todos", use_container_width=True, key="all_docs"):
                st.session_state.visible_docs = [doc.name for doc in data]
                st.rerun()
        with col_none:
            if st.button("🚫 Nenhum", use_container_width=True, key="no_docs"):
                st.session_state.visible_docs = []
                st.rerun()

    st.divider()

    # ---- Shortcuts to IA tabs (always present) ---------------------------
    st.markdown("##### 🤖 IA Multi‑Agente")
    st.markdown(
        "<div class='sidebar-pill'>🧠 Resumo Inteligente</div>"
        "<div class='sidebar-pill'>🎓 Avaliação Interativa</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Estas tabs estão sempre disponíveis no painel principal. "
        "Em cada uma, escolhes que documentos incluir na matéria a analisar."
    )


# =============================================================================
# 8. MAIN PAGE LOGIC
# =============================================================================
if not st.session_state.pdf_docs:
    # Welcome screen
    with st.container(border=True):
        st.markdown("### 👋 Bem‑vindo")
        st.write(
            "Para começar, carregue na barra lateral um ou mais ficheiros PDF. "
            "Após o upload, o sistema extrairá o texto, gerará resumos por chunk "
            "e deixará tudo pronto para revisão."
        )
        st.markdown(
            "- 📖 Cada PDF ganha **uma tab** (escolhe na barra lateral quais abrir).\n"
            "- 🧠 Dentro da tab de cada PDF vê o resumo gerado (scroll contínuo).\n"
            "- 🎓 Na última tab (**Avaliação Interativa**) seleciona os PDFs que deseja incluir "
            "no teste e inicia o debate entre os três agentes."
        )
        with st.expander("ℹ️ Estrutura esperada dos PDFs"):
            st.markdown(
                "Os PDFs podem conter qualquer conteúdo; o app irá extrair o texto bruto "
                "e, em seguida, gerar resumos estruturados usando o prompt do Professor Catedrático."
            )
else:
    # Build tab list: one per PDF (if selected) + the evaluation tab
    visible_docs = [doc for doc in st.session_state.pdf_docs if doc.name in st.session_state.visible_docs]
    doc_labels: List[str] = []
    for doc in visible_docs:
        label = doc.name
        if len(label) > 55:
            label = label[:53] + "…"
        doc_labels.append(f"📄 {label}")

    ai_labels = ["🧠 Resumo Inteligente", "🎓 Avaliação Interativa"]
    all_labels = doc_labels + ai_labels
    tabs = st.tabs(all_labels)

    # ----- Tabs for each PDF ------------------------------------------------
    for idx, tab in enumerate(tabs[:-2]):  # exclude the last two (IA tabs)
        with tab:
            doc = visible_docs[idx]
            st.markdown(f"## 📄 {doc.name}")
            st.caption(f"{len(doc.raw_text):,} caracteres extraídos")
            st.markdown("---")
            # Show the generated summary (already stored)
            if doc.summary:
                st.markdown(doc.summary)
            else:
                st.info("Ainda não há resumo disponível (talvez o processamento tenha falhado).")

    # ----- Tab 1: Resumo Inteligente (placeholder – we already have per‑PDF summaries) -----
    with tabs[-2]:
        st.markdown("### 🧠 Resumo Inteligente")
        st.caption(
            "Esta tab exibe o resumo de **todos** os PDFs carregados (concatenado). "
            "Pode ser útil para uma visão global."
        )
        if st.session_state.pdf_docs:
            all_summaries = "\n\n---\n\n".join([doc.summary for doc in st.session_state.pdf_docs if doc.summary])
            if all_summaries:
                st.markdown(all_summaries)
            else:
                st.info("Nenhum resumo disponível ainda.")
        else:
            st.info("Carregue PDFs para gerar o resumo.")

    # ----- Tab 2: Avaliação Interativa ---------------------------------------
    with tabs[-1]:
        st.markdown("### 🎓 Avaliação Interativa")
        st.caption(
            "Selecione os PDFs que devem participar do teste de revisão. "
            "Os três agentes vão debater até chegar a um consenso ou atingir o limite de iterações."
        )
        # Multiselect of PDFs (by name) to include in the test
        pdf_names = [doc.name for doc in st.session_state.pdf_docs]
        selected_for_test = st.multiselect(
            "📚 Selecionar Matéria para o Teste",
            options=pdf_names,
            default=pdf_names[:1] if pdf_names else [],
            key="eval_multiselect",
        )
        st.write("")
        # Button to start the consensus process
        can_run = (
            bool(st.session_state.nvidia_api_key)
            and bool(selected_for_test)
            and bool(st.session_state.pdf_docs)
        )
        if st.button(
            "🚀 Gerar Prova (Questões + Exercícios)",
            type="primary",
            disabled=not can_run,
            use_container_width=True,
            key="run_eval",
        ):
            # Build material from selected PDFs (use their summaries)
            selected_docs = [doc for doc in st.session_state.pdf_docs if doc.name in selected_for_test]
            material = "\n\n---\n\n".join([doc.summary for doc in selected_docs if doc.summary])
            if not material.strip():
                st.warning("O material selecionado está vazio (verifique se os resumos foram gerados).")
            else:
                debate_container = st.container()
                debate_container.markdown("#### 🎬 Debate em curso")
                try:
                    client = get_nvidia_client(st.session_state.nvidia_api_key)
                    result = run_consensus_loop(
                        client=client,
                        material=material,
                        task="evaluation",
                        max_iterations=st.session_state.max_iterations,
                        status_container=debate_container,
                    )
                    st.session_state.eval_result = result
                except OpenAIError as e:
                    debate_container.markdown(friendly_api_error(e))
                except Exception as e:
                    debate_container.error(f"❌ Erro inesperado: {e}")

        # Show result if available
        result: Optional[DebateResult] = st.session_state.get("eval_result")
        if result:
            st.divider()
            status_emoji = "🎉" if result.consensus_reached else "⏱️"
            status_text = (
                f"Consenso atingido em {result.iterations_used} ronda(s)"
                if result.consensus_reached
                else f"Limite de {result.iterations_used} rondas atingido sem consenso"
            )
            st.markdown(f"## {status_emoji} Versão Final · {status_text}")
            st.caption(f"Autoria final: **{'👑' if result.final_author == 'Chefe' else '🅰️' if result.final_author == 'Validador A' else '🅱️'} {result.final_author}**")
            with st.container(border=True):
                st.markdown(result.final_content)
            # Download button
            st.download_button(
                "📥 Descarregar em Markdown",
                data=result.final_content,
                file_name="teste_revisao.md",
                mime="text/markdown",
                key="dl_eval",
            )
            # Optional: show debate history
            with st.expander(f"🗂️ Histórico completo do debate ({len(result.history)} intervenções)"):
                for entry in result.history:
                    icon = (
                        "👑"
                        if entry.author == "Chefe"
                        else "🅰️"
                        if entry.author == "Validador A"
                        else "🅱️"
                    )
                    if entry.kind == "draft":
                        tag = "📝 Rascunho inicial"
                    elif entry.kind == "approval":
                        tag = f"✅ Aprovou a versão de {entry.target_author}"
                    else:
                        tag = f"✏️ Reescreveu (alterações à versão de {entry.target_author})"
                    st.markdown(
                        f"**Ronda {entry.iteration} · {icon} {entry.author}** — {tag}"
                    )
                    if entry.kind == "approval":
                        st.code(entry.content[:1500], language="markdown")
                    else:
                        st.markdown(entry.content)
                    st.write("")


# --------------------------------------------------------------
# End of app.py
# --------------------------------------------------------------
