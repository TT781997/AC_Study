"""
llm_client.py — Comunicação com NVIDIA NIM (v5.2)
==================================================

Novidades face à v5.1:
  ⭐ call_with_retry()  — exponential backoff para 429/timeout
  ⭐ call_vision_llm()  — chamada multimodal (imagem base64) p/ OCR
  ⭐ stream_call_threaded internamente embrulha em retry
"""

from __future__ import annotations

import base64
import threading
import time
from queue import Queue, Empty
from typing import Callable, Optional

import streamlit as st

try:
    from openai import OpenAI, OpenAIError
except ImportError:
    OpenAI = None
    OpenAIError = Exception

from config import (
    NVIDIA_BASE_URL, MODEL_REGISTRY, DEFAULT_SPEED_ESTIMATE_4K,
    VISION_MODEL_DEFAULT, VISION_MAX_TOKENS, VISION_TEMPERATURE,
    MAX_RETRY_ATTEMPTS, RETRY_BASE_DELAY, RETRY_MAX_DELAY, RETRY_ON_PATTERNS,
)


def get_nvidia_client(api_key: str):
    """Cria cliente OpenAI apontado à NVIDIA NIM. None se key vazia/inválida."""
    if not api_key or not api_key.strip():
        return None
    if OpenAI is None:
        return None
    try:
        return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key.strip())
    except Exception:
        return None


def estimate_eta(model: str, max_tokens: int) -> int:
    meta = MODEL_REGISTRY.get(model, {})
    base = meta.get("est_seconds_4k", DEFAULT_SPEED_ESTIMATE_4K)
    if not isinstance(base, (int, float)) or base <= 0:
        base = DEFAULT_SPEED_ESTIMATE_4K
    return max(5, int(base * (max_tokens / 4000.0)))


def friendly_api_error(e: Exception) -> str:
    msg = str(e).lower()
    if "404" in msg or "not found" in msg:
        return ("❌ **Modelo não encontrado (404).** Muda em **⚙️** para um modelo a que tenhas acesso.")
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
        return "❌ **API Key inválida (401).** Verifica na sidebar esquerda."
    if "429" in msg or "rate limit" in msg or "quota" in msg:
        return ("⏳ **Rate limit (429).** Aguarda alguns segundos. Considera modelo Flash em **⚙️**.")
    if "context" in msg and ("length" in msg or "limit" in msg or "exceed" in msg):
        return ("📏 **Contexto excedido.** Tenta Kimi K2.6 ou Nemotron 120B em **⚙️**.")
    if "timeout" in msg or "timed out" in msg:
        return "🌐 **Timeout.** Verifica a rede e tenta de novo."
    return f"❌ **Erro NVIDIA NIM:** {e}"


# ════════════════════════════════════════════════════════════════════════════
# ⭐ v5.2 — Exponential Backoff Retry
# ════════════════════════════════════════════════════════════════════════════

def _should_retry(exc: Exception) -> bool:
    """True se o erro corresponde a um padrão retryable (429, timeout, 5xx)."""
    msg = str(exc).lower()
    return any(pattern in msg for pattern in RETRY_ON_PATTERNS)


def _backoff_delay(attempt: int) -> float:
    """Delay para a tentativa N (0-indexed). 2s, 4s, 8s… cap a RETRY_MAX_DELAY."""
    delay = RETRY_BASE_DELAY * (2 ** attempt)
    return min(delay, RETRY_MAX_DELAY)


