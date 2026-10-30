import { useEffect, useRef } from 'react';

interface Props {
  valor: number;
  max?: number;
  /** Nome do que está sendo medido (ex.: "Trilha de ativação"). */
  rotulo: string;
  /** Texto visível ao lado; padrão "{valor} de {max}". `null` esconde. */
  texto?: string | null;
  className?: string;
}

export function fracaoProgresso(valor: number, max: number): number {
  if (!Number.isFinite(valor) || !Number.isFinite(max) || max <= 0) return 0;
  return Math.min(1, Math.max(0, valor / max));
}

/**
 * Barra de progresso (`role=progressbar` com valuenow/min/max). A largura do
 * preenchimento vem da custom property `--progresso` definida por CSSOM —
 * nunca `style` inline (CSP `style-src 'self'`, ADR-0013). Para a trilha de
 * ativação e o perfil (P12, P13).
 */
export function BarraProgresso({ valor, max = 100, rotulo, texto, className }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const fracao = fracaoProgresso(valor, max);
  const valorLimitado = Math.round(fracao * max);

  useEffect(() => {
    ref.current?.style.setProperty('--progresso', fracao.toFixed(4));
  }, [fracao]);

  const textoVisivel = texto === undefined ? `${valorLimitado} de ${max}` : texto;
  return (
    <div className={className ? `barra-progresso ${className}` : 'barra-progresso'}>
      <div
        ref={ref}
        className="barra-progresso__trilho"
        role="progressbar"
        aria-label={rotulo}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={valorLimitado}
        aria-valuetext={textoVisivel ?? undefined}
      >
        <div className="barra-progresso__preenchimento" />
      </div>
      {textoVisivel ? <span className="barra-progresso__texto">{textoVisivel}</span> : null}
    </div>
  );
}
