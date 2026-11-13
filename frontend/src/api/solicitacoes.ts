import { ApiError, api } from './client';

/**
 * Minhas solicitações (P05; RF-SO-01..15; contrato da Onda 2 em docs/PLANO-EXECUCAO.md).
 * Nunca `contact_id`, `sub`, CPF, `crm_*` ou e-mail na resposta (RF-SO-06, ADR-0014).
 */

/** Oito status internos (spec v2 §8.5); `sem_retorno` é marcador (`aguardando_parceiro`), não status. */
export type StatusSolicitacao =
  | 'criada'
  | 'enviada'
  | 'em_atendimento'
  | 'pendente_associado'
  | 'concluida_positiva'
  | 'concluida_negativa'
  | 'cancelada';

/** Tipos que a SPA cria por `POST /solicitacoes` (os demais nascem de outras rotas). */
export type TipoServicoCriavel = 'outro' | 'declaracao_associado' | 'alteracao_cadastro';

/**
 * Paridade com o App APM (ADR-0024; flag `solicitacoes_crm`): situação do registro no CRM,
 * a mesma que o App mostra. Nula enquanto o pedido não chegou ao CRM.
 */
export type SituacaoCrm = 'aberta' | 'em_andamento' | 'aguardando_associado' | 'concluida' | 'cancelada';
export type CanalAbertura = 'app' | 'minha_apm';
export type QuemResponde = 'central' | 'apm';

export type AtorLinhaDoTempo = 'voce' | 'equipe_apm' | 'parceiro' | 'sistema';

export interface ResumoSolicitacao {
  id: string;
  tipo: { codigo: string; rotulo: string };
  beneficio: { slug: string; titulo: string } | null;
  status: StatusSolicitacao;
  /** Rótulo ao associado vindo do servidor (7 rótulos; tipo 3: "Encaminhada à equipe"). */
  rotulo_status: string;
  /** Marcador `sem_retorno`: "Aguardando o parceiro, a APM já está cobrando". */
  aguardando_parceiro: boolean;
  /** AAAA-MM-DD; nulo enquanto não foi enviada (RF-SO-15). */
  prazo_em: string | null;
  contato: { canal: string; texto: string } | null;
  /** Protocolo da Central no CRM (CAS-######-XXXXXX); nulo até o pedido chegar lá. */
  protocolo: string | null;
  /** Já está no CRM: cancelar e complementar são com a Central, pelo protocolo (ADR-0023). */
  na_central: boolean;
  criada_em: string;
  atualizada_em: string;
  pode_cancelar: boolean;
  pode_responder: boolean;
  pode_avaliar: boolean;
  /** Paridade com o App (ADR-0024); ausentes ou no padrão com a flag desligada. */
  situacao?: SituacaoCrm | null;
  canal?: CanalAbertura | null;
  responde?: QuemResponde | null;
  pode_enviar_mensagem?: boolean;
  nova_resposta?: boolean;
}

export type ValorCampo = string | number | boolean | null | Record<string, string | number | boolean | null>;

export interface EventoLinhaDoTempo {
  quando: string;
  status: StatusSolicitacao;
  rotulo: string;
  ator: AtorLinhaDoTempo;
  mensagem: string | null;
}

export interface Avaliacao {
  nota: number;
  comentario: string | null;
  avaliada_em: string;
}

export interface Solicitacao extends ResumoSolicitacao {
  /** Só os campos permitidos do tipo (allowlist no servidor). */
  campos: Record<string, ValorCampo>;
  linha_do_tempo: EventoLinhaDoTempo[];
  avaliacao: Avaliacao | null;
}

export type SituacaoLista = 'andamento' | 'encerradas';

export interface PaginaSolicitacoes {
  itens: ResumoSolicitacao[];
  proximo_cursor: string | null;
  /** O CRM não respondeu: o que foi aberto pelo App pode estar faltando. */
  parcial?: boolean;
}

/** Tipo do catálogo comum com o App (`GET /solicitacoes/tipos`); some quando a APM desliga o serviço. */
export interface TipoCatalogo {
  codigo: string;
  rotulo: string;
  grupo: string | null;
  grupo_rotulo: string | null;
  ordem: number;
  responde: QuemResponde;
  carencia_meses: number;
}

export interface MensagemConversa {
  id: string;
  autor: 'voce' | 'central';
  texto: string;
  quando: string | null;
  /** `enviando`: na fila da área; `falhou`: não chegou à Central. */
  estado: 'enviada' | 'enviando' | 'falhou';
}

export interface Conversa {
  mensagens: MensagemConversa[];
  pode_enviar: boolean;
  motivo_bloqueio: 'aguardando_envio' | 'encerrada' | 'nao_permitida' | null;
  responde: QuemResponde;
  truncado: boolean;
}

/** Limites do hub, em unidades UTF-16 (o `length` do JavaScript conta igual). */
export const DESCRICAO_MIN = 10;
export const DESCRICAO_MAX = 2000;
export const MENSAGEM_MIN = 2;
export const MENSAGEM_MAX = 2000;

export const LIMITE_PAGINA = 20;
export const RESPOSTA_MAX = 2000;
export const MOTIVO_CANCELAMENTO_MAX = 200;
export const COMENTARIO_AVALIACAO_MAX = 500;
export const NOTA_MAX = 10;

/** Identificador de solicitação aceito na URL (uuid; mesmo formato do segmento de sub-rota). */
const ID_VALIDO = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