def call_with_retry(
    fn: Callable,
    *args,
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    **kwargs,
):
    """
    Executa `fn(*args, **kwargs)` com exponential backoff em erros retryable
    (429, timeout, 5xx). Erros não-retryable (404, 401) propagam imediatamente.

    Args:
        fn: callable a executar.
        on_retry(attempt, delay, exc): callback opcional antes de cada retry
            (usado pela UI para mostrar banner).

    Returns:
        O resultado de `fn(*args, **kwargs)`.

    Raises:
        A última exception se todas as tentativas falharem ou se a primeira
        exception não for retryable.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if not _should_retry(exc):
                raise   # erro definitivo (404, 401, etc.) — fail-fast
            if attempt >= MAX_RETRY_ATTEMPTS - 1:
                break   # esgotadas as tentativas
            delay = _backoff_delay(attempt)
            if on_retry:
                try: on_retry(attempt + 1, delay, exc)
                except Exception: pass
            time.sleep(delay)
    raise last_exc   # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
# ⭐ v5.2 — Vision LLM (imagem → texto via NVIDIA NIM multimodal)
# ════════════════════════════════════════════════════════════════════════════

DEFAULT_OCR_PROMPT = (
    "Extract ALL text visible in this image, preserving structure (headings, "
    "paragraphs, lists). If there are mathematical formulas, transcribe them "
    "in LaTeX notation ($...$ inline, $$...$$ display). Return ONLY the "
    "extracted text — no preambles or commentary."
)


def call_vision_llm(
    client,
    image_bytes: bytes,
    *,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    image_mime: str = "image/png",
) -> str:
    """
    Chama o modelo multimodal NVIDIA NIM com uma imagem inline (base64).

    Args:
        client: OpenAI client apontado para NVIDIA NIM.
        image_bytes: bytes brutos da imagem (PNG/JPG).
        prompt: instrução textual (default: OCR genérico).
        model: ID do modelo Vision (default: VISION_MODEL_DEFAULT do config).
        image_mime: mime-type da imagem.

    Returns:
        Texto extraído. "" se o modelo não respondeu.

    Raises:
        Exception (após retry) se falhar definitivamente.
    """
    if client is None:
        return ""

    if not image_bytes:
        return ""

    model_id = model or VISION_MODEL_DEFAULT
    user_prompt = prompt or DEFAULT_OCR_PROMPT
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{image_mime};base64,{b64}"

    def _do_call():
        response = client.chat.completions.create(
            model=model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            max_tokens=VISION_MAX_TOKENS,
            temperature=VISION_TEMPERATURE,
            stream=False,
        )
        if not response.choices:
            return ""
        msg = response.choices[0].message
        return (msg.content or "").strip()

    return call_with_retry(_do_call)


def make_vision_callback(client):
    """
    Factory: produz uma `vision_callback` (bytes → str) pronta a injectar
    no `ingest_file()`. Encapsula `call_vision_llm` com retry.

    Usage no app.py:
        vc = make_vision_callback(client)
        ingest_file(uploaded, vision_callback=vc)
    """
    if client is None:
        return None

    def _callback(image_bytes: bytes) -> str:
        try:
            return call_vision_llm(client, image_bytes)
        except Exception:
            return ""

    return _callback


# ════════════════════════════════════════════════════════════════════════════
# Streaming threaded (com retry embrulhado)
# ════════════════════════════════════════════════════════════════════════════

def stream_call_threaded(
    client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    container,
    *,
    temperature: float = 0.3,
    max_tokens: int = 4500,
    lang_code: str = "pt",
    on_chunk: Optional[Callable[[str, bool], None]] = None,
) -> str:
    """
    Streaming threaded com retry embrulhado: a chamada inicial à API
    (que pode falhar com 429/timeout) é envolvida em call_with_retry.
    Uma vez aberto o stream, é consumido normalmente.

    Worker thread NUNCA toca em st.*; comunicação via Queue + animator.
    """
    from ui_components import LoadingAnimator

    if client is None:
        try:
            container.error("❌ Cliente NVIDIA não configurado.")
        except Exception:
            st.error("❌ Cliente NVIDIA não configurado.")
        return ""

    animator = LoadingAnimator(
        container, lang_code=lang_code,
        eta_seconds=estimate_eta(model, max_tokens),
        model_label=MODEL_REGISTRY.get(model, {}).get("label", model),
    )

    chunks_queue: Queue = Queue()
    done_event = threading.Event()
    error_holder = {"err": None}

    def _open_stream():
        return client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

    def _worker():
        try:
            # ⭐ v5.2: abertura do stream com retry
            stream = call_with_retry(_open_stream)
            for raw_chunk in stream:
                if not getattr(raw_chunk, "choices", None):
                    continue
                delta = getattr(raw_chunk.choices[0], "delta", None)
                if delta is None:
                    continue
                content = getattr(delta, "content", None) or ""
                if content:
                    chunks_queue.put(content)
        except Exception as e:
            error_holder["err"] = e
        finally:
            done_event.set()

    worker_thread = threading.Thread(target=_worker, daemon=True)
    worker_thread.start()

    accumulated = ""
    while True:
        try:
            delta = chunks_queue.get(timeout=0.5)
            accumulated += delta
            animator.update(current_text=accumulated)
            if on_chunk:
                try: on_chunk(accumulated, False)
                except Exception: pass
        except Empty:
            animator.update(current_text=accumulated, force=True)
            if on_chunk:
                try: on_chunk(accumulated, True)
                except Exception: pass
            if done_event.is_set() and chunks_queue.empty():
                break

    animator.clear()

    if error_holder["err"] is not None:
        msg = friendly_api_error(error_holder["err"])
        try: container.error(msg)
        except Exception: st.error(msg)
        return ""

    return accumulated
