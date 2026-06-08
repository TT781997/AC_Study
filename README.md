# 🎓 Universal ScholarGPT v5.2

**Multi-formato · Multi-modal · Persistência SQLite · Resiliente**

Sistema multi-agente em Python nativo (sem LangChain) que ingere documentos de
**10 formatos** (PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG, JPEG), processa-os
com Vision LLM quando necessário, debate o conteúdo entre 4 agentes especializados,
e persiste tudo em SQLite para acesso futuro instantâneo.

**9 ficheiros · 4 554 linhas · 31/31 testes ✅**

---

## Como correr

```bash
# 1. Descarrega a pasta universal_scholargpt_v52 inteira

# 2. Cria venv (recomendado)
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# 3. Instala dependências (núcleo + multi-formato)
pip install -r requirements.txt

# 4. (OPCIONAL) Para OCR local, instala também:
#    macOS:  brew install tesseract poppler
#    Linux:  sudo apt install tesseract-ocr poppler-utils
#    Windows: descarrega Tesseract OCR + Poppler binaries
# Se não instalares, o sistema usa Vision LLM (NVIDIA NIM) automaticamente.

# 5. Corre
cd universal_scholargpt_v52
streamlit run app.py
```

A app abre em `http://localhost:8501`. Segue o "How to use" na sidebar:
1. Vai a `https://build.nvidia.com/explore/discover`, obtém API key
2. Cola-a no campo "🔑 NVIDIA API Key"
3. Carrega um ficheiro de qualquer formato

A partir daí: tudo automático.

---

## Mapping spec → implementação

| Requisito | Implementação |
|---|---|
| §1 Multimodal Vision | `llm_client.call_vision_llm()` envia imagem base64 inline ao modelo NVIDIA NIM multimodal |
| §1 Resiliência (retry 429/timeout) | `llm_client.call_with_retry()` — exponential backoff 2/4/8s, cap 30s, max 3 tentativas, fail-fast em 404/401 |
| §2 Arquitetura modular | 9 ficheiros: `app·config·i18n·db·ingestion·llm_client·agents·document_processor·ui_components` |
| §2 `processed_files = dict {hash: doc_id}` | `app._init_session_state()` linha 67 |
| §2 `@st.cache_resource` para conn | `app.get_db_connection()` linha 53 |
| §3 SQLite com `init_db()` idempotente | `db.init_db()` com `_ensure_columns` para ALTER TABLE |
| §3 Tabela `Documents` | id · file_name · file_hash (UNIQUE INDEX) · file_type · created_at · raw_text · ocr_text · language |
| §3 Tabela `Analyses` | id · document_id (FK ON DELETE CASCADE) · summary_json · quiz_json · debate_log_json · created_at |
| §3 SQLite efémero → init silencioso | `init_db()` corre sempre no arranque sem efeitos colaterais |
| §4 Uploader dinâmico via `SUPPORTED_FORMATS` | `ui_components.render_sidebar()` usa `type=SUPPORTED_FORMATS` de `ingestion.py` |
| §4 ThreadPoolExecutor / st.status | `llm_client.stream_call_threaded()` worker thread + `Queue`; UI via `st.status()` |
| §5 `ingest_file(file) -> dict` | `ingestion.ingest_file()` devolve `{text, metadata, sources}` |
| §5 Fallback OCR `len(pdf_text) < 100` | `ingestion._needs_ocr_fallback()` + `_run_pdf_ocr()` cadeia Vision→Tesseract |
| §6 Pipeline com `file_hash` lookup | `document_processor.process_document_pipeline()` |
| §6 Cache hit serve de Analyses | `_build_result_from_cache()` |
| §6 Map-Reduce 60k chars | `chunk_text(MAX_CHARS_PER_SUMMARY_CHUNK=60_000)` |
| §6 Auditoria + Gap-fill | `_audit_coverage_against_index()` + `_generate_missing_sections()` injectadas antes de `📋 Cobertura` |
| §6 Debate guardado no log | `DebateLogEntry` serializado para `debate_log_json` |
| §6 Quiz com `st.expander("👀 Ver Respostas")` | `ui_components.render_quiz_with_answers_toggle()` |
| §6 Downloads .md | `_render_download_buttons()` (questions only + full) |

---

## Fluxo end-to-end

