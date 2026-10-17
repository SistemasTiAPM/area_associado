import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { Icon } from '../components/Icon';

const ROTAS_COM_BUSCA = ['/beneficios', '/noticias'];
const DEBOUNCE_MS = 200;
const TERMO_MAX = 80;

/**
 * Busca global do header (RF-SH-04). O termo vive na URL (`?q=`), então a
 * recarga mantém o resultado. Fora de Benefícios/Notícias, digitar leva a
 * Benefícios. A filtragem em si chega com as telas (Fases 4 e 5).
 */
export function CampoBusca() {
  const { pathname } = useLocation();
  const navegar = useNavigate();
  const [parametros] = useSearchParams();
  const [termo, setTermo] = useState(parametros.get('q') ?? '');
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rotaComBusca = ROTAS_COM_BUSCA.includes(pathname);

  useEffect(() => {
    // Ao trocar de rota por outro caminho (menu, voltar), o campo reflete a URL.
    setTermo(parametros.get('q') ?? '');
  }, [parametros]);

  useEffect(
    () => () => {
      if (temporizador.current !== null) clearTimeout(temporizador.current);
    },
    [],
  );

  const aplicar = (valor: string) => {
    const q = valor.trim();
    const alvo = rotaComBusca ? pathname : '/beneficios';
    if (!q) {
      if (rotaComBusca) navegar(alvo, { replace: true });
      return;
    }
    navegar(`${alvo}?q=${encodeURIComponent(q)}`, { replace: rotaComBusca });
  };

  const aoDigitar = (valor: string) => {
    const limitado = valor.slice(0, TERMO_MAX);
    setTermo(limitado);
    if (temporizador.current !== null) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => aplicar(limitado), DEBOUNCE_MS);
  };

  return (
    <div className="busca" role="search">
      <label htmlFor="busca-global" className="visualmente-oculto">
        Buscar benefício, parceiro ou evento
      </label>
      <Icon nome="busca" tamanho={17} />
      <input
        id="busca-global"
        className="busca__campo"
        type="search"
        placeholder="Buscar benefício, parceiro, evento..."
        autoComplete="off"
        maxLength={TERMO_MAX}
        value={termo}
        onChange={(e) => aoDigitar(e.target.value)}
      />
      {termo ? (
        <button
          type="button"
          className="busca__limpar"
          aria-label="Limpar busca"
          onClick={() => {
            if (temporizador.current !== null) clearTimeout(temporizador.current);
            setTermo('');
            aplicar('');
          }}
        >
          <Icon nome="fechar" tamanho={14} />
        </button>
      ) : null}
    </div>
  );
}
