import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { useSessao } from '../state/SessaoContext';
import { CampoBusca } from './CampoBusca';
import { ID_DRAWER } from './Drawer';

interface Props {
  titulo: string;
  drawerAberto: boolean;
  aoAbrirMenu: () => void;
}

/** Header sticky (RF-SH-03). O h1 recebe o foco na troca de rota. */
export const Cabecalho = forwardRef<HTMLHeadingElement, Props>(function Cabecalho(
  { titulo, drawerAberto, aoAbrirMenu },
  refTitulo,
) {
  const { sessao } = useSessao();
  const { nome, iniciais } = sessao.associado;

  return (
    <header className="topo">
      <div className="topo__interno">
        <button
          type="button"
          className="topo__menu"
          aria-label="Abrir menu"
          aria-expanded={drawerAberto}
          aria-controls={ID_DRAWER}
          onClick={aoAbrirMenu}
        >
          <Icon nome="menu" tamanho={20} />
        </button>
        <h1 ref={refTitulo} className="topo__titulo" tabIndex={-1}>
          {titulo}
        </h1>
        <CampoBusca />
        <div className="topo__acoes">
          {sessao.flags.mensalidade_zero ? (
            <span className="pill-status">
              <span className="pill-status__ponto" aria-hidden="true" />
              Mensalidade Zero ativa
            </span>
          ) : null}
          <Link
            to="/carteirinha"
            className="avatar avatar--40"
            // WCAG 2.5.3: o nome acessível começa pelo texto visível (as iniciais).
            aria-label={nome ? `${iniciais}, carteirinha digital de ${nome}` : `${iniciais}, carteirinha digital`}
          >
            {iniciais}
          </Link>
        </div>
      </div>
    </header>
  );
});
