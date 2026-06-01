"""
app.py — Plataforma Análise de Custos ISEL (Consenso Multi-Agente)
====================================================================
EdTech app em Streamlit com:
  • Identidade visual inspirada no ISEL (azul institucional, cards, ícones)
  • Sidebar com ⚙️ Configurações:
        - NVIDIA API Key (password, persistida em session_state)
        - MAX_ITERATIONS de debate (slider 2..10, default 4)
  • Carregamento de múltiplos resumos (.txt / .md)
  • Apresentação por Tabs — uma por capítulo + duas Tabs inteligentes
  • Loop de Consenso Dinâmico entre 3 agentes NVIDIA NIM:
        👑 Chefe       — meta/llama-3.1-nemotron-70b-instruct //llama-3.1-405b-instruct
        🅰️ Validador A — mistralai/mistral-large-2-instruct
        🅱️ Validador B — meta/llama-3.1-70b-instruct
    com a REGRA DE OURO: nenhum agente avalia ou reescreve o seu próprio output.

Execução:
    streamlit run app.py

Dependências:
    pip install streamlit openai
"""

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
.agent-card .model {{ color: {ISEL_MUTED}; font-size: 0.82rem; font-family: ui-monospace, monospace; }}
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

# Definição declarativa dos agentes. A ordem em AGENTS_ORDER determina a
# sequência em que os validadores são chamados em cada ronda.
AGENTS_ORDER = ["Chefe", "Validador A", "Validador B"]
AGENTS: Dict[str, Dict[str, str]] = {
    "Chefe": {"model": "nvidia/llama-3.1-nemotron-70b-instruct", "icon": "👑"},
    "Validador A": {"model": "mistralai/mistral-large-2-instruct", "icon": "🅰️"},
    "Validador B": {"model": "meta/llama-3.1-70b-instruct",        "icon": "🅱️"},
}

UNANIMITY_TOKEN = "[UNANIMIDADE]"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


# =============================================================================
# 4. PARSER DOS RESUMOS
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


def flatten_chapters(data: Dict) -> List[Tuple[str, str, Dict[str, str]]]:
    out: List[Tuple[str, str, Dict[str, str]]] = []
    for doc, chapters in data.items():
        for title, sections in chapters.items():
            out.append((doc, title, sections))
    return out


def build_full_material(data: Dict) -> str:
    """Compila toda a matéria carregada num único texto enviado aos agentes."""
    parts: List[str] = []
    for doc, chapters in data.items():
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
            # Mostra os últimos ~1800 caracteres com cursor (mais leve para o front-end)
            tail = accumulated[-1800:]
            placeholder.code(tail + "▌", language="markdown")

    placeholder.empty()
    return accumulated.strip()


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
    """
    Considera-se aprovação se a resposta contém o token [UNANIMIDADE] logo
    nos primeiros 300 caracteres (tolerância pequena ao formato exacto).
    """
    head = response.strip()[:300].upper()
    return UNANIMITY_TOKEN.upper() in head


