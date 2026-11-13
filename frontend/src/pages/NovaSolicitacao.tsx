import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { ApiError } from '../api/client';
import {
  DESCRICAO_MAX,
  DESCRICAO_MIN,
  criarSolicitacao,
  liberaEmDe,
  listarTipos,
  novaChaveIdempotencia,
  type Solicitacao,
  type TipoCatalogo,
} from '../api/solicitacoes';
import { Campo } from '../components/Campo';
import { EstadoErro } from '../components/EstadoErro';
import { EstadoVazio } from '../components/EstadoVazio';
import { Icon } from '../components/Icon';
import { LinkInterno } from '../components/LinkInterno';
import { Skeleton } from '../components/Skeleton';
import { registrarErroExibido } from '../lib/erros';
import { useDefinirTituloPagina } from '../shell/TituloPagina';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';
import { abortado, mensagemDe, requestIdDe } from './SolicitacaoComum';

/**
 * Nova solicitação (`/solicitacoes/nova`; ADR-0024, flag `solicitacoes_crm`): o MESMO
 * catálogo do App APM. O servidor só devolve os tipos que a APM mantém ligados no CRM;
 * os seguros ficam agrupados em uma linha que abre a sublista. Formulário único: o texto
 * do associado (10 a 2000 caracteres) é o que a equipe recebe.
 */

const QUEM_RESPONDE: Record<TipoCatalogo['responde'], string> = {
  central: 'Central de Relacionamento',
  apm: 'Equipe APM',
};

type Entrada =
  | { classe: 'tipo'; ordem: number; tipo: TipoCatalogo }
  | { classe: 'grupo'; ordem: number; codigo: string; rotulo: string; tipos: TipoCatalogo[] };

/** Tipos na ordem do catálogo; cada grupo vira uma linha na posição do seu menor `ordem`. */
export function organizarCatalogo(tipos: readonly TipoCatalogo[]): Entrada[] {
  const entradas: Entrada[] = [];
  const grupos = new Map<string, Extract<Entrada, { classe: 'grupo' }>>();
  for (const tipo of [...tipos].sort((a, b) => a.ordem - b.ordem)) {
    if (!tipo.grupo) {
      entradas.push({ classe: 'tipo', ordem: tipo.ordem, tipo });
      continue;
    }
    let grupo = grupos.get(tipo.grupo);
    if (!grupo) {
      grupo = { classe: 'grupo', ordem: tipo.ordem, codigo: tipo.grupo, rotulo: tipo.grupo_rotulo || tipo.rotulo, tipos: [] };
      grupos.set(tipo.grupo, grupo);
      entradas.push(grupo);
    }
    grupo.tipos.push(tipo);
  }
  return entradas.sort((a, b) => a.ordem - b.ordem);
}

type EstadoCatalogo =
  | { fase: 'carregando' }
  | { fase: 'desligado' }
  | { fase: 'erro'; falha: unknown }
  | { fase: 'pronto'; tipos: TipoCatalogo[] };

function BotaoTipo({ tipo, aoEscolher }: { tipo: TipoCatalogo; aoEscolher: (tipo: TipoCatalogo) => void }) {
  return (
    <button type="button" className="catalogo-tipos__botao" onClick={() => aoEscolher(tipo)}>
      <span>{tipo.rotulo}</span>
      <Icon nome="seta" tamanho={16} />
    </button>
  );
}

