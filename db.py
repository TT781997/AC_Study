"""
db.py — Camada de Persistência SQLite (Universal ScholarGPT v5.2)
==================================================================

Responsabilidades:
  • Esquema relacional (Documents + Analyses) com FK e índice único em file_hash
  • init_db() IDEMPOTENTE — corre sempre no arranque, em silêncio
  • Schema evolution leve via _ensure_columns (ALTER TABLE ADD COLUMN no-op se existir)
  • Conexão pronta para `@st.cache_resource` (uma só conexão por sessão)
  • Hash SHA-256 de ficheiros para deduplicação
  • Helpers CRUD com Row factory dict-like

Design:
  • sqlite3 puro (sem SQLAlchemy) — minimiza dependências
  • check_same_thread=False — necessário para Streamlit (vários threads partilham
    a conexão cached). Compensado por commits explícitos e PRAGMA WAL.
  • Foreign keys ON CASCADE — apagar Document remove Analyses dele
  • Aviso da spec: SQLite efémero em cloud → init_db sempre no arranque silencioso

Sem dependências internas. Apenas stdlib.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = "database.db"

# Esquema canónico — fonte de verdade. Adicionar novas colunas aqui faz
# init_db emitir ALTER TABLE ADD COLUMN no arranque seguinte (idempotente).
_DOCUMENTS_SCHEMA: List[Tuple[str, str]] = [
    ("id",         "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("file_name",  "TEXT    NOT NULL"),
    ("file_hash",  "TEXT    NOT NULL UNIQUE"),
    ("file_type",  "TEXT    NOT NULL"),
    ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("raw_text",   "TEXT"),
    ("ocr_text",   "TEXT"),
    ("language",   "TEXT"),
]

_ANALYSES_SCHEMA: List[Tuple[str, str]] = [
    ("id",                "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("document_id",       "INTEGER NOT NULL"),
    ("summary_json",      "TEXT"),
    ("quiz_json",         "TEXT"),
    ("debate_log_json",   "TEXT"),
    ("created_at",        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    # Foreign key declarada na CREATE TABLE; restantes via ALTER se evoluir
]


# ═══════════════════════════════════════════════════════════════════════════
# CONEXÃO
# ═══════════════════════════════════════════════════════════════════════════

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Devolve uma conexão SQLite configurada para uso em Streamlit.

    ⚠️ Deve ser embrulhado em `@st.cache_resource` no `app.py` para que
    cada sessão reuse a mesma conexão (Streamlit faz rerun e abrir/fechar
    a cada interacção é desperdício).

    Configurações:
      • check_same_thread=False: necessário para Streamlit (vários threads)
      • row_factory=Row: acesso por nome OU índice (row['file_name'])
      • PRAGMA foreign_keys=ON: garante ON DELETE CASCADE
      • PRAGMA journal_mode=WAL: melhor concorrência leitura/escrita
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """
    Context manager: commit no sucesso, rollback no erro.

    Uso:
        with transaction(conn):
            conn.execute(...)
            conn.execute(...)
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ═══════════════════════════════════════════════════════════════════════════
# init_db — idempotente, silencioso, schema evolution
# ═══════════════════════════════════════════════════════════════════════════