function caminhoSolicitacao(id: string, acao = ''): string {
  if (!ID_VALIDO.test(id)) {
    // Mesmo erro de "não encontrada" do servidor: sem oráculo e sem montar URL com dado inválido.
    throw new ApiError(404, 'nao_encontrado', 'Não encontramos esta solicitação.');
  }
  return `/solicitacoes/${encodeURIComponent(id)}${acao}`;
}

/**
 * Chave de idempotência de um formulário (RF-SO-03): gerada uma vez quando o
 * formulário abre e reenviada em cada nova tentativa do mesmo pedido; nova só
 * depois de um envio confirmado.
 */
export function novaChaveIdempotencia(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Navegador sem randomUUID (Safari < 15.4): UUID v4 a partir de getRandomValues (RFC 9562 §5.4).
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = ((b[6] ?? 0) & 0x0f) | 0x40;
  b[8] = ((b[8] ?? 0) & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function listarSolicitacoes(situacao: SituacaoLista, cursor: string | null, sinal?: AbortSignal) {
  const consulta = new URLSearchParams({ situacao, limite: String(LIMITE_PAGINA) });
  if (cursor) consulta.set('cursor', cursor);
  return api<PaginaSolicitacoes>(`/solicitacoes?${consulta.toString()}`, sinal ? { sinal } : {});
}

export function obterSolicitacao(id: string, sinal?: AbortSignal) {
  return api<Solicitacao>(caminhoSolicitacao(id), sinal ? { sinal } : {});
}

export interface NovaSolicitacao {
  /** Um `TipoServicoCriavel` ou, com a paridade ligada, o `codigo` de um `TipoCatalogo`. */
  tipo_servico: TipoServicoCriavel | (string & {});
  campos: Record<string, ValorCampo>;
  chave_idempotencia: string;
}

export const criarSolicitacao = (pedido: NovaSolicitacao) =>
  api<Solicitacao>('/solicitacoes', { metodo: 'POST', corpo: pedido });

export function cancelarSolicitacao(id: string, motivo?: string) {
  const texto = motivo?.trim();
  return api<Solicitacao>(caminhoSolicitacao(id, '/cancelar'), { metodo: 'POST', corpo: texto ? { motivo: texto } : {} });
}

export function responderSolicitacao(id: string, texto: string) {
  return api<Solicitacao>(caminhoSolicitacao(id, '/responder'), { metodo: 'POST', corpo: { texto: texto.trim() } });
}

export async function listarTipos(sinal?: AbortSignal): Promise<TipoCatalogo[]> {
  const resposta = await api<{ itens: TipoCatalogo[] }>('/solicitacoes/tipos', sinal ? { sinal } : {});
  return resposta.itens;
}

/**
 * `atualizar`: pedido explícito do associado ("Atualizar conversa" ou logo depois de enviar) —
 * o servidor confere no CRM se há mensagem nova. Sem ele, a conversa vem do cache do servidor
 * enquanto nada mudou (cada mensagem relida gasta cota do hub).
 */
export function listarMensagens(id: string, sinal?: AbortSignal, atualizar = false) {
  const caminho = caminhoSolicitacao(id, '/mensagens') + (atualizar ? '?atualizar=true' : '');
  return api<Conversa>(caminho, sinal ? { sinal } : {});
}

/** `chave` = `novaChaveIdempotencia()`, a mesma em cada nova tentativa da mesma mensagem. */
export function enviarMensagem(id: string, texto: string, chave: string) {
  return api<MensagemConversa>(caminhoSolicitacao(id, '/mensagens'), {
    metodo: 'POST',
    corpo: { texto: texto.trim(), chave_idempotencia: chave },
  });
}

export function avaliarSolicitacao(id: string, nota: number, comentario?: string) {
  const texto = comentario?.trim();
  return api<Solicitacao>(caminhoSolicitacao(id, '/avaliar'), {
    metodo: 'POST',
    corpo: texto ? { nota, comentario: texto } : { nota },
  });
}

/**
 * Data de liberação de `409 nao_elegivel` (declaração AMB com < 1 mês de filiação).
 * O contrato diz `{libera_em}`: aceita no corpo (`extras`), em `detalhes` objeto ou
 * como item `{campo: 'libera_em', mensagem: 'AAAA-MM-DD'}`. Data inválida → `null`.
 */
export function liberaEmDe(falha: unknown): Date | null {
  if (!(falha instanceof ApiError) || falha.erro !== 'nao_elegivel') return null;
  const candidatos: unknown[] = [falha.extras.libera_em];
  const detalhes: unknown = falha.detalhes;
  if (Array.isArray(detalhes)) {
    for (const item of detalhes as unknown[]) {
      if (typeof item === 'object' && item !== null && (item as Record<string, unknown>).campo === 'libera_em') {
        candidatos.push((item as Record<string, unknown>).mensagem);
      }
    }
  } else if (typeof detalhes === 'object' && detalhes !== null) {
    candidatos.push((detalhes as Record<string, unknown>).libera_em);
  }
  for (const valor of candidatos) {
    if (typeof valor !== 'string') continue;
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(valor);
    if (!m) continue;
    // Meio-dia UTC: a data de calendário não muda no fuso de exibição (America/Sao_Paulo).
    const data = new Date(`${m[1]}-${m[2]}-${m[3]}T12:00:00Z`);
    if (Number.isFinite(data.getTime())) return data;
  }
  return null;
}
