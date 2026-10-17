import { render } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import type { Sessao } from '../api/tipos';
import { App } from '../App';

export function fabricarSessao(parcial: Partial<Omit<Sessao, 'associado' | 'flags' | 'config'>> & {
  associado?: Partial<Sessao['associado']>;
  flags?: Partial<Sessao['flags']>;
  config?: Partial<Sessao['config']>;
} = {}): Sessao {
  return {
    csrf: 'token-csrf-teste',
    rota_inicial: '/area',
    stub: false,
    solicitacoes_aguardando: 0,
    expira_em: '2026-10-17T12:00:00Z',
    ...parcial,
    associado: {
      nome: 'Telma Nogueira',
      nome_exibicao: 'Telma',
      iniciais: 'TN',
      tipo: 'Efetivo',
      status: 'Ativo',
      tem_foto: false,
      foto_versao: null,
      ...parcial.associado,
    },
    flags: {
      mensalidade_zero: false,
      fatura_valor: false,
      patrocinio: false,
      clube_economia: false,
      comunidade_posts: false,
      wallet: false,
      erp_financeiro: false,
      totalpass: false,
      ...parcial.flags,
    },
    config: { whatsapp: '551131886200', show_whatsapp: true, animations: true, ...parcial.config },
  };
}

export function respostaJson(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Request-Id': '0123456789abcdef' },
  });
}

export type Rotas = (url: string, init: RequestInit | undefined) => Response | undefined;

/** `fetch` falso: `/api/v1/sessao` devolve a sessão; `rotas` responde o resto; senão 202 vazio. */
export function simularApi(sessao: Sessao, rotas?: Rotas) {
  const chamadas: { url: string; init: RequestInit | undefined }[] = [];
  const fetchFalso = vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = String(entrada);
    chamadas.push({ url, init });
    if (url === '/api/v1/sessao') return respostaJson(sessao);
    const especifica = rotas?.(url, init);
    if (especifica) return especifica;
    return respostaJson({ gravados: 0, descartados: 0 }, 202);
  });
  vi.stubGlobal('fetch', fetchFalso);
  return { fetchFalso, chamadas };
}

export function montarApp(
  rota: string,
  sessao: Sessao = fabricarSessao(),
  rotas?: Rotas,
): ReturnType<typeof render> & ReturnType<typeof simularApi> {
  const api = simularApi(sessao, rotas);
  const resultado = render(
    <MemoryRouter initialEntries={[rota]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </MemoryRouter>,
  );
  return { ...resultado, ...api };
}

export function Envolvido({ children }: { children: ReactNode }) {
  return <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{children}</MemoryRouter>;
}
