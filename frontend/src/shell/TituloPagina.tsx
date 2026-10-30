import { createContext, useContext, useEffect } from 'react';

/**
 * Título do `h1` vindo da página (sub-rotas: `/beneficios/{slug}` mostra o nome
 * do benefício, `/solicitacoes/{uuid}` o protocolo). O shell continua dono do
 * `h1`, do `<title>` e do foco; a página só informa o texto. `null` devolve o
 * título da rota. O shell zera o título a cada troca de pathname.
 */
export type DefinirTituloPagina = (titulo: string | null) => void;

export const ContextoTituloPagina = createContext<DefinirTituloPagina | null>(null);

export function useDefinirTituloPagina(titulo: string | null): void {
  const definir = useContext(ContextoTituloPagina);
  useEffect(() => {
    if (!definir) return;
    const limpo = titulo?.trim() || null;
    definir(limpo);
    return () => definir(null);
  }, [definir, titulo]);
}
