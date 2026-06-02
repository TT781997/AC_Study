"""
app.py — Plataforma Análise de Custos ISEL (Consenso Multi-Agente)
====================================================================
REFACTOR COMPLETO — Versão 2.0
--------------------------------------------------------------------
Mudanças face à versão anterior:
  • Suporte NATIVO a PDFs (PyMuPDF) — extração automática de texto.
  • Resumos académicos gerados AUTOMATICAMENTE ao carregar um PDF.
  • Uma TAB por PDF; dentro, o resumo completo scrolla na vertical.
  • Aba antiga "Resumo Inteligente (debate)" removida — fica apenas
    "📚 Tabs dos PDFs resumidos" + "🎓 Avaliação Interativa".
  • Aba "🎓 Avaliação" com `st.multiselect` para escolher quais PDFs
    alimentam o Catedrático.
  • Persistência ESTRITA em `st.session_state` — só se apaga via botão
    explícito "🗑️ Apagar Base de Dados de Resumos".
  • Truncagem/chunking defensivos contra `context_length_exceeded`.
  • Loop de Consenso CIRCULAR estrito na Avaliação (Regra de Ouro):
    o autor da versão atual NUNCA se avalia a si próprio; só sai do
    loop quando os DOIS não-autores aprovam na mesma ronda.
  • Validadores ultra-rápidos: max_tokens reduzido + prompts concisos.
  • Animações de loading divertidas (mensagens rotativas + GIFs opcionais).

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
# 1. CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Análise de Custos | ISEL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# 2. IDENTIDADE VISUAL ISEL (CSS injetado — paleta institucional)
# =============================================================================
ISEL_PRIMARY    = "#113264"   # Azul institucional ISEL (oficial)
ISEL_PRIMARY_DK = "#0a1f44"
ISEL_ACCENT     = "#004b87"   # Azul claro alternativo
ISEL_BG         = "#f5f7fa"
ISEL_SURFACE    = "#ffffff"
ISEL_BORDER     = "#dde3ec"
ISEL_TEXT       = "#1a2332"
ISEL_MUTED      = "#6c757d"
ISEL_SUCCESS    = "#198754"
ISEL_WARN       = "#e0a800"
ISEL_DANGER     = "#c0392b"

CUSTOM_CSS = f"""
<style>
.stApp {{ background-color: {ISEL_BG}; }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}

h1, h2, h3, h4 {{ color: {ISEL_PRIMARY} !important; font-weight: 700; }}
h1 {{ letter-spacing: -0.02em; }}

[data-testid="stSidebar"] {{ background-color: {ISEL_SURFACE}; border-right: 1px solid {ISEL_BORDER}; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {ISEL_PRIMARY} !important; }}

.stButton > button, .stDownloadButton > button {{
    background-color: {ISEL_PRIMARY}; color: white !important;
    border: none; border-radius: 6px; padding: 0.55rem 1.4rem;
    font-weight: 600; transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(17, 50, 100, 0.18);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    background-color: {ISEL_PRIMARY_DK}; transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(17, 50, 100, 0.28); color: white !important;
}}
.stButton > button:disabled {{ background-color: #b0bcc8; color: white !important; transform: none; cursor: not-allowed; }}

.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background-color: {ISEL_SURFACE}; padding: 6px;
    border-radius: 10px; border: 1px solid {ISEL_BORDER}; overflow-x: auto;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: transparent; border-radius: 7px;
    padding: 0.45rem 1rem; color: {ISEL_TEXT}; font-weight: 500;
}}
.stTabs [data-baseweb="tab"]:hover {{ background-color: rgba(17, 50, 100, 0.06); }}
.stTabs [aria-selected="true"] {{ background-color: {ISEL_PRIMARY} !important; color: white !important; }}

.stTextInput input, .stTextArea textarea {{ border-radius: 6px; border: 1px solid {ISEL_BORDER}; }}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {ISEL_PRIMARY}; box-shadow: 0 0 0 2px rgba(17, 50, 100, 0.15);
}}

.stExpander {{ border-radius: 8px; border: 1px solid {ISEL_BORDER}; background-color: {ISEL_SURFACE}; }}

