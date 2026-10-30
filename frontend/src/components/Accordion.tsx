import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Icon } from './Icon';

export interface ItemAccordion {
  id: string;
  titulo: string;
  conteudo: ReactNode;
}

interface Props {
  itens: readonly ItemAccordion[];
  /** Ids abertos no início. */
  abertosIniciais?: readonly string[];
  /** Vários painéis abertos ao mesmo tempo (padrão: um por vez). */
  permitirMultiplos?: boolean;
  /** Nível do cabeçalho de cada item dentro da hierarquia da página. */
  nivel?: 2 | 3 | 4;
  aoAlternar?: (id: string, aberto: boolean) => void;
}

/**
 * Accordion (APG): cabeçalho é `button` com `aria-expanded`/`aria-controls`,
 * painel é `role=region` rotulado pelo botão; setas, Home e End movem entre
 * os cabeçalhos. Para FAQ, regras e "como funciona" (P04, P14).
 */
export function Accordion({ itens, abertosIniciais = [], permitirMultiplos = false, nivel = 3, aoAlternar }: Props) {
  const prefixo = useId();
  const [abertos, setAbertos] = useState<ReadonlySet<string>>(() => new Set(abertosIniciais));
  const botoes = useRef<(HTMLButtonElement | null)[]>([]);
  const Cabecalho = `h${nivel}` as const;

  const alternar = (id: string) => {
    const estavaAberto = abertos.has(id);
    setAbertos((atual) => {
      const proximo = new Set(permitirMultiplos ? atual : []);
      if (estavaAberto) proximo.delete(id);
      else proximo.add(id);
      return proximo;
    });
    aoAlternar?.(id, !estavaAberto);
  };

  const aoTeclar = (evento: KeyboardEvent<HTMLButtonElement>, indice: number) => {
    const total = itens.length;
    let destino: number | null = null;
    if (evento.key === 'ArrowDown') destino = (indice + 1) % total;
    else if (evento.key === 'ArrowUp') destino = (indice - 1 + total) % total;
    else if (evento.key === 'Home') destino = 0;
    else if (evento.key === 'End') destino = total - 1;
    if (destino === null) return;
    evento.preventDefault();
    botoes.current[destino]?.focus();
  };

  return (
    <div className="accordion">
      {itens.map((item, indice) => {
        const aberto = abertos.has(item.id);
        const idBotao = `${prefixo}-${item.id}-botao`;
        const idPainel = `${prefixo}-${item.id}-painel`;
        return (
          <div key={item.id} className={aberto ? 'accordion__item accordion__item--aberto' : 'accordion__item'}>
            <Cabecalho className="accordion__cabecalho">
              <button
                ref={(el) => {
                  botoes.current[indice] = el;
                }}
                type="button"
                id={idBotao}
                className="accordion__botao"
                aria-expanded={aberto}
                aria-controls={idPainel}
                onClick={() => alternar(item.id)}
                onKeyDown={(e) => aoTeclar(e, indice)}
              >
                <span className="accordion__titulo">{item.titulo}</span>
                <span className="accordion__seta" aria-hidden="true">
                  <Icon nome="chevron" tamanho={18} />
                </span>
              </button>
            </Cabecalho>
            <div id={idPainel} role="region" aria-labelledby={idBotao} className="accordion__painel" hidden={!aberto}>
              <div className="accordion__conteudo">{item.conteudo}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
