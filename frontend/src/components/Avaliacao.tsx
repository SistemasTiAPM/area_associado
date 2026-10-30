import { useId } from 'react';

interface Props {
  /** `name` dos inputs (único na página). */
  nome: string;
  valor: number | null;
  aoMudar: (nota: number) => void;
  legenda?: string;
  erro?: string | undefined;
  desabilitado?: boolean;
  max?: number;
}

/**
 * Nota de 0 a 10 (RF-SO-10; spec v2 P05): `fieldset` com `role=radiogroup` e
 * 11 rádios nativos (setas do navegador), cada rótulo com alvo ≥ 44 × 44 px
 * (spec v2 §14). As pontas da escala têm texto, não só número.
 */
export function Avaliacao({
  nome,
  valor,
  aoMudar,
  legenda = 'Que nota você dá para este atendimento?',
  erro,
  desabilitado = false,
  max = 10,
}: Props) {
  const idLegenda = useId();
  const idEscala = useId();
  const idErro = useId();
  const notas = Array.from({ length: max + 1 }, (_, n) => n);
  const descricao = [idEscala, erro ? idErro : ''].filter(Boolean).join(' ');
  return (
    <fieldset
      className={erro ? 'avaliacao avaliacao--erro' : 'avaliacao'}
      role="radiogroup"
      aria-labelledby={idLegenda}
      aria-describedby={descricao}
      aria-invalid={erro ? true : undefined}
      disabled={desabilitado}
    >
      <legend className="grupo-opcoes__legenda" id={idLegenda}>
        {legenda}
      </legend>
      <p className="campo__dica" id={idEscala}>
        0 é nada satisfeito e {max} é muito satisfeito.
      </p>
      <div className="avaliacao__escala">
        {notas.map((n) => {
          const id = `${nome}-${n}`;
          return (
            <div key={n} className="avaliacao__item">
              <input
                id={id}
                className="avaliacao__entrada"
                type="radio"
                name={nome}
                value={n}
                checked={valor === n}
                onChange={() => aoMudar(n)}
              />
              <label className="avaliacao__nota" htmlFor={id}>
                {n}
              </label>
            </div>
          );
        })}
      </div>
      {erro ? (
        <p className="campo__erro" id={idErro} role="alert">
          {erro}
        </p>
      ) : null}
    </fieldset>
  );
}
