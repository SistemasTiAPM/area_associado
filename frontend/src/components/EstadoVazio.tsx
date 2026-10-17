import type { ReactNode } from 'react';

export function EstadoVazio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <section className="cartao estado-vazio">
      <h2 className="estado-vazio__titulo">{titulo}</h2>
      {children ? <div className="estado-vazio__texto">{children}</div> : null}
    </section>
  );
}
