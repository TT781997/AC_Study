"""
agents.py — Motor de Debate Multi-Agente "Veredict-First" (v5.1)
=================================================================

Núcleo lógico do Universal ScholarGPT. Orquestrador explícito
`run_consensus_loop()` que implementa um autómato finito sobre
(autor_atual, versão, ronda).

Diferenças face à v5.0:
  • Função canónica renomeada para `run_consensus_loop` (spec v5.1).
    `run_eval_consensus` mantido como alias de retrocompatibilidade.
  • `DebateLogEntry` enriquecida com `decision`, `version`, `brief_reason`
    para alimentar o "Log Visual do Debate" persistente em tempo real.
  • Append-only `debate_log: List[DebateLogEntry]` exposto via callback
    `on_log_update(entry)` para a UI redesenhar.
  • Banner explícito "⏱️ Consenso parcial atingido após N rodadas"
    quando se atinge `max_rounds` sem unanimidade.
  • Mantém: 4 personas, Veredict-First, Regra de Ouro, prompt do Chefe
    com `=== RESPOSTAS ===` obrigatório, prompt do Chefe-como-validador.

Sem dependência de Streamlit no caminho lógico (apenas via container
passado para o stream_fn). Pode ser testado isoladamente com mocks.

Dependências:
  • config — constantes, marcadores, AGENTS_ORDER
  • i18n   — t, agent_display, language_instruction
  • stream_fn injectada (assinada como llm_client.stream_call_threaded)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import streamlit as st

from config import (
    AGENTS_ORDER, AGENT_ICONS, DEFAULT_MODELS,
    APPROVAL_MARKER, REWRITE_MARKER, REWRITE_BLOCK_MARKER,
    LEGACY_APPROVAL_TOKEN, ANSWERS_SEPARATOR,
)
from i18n import t, agent_display, language_instruction, random_fun_message


# ════════════════════════════════════════════════════════════════════════════
# PROMPT — Chefe Redator (impõe separador `=== RESPOSTAS ===` + LaTeX rules)
# ════════════════════════════════════════════════════════════════════════════

EVAL_INITIAL_SYSTEM = f"""És o **Chefe Redator** — Professor Universitário Sénior, estruturado, claro e académico.

Crias quizzes/testes universitários de revisão sobre QUALQUER disciplina académica.

═══════════════════════════════════════════════════════════════
⚠️ ESTRUTURA OBRIGATÓRIA — TRÊS BLOCOS, SEPARADOS POR `{ANSWERS_SEPARATOR}`
═══════════════════════════════════════════════════════════════

【 BLOCO 1 — ENUNCIADOS Parte I 】

## Parte I — Escolha Múltipla (10 questões)

Cada questão APENAS com:
- Enunciado claro, sem ambiguidades.
- 4 opções: a), b), c), d).

❌ NÃO incluas a resposta correta NESTE bloco.
❌ NÃO incluas justificação NESTE bloco.

【 BLOCO 2 — ENUNCIADOS Parte II 】

## Parte II — Exercícios Práticos (2 exercícios)

Cada exercício APENAS com:
- Enunciado realista (dados quantitativos coerentes quando aplicável).
- 3-5 alíneas de complexidade crescente.

❌ NÃO incluas resolução NESTE bloco.
❌ NÃO incluas resultado final NESTE bloco.

═══════════════════════════════════════════════════════════════
⚠️ SEPARADOR OBRIGATÓRIO (linha sozinha, exactamente como escrito):

{ANSWERS_SEPARATOR}

═══════════════════════════════════════════════════════════════

【 BLOCO 3 — SOLUÇÕES (escondidas até clique do aluno) 】

## Soluções Parte I
- **Q1:** Resposta: **x)** — Justificação (1-2 frases) com referência à matéria.
- **Q2:** Resposta: **x)** — ...
... (uma por cada uma das 10 questões)

## Soluções Parte II
- **Exercício 1:** resolução passo-a-passo, cálculos visíveis. Resultado final em **negrito**.
- **Exercício 2:** ...

═══════════════════════════════════════════════════════════════
⚠️ REGRAS LATEX (críticas para o rendering Streamlit/MathJax):
═══════════════════════════════════════════════════════════════

