import {
  BarChart3,
  BookMarked,
  Bot,
  CalendarDays,
  KanbanSquare,
  LayoutDashboard,
  Library,
  MessagesSquare,
  Package,
  Plug,
  Receipt,
  RefreshCcw,
  Settings,
  Sparkles,
  Stethoscope,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface ModuleDef {
  key: string;
  label: string;
  path: string;
  icon: LucideIcon;
  phase: number;
  permission?: string;
  scope?: string[];
}

export const MODULES: ModuleDef[] = [
  { key: "dashboard", label: "Dashboard geral", path: "/", icon: LayoutDashboard, phase: 1, permission: "dashboard:read" },
  { key: "crm", label: "CRM", path: "/crm", icon: KanbanSquare, phase: 1, permission: "crm:read" },
  {
    key: "conversas", label: "Conversas", path: "/conversas", icon: MessagesSquare, phase: 2,
    scope: [
      "Lista, pesquisa e filtros de conversas com histórico cronológico persistente.",
      "Identificação do contato com link para o cartão do CRM (mesmo registro de contato).",
      "Etiquetas, notas internas, responsável e indicador de atendimento por IA ou humano.",
      "Botões Assumir conversa / Devolver ao agente, com bloqueio de envio automático concorrente no backend.",
      "Na Fase 2, somente conversas demonstrativas claramente identificadas; canal real apenas na Fase 6.",
    ],
  },
  {
    key: "agenda", label: "Agenda", path: "/agenda", icon: CalendarDays, phase: 2,
    scope: [
      "Visualizações diária, semanal e mensal com cliente, serviço e profissional.",
      "Confirmação, cancelamento, reagendamento e detecção de conflitos.",
      "Estados agendado, confirmado, compareceu, cancelado e não compareceu, alimentando o funil de forma idempotente.",
      "Até lá, mover contatos para Agendou/Compareceu no CRM exige exceção justificada.",
    ],
  },
  { key: "leads", label: "Leads", path: "/leads", icon: UserPlus, phase: 1, permission: "crm:read" },
  { key: "clientes", label: "Clientes", path: "/clientes", icon: Users, phase: 1, permission: "crm:read" },
  {
    key: "profissionais", label: "Profissionais", path: "/profissionais", icon: Stethoscope, phase: 2,
    scope: [
      "Cadastro de profissionais, especialidades, serviços habilitados e disponibilidade.",
      "Conexão individual e opcional ao agente de IA (apenas Admin ou Gestor com permissão explícita).",
      "Dashboard de desempenho com fórmula, amostra e período (Fase 3).",
    ],
  },
  { key: "servicos", label: "Serviços e procedimentos", path: "/servicos", icon: Sparkles, phase: 1, permission: "services:read" },
  {
    key: "followup", label: "Follow-up e reativação", path: "/follow-up", icon: RefreshCcw, phase: 3,
    scope: [
      "Pendências com próxima data, responsável, motivo, prioridade, tentativas e resultado.",
      "Segmentos de reativação com critérios configuráveis, respeitando consentimento e opt-out.",
      "Dashboard comercial com conversões atribuídas segundo critérios explícitos.",
      "Na Fase 1, a 'próxima ação' do contato no CRM já é registrada e persistida.",
    ],
  },
  {
    key: "financeiro", label: "Financeiro", path: "/financeiro", icon: Wallet, phase: 4,
    scope: [
      "Receitas, recebimentos, fluxo de caixa e dashboard financeiro.",
      "Mesmos registros financeiros que a tela Despesas — sem tabelas duplicadas.",
      "Distinção entre competência e caixa; resultado de caixa não é lucro contábil.",
    ],
  },
  {
    key: "despesas", label: "Despesas", path: "/despesas", icon: Receipt, phase: 4,
    scope: [
      "Despesas por categoria, competência, vencimento e pagamento, com fornecedor e recorrência.",
      "Consulta os mesmos lançamentos do Financeiro; compras não duplicam despesas.",
    ],
  },
  {
    key: "estoque", label: "Estoque", path: "/estoque", icon: Package, phase: 5,
    scope: [
      "Produtos, SKU, lote, validade, estoque mínimo e custo unitário.",
      "Movimentações auditáveis (entrada, consumo, ajuste, perda, devolução, transferência).",
      "Consumo por serviço somente com confirmação do consumo real — agendar não é consumir.",
    ],
  },
  { key: "relatorios", label: "Relatórios e desempenho", path: "/relatorios", icon: BarChart3, phase: 1, permission: "indicators:read" },
  {
    key: "agente", label: "Agente de IA", path: "/agente-ia", icon: Bot, phase: 7,
    scope: [
      "Configuração por agente: nome, finalidade, provedor e modelo, objetivos, tom, regras, critérios de encaminhamento humano, ferramentas permitidas e ações proibidas.",
      "Prompt-base armazenado no backend, versionado (rascunho → teste → publicação explícita), com autor, data e reversão para versões anteriores.",
      "Ambiente de avaliação mostrando resposta, contexto usado, fontes recuperadas e ferramentas acionadas — sem enviar mensagens reais pelo WhatsApp.",
      "Em cada execução: prompt publicado + contexto da conversa + dados autorizados + trechos do RAG + ferramentas permitidas; conteúdo recuperado nunca altera instruções, permissões ou políticas.",
      "Pausa do agente, registro de ações e ativação independente da conexão do WhatsApp.",
      "Nenhum modelo de IA está conectado nesta fase.",
    ],
  },
  {
    key: "rag", label: "Base de conhecimento — RAG", path: "/base-conhecimento", icon: Library, phase: 7,
    scope: [
      "Gerenciada separadamente do prompt-base: cadastro, organização, categorização por origem e finalidade, versões e remoção de documentos.",
      "Pipeline: Documento → Extração → Limpeza → Segmentação → Embeddings → Índice → Recuperação → Contexto do agente.",
      "Seleção das bases disponíveis por agente, com restrições por clínica e função.",
      "Erros de ingestão/indexação identificados; documentos com falha nunca ficam disponíveis ao agente.",
      "Base jurídica futura: repositório github.com/ctresb/leis como fonte candidata (não oficial), com ingestão seletiva e validação de fonte oficial, jurisdição, vigência, número, órgão emissor, URL, data da consulta, versão e estado de validação.",
      "Respostas jurídicas exibem a fonte, indicam quando não validadas e não constituem parecer jurídico.",
    ],
  },
  {
    key: "repertorio", label: "Repertório operacional Vatrexz", path: "/repertorio", icon: BookMarked, phase: 7,
    scope: [
      "Padrões reutilizáveis: DADO → GAP → CONSEQUÊNCIA → OPORTUNIDADE → SOLUÇÃO → MÉTRICA.",
      "Distinção explícita entre FATO, EVIDÊNCIA, SINAL, HIPÓTESE e ESTIMATIVA; distinção entre texto legislativo, interpretação, orientação interna e hipótese.",
      "Relação com processos, indicadores, serviços, profissionais, documentos e estoque.",
    ],
  },
  {
    key: "integracoes", label: "Integrações", path: "/integracoes", icon: Plug, phase: 6,
    scope: [
      "Canais e integrações: Conectar WhatsApp com adaptador independente do fornecedor.",
      "QR Code real apenas quando o provedor suportar; estados e expirações (QR, solicitação, sessão) distintos.",
      "Consentimento, opt-out, modelos aprovados e janelas de atendimento; sessões isoladas por clínica.",
      "Nenhum canal está conectado nesta fase.",
    ],
  },
  { key: "configuracoes", label: "Configurações", path: "/configuracoes", icon: Settings, phase: 1 },
];

export function moduleForPath(pathname: string): ModuleDef | undefined {
  if (pathname === "/") return MODULES[0];
  return MODULES.find((m) => m.path !== "/" && pathname.startsWith(m.path));
}
