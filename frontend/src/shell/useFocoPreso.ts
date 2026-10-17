import { useEffect, type RefObject } from 'react';

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Foco preso no diálogo enquanto `ativo` (RNF-10): Tab e Shift+Tab circulam
 * dentro do contêiner, Esc chama `aoFechar`, e ao desativar o foco volta ao
 * elemento que abriu o diálogo.
 */
export function useFocoPreso(conteiner: RefObject<HTMLElement | null>, ativo: boolean, aoFechar: () => void): void {
  useEffect(() => {
    const el = conteiner.current;
    if (!ativo || !el) return;
    const anterior = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focaveis = () => Array.from(el.querySelectorAll<HTMLElement>(FOCAVEIS));
    focaveis()[0]?.focus();

    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') {
        evento.preventDefault();
        aoFechar();
        return;
      }
      if (evento.key !== 'Tab') return;
      const lista = focaveis();
      const primeiro = lista[0];
      const ultimo = lista[lista.length - 1];
      if (!primeiro || !ultimo) return;
      if (evento.shiftKey && document.activeElement === primeiro) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      }
    };
    document.addEventListener('keydown', aoTeclar);
    return () => {
      document.removeEventListener('keydown', aoTeclar);
      anterior?.focus();
    };
  }, [conteiner, ativo, aoFechar]);
}