function ListaTipos({ tipos, aoEscolher }: { tipos: TipoCatalogo[]; aoEscolher: (tipo: TipoCatalogo) => void }) {
  const entradas = useMemo(() => organizarCatalogo(tipos), [tipos]);
  const [abertos, setAbertos] = useState<ReadonlySet<string>>(new Set());
  const alternar = (codigo: string) =>
    setAbertos((atual) => {
      const novo = new Set(atual);
      if (!novo.delete(codigo)) novo.add(codigo);
      return novo;
    });
  return (
    <ul className="catalogo-tipos" aria-label="Tipos de solicitação">
      {entradas.map((entrada) =>
        entrada.classe === 'tipo' ? (
          <li key={entrada.tipo.codigo}>
            <BotaoTipo tipo={entrada.tipo} aoEscolher={aoEscolher} />
          </li>
        ) : (
          <li key={`grupo-${entrada.codigo}`}>
            <button
              type="button"
              className="catalogo-tipos__botao catalogo-tipos__botao--grupo"
              aria-expanded={abertos.has(entrada.codigo)}
              aria-controls={`grupo-${entrada.codigo}`}
              onClick={() => alternar(entrada.codigo)}
            >
              <span>{entrada.rotulo}</span>
              <Icon nome="chevron" tamanho={16} />
            </button>
            <ul
              id={`grupo-${entrada.codigo}`}
              className="catalogo-tipos catalogo-tipos--sub"
              aria-label={entrada.rotulo}
              hidden={!abertos.has(entrada.codigo)}
            >
              {entrada.tipos.map((tipo) => (
                <li key={tipo.codigo}>
                  <BotaoTipo tipo={tipo} aoEscolher={aoEscolher} />
                </li>
              ))}
            </ul>
          </li>
        ),
      )}
    </ul>
  );
}

interface PropsFormulario {
  tipo: TipoCatalogo;
  aoVoltar: () => void;
  aoCriar: (criada: Solicitacao) => void;
  /** O serviço foi desligado no CRM entre a lista e o envio: recarrega o catálogo. */
  aoIndisponivel: () => void;
}

function Formulario({ tipo, aoVoltar, aoCriar, aoIndisponivel }: PropsFormulario) {
  const { mostrar, mostrarErro } = useToast();
  const [texto, setTexto] = useState('');
  const [erro, setErro] = useState<string | undefined>(undefined);
  const [carencia, setCarencia] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  // Mesma chave em cada nova tentativa do MESMO pedido (RF-SO-03).
  const chave = useRef(novaChaveIdempotencia());
  const titulo = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    titulo.current?.focus();
  }, []);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    const limpo = texto.trim();
    if (limpo.length < DESCRICAO_MIN) {
      setErro(`Conte o que você precisa em pelo menos ${DESCRICAO_MIN} caracteres.`);
      return;
    }
    setErro(undefined);
    setCarencia(null);
    setEnviando(true);
    try {
      const criada = await criarSolicitacao({
        tipo_servico: tipo.codigo,
        campos: { mensagem: limpo },
        chave_idempotencia: chave.current,
      });
      chave.current = novaChaveIdempotencia();
      mostrar('Solicitação enviada');
      aoCriar(criada);
    } catch (falha) {
      const api = falha instanceof ApiError ? falha : null;
      const campo = api?.detalhes?.find((d) => d.campo === 'campos.mensagem');
      if (liberaEmDe(falha)) {
        setCarencia(mensagemDe(falha));
        registrarErroExibido(falha);
      } else if (campo) {
        setErro(campo.mensagem);
      } else {
        mostrarErro(falha);
        if (api?.erro === 'servico_indisponivel') aoIndisponivel();
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="cartao secao-solicitacao" aria-labelledby="titulo-nova">
      <h2 className="secao__titulo" id="titulo-nova" tabIndex={-1} ref={titulo}>
        {tipo.rotulo}
      </h2>
      <p className="secao__subtitulo">Quem responde: {QUEM_RESPONDE[tipo.responde] ?? QUEM_RESPONDE.apm}.</p>
      <form className="formulario" onSubmit={(e) => void enviar(e)} noValidate>
        <Campo
          id="nova-solicitacao-mensagem"
          rotulo="Conte o que você precisa"
          erro={erro}
          dica={`${texto.length} de ${DESCRICAO_MAX} caracteres. Não informe CPF nem números de documento.`}
        >
          {(a) => (
            <textarea
              {...a}
              className="campo__entrada campo__entrada--texto"
              rows={6}
              maxLength={DESCRICAO_MAX}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              required
            />
          )}
        </Campo>
        {carencia ? (
          <p className="aviso" role="alert">
            {carencia}
          </p>
        ) : null}
        <div className="botoes">
          <button type="submit" className="botao botao--primario" disabled={enviando} aria-busy={enviando}>
            {enviando ? 'Enviando…' : 'Enviar solicitação'}
          </button>
          <button type="button" className="botao botao--secundario" onClick={aoVoltar} disabled={enviando}>
            Escolher outro tipo
          </button>
        </div>
      </form>
    </section>
  );
}

