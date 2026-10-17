import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ApiError } from '../api/client';
import { Icon } from '../components/Icon';
import { registrarUso } from '../lib/analytics';

/**
 * Toast único (RF-SH-07): uma mensagem por vez — a nova substitui a anterior —
 * com auto-dismiss em 2,6 s. As duas regiões vivas existem sempre no DOM
 * (leitor de tela só anuncia mudança em região já presente): sucesso em
 * `role=status` (polite), erro em `role=alert`.
 */

export const DURACAO_TOAST_MS = 2600;
const MENSAGEM_ERRO_PADRAO = 'Não foi possível concluir agora. Tente novamente em instantes.';
const ROTA_ANALYTICS = /^\/area(\/[a-z0-9-]{1,32}){0,3}$/;

interface Toast {
  id: number;
  texto: string;
  tipo: 'ok' | 'erro';
}

interface ValorContexto {
  mostrar: (texto: string) => void;
  mostrarErro: (falha: unknown) => void;
}

const Contexto = createContext<ValorContexto | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const proximoId = useRef(1);

  const exibir = useCallback((texto: string, tipo: Toast['tipo']) => {
    if (temporizador.current !== null) clearTimeout(temporizador.current);
    setToast({ id: proximoId.current++, texto, tipo });
    temporizador.current = setTimeout(() => setToast(null), DURACAO_TOAST_MS);
  }, []);

  useEffect(
    () => () => {
      if (temporizador.current !== null) clearTimeout(temporizador.current);
    },
    [],
  );

  const valor = useMemo<ValorContexto>(
    () => ({
      mostrar: (texto) => exibir(texto, 'ok'),
      mostrarErro: (falha) => {
        const erro = falha instanceof ApiError ? falha : null;
        exibir(erro?.message || MENSAGEM_ERRO_PADRAO, 'erro');
        const detalhes: Record<string, string> = { codigo: erro?.erro ?? 'erro_cliente' };
        if (erro?.requestId) detalhes.request_id = erro.requestId;
        const rota = window.location.pathname;
        if (ROTA_ANALYTICS.test(rota)) detalhes.rota = rota;
        registrarUso({ acao: 'erro_exibido', entidade: 'rota', entidade_id: rota.slice(0, 64), detalhes });
        if (!erro) console.error(falha); // erro de programação: visível no console, nunca silencioso
      },
    }),
    [exibir],
  );

  return (
    <Contexto.Provider value={valor}>
      {children}
      <div className="toast-regiao">
        <div role="status" aria-live="polite">
          {toast?.tipo === 'ok' ? (
            <div key={toast.id} className="toast">
              <Icon nome="check" tamanho={15} />
              <span>{toast.texto}</span>
            </div>
          ) : null}
        </div>
        <div role="alert">
          {toast?.tipo === 'erro' ? (
            <div key={toast.id} className="toast toast--erro">
              <Icon nome="alerta" tamanho={15} />
              <span>{toast.texto}</span>
            </div>
          ) : null}
        </div>
      </div>
    </Contexto.Provider>
  );
}

export function useToast(): ValorContexto {
  const valor = useContext(Contexto);
  if (valor === null) throw new Error('useToast fora do ToastProvider');
  return valor;
}
