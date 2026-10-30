import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Icon } from './Icon';

export interface OpcaoCombobox {
  id: string;
  rotulo: string;
  /** Tipo/grupo exibido ao lado (ex.: "Benefício", "Evento", "Notícia"). */
  tipo?: string;
}

interface Props {
  id: string;
  rotulo: string;
  valor: string;
  aoMudar: (texto: string) => void;
  opcoes: readonly OpcaoCombobox[];
  aoEscolher: (opcao: OpcaoCombobox) => void;
  placeholder?: string;
  /** Texto quando há busca e nenhuma sugestão (voz §3.3: diz o que fazer). */
  textoSemResultado?: string;
  carregando?: boolean;
  /** Mínimo de caracteres para abrir a lista. */
  minimo?: number;
  /** Rótulo visível ou só para leitor de tela. */
  rotuloOculto?: boolean;
  className?: string;
}

/**
 * Combobox com sugestões (APG, autocomplete=list): `role=combobox` no input,
 * `aria-expanded`, `aria-controls` → `role=listbox` com `role=option`,
 * `aria-activedescendant` no item realçado. Setas movem, Enter escolhe, Esc
 * fecha (e, fechado, limpa), Home/End vão às pontas. A contagem de sugestões
 * é anunciada em `aria-live`. Puro: as opções vêm por prop; quem busca é o
 * chamador.
 */
export function Combobox({
  id,
  rotulo,
  valor,
  aoMudar,
  opcoes,
  aoEscolher,
  placeholder,
  textoSemResultado = 'Nenhuma sugestão. Continue digitando ou confira a grafia.',
  carregando = false,
  minimo = 1,
  rotuloOculto = false,
  className,
}: Props) {
  const idLista = `${id}-lista`;
  const idStatus = useId();
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const raiz = useRef<HTMLDivElement>(null);
  const temTexto = valor.trim().length >= minimo;
  const listaVisivel = aberto && temTexto;

  useEffect(() => {
    setAtivo((atual) => (atual >= opcoes.length ? -1 : atual));
  }, [opcoes]);

  useEffect(() => {
    if (!listaVisivel) return;
    const aoClicarFora = (evento: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(evento.target as Node)) setAberto(false);
    };
    document.addEventListener('mousedown', aoClicarFora);
    return () => document.removeEventListener('mousedown', aoClicarFora);
  }, [listaVisivel]);

  const escolher = (opcao: OpcaoCombobox) => {
    aoEscolher(opcao);
    setAberto(false);
    setAtivo(-1);
  };

  const aoTeclar = (evento: KeyboardEvent<HTMLInputElement>) => {
    const total = opcoes.length;
    switch (evento.key) {
      case 'ArrowDown':
        evento.preventDefault();
        if (!listaVisivel) {
          setAberto(true);
          setAtivo(total > 0 ? 0 : -1);
        } else if (total > 0) {
          setAtivo((a) => (a + 1) % total);
        }
        break;
      case 'ArrowUp':
        evento.preventDefault();
        if (listaVisivel && total > 0) setAtivo((a) => (a <= 0 ? total - 1 : a - 1));
        break;
      case 'Home':
        if (listaVisivel && total > 0) {
          evento.preventDefault();
          setAtivo(0);
        }
        break;
      case 'End':
        if (listaVisivel && total > 0) {
          evento.preventDefault();
          setAtivo(total - 1);
        }
        break;
      case 'Enter': {
        const opcao = listaVisivel && ativo >= 0 ? opcoes[ativo] : undefined;
        if (opcao) {
          evento.preventDefault();
          escolher(opcao);
        }
        break;
      }
      case 'Escape':
        if (listaVisivel) {
          evento.preventDefault();
          setAberto(false);
          setAtivo(-1);
        } else if (valor) {
          evento.preventDefault();
          aoMudar('');
        }
        break;
      default:
        break;
    }
  };

  const statusTexto = !listaVisivel
    ? ''
    : carregando
      ? 'Buscando sugestões…'
      : opcoes.length === 0
        ? textoSemResultado
        : `${opcoes.length} ${opcoes.length === 1 ? 'sugestão' : 'sugestões'}. Use as setas para navegar e Enter para escolher.`;

  return (
    <div ref={raiz} className={className ? `combobox ${className}` : 'combobox'}>
      <label htmlFor={id} className={rotuloOculto ? 'visualmente-oculto' : 'campo__rotulo'}>
        {rotulo}
      </label>
      <div className="combobox__campo">
        <input
          id={id}
          className="campo__entrada combobox__entrada"
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={valor}
          aria-expanded={listaVisivel}
          aria-controls={idLista}
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-activedescendant={listaVisivel && ativo >= 0 ? `${idLista}-${ativo}` : undefined}
          aria-describedby={idStatus}
          onChange={(e) => {
            aoMudar(e.target.value);
            setAberto(true);
            setAtivo(-1);
          }}
          onFocus={() => setAberto(true)}
          onKeyDown={aoTeclar}
        />
        {valor ? (
          <button
            type="button"
            className="combobox__limpar"
            aria-label="Limpar busca"
            onClick={() => {
              aoMudar('');
              setAtivo(-1);
              document.getElementById(id)?.focus();
            }}
          >
            <Icon nome="fechar" tamanho={16} />
          </button>
        ) : null}
      </div>
      <ul id={idLista} role="listbox" aria-label={`Sugestões para ${rotulo}`} className="combobox__lista" hidden={!listaVisivel}>
        {listaVisivel
          ? opcoes.map((opcao, indice) => (
              <li
                key={opcao.id}
                id={`${idLista}-${indice}`}
                role="option"
                aria-selected={indice === ativo}
                className={indice === ativo ? 'combobox__opcao combobox__opcao--ativa' : 'combobox__opcao'}
                onMouseDown={(e) => e.preventDefault()} // mantém o foco no input
                onMouseEnter={() => setAtivo(indice)}
                onClick={() => escolher(opcao)}
              >
                <span className="combobox__rotulo">{opcao.rotulo}</span>
                {opcao.tipo ? <span className="combobox__tipo">{opcao.tipo}</span> : null}
              </li>
            ))
          : null}
      </ul>
      <p id={idStatus} className="visualmente-oculto" role="status" aria-live="polite">
        {statusTexto}
      </p>
      {listaVisivel && !carregando && opcoes.length === 0 ? (
        <p className="combobox__vazio" aria-hidden="true">
          {textoSemResultado}
        </p>
      ) : null}
    </div>
  );
}
