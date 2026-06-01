# --------------------------------------------------------------
# app.py – Plataforma Análise de Custos ISEL (Consenso Multi‑Agente)
# --------------------------------------------------------------
# Autor: Engenheiro de Software Sénior & Arquiteto de IA
# Descrição: Aplicação completa, modular, pronta‑para‑rodar.
# --------------------------------------------------------------

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import streamlit as st
from openai import OpenAI, OpenAIError

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Análise de Custos | ISEL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# 2. IDENTIDADE VISUAL ISEL (CSS injetado)
# =============================================================================
ISEL_PRIMARY    = "#004b87"   # Azul institucional
ISEL_PRIMARY_DK = "#003864"
ISEL_BG         = "#f5f7fa"
ISEL_SURFACE    = "#ffffff"
ISEL_BORDER     = "#e0e6ed"
ISEL_TEXT       = "#1a2332"
ISEL_MUTED      = "#6c757d"
ISEL_SUCCESS    = "#198754"
ISEL_WARN       = "#e0a800"

CUSTOM_CSS = f"""
<style>
/* Base ----------------------------------------------------------- */
.stApp {{ background-color: {ISEL_BG}; }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}

/* Tipografia ----------------------------------------------------- */
h1, h2, h3, h4 {{ color: {ISEL_PRIMARY} !important; font-weight: 700; }}
h1 {{ letter-spacing: -0.02em; }}

/* Sidebar -------------------------------------------------------- */
[data-testid="stSidebar"] {{ background-color: {ISEL_SURFACE}; border-right: 1px solid {ISEL_BORDER}; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {ISEL_PRIMARY} !important; }}

/* Botões --------------------------------------------------------- */
.stButton > button, .stDownloadButton > button {{
    background-color: {ISEL_PRIMARY}; color: white !important;
    border: none; border-radius: 6px; padding: 0.55rem 1.4rem;
    font-weight: 600; transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(0, 75, 135, 0.15);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    background-color: {ISEL_PRIMARY_DK}; transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 75, 135, 0.25); color: white !important;
}}
.stButton > button:disabled {{ background-color: #b0bcc8; color: white !important; transform: none; cursor: not-allowed; }}

/* Tabs ----------------------------------------------------------- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background-color: {ISEL_SURFACE}; padding: 6px;
    border-radius: 10px; border: 1px solid {ISEL_BORDER};
    overflow-x: auto;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: transparent; border-radius: 7px;
    padding: 0.45rem 1rem; color: {ISEL_TEXT}; font-weight: 500;
}}
.stTabs [data-baseweb="tab"]:hover {{ background-color: rgba(0, 75, 135, 0.06); }}
.stTabs [aria-selected="true"] {{ background-color: {ISEL_PRIMARY} !important; color: white !important; }}

/* Inputs --------------------------------------------------------- */
.stTextInput input, .stTextArea textarea {{
    border-radius: 6px; border: 1px solid {ISEL_BORDER};
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {ISEL_PRIMARY}; box-shadow: 0 0 0 2px rgba(0, 75, 135, 0.15);
}}

/* Expander ------------------------------------------------------- */
.stExpander {{ border-radius: 8px; border: 1px solid {ISEL_BORDER}; background-color: {ISEL_SURFACE}; }}

/* Banner ISEL ---------------------------------------------------- */
.isel-banner {{
    background: linear-gradient(135deg, {ISEL_PRIMARY} 0%, {ISEL_PRIMARY_DK} 100%);
    color: white; padding: 1.5rem 2rem; border-radius: 12px;
    margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(0, 75, 135, 0.2);
}}
.isel-banner h1 {{ color: white !important; margin: 0; font-size: 1.9rem; }}
.isel-banner p {{ margin: 0.25rem 0 0 0; opacity: 0.92; font-size: 0.95rem; }}

/* Section title (small accent bar) ------------------------------- */
.section-title {{
    color: {ISEL_PRIMARY}; font-weight: 700; font-size: 1.05rem;
    margin: 1.25rem 0 0.6rem 0; display: flex; align-items: center; gap: 0.5rem;
}}
.section-title::before {{
    content: ""; width: 4px; height: 18px; background: {ISEL_PRIMARY}; border-radius: 2px;
}}

/* Agent cards ---------------------------------------------------- */
.agent-card {{
    background-color: {ISEL_SURFACE}; border: 1px solid {ISEL_BORDER};
    border-radius: 10px; padding: 1rem 1.1rem;
    border-left: 4px solid {ISEL_PRIMARY};
}}
.agent-card .role {{ color: {ISEL_PRIMARY}; font-weight: 700; }}
.agent-card .model {{ color: {ISEL_MUTED}; font-size: 0.82rem; font-family: ui-monospace, monospace; word-break: break-all; }}
.round-tag {{
    display: inline-block; background: {ISEL_PRIMARY}; color: white;
    padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;
    margin-bottom: 0.5rem;
}}
.consensus-banner {{
    background: linear-gradient(135deg, {ISEL_SUCCESS} 0%, #146c43 100%);
    color: white; padding: 1rem 1.3rem; border-radius: 10px;
    font-weight: 600; margin: 1rem 0;
}}
.no-consensus-banner {{
    background: linear-gradient(135deg, {ISEL_WARN} 0%, #b88a00 100%);
    color: white; padding: 1rem 1.3rem; border-radius: 10px;
    font-weight: 600; margin: 1rem 0;
}}

/* Sidebar item — atalho IA --------------------------------------- */
.sidebar-pill {{
    display: block; background: {ISEL_BG}; border: 1px solid {ISEL_BORDER};
    border-left: 3px solid {ISEL_PRIMARY};
    padding: 0.55rem 0.85rem; border-radius: 6px;
    margin-bottom: 0.4rem; font-weight: 600; color: {ISEL_PRIMARY};
    font-size: 0.9rem;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============================================================================
# 3. CONSTANTES — PARSER E AGENTES
# =============================================================================
SECTION_MARKERS: Dict[str, str] = {
    "foco":      "🎯 Foco Principal",
    "conceitos": "🧠 Conceitos-Chave",
    "formulas":  "🧮 Fórmulas e Metodologias",
    "aplicacao": "🏭 Aplicação",
    "dica":      "🎓 Dica do Catedrático",
}

# Definição declarativa dos agentes — a chave "model" aqui é o DEFAULT.
# O modelo real em uso é st.session_state.agent_models[name] (ver Configurações).
AGENTS_ORDER = ["Chefe", "Validador A", "Validador B"]
DEFAULT_MODELS: Dict[str, str] = {
    # Defaults escolhidos por terem boa disponibilidade na maioria das contas NVIDIA NIM.
    # Se a tua conta tiver outros modelos, altera em ⚙️ Configurações → 🤖 Modelos.
    "Chefe":       "meta/llama-3.3-70b-instruct",
    "Validador A": "mistralai/mistral-large-2-instruct",
    "Validador B": "meta/llama-3.1-70b-instruct",
}
AGENT_ICONS: Dict[str, str] = {
    "Chefe": "👑",
    "Validador A": "🅰️",
    "Validador B": "🅱️",
}

UNANIMITY_TOKEN = "[UNANIMIDADE]"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def get_model(name: str) -> str:
    """Devolve o modelo atual de um agente (override no session_state)."""
    return st.session_state.agent_models.get(name, DEFAULT_MODELS[name])


# =============================================================================
# 4. PARSER DOS RESUMOS (arquivos .txt / .md)
# =============================================================================
def parse_sections(chapter_body: str) -> Dict[str, str]:
    """Extrai as 5 secções padrão de um capítulo."""
    sections = {key: "" for key in SECTION_MARKERS}
    positions: List[Tuple[int, int, str]] = []
    for key, marker in SECTION_MARKERS.items():
        pat = r"(?:\*\s+)?\*\*" + re.escape(marker) + r":\*\*"
        m = re.search(pat, chapter_body)
        if m:
            positions.append((m.start(), m.end(), key))
    positions.sort(key=lambda x: x[0])
    for i, (_, end, key) in enumerate(positions):
        nxt = positions[i + 1][0] if i + 1 < len(positions) else len(chapter_body)
        sections[key] = chapter_body[end:nxt].strip()
    return sections


def parse_chapters(doc_body: str) -> Dict[str, Dict[str, str]]:
    chapters: Dict[str, Dict[str, str]] = {}
    matches = list(re.finditer(r"####\s*([^\n]+)", doc_body))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(doc_body)
        chapters[title] = parse_sections(doc_body[m.end():body_end])
    return chapters


def parse_content(text: str, fallback_name: str = "Documento") -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Espera que o ficheiro contenha blocos do tipo:
        ### 📄 Documento: Nome do Documento
        #### Capítulo 1: Título do Capítulo
        * **🎯 Foco Principal:** …
        * **🧠 Conceitos-Chave:** …
        …
    Retorna um dicionário: {doc_name: {chapter_title: {section_key: text}}}.
    """
    out: Dict[str, Dict[str, Dict[str, str]]] = {}
    matches = list(re.finditer(r"###\s*(?:📄\s*)?Documento:\s*([^\n]+)", text))
    if not matches:
        chapters = parse_chapters(text)
        if chapters:
            out[fallback_name] = chapters
        return out
    for i, m in enumerate(matches):
        doc_name = m.group(1).strip()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters = parse_chapters(text[m.end():body_end])
        if chapters:
            out.setdefault(doc_name, {}).update(chapters)
    return out


