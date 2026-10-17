import { Icon } from '../components/Icon';
import { useSessao } from '../state/SessaoContext';

/**
 * Logout (RF-AU-07): navegação top-level por `<form method=post>`, não fetch —
 * o servidor responde 303 para o `/oauth/logout` do IdP, permitido pela
 * diretiva `form-action` da CSP. Texto "Sair" é proposta (LA-25).
 */
export function FormularioSair() {
  const { sessao } = useSessao();
  return (
    <form className="sair" method="post" action="/auth/logout">
      <input type="hidden" name="csrf" value={sessao.csrf} />
      <button type="submit" className="sair__botao">
        <Icon nome="sair" />
        <span>Sair</span>
      </button>
    </form>
  );
}
