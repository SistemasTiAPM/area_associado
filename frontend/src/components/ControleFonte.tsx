import type { TamanhoFonte } from '../api/tipos';

interface Props {
  valor: TamanhoFonte;
  opcoes: readonly { valor: string; rotulo: string }[];
  aoMudar: (valor: TamanhoFonte) => void;
  ocupado?: boolean;
}

function ehTamanho(valor: string): valor is TamanhoFonte {
  return valor === 'padrao' || valor === 'grande' || valor === 'maior';
}

/**
 * Tamanho do texto em três passos (TI-64): botões de opção única (`aria-pressed`),
 * cada um com a letra na escala que aplica. Quem aplica é a sessão (`data-fonte` no
 * `<html>`); este componente só escolhe. O tamanho de cada amostra vem de classe
 * CSS, nunca de estilo inline (ADR-0013).
 */
export function ControleFonte({ valor, opcoes, aoMudar, ocupado = false }: Props) {
  return (
    <div className="controle-fonte" role="group" aria-label="Tamanho do texto">
      {opcoes.filter((o) => ehTamanho(o.valor)).map((opcao) => {
        const tamanho = opcao.valor as TamanhoFonte;
        const ativo = tamanho === valor;
        return (
          <button
            key={tamanho}
            type="button"
            className={`controle-fonte__opcao${ativo ? ' controle-fonte__opcao--ativa' : ''}`}
            aria-pressed={ativo}
            disabled={ocupado}
            onClick={() => {
              if (!ativo) aoMudar(tamanho);
            }}
          >
            <span className={`controle-fonte__amostra controle-fonte__amostra--${tamanho}`} aria-hidden="true">
              A
            </span>
            {opcao.rotulo}
          </button>
        );
      })}
    </div>
  );
}