.isel-banner {{
    background: linear-gradient(135deg, {ISEL_PRIMARY} 0%, {ISEL_PRIMARY_DK} 100%);
    color: white; padding: 1.5rem 2rem; border-radius: 12px;
    margin-bottom: 1.5rem; box-shadow: 0 4px 14px rgba(17, 50, 100, 0.25);
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

.pdf-meta {{
    color: {ISEL_MUTED}; font-size: 0.85rem; margin-bottom: 1rem;
    padding: 0.6rem 0.9rem; background: {ISEL_BG};
    border-left: 3px solid {ISEL_PRIMARY}; border-radius: 4px;
}}

.loading-fun {{
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.9rem 1.1rem; background: {ISEL_BG};
    border-left: 4px solid {ISEL_PRIMARY}; border-radius: 8px;
    font-size: 0.95rem; color: {ISEL_TEXT}; margin: 0.6rem 0;
}}
.loading-fun .emoji {{ font-size: 1.6rem; }}

.sidebar-pill {{
    display: block; background: {ISEL_BG}; border: 1px solid {ISEL_BORDER};
    border-left: 3px solid {ISEL_PRIMARY};
    padding: 0.55rem 0.85rem; border-radius: 6px;
    margin-bottom: 0.4rem; font-weight: 600; color: {ISEL_PRIMARY}; font-size: 0.9rem;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =============================================================================
# 3. CONSTANTES — AGENTES, MODELOS, LIMITES
# =============================================================================
AGENTS_ORDER = ["Chefe", "Validador A", "Validador B"]
DEFAULT_MODELS: Dict[str, str] = {
    "Chefe":       "meta/llama-3.3-70b-instruct",
    "Validador A": "mistralai/mistral-large-2-instruct",
    "Validador B": "meta/llama-3.1-70b-instruct",
}
AGENT_ICONS: Dict[str, str] = {
    "Chefe": "👑",
    "Validador A": "🅰️",
    "Validador B": "🅱️",
}

# Modelo dedicado à geração automática dos resumos académicos
# (separado dos modelos do debate; editável pelo utilizador na sidebar).
DEFAULT_SUMMARY_MODEL = "meta/llama-3.3-70b-instruct"

UNANIMITY_TOKEN = "[UNANIMIDADE]"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# --- Limites defensivos contra context_length_exceeded ---------------------
# Os modelos NVIDIA NIM 70B aceitam tipicamente 128k tokens de contexto. Por
# segurança usamos limites em CARACTERES (≈ 4 chars por token em texto PT).
MAX_CHARS_PER_SUMMARY_CHUNK = 60_000   # 1 chunk ≈ 15k tokens
MAX_CHARS_FOR_EVAL_INPUT    = 120_000  # input à avaliação (multi-PDF)
HARD_TRUNCATE_MARGIN        = 200      # margem na truncagem hard

# --- Loading divertido -----------------------------------------------------
FUNNY_LOADING_MESSAGES: List[str] = [
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
    "🐝 As abelhas a juntar mel das fórmulas mais doces…",
    "🦝 O guaxinim revisor encontrou outra contradição…",
    "🐹 Hamsters na roda — assim os tokens correm mais depressa!",
    "🦥 O Validador B em modo preguiça-acadêmica intencional…",
]

# GIFs opcionais. Lista vazia → só mensagens textuais. Adiciona URLs de
# Giphy/Tenor estáveis se quiseres reforçar o tom divertido.
LOADING_GIF_URLS: List[str] = [
    # "https://i.giphy.com/...",
]


def random_fun_message() -> str:
    return random.choice(FUNNY_LOADING_MESSAGES)


def show_fun_loading(container, message: Optional[str] = None) -> None:
    """Pílula de loading divertida (texto + GIF opcional)."""
    msg = message or random_fun_message()
    container.markdown(
        f"<div class='loading-fun'><span class='emoji'>⏳</span>"
        f"<span>{msg}</span></div>",
        unsafe_allow_html=True,
    )
    if LOADING_GIF_URLS:
        container.image(random.choice(LOADING_GIF_URLS), width=200)


def get_model(name: str) -> str:
    return st.session_state.agent_models.get(name, DEFAULT_MODELS[name])


def get_summary_model() -> str:
    return st.session_state.get("summary_model", DEFAULT_SUMMARY_MODEL)


# =============================================================================
# 4. PROMPT OFICIAL DO CATEDRÁTICO (resumos automáticos)
# =============================================================================
# ATENÇÃO: o prompt fornecido pelo utilizador no pedido original está
# truncado a meio da secção "🧮 Fórmulas e Metodologias". O bloco delimitado
# por "[INÍCIO TEXTO PROVIDENCIADO]" / "[FIM TEXTO PROVIDENCIADO]" reproduz
# o que foi enviado, palavra a palavra. O resto é uma continuação coerente
# baseada nas 5 secções já usadas no parser original (🎯 🧠 🧮 🏭 🎓). Quando
# tiveres a versão completa, substitui apenas o bloco delimitado.

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

2. REGRAS DE FORMATAÇÃO E LINGUAGEM:
   - Usa cabeçalhos `####` para o título de cada capítulo (ex.: `#### Capítulo X: Título`).
   - Português Europeu (PT-PT). Markdown limpo.
   - Sem preâmbulos, sem despedidas, sem meta-comentários. Entrega APENAS o resumo estruturado.
   - Se o texto fornecido for apenas um fragmento, resume APENAS o que está presente — não inventes conteúdo que não esteja na fonte.

---

MATERIAL DE ESTUDO A RESUMIR:

{material}
"""


# =============================================================================
# 5. PROMPTS — Avaliação Interativa (Teste de Revisão)
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

# Prompt de validação ENCURTADO — pede decisão binária rápida.
EVAL_VALIDATION_SYSTEM = """És **{validator}**, revisor académico rigoroso de Análise de Custos (ISEL).

⚠️ REGRA DE OURO: avalias o teste produzido por **{author}**. NUNCA avalies a tua própria autoria.

Verifica de forma rápida e cirúrgica:
1. Cálculos certos (refaz cada um mentalmente).
2. Cada escolha múltipla tem UMA resposta única e correta.
3. Sem ambiguidades ou enunciados imprecisos.
4. Cobertura razoável da matéria, sem invenções.

DECISÃO BINÁRIA — sê EXTREMAMENTE conciso:

▶ APROVAR (sem alterações):
   Responde EXATAMENTE com a linha:
   {token}
   Seguido de NO MÁXIMO 1 frase a justificar. NADA MAIS.

▶ REESCREVER (apenas se houver QUALQUER falha real — não trivialidades):
   - NÃO uses {token}.
   - Devolve o teste COMPLETO reescrito em Markdown (Parte I + Parte II + soluções).
   - Apenas o teste, sem comentários antes ou depois.

Português Europeu. Sê implacável só com erros que importam — pequenas preferências estilísticas NÃO justificam reescrita.
"""


# =============================================================================
# 6. EXTRAÇÃO E CHUNKING DE PDFs
# =============================================================================
def extract_pdf_text(pdf_bytes: bytes) -> Dict[str, object]:
    """
    Extrai texto de um PDF (bytes) com PyMuPDF. Devolve dict com
    'text' (str), 'pages' (int) e 'chars' (int).
    """
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
    """
    Divide texto em chunks de até `max_chars`, preferindo cortes em
    quebras de parágrafo. Garante que nenhum chunk excede `max_chars`.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for p in paragraphs:
        if len(p) > max_chars:
            if current.strip():
                chunks.append(current.strip())
                current = ""
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
    """Truncagem defensiva com margem."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - HARD_TRUNCATE_MARGIN] + "\n\n[... texto truncado por limite de contexto ...]"


# =============================================================================
# 7. CHAMADAS À API NVIDIA
# =============================================================================
def get_nvidia_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def stream_call(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    status_obj=None,
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    show_stream: bool = True,
) -> str:
    """Chamada com streaming. Se status_obj+show_stream, mostra em tempo real."""
    placeholder = status_obj.empty() if (status_obj is not None and show_stream) else None
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
            if placeholder is not None:
                tail = accumulated[-1500:]
                placeholder.code(tail + "▌", language="markdown")

    if placeholder is not None:
        placeholder.empty()
    return accumulated.strip()


def friendly_api_error(err: Exception) -> str:
    msg = str(err)
    lower = msg.lower()
    if "404" in msg or "not found" in lower:
        return (
            "❌ **Modelo não encontrado na tua conta NVIDIA.**\n\n"
            "Vai à sidebar → **⚙️ Configurações → 🤖 Modelos** e usa um modelo "
            "a que tenhas acesso. Exemplos comuns:\n"
            "- `meta/llama-3.3-70b-instruct`\n"
            "- `meta/llama-3.1-70b-instruct`\n"
            "- `mistralai/mistral-large-2-instruct`\n"
            "- `meta/llama-3.1-8b-instruct`\n\n"
            f"_Detalhe técnico:_ `{msg[:300]}`"
        )
    if "401" in msg or "unauthorized" in lower or "authentication" in lower:
        return (
            "❌ **Chave NVIDIA inválida ou expirada.** "
            "Verifica em ⚙️ Configurações (deve começar por `nvapi-`).\n\n"
            f"_Detalhe:_ `{msg[:300]}`"
        )
    if "429" in msg or "rate" in lower:
        return f"⏱️ **Limite de pedidos atingido.** Aguarda e tenta de novo.\n\n_Detalhe:_ `{msg[:300]}`"
    if "context" in lower or "length" in lower or "token" in lower:
        return (
            "📏 **Texto demasiado longo.** O sistema já trunca defensivamente — "
            "se isto persiste, reduz o número de PDFs selecionados.\n\n"
            f"_Detalhe:_ `{msg[:300]}`"
        )
    return f"❌ Erro da API NVIDIA: {msg}"


# =============================================================================
# 8. GERAÇÃO AUTOMÁTICA DE RESUMOS (por PDF)
# =============================================================================
def summarize_pdf(
    client: OpenAI,
    pdf_name: str,
    pdf_text: str,
    *,
    status_container,
) -> str:
    """
    Resume UM PDF. Se o texto couber em 1 chunk, faz 1 chamada; caso
    contrário, divide em chunks e concatena os resumos parciais.
    """
    chunks = chunk_text(pdf_text, max_chars=MAX_CHARS_PER_SUMMARY_CHUNK)
    summary_model = get_summary_model()

    if len(chunks) == 1:
        status_container.write(f"📝 A resumir `{pdf_name}` ({len(chunks[0]):,} chars)…")
        prompt = PROMPT_RESUMO_TEMPLATE.format(material=chunks[0])
        return stream_call(
            client,
            model=summary_model,
            system_prompt="És um Professor Catedrático. Produzes resumos académicos rigorosos.",
            user_prompt=prompt,
            status_obj=status_container,
            temperature=0.4,
            max_tokens=6000,
            show_stream=True,
        )

    # Multi-chunk
    status_container.write(
        f"📚 `{pdf_name}` é grande — dividido em **{len(chunks)} blocos** para evitar limite de contexto."
    )
    parts: List[str] = []
    for i, ck in enumerate(chunks, start=1):
        status_container.write(f"🧠 Bloco {i}/{len(chunks)} ({len(ck):,} chars) — {random_fun_message()}")
        prompt = PROMPT_RESUMO_TEMPLATE.format(material=ck)
        partial = stream_call(
            client,
            model=summary_model,
            system_prompt=(
                "És um Professor Catedrático. Este texto faz parte de um documento maior — "
                f"resume EXCLUSIVAMENTE o material apresentado neste bloco ({i}/{len(chunks)})."
            ),
            user_prompt=prompt,
            status_obj=status_container,
            temperature=0.4,
            max_tokens=6000,
            show_stream=True,
        )
        parts.append(f"<!-- Bloco {i}/{len(chunks)} -->\n\n{partial}")

    return "\n\n---\n\n".join(parts)


def auto_process_uploaded_pdfs(uploaded_files) -> None:
    """
    Para cada PDF NOVO no uploader:
      1) Extrai texto (PyMuPDF).
      2) Gera resumo via LLM (se houver API key).
      3) Guarda em st.session_state.pdf_database.
    Persistência estrita — PDFs já em memória não são reprocessados.
    """
    api_key = st.session_state.nvidia_api_key
    if not api_key:
        st.warning(
            "⚠️ Sem **NVIDIA API Key** em ⚙️ Configurações: os PDFs ficam só com o "
            "texto extraído (resumo pendente, gera-se à mão por tab).",
            icon="⚠️",
        )

    client = get_nvidia_client(api_key) if api_key else None
    new_files = [f for f in uploaded_files if f.name not in st.session_state.pdf_database]
    if not new_files:
        return

    for f in new_files:
        with st.status(
            f"📄 A processar **{f.name}** — {random_fun_message()}",
            expanded=True,
        ) as s:
            try:
                s.write("⛏️ A extrair texto do PDF (PyMuPDF)…")
                meta = extract_pdf_text(f.getvalue())
                raw_text: str = meta["text"]      # type: ignore[assignment]
                n_pages: int = meta["pages"]      # type: ignore[assignment]
                n_chars: int = meta["chars"]      # type: ignore[assignment]
                s.write(f"📑 {n_pages} páginas · {n_chars:,} caracteres extraídos.")

                if not raw_text.strip():
                    st.session_state.pdf_database[f.name] = {
                        "raw_text": "",
                        "summary": "_Não foi possível extrair texto deste PDF (provavelmente é uma digitalização sem OCR)._",
                        "pages": n_pages,
                        "chars": 0,
                        "auto_generated": False,
                    }
                    s.update(
                        label=f"⚠️ `{f.name}` — texto vazio (digitalização sem OCR?).",
                        state="error",
                        expanded=True,
                    )
                    continue

                if client is None:
                    st.session_state.pdf_database[f.name] = {
                        "raw_text": raw_text,
                        "summary": (
                            "_Texto extraído com sucesso. Define a tua NVIDIA API Key em "
                            "**⚙️ Configurações** e clica em **🔄 Refazer resumo** acima._"
                        ),
                        "pages": n_pages,
                        "chars": n_chars,
                        "auto_generated": False,
                    }
                    s.update(
                        label=f"✅ `{f.name}` — texto extraído (resumo pendente, sem API key).",
                        state="complete",
                        expanded=False,
                    )
                    continue

                summary_md = summarize_pdf(client, f.name, raw_text, status_container=s)
                st.session_state.pdf_database[f.name] = {
                    "raw_text": raw_text,
                    "summary": summary_md,
                    "pages": n_pages,
                    "chars": n_chars,
                    "auto_generated": True,
                }
                s.update(
                    label=f"✅ `{f.name}` resumido com sucesso!",
                    state="complete",
                    expanded=False,
                )

            except OpenAIError as e:
                s.markdown(friendly_api_error(e))
                s.update(label=f"❌ Falha ao processar `{f.name}`.", state="error", expanded=True)
            except Exception as e:
                s.error(f"❌ Erro inesperado ao processar `{f.name}`: {e}")
                s.update(label=f"❌ Erro em `{f.name}`.", state="error", expanded=True)


def regenerate_summary(pdf_name: str) -> None:
    """Refaz o resumo de UM PDF (botão por-tab)."""
    api_key = st.session_state.nvidia_api_key
    if not api_key:
        st.warning("Define a NVIDIA API Key primeiro.")
        return
    if pdf_name not in st.session_state.pdf_database:
        return

    entry = st.session_state.pdf_database[pdf_name]
    raw_text = entry.get("raw_text", "")
    if not raw_text:
        st.error("Este PDF não tem texto extraído.")
        return

    client = get_nvidia_client(api_key)
    with st.status(
        f"🔄 A refazer o resumo de **{pdf_name}** — {random_fun_message()}", expanded=True
    ) as s:
        try:
            new_summary = summarize_pdf(client, pdf_name, raw_text, status_container=s)
            entry["summary"] = new_summary
            entry["auto_generated"] = True
            st.session_state.pdf_database[pdf_name] = entry
            s.update(label=f"✅ Resumo de `{pdf_name}` refeito!", state="complete", expanded=False)
        except OpenAIError as e:
            s.markdown(friendly_api_error(e))
            s.update(label="❌ Falha ao refazer resumo.", state="error", expanded=True)


# =============================================================================
# 9. LOOP DE CONSENSO CIRCULAR — AVALIAÇÃO INTERATIVA
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
    head = response.strip()[:300].upper()
    return UNANIMITY_TOKEN.upper() in head


def run_eval_consensus(
    client: OpenAI,
    full_material: str,
    *,
    max_iterations: int,
    ui_container,
) -> DebateResult:
    """
    Consenso Circular Estrito:
      V1: Chefe produz → validadores são A e B; AMBOS têm de aprovar.
      Se A reescrever: A torna-se autor → validadores: B e Chefe.
      Se B reescrever: B torna-se autor → validadores: A e Chefe.
      Se Chefe reescrever: validadores voltam a ser A e B.
      Loop até unanimidade dos dois não-autores OU max_iterations.

    Performance:
      - Validadores: max_tokens reduzido (3000); prompt conciso.
      - Reescrita pelo validador: continua a caber em 3000 tokens
        (≈ 12k chars — suficiente para teste compacto).
    """
    history: List[DebateEntry] = []

    # FASE 0 — Chefe cria V1 -------------------------------------------------
    with ui_container.status(
        f"{AGENT_ICONS['Chefe']} **Chefe** a criar V1 do Teste — {random_fun_message()}",
        expanded=True,
    ) as s:
        chefe_model = get_model("Chefe")
        s.write(f"Modelo: `{chefe_model}`")
        user_prompt = (
            "MATÉRIA DE ESTUDO COMPLETA:\n\n"
            f"{full_material}\n\n---\n\n"
            "Produz agora o Teste de Revisão seguindo rigorosamente a estrutura."
        )
        initial_draft = stream_call(
            client,
            model=chefe_model,
            system_prompt=EVAL_INITIAL_SYSTEM,
            user_prompt=user_prompt,
            status_obj=s,
            temperature=0.35,
            max_tokens=5500,
        )
        s.update(label="✅ **Chefe** entregou a V1", state="complete", expanded=False)

    history.append(DebateEntry(0, "Chefe", None, initial_draft, "draft"))

    current_author = "Chefe"
    current_content = initial_draft
    version_number = 1

    # FASE 1+ — Rondas circulares --------------------------------------------
    for iteration in range(1, max_iterations + 1):
        ui_container.markdown(
            f"<div class='round-tag'>🔄 Ronda {iteration} de {max_iterations} · "
            f"V{version_number} (autoria: {current_author})</div>",
            unsafe_allow_html=True,
        )

        # REGRA DE OURO — validadores são os 2 que NÃO são autores.
        validators_this_round = [a for a in AGENTS_ORDER if a != current_author]

        approvals_this_round: List[str] = []
        rewrite_happened = False

        for validator_name in validators_this_round:
            with ui_container.status(
                f"{AGENT_ICONS[validator_name]} **{validator_name}** "
                f"a avaliar V{version_number} de **{current_author}** — {random_fun_message()}",
                expanded=True,
            ) as s:
                v_model = get_model(validator_name)
                s.write(f"Modelo: `{v_model}`")

                system_prompt = EVAL_VALIDATION_SYSTEM.format(
                    validator=validator_name,
                    author=current_author,
                    token=UNANIMITY_TOKEN,
                )
                user_prompt = (
                    "MATÉRIA DE ESTUDO ORIGINAL:\n\n"
                    f"{full_material}\n\n---\n\n"
                    f"TESTE A AVALIAR (autoria: {current_author}, V{version_number}):\n\n"
                    f"{current_content}\n\n---\n\n"
                    f"DECIDE AGORA — aprovar com `{UNANIMITY_TOKEN}` ou reescrever o teste completo."
                )
                response = stream_call(
                    client,
                    model=v_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    status_obj=s,
                    temperature=0.2,
                    max_tokens=3000,  # validadores rápidos
                )

                if is_approval(response):
                    approvals_this_round.append(validator_name)
                    history.append(
                        DebateEntry(iteration, validator_name, current_author, response, "approval")
                    )
                    s.update(
                        label=f"✅ **{validator_name}** aprovou ({UNANIMITY_TOKEN})",
                        state="complete",
                        expanded=False,
                    )
                else:
                    history.append(
                        DebateEntry(iteration, validator_name, current_author, response, "rewrite")
                    )
                    version_number += 1
                    s.update(
                        label=(
                            f"✏️ **{validator_name}** reescreveu — nova V{version_number}. "
                            f"Próxima ronda: validadores são os outros 2."
                        ),
                        state="complete",
                        expanded=False,
                    )
                    current_author = validator_name
                    current_content = response
                    rewrite_happened = True
                    break  # ronda termina aqui; nova ronda com rotação circular

        # Verifica consenso
        if not rewrite_happened and len(approvals_this_round) == len(validators_this_round):
            ui_container.markdown(
                f"<div class='consensus-banner'>🎉 Consenso atingido na ronda {iteration}! "
                f"V{version_number} de {current_author} aprovada por "
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
        f"<div class='no-consensus-banner'>⏱️ Limite de {max_iterations} rondas atingido. "
        f"Versão final: V{version_number} (autoria de {current_author}).</div>",
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
# 10. ESTADO DA SESSÃO
# =============================================================================
DEFAULT_MAX_ITER = 4

st.session_state.setdefault("nvidia_api_key", "")
st.session_state.setdefault("max_iterations", DEFAULT_MAX_ITER)
st.session_state.setdefault("agent_models", DEFAULT_MODELS.copy())
st.session_state.setdefault("summary_model", DEFAULT_SUMMARY_MODEL)
# pdf_database: {pdf_name: {raw_text, summary, pages, chars, auto_generated}}
st.session_state.setdefault("pdf_database", {})
st.session_state.setdefault("eval_selected_pdfs", [])
st.session_state.setdefault("eval_result", None)
st.session_state.setdefault("_processed_signatures", set())

# Carrega chave de st.secrets se existir
if not st.session_state.nvidia_api_key:
    try:
        secret_key = st.secrets.get("NVIDIA_API_KEY", "")
        if secret_key:
            st.session_state.nvidia_api_key = secret_key
    except Exception:
        pass


# =============================================================================
# 11. BARRA LATERAL
# =============================================================================
with st.sidebar:
    st.markdown(
        f"<h2 style='color:{ISEL_PRIMARY};margin-top:0'>📊 Análise de Custos</h2>"
        f"<p style='color:{ISEL_MUTED};margin-top:-0.5rem;font-size:0.9rem'>"
        f"ISEL · Instituto Superior de Engenharia de Lisboa</p>",
        unsafe_allow_html=True,
    )

    # --- ⚙️ Configurações ---------------------------------------------------
    with st.expander("⚙️ Configurações", expanded=not st.session_state.nvidia_api_key):
        api_key_input = st.text_input(
            "🔑 NVIDIA API Key",
            value=st.session_state.nvidia_api_key,
            type="password",
            placeholder="nvapi-…",
            help="Necessária para gerar resumos automáticos e avaliações.",
        )
        if api_key_input != st.session_state.nvidia_api_key:
            st.session_state.nvidia_api_key = api_key_input
            st.rerun()

        max_iter_input = st.slider(
            "🔁 Máximo de rondas (avaliação)",
            min_value=2, max_value=10,
            value=st.session_state.max_iterations,
        )
        if max_iter_input != st.session_state.max_iterations:
            st.session_state.max_iterations = max_iter_input

        st.markdown("**🤖 Modelo do Catedrático (resumos)**")
        new_sm = st.text_input(
            "Modelo de resumo",
            value=st.session_state.summary_model,
            key="summary_model_input",
            label_visibility="collapsed",
        )
        if new_sm.strip() and new_sm.strip() != st.session_state.summary_model:
            st.session_state.summary_model = new_sm.strip()

        st.markdown("**🤖 Modelos do Debate (avaliação)**")
        st.caption("Erro 404? Muda aqui para um modelo a que tenhas acesso.")
        for agent_name in AGENTS_ORDER:
            new_val = st.text_input(
                f"{AGENT_ICONS[agent_name]} {agent_name}",
                value=st.session_state.agent_models.get(agent_name, DEFAULT_MODELS[agent_name]),
                key=f"model_input_{agent_name}",
            )
            st.session_state.agent_models[agent_name] = new_val.strip()

        if st.button("↺ Repor modelos por defeito", use_container_width=True, key="reset_models"):
            st.session_state.agent_models = DEFAULT_MODELS.copy()
            st.session_state.summary_model = DEFAULT_SUMMARY_MODEL
            st.rerun()

        if st.session_state.nvidia_api_key:
            st.success("🔒 Chave carregada — IA ativa", icon="✅")
        else:
            st.warning("Sem chave — IA inativa.", icon="⚠️")

    st.divider()

    # --- 📁 Upload de PDFs --------------------------------------------------
    st.markdown("##### 📁 Carregar PDFs")
    uploaded_files = st.file_uploader(
        "Carrega PDFs da matéria",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Cada PDF é automaticamente resumido pelo Catedrático ao ser carregado.",
    )

    # Processamento automático no upload (só ficheiros novos nesta sessão)
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
        st.success(f"✅ {len(db)} PDF(s) em memória")
        total_chars = sum(int(e.get("chars", 0)) for e in db.values())
        total_pages = sum(int(e.get("pages", 0)) for e in db.values())
        st.caption(f"📄 {total_pages} páginas · {total_chars:,} caracteres no total")

    st.divider()

    # --- 🤖 Atalho IA --------------------------------------------------------
    st.markdown("##### 🤖 IA Multi-Agente")
    st.markdown(
        "<div class='sidebar-pill'>🎓 Avaliação Interativa</div>",
        unsafe_allow_html=True,
    )
    st.caption("Tab sempre disponível no painel principal.")

    st.divider()

    # --- 🗑️ Gestão da Base de Dados ----------------------------------------
    st.markdown("##### 🗑️ Base de Dados")
    if db:
        confirm_delete = st.checkbox(
            "Confirmar apagar TUDO",
            key="confirm_delete_db",
            help="Marca esta caixa para libertar o botão de apagar.",
        )
        if st.button(
            "🗑️ Apagar Base de Dados de Resumos",
            disabled=not confirm_delete,
            use_container_width=True,
            type="secondary",
            key="delete_db_btn",
        ):
            st.session_state.pdf_database = {}
            st.session_state._processed_signatures = set()
            st.session_state.eval_result = None
            st.session_state.eval_selected_pdfs = []
            st.session_state.confirm_delete_db = False
            st.success("Base de dados apagada.")
            time.sleep(0.4)
            st.rerun()
    else:
        st.caption("(sem PDFs carregados)")


# =============================================================================
# 12. CABEÇALHO PRINCIPAL
# =============================================================================
st.markdown(
    f"""
    <div class="isel-banner">
        <h1>📊 Análise de Custos</h1>
        <p class="subtitle">Plataforma de Estudo Interativa · Instituto Superior de Engenharia de Lisboa</p>
        <div>
            <span class="badge">🧠 Resumos por IA</span>
            <span class="badge">🎓 Avaliação Multi-Agente</span>
            <span class="badge">📄 PDF nativo</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 13. RENDERIZADORES
# =============================================================================
def render_agent_panel() -> None:
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


def render_pdf_tab(pdf_name: str, entry: Dict) -> None:
    """Tab única por PDF — resumo completo em scroll vertical."""
    st.markdown(f"## 📄 {pdf_name}")

    pages = entry.get("pages", "?")
    chars = int(entry.get("chars", 0))
    auto = entry.get("auto_generated", False)
    badge = "🤖 Resumo gerado automaticamente" if auto else "📝 Resumo pendente"
    st.markdown(
        f"<div class='pdf-meta'>📑 <b>{pages}</b> páginas · "
        f"{chars:,} caracteres extraídos · {badge}</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 1, 1, 3])
    with cols[0]:
        if st.button("🔄 Refazer resumo", key=f"regen_{pdf_name}", use_container_width=True):
            regenerate_summary(pdf_name)
            st.rerun()
    with cols[1]:
        st.download_button(
            "📥 .md",
            data=entry.get("summary", ""),
            file_name=f"{pdf_name}.resumo.md",
            mime="text/markdown",
            key=f"dl_summary_{pdf_name}",
            use_container_width=True,
        )
    with cols[2]:
        st.download_button(
            "📥 raw",
            data=entry.get("raw_text", ""),
            file_name=f"{pdf_name}.raw.txt",
            mime="text/plain",
            key=f"dl_raw_{pdf_name}",
            use_container_width=True,
        )

    st.divider()

    summary = entry.get("summary", "")
    if summary:
        st.markdown(summary)
    else:
        st.warning("Este PDF ainda não tem resumo. Carrega em **🔄 Refazer resumo** acima.")

    with st.expander("🔍 Ver texto extraído do PDF (debug)", expanded=False):
        raw = entry.get("raw_text", "")
        st.text(raw[:50_000] + ("\n\n[... truncado ...]" if len(raw) > 50_000 else ""))


def render_debate_history(result: DebateResult) -> None:
    with st.expander(f"🗂️ Histórico do debate ({len(result.history)} intervenções)"):
        for entry in result.history:
            icon = AGENT_ICONS[entry.author]
            if entry.kind == "draft":
                tag = "📝 Rascunho inicial (V1)"
            elif entry.kind == "approval":
                tag = f"✅ Aprovou a versão de {entry.target_author}"
            else:
                tag = f"✏️ Reescreveu (V de {entry.target_author})"
            st.markdown(f"**Ronda {entry.iteration} · {icon} {entry.author}** — {tag}")
            with st.container(border=True):
                if entry.kind == "approval":
                    st.code(entry.content[:1500], language="markdown")
                else:
                    st.markdown(entry.content)
            st.write("")


def render_evaluation_tab() -> None:
    st.markdown("### 🎓 Avaliação Interativa")
    st.caption(
        "Os três agentes debatem em loop circular estrito até que os dois "
        "não-autores aprovem unanimemente o teste (ou se atinja o limite de rondas)."
    )
    st.write("")

    db = st.session_state.pdf_database
    if not db:
        st.info("📁 Começa por carregar PDFs na barra lateral.")
        return

    # --- Seleção de PDFs ----------------------------------------------------
    st.markdown("<div class='section-title'>📚 PDFs a incluir na avaliação</div>", unsafe_allow_html=True)

    valid_sel = [n for n in st.session_state.eval_selected_pdfs if n in db]
    if valid_sel != st.session_state.eval_selected_pdfs:
        st.session_state.eval_selected_pdfs = valid_sel

    chosen = st.multiselect(
        "Que PDFs queres incluir?",
        options=list(db.keys()),
        default=st.session_state.eval_selected_pdfs,
        key="eval_multiselect",
        help="Apenas o conteúdo destes PDFs alimenta o Catedrático no rascunho inicial.",
    )
    if chosen != st.session_state.eval_selected_pdfs:
        st.session_state.eval_selected_pdfs = chosen

    cols_sel = st.columns(2)
    with cols_sel[0]:
        if st.button("✅ Selecionar todos", use_container_width=True, key="sel_all_eval"):
            st.session_state.eval_selected_pdfs = list(db.keys())
            st.rerun()
    with cols_sel[1]:
        if st.button("🚫 Limpar seleção", use_container_width=True, key="sel_none_eval"):
            st.session_state.eval_selected_pdfs = []
            st.rerun()

    st.write("")

    # --- Cards dos agentes --------------------------------------------------
    render_agent_panel()
    st.write("")

    # --- Botão --------------------------------------------------------------
    api_key = st.session_state.nvidia_api_key
    max_iter = st.session_state.max_iterations
    selected = st.session_state.eval_selected_pdfs
    can_run = bool(api_key) and bool(selected)

    cols = st.columns([3, 1])
    with cols[0]:
        existing = st.session_state.get("eval_result")
        btn_label = "🔄 Refazer Avaliação" if existing else "🚀 Iniciar Debate Multi-Agente"
        run = st.button(
            btn_label,
            type="primary",
            disabled=not can_run,
            use_container_width=True,
            key="run_eval",
        )
    with cols[1]:
        if st.session_state.get("eval_result"):
            if st.button("🗑️ Limpar", use_container_width=True, key="clear_eval"):
                st.session_state.eval_result = None
                st.rerun()

    if not api_key:
        st.warning("Define a NVIDIA API Key em **⚙️ Configurações**.")
    elif not selected:
        st.warning("Seleciona pelo menos um PDF acima.")
    else:
        st.caption(
            f"Limite atual: **{max_iter} rondas** · "
            f"PDFs selecionados: **{len(selected)}**."
        )

    # --- Execução ------------------------------------------------------------
    if run and can_run:
        st.session_state.eval_result = None
        debate_container = st.container()
        debate_container.markdown("#### 🎬 Debate em curso")

        loading_slot = debate_container.empty()
        show_fun_loading(loading_slot)

        try:
            client = get_nvidia_client(api_key)

            # Material = RESUMOS dos PDFs selecionados (mais denso, ideal para
            # o Chefe). Se um resumo não existir, recorre ao texto bruto.
            material_parts: List[str] = []
            for pdf_name in selected:
                entry = db.get(pdf_name, {})
                src = entry.get("summary") or entry.get("raw_text", "")
                material_parts.append(f"\n=== PDF: {pdf_name} ===\n\n{src}")
            full_material = "\n\n".join(material_parts).strip()

            original_len = len(full_material)
            full_material = safe_truncate(full_material, MAX_CHARS_FOR_EVAL_INPUT)
            if len(full_material) < original_len:
                debate_container.info(
                    f"📏 Matéria muito extensa ({original_len:,} chars). "
                    f"Truncada para {len(full_material):,} chars."
                )

            loading_slot.empty()
            result = run_eval_consensus(
                client=client,
                full_material=full_material,
                max_iterations=max_iter,
                ui_container=debate_container,
            )
            st.session_state.eval_result = result

        except OpenAIError as e:
            loading_slot.empty()
            debate_container.markdown(friendly_api_error(e))
        except Exception as e:
            loading_slot.empty()
            debate_container.error(f"❌ Erro inesperado: {e}")

    # --- Resultado ----------------------------------------------------------
    result: Optional[DebateResult] = st.session_state.get("eval_result")
    if result:
        st.divider()
        status_emoji = "🎉" if result.consensus_reached else "⏱️"
        status_text = (
            f"Consenso em {result.iterations_used} ronda(s)"
            if result.consensus_reached
            else f"Limite de {result.iterations_used} rondas atingido"
        )
        st.markdown(f"## {status_emoji} Versão Final · {status_text}")
        st.caption(f"Autoria final: **{AGENT_ICONS[result.final_author]} {result.final_author}**")

        with st.container(border=True):
            st.markdown(result.final_content)

        st.download_button(
            "📥 Descarregar teste em Markdown",
            data=result.final_content,
            file_name="teste_revisao.md",
            mime="text/markdown",
            key="dl_eval_result",
        )

        render_debate_history(result)


# =============================================================================
# 14. CONSTRUÇÃO DAS TABS — uma por PDF + 1 fixa de Avaliação
# =============================================================================
db = st.session_state.pdf_database

if not db:
    with st.container(border=True):
        st.markdown("### 👋 Bem-vindo")
        st.write("Carrega os teus PDFs de Análise de Custos na barra lateral. A plataforma irá automaticamente:")
        st.markdown(
            "- ⛏️ Extrair o texto de cada PDF (via PyMuPDF)  \n"
            "- 🧠 Pedir ao **Catedrático** que gere um resumo académico estruturado  \n"
            "- 📚 Abrir uma **tab por PDF** com o resumo completo em scroll  \n"
            "- 🎓 Disponibilizar uma **avaliação interativa** com debate multi-agente"
        )

    tab = st.tabs(["🎓 Avaliação Interativa"])
    with tab[0]:
        render_evaluation_tab()

else:
    pdf_names = list(db.keys())

    tab_labels: List[str] = []
    for name in pdf_names:
        label = name if len(name) <= 50 else name[:47] + "…"
        tab_labels.append(f"📄 {label}")
    tab_labels.append("🎓 Avaliação Interativa")

    tabs = st.tabs(tab_labels)

    for i, pdf_name in enumerate(pdf_names):
        with tabs[i]:
            render_pdf_tab(pdf_name, db[pdf_name])

    with tabs[-1]:
        render_evaluation_tab()
