import { useEffect, useState } from 'react';
import { Icon } from './Icon';

export type Proporcao = '1/1' | '4/3' | '3/2' | '16/9';

interface Props {
  src: string | null | undefined;
  /** Texto alternativo; vazio = decorativa. */
  alt: string;
  /** Hosts ou origens permitidos (formato de `CSP_IMG_HOSTS`: `https://www.apm.org.br`, ou só o host). */
  hostsPermitidos: readonly string[];
  /** Caminhos relativos da própria origem (`/static/...`, `/api/v1/.../foto`) passam (CSP `img-src 'self'`). */
  permitirMesmaOrigem?: boolean;
  proporcao?: Proporcao;
  className?: string;
}

function hostDe(entrada: string): string | null {
  const limpa = entrada.trim().toLowerCase();
  if (!limpa) return null;
  if (limpa.includes('://')) {
    try {
      const url = new URL(limpa);
      return url.protocol === 'https:' ? url.hostname : null;
    } catch (falha) {
      if (falha instanceof TypeError) return null;
      throw falha;
    }
  }
  return /^[a-z0-9.-]+$/.test(limpa) ? limpa : null;
}

/**
 * URL de imagem que a CSP aceitaria: caminho relativo da própria origem (sem
 * `//`), ou `https:` com host na allowlist. Qualquer outra coisa (`http:`,
 * `data:`, `javascript:`, host fora da lista, credenciais) devolve `null`.
 */
export function urlImagemSegura(bruta: string | null | undefined, hosts: readonly string[], permitirMesmaOrigem = true): string | null {
  if (typeof bruta !== 'string') return null;
  const src = bruta.trim();
  if (!src) return null;
  if (src.startsWith('/')) {
    return permitirMesmaOrigem && !src.startsWith('//') && !/[\s\\]/.test(src) ? src : null;
  }
  let url: URL;
  try {
    url = new URL(src);
  } catch (falha) {
    if (falha instanceof TypeError) return null;
    throw falha;
  }
  if (url.protocol !== 'https:' || url.username || url.password) return null;
  const permitidos = new Set(hosts.map(hostDe).filter((h): h is string => h !== null));
  return permitidos.has(url.hostname.toLowerCase()) ? url.toString() : null;
}

/**
 * Imagem de terceiro (logo de parceiro, capa de notícia/evento) só quando o
 * host está na lista permitida — a mesma que o servidor coloca em `img-src`
 * (via `/sessao`). Caso contrário, ou se a imagem falhar, mostra um
 * placeholder do mesmo tamanho (proporção fixa evita salto de layout, CLS).
 * `loading=lazy`, `decoding=async`, `referrerpolicy=no-referrer`.
 */
export function ImagemSegura({ src, alt, hostsPermitidos, permitirMesmaOrigem = true, proporcao = '16/9', className }: Props) {
  const segura = urlImagemSegura(src, hostsPermitidos, permitirMesmaOrigem);
  const [falhou, setFalhou] = useState(false);
  useEffect(() => setFalhou(false), [segura]);

  const decorativa = alt.trim() === '';
  const classes = ['imagem-segura', `imagem-segura--${proporcao.replace('/', '-')}`, className ?? ''].filter(Boolean).join(' ');

  if (segura === null || falhou) {
    return (
      <span
        className={`${classes} imagem-segura--placeholder`}
        role={decorativa ? undefined : 'img'}
        aria-label={decorativa ? undefined : alt}
        aria-hidden={decorativa ? true : undefined}
        data-motivo={segura === null ? 'host_nao_permitido' : 'falha_carregamento'}
      >
        <Icon nome="imagem" tamanho={28} />
      </span>
    );
  }
  return (
    <span className={classes}>
      <img
        className="imagem-segura__img"
        src={segura}
        alt={alt}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFalhou(true)}
      />
    </span>
  );
}
