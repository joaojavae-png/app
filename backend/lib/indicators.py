"""Indicator Registry — the single source of KPI definitions AND calculations.

Dashboards, reports and exports must call `compute_values`; no screen computes its own KPI.
"""

from datetime import datetime, timedelta, timezone

from lib.authz import TenantRepo
from lib.funnel import LOST, ORDER, reached_set
from lib.periods import date_range_filter

_COMMON_UNAVAILABLE = {
    "numerator": None, "denominator": None, "filters": [], "inclusion": "—", "exclusion": "—",
    "frequency": "—", "attribution": "—", "available": False,
}

REGISTRY: list[dict] = [
    {
        "id": "KPI-CRM-001", "code": "leads_recebidos", "module": "CRM", "kind": "fluxo",
        "name": "Leads recebidos",
        "description": "Quantidade de contatos criados (data de entrada) no período selecionado.",
        "objective": "Medir o volume de novas pessoas que iniciaram contato com a clínica.",
        "formula": "COUNT(contatos WHERE entered_at ∈ [início, fim))",
        "numerator": "Contatos com data de entrada no período", "denominator": None, "unit": "contatos",
        "source": "Coleção contacts (campo entered_at), clínica do usuário autenticado.",
        "filters": ["período (fuso da clínica)"],
        "inclusion": "Todos os contatos da clínica, em qualquer etapa atual, inclusive Perdido.",
        "exclusion": "Contatos de outras clínicas. Nenhuma outra exclusão.",
        "frequency": "Calculado sob demanda a cada consulta.",
        "attribution": "Atribuído à data de entrada, não à data da última interação.",
        "limitations": "Na Fase 1 os contatos são cadastrados manualmente (sem canal conectado). Comparação com o período anterior de mesma duração quando o período é limitado. Se a clínica não tem nenhum contato, o resultado é 'sem dados' e não zero.",
        "available": True,
    },
    {
        "id": "KPI-CRM-002", "code": "snapshot_funil", "module": "CRM", "kind": "snapshot",
        "name": "Snapshot do funil",
        "description": "Quantidade ATUAL de contatos em cada etapa do CRM.",
        "objective": "Mostrar a situação presente do funil, sem interpretá-la como conversão.",
        "formula": "COUNT(contatos) GROUP BY etapa_atual",
        "numerator": None, "denominator": None, "unit": "contatos",
        "source": "Coleção contacts (campo stage), estado atual.",
        "filters": ["nenhum — sempre o estado atual"],
        "inclusion": "Todos os contatos da clínica, inclusive Perdido.",
        "exclusion": "Contatos de outras clínicas.",
        "frequency": "Calculado sob demanda a cada consulta.",
        "attribution": "Etapa atual de cada contato.",
        "limitations": "É um retrato do momento: não usa o filtro de período e NÃO deve ser usado para calcular taxas de conversão históricas (use KPI-CRM-003).",
        "available": True,
    },
    {
        "id": "KPI-CRM-003", "code": "conversao_coorte", "module": "CRM", "kind": "coorte",
        "name": "Conversão por coorte",
        "description": "Percentual dos contatos que entraram no período e alcançaram a etapa de destino (ou posterior) dentro da janela de conversão.",
        "objective": "Medir a capacidade do funil de converter novas entradas, com base no histórico de eventos.",
        "formula": "contatos da coorte que alcançaram a etapa-alvo em até N dias após a entrada ÷ contatos da coorte",
        "numerator": "Contatos da coorte com evento de entrada na etapa-alvo ou posterior em até N dias após entered_at",
        "denominator": "Contatos com entered_at no período (coorte)", "unit": "%",
        "source": "Coleções contacts (entered_at) e contact_events (tipos created e stage_change).",
        "filters": ["período de entrada", "etapa-alvo", "janela em dias (1–365)"],
        "inclusion": "Contatos da clínica com entrada no período. Conta como alcançado se houve evento para a etapa-alvo ou qualquer etapa linear posterior, mesmo que o contato tenha retrocedido depois.",
        "exclusion": "Eventos ocorridos após a janela. Movimentos para Perdido não contam como conversão.",
        "frequency": "Calculado sob demanda a cada consulta.",
        "attribution": "Atribuído à coorte de entrada do contato.",
        "limitations": "Contatos cuja janela ainda não terminou tornam o resultado parcial (informado nas notas). Na Fase 1 não há agenda: entradas em Agendou/Compareceu são registradas como exceção justificada, sem agendamento vinculado.",
        "available": True,
    },
    {
        "id": "KPI-CRM-004", "code": "contatos_sem_responsavel", "module": "CRM", "kind": "snapshot",
        "name": "Contatos sem responsável",
        "description": "Quantidade atual de contatos ativos sem usuário responsável atribuído.",
        "objective": "Evidenciar contatos sem dono, que tendem a não receber acompanhamento.",
        "formula": "COUNT(contatos WHERE owner_id IS NULL AND etapa ≠ perdido)",
        "numerator": "Contatos ativos sem responsável", "denominator": "Contatos ativos (etapa ≠ perdido)",
        "unit": "contatos",
        "source": "Coleção contacts (campos owner_id e stage), estado atual.",
        "filters": ["nenhum — sempre o estado atual"],
        "inclusion": "Contatos em qualquer etapa linear.",
        "exclusion": "Contatos em Perdido / Sem interesse.",
        "frequency": "Calculado sob demanda a cada consulta.",
        "attribution": "Estado atual do campo responsável.",
        "limitations": "Retrato do momento; não indica há quanto tempo o contato está sem responsável.",
        "available": True,
    },
    # ---- Indicators that depend on later phases: defined, but never computed in Phase 1 ----
    {**_COMMON_UNAVAILABLE, "id": "KPI-CON-001", "code": "tempo_primeira_resposta", "module": "Conversas", "kind": "fluxo",
     "name": "Tempo de primeira resposta", "description": "Horário da primeira resposta elegível menos o horário do primeiro contato recebido; conversas sem resposta são exibidas, não excluídas.",
     "objective": "Medir a agilidade do atendimento.", "formula": "primeira_resposta_at − primeiro_contato_at", "unit": "minutos",
     "source": "Mensagens de conversas (Fase 2/6).", "limitations": "Requer mensagens registradas.", "depends_on": "Fase 2: Conversas"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-AGE-001", "code": "agendamentos", "module": "Agenda", "kind": "fluxo",
     "name": "Agendamentos, comparecimentos e faltas", "description": "Volume de agendamentos por estado no período.",
     "objective": "Acompanhar a operação da agenda.", "formula": "COUNT(agendamentos) GROUP BY estado", "unit": "agendamentos",
     "source": "Agendamentos (Fase 2).", "limitations": "Requer o módulo Agenda.", "depends_on": "Fase 2: Agenda"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-AGE-002", "code": "taxa_confirmacao", "module": "Agenda", "kind": "fluxo",
     "name": "Taxa de confirmação", "description": "Agendamentos confirmados ÷ agendamentos elegíveis para confirmação.",
     "objective": "Reduzir faltas.", "formula": "confirmados ÷ elegíveis", "unit": "%",
     "source": "Agendamentos (Fase 2).", "limitations": "Requer o módulo Agenda.", "depends_on": "Fase 2: Agenda"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-AGE-003", "code": "taxa_comparecimento", "module": "Agenda", "kind": "fluxo",
     "name": "Taxa de comparecimento / no-show", "description": "Comparecimentos ÷ (comparecimentos + não comparecimentos); cancelamentos excluídos.",
     "objective": "Medir a efetividade da agenda.", "formula": "compareceu ÷ (compareceu + não compareceu)", "unit": "%",
     "source": "Agendamentos (Fase 2).", "limitations": "Requer o módulo Agenda.", "depends_on": "Fase 2: Agenda"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-AGE-004", "code": "ocupacao_agenda", "module": "Agenda", "kind": "fluxo",
     "name": "Ocupação da agenda", "description": "Duração reservada ÷ duração de disponibilidade cadastrada. Ocupação não é receita.",
     "objective": "Avaliar capacidade.", "formula": "minutos reservados ÷ minutos disponíveis", "unit": "%",
     "source": "Agenda e disponibilidade dos profissionais (Fase 2/3).", "limitations": "Não calculável sem disponibilidade cadastrada.", "depends_on": "Fase 3: Dashboard da agenda"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-FUP-001", "code": "conclusao_followup", "module": "Follow-up", "kind": "fluxo",
     "name": "Conclusão de follow-up", "description": "Tarefas concluídas ÷ tarefas vencidas no período; pendentes exibidas.",
     "objective": "Garantir retorno aos contatos.", "formula": "concluídas ÷ vencidas", "unit": "%",
     "source": "Tarefas de follow-up (Fase 3).", "limitations": "Requer o módulo Follow-up.", "depends_on": "Fase 3: Follow-up"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-FUP-002", "code": "conversao_reativacao", "module": "Reativação", "kind": "coorte",
     "name": "Conversão de reativação", "description": "Contatados elegíveis que alcançaram o resultado na janela ÷ conjunto elegível.",
     "objective": "Medir resultados de reativação.", "formula": "convertidos ÷ elegíveis", "unit": "%",
     "source": "Segmentos de reativação (Fase 3).", "limitations": "Requer o módulo Reativação.", "depends_on": "Fase 3: Reativação"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-PRO-001", "code": "desempenho_profissional", "module": "Profissionais", "kind": "fluxo",
     "name": "Desempenho profissional", "description": "Comparação de indicadores individuais por período, sem pontuação universal.",
     "objective": "Apoiar a gestão de equipe com critérios explícitos.", "formula": "Indicadores individuais (sem ranking automático)", "unit": "—",
     "source": "Agenda e profissionais (Fase 2/3).", "limitations": "Amostras pequenas são sinalizadas.", "depends_on": "Fase 3: Desempenho profissional"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-FIN-001", "code": "recebimentos", "module": "Financeiro", "kind": "fluxo",
     "name": "Recebimentos", "description": "Valores com recebimento registrado no período (visão de caixa).",
     "objective": "Acompanhar entradas efetivas.", "formula": "SUM(valor WHERE recebido_em ∈ período)", "unit": "R$",
     "source": "Lançamentos financeiros (Fase 4).", "limitations": "Diferente de receita lançada por competência.", "depends_on": "Fase 4: Financeiro"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-FIN-002", "code": "despesas_pagas", "module": "Despesas", "kind": "fluxo",
     "name": "Despesas pagas", "description": "Despesas efetivamente pagas no período.",
     "objective": "Acompanhar saídas efetivas.", "formula": "SUM(valor WHERE pago_em ∈ período)", "unit": "R$",
     "source": "Lançamentos financeiros (Fase 4).", "limitations": "Diferente de pendentes, vencidas e competência.", "depends_on": "Fase 4: Financeiro"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-FIN-003", "code": "resultado_caixa", "module": "Financeiro", "kind": "fluxo",
     "name": "Resultado de caixa", "description": "Entradas recebidas − saídas pagas. Não é lucro contábil.",
     "objective": "Visão de caixa do período.", "formula": "recebimentos − despesas pagas", "unit": "R$",
     "source": "Lançamentos financeiros (Fase 4).", "limitations": "Não substitui contabilidade.", "depends_on": "Fase 4: Financeiro"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-EST-001", "code": "valor_estoque", "module": "Estoque", "kind": "snapshot",
     "name": "Valor de estoque e itens abaixo do mínimo", "description": "Saldo calculado × custo unitário registrado; itens sem custo sinalizados.",
     "objective": "Controlar capital em estoque e reposição.", "formula": "Σ saldo × custo_unitário", "unit": "R$",
     "source": "Movimentações de estoque (Fase 5).", "limitations": "Requer custos registrados.", "depends_on": "Fase 5: Estoque"},
    {**_COMMON_UNAVAILABLE, "id": "KPI-IA-001", "code": "acoes_ia", "module": "Agente de IA", "kind": "fluxo",
     "name": "Uso e resultados das ações de IA", "description": "Ações executadas pelo agente, ferramenta, estado e resultado observado.",
     "objective": "Supervisionar o agente.", "formula": "COUNT(ações) GROUP BY ferramenta, estado", "unit": "ações",
     "source": "Logs do agente (Fase 7).", "limitations": "Nenhum agente está conectado na Fase 1.", "depends_on": "Fase 7: Inteligência"},
]