```
Upload → app.py._process_uploaded_files()
            ↓
        compute_file_hash (SHA-256)
            ↓
        process_document_pipeline()
            ├─ DB lookup por hash
            │   ├─ HIT  → _build_result_from_cache() → return (cached=True)
            │   └─ MISS ↓
            │
            ├─ ingest_file() ────► routing por extensão
            │    ├─ PDF: PyMuPDF
            │    │    └─ Se < 100 chars → fallback OCR:
            │    │         1. vision_callback (NVIDIA NIM multimodal)
            │    │         2. pdf2image + pytesseract
            │    │         3. PyMuPDF pixmap + vision
            │    ├─ DOCX: python-docx (paragraphs + tables)
            │    ├─ PPTX: python-pptx (shapes + notes)
            │    ├─ XLSX: pandas → openpyxl fallback
            │    ├─ HTML: bs4 → regex fallback
            │    ├─ TXT/MD: decode directo
            │    └─ PNG/JPG: vision_callback / pytesseract
            │
            ├─ db.get_or_insert_document() → doc_id
            │
            ├─ summarize_pdf_robust()  (pipeline 4 fases v5.1)
            │    ├─ extract_topic_index
            │    ├─ generate_summary (Map-Reduce 60k chars)
            │    ├─ audit_coverage (COVERAGE_OK/GAPS)
            │    └─ generate_missing_sections + inject
            │
            ├─ run_consensus_loop()  (debate 4 agentes)
            │    ├─ Chefe → V1
            │    └─ Loop: 3 APPROVE mesma ronda OR max_rounds
            │
            └─ db.insert_analysis() → JSONs persistidos
                ↓
            UI: render_document_tab (com cache badge, format pill)
```

Todas as chamadas LLM (`stream_call_threaded` + `call_vision_llm`) embrulhadas
em `call_with_retry` — 429/timeout/5xx → retry exponencial; 404/401 → fail-fast.

---

## Estrutura de ficheiros

```
9 ficheiros · 4 554 linhas
─────────────────────────────────────────────────────────────────
config.py                   419  constantes + CSS + MODEL_REGISTRY + VISION + RETRY
i18n.py                     532  5 línguas, ~130 chaves
db.py                       471  SQLite, init_db, CRUD, JSON helpers
ingestion.py                719  10 formatos, fallback OCR em camadas
llm_client.py               315  retry + Vision + streaming threaded
agents.py                   594  4 prompts + run_consensus_loop + parsing
document_processor.py       558  pipeline 4 fases + process_document_pipeline
ui_components.py            599  sidebar + Right Panel + Log Visual + cache badges
app.py                      347  wiring + @st.cache_resource + lazy load BD
```

---

## v5.2 vs v5.1 — o que mudou

| Aspecto | v5.1 | v5.2 |
|---|---|---|
| Formatos | só PDF | **10 formatos** (PDF/DOCX/PPTX/XLSX/HTML/MD/TXT/PNG/JPG/JPEG) |
| OCR | nenhum | Vision LLM (NVIDIA NIM multimodal) + Tesseract fallback |
| Persistência | só `session_state` (volátil) | **SQLite** com Documents + Analyses (cascade) |
| Cache | none | **DB lookup por SHA-256**, instant load |
| Resiliência | falha em 429 | **retry exponential backoff** (2/4/8s, max 3) |
| `processed_files` | `set` | **`dict {hash: doc_id}`** |
| Conn DB | n/a | **`@st.cache_resource`** singleton |
| Pipeline | manual em 2 fases | **`process_document_pipeline()`** end-to-end |
| Refazer análise | reprocessa tudo | reusa `raw_text` da BD, só recorre LLM |

---

## Limitações e notas práticas

- **SQLite efémero em cloud**: Streamlit Cloud reinicia o filesystem ao re-deploy. `init_db()` é chamada sempre no arranque, mas os dados anteriores podem-se perder. Para persistência real em cloud, montar volume externo (S3, GCS) e copiar `database.db` no boot.
- **Vision LLM requer modelo multimodal disponível na tua conta NVIDIA**. Default `meta/llama-3.2-90b-vision-instruct`; alternativas em `config.VISION_MODEL_FALLBACKS`. Muda em ⚙️ se 404.
- **OCR local opcional**: se não instalares `tesseract` e `poppler` no SO, o sistema usa só Vision LLM (mais qualidade mas usa créditos NVIDIA). Para 100% local sem créditos: `brew install tesseract poppler` (macOS) ou `apt install` equivalente.
- **PDFs muito grandes (>128 págs)**: continuam a demorar 12-20 min e gastar 15-25 chamadas LLM. Mas agora, a segunda vez que carregares o mesmo PDF, é instantâneo (cache hit).
- **Imagens (PNG/JPG)**: requerem `vision_callback` OU `pytesseract` instalado. Caso contrário, warning amigável sem crash.
- **Concorrência SQLite**: usa `PRAGMA journal_mode=WAL` para suportar múltiplas leituras durante escritas. Streamlit single-user: sem problemas. Multi-user na mesma conn: OK até alguns concurrent users.

---

Versões anteriores também em `outputs/`:
- `universal_scholargpt/` (v5.0)
- `universal_scholargpt_v51/` (v5.1)
- `universal_scholargpt_v52/` (esta, recomendada)
