import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { ConteudoAvatar } from '../components/Avatar';
import { Icon } from '../components/Icon';
import { useSessao } from '../state/SessaoContext';
import { CampoBusca } from './CampoBusca';
import { ID_DRAWER } from './Drawer';

interface Props {
  titulo: string;
  /** Linha editorial da rota (rotas.ts); ausente em "página não encontrada". */
  chamada?: string | undefined;
  /** Na Início, o sobretítulo é a data de hoje (como no mockup). */
  inicio: boolean;
  drawerAberto: boolean;
  aoAbrirMenu: () => void;
}

const FORMATO_DATA = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });

/**
 * Cabeçalho do mockup (ADR-0017): bloco em degradê navy que se dissolve sobre o
 * conteúdo, sobretítulo + título + chamada, busca e chip do perfil. O h1 é
 * sempre o título da rota e recebe o foco na troca de rota (RF-SH-03).
 * Sem sino de notificações: não há fonte de dados (regra 19).
 */
export const Cabecalho = forwardRef<HTMLHeadingElement, Props>(function Cabecalho(
  { titulo, chamada, inicio, drawerAberto, aoAbrirMenu },
  refTitulo,
) {
  const { sessao } = useSessao();
  const { nome_exibicao, iniciais, foto_versao, tipo } = sessao.associado;
  const sobretitulo = inicio ? FORMATO_DATA.format(new Date()) : 'Minha APM';

  return (
    <header className="topo">
      <div className="topo__interno">
        <button
          type="button"
          className="topo__menu vidro--escuro"
          aria-label="Abrir menu"
          aria-expanded={drawerAberto}
          aria-controls={ID_DRAWER}
          onClick={aoAbrirMenu}
        >
          <Icon nome="menu" tamanho={20} />
        </button>
        <div className="topo__titulos">
          <p className="topo__sobretitulo">{sobretitulo}</p>
          <h1 ref={refTitulo} className="topo__titulo" tabIndex={-1}>
            {titulo}
          </h1>
          {chamada ? <p className="topo__chamada">{chamada}</p> : null}
        </div>
        <div className="topo__acoes">
          <CampoBusca />
          {sessao.flags.mensalidade_zero ? (
            <span className="pill-status vidro--escuro">
              <span className="pill-status__ponto" aria-hidden="true" />
              Mensalidade Zero ativa
            </span>
          ) : null}
          <Link to="/perfil" className="topo__perfil vidro--escuro">
            <span className="avatar avatar--40">
              <ConteudoAvatar iniciais={iniciais} fotoVersao={foto_versao} tamanho={40} />
            </span>
            <span className="topo__perfil-textos">
              <b className="topo__perfil-nome">{nome_exibicao || iniciais}</b>
              {tipo ? <span className="topo__perfil-tipo">{tipo}</span> : null}
            </span>
            <span className="visualmente-oculto">, abrir meu perfil</span>
          </Link>
        </div>
      </div>
    </header>
  );
});