✅ Inline:    `$x = y$`
✅ Display:   `$$E = mc^2$$`
✅ Frações:   `$\\frac{{a}}{{b}}$`
✅ Unidades em texto fora do LaTeX: `$P = 100$ W`  (não `$P = 100\\,\\mathrm{{W}}$`)
✅ Símbolos gregos: `$\\alpha, \\beta, \\Sigma$`

❌ NUNCA uses `\\(` `\\)` nem `\\[` `\\]` — só `$...$` e `$$...$$`.
❌ NUNCA misturar Markdown bold com LaTeX no mesmo token (`**$x$**` quebra render).

═══════════════════════════════════════════════════════════════
⚠️ INFRACÇÃO CRÍTICA — separador obrigatório
═══════════════════════════════════════════════════════════════

O separador `{ANSWERS_SEPARATOR}` DEVE aparecer:
  • EXATAMENTE assim, sem aspas, sem traços extra.
  • Numa linha sozinha (parágrafo próprio).
  • UMA VEZ APENAS (entre enunciados e soluções).

Sem este separador, a interface mostra todas as soluções imediatamente
e perde-se o efeito de quiz interactivo. Os outros agentes vão validar
a presença e correção deste separador.

═══════════════════════════════════════════════════════════════

REGRAS GERAIS:
- COBERTURA TRANSVERSAL: as 10 perguntas distribuem-se por TÓPICOS DIFERENTES.
- Valores realistas; cálculos que fechem.
- Markdown limpo, sem preâmbulos, sem despedidas, sem meta-comentários.
- CONCISO mas COMPLETO.
"""


# ════════════════════════════════════════════════════════════════════════════
# PROMPTS — Validadores (4: Chefe-as-validator + 3 especializados)
# ════════════════════════════════════════════════════════════════════════════

_VALIDATOR_RESPONSE_FORMAT = f"""
⚠️ FORMATO DE RESPOSTA — MARCADORES UNIVERSAIS (em INGLÊS, invariáveis):

LINHA 1: `{{approve_marker}}` OU `{{rewrite_marker}}`

→ Se aprovas:
   Linha 2 (opcional, recomendado): 1 frase breve com o que ficou bem
   (será mostrada no Log Visual do Debate como "Motivo").
   PARA. Poupar tokens é prioritário.

→ Se reescreves:
   Linhas seguintes: 1 bullet curto por cada erro encontrado.
   (As primeiras 1-2 linhas serão mostradas como "Motivo" no Log.)
   Depois: linha `{{block_marker}}`
   Em seguida: quiz COMPLETO corrigido, OBRIGATORIAMENTE com:
     • Parte I (10 questões) + Parte II (2 exercícios) — só enunciados
     • Linha sozinha com o separador EXATO `{ANSWERS_SEPARATOR}`
     • Soluções Parte I + Soluções Parte II
   ⚠️ Se omitires `{ANSWERS_SEPARATOR}` na reescrita, partes a UI. NÃO o omitas.
"""

EVAL_VALIDATION_SYSTEMS: Dict[str, str] = {
    "Chefe": f"""És o **Chefe Redator** e, NESTA ronda, és VALIDADOR (porque um dos outros agentes
reescreveu na ronda anterior, tornando-se o novo autor). Avalias o quiz com visão holística.

⚠️ REGRA DE OURO: avalias o quiz produzido por **{{author}}**. NUNCA reescreves a tua própria autoria.

VERIFICA (visão holística — és o autor original, conheces o standard):
1. Estrutura: Parte I (10 questões), Parte II (2 exercícios), Soluções no fim.
2. Cobertura transversal da matéria fornecida.
3. Rigor técnico-científico geral.
4. Clareza e didáctica.
5. Presença e correção do separador `{ANSWERS_SEPARATOR}` (linha sozinha entre enunciados e soluções).
6. LaTeX: `$...$` inline, `$$...$$` display, sem `\\(` `\\[`.
{_VALIDATOR_RESPONSE_FORMAT}
⚠️ POLÍTICA DE TOLERÂNCIA: és exigente mas justo. Aprova se a versão actual é
GLOBALMENTE boa, mesmo que tu pessoalmente terias escrito de forma ligeiramente diferente.
Reescreve só se há um erro estrutural ou se o separador `{ANSWERS_SEPARATOR}` está ausente.
""",

    "Verificador Técnico": f"""És o **Verificador Técnico** — preciso, céptico e rigoroso.

