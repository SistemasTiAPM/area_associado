import { Suspense, lazy, type ComponentType } from 'react';
import { Route, Routes, useParams } from 'react-router';
import { LimiteCargaPagina } from './components/LimiteCargaPagina';
import { Skeleton } from './components/Skeleton';
import { PaginaCarteirinha } from './pages/Carteirinha';
import { EmConstrucao } from './pages/EmConstrucao';
import { Inicio } from './pages/Inicio';
import { NaoEncontrada } from './pages/NaoEncontrada';
import { PaginaPerfil } from './pages/Perfil';
import { ROTAS, recursoPronto, rotaDoCaminho, rotaVisivel, type Rota } from './rotas';
import { AppShell } from './shell/AppShell';
import { SessaoProvider, useSessao } from './state/SessaoContext';
import { ToastProvider } from './state/ToastContext';

/** Props que toda página recebe; `parametro` só existe em sub-rota (`/beneficios/{slug}`). */
export interface PropsPagina {
  parametro?: string;
}

// Telas da Onda 2 em pedaços próprios (orçamento de 250 kB do bundle inicial, vite.config.ts).
const PaginaSolicitacoes = lazy(() => import('./pages/Solicitacoes').then((m) => ({ default: m.PaginaSolicitacoes })));
const PaginaAjuda = lazy(() => import('./pages/Ajuda').then((m) => ({ default: m.PaginaAjuda })));

/** Telas já implementadas; as demais seguem "em construção" até a sua fase. */
const PAGINAS: Record<string, ComponentType<PropsPagina>> = {
  perfil: PaginaPerfil,
  card: PaginaCarteirinha,
  solicitacoes: PaginaSolicitacoes,
  ajuda: PaginaAjuda,
};

/**
 * Rota sob flag desligada ou de outra persona vira "não encontrada" (RF-SH-11);
 * recurso ainda sem migração no servidor (`sessao.recursos`) vira "em construção",
 * sem montar a página (nenhuma chamada à API dela).
 */
function Guarda({ rota }: { rota: Rota }) {
  const { sessao } = useSessao();
  const { parametro } = useParams<'parametro'>();
  if (!rotaVisivel(rota, sessao)) return <NaoEncontrada />;
  // O shell já validou o formato do segmento (resolverCaminho); sem rota resolvida, não encontrada.
  if (parametro !== undefined && rotaDoCaminho(`/${rota.caminho}/${parametro}`) !== rota) return <NaoEncontrada />;
  const Pagina = recursoPronto(rota, sessao) ? PAGINAS[rota.id] : undefined;
  if (!Pagina) return <EmConstrucao titulo={rota.titulo} parametro={parametro} />;
  return (
    <LimiteCargaPagina>
      <Suspense fallback={<Skeleton variante="texto" quantidade={4} rotulo="Carregando a página…" />}>
        {parametro === undefined ? <Pagina /> : <Pagina parametro={parametro} />}
      </Suspense>
    </LimiteCargaPagina>
  );
}

export function App() {
  return (
    <SessaoProvider>
      <ToastProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Inicio />} />
            {ROTAS.filter((r) => r.caminho !== '').map((rota) => (
              <Route key={rota.id} path={rota.caminho} element={<Guarda rota={rota} />} />
            ))}
            {ROTAS.filter((r) => r.subRota !== undefined).map((rota) => (
              <Route key={`${rota.id}-sub`} path={`${rota.caminho}/:parametro`} element={<Guarda rota={rota} />} />
            ))}
            <Route path="*" element={<NaoEncontrada />} />
          </Route>
        </Routes>
      </ToastProvider>
    </SessaoProvider>
  );
}