def build_full_material(
    data: Dict[str, Dict[str, Dict[str, str]]],
    selected_docs: Optional[List[str]] = None,
) -> str:
    """
    Compila a matéria carregada num único texto enviado aos agentes.
    Se `selected_docs` for fornecido, apenas esses documentos são incluídos —
    é o filtro do selector de matéria nas tabs de IA.
    """
    if selected_docs is None:
        selected_docs = list(data.keys())

    parts: List[str] = []
    for doc in selected_docs:
        if doc not in data:
            continue
        chapters = data[doc]
        parts.append(f"\n=== DOCUMENTO: {doc} ===")
        for title, sections in chapters.items():
            parts.append(f"\n--- {title} ---")
            for key, label in [
                ("foco", "Foco Principal"),
                ("conceitos", "Conceitos-Chave"),
                ("formulas", "Fórmulas e Metodologias"),
                ("aplicacao", "Aplicação"),
                ("dica", "Dica do Catedrático"),
            ]:
                if sections.get(key):
                    parts.append(f"\n[{label}]\n{sections[key]}")
    return "\n".join(parts).strip()


# =============================================================================
# 5. PROMPTS DOS AGENTES — Resumo Inteligente
# =============================================================================
SUMMARY_INITIAL_SYSTEM = """És o **Chefe** — Professor Catedrático de Análise de Custos do ISEL, com 25 anos de docência.
A tua tarefa é produzir um **Resumo Inteligente e Explicativo** sobre a matéria fornecida.

OBJETIVO PEDAGÓGICO:
- Explicações precisas, profundas e didáticas dos conceitos-chave.
- Linguagem objetiva, clara, simplista — mas sem perder rigor académico.
- Explica sempre o "porquê" e o "como" de cada conceito.
- Usa analogias concretas (ex.: comparar custos fixos a uma renda mensal) quando ajudarem.

ESTRUTURA:
- Headings ## por bloco temático, ### por conceito.
- LaTeX inline `$...$` e display `$$...$$` para fórmulas.
- Listas e tabelas quando úteis.
- NUNCA listes só definições secas — sempre expansão e exemplo.

REGRAS:
- Português Europeu (PT-PT).
- Cobre TODA a matéria; não te concentres num único capítulo.
- Markdown limpo. Sem preâmbulos, sem despedidas — entrega só o resumo.
"""