⚠️ REGRA DE OURO: avalias o quiz produzido por **{{author}}**. NUNCA reescreves a tua própria autoria.

VERIFICA (foco técnico):
1. Cálculos exatos (refaz mentalmente cada um).
2. Fórmulas corretas com unidades consistentes.
3. Cada questão de escolha múltipla com UMA E SÓ UMA resposta correta.
4. Factos verdadeiros.
5. Notação LaTeX correta: `$...$` inline, `$$...$$` display, sem `\\(` `\\[`.
6. Presença do separador `{ANSWERS_SEPARATOR}` (linha sozinha entre enunciados e soluções).
{_VALIDATOR_RESPONSE_FORMAT}
⚠️ POLÍTICA DE TOLERÂNCIA: aprova se não há erros TÉCNICOS REAIS. Preferências estilísticas,
variantes de notação ou frases que poderiam ser mais elegantes NÃO justificam reescrita.
Reescreve APENAS se há um erro que estraga o quiz, ou se o separador está ausente/incorreto.
""",

    "Verificador Pedagógico": f"""És o **Verificador Pedagógico** — focado em clareza e aprendizagem.

⚠️ REGRA DE OURO: avalias o quiz produzido por **{{author}}**. NUNCA reescreves a tua própria autoria.

VERIFICA (foco pedagógico):
1. Enunciados claros e SEM ambiguidades.
2. Estrutura pedagógica sólida (do simples ao complexo).
3. Cobertura transversal da matéria (10 perguntas em tópicos distintos, não 5 sobre o mesmo).
4. Markdown limpo, sem ruído visual, com headers `## Parte I` e `## Parte II`.
5. Separador `{ANSWERS_SEPARATOR}` exatamente como definido.
6. Soluções no fim, NUNCA misturadas com enunciados.
{_VALIDATOR_RESPONSE_FORMAT}
⚠️ POLÍTICA DE TOLERÂNCIA: reescreve só se há ambiguidades REAIS, má estrutura,
ou separador `{ANSWERS_SEPARATOR}` ausente/mal posicionado. Variações de estilo NÃO justificam.
""",

    "Aluno Crítico": f"""És o **Aluno Crítico** — representas o aluno universitário que VAI USAR este quiz para estudar.

⚠️ REGRA DE OURO: avalias o quiz produzido por **{{author}}**. NUNCA reescreves a tua própria autoria.