def run_consensus_loop(
    client: OpenAI,
    full_material: str,
    *,
    task: str,                     # "summary" | "evaluation"
    max_iterations: int,
    ui_container,                  # contentor onde se desenha o debate
) -> DebateResult:
    """
    Algoritmo de Consenso Dinâmico:

    1) O Chefe produz sempre o rascunho inicial (V1).
    2) Em cada ronda, os DOIS agentes que NÃO são autores da versão corrente
       avaliam-na sequencialmente.
         - Devolverem [UNANIMIDADE]  →  aprovam.
         - Caso contrário, a sua resposta É a nova versão e passam a ser
           o novo autor.
    3) Se ambos aprovarem na mesma ronda → CONSENSO, sai.
    4) Se um reescrever, interrompe a ronda. Próxima ronda usa os outros dois
       (a Regra de Ouro é garantida porque o autor atual é sempre excluído
       da lista de validadores).
    5) Termina por consenso ou ao atingir `max_iterations`.
    """
    # --- Selecciona prompts conforme a tarefa --------------------------------
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

    # -------------------------------------------------------------------------
    # FASE 0 — Chefe cria o rascunho inicial V1
    # -------------------------------------------------------------------------
    with ui_container.status(
        f"{AGENTS['Chefe']['icon']} **Chefe** a criar o rascunho inicial de **{task_label}**…",
        expanded=True,
    ) as s:
        s.write(f"Modelo: `{AGENTS['Chefe']['model']}`")
        user_prompt = (
            "MATÉRIA DE ESTUDO COMPLETA:\n\n"
            f"{full_material}\n\n---\n\n"
            f"Produz agora o {task_label} seguindo rigorosamente a estrutura."
        )
        initial_draft = stream_agent_call(
            client,
            model=AGENTS["Chefe"]["model"],
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

    # -------------------------------------------------------------------------
    # FASE 1+ — Rondas de validação
    # -------------------------------------------------------------------------
    for iteration in range(1, max_iterations + 1):
        ui_container.markdown(
            f"<div class='round-tag'>🔄 Ronda {iteration} de {max_iterations}</div>",
            unsafe_allow_html=True,
        )

        # REGRA DE OURO — validadores desta ronda = todos os agentes menos o
        # autor da versão atual.
        validators_this_round = [a for a in AGENTS_ORDER if a != current_author]

        approvals_this_round: List[str] = []
        rewrite_happened = False

        for validator_name in validators_this_round:
            with ui_container.status(
                f"{AGENTS[validator_name]['icon']} **{validator_name}** "
                f"a avaliar V{version_number} de **{current_author}**…",
                expanded=True,
            ) as s:
                s.write(f"Modelo: `{AGENTS[validator_name]['model']}`")

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
                    model=AGENTS[validator_name]["model"],
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
                    # Reescrita → nova versão. Interrompemos a ronda.
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
                    break  # próxima ronda: o autor mudou

        # ----- Avalia o estado no final desta ronda --------------------------
        if not rewrite_happened and len(approvals_this_round) == len(validators_this_round):
            # Os dois não-autores aprovaram → CONSENSO
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

    # Limite atingido sem consenso
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
st.session_state.setdefault("summary_result", None)   # DebateResult
st.session_state.setdefault("eval_result", None)      # DebateResult

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

    data = st.session_state.parsed_data
    if data:
        n_docs = len(data)
        n_chapters = sum(len(c) for c in data.values())
        st.success(f"✅ {n_docs} documento(s) · {n_chapters} capítulo(s)")


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
# 12. RENDERIZAÇÃO DAS TABS
# =============================================================================
def render_chapter_tab(doc: str, ch_title: str, sections: Dict[str, str]) -> None:
    """Renderiza o conteúdo de um capítulo dentro da sua tab."""
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


def render_agent_panel() -> None:
    """Apresenta os 3 agentes em cards lado-a-lado."""
    c1, c2, c3 = st.columns(3)
    for col, name in zip([c1, c2, c3], AGENTS_ORDER):
        with col:
            st.markdown(
                f"""
                <div class='agent-card'>
                    <div class='role'>{AGENTS[name]['icon']} {name}</div>
                    <div class='model'>{AGENTS[name]['model']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_debate_history(result: DebateResult) -> None:
    """Mostra o histórico completo do debate dentro de um expander."""
    with st.expander(f"🗂️ Histórico completo do debate ({len(result.history)} intervenções)"):
        for entry in result.history:
            icon = AGENTS[entry.author]["icon"]
            if entry.kind == "draft":
                tag = "📝 Rascunho inicial"
            elif entry.kind == "approval":
                tag = f"✅ Aprovou a versão de {entry.target_author}"
            else:
                tag = f"✏️ Reescreveu (alterações à versão de {entry.target_author})"
            st.markdown(f"**Ronda {entry.iteration} · {icon} {entry.author}** — {tag}")
            with st.container(border=True):
                if entry.kind == "approval":
                    # Aprovações tendem a ser curtas — mostra em bloco de código
                    st.code(entry.content[:1500], language="markdown")
                else:
                    # Drafts e rewrites são longos — renderiza markdown
                    st.markdown(entry.content)
            st.write("")


def render_ai_tab(
    task: str,
    label: str,
    description: str,
    result_state_key: str,
) -> None:
    """Renderiza uma das duas tabs inteligentes (resumo ou avaliação)."""
    st.markdown(f"### {label}")
    st.caption(description)
    st.write("")

    # Cards dos agentes
    render_agent_panel()
    st.write("")

    api_key = st.session_state.nvidia_api_key
    max_iter = st.session_state.max_iterations
    can_run = bool(api_key) and bool(st.session_state.parsed_data)

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
    elif not st.session_state.parsed_data:
        st.info("Carregue primeiro os resumos da matéria na barra lateral.")
    else:
        st.caption(f"Limite atual: **{max_iter} rondas** · alterável em ⚙️ Configurações.")

    # --- Execução do loop quando o botão é premido ---------------------------
    if run and can_run:
        st.session_state[result_state_key] = None
        debate_container = st.container()
        debate_container.markdown("#### 🎬 Debate em curso")
        try:
            client = get_nvidia_client(api_key)
            full_material = build_full_material(st.session_state.parsed_data)

            # Truncagem defensiva caso o material seja muito grande
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
            debate_container.error(f"❌ Erro da API NVIDIA: {e}")
        except Exception as e:
            debate_container.error(f"❌ Erro inesperado: {e}")

    # --- Mostra o resultado se existir ---------------------------------------
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
        st.caption(f"Autoria final: **{AGENTS[result.final_author]['icon']} {result.final_author}**")

        with st.container(border=True):
            st.markdown(result.final_content)

        # Download
        fname = "resumo_inteligente.md" if task == "summary" else "teste_revisao.md"
        st.download_button(
            "📥 Descarregar em Markdown",
            data=result.final_content,
            file_name=fname,
            mime="text/markdown",
            key=f"dl_{task}",
        )

        # Histórico do debate
        render_debate_history(result)


# =============================================================================
# 13. CONSTRUÇÃO DAS TABS
# =============================================================================
data = st.session_state.parsed_data

if not data:
    with st.container(border=True):
        st.markdown("### 👋 Bem-vindo")
        st.write(
            "Para começar, carregue na barra lateral um ou mais ficheiros `.txt` "
            "ou `.md` com os seus resumos. A plataforma irá:"
        )
        st.markdown(
            "- 📖 Organizar a matéria em **Tabs** (uma por capítulo) com **LaTeX** nas fórmulas  \n"
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
    chapter_list = flatten_chapters(data)
    multi_doc = len({doc for doc, _, _ in chapter_list}) > 1

    # Etiquetas das tabs dos capítulos (truncagem para evitar tabs gigantes)
    chapter_labels: List[str] = []
    for doc, title, _ in chapter_list:
        label = title if not multi_doc else f"{title}  ·  {doc}"
        if len(label) > 55:
            label = label[:53] + "…"
        chapter_labels.append(f"📖 {label}")

    # Tabs dos capítulos + duas Tabs inteligentes
    all_labels = chapter_labels + ["🧠 Resumo Inteligente", "🎓 Avaliação Interativa"]
    tabs = st.tabs(all_labels)

    # Tabs de capítulos
    for i, (doc, ch_title, sections) in enumerate(chapter_list):
        with tabs[i]:
            render_chapter_tab(doc, ch_title, sections)

    # Tab AI 1 — Resumo Inteligente
    with tabs[-2]:
        render_ai_tab(
            task="summary",
            label="🧠 Resumo Inteligente e Explicativo",
            description=(
                "Os três agentes debatem iterativamente até produzirem um resumo "
                "claro, profundo e didático de toda a matéria carregada."
            ),
            result_state_key="summary_result",
        )

    # Tab AI 2 — Avaliação Interativa
    with tabs[-1]:
        render_ai_tab(
            task="evaluation",
            label="🎓 Avaliação Interativa",
            description=(
                "Os três agentes debatem até obter um teste de revisão "
                "(10 questões de escolha múltipla + 2 exercícios práticos) à prova de erros."
            ),
            result_state_key="eval_result",
        )
