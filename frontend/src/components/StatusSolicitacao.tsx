import type { StatusSolicitacao as Status } from '../api/solicitacoes';
import { Icon, type NomeIcone } from './Icon';

/**
 * Selo de status de solicitação (RF-SO-08; spec v2 §8.5): texto sempre, nunca só
 * cor; o texto é o `rotulo_status` da API (tipo 3: "Encaminhada à equipe"). O tom
 * segue REQUISITOS §3.12: cinza (recebida, cancelada), azul (enviada, em
 * atendimento), âmbar (o que depende do associado), menta (concluída), rose (não seguiu).
 */
type Tom = 'neutro' | 'info' | 'atencao' | 'ok' | 'negativo';

const TOM: Record<Status, Tom> = {
  criada: 'neutro',
  enviada: 'info',
  em_atendimento: 'info',
  pendente_associado: 'atencao',
  concluida_positiva: 'ok',
  concluida_negativa: 'negativo',
  cancelada: 'neutro',
};

const ICONE: Record<Status, NomeIcone> = {
  criada: 'caixa',
  enviada: 'seta',
  em_atendimento: 'relogio',
  pendente_associado: 'alerta',
  concluida_positiva: 'check',
  concluida_negativa: 'info',
  cancelada: 'fechar',
};

/** Rótulos da spec (proposta até P-44), só para quando a API não mandar `rotulo_status`. */
export const ROTULO_STATUS_PADRAO: Record<Status, string> = {
  criada: 'Recebida pela APM',
  enviada: 'Enviada ao parceiro',
  em_atendimento: 'Em atendimento',
  pendente_associado: 'O parceiro precisa de algo seu',
  concluida_positiva: 'Concluída',
  concluida_negativa: 'Não seguiu',
  cancelada: 'Cancelada',
};

export function StatusSolicitacao({ status, rotulo }: { status: Status; rotulo?: string | null | undefined }) {
  const tom = TOM[status] ?? 'neutro';
  const texto = rotulo?.trim() || ROTULO_STATUS_PADRAO[status] || 'Situação indisponível';
  return (
    <span className={`status-solicitacao status-solicitacao--${tom}`} data-status={status}>
      <Icon nome={ICONE[status] ?? 'info'} tamanho={14} />
      <span>{texto}</span>
    </span>
  );
}
