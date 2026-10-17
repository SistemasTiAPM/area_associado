import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { ROTAS, destino, rotaVisivel } from '../rotas';
import { useSessao } from '../state/SessaoContext';
import { FormularioSair } from './FormularioSair';

/** Conteúdo da sidebar (desktop) e do drawer (mobile) — RF-SH-02 e RF-SH-05. */
interface Props {
  rotuloNav: string;
  aoNavegar?: () => void;
  /** Conteúdo antes da marca (o drawer põe o botão de fechar). */
  topo?: ReactNode;
}

export function MenuLateral({ rotuloNav, aoNavegar, topo }: Props) {
  const { sessao } = useSessao();
  const rotas = ROTAS.filter((r) => rotaVisivel(r, sessao));

  return (
    <div className="menu-lateral">
      {topo}
      <div className="marca">
        <span className="marca__sigla" aria-hidden="true">
          APM
        </span>
        <span className="marca__legenda">Associação Paulista de Medicina</span>
        <p className="marca__produto">Minha APM</p>
        <p className="marca__subtitulo">área do associado</p>
      </div>
      <div className="menu-lateral__divisor" aria-hidden="true" />
      <nav aria-label={rotuloNav}>
        <ul className="nav">
          {rotas.map((rota) => (
            <li key={rota.id} className={rota.separada ? 'nav__separado' : undefined}>
              <NavLink
                to={destino(rota)}
                end={rota.caminho === ''}
                className={rota.id === 'onb' ? 'nav__item nav__item--onboarding' : 'nav__item'}
                onClick={aoNavegar}
              >
                <Icon nome={rota.icone} />
                <span>{rota.titulo}</span>
                {rota.id === 'solicitacoes' && sessao.solicitacoes_aguardando > 0 ? (
                  <span className="nav__contador">
                    {sessao.solicitacoes_aguardando}
                    <span className="visualmente-oculto"> aguardando você</span>
                  </span>
                ) : null}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="menu-lateral__rodape">
        {sessao.flags.mensalidade_zero ? (
          <div className="bloco-mensalidade">
            <p className="bloco-mensalidade__titulo">Mensalidade Zero</p>
            <p className="bloco-mensalidade__texto">patrocínio ativo · 2026</p>
          </div>
        ) : null}
        <FormularioSair />
      </div>
    </div>
  );
}
