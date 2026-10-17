import { Link } from 'react-router-dom';
import { EstadoVazio } from '../components/EstadoVazio';
import { Icon } from '../components/Icon';

/** Rota desconhecida ou desligada por flag (RF-SH-01, RF-SH-11). */
export function NaoEncontrada() {
  return (
    <EstadoVazio titulo="Não encontramos esta página">
      <p>O endereço pode ter mudado ou esta seção não está disponível para você.</p>
      <p>
        <Link to="/" className="link-texto">
          <Icon nome="voltar" tamanho={14} />
          voltar para o início
        </Link>
      </p>
    </EstadoVazio>
  );
}