def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Inicializa a base de dados. Idempotente: pode ser chamada em todo o
    arranque sem efeitos colaterais.

    Cria tabelas se não existirem e, para tabelas existentes, adiciona
    colunas em falta via ALTER TABLE (suporta schema evolution leve).

    Aviso da spec §3: SQLite é efémero em deploys cloud (Streamlit Cloud
    reinicia o filesystem ao re-deploy). Por isso esta função deve ser
    chamada SEMPRE no arranque do app.

    Devolve a conexão (já com pragmas configurados) pronta a usar.
    """
    conn = get_connection(db_path)

    with transaction(conn):
        # ── Documents ──
        conn.execute(_build_create_table_ddl("Documents", _DOCUMENTS_SCHEMA))
        # Index único redundante (a coluna já tem UNIQUE) — explícito para
        # caso a coluna tenha sido adicionada via ALTER (sem UNIQUE inline)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_file_hash "
            "ON Documents(file_hash)"
        )
        # Index secundário para listagens por data
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_created_at "
            "ON Documents(created_at DESC)"
        )

        # ── Analyses ── (FK ON DELETE CASCADE para limpar quando Document é apagado)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Analyses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id     INTEGER NOT NULL,
                summary_json    TEXT,
                quiz_json       TEXT,
                debate_log_json TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES Documents(id) ON DELETE CASCADE
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_document_id "
            "ON Analyses(document_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_created_at "
            "ON Analyses(document_id, created_at DESC)"
        )

        # ── Schema evolution: garante que todas as colunas esperadas existem ──
        _ensure_columns(conn, "Documents", _DOCUMENTS_SCHEMA)
        _ensure_columns(conn, "Analyses",  _ANALYSES_SCHEMA)

    return conn


def _build_create_table_ddl(table_name: str, schema: List[Tuple[str, str]]) -> str:
    """Constrói CREATE TABLE IF NOT EXISTS a partir da lista (nome, definição)."""
    cols_ddl = ",\n    ".join(f"{name} {definition}" for name, definition in schema)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {cols_ddl}\n)"


def _ensure_columns(
    conn: sqlite3.Connection,
    table_name: str,
    expected_schema: List[Tuple[str, str]],
) -> List[str]:
    """
    Para cada coluna do esquema esperado, verifica se existe; se não, adiciona-a
    via ALTER TABLE ADD COLUMN (sem UNIQUE/PRIMARY KEY — SQLite não permite
    estes constraints em ALTER).

    Devolve a lista de colunas adicionadas (para log se necessário).

    SAFE: chamável em todo o arranque, é no-op se schema está em dia.
    """
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}  # row[1] = name

    added: List[str] = []
    for col_name, col_definition in expected_schema:
        if col_name in existing:
            continue
        # Strip de UNIQUE/PRIMARY KEY/AUTOINCREMENT — não permitido em ALTER
        clean_def = (
            col_definition
            .replace("UNIQUE", "")
            .replace("PRIMARY KEY", "")
            .replace("AUTOINCREMENT", "")
            .strip()
        )
        try:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {clean_def}")
            added.append(col_name)
        except sqlite3.OperationalError:
            # já existe ou DDL inválido — ignora (idempotência)
            pass
    return added


# ═══════════════════════════════════════════════════════════════════════════
# HASH — chave de deduplicação
# ═══════════════════════════════════════════════════════════════════════════

def compute_file_hash(file_bytes: bytes) -> str:
    """
    SHA-256 do conteúdo binário. Determinista e colisão-seguro para o nosso
    caso de uso (deduplicação de PDFs/docs uploadados pelo utilizador).

    Não usar MD5 (colisões fáceis) nem hash dos metadados (file_name pode
    mudar mas conteúdo é o mesmo → queremos dedup).
    """
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise TypeError("file_bytes deve ser bytes")
    return hashlib.sha256(file_bytes).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# CRUD — Documents
# ═══════════════════════════════════════════════════════════════════════════

def insert_document(
    conn: sqlite3.Connection,
    *,
    file_name: str,
    file_hash: str,
    file_type: str,
    raw_text: Optional[str] = None,
    ocr_text: Optional[str] = None,
    language: Optional[str] = None,
) -> int:
    """
    Insere um Document. Devolve o `id` gerado.

    Se o hash já existir (índice UNIQUE), levanta `sqlite3.IntegrityError`.
    Para ter "upsert idempotente", usar `get_or_insert_document()`.
    """
    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO Documents (file_name, file_hash, file_type, raw_text, ocr_text, language)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_name, file_hash, file_type, raw_text, ocr_text, language),
        )
        return cursor.lastrowid


def get_document_by_hash(
    conn: sqlite3.Connection,
    file_hash: str,
) -> Optional[Dict[str, Any]]:
    """Procura Document pelo hash. Devolve dict ou None."""
    cursor = conn.execute(
        "SELECT * FROM Documents WHERE file_hash = ?",
        (file_hash,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def get_document_by_id(
    conn: sqlite3.Connection,
    document_id: int,
) -> Optional[Dict[str, Any]]:
    cursor = conn.execute("SELECT * FROM Documents WHERE id = ?", (document_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_or_insert_document(
    conn: sqlite3.Connection,
    *,
    file_name: str,
    file_hash: str,
    file_type: str,
    raw_text: Optional[str] = None,
    ocr_text: Optional[str] = None,
    language: Optional[str] = None,
) -> Tuple[int, bool]:
    """
    Upsert idempotente.

    Devolve `(document_id, is_new)`:
      • is_new=True   → Document foi criado agora
      • is_new=False  → já existia (dedup por hash); devolve o id antigo
    """
    existing = get_document_by_hash(conn, file_hash)
    if existing is not None:
        return int(existing["id"]), False
    new_id = insert_document(
        conn,
        file_name=file_name,
        file_hash=file_hash,
        file_type=file_type,
        raw_text=raw_text,
        ocr_text=ocr_text,
        language=language,
    )
    return new_id, True


def list_all_documents(
    conn: sqlite3.Connection,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Lista todos os documentos por data de criação (descendente)."""
    sql = "SELECT id, file_name, file_hash, file_type, created_at, language FROM Documents ORDER BY created_at DESC"
    if limit:
        sql += " LIMIT ?"
        cursor = conn.execute(sql, (limit,))
    else:
        cursor = conn.execute(sql)
    return [dict(row) for row in cursor.fetchall()]