PERGUNTA-TE (perspectiva do utilizador final):
1. Conseguiria responder com APENAS a matéria fornecida? Há armadilhas injustas?
2. O nível de dificuldade é adequado a exame universitário (nem trivial, nem impossível)?
3. Algum exercício está FORA do âmbito do material fornecido?
4. As perguntas refletem o que tipicamente é avaliado em exame?
5. Como aluno, vou conseguir distinguir enunciados das soluções? (Verifica `{ANSWERS_SEPARATOR}`.)
{_VALIDATOR_RESPONSE_FORMAT}
⚠️ POLÍTICA DE TOLERÂNCIA: reescreve só se há perguntas REALMENTE injustas, fora-de-âmbito,
ou se o separador `{ANSWERS_SEPARATOR}` está em falta. Dificuldade variada é OK.
""",
}


# ════════════════════════════════════════════════════════════════════════════
# HELPERS DE PARSING — Veredict-First + reescrita + separador
# ════════════════════════════════════════════════════════════════════════════

def is_approval(response: str) -> bool:
    """1ª linha começa com APPROVE? Fallback p/ legacy `[UNANIMIDADE]`."""
    if not response:
        return False
    first_line = response.strip().split("\n", 1)[0].strip().upper()
    if first_line.startswith(APPROVAL_MARKER.upper()):
        return True
    if first_line.startswith(REWRITE_MARKER.upper()):
        return False
    return LEGACY_APPROVAL_TOKEN.upper() in response.strip()[:300].upper()


def extract_rewrite(response: str) -> str:
    """Extrai o quiz reescrito após `--- REWRITTEN TEST ---` (ou variantes PT/EN)."""
    if REWRITE_BLOCK_MARKER in response:
        return response.split(REWRITE_BLOCK_MARKER, 1)[1].strip()
    for variant in ["--- TESTE REESCRITO ---", "--- TEST REWRITTEN ---",
                    "--- NEW TEST ---", "--- QUIZ REESCRITO ---"]:
        if variant in response:
            return response.split(variant, 1)[1].strip()
    return response.strip().split("\n", 1)[-1].strip() if "\n" in response else response.strip()


def extract_brief_reason(response: str, decision: str) -> str:
    """
    Extrai 1-2 frases curtas da resposta do validador, para mostrar no Log Visual.

    • Para APPROVE: linha 2 (se existir) ou frase de 'aprovado'.
    • Para REWRITE: primeiras 2 linhas de bullets antes do block marker.
    """
    if not response:
        return ""
    lines = [l for l in response.strip().split("\n") if l.strip()]
    if not lines:
        return ""
    # Skip line 1 (DECISION: ...) and pick next 1-2 meaningful lines
    body_lines = lines[1:]
    if decision == "APPROVE":
        if body_lines:
            return body_lines[0].strip()[:160]
        return "Aprovado sem comentários adicionais."
    # REWRITE: bullets antes do block marker
    reasons = []
    for line in body_lines:
        if REWRITE_BLOCK_MARKER in line or any(v in line for v in [
            "--- TESTE REESCRITO ---", "--- TEST REWRITTEN ---",
        ]):
            break
        cleaned = line.lstrip("-•* ").strip()
        if cleaned:
            reasons.append(cleaned)
        if len(reasons) >= 2:
            break
    return " · ".join(reasons)[:200] if reasons else "Sem motivo explícito."


def split_quiz_and_answers(quiz_text: str) -> Tuple[str, Optional[str]]:
    """
    ⭐ Núcleo da feature "Ver Respostas".

    Divide `(questions, answers)` pelo separador `=== RESPOSTAS ===`.
    Devolve `(text, None)` se o separador estiver ausente (UI mostra aviso).
    """
    if not quiz_text:
        return "", None
    if ANSWERS_SEPARATOR in quiz_text:
        questions, answers = quiz_text.split(ANSWERS_SEPARATOR, 1)
        return questions.strip(), answers.strip()
    return quiz_text.strip(), None


def has_answers_separator(quiz_text: str) -> bool:
    """Helper booleano para a UI decidir entre mostrar st.expander ou aviso."""
    return ANSWERS_SEPARATOR in (quiz_text or "")


# ════════════════════════════════════════════════════════════════════════════
# DATA CLASSES — DebateLogEntry enriquecida + DebateResult
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class DebateLogEntry:
    """
    Entrada estruturada do Log Visual do Debate.

    Contém o que a UI precisa para mostrar uma linha persistente em tempo real:
      • round_num         — número da ronda (0 = draft inicial; 1+ = validação)
      • author            — quem produziu este conteúdo (autor do draft/rewrite)
      • validator         — None para drafts; nome do validador caso contrário
      • decision          — None (draft) | "APPROVE" | "REWRITE"
      • version           — número da versão (V1, V2, …)
      • brief_reason      — 1-2 frases extraídas da resposta (motivo)
      • content           — resposta crua completa (debug/expander)
      • kind              — "draft" | "approval" | "rewrite"
    """
    round_num: int
    author: str
    validator: Optional[str]
    decision: Optional[str]
    version: int
    brief_reason: str
    content: str
    kind: str


@dataclass
class DebateResult:
    """Resultado final do consenso multi-agente."""
    final_content: str                 # quiz final (com `=== RESPOSTAS ===`)
    final_author: str                  # autor da versão final
    final_version: int                 # número da versão final
    rounds_used: int                   # rondas efectivamente executadas
    consensus_reached: bool            # True só se 3 APPROVE na mesma ronda
    debate_log: List[DebateLogEntry] = field(default_factory=list)

    # Backward-compat com v5.0: `history` e `iterations_used`
    @property
    def history(self) -> List[DebateLogEntry]:
        return self.debate_log

    @property
    def iterations_used(self) -> int:
        return self.rounds_used


# ════════════════════════════════════════════════════════════════════════════
# HELPERS — Resolução de modelo do session_state
# ════════════════════════════════════════════════════════════════════════════

def get_model_for_agent(agent_name: str) -> str:
    """Lê do session_state['agent_models'] com fallback para DEFAULT_MODELS."""
    if hasattr(st, "session_state"):
        models = st.session_state.get("agent_models", DEFAULT_MODELS)
    else:
        models = DEFAULT_MODELS
    return models.get(agent_name, DEFAULT_MODELS[agent_name])


# ════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR CENTRAL — `run_consensus_loop`
# ════════════════════════════════════════════════════════════════════════════

def run_consensus_loop(
    client,
    full_material: str,
    *,
    max_rounds: int,
    ui_container,
    lang_code: str,
    stream_fn: Callable,
    model_resolver: Optional[Callable[[str], str]] = None,
    on_log_update: Optional[Callable[[DebateLogEntry], None]] = None,
) -> DebateResult:
    """
    Autómato finito sobre `(current_author, version, round)` que implementa
    consenso unânime ESTRITO (3 APPROVE na mesma ronda) entre 4 agentes.

    Parâmetros:
      client:          OpenAI/NVIDIA NIM client
      full_material:   resumos + raw_text dos PDFs (string única)
      max_rounds:      limite de rondas; se atingido sem unanimidade
                       → consensus_reached=False + banner
                       "⏱️ Consenso parcial atingido após N rodadas"
      ui_container:    Streamlit container/expander onde mostrar progresso
      lang_code:       idioma da UI
      stream_fn:       função injectada (llm_client.stream_call_threaded)
      model_resolver:  callable(agent_name) -> model_id (default: get_model_for_agent)
      on_log_update:   callback(entry: DebateLogEntry) chamado a CADA nova
                       entrada do log — permite à UI redesenhar o Log
                       Visual em tempo real, append-only.

    Devolve:
      DebateResult com final_content, final_author, final_version,
      rounds_used, consensus_reached e debate_log completo.

    Garantias formais:
      1. Consenso unânime ↔ 3 APPROVE em sequência NA MESMA ronda.
      2. Quem reescreve passa a ser o autor; ninguém se auto-avalia.
      3. `debate_log` é append-only e estruturado (não é só `content` cru).
    """
    if model_resolver is None:
        model_resolver = get_model_for_agent

    debate_log: List[DebateLogEntry] = []
    lang_block = language_instruction(lang_code)

    def _append_log(entry: DebateLogEntry) -> None:
        debate_log.append(entry)
        if on_log_update is not None:
            try:
                on_log_update(entry)
            except Exception:
                pass

    # ─── FASE 0 — Chefe redige V1 ──────────────────────────────────────────
    with ui_container.status(
        t("chefe_drafting") + " — " + random_fun_message(lang_code), expanded=True,
    ) as s:
        chefe_model = model_resolver("Chefe")
        s.write(f"`{chefe_model}`")
        system_prompt = EVAL_INITIAL_SYSTEM + "\n\n" + lang_block
        user_prompt = (
            "MATERIAL DE ESTUDO COMPLETO:\n\n"
            f"{full_material}\n\n---\n\n"
            "Produz agora o Quiz completo. Lembra-te: separador "
            f"`{ANSWERS_SEPARATOR}` é OBRIGATÓRIO entre enunciados e soluções."
        )
        initial_draft = stream_fn(
            client, chefe_model, system_prompt, user_prompt, s,
            temperature=0.35, max_tokens=5500, lang_code=lang_code,
        )
        s.update(label="✅ Chefe → V1", state="complete", expanded=False)

    _append_log(DebateLogEntry(
        round_num=0, author="Chefe", validator=None,
        decision=None, version=1,
        brief_reason="Draft inicial gerado.",
        content=initial_draft, kind="draft",
    ))

    current_author = "Chefe"
    current_content = initial_draft
    current_version = 1

    # ─── FASES 1..N — Validação e potencial reescrita ──────────────────────
    rounds_executed = 0
    for round_num in range(1, max_rounds + 1):
        rounds_executed = round_num
        ui_container.markdown(
            "<div class='round-tag'>"
            + t("round_of", i=round_num, n=max_rounds,
                v=current_version, a=agent_display(current_author))
            + "</div>",
            unsafe_allow_html=True,
        )

        # Regra de Ouro: validadores = todos EXCEPTO o autor actual
        validators_this_round = [a for a in AGENTS_ORDER if a != current_author]
        approvals_this_round: List[str] = []
        rewrite_happened = False

        for validator_name in validators_this_round:
            label = (
                t("validator_evaluating",
                  icon=AGENT_ICONS[validator_name], v=agent_display(validator_name),
                  n=current_version, a=agent_display(current_author))
                + " — " + random_fun_message(lang_code)
            )
            with ui_container.status(label, expanded=True) as s:
                v_model = model_resolver(validator_name)
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
                    f"QUIZ A AVALIAR (autoria: {agent_display(current_author)}, "
                    f"V{current_version}):\n\n{current_content}\n\n---\n\n"
                    f"DECIDE: começa por `{APPROVAL_MARKER}` ou `{REWRITE_MARKER}`."
                )

                response = stream_fn(
                    client, v_model, system_prompt, user_prompt, s,
                    temperature=0.1, max_tokens=5500, lang_code=lang_code,
                )

                if is_approval(response):
                    approvals_this_round.append(validator_name)
                    reason = extract_brief_reason(response, "APPROVE")
                    _append_log(DebateLogEntry(
                        round_num=round_num, author=current_author,
                        validator=validator_name, decision="APPROVE",
                        version=current_version, brief_reason=reason,
                        content=response, kind="approval",
                    ))
                    s.update(label=t("approved", v=agent_display(validator_name)),
                             state="complete", expanded=False)
                else:
                    rewritten = extract_rewrite(response)
                    reason = extract_brief_reason(response, "REWRITE")
                    current_version += 1
                    _append_log(DebateLogEntry(
                        round_num=round_num, author=current_author,
                        validator=validator_name, decision="REWRITE",
                        version=current_version, brief_reason=reason,
                        content=response, kind="rewrite",
                    ))
                    s.update(label=t("rewrote", v=agent_display(validator_name),
                                     n=current_version),
                             state="complete", expanded=False)
                    # Quem reescreveu passa a ser o autor — ronda termina aqui
                    current_author = validator_name
                    current_content = rewritten
                    rewrite_happened = True
                    break

        # ── CONSENSO UNÂNIME ESTRITO: 3 APPROVE NA MESMA RONDA ────────────
        if not rewrite_happened and len(approvals_this_round) == len(validators_this_round):
            others = ", ".join(agent_display(v) for v in validators_this_round)
            ui_container.markdown(
                "<div class='consensus-banner'>"
                + t("consensus_msg", i=round_num, v=current_version,
                    a=agent_display(current_author), others=others)
                + "</div>",
                unsafe_allow_html=True,
            )
            return DebateResult(
                final_content=current_content,
                final_author=current_author,
                final_version=current_version,
                rounds_used=round_num,
                consensus_reached=True,
                debate_log=debate_log,
            )

    # ─── Atingiu max_rounds sem unanimidade ────────────────────────────────
    ui_container.markdown(
        "<div class='no-consensus-banner'>"
        + t("consensus_partial", n=max_rounds, v=current_version,
            a=agent_display(current_author))
        + "</div>",
        unsafe_allow_html=True,
    )
    return DebateResult(
        final_content=current_content,
        final_author=current_author,
        final_version=current_version,
        rounds_used=rounds_executed,
        consensus_reached=False,
        debate_log=debate_log,
    )


# ─── Alias de retrocompatibilidade com v5.0 ────────────────────────────────
def run_eval_consensus(
    client,
    full_material: str,
    *,
    max_iterations: int,
    ui_container,
    lang_code: str,
    stream_fn: Callable,
    model_resolver: Optional[Callable[[str], str]] = None,
) -> DebateResult:
    """
    Alias deprecated → encaminha para `run_consensus_loop`.
    `max_iterations` mapeia para `max_rounds`. Mantido para que o
    `app.py` v5.0 continue a funcionar sem alterações.
    """
    return run_consensus_loop(
        client, full_material,
        max_rounds=max_iterations,
        ui_container=ui_container,
        lang_code=lang_code,
        stream_fn=stream_fn,
        model_resolver=model_resolver,
    )
