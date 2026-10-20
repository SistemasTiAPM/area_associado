import { useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { registrarUso } from '../lib/analytics';
import { TITULO_NAO_ENCONTRADA, rotaDoCaminho, rotaVisivel } from '../rotas';
import { useSessao } from '../state/SessaoContext';
import { BotaoWhatsapp } from './BotaoWhatsapp';
import { Cabecalho } from './Cabecalho';
import { Drawer } from './Drawer';
import { MenuLateral } from './MenuLateral';
import { NavInferior } from './NavInferior';

/**
 * Shell fixo (spec "Estrutura"; RF-SH-01..13). Na troca de rota: rola ao topo,
 * atualiza o <title>, move o foco para o h1 (leitor de tela anuncia a página)
 * e registra `pagina_ver`. O conteúdo é remontado por rota (`key`) para a
 * animação de entrada (RF-SH-10).
 */
export function AppShell() {
  const { sessao } = useSessao();
  const { pathname } = useLocation();
  const [drawerAberto, setDrawerAberto] = useState(false);
  const refTitulo = useRef<HTMLHeadingElement>(null);
  const primeiraRenderizacao = useRef(true);

  const rota = rotaDoCaminho(pathname);
  const titulo = rota && rotaVisivel(rota, sessao) ? rota.titulo : TITULO_NAO_ENCONTRADA;
  const fecharDrawer = useCallback(() => setDrawerAberto(false), []);

  useEffect(() => {
    document.title = `${titulo} · Minha APM`;
  }, [titulo]);

  useEffect(() => {
    const caminhoCompleto = `/area${pathname === '/' ? '' : pathname}`.replace(/\/+$/, '') || '/area';
    registrarUso({ acao: 'pagina_ver', entidade: 'rota', entidade_id: caminhoCompleto.slice(0, 64) });
    if (primeiraRenderizacao.current) {
      primeiraRenderizacao.current = false;
      return;
    }
    window.scrollTo(0, 0);
    refTitulo.current?.focus();
  }, [pathname]);

  return (
    <>
      <a className="pular-conteudo" href="#conteudo">
        Pular para o conteúdo
      </a>
      {sessao.stub ? (
        <div className="faixa-stub" role="status">
          Ambiente de construção: login sem o Login APM (AUTH_MODE=stub). Dados ilustrativos.
        </div>
      ) : sessao.dados_demonstracao ? (
        <div className="faixa-stub" role="status">
          Ambiente em construção: celular, endereço e foto são de demonstração e não vão para o seu cadastro na APM.
        </div>
      ) : null}
      <div className="shell">
        <aside className="sidebar">
          <MenuLateral rotuloNav="Menu principal" />
        </aside>
        <div className="principal">
          <Cabecalho
            ref={refTitulo}
            titulo={titulo}
            drawerAberto={drawerAberto}
            aoAbrirMenu={() => setDrawerAberto(true)}
          />
          <main id="conteudo" key={pathname} className="conteudo pagina-entrada" tabIndex={-1}>
            <Outlet />
          </main>
        </div>
      </div>
      <Drawer aberto={drawerAberto} aoFechar={fecharDrawer} />
      <NavInferior />
      <BotaoWhatsapp />
    </>
  );
}
