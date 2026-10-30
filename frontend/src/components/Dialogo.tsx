import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useFocoPreso } from '../shell/useFocoPreso';
import { Icon } from './Icon';

interface Props {
  aberto: boolean;
  titulo: string;
  /** Uma frase sob o título (vira `aria-describedby`). */
  descricao?: string | undefined;
  aoFechar: () => void;
  children?: ReactNode;
  /** Botões do rodapé (o chamador decide; um único primário por bloco, spec §3.2). */
  acoes?: ReactNode;
  /**
   * Confirmação de ação irreversível (cancelar, remover): `role=alertdialog`,
   * borda de alerta e o foco inicial cai no botão de fechar, não na ação.
   */
  destrutivo?: boolean;
  rotuloFechar?: string;
}

/**
 * Modal acessível (APG dialog): `role=dialog|alertdialog`, `aria-modal`,
 * rotulado pelo título, foco preso (`useFocoPreso`), Esc e clique no scrim
 * fecham, foco volta a quem abriu, rolagem da página travada. Puro: não fala
 * com API; quem abre decide o conteúdo e as ações.
 *
 * Renderizado num portal em `document.body`, fora do `<main>`: o conteúdo cria
 * contexto de empilhamento próprio e, no celular, a barra inferior fixa cobria o
 * rodapé do modal e seus links continuavam clicáveis por cima dele (WCAG 2.2
 * 2.5.8, achado no e2e da Onda 2). Enquanto aberto, a raiz da SPA fica `inert`
 * (fora da árvore de acessibilidade e de foco), como pede `aria-modal`.
 */
export function Dialogo({ aberto, titulo, descricao, aoFechar, children, acoes, destrutivo = false, rotuloFechar = 'Fechar' }: Props) {
  const painel = useRef<HTMLDivElement>(null);
  const idTitulo = useId();
  const idDescricao = useId();

  // Declarado antes de `useFocoPreso`: na desmontagem as limpezas rodam na ordem de
  // declaração, então a raiz deixa de ser `inert` antes de o foco voltar a quem abriu.
  useEffect(() => {
    if (!aberto) return;
    const raizApp = document.getElementById('raiz');
    if (!raizApp || raizApp.inert) return;
    raizApp.inert = true;
    return () => {
      raizApp.inert = false;
    };
  }, [aberto]);

  useFocoPreso(painel, aberto, aoFechar);

  useEffect(() => {
    if (!aberto) return;
    const raiz = document.documentElement;
    raiz.classList.add('rolagem-travada');
    return () => raiz.classList.remove('rolagem-travada');
  }, [aberto]);

  if (!aberto) return null;
  return createPortal(
    <div className="dialogo-camada">
      <div className="scrim scrim--visivel" onClick={aoFechar} aria-hidden="true" />
      <div
        ref={painel}
        className={destrutivo ? 'dialogo cartao dialogo--destrutivo' : 'dialogo cartao'}
        role={destrutivo ? 'alertdialog' : 'dialog'}
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={descricao ? idDescricao : undefined}
      >
        <div className="dialogo__cabecalho">
          <h2 className="dialogo__titulo" id={idTitulo}>
            {titulo}
          </h2>
          <button type="button" className="dialogo__fechar" onClick={aoFechar} aria-label={rotuloFechar}>
            <Icon nome="fechar" />
          </button>
        </div>
        {descricao ? (
          <p className="dialogo__descricao" id={idDescricao}>
            {descricao}
          </p>
        ) : null}
        {children ? <div className="dialogo__corpo">{children}</div> : null}
        {acoes ? <div className="dialogo__acoes botoes">{acoes}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