def delete_document(conn: sqlite3.Connection, document_id: int) -> bool:
    """
    Apaga um Document e (por FK CASCADE) todas as suas Analyses.
    Devolve True se algo foi apagado, False se o id não existia.
    """
    with transaction(conn):
        cursor = conn.execute("DELETE FROM Documents WHERE id = ?", (document_id,))
        return cursor.rowcount > 0


def delete_all_documents(conn: sqlite3.Connection) -> int:
    """Apaga tudo. Devolve nº de Documents apagados (Analyses caem por cascade)."""
    with transaction(conn):
        cursor = conn.execute("DELETE FROM Documents")
        return cursor.rowcount


# ═══════════════════════════════════════════════════════════════════════════
# CRUD — Analyses
# ═══════════════════════════════════════════════════════════════════════════

def insert_analysis(
    conn: sqlite3.Connection,
    *,
    document_id: int,
    summary_json: Optional[Any] = None,
    quiz_json: Optional[Any] = None,
    debate_log_json: Optional[Any] = None,
) -> int:
    """
    Insere uma Analysis para um Document.

    Os parâmetros *_json aceitam dict/list (serializa para JSON automaticamente)
    OU str (assumida como já serializada).
    """
    with transaction(conn):
        cursor = conn.execute(
            """
            INSERT INTO Analyses (document_id, summary_json, quiz_json, debate_log_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                document_id,
                _to_json_str(summary_json),
                _to_json_str(quiz_json),
                _to_json_str(debate_log_json),
            ),
        )
        return cursor.lastrowid


def get_latest_analysis(
    conn: sqlite3.Connection,
    document_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Devolve a Analysis mais recente para um Document, com os campos JSON
    já desserializados. None se não houver nenhuma.
    """
    cursor = conn.execute(
        """
        SELECT * FROM Analyses
        WHERE document_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (document_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    out = dict(row)
    out["summary_json"]    = _from_json_str(out.get("summary_json"))
    out["quiz_json"]       = _from_json_str(out.get("quiz_json"))
    out["debate_log_json"] = _from_json_str(out.get("debate_log_json"))
    return out


def list_analyses(
    conn: sqlite3.Connection,
    document_id: int,
) -> List[Dict[str, Any]]:
    """Lista todas as Analyses de um Document, mais recente primeiro."""
    cursor = conn.execute(
        """
        SELECT * FROM Analyses
        WHERE document_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (document_id,),
    )
    out = []
    for row in cursor.fetchall():
        d = dict(row)
        d["summary_json"]    = _from_json_str(d.get("summary_json"))
        d["quiz_json"]       = _from_json_str(d.get("quiz_json"))
        d["debate_log_json"] = _from_json_str(d.get("debate_log_json"))
        out.append(d)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Helpers JSON
# ═══════════════════════════════════════════════════════════════════════════

def _to_json_str(value: Any) -> Optional[str]:
    """Serializa dict/list/None para str JSON. Se já for str, devolve tal qual."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        # Último recurso: representação string segura
        return json.dumps({"_unserializable": str(value)})


def _from_json_str(value: Optional[str]) -> Any:
    """Desserializa str JSON em dict/list. None ou inválido → devolve tal qual."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


# ═══════════════════════════════════════════════════════════════════════════
# Diagnóstico (útil para debug/UI)
# ═══════════════════════════════════════════════════════════════════════════

def db_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    """Devolve contadores básicos para mostrar na UI."""
    n_docs = conn.execute("SELECT COUNT(*) FROM Documents").fetchone()[0]
    n_analyses = conn.execute("SELECT COUNT(*) FROM Analyses").fetchone()[0]
    return {"documents": n_docs, "analyses": n_analyses}
