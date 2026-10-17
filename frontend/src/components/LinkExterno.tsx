import type { ReactNode } from 'react';
import { urlExternaSegura } from '../lib/links';

interface Props {
  href: string;
  children: ReactNode;
  className?: string;
  rotulo?: string;
  aoClicar?: () => void;
}

/**
 * Único ponto do código autorizado a abrir link em nova aba (RF-SH-12; lint
 * proíbe `target` em `<a>` fora daqui). URL fora da allowlist ou não-https
 * não vira link: renderiza só o conteúdo, sem destino.
 */
export function LinkExterno({ href, children, className, rotulo, aoClicar }: Props) {
  const seguro = urlExternaSegura(href);
  if (seguro === null) {
    return <span className={className}>{children}</span>;
  }
  return (
    // eslint-disable-next-line no-restricted-syntax -- este é o componente seguro
    <a href={seguro} target="_blank" rel="noopener noreferrer" className={className} aria-label={rotulo} onClick={aoClicar}>
      {children}
      <span className="visualmente-oculto"> (abre em nova aba)</span>
    </a>
  );
}
