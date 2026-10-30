import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';

export interface Aba {
  id: string;
  rotulo: string;
  conteudo: ReactNode;
}

interface Props {
  abas: readonly Aba[];
  /** Nome do conjunto para o leitor de tela (ex.: "Período do extrato"). */
  rotulo: string;
  /** Aba inicial (não controlado). */
  abaInicial?: string;
  /** Aba ativa (controlado); use com `aoMudar`. */
  ativa?: string | undefined;
  aoMudar?: (id: string) => void;
}

/**
 * Tabs (APG, ativação automática): `tablist` com `tab`s em tabindex itinerante
 * (só a ativa entra na ordem de Tab), setas Esquerda/Direita, Home e End;
 * um único `tabpanel` montado por vez, focável. Para o seletor de período
 * (P06, P08) e agrupamentos de catálogo (P03).
 */
export function Tabs({ abas, rotulo, abaInicial, ativa, aoMudar }: Props) {
  const prefixo = useId();
  const [interna, setInterna] = useState<string>(() => abaInicial ?? abas[0]?.id ?? '');
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const atualId = ativa ?? interna;
  const atual = abas.find((a) => a.id === atualId) ?? abas[0];

  const selecionar = (id: string) => {
    if (ativa === undefined) setInterna(id);
    aoMudar?.(id);
  };

  const aoTeclar = (evento: KeyboardEvent<HTMLButtonElement>, indice: number) => {
    const total = abas.length;
    let destino: number | null = null;
    if (evento.key === 'ArrowRight') destino = (indice + 1) % total;
    else if (evento.key === 'ArrowLeft') destino = (indice - 1 + total) % total;
    else if (evento.key === 'Home') destino = 0;
    else if (evento.key === 'End') destino = total - 1;
    if (destino === null) return;
    evento.preventDefault();
    const aba = abas[destino];
    if (!aba) return;
    refs.current[destino]?.focus();
    selecionar(aba.id);
  };

  if (!atual) return null;
  return (
    <div className="tabs">
      <div className="tabs__lista" role="tablist" aria-label={rotulo}>
        {abas.map((aba, indice) => {
          const selecionada = aba.id === atual.id;
          return (
            <button
              key={aba.id}
              ref={(el) => {
                refs.current[indice] = el;
              }}
              type="button"
              role="tab"
              id={`${prefixo}-${aba.id}-tab`}
              className={selecionada ? 'tabs__aba tabs__aba--ativa' : 'tabs__aba'}
              aria-selected={selecionada}
              aria-controls={`${prefixo}-${aba.id}-painel`}
              tabIndex={selecionada ? 0 : -1}
              onClick={() => selecionar(aba.id)}
              onKeyDown={(e) => aoTeclar(e, indice)}
            >
              {aba.rotulo}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${prefixo}-${atual.id}-painel`}
        aria-labelledby={`${prefixo}-${atual.id}-tab`}
        className="tabs__painel"
        tabIndex={0}
      >
        {atual.conteudo}
      </div>
    </div>
  );
}
