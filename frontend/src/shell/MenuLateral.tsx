import type { ReactNode } from 'react';
import { NavLink } from 'react-router';
import { ConteudoAvatar } from '../components/Avatar';
import { Icon } from '../components/Icon';
import { ROTAS, destino, rotaVisivel, type Rota } from '../rotas';
import { useSessao } from '../state/SessaoContext';
import { FormularioSair } from './FormularioSair';

/**
 * Trilho lateral (desktop) e drawer (mobile) — RF-SH-02 e RF-SH-05, no visual
 * do mockup (ADR-0017): pílula de vidro, ícone + nome, ativo em gradiente.
 * "Meu perfil" fica no rodapé, com o avatar, como no mockup; "Ajuda" (P14)
 * fica no rodapé logo acima dele (fora da barra inferior).
 */
interface Props {
  rotuloNav: string;
  aoNavegar?: () => void;
  /** Conteúdo antes da marca (o drawer põe o botão de fechar). */
  topo?: ReactNode;
}

const ID_PERFIL = 'perfil';
const ID_AJUDA = 'ajuda';
const NO_RODAPE = new Set([ID_PERFIL, ID_AJUDA]);

export function MenuLateral({ rotuloNav, aoNavegar, topo }: Props) {
  const { sessao } = useSessao();
  const rotas = ROTAS.filter((r) => !NO_RODAPE.has(r.id) && rotaVisivel(r, sessao));
  const perfil = ROTAS.find((r) => r.id === ID_PERFIL);
  const ajuda = ROTAS.find((r) => r.id === ID_AJUDA && rotaVisivel(r, sessao));

  const aguardando = sessao.solicitacoes_aguardando;
  const item = (rota: Rota, conteudoIcone: ReactNode, classeExtra = '') => {
    const contador = rota.id === 'solicitacoes' && aguardando > 0;
    return (
      <NavLink
        to={destino(rota)}
        end={rota.caminho === ''}
        className={`nav__item${rota.id === 'onb' ? ' nav__item--onboarding' : ''}${classeExtra}`}
        onClick={aoNavegar}
        // RF-SO-07: o nome acessível diz a contagem por extenso (o número visível é decorativo).
        aria-label={contador ? `${rota.titulo}, ${aguardando} ${aguardando === 1 ? 'solicitação aguardando' : 'solicitações aguardando'} você` : undefined}
      >
        {conteudoIcone}
        <span className="nav__rotulo">{rota.titulo}</span>
        {contador ? (
          <span className="nav__contador" aria-hidden="true">
            {aguardando}
          </span>
        ) : null}
      </NavLink>
    );
  };

  return (
    <div className="menu-lateral vidro">
      {topo}
      <div className="marca">
        <span className="marca__selo" aria-hidden="true">
          APM
        </span>
        <span className="marca__textos">
          <span className="marca__produto">Minha APM</span>
          <span className="marca__subtitulo">área do associado</span>
        </span>
        <span className="visualmente-oculto">Associação Paulista de Medicina</span>
      </div>
      <nav className="menu-lateral__nav" aria-label={rotuloNav}>
        <ul className="nav">
          {rotas.map((rota) => (
            <li key={rota.id} className={rota.separada ? 'nav__separado' : undefined}>
              {item(rota, <Icon nome={rota.icone} tamanho={20} />)}
            </li>
          ))}
        </ul>
        {perfil || ajuda ? (
          <ul className="nav nav--rodape">
            {ajuda ? <li>{item(ajuda, <Icon nome={ajuda.icone} tamanho={20} />)}</li> : null}
            {perfil ? (
              <li>
                {item(
                  perfil,
                  <span className="avatar avatar--32" aria-hidden="true">
                    <ConteudoAvatar
                      iniciais={sessao.associado.iniciais}
                      fotoVersao={sessao.associado.foto_versao}
                      tamanho={32}
                    />
                  </span>,
                  ' nav__item--perfil',
                )}
              </li>
            ) : null}
          </ul>
        ) : null}
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