REGISTRY_BY_CODE = {d["code"]: d for d in REGISTRY}


async def compute_values(repo: TenantRepo, clinic: dict, start: datetime | None, end: datetime | None,
                         target_stage: str, window_days: int) -> list[dict]:
    total_contacts = await repo.count("contacts")
    stage_labels = {s["code"]: s for s in clinic["stages"]}
    values: list[dict] = []

    # KPI-CRM-001 — leads recebidos (fluxo)
    leads = {"id": "KPI-CRM-001", "unit": "contatos", "notes": [], "breakdown": []}
    if total_contacts == 0:
        leads.update(status="sem_dados", notes=["Nenhum contato registrado nesta clínica."])
    else:
        leads["value"] = await repo.count("contacts", date_range_filter("entered_at", start, end))
        leads["status"] = "ok"
        if start and end:
            prev_start = start - (end - start)
            leads["previous_value"] = await repo.count("contacts", date_range_filter("entered_at", prev_start, start))
    values.append(leads)

    # KPI-CRM-002 — snapshot (estado atual)
    snap = {"id": "KPI-CRM-002", "unit": "contatos", "notes": ["Estado atual — não usa o filtro de período."]}
    if total_contacts == 0:
        snap.update(status="sem_dados", breakdown=[])
    else:
        rows = await repo.aggregate("contacts", [{"$group": {"_id": "$stage", "n": {"$sum": 1}}}])
        counts = {r["_id"]: r["n"] for r in rows}
        snap.update(status="ok", value=total_contacts, breakdown=[
            {"key": code, "label": cfg["label"], "value": counts.get(code, 0), "color": cfg["color"]}
            for code, cfg in stage_labels.items()
        ])
    values.append(snap)

    # KPI-CRM-003 — conversão por coorte (eventos)
    cohort_val = {"id": "KPI-CRM-003", "unit": "%", "notes": [], "breakdown": []}
    cohort = await repo.find("contacts", date_range_filter("entered_at", start, end))
    if not cohort:
        cohort_val.update(status="sem_dados", notes=["Nenhum contato entrou no período selecionado."])
    else:
        ids = [c["id"] for c in cohort]
        events = await repo.find("contact_events", {
            "contact_id": {"$in": ids}, "type": {"$in": ["created", "stage_change"]},
            "to_stage": {"$in": reached_set(target_stage)},
        })
        first_reach: dict[str, datetime] = {}
        exception_ids: set[str] = set()
        for ev in events:
            if ev["contact_id"] not in first_reach or ev["at"] < first_reach[ev["contact_id"]]:
                first_reach[ev["contact_id"]] = ev["at"]
            if ev.get("exception_confirmed"):
                exception_ids.add(ev["contact_id"])
        now = datetime.now(timezone.utc)
        window = timedelta(days=window_days)
        converted, open_window = 0, 0
        for c in cohort:
            reach = first_reach.get(c["id"])
            if reach is not None and reach <= c["entered_at"] + window:
                converted += 1
            elif c["entered_at"] + window > now:
                open_window += 1
        denom = len(cohort)
        cohort_val.update(status="ok", numerator=converted, denominator=denom,
                          value=round(converted * 100 / denom, 1))
        label = stage_labels.get(target_stage, {}).get("label", target_stage)
        cohort_val["notes"].append(f"Etapa-alvo: {label} (ou posterior), janela de {window_days} dias.")
        if open_window:
            cohort_val["notes"].append(f"Resultado parcial: {open_window} contato(s) da coorte ainda estão dentro da janela.")
        if exception_ids & set(ids):
            cohort_val["notes"].append(
                f"{len(exception_ids & set(ids))} contato(s) alcançaram etapas de agenda por exceção justificada (Agenda — Fase 2).")
    values.append(cohort_val)

    # KPI-CRM-004 — contatos sem responsável (snapshot)
    active = await repo.count("contacts", {"stage": {"$ne": LOST}})
    no_owner = {"id": "KPI-CRM-004", "unit": "contatos", "notes": ["Estado atual — não usa o filtro de período."], "breakdown": []}
    if active == 0:
        no_owner.update(status="sem_dados")
    else:
        n = await repo.count("contacts", {"stage": {"$ne": LOST}, "owner_id": None})
        no_owner.update(status="ok", value=n, numerator=n, denominator=active)
    values.append(no_owner)

    for d in REGISTRY:
        if not d["available"]:
            values.append({"id": d["id"], "status": "indisponivel", "unit": d["unit"], "breakdown": [],
                           "notes": [f"Indisponível — depende da {d['depends_on']}"]})
    return values


def validate_target(target_stage: str) -> bool:
    return target_stage in ORDER and target_stage != "iniciou_conversa"
