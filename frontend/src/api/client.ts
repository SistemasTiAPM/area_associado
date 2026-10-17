import type { CorpoErro } from './tipos';

/**
 * Cliente da API `/api/v1` (mesma origem, cookie httponly de sessão).
 *
 * - CSRF: `X-CSRF-Token` em todo método não seguro (RF-AU-05). O token vem de
 *   `GET /sessao` e fica só em memória.
 * - `redirect: 'error'`: a API nunca redireciona; um 3xx inesperado vira erro
 *   em vez de a SPA receber HTML de outra página.
 * - 401 → navega para o login com `next` = rota atual (RF-AU-08).
 * - 403 `csrf_invalido` → avisa quem registrou `aoCsrfInvalido` (renova o
 *   token) e propaga o erro; NÃO reenvia sozinho (RF-SH-09).
 */

export const MENSAGEM_SEM_CONEXAO = 'Sem conexão. Verifique a internet e tente novamente.';
const MENSAGEM_PADRAO = 'Não foi possível concluir agora. Tente novamente em instantes.';

export class ApiError extends Error {
  readonly status: number;
  readonly erro: string;
  readonly requestId: string | null;
  readonly detalhes: CorpoErro['detalhes'];

  constructor(status: number, erro: string, mensagem: string, requestId: string | null = null, detalhes?: CorpoErro['detalhes']) {
    super(mensagem);
    this.name = 'ApiError';
    this.status = status;
    this.erro = erro;
    this.requestId = requestId;
    this.detalhes = detalhes;
  }
}

let tokenCsrf: string | null = null;
let ouvinteCsrfInvalido: (() => void) | null = null;

export function definirCsrf(token: string | null): void {
  tokenCsrf = token;
}

export function obterCsrf(): string | null {
  return tokenCsrf;
}

export function aoCsrfInvalido(ouvinte: (() => void) | null): void {
  ouvinteCsrfInvalido = ouvinte;
}

export function urlLogin(): string {
  const destino = `${window.location.pathname}${window.location.search}`;
  return `/auth/login?next=${encodeURIComponent(destino)}`;
}

export function irParaLogin(): void {
  window.location.assign(urlLogin());
}

type Metodo = 'GET' | 'POST' | 'PUT' | 'DELETE';

export interface OpcoesRequisicao {
  metodo?: Metodo;
  corpo?: unknown;
  sinal?: AbortSignal;
}

function corpoErroValido(valor: unknown): valor is CorpoErro {
  if (typeof valor !== 'object' || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return typeof v.erro === 'string' && typeof v.mensagem === 'string';
}

async function lerCorpo(resposta: Response): Promise<unknown> {
  try {
    return await resposta.json();
  } catch (falha) {
    if (!(falha instanceof SyntaxError)) throw falha;
    return null; // proxy ou servidor sem corpo JSON: cai na mensagem padrão
  }
}

async function lerErro(resposta: Response): Promise<ApiError> {
  const corpo = await lerCorpo(resposta);
  const requestId = resposta.headers.get('X-Request-Id');
  if (corpoErroValido(corpo)) {
    return new ApiError(resposta.status, corpo.erro, corpo.mensagem, corpo.request_id ?? requestId, corpo.detalhes);
  }
  const erro = resposta.status === 429 ? 'limite_taxa' : resposta.status >= 500 ? 'erro_interno' : 'erro_desconhecido';
  return new ApiError(resposta.status, erro, MENSAGEM_PADRAO, requestId);
}

async function executar<T>(caminho: string, init: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(`/api/v1${caminho}`, { ...init, credentials: 'same-origin', cache: 'no-store', redirect: 'error' });
  } catch (falha) {
    if (falha instanceof DOMException && falha.name === 'AbortError') throw falha;
    throw new ApiError(0, 'sem_conexao', MENSAGEM_SEM_CONEXAO);
  }

  if (resposta.status === 401) {
    irParaLogin();
    throw await lerErro(resposta);
  }
  if (!resposta.ok) {
    const erro = await lerErro(resposta);
    if (erro.erro === 'csrf_invalido') ouvinteCsrfInvalido?.();
    throw erro;
  }
  if (resposta.status === 204) return undefined as T;
  return (await resposta.json()) as T;
}

export async function api<T>(caminho: string, opcoes: OpcoesRequisicao = {}): Promise<T> {
  const metodo = opcoes.metodo ?? 'GET';
  const cabecalhos: Record<string, string> = { Accept: 'application/json' };
  if (metodo !== 'GET') {
    cabecalhos['Content-Type'] = 'application/json';
    if (tokenCsrf) cabecalhos['X-CSRF-Token'] = tokenCsrf;
  }
  const init: RequestInit = { method: metodo, headers: cabecalhos };
  if (opcoes.corpo !== undefined) init.body = JSON.stringify(opcoes.corpo);
  if (opcoes.sinal) init.signal = opcoes.sinal;
  return executar<T>(caminho, init);
}

/** Envio multipart (foto). O navegador define o Content-Type com o boundary. */
export async function enviarFormulario<T>(caminho: string, formulario: FormData): Promise<T> {
  const cabecalhos: Record<string, string> = { Accept: 'application/json' };
  if (tokenCsrf) cabecalhos['X-CSRF-Token'] = tokenCsrf;
  return executar<T>(caminho, { method: 'POST', headers: cabecalhos, body: formulario });
}
