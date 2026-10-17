import { useEffect, useRef } from 'react';
import { Icon } from '../components/Icon';
import { MenuLateral } from './MenuLateral';
import { useFocoPreso } from './useFocoPreso';

export const ID_DRAWER = 'menu-mobile';

/**
 * Drawer mobile (RF-SH-05): `role=dialog` + `aria-modal`, foco preso, Esc e
 * toque no scrim fecham, foco volta ao hambúrguer, rolagem da página travada
 * enquanto aberto. Fechado, fica `visibility:hidden` (fora da ordem de Tab e
 * da árvore de acessibilidade) para permitir a animação de saída.
 */
export function Drawer({ aberto, aoFechar }: { aberto: boolean; aoFechar: () => void }) {
  const painel = useRef<HTMLDivElement>(null);
  useFocoPreso(painel, aberto, aoFechar);

  useEffect(() => {
    const raiz = document.documentElement;
    raiz.classList.toggle('rolagem-travada', aberto);
    return () => raiz.classList.remove('rolagem-travada');
  }, [aberto]);

  return (
    <>
      <div className={aberto ? 'scrim scrim--visivel' : 'scrim'} onClick={aoFechar} aria-hidden="true" />
      <div
        ref={painel}
        id={ID_DRAWER}
        className={aberto ? 'drawer drawer--aberto' : 'drawer'}
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
      >
        <MenuLateral
          aoNavegar={aoFechar}
          rotuloNav="Menu principal (mobile)"
          topo={
            <button type="button" className="drawer__fechar" onClick={aoFechar} aria-label="Fechar menu">
              <Icon nome="fechar" />
            </button>
          }
        />
      </div>
    </>
  );
}
