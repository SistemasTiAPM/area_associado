import type { ReactNode } from 'react';

interface Props {
  id: string;
  rotulo: string;
  erro?: string | undefined;
  dica?: string;
  children: (atributos: { id: string; 'aria-invalid': boolean; 'aria-describedby': string | undefined }) => ReactNode;
}

/** Rótulo + controle + erro/dica ligados por `aria-describedby` (RNF-10). */
export function Campo({ id, rotulo, erro, dica, children }: Props) {
  const idDica = dica ? `${id}-dica` : undefined;
  const idErro = erro ? `${id}-erro` : undefined;
  const descricao = [idDica, idErro].filter(Boolean).join(' ') || undefined;
  return (
    <div className={erro ? 'campo campo--erro' : 'campo'}>
      <label className="campo__rotulo" htmlFor={id}>
        {rotulo}
      </label>
      {children({ id, 'aria-invalid': Boolean(erro), 'aria-describedby': descricao })}
      {dica ? (
        <p className="campo__dica" id={idDica}>
          {dica}
        </p>
      ) : null}
      {erro ? (
        <p className="campo__erro" id={idErro}>
          {erro}
        </p>
      ) : null}
    </div>
  );
}
