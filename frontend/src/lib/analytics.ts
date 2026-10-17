import { obterCsrf } from '../api/client';

/**
 * Eventos de uso de origem `ui` (REQUISITOS §8). Fila em memória, enviada em
 * lotes de até 20 para `POST /api/v1/uso` com `keepalive` — sobrevive ao
 * fechamento da aba. A identidade é do servidor (sessão); aqui vai só o fato.
 *
 * Analytics nunca pode quebrar a tela: falha de envio descarta o lote e só
 * incrementa um contador (útil em teste e depuração).
 */

export type AcaoUi =
  | 'pagina_ver'
  | 'busca_global'
  | 'filtro_aplicar'
  | 'categoria_abrir'
  | 'beneficio_gerenciar'
  | 'beneficio_abrir'
  | 'totalpass_abrir'
  | 'plantoes_abrir'
  | 'clube_oferta_usar'
  | 'noticia_abrir'
  | 'congresso_programacao_abrir'
  | 'comunidade_abrir'
  | 'programa_saber_mais'
  | 'wallet_adicionar'
  | 'central_whatsapp_abrir'
  | 'erro_exibido';

export interface EventoUi {
  acao: AcaoUi;
  entidade: string;
  entidade_id?: string;
  detalhes?: Record<string, string | number>;
}

const LOTE_MAX = 20;
const ATRASO_MS = 3000;

const fila: EventoUi[] = [];
let temporizador: ReturnType<typeof setTimeout> | null = null;
let descartados = 0;

export function eventosDescartados(): number {
  return descartados;
}

export function enviarFila(keepalive = false): void {
  if (temporizador !== null) {
    clearTimeout(temporizador);
    temporizador = null;
  }
  const csrf = obterCsrf();
  while (fila.length > 0) {
    const lote = fila.splice(0, LOTE_MAX);
    if (!csrf) {
      descartados += lote.length;
      continue;
    }
    fetch('/api/v1/uso', {
      method: 'POST',
      keepalive,
      credentials: 'same-origin',
      redirect: 'error',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({ eventos: lote }),
    })
      .then((resposta) => {
        if (!resposta.ok) descartados += lote.length;
      })
      .catch(() => {
        descartados += lote.length;
      });
  }
}

export function registrarUso(evento: EventoUi): void {
  fila.push(evento);
  if (fila.length >= LOTE_MAX) {
    enviarFila();
  } else if (temporizador === null) {
    temporizador = setTimeout(() => enviarFila(), ATRASO_MS);
  }
}

let ouvintesInstalados = false;

/** Envia o que restar quando a aba some (pagehide/visibilitychange). */
export function instalarEnvioAoSair(): void {
  if (ouvintesInstalados) return;
  ouvintesInstalados = true;
  window.addEventListener('pagehide', () => enviarFila(true));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') enviarFila(true);
  });
}

/** Só para testes. */
export function _reiniciarAnalytics(): void {
  fila.length = 0;
  descartados = 0;
  if (temporizador !== null) clearTimeout(temporizador);
  temporizador = null;
}
