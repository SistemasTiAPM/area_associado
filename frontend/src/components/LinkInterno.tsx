import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { destinoSeguro } from '../lib/navegacao';

interface Props {
  /** Caminho relativo ao basename `/area` (ex.: `/solicitacoes/{id}`), validado por `destinoSeguro`. */
  para: string;
  children: ReactNode;
  className?: string;
  /** Rótulo acessível quando o texto visível não basta. */
  rotulo?: string;
  aoClicar?: () => void;
}

/**
 * Link interno com destino montado em tempo de execução (TI-10 / P-40). Único
 * ponto, fora do shell, autorizado a passar um valor não literal em `<Link to>`
 * (o lint proíbe no resto do código). Destino fora das rotas conhecidas não
 * vira link: renderiza só o conteúdo, como `LinkExterno`.
 */
export function LinkInterno({ para, children, className, rotulo, aoClicar }: Props) {
  const seguro = destinoSeguro(para);
  if (seguro === null) return <span className={className}>{children}</span>;
  return (
    <Link to={seguro} className={className} aria-label={rotulo} onClick={aoClicar}>
      {children}
    </Link>
  );
}
