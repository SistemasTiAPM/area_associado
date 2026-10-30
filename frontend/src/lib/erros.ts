import { ApiError } from '../api/client';
import { caminhoParaAnalytics } from '../rotas';
import { registrarUso } from './analytics';

/** `erro_exibido.detalhes.rota` (validador `_ROTA` de app/uso.py): só caminhos da área, sem consulta. */
const ROTA_ANALYTICS = /^\/area(\/[a-z0-9-]{1,32}){0,3}$/;
/** `erro_exibido.detalhes.request_id` (validador `_HEX16`). */
const REQUEST_ID = /^[0-9a-f]{16}$/;

/**
 * Registra `erro_exibido` (REQUISITOS §8) para um erro mostrado ao associado — por
 * toast (`useToast().mostrarErro`) ou por bloco (`EstadoErro`). Só código do erro,
 * `request_id` e rota; nunca a mensagem. Rota de sub-rota pessoal (protocolo) não
 * vira `_`, como no `pagina_ver` (regra 17).
 */
export function registrarErroExibido(falha: unknown): void {
  const erro = falha instanceof ApiError ? falha : null;
  const detalhes: Record<string, string> = { codigo: erro?.erro ?? 'erro_cliente' };
  if (erro?.requestId && REQUEST_ID.test(erro.requestId)) detalhes.request_id = erro.requestId;
  // Mesmo identificador do `pagina_ver`: protocolo de solicitação vira `_` (dado do associado).
  const caminho = window.location.pathname.replace(/^\/area(?=\/|$)/, '') || '/';
  const rota = caminhoParaAnalytics(caminho);
  if (ROTA_ANALYTICS.test(rota)) detalhes.rota = rota;
  registrarUso({ acao: 'erro_exibido', entidade: 'rota', entidade_id: rota, detalhes });
}