SUMMARY_VALIDATION_SYSTEM = """És **{validator}**, um revisor académico extremamente rigoroso de Análise de Custos.

⚠️ REGRA DE OURO: vais avaliar um Resumo Inteligente produzido por **{author}**. Este NÃO é o teu trabalho. NUNCA podes avaliar nem alterar uma versão da tua própria autoria — neste pedido isso não acontece, mas mantém o princípio.

CRITÉRIOS DE AVALIAÇÃO:
1. Clareza didática real (não é só dizer "é claro" — verifica se um aluno entenderia).
2. Profundidade adequada (sem superficialidade, sem buracos).
3. Correção técnica e matemática.
4. Cobertura da matéria.
5. Uso eficaz de analogias e exemplos.
6. Qualidade da estrutura Markdown e LaTeX.

A TUA DECISÃO É BINÁRIA:

▶ OPÇÃO 1 — APROVAR sem alterações:
   Se o documento está realmente bom em todos os critérios, responde EXATAMENTE com a linha:
   {token}
   Seguida de 1 a 3 frases curtas a explicar porque concordas.
   NÃO incluas mais nada nem reescrevas nada.

▶ OPÇÃO 2 — REESCREVER:
   Se houver QUALQUER falha (mesmo só uma analogia fraca, uma frase superficial, um exemplo em falta):
   - NÃO uses a palavra {token} em lado nenhum.
   - Reescreve o documento INTEIRO em Markdown, com as tuas melhorias aplicadas.
   - Devolve APENAS o documento reescrito, sem comentários antes ou depois.

Português Europeu. Sê exigente mas justo: só reescreve se houver melhoria real a fazer.
"""

# =============================================================================
# 6. PROMPTS DOS AGENTES — Avaliação Interativa (Teste)
# =============================================================================
EVAL_INITIAL_SYSTEM = """És o **Chefe** — Professor Catedrático de Análise de Custos do ISEL.
A tua tarefa: criar um Teste de Revisão completo sobre a matéria fornecida.

ESTRUTURA OBRIGATÓRIA:

## Parte I — Escolha Múltipla (10 questões)
Para cada questão:
- Enunciado claro, sem ambiguidade.
- 4 opções rotuladas a), b), c), d).
- Identifica a opção correta com **"Resposta: x)"**.
- Justificação curta (1–2 frases) com base na matéria.

## Parte II — Exercícios Práticos (2 exercícios)
Cada exercício deve ter:
- Enunciado realista (empresa industrial fictícia, dados quantitativos coerentes).
- 3 a 5 alíneas com complexidade crescente.
- Resolução passo-a-passo com TODOS os cálculos visíveis.
- Resultado final destacado.

REGRAS CRÍTICAS:
- Cobre TRANSVERSALMENTE toda a matéria (vários capítulos).
- Valores numéricos realistas; cálculos têm de fechar exatamente.
- LaTeX `$...$` / `$$...$$` para fórmulas.
- Português Europeu. Markdown limpo. Sem preâmbulos.
"""

EVAL_VALIDATION_SYSTEM = """És **{validator}**, um revisor académico extremamente rigoroso de Análise de Custos do ISEL.

⚠️ REGRA DE OURO: vais avaliar um Teste de Revisão produzido por **{author}**. Este NÃO é o teu trabalho. NUNCA podes avaliar uma versão da tua autoria.

A TUA MISSÃO:
- Refaz mentalmente cada cálculo das resoluções; sinaliza erros aritméticos ou fórmulas mal aplicadas.
- Para cada pergunta de escolha múltipla: verifica se a opção correta é mesmo única e correta; deteta ambiguidades, distratores absurdos, enunciados imprecisos.
- Verifica se a matéria coberta corresponde à matéria fornecida (sem invenções).
- Avalia clareza de enunciados e suficiência de dados para resolver.

A TUA DECISÃO É BINÁRIA:

▶ OPÇÃO 1 — APROVAR:
   Se o teste está à prova de bala — cálculos certos, sem ambiguidades, cobertura adequada — responde EXATAMENTE com:
   {token}
   Seguido de 1 a 3 frases a justificar a aprovação.
   NÃO incluas mais nada.

▶ OPÇÃO 2 — REESCREVER:
   Se houver QUALQUER falha (erro de cálculo, ambiguidade, enunciado pouco claro, distrator inadequado):
   - NÃO uses a palavra {token}.
   - Reescreve o teste COMPLETO em Markdown, com as tuas correções aplicadas (mantendo a mesma estrutura: Parte I + Parte II + soluções).
   - Devolve apenas o teste reescrito, sem comentários.

Português Europeu. Sê implacável com erros matemáticos.
"""