export function NovaSolicitacao() {
  const { sessao } = useSessao();
  const ligada = sessao.flags.solicitacoes_crm === true;
  const [estado, setEstado] = useState<EstadoCatalogo>(ligada ? { fase: 'carregando' } : { fase: 'desligado' });
  const [tentativa, setTentativa] = useState(0);
  const [escolhido, setEscolhido] = useState<TipoCatalogo | null>(null);
  const [criada, setCriada] = useState<Solicitacao | null>(null);

  useDefinirTituloPagina('Nova solicitação');

  useEffect(() => {
    if (!ligada) {
      setEstado({ fase: 'desligado' });
      return;
    }
    const controle = new AbortController();
    setEstado({ fase: 'carregando' });
    listarTipos(controle.signal).then(
      (tipos) => setEstado({ fase: 'pronto', tipos }),
      (falha: unknown) => {
        if (abortado(falha)) return;
        if (falha instanceof ApiError && falha.erro === 'recurso_desligado') {
          setEstado({ fase: 'desligado' });
          return;
        }
        registrarErroExibido(falha);
        setEstado({ fase: 'erro', falha });
      },
    );
    return () => controle.abort();
  }, [ligada, tentativa]);

  const voltar = (
    <p>
      <Link to="/solicitacoes" className="link-texto">
        <Icon nome="voltar" tamanho={14} />
        Voltar para Minhas solicitações
      </Link>
    </p>
  );

  if (estado.fase === 'desligado') {
    return (
      <EstadoVazio titulo="Não encontramos esta página">
        <p>Para falar com a APM, use a Ajuda ou volte para as suas solicitações.</p>
        {voltar}
      </EstadoVazio>
    );
  }
  if (criada) {
    return (
      <>
        {voltar}
        <section className="cartao secao-solicitacao" aria-labelledby="titulo-enviada" role="status">
          <h2 className="secao__titulo" id="titulo-enviada">
            Recebemos sua solicitação
          </h2>
          <p>
            {criada.tipo.rotulo}. Você acompanha cada etapa e conversa com a equipe em Minhas solicitações.
          </p>
          <div className="botoes">
            <LinkInterno para={`/solicitacoes/${criada.id}`} className="botao botao--primario">
              Acompanhar esta solicitação
            </LinkInterno>
          </div>
        </section>
      </>
    );
  }
  if (estado.fase === 'carregando') {
    return (
      <>
        {voltar}
        <Skeleton variante="lista" quantidade={5} rotulo="Carregando os tipos de solicitação…" />
      </>
    );
  }
  if (estado.fase === 'erro') {
    return (
      <>
        {voltar}
        <EstadoErro
          titulo="Não conseguimos carregar os tipos de solicitação agora"
          mensagem={mensagemDe(estado.falha)}
          requestId={requestIdDe(estado.falha)}
          aoTentarNovamente={() => setTentativa((t) => t + 1)}
        />
      </>
    );
  }
  if (estado.tipos.length === 0) {
    return (
      <>
        {voltar}
        <EstadoVazio titulo="Nenhum serviço disponível para solicitação agora">
          <p>Se precisar de algo, fale com a Central pela Ajuda.</p>
        </EstadoVazio>
      </>
    );
  }
  // O tipo escolhido pode ter saído do catálogo numa recarga (serviço desligado no CRM).
  const tipo = escolhido ? estado.tipos.find((t) => t.codigo === escolhido.codigo) ?? null : null;
  return (
    <>
      {voltar}
      {tipo ? (
        <Formulario
          key={tipo.codigo}
          tipo={tipo}
          aoVoltar={() => setEscolhido(null)}
          aoCriar={setCriada}
          aoIndisponivel={() => {
            setEscolhido(null);
            setTentativa((t) => t + 1);
          }}
        />
      ) : (
        <section className="cartao secao-solicitacao" aria-labelledby="titulo-tipos">
          <h2 className="secao__titulo" id="titulo-tipos">
            Sobre o que você quer falar com a APM?
          </h2>
          <ListaTipos tipos={estado.tipos} aoEscolher={setEscolhido} />
        </section>
      )}
    </>
  );
}
