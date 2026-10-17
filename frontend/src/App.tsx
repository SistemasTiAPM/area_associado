import type { ComponentType } from 'react';
import { Route, Routes } from 'react-router-dom';
import { PaginaCarteirinha } from './pages/Carteirinha';
import { EmConstrucao } from './pages/EmConstrucao';
import { Inicio } from './pages/Inicio';
import { NaoEncontrada } from './pages/NaoEncontrada';
import { PaginaPerfil } from './pages/Perfil';
import { ROTAS, rotaVisivel, type Rota } from './rotas';
import { AppShell } from './shell/AppShell';
import { SessaoProvider, useSessao } from './state/SessaoContext';
import { ToastProvider } from './state/ToastContext';

/** Telas já implementadas; as demais seguem "em construção" até a sua fase. */
const PAGINAS: Record<string, ComponentType> = {
  perfil: PaginaPerfil,
  card: PaginaCarteirinha,
};

/** Rota sob flag desligada ou de outra persona vira "não encontrada" (RF-SH-11). */
function Guarda({ rota }: { rota: Rota }) {
  const { sessao } = useSessao();
  if (!rotaVisivel(rota, sessao)) return <NaoEncontrada />;
  const Pagina = PAGINAS[rota.id];
  return Pagina ? <Pagina /> : <EmConstrucao titulo={rota.titulo} />;
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
            <Route path="*" element={<NaoEncontrada />} />
          </Route>
        </Routes>
      </ToastProvider>
    </SessaoProvider>
  );
}
