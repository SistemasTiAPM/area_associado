import type { ReactNode } from 'react';

export interface Opcao<V extends string = string> {
  valor: V;
  rotulo: string;
  descricao?: string;
  desabilitada?: boolean;
}

interface PropsBase<V extends string> {
  /** Base dos ids e `name` dos inputs. */
  nome: string;
  legenda: ReactNode;
  opcoes: readonly Opcao<V>[];
  dica?: string | undefined;
  erro?: string | undefined;
  /** Legenda só para leitor de tela (quando a tela já tem o título). */
  legendaOculta?: boolean;
  className?: string;
}

interface PropsRadio<V extends string> extends PropsBase<V> {
  valor: V | null;
  aoMudar: (valor: V) => void;
}

interface PropsCheckbox<V extends string> extends PropsBase<V> {
  valores: readonly V[];
  aoMudar: (valores: V[]) => void;
}

function Envoltorio<V extends string>({
  nome,
  legenda,
  dica,
  erro,
  legendaOculta,
  className,
  tipo,
  children,
}: PropsBase<V> & { tipo: 'radio' | 'checkbox'; children: ReactNode }) {
  const idDica = dica ? `${nome}-dica` : undefined;
  const idErro = erro ? `${nome}-erro` : undefined;
  const descricao = [idDica, idErro].filter(Boolean).join(' ') || undefined;
  const classes = ['grupo-opcoes', `grupo-opcoes--${tipo}`, erro ? 'grupo-opcoes--erro' : '', className ?? ''].filter(Boolean).join(' ');
  return (
    <fieldset className={classes} aria-describedby={descricao} aria-invalid={erro ? true : undefined}>
      <legend className={legendaOculta ? 'visualmente-oculto' : 'grupo-opcoes__legenda'}>{legenda}</legend>
      {dica ? (
        <p className="campo__dica" id={idDica}>
          {dica}
        </p>
      ) : null}
      <div className="grupo-opcoes__lista">{children}</div>
      {erro ? (
        <p className="campo__erro" id={idErro} role="alert">
          {erro}
        </p>
      ) : null}
    </fieldset>
  );
}

function Item<V extends string>({
  nome,
  tipo,
  opcao,
  marcada,
  aoMudar,
}: {
  nome: string;
  tipo: 'radio' | 'checkbox';
  opcao: Opcao<V>;
  marcada: boolean;
  aoMudar: () => void;
}) {
  const id = `${nome}-${opcao.valor}`;
  const idDescricao = opcao.descricao ? `${id}-descricao` : undefined;
  return (
    <div className={marcada ? 'opcao opcao--marcada' : 'opcao'}>
      <input
        id={id}
        className="opcao__entrada"
        type={tipo}
        name={nome}
        value={opcao.valor}
        checked={marcada}
        disabled={opcao.desabilitada}
        aria-describedby={idDescricao}
        onChange={aoMudar}
      />
      <label className="opcao__rotulo" htmlFor={id}>
        <span className="opcao__texto">{opcao.rotulo}</span>
        {opcao.descricao ? (
          <span className="opcao__descricao" id={idDescricao}>
            {opcao.descricao}
          </span>
        ) : null}
      </label>
    </div>
  );
}

/**
 * Grupo de opção única (`fieldset` + `legend` + inputs nativos `radio`; setas
 * do próprio navegador). Alvo de 44 px por item; dica e erro ligados por
 * `aria-describedby`. Para atuação (P13) e motivos de cancelamento (P14).
 */
export function RadioGroup<V extends string>({ valor, aoMudar, ...resto }: PropsRadio<V>) {
  return (
    <Envoltorio {...resto} tipo="radio">
      {resto.opcoes.map((opcao) => (
        <Item key={opcao.valor} nome={resto.nome} tipo="radio" opcao={opcao} marcada={valor === opcao.valor} aoMudar={() => aoMudar(opcao.valor)} />
      ))}
    </Envoltorio>
  );
}

/** Grupo de múltipla escolha (inputs nativos `checkbox`); devolve a lista na ordem das opções. */
export function CheckboxGroup<V extends string>({ valores, aoMudar, ...resto }: PropsCheckbox<V>) {
  const alternar = (valor: V) => {
    const conjunto = new Set(valores);
    if (conjunto.has(valor)) conjunto.delete(valor);
    else conjunto.add(valor);
    aoMudar(resto.opcoes.map((o) => o.valor).filter((v) => conjunto.has(v)));
  };
  return (
    <Envoltorio {...resto} tipo="checkbox">
      {resto.opcoes.map((opcao) => (
        <Item key={opcao.valor} nome={resto.nome} tipo="checkbox" opcao={opcao} marcada={valores.includes(opcao.valor)} aoMudar={() => alternar(opcao.valor)} />
      ))}
    </Envoltorio>
  );
}
