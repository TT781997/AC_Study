"""
app.py — Plataforma de Estudo: Análise de Custos
=================================================
Aplicação Streamlit para centralizar e estudar resumos da unidade curricular
de Análise de Custos, com pesquisa global, navegação por capítulo e modo Flashcard.

Como executar:
    streamlit run app.py

Dependências (ver requirements.txt):
    pip install streamlit
"""

import re
from typing import Dict, List, Tuple

import streamlit as st

# -----------------------------------------------------------------------------
# Configuração da página
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Análise de Custos | Plataforma de Estudo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS leve para refinamentos visuais (sem alterar a UX do Streamlit)
st.markdown(
    """
    <style>
        .block-container { padding-top: 2.5rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: #1f3a5f; }
        .stExpander { border-radius: 8px; }
        .chapter-meta { color: #6c757d; font-size: 0.9rem; margin-bottom: 1rem; }
        /* Snippet de resultados de pesquisa */
        .search-snippet { background-color: #fff7e6; padding: 0.5rem 0.75rem;
                          border-left: 3px solid #f0ad4e; border-radius: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Marcadores das secções: chave interna -> texto exato presente no markdown
# -----------------------------------------------------------------------------
SECTION_MARKERS: Dict[str, str] = {
    "foco":       "🎯 Foco Principal",
    "conceitos":  "🧠 Conceitos-Chave",
    "formulas":   "🧮 Fórmulas e Metodologias",
    "aplicacao":  "🏭 Aplicação",
    "dica":       "🎓 Dica do Catedrático",
}


# -----------------------------------------------------------------------------
# Funções de parsing
# -----------------------------------------------------------------------------
def parse_sections(chapter_body: str) -> Dict[str, str]:
    """
    Extrai as 5 secções padrão (foco, conceitos, fórmulas, aplicação, dica)
    a partir do corpo de um capítulo.

    A estratégia é: localizar a posição de cada marcador no texto e
    capturar o conteúdo entre o fim de um marcador e o início do seguinte.
    Isto torna o parser tolerante a quebras de linha, sub-bullets e ordem
    inesperada das secções.
    """
    sections: Dict[str, str] = {key: "" for key in SECTION_MARKERS}
    positions: List[Tuple[int, int, str]] = []

    for key, marker in SECTION_MARKERS.items():
        # Padrão tolerante: "* **<marker>:**" (o "* " inicial é opcional)
        pattern = r"(?:\*\s+)?\*\*" + re.escape(marker) + r":\*\*"
        match = re.search(pattern, chapter_body)
        if match:
            positions.append((match.start(), match.end(), key))

    # Ordena pelas posições de início para podermos delimitar cada secção
    positions.sort(key=lambda x: x[0])

    for i, (_, marker_end, key) in enumerate(positions):
        next_start = positions[i + 1][0] if i + 1 < len(positions) else len(chapter_body)
        sections[key] = chapter_body[marker_end:next_start].strip()

    return sections


def parse_chapters(doc_body: str) -> Dict[str, Dict[str, str]]:
    """
    Divide o corpo de um documento em capítulos delimitados por '#### '.
    Devolve um dicionário { título_capítulo: { secção: conteúdo } }.
    """
    chapters: Dict[str, Dict[str, str]] = {}
    chapter_pattern = r"####\s*([^\n]+)"
    matches = list(re.finditer(chapter_pattern, doc_body))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(doc_body)
        body = doc_body[body_start:body_end]
        chapters[title] = parse_sections(body)

    return chapters


def parse_content(
    text: str,
    fallback_name: str = "Documento sem título",
) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Faz o parsing completo de um ficheiro de resumos.

    Devolve um dicionário aninhado com a estrutura:
        { nome_documento: { título_capítulo: { secção: conteúdo } } }

    Se o ficheiro não contiver cabeçalho '### 📄 Documento:', usa
    'fallback_name' (tipicamente o nome do ficheiro) como nome do documento.
    """
    result: Dict[str, Dict[str, Dict[str, str]]] = {}

    # O emoji 📄 é opcional para tolerar pequenas variações de formatação
    doc_pattern = r"###\s*(?:📄\s*)?Documento:\s*([^\n]+)"
    matches = list(re.finditer(doc_pattern, text))

    if not matches:
        chapters = parse_chapters(text)
        if chapters:
            result[fallback_name] = chapters
        return result

    for i, m in enumerate(matches):
        doc_name = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        chapters = parse_chapters(body)
        if chapters:
            # Se o mesmo nome de documento aparecer em vários ficheiros,
            # juntamos os capítulos em vez de sobrepor.
            if doc_name in result:
                result[doc_name].update(chapters)
            else:
                result[doc_name] = chapters

    return result


def search_global(data: Dict, query: str) -> List[Tuple[str, str, str]]:
    """
    Pesquisa case-insensitive em todas as secções de todos os capítulos.
    Devolve uma lista de tuplos (documento, capítulo, excerto contextual).
    """
    results: List[Tuple[str, str, str]] = []
    q = query.strip().lower()
    if not q:
        return results

    for doc, chapters in data.items():
        for ch_title, sections in chapters.items():
            full_text = "\n".join(sections.values())
            lower = full_text.lower()
            idx = lower.find(q)
            if idx == -1:
                continue
            # Constrói um excerto com algum contexto à volta da ocorrência
            start = max(0, idx - 70)
            end = min(len(full_text), idx + len(q) + 70)
            snippet = full_text[start:end].replace("\n", " ").strip()
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(full_text) else ""
            results.append((doc, ch_title, f"{prefix}{snippet}{suffix}"))
    return results


# -----------------------------------------------------------------------------
# Estado da sessão
# -----------------------------------------------------------------------------
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = {}
if "files_signature" not in st.session_state:
    st.session_state.files_signature = None


# -----------------------------------------------------------------------------
# Barra lateral — pesquisa, upload e navegação
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 Análise de Custos")
    st.caption("Plataforma de Estudo")

    # 1) Pesquisa global (no topo, conforme requisito)
    search_query = st.text_input(
        "🔍 Pesquisa global",
        placeholder="Ex: Custeio Variável",
        help="Procura o termo em todos os documentos e capítulos carregados.",
    )

    st.divider()

    # 2) Upload de ficheiros
    st.subheader("📁 Carregar resumos")
    uploaded_files = st.file_uploader(
        "Ficheiros .txt ou .md",
        type=["txt", "md"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    # Faz o parsing apenas quando o conjunto de ficheiros muda
    if uploaded_files:
        signature = tuple((f.name, f.size) for f in uploaded_files)
        if signature != st.session_state.files_signature:
            combined: Dict[str, Dict[str, Dict[str, str]]] = {}
            for f in uploaded_files:
                try:
                    content = f.getvalue().decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback para ficheiros codificados em latin-1
                    content = f.getvalue().decode("latin-1")
                fallback = f.name.rsplit(".", 1)[0]
                parsed = parse_content(content, fallback_name=fallback)
                for doc_name, chapters in parsed.items():
                    if doc_name in combined:
                        combined[doc_name].update(chapters)
                    else:
                        combined[doc_name] = chapters
            st.session_state.parsed_data = combined
            st.session_state.files_signature = signature

    data = st.session_state.parsed_data

    # Pequeno indicador do que está carregado
    if data:
        n_docs = len(data)
        n_chapters = sum(len(ch) for ch in data.values())
        st.success(f"✅ {n_docs} documento(s), {n_chapters} capítulo(s) carregados.")

    st.divider()

    # 3) Navegação Documento -> Capítulo
    selected_doc = None
    selected_chapter = None
    flashcard_mode = False

    if data:
        st.subheader("📚 Navegação")
        doc_names = sorted(data.keys())
        selected_doc = st.selectbox("Documento", doc_names)

        if selected_doc:
            chapter_titles = list(data[selected_doc].keys())
            selected_chapter = st.selectbox("Capítulo", chapter_titles)

        st.divider()

        # 4) Modo Flashcard
        st.subheader("⚙️ Modo de estudo")
        flashcard_mode = st.toggle(
            "🃏 Modo Flashcard",
            help="Esconde os Conceitos-Chave até clicar em 'Revelar'. Ajuda na retenção.",
        )


# -----------------------------------------------------------------------------
# Área principal
# -----------------------------------------------------------------------------
st.title("📊 Análise de Custos")
st.caption("Plataforma interativa para revisão e estudo dos seus resumos.")
st.divider()

# --- Caso A: pesquisa global ativa --------------------------------------------
if search_query and data:
    st.subheader(f"🔍 Resultados para: «{search_query}»")
    results = search_global(data, search_query)

    if results:
        st.success(f"Encontradas **{len(results)}** ocorrência(s).")
        for doc, ch, snippet in results:
            with st.container(border=True):
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.markdown(f"**📄 Documento:** {doc}")
                with col2:
                    st.markdown(f"**📖 Capítulo:** {ch}")
                st.markdown(
                    f"<div class='search-snippet'>{snippet}</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.warning("Nenhum resultado encontrado para o termo pesquisado.")

# --- Caso B: ainda não foram carregados ficheiros -----------------------------
elif not data:
    st.info("👈 Carregue os seus ficheiros de resumos na barra lateral para começar.")

    with st.expander("ℹ️ Estrutura esperada dos ficheiros"):
        st.markdown(
            """
Cada ficheiro `.txt` ou `.md` deve seguir esta estrutura:

```markdown
### 📄 Documento: Nome do Documento

#### Capítulo 1: Título do Capítulo

* **🎯 Foco Principal:** Descrição do foco do capítulo.

* **🧠 Conceitos-Chave:**
  * Conceito A — definição
  * Conceito B — definição

* **🧮 Fórmulas e Metodologias:** Fórmulas relevantes.

* **🏭 Aplicação:** Como aplicar este conhecimento.

* **🎓 Dica do Catedrático:** Insight prático do professor.
```

> ✅ Pode carregar vários ficheiros em simultâneo.  
> ✅ Cada ficheiro pode conter vários documentos e vários capítulos.
            """
        )

# --- Caso C: capítulo selecionado — apresentação do conteúdo ------------------
elif selected_doc and selected_chapter:
    sections = data[selected_doc][selected_chapter]

    # Cabeçalho do capítulo
    st.header(selected_chapter)
    st.markdown(
        f"<div class='chapter-meta'>📄 {selected_doc}</div>",
        unsafe_allow_html=True,
    )

    # 🎯 Foco Principal — em destaque (st.info)
    if sections.get("foco"):
        st.markdown("### 🎯 Foco Principal")
        st.info(sections["foco"])

    # 🧠 Conceitos-Chave — com lógica de Modo Flashcard
    if sections.get("conceitos"):
        st.markdown("### 🧠 Conceitos-Chave")

        if flashcard_mode:
            # Chave única por capítulo: cada flashcard tem estado independente
            reveal_key = f"reveal::{selected_doc}::{selected_chapter}"
            revealed = st.session_state.get(reveal_key, False)

            if revealed:
                st.markdown(sections["conceitos"])
                if st.button("🙈 Esconder novamente", key=f"hide_btn::{reveal_key}"):
                    st.session_state[reveal_key] = False
                    st.rerun()
            else:
                st.warning(
                    "🃏 **Modo Flashcard ativo.** Tente recordar os conceitos antes de revelar."
                )
                if st.button("👁️ Revelar conceitos", key=f"show_btn::{reveal_key}"):
                    st.session_state[reveal_key] = True
                    st.rerun()
        else:
            st.markdown(sections["conceitos"])

    # 🧮 Fórmulas e Metodologias — destacadas num container com borda
    if sections.get("formulas"):
        st.markdown("### 🧮 Fórmulas e Metodologias")
        with st.container(border=True):
            st.markdown(sections["formulas"])

    # 🏭 Aplicação
    if sections.get("aplicacao"):
        st.markdown("### 🏭 Aplicação")
        st.markdown(sections["aplicacao"])

    # 🎓 Dica do Catedrático — escondida num expander (favorece memorização)
    if sections.get("dica"):
        st.write("")
        with st.expander("Ver Dica do Catedrático 🎓"):
            st.success(sections["dica"])

    # Rodapé com navegação contextual entre capítulos
    st.divider()
    chapter_list = list(data[selected_doc].keys())
    current_idx = chapter_list.index(selected_chapter)
    col_prev, col_mid, col_next = st.columns([2, 1, 2])
    with col_prev:
        if current_idx > 0:
            st.caption(f"⬅️ Anterior: *{chapter_list[current_idx - 1]}*")
    with col_mid:
        st.caption(f"**{current_idx + 1} / {len(chapter_list)}**")
    with col_next:
        if current_idx < len(chapter_list) - 1:
            st.caption(f"Próximo: *{chapter_list[current_idx + 1]}* ➡️")

else:
    st.info("Selecione um documento e um capítulo na barra lateral para começar a estudar.")