# =============================================================================
# 7. CHAMADAS À API NVIDIA (com streaming dentro de st.status)
# =============================================================================
def get_nvidia_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def stream_agent_call(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    status_obj,
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """
    Chama um modelo NVIDIA em modo streaming, mostrando o output em tempo real
    dentro do contentor `status_obj` (um st.status). Devolve o texto acumulado.
    """
    placeholder = status_obj.empty()
    accumulated = ""

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
            tail = accumulated[-1800:]
            placeholder.code(tail + "▌", language="markdown")

    placeholder.empty()
    return accumulated.strip()


def friendly_api_error(err: Exception) -> str:
    """Traduz erros da API NVIDIA em sugestões acionáveis."""
    msg = str(err)
    lower = msg.lower()
    if "404" in msg or "not found" in lower:
        return (
            "❌ **Modelo não encontrado na tua conta NVIDIA.**\n\n"
            "O modelo indicado não existe ou não está disponível para o teu API key. "
            "Vai à barra lateral → **⚙️ Configurações → 🤖 Modelos dos Agentes** e "
            "muda para um modelo a que tenhas acesso. Exemplos que costumam funcionar:\n"
            "- `meta/llama-3.3-70b-instruct`\n"
            "- `meta/llama-3.1-70b-instruct`\n"
            "- `mistralai/mistral-large-2-instruct`\n"
            "- `meta/llama-3.1-8b-instruct`\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "401" in msg or "unauthorized" in lower or "authentication" in lower:
        return (
            "❌ **Chave NVIDIA inválida ou expirada.**\n\n"
            "Verifica a tua API Key em **⚙️ Configurações**. Ela deve começar por `nvapi-`.\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "429" in msg or "rate" in lower:
        return (
            "⏱️ **Limite de pedidos atingido.** Aguarda alguns segundos e tenta de novo.\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    return f"❌ Erro da API NVIDIA: {msg}"


# =============================================================================
# 8. LOOP DE CONSENSO DINÂMICO — O CORAÇÃO DA APLICAÇÃO
# =============================================================================
@dataclass
class DebateEntry:
    """Uma intervenção de um agente no debate."""
    iteration: int                # 0 = rascunho inicial; >=1 = ronda de validação
    author: str                   # quem produziu este conteúdo
    target_author: Optional[str]  # quem produziu a versão a que isto responde
    content: str                  # texto produzido
    kind: str                     # "draft" | "approval" | "rewrite"


@dataclass
class DebateResult:
    final_content: str
    final_author: str
    history: List[DebateEntry] = field(default_factory=list)
    consensus_reached: bool = False
    iterations_used: int = 0


def is_approval(response: str) -> bool:
    head = response.strip()[:300].upper()
    return UNANIMITY_TOKEN.upper() in head


def run_consensus_loop(
    client: OpenAI,
    full_material: str,
    *,
    task: str,
    max_iterations: int,
    ui_container,
) -> DebateResult:
    """Algoritmo de Consenso Dinâmico (ver docstring no topo do ficheiro)."""
    if task == "summary":
        initial_system = SUMMARY_INITIAL_SYSTEM
        validation_system_tpl = SUMMARY_VALIDATION_SYSTEM
        task_label = "Resumo Inteligente"
    elif task == "evaluation":
        initial_system = EVAL_INITIAL_SYSTEM
        validation_system_tpl = EVAL_VALIDATION_SYSTEM
        task_label = "Teste de Revisão"
    else:
        raise ValueError(f"task inválida: {task}")

    history: List[DebateEntry] = []

    # FASE 0 — Chefe cria o rascunho inicial V1 -----------------------------
    with ui_container.status(
        f"{AGENT_ICONS['Chefe']} **Chefe** a criar o rascunho inicial de **{task_label}**…",
        expanded=True,
    ) as s:
        chefe_model = get_model("Chefe")
        s.write(f"Modelo: `{chefe_model}`")
        user_prompt = (
            "MATÉRIA DE ESTUDO COMPLETA:\n\n"
            f"{full_material}\n\n---\n\n"
            f"Produz agora o {task_label} seguindo rigorosamente a estrutura."
        )
        initial_draft = stream_agent_call(
            client,
            model=chefe_model,
            system_prompt=initial_system,
            user_prompt=user_prompt,
            status_obj=s,
            temperature=0.45 if task == "summary" else 0.35,
            max_tokens=5500,
        )
        s.update(label=f"✅ **Chefe** entregou o rascunho V1", state="complete", expanded=False)

    history.append(
        DebateEntry(
            iteration=0,
            author="Chefe",
            target_author=None,
            content=initial_draft,
            kind="draft",
        )
    )

    current_author = "Chefe"
    current_content = initial_draft
    version_number = 1

    # FASE 1+ — Rondas de validação ------------------------------------------
    for iteration in range(1, max_iterations + 1):
        ui_container.markdown(
            f"<div class='round-tag'>🔄 Ronda {iteration} de {max_iterations}</div>",
            unsafe_allow_html=True,
        )

        validators_this_round = [a for a in AGENTS_ORDER if a != current_author]

        approvals_this_round: List[str] = []
        rewrite_happened = False

        for validator_name in validators_this_round:
            with ui_container.status(
                f"{AGENT_ICONS[validator_name]} **{validator_name}** "
                f"a avaliar V{version_number} de **{current_author}**…",
                expanded=True,
            ) as s:
                v_model = get_model(validator_name)
                s.write(f"Modelo: `{v_model}`")

                system_prompt = validation_system_tpl.format(
                    validator=validator_name,
                    author=current_author,
                    token=UNANIMITY_TOKEN,
                )
                user_prompt = (
                    "MATÉRIA DE ESTUDO ORIGINAL:\n\n"
                    f"{full_material}\n\n---\n\n"
                    f"DOCUMENTO A AVALIAR (autoria: {current_author}, versão V{version_number}):\n\n"
                    f"{current_content}\n\n---\n\n"
                    f"Aplica agora a tua decisão binária (APROVAR com {UNANIMITY_TOKEN} "
                    "ou REESCREVER o documento completo)."
                )
                response = stream_agent_call(
                    client,
                    model=v_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    status_obj=s,
                    temperature=0.25,
                    max_tokens=5500,
                )

                if is_approval(response):
                    approvals_this_round.append(validator_name)
                    history.append(
                        DebateEntry(
                            iteration=iteration,
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
                            iteration=iteration,
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
                    break

        if not rewrite_happened and len(approvals_this_round) == len(validators_this_round):
            ui_container.markdown(
                f"<div class='consensus-banner'>🎉 Consenso atingido na ronda {iteration}! "
                f"V{version_number} de {current_author} foi unanimemente aprovada por "
                f"{', '.join(validators_this_round)}.</div>",
                unsafe_allow_html=True,
            )
            return DebateResult(
                final_content=current_content,
                final_author=current_author,
                history=history,
                consensus_reached=True,
                iterations_used=iteration,
            )

    ui_container.markdown(
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
# 9. ESTADO DA SESSÃO
# =============================================================================
DEFAULT_MAX_ITER = 4

st.session_state.setdefault("nvidia_api_key", "")
st.session_state.setdefault("max_iterations", DEFAULT_MAX_ITER)
st.session_state.setdefault("parsed_data", {})
st.session_state.setdefault("files_signature", None)
st.session_state.setdefault("summary_result", None)
st.session_state.setdefault("eval_result", None)
st.session_state.setdefault("agent_models", DEFAULT_MODELS.copy())
st.session_state.setdefault("visible_docs", [])         # docs abertos como tabs
st.session_state.setdefault("summary_material", [])     # docs incluídos no resumo
st.session_state.setdefault("eval_material", [])        # docs incluídos na avaliação

# Carrega chave por defeito de st.secrets se existir
if not st.session_state.nvidia_api_key:
    try:
        secret_key = st.secrets.get("NVIDIA_API_KEY", "")
        if secret_key:
            st.session_state.nvidia_api_key = secret_key
    except Exception:
        pass


# =============================================================================
# 10. BARRA LATERAL
# =============================================================================
with st.sidebar:
    st.markdown(
        f"<h2 style='color:{ISEL_PRIMARY};margin-top:0'>📊 Análise de Custos</h2>"
        f"<p style='color:{ISEL_MUTED};margin-top:-0.5rem;font-size:0.9rem'>"
        f"ISEL · Plataforma de Estudo</p>",
        unsafe_allow_html=True,
    )

    # --- ⚙️ Configurações ---------------------------------------------------
    with st.expander("⚙️ Configurações", expanded=not st.session_state.nvidia_api_key):
        api_key_input = st.text_input(
            "🔑 NVIDIA API Key",
            value=st.session_state.nvidia_api_key,
            type="password",
            placeholder="nvapi-…",
            help="A chave fica guardada apenas na sessão atual. "
                 "Pode também defini-la em st.secrets['NVIDIA_API_KEY'].",
        )
        if api_key_input != st.session_state.nvidia_api_key:
            st.session_state.nvidia_api_key = api_key_input

        max_iter_input = st.slider(
            "🔁 Máximo de rondas de debate",
            min_value=2, max_value=10,
            value=st.session_state.max_iterations,
            help="Número máximo de iterações no loop de consenso entre os agentes.",
        )
        if max_iter_input != st.session_state.max_iterations:
            st.session_state.max_iterations = max_iter_input

        # 🤖 Modelos dos agentes — TEXT INPUT para o utilizador poder usar
        # qualquer modelo a que a sua conta NVIDIA tenha acesso.
        st.markdown("**🤖 Modelos dos Agentes**")
        st.caption(
            "Se vires um erro 404 _Not Found_, é porque o teu API key não tem "
            "acesso ao modelo indicado. Muda aqui para um que tenhas."
        )
        for agent_name in AGENTS_ORDER:
            new_val = st.text_input(
                f"{AGENT_ICONS[agent_name]} {agent_name}",
                value=st.session_state.agent_models.get(agent_name, DEFAULT_MODELS[agent_name]),
                key=f"model_input_{agent_name}",
                help=f"Modelo NVIDIA NIM para o agente {agent_name}.",
            )
            st.session_state.agent_models[agent_name] = new_val.strip()

        cols_rst = st.columns(2)
        with cols_rst[0]:
            if st.button("↺ Repor defaults", use_container_width=True, key="reset_models"):
                st.session_state.agent_models = DEFAULT_MODELS.copy()
                st.rerun()
        with cols_rst[1]:
            st.caption(" ")

        if st.session_state.nvidia_api_key:
            st.success("🔒 Chave carregada — IA ativa", icon="✅")
        else:
            st.warning("Sem chave — Tabs de IA estão desativadas.", icon="⚠️")

    st.divider()

    # --- 📁 Upload ----------------------------------------------------------
    st.markdown("##### 📁 Resumos da matéria")
    uploaded_files = st.file_uploader(
        "Carregar resumos (.txt / .md)",
        type=["txt", "md"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        signature = tuple((f.name, f.size) for f in uploaded_files)
        if signature != st.session_state.files_signature:
            combined: Dict[str, Dict[str, Dict[str, str]]] = {}
            for f in uploaded_files:
                try:
                    text = f.getvalue().decode("utf-8")
                except UnicodeDecodeError:
                    text = f.getvalue().decode("latin-1")
                parsed = parse_content(text, fallback_name=f.name.rsplit(".", 1)[0])
                for doc, chapters in parsed.items():
                    combined.setdefault(doc, {}).update(chapters)
            st.session_state.parsed_data = combined
            st.session_state.files_signature = signature
            # Resultados anteriores ficam desatualizados quando a matéria muda
            st.session_state.summary_result = None
            st.session_state.eval_result = None
            # Por defeito não abre nenhum documento — o utilizador escolhe.
            st.session_state.visible_docs = []
            # Por defeito, ambas as IA usam TODOS os documentos.
            st.session_state.summary_material = list(combined.keys())
            st.session_state.eval_material = list(combined.keys())

    data = st.session_state.parsed_data
    if data:
        n_docs = len(data)
        n_chapters = sum(len(c) for c in data.values())
        st.success(f"✅ {n_docs} documento(s) · {n_chapters} capítulo(s)")

    st.divider()

    # --- 📚 Lista de documentos (multiselect — abre tabs no main) -----------
    if data:
        st.markdown("##### 📚 Documentos")
        st.caption("Seleciona os documentos a abrir como tabs no painel principal.")

        # Sanitiza visible_docs caso o utilizador tenha carregado outro ficheiro
        valid_visible = [d for d in st.session_state.visible_docs if d in data]
        if valid_visible != st.session_state.visible_docs:
            st.session_state.visible_docs = valid_visible

        selected = st.multiselect(
            "Documentos abertos",
            options=list(data.keys()),
            default=st.session_state.visible_docs,
            label_visibility="collapsed",
            key="docs_multiselect",
        )
        if selected != st.session_state.visible_docs:
            st.session_state.visible_docs = selected
            st.rerun()

        cols_qa = st.columns(2)
        with cols_qa[0]:
            if st.button("✅ Todos", use_container_width=True, key="all_docs"):
                st.session_state.visible_docs = list(data.keys())
                st.rerun()
        with cols_qa[1]:
            if st.button("🚫 Nenhum", use_container_width=True, key="no_docs"):
                st.session_state.visible_docs = []
                st.rerun()

    st.divider()

    # --- 🤖 Atalhos para as Tabs de IA (sempre presentes) -------------------
    st.markdown("##### 🤖 IA Multi-Agente")
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
# 11. CABEÇALHO PRINCIPAL
# =============================================================================
st.markdown(
    """
    <div class="isel-banner">
        <h1>📊 Análise de Custos</h1>
        <p>Plataforma de estudo interativa · Instituto Superior de Engenharia de Lisboa</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 12. RENDERIZADORES
# =============================================================================
def render_chapter_body(doc: str, ch_title: str, sections: Dict[str, str]) -> None:
    """Renderiza o corpo de um capítulo (5 secções)."""
    st.markdown(f"### {ch_title}")
    st.caption(f"📄 {doc}")
    st.write("")

    if sections.get("foco"):
        st.markdown("<div class='section-title'>🎯 Foco Principal</div>", unsafe_allow_html=True)
        st.info(sections["foco"])

    if sections.get("conceitos"):
        st.markdown("<div class='section-title'>🧠 Conceitos-Chave</div>", unsafe_allow_html=True)
        st.markdown(sections["conceitos"])

    if sections.get("formulas"):
        st.markdown("<div class='section-title'>🧮 Fórmulas e Metodologias</div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(sections["formulas"])

    if sections.get("aplicacao"):
        st.markdown("<div class='section-title'>🏭 Aplicação Prática</div>", unsafe_allow_html=True)
        st.markdown(sections["aplicacao"])

    if sections.get("dica"):
        st.write("")
        with st.expander("🎓 **Ver Dica do Catedrático**", expanded=False):
            st.success(sections["dica"])


def render_document_tab(doc_name: str, chapters: Dict[str, Dict[str, str]]) -> None:
    """
    Renderiza UM documento por completo numa única tab.
    Dentro da tab, um selectbox permite navegar entre os seus capítulos.
    """
    st.markdown(f"## 📄 {doc_name}")
    st.caption(f"{len(chapters)} capítulo(s) neste documento")

    chapter_titles = list(chapters.keys())
    if not chapter_titles:
        st.warning("Este documento não tem capítulos reconhecidos.")
        return

    # Selector de capítulo (persistente por documento)
    state_key = f"selected_chapter::{doc_name}"
    default_idx = 0
    if state_key in st.session_state and st.session_state[state_key] in chapter_titles:
        default_idx = chapter_titles.index(st.session_state[state_key])

    selected_title = st.selectbox(
        "Escolhe o capítulo:",
        options=chapter_titles,
        index=default_idx,
        key=f"chap_select::{doc_name}",
    )
    st.session_state[state_key] = selected_title

    st.divider()
    render_chapter_body(doc_name, selected_title, chapters[selected_title])


def render_agent_panel() -> None:
    """Apresenta os 3 agentes em cards lado-a-lado (modelos vêm de session_state)."""
    c1, c2, c3 = st.columns(3)
    for col, name in zip([c1, c2, c3], AGENTS_ORDER):
        with col:
            st.markdown(
                f"""
                <div class='agent-card'>
                    <div class='role'>{AGENT_ICONS[name]} {name}</div>
                    <div class='model'>{get_model(name)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_debate_history(result: DebateResult) -> None:
    with st.expander(f"🗂️ Histórico completo do debate ({len(result.history)} intervenções)"):
        for entry in result.history:
            icon = AGENT_ICONS[entry.author]
            if entry.kind == "draft":
                tag = "📝 Rascunho inicial"
            elif entry.kind == "approval":
                tag = f"✅ Aprovou a versão de {entry.target_author}"
            else:
                tag = f"✏️ Reescreveu (alterações à versão de {entry.target_author})"
            st.markdown(f"**Ronda {entry.iteration} · {icon} {entry.author}** — {tag}")
            with st.container(border=True):
                if entry.kind == "approval":
                    st.code(entry.content[:1500], language="markdown")
                else:
                    st.markdown(entry.content)
            st.write("")


def render_ai_tab(
    task: str,
    label: str,
    description: str,
    result_state_key: str,
    material_state_key: str,
) -> None:
    """
    Renderiza uma das duas tabs inteligentes (resumo ou avaliação).
    Inclui o selector de matéria (documentos a incluir).
    """
    st.markdown(f"### {label}")
    st.caption(description)
    st.write("")

    # --- 1. Selector de matéria ---------------------------------------------
    data = st.session_state.parsed_data
    if data:
        st.markdown("<div class='section-title'>📚 Matéria a incluir</div>", unsafe_allow_html=True)

        valid_material = [d for d in st.session_state[material_state_key] if d in data]
        if valid_material != st.session_state[material_state_key]:
            st.session_state[material_state_key] = valid_material

        chosen = st.multiselect(
            "Que documentos queres incluir na análise?",
            options=list(data.keys()),
            default=st.session_state[material_state_key],
            key=f"material_multiselect_{task}",
            help="Os 3 agentes vão debater APENAS sobre os documentos aqui selecionados.",
        )
        if chosen != st.session_state[material_state_key]:
            st.session_state[material_state_key] = chosen

        cols_mat = st.columns(2)
        with cols_mat[0]:
            if st.button("✅ Tudo", use_container_width=True, key=f"all_mat_{task}"):
                st.session_state[material_state_key] = list(data.keys())
                st.rerun()
        with cols_mat[1]:
            if st.button("🚫 Limpar seleção", use_container_width=True, key=f"clear_mat_{task}"):
                st.session_state[material_state_key] = []
                st.rerun()

        st.write("")

    # --- 2. Cards dos agentes -----------------------------------------------
    render_agent_panel()
    st.write("")

    # --- 3. Controlo do botão -----------------------------------------------
    api_key = st.session_state.nvidia_api_key
    max_iter = st.session_state.max_iterations
    selected_material = st.session_state[material_state_key]
    can_run = bool(api_key) and bool(data) and bool(selected_material)

    cols = st.columns([3, 1])
    with cols[0]:
        existing = st.session_state.get(result_state_key)
        btn_label = "🔄 Refazer Debate" if existing else "🚀 Iniciar Debate Multi-Agente"
        run = st.button(
            btn_label,
            type="primary",
            disabled=not can_run,
            use_container_width=True,
            key=f"run_{task}",
        )
    with cols[1]:
        if st.session_state.get(result_state_key):
            if st.button("🗑️ Limpar", use_container_width=True, key=f"clear_{task}"):
                st.session_state[result_state_key] = None
                st.rerun()

    if not api_key:
        st.warning("Defina a chave NVIDIA API em **⚙️ Configurações** para ativar.")
    elif not data:
        st.info("Carregue primeiro os resumos da matéria na barra lateral.")
    elif not selected_material:
        st.warning("Selecione pelo menos um documento na matéria acima.")
    else:
        st.caption(
            f"Limite atual: **{max_iter} rondas** · alterável em ⚙️ Configurações. "
            f"Matéria selecionada: **{len(selected_material)} documento(s)**."
        )

    # --- 4. Execução do loop quando o botão é premido -----------------------
    if run and can_run:
        st.session_state[result_state_key] = None
        debate_container = st.container()
        debate_container.markdown("#### 🎬 Debate em curso")
        try:
            client = get_nvidia_client(api_key)
            full_material = build_full_material(data, selected_docs=selected_material)

            MAX_CHARS = 120_000
            if len(full_material) > MAX_CHARS:
                debate_container.info(
                    f"Matéria muito extensa ({len(full_material):,} caracteres). "
                    f"A truncar para {MAX_CHARS:,} caracteres."
                )
                full_material = full_material[:MAX_CHARS]

            result = run_consensus_loop(
                client=client,
                full_material=full_material,
                task=task,
                max_iterations=max_iter,
                ui_container=debate_container,
            )
            st.session_state[result_state_key] = result

        except OpenAIError as e:
            debate_container.markdown(friendly_api_error(e))
        except Exception as e:
            debate_container.error(f"❌ Erro inesperado: {e}")

    # --- 5. Mostra o resultado se existir -----------------------------------
    result: Optional[DebateResult] = st.session_state.get(result_state_key)
    if result:
        st.divider()
        status_emoji = "🎉" if result.consensus_reached else "⏱️"
        status_text = (
            f"Consenso atingido em {result.iterations_used} ronda(s)"
            if result.consensus_reached
            else f"Limite de {result.iterations_used} rondas atingido sem consenso"
        )
        st.markdown(f"## {status_emoji} Versão Final · {status_text}")
        st.caption(f"Autoria final: **{AGENT_ICONS[result.final_author]} {result.final_author}**")

        with st.container(border=True):
            st.markdown(result.final_content)

        fname = "resumo_inteligente.md" if task == "summary" else "teste_revisao.md"
        st.download_button(
            "📥 Descarregar em Markdown",
            data=result.final_content,
            file_name=fname,
            mime="text/markdown",
            key=f"dl_{task}",
        )

        render_debate_history(result)


# =============================================================================
# 13. CONSTRUÇÃO DAS TABS — uma por DOCUMENTO + 2 tabs fixas de IA
# =============================================================================
data = st.session_state.parsed_data

if not data:
    # Estado vazio — boas-vindas
    with st.container(border=True):
        st.markdown("### 👋 Bem-vindo")
        st.write(
            "Para começar, carregue na barra lateral um ou mais ficheiros `.txt` "
            "ou `.md` com os seus resumos. A plataforma irá:"
        )
        st.markdown(
            "- 📖 Organizar a matéria com **uma tab por documento** "
            "(escolhes na barra lateral quais abrir)  \n"
            "- 🧠 Gerar **resumos didáticos** através de um sistema de **3 agentes em debate**  \n"
            "- 🎓 Produzir **testes de revisão** validados por consenso multi-agente"
        )
        with st.expander("ℹ️ Estrutura esperada dos ficheiros"):
            st.code(
                """### 📄 Documento: Nome do Documento

#### Capítulo 1: Título do Capítulo

* **🎯 Foco Principal:** Descrição do foco.

* **🧠 Conceitos-Chave:**
  * Conceito A — definição
  * Conceito B — definição

* **🧮 Fórmulas e Metodologias:** $CT = CF + CV$

* **🏭 Aplicação:** Como aplicar este conhecimento.

* **🎓 Dica do Catedrático:** Insight prático.
""",
                language="markdown",
            )
else:
    # Tabs: uma por documento aberto + 2 fixas de IA --------------------------
    visible_docs = [d for d in st.session_state.visible_docs if d in data]

    # Etiquetas dos documentos (truncagem para evitar tabs gigantes)
    doc_labels: List[str] = []
    for d in visible_docs:
        label = d
        if len(label) > 55:
            label = label[:53] + "…"
        doc_labels.append(f"📄 {label}")

    # As duas tabs de IA estão SEMPRE no fim — fixas.
    ai_labels = ["🧠 Resumo Inteligente", "🎓 Avaliação Interativa"]
    all_labels = doc_labels + ai_labels

    tabs = st.tabs(all_labels)

    # Tabs dos documentos -----------------------------------------------------
    if not visible_docs:
        # Não foi selecionado nenhum documento — o utilizador vai diretamente
        # para uma das tabs de IA. Mostramos uma dica leve.
        # (Não é renderizado dentro de nenhuma tab porque não há tabs de docs.)
        st.info(
            "👈 Seleciona na barra lateral os documentos que queres abrir como tabs, "
            "ou usa diretamente uma das tabs de **IA** acima."
        )

    for i, doc_name in enumerate(visible_docs):
        with tabs[i]:
            render_document_tab(doc_name, data[doc_name])

    # Tab IA 1 — Resumo Inteligente ------------------------------------------
    with tabs[-2]:
        render_ai_tab(
            task="summary",
            label="🧠 Resumo Inteligente e Explicativo",
            description=(
                "Os três agentes debatem iterativamente até produzirem um resumo "
                "claro, profundo e didático da matéria selecionada."
            ),
            result_state_key="summary_result",
            material_state_key="summary_material",
        )

    # Tab IA 2 — Avaliação Interativa ----------------------------------------
    with tabs[-1]:
        render_ai_tab(
            task="evaluation",
            label="🎓 Avaliação Interativa",
            description=(
                "Os três agentes debatem até obter um teste de revisão "
                "(10 questões de escolha múltipla + 2 exercícios práticos) à prova de erros, "
                "sobre a matéria selecionada."
            ),
            result_state_key="eval_result",
            material_state_key="eval_material",
        )
