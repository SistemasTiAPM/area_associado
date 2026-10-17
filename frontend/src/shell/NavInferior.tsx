import { NavLink } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { ORDEM_INFERIOR, ROTAS, destino, rotaVisivel } from '../rotas';
import { useSessao } from '../state/SessaoContext';

/** Bottom-nav mobile (RF-SH-06): 5 abas fixas, `aria-current` na ativa. */
export function NavInferior() {
  const { sessao } = useSessao();
  const abas = ORDEM_INFERIOR.map((id) => ROTAS.find((r) => r.id === id)).filter(
    (r): r is NonNullable<typeof r> => r !== undefined && rotaVisivel(r, sessao),
  );

  return (
    <nav className="nav-inferior" aria-label="Atalhos">
      {abas.map((rota) => (
        <NavLink key={rota.id} to={destino(rota)} end={rota.caminho === ''} className="nav-inferior__aba">
          <Icon nome={rota.icone} tamanho={21} />
          <span>{rota.rotuloInferior}</span>
        </NavLink>
      ))}
    </nav>
  );
}
