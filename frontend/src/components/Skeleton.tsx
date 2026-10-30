export type VarianteSkeleton = 'linha' | 'texto' | 'card' | 'lista' | 'bloco' | 'circulo';

interface Props {
  variante?: VarianteSkeleton;
  /** `texto`: linhas; `lista`: itens. */
  quantidade?: number;
  /** Anunciado ao leitor de tela (`role=status`, `aria-busy`). */
  rotulo?: string;
  className?: string;
}

/**
 * Esqueleto de carregamento: formas decorativas (`aria-hidden`) dentro de uma
 * região `role=status` com `aria-busy`, para o leitor de tela saber que o
 * bloco ainda carrega. O brilho respeita `prefers-reduced-motion` (motion.css).
 */
export function Skeleton({ variante = 'bloco', quantidade = 3, rotulo = 'Carregando…', className }: Props) {
  const n = Math.max(1, Math.min(12, Math.trunc(quantidade)));
  const classes = ['skeleton', `skeleton--${variante}`, className ?? ''].filter(Boolean).join(' ');

  const formas = (() => {
    switch (variante) {
      case 'texto':
        return Array.from({ length: n }, (_, i) => (
          <span key={i} className={i === n - 1 ? 'skeleton__forma skeleton__forma--linha skeleton__forma--curta' : 'skeleton__forma skeleton__forma--linha'} />
        ));
      case 'lista':
        return Array.from({ length: n }, (_, i) => (
          <span key={i} className="skeleton__item">
            <span className="skeleton__forma skeleton__forma--circulo" />
            <span className="skeleton__forma skeleton__forma--linha" />
          </span>
        ));
      case 'card':
        return (
          <>
            <span className="skeleton__forma skeleton__forma--quadrado" />
            <span className="skeleton__forma skeleton__forma--linha" />
            <span className="skeleton__forma skeleton__forma--linha skeleton__forma--curta" />
          </>
        );
      case 'circulo':
        return <span className="skeleton__forma skeleton__forma--circulo" />;
      case 'linha':
        return <span className="skeleton__forma skeleton__forma--linha" />;
      case 'bloco':
        return <span className="skeleton__forma skeleton__forma--bloco" />;
    }
  })();

  return (
    <div className={classes} role="status" aria-busy="true" aria-live="polite">
      <span className="visualmente-oculto">{rotulo}</span>
      <span className="skeleton__formas" aria-hidden="true">
        {formas}
      </span>
    </div>
  );
}
