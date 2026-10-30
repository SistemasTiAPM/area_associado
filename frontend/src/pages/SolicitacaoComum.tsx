import { ApiError } from '../api/client';
import type { ResumoSolicitacao } from '../api/solicitacoes';
import { dataBR, dataDaApi } from '../lib/formato';
import { urlTelefone } from '../lib/links';

/** Peças compartilhadas da lista e do detalhe de solicitações (P05). */

export const FAIXA_AGUARDANDO_PARCEIRO = 'Aguardando o parceiro, a APM já está cobrando';

export function abortado(falha: unknown): boolean {
  return falha instanceof DOMException && falha.name === 'AbortError';
}

export function mensagemDe(falha: unknown): string {
  return falha instanceof ApiError ? falha.message : 'Não foi possível concluir agora. Tente novamente em instantes.';
}

export function requestIdDe(falha: unknown): string | null {
  return falha instanceof ApiError ? falha.requestId : null;
}

export function data(valor: string | null): string {
  const d = dataDaApi(valor);
  return d ? dataBR(d) : '—';
}

/** Contato da solicitação (RF-SO-15): telefone vira `tel:` só com dígitos válidos; o resto é texto. */
export function ContatoSolicitacao({ contato }: { contato: NonNullable<ResumoSolicitacao['contato']> }) {
  const tel = contato.canal === 'telefone' ? urlTelefone(contato.texto.replace(/[\s().-]/g, '')) : null;
  return tel ? (
    <a className="link-texto" href={tel}>
      {contato.texto}
    </a>
  ) : (
    <>{contato.texto}</>
  );
}
