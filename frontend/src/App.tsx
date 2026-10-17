import { Route, Routes } from 'react-router-dom';
import { EmConstrucao } from './pages/EmConstrucao';
import { Inicio } from './pages/Inicio';
import { NaoEncontrada } from './pages/NaoEncontrada';
import { ROTAS, rotaVisivel, type Rota } from './rotas';
import { AppShell } from './shell/AppShell';
import { SessaoProvider, useSessao } from './state/SessaoContext';
import { ToastProvider } from './state/ToastContext';

/** Rota sob flag desligada ou de outra persona vira "não encontrada" (RF-SH-11). */
function Guarda({ rota }: { rota: Rota }) {
  const { sessao } = useSessao();
  if (!rotaVisivel(rota, sessao)) return <NaoEncontrada />;
  return <EmConstrucao titulo={rota.titulo} />;
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
