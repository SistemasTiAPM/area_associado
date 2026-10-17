import { EstadoVazio } from '../components/EstadoVazio';

/**
 * Página ainda não implementada (fases 2 a 8). Só existe na fase de
 * construção, sem acesso público; cada fase substitui a sua.
 */
export function EmConstrucao({ titulo }: { titulo: string }) {
  return (
    <EstadoVazio titulo={titulo}>
      Esta seção está em construção e chega nas próximas entregas da Minha APM.
    </EstadoVazio>
  );
}
