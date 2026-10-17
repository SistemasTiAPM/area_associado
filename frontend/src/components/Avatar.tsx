import { urlFoto } from '../api/perfil';

interface Props {
  iniciais: string;
  fotoVersao: string | null;
  tamanho: 40 | 96;
}

/**
 * Foto do associado (miniatura 128×128 servida pela própria origem, versionada
 * pelo ETag) ou as iniciais. Decorativa: o rótulo acessível fica no controle
 * que a envolve.
 */
export function ConteudoAvatar({ iniciais, fotoVersao, tamanho }: Props) {
  if (fotoVersao) {
    return <img className="avatar__foto" src={urlFoto(fotoVersao)} alt="" width={tamanho} height={tamanho} />;
  }
  return <>{iniciais}</>;
}
