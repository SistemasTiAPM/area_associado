import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError, aoCsrfInvalido, api, definirCsrf } from '../api/client';
import type { Sessao } from '../api/tipos';

type Estado =
  | { fase: 'carregando' }
  | { fase: 'erro'; erro: ApiError }
  | { fase: 'pronta'; sessao: Sessao };

interface ValorContexto {
  sessao: Sessao;
  recarregar: () => Promise<void>;
}

const Contexto = createContext<ValorContexto | null>(null);

function aplicarPreferencias(sessao: Sessao): void {
  // Atributo no <html>, não estilo inline: compatível com a CSP (ADR-0013).
  document.documentElement.dataset.animacoes = sessao.config.animations ? 'on' : 'off';
}

/**
 * Primeira chamada da SPA: `GET /api/v1/sessao` (RF-AU-03). Sem sessão o
 * cliente já navegou para o login (401); erro de rede/servidor mostra a tela
 * de erro com "Tentar novamente". Nada da sessão vai para armazenamento local.
 */
export function SessaoProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ fase: 'carregando' });
  const montado = useRef(true);

  const carregar = useCallback(async (silencioso: boolean) => {
    if (!silencioso) setEstado({ fase: 'carregando' });
    try {
      const sessao = await api<Sessao>('/sessao');
      definirCsrf(sessao.csrf);
      aplicarPreferencias(sessao);
      if (montado.current) setEstado({ fase: 'pronta', sessao });
    } catch (falha) {
      if (!(falha instanceof ApiError)) throw falha;
      if (falha.status === 401) return; // já redirecionando para o login
      if (montado.current && !silencioso) setEstado({ fase: 'erro', erro: falha });
    }
  }, []);

  useEffect(() => {
    montado.current = true;
    void carregar(false);
    // 403 csrf_invalido em qualquer chamada: renova o token em silêncio.
    aoCsrfInvalido(() => void carregar(true));
    return () => {
      montado.current = false;
      aoCsrfInvalido(null);
    };
  }, [carregar]);

  const recarregar = useCallback(() => carregar(true), [carregar]);
  const valor = useMemo(
    () => (estado.fase === 'pronta' ? { sessao: estado.sessao, recarregar } : null),
    [estado, recarregar],
  );

  if (estado.fase === 'carregando') {
    return (
      <div className="tela-estado" aria-busy="true">
        <div className="tela-estado__caixa">
          <p className="tela-estado__titulo" role="status">
            Carregando a Minha APM…
          </p>
        </div>
      </div>
    );
  }
  if (estado.fase === 'erro') {
    return (
      <div className="tela-estado">
        <div className="tela-estado__caixa" role="alert">
          <h1 className="tela-estado__titulo">Não foi possível carregar a Minha APM.</h1>
          <p className="tela-estado__texto">{estado.erro.message}</p>
          {estado.erro.requestId ? (
            <p className="tela-estado__texto">
              Código para a Central de Relacionamento: <code>{estado.erro.requestId}</code>
            </p>
          ) : null}
          <button type="button" className="botao botao--primario" onClick={() => void carregar(false)}>
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSessao(): ValorContexto {
  const valor = useContext(Contexto);
  if (valor === null) throw new Error('useSessao fora do SessaoProvider');
  return valor;
}
