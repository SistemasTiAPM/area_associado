import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import {
  BUSCA_FAQ_MAX,
  COMENTARIO_CANCELAMENTO_MAX,
  MENSAGEM_MAX,
  buscarFaq,
  enviarFormularioCentral,
  obterContatoCentral,
  pedirCancelamento,
  urlReautenticacaoAjuda,
  type AssuntoFormulario,
  type ContatoCentral,
  type ItemFaq,
  type MotivoCancelamento,
  type RespostaFaq,
} from '../api/ajuda';
import { ApiError } from '../api/client';
import {
  ASSUNTOS,
  ASSUNTO_ANALYTICS,
  MOTIVOS,
  ROTULOS_ASSUNTO,
  ROTULOS_FINALIDADE,
  ROTULOS_MOTIVO,
  type FinalidadeDeclaracao,
} from '../api/rotulos';
import { criarSolicitacao, liberaEmDe, novaChaveIdempotencia, type Solicitacao } from '../api/solicitacoes';
import { Accordion } from '../components/Accordion';
import { Campo } from '../components/Campo';
import { EstadoErro } from '../components/EstadoErro';
import { RadioGroup, type Opcao } from '../components/GrupoOpcoes';
import { Icon } from '../components/Icon';
import { LinkExterno } from '../components/LinkExterno';
import { LinkInterno } from '../components/LinkInterno';
import { SeloEstado } from '../components/SeloEstado';
import { Skeleton } from '../components/Skeleton';
import { registrarUso } from '../lib/analytics';
import { registrarErroExibido } from '../lib/erros';
import { dataBR, dataDaApi } from '../lib/formato';
import { urlExternaSegura, urlTelefone } from '../lib/links';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';
import { abortado, mensagemDe, requestIdDe } from './SolicitacaoComum';

/**
 * Ajuda e atendimento (P14; RF-AJ-01..05, RF-FI-04). Blocos: perguntas frequentes
 * (busca no servidor, `Accordion` por categoria; some se a FAQ estiver vazia),
 * canais da Central (`GET /ajuda/contato`; canal sem configuração some), pedidos
 * comuns (perfil, declaração, dúvida) e, com a flag `cancelamento_online`, o
 * pedido de cancelamento com step-up. Evento de UI: `ajuda_contatar` (canal e
 * assunto); a criação de solicitação e o pedido de cancelamento o servidor registra.
 * Textos fora da spec: proposta (P-44), voz §3.3.
 */

const ATRASO_BUSCA_MS = 300;

type Carga<T> = { fase: 'carregando' } | { fase: 'erro'; falha: unknown } | { fase: 'pronta'; dados: T };

/** `detalhes` da API indexados pelo nome do campo, sem o prefixo `campos.`. */
function errosDe(falha: unknown): Record<string, string> {
  if (!(falha instanceof ApiError) || !Array.isArray(falha.detalhes)) return {};
  return Object.fromEntries(falha.detalhes.map((d) => [d.campo.replace(/^campos\./, ''), d.mensagem]));
}

/* ------------------------------------------------------------------ FAQ */

function Resposta({ texto }: { texto: string }) {
  const paragrafos = texto.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return (
    <>
      {paragrafos.map((p, i) => (
        <p key={i} className="faq__paragrafo">
          {p}
        </p>
      ))}
    </>
  );
}

function agrupar(dados: RespostaFaq): { codigo: string; rotulo: string; itens: ItemFaq[] }[] {
  const rotulos = new Map(dados.categorias.map((c) => [c.codigo, c.rotulo]));
  const grupos = new Map<string, ItemFaq[]>();
  for (const item of dados.itens) {
    const chave = rotulos.has(item.categoria) ? item.categoria : '';
    grupos.set(chave, [...(grupos.get(chave) ?? []), item]);
  }
  const ordem = [...dados.categorias.map((c) => c.codigo), ''];
  return ordem
    .filter((codigo) => grupos.has(codigo))
    .map((codigo) => ({ codigo, rotulo: rotulos.get(codigo) ?? 'Outras perguntas', itens: grupos.get(codigo) ?? [] }));
}

function BlocoFaq() {
  const idBusca = useId();
  const [termo, setTermo] = useState('');
  const [filtro, setFiltro] = useState<{ q: string; categoria: string | null }>({ q: '', categoria: null });
  const [estado, setEstado] = useState<Carga<RespostaFaq>>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);

  // Busca no servidor (`?q=`, ≤ 80) depois de uma pausa na digitação; termo novo limpa a categoria.
  // Termo igual ao filtro atual devolve o mesmo objeto: nada de nova busca.
  useEffect(() => {
    const q = termo.trim();
    const t = setTimeout(() => setFiltro((atual) => (atual.q === q ? atual : { q, categoria: null })), ATRASO_BUSCA_MS);
    return () => clearTimeout(t);
  }, [termo]);

  useEffect(() => {
    const controle = new AbortController();
    setEstado({ fase: 'carregando' });
    buscarFaq(filtro, controle.signal).then(
      (dados) => setEstado({ fase: 'pronta', dados }),
      (falha: unknown) => {
        if (abortado(falha)) return;
        registrarErroExibido(falha);
        setEstado({ fase: 'erro', falha });
      },
    );
    return () => controle.abort();
  }, [filtro, tentativa]);

  const semFiltro = filtro.q === '' && filtro.categoria === null;
  // Spec v2 §3.2: bloco sem conteúdo não aparece (FAQ ainda sem perguntas publicadas).
  if (estado.fase === 'pronta' && semFiltro && estado.dados.itens.length === 0) return null;

  const escolherCategoria = (codigo: string | null) => {
    setTermo('');
    setFiltro({ q: '', categoria: codigo });
  };

  const rotuloCategoria =
    estado.fase === 'pronta' && filtro.categoria
      ? estado.dados.categorias.find((c) => c.codigo === filtro.categoria)?.rotulo ?? null
      : null;

  return (
    <section className="cartao secao-ajuda" aria-labelledby="titulo-faq">
      <h2 className="secao__titulo" id="titulo-faq">
        Perguntas frequentes
      </h2>
      <div className="faq__busca" role="search" aria-label="Perguntas frequentes">
        <label htmlFor={idBusca} className="campo__rotulo">
          Buscar nas perguntas frequentes
        </label>
        <input
          id={idBusca}
          className="campo__entrada"
          type="search"
          autoComplete="off"
          maxLength={BUSCA_FAQ_MAX}
          value={termo}
          onChange={(e) => setTermo(e.target.value.slice(0, BUSCA_FAQ_MAX))}
        />
      </div>

      {filtro.categoria && rotuloCategoria ? (
        <p className="faq__filtro">
          Mostrando: <strong>{rotuloCategoria}</strong>
          <button type="button" className="link-texto" onClick={() => escolherCategoria(null)}>
            Ver todas as perguntas
          </button>
        </p>
      ) : null}

      {estado.fase === 'carregando' ? <Skeleton variante="texto" quantidade={4} rotulo="Carregando as perguntas frequentes…" /> : null}
      {estado.fase === 'erro' ? (
        <EstadoErro
          titulo="Não conseguimos carregar as perguntas frequentes agora"
          mensagem={mensagemDe(estado.falha)}
          requestId={requestIdDe(estado.falha)}
          aoTentarNovamente={() => setTentativa((t) => t + 1)}
        />
      ) : null}
      {estado.fase === 'pronta' ? <ResultadoFaq dados={estado.dados} q={filtro.q} aoEscolherCategoria={escolherCategoria} /> : null}
    </section>
  );
}

function ResultadoFaq({
  dados,
  q,
  aoEscolherCategoria,
}: {
  dados: RespostaFaq;
  q: string;
  aoEscolherCategoria: (codigo: string) => void;
}) {
  const total = dados.itens.length;
  const anuncio = q ? (total === 1 ? '1 pergunta encontrada.' : `${total} perguntas encontradas.`) : '';
  const rotulos = new Map(dados.categorias.map((c) => [c.codigo, c.rotulo]));
  const sugestoes = dados.sugestoes.filter((codigo) => rotulos.has(codigo));
  return (
    <>
      <p className="visualmente-oculto" role="status">
        {anuncio}
      </p>
      {total === 0 ? (
        <div className="faq__vazio">
          <p>
            {q ? `Não encontramos perguntas sobre “${q}”. Tente outras palavras` : 'Não há perguntas nesta categoria agora'}
            {sugestoes.length > 0 ? ' ou veja uma destas categorias:' : '. Se precisar, fale com a Central.'}
          </p>
          {sugestoes.length > 0 ? (
            <ul className="faq__sugestoes" aria-label="Categorias sugeridas">
              {sugestoes.map((codigo) => (
                <li key={codigo}>
                  <button type="button" className="botao botao--secundario" onClick={() => aoEscolherCategoria(codigo)}>
                    {rotulos.get(codigo)}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        agrupar(dados).map((grupo) => (
          <div key={grupo.codigo || 'outras'} className="faq__categoria">
            <h3 className="faq__categoria-titulo">{grupo.rotulo}</h3>
            <Accordion
              nivel={4}
              itens={grupo.itens.map((item) => ({ id: String(item.id), titulo: item.pergunta, conteudo: <Resposta texto={item.resposta} /> }))}
            />
          </div>
        ))
      )}
    </>
  );
}

/* ------------------------------------------------------------- Central */

function BlocoCentral({ aoEscrever, formularioDisponivel }: { aoEscrever: () => void; formularioDisponivel: boolean }) {
  const [estado, setEstado] = useState<Carga<ContatoCentral>>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    const controle = new AbortController();
    setEstado({ fase: 'carregando' });
    obterContatoCentral(controle.signal).then(
      (dados) => setEstado({ fase: 'pronta', dados }),
      (falha: unknown) => {
        if (abortado(falha)) return;
        registrarErroExibido(falha);
        setEstado({ fase: 'erro', falha });
      },
    );
    return () => controle.abort();
  }, [tentativa]);

  const contato = estado.fase === 'pronta' ? estado.dados : null;
  const whatsapp = contato?.whatsapp && urlExternaSegura(contato.whatsapp.url) ? contato.whatsapp : null;
  const telefone = contato?.telefone ? urlTelefone(contato.telefone.uri) : null;
  const horario = contato?.horario?.trim() || null;
  const temCanal = Boolean(whatsapp || telefone || formularioDisponivel);
  if (estado.fase === 'pronta' && !temCanal) return null;

  return (
    <section className="cartao secao-ajuda" aria-labelledby="titulo-central">
      <h2 className="secao__titulo" id="titulo-central">
        Fale com a Central de Relacionamento
      </h2>
      {horario ? <p className="secao__subtitulo">Horário de atendimento: {horario}</p> : null}
      {estado.fase === 'carregando' ? <Skeleton variante="lista" quantidade={2} rotulo="Carregando os canais da Central…" /> : null}
      {estado.fase === 'erro' ? (
        <EstadoErro
          titulo="Não conseguimos carregar os canais da Central agora"
          mensagem={mensagemDe(estado.falha)}
          requestId={requestIdDe(estado.falha)}
          aoTentarNovamente={() => setTentativa((t) => t + 1)}
        />
      ) : null}
      {estado.fase !== 'carregando' ? (
        <ul className="canais">
          {whatsapp ? (
            <li className="canal">
              <span className="canal__icone" aria-hidden="true">
                <Icon nome="conversa" tamanho={20} />
              </span>
              <span className="canal__textos">
                <b className="canal__titulo">WhatsApp</b>
                <span className="canal__texto">{whatsapp.exibicao}</span>
              </span>
              <LinkExterno
                href={whatsapp.url}
                className="link-texto canal__acao"
                aoClicar={() => registrarUso({ acao: 'ajuda_contatar', entidade: 'central', detalhes: { canal: 'whatsapp' } })}
              >
                Conversar pelo WhatsApp
              </LinkExterno>
            </li>
          ) : null}
          {telefone && contato?.telefone ? (
            <li className="canal">
              <span className="canal__icone" aria-hidden="true">
                <Icon nome="telefone" tamanho={20} />
              </span>
              <span className="canal__textos">
                <b className="canal__titulo">Telefone</b>
                <span className="canal__texto">{contato.telefone.exibicao}</span>
              </span>
              <a
                className="link-texto canal__acao"
                href={telefone}
                onClick={() => registrarUso({ acao: 'ajuda_contatar', entidade: 'central', detalhes: { canal: 'telefone' } })}
              >
                Ligar para a Central
              </a>
            </li>
          ) : null}
          {formularioDisponivel ? (
            <li className="canal">
              <span className="canal__icone" aria-hidden="true">
                <Icon nome="envelope" tamanho={20} />
              </span>
              <span className="canal__textos">
                <b className="canal__titulo">Mensagem</b>
                <span className="canal__texto">A resposta chega em Minhas solicitações.</span>
              </span>
              <button type="button" className="link-texto canal__acao" onClick={aoEscrever}>
                Escrever para a Central
              </button>
            </li>
          ) : null}
        </ul>
      ) : null}
    </section>
  );
}

/* --------------------------------------------------- pedidos e formulários */

type Pedido = { tipo: 'duvida'; assunto: AssuntoFormulario } | { tipo: 'declaracao' };

/** Confirmação depois de criar a solicitação: prazo (quando houver) e próximo passo (spec v2 P04/P14). */
function Confirmacao({ titulo, texto, solicitacao, aoFechar }: { titulo: string; texto: string; solicitacao: Solicitacao; aoFechar: () => void }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => ref.current?.focus(), []);
  const prazo = dataDaApi(solicitacao.prazo_em);
  return (
    <div className="confirmacao">
      <h3 ref={ref} className="confirmacao__titulo" tabIndex={-1}>
        <Icon nome="check" tamanho={18} />
        {titulo}
      </h3>
      <p>{texto}</p>
      {prazo ? <p>Prazo de retorno: {dataBR(prazo)}.</p> : null}
      <div className="botoes">
        <LinkInterno para={`/solicitacoes/${solicitacao.id}`} className="botao botao--primario">
          Acompanhar a solicitação
        </LinkInterno>
        <button type="button" className="link-texto" onClick={aoFechar}>
          Fechar
        </button>
      </div>
    </div>
  );
}

function FormularioDuvida({ assuntoInicial, aoFechar }: { assuntoInicial: AssuntoFormulario; aoFechar: () => void }) {
  const { mostrar, mostrarErro } = useToast();
  // Uma chave por formulário aberto: a repetição do envio (rede caiu) não cria outra solicitação.
  const [chave, setChave] = useState(novaChaveIdempotencia);
  const [assunto, setAssunto] = useState<AssuntoFormulario>(assuntoInicial);
  const [mensagem, setMensagem] = useState('');
  const [erros, setErros] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [criada, setCriada] = useState<Solicitacao | null>(null);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (!mensagem.trim()) {
      setErros({ mensagem: 'Escreva sua mensagem antes de enviar.' });
      return;
    }
    setErros({});
    setEnviando(true);
    try {
      const solicitacao = await enviarFormularioCentral({ assunto, mensagem, chave_idempotencia: chave });
      registrarUso({ acao: 'ajuda_contatar', entidade: 'central', detalhes: { canal: 'formulario', assunto: ASSUNTO_ANALYTICS[assunto] } });
      setCriada(solicitacao);
      setChave(novaChaveIdempotencia());
      mostrar('Mensagem enviada');
    } catch (falha) {
      setErros(errosDe(falha));
      mostrarErro(falha);
    } finally {
      setEnviando(false);
    }
  };

  if (criada) {
    return (
      <Confirmacao
        titulo="Recebemos sua mensagem"
        texto="Nós encaminhamos para a equipe certa e avisamos você a cada etapa. A resposta fica em Minhas solicitações."
        solicitacao={criada}
        aoFechar={aoFechar}
      />
    );
  }

  return (
    <form className="formulario" onSubmit={(e) => void enviar(e)} noValidate>
      <Campo id="duvida-assunto" rotulo="Assunto" erro={erros.assunto}>
        {(a) => (
          <select {...a} className="campo__entrada" value={assunto} onChange={(e) => setAssunto(e.target.value as AssuntoFormulario)}>
            {ASSUNTOS.map((codigo) => (
              <option key={codigo} value={codigo}>
                {ROTULOS_ASSUNTO[codigo]}
              </option>
            ))}
          </select>
        )}
      </Campo>
      <Campo id="duvida-mensagem" rotulo="Mensagem" erro={erros.mensagem} dica={`${mensagem.length} de ${MENSAGEM_MAX} caracteres. Não escreva dados de saúde nem o seu CPF.`}>
        {(a) => (
          <textarea
            {...a}
            className="campo__entrada campo__entrada--texto"
            rows={6}
            maxLength={MENSAGEM_MAX}
            value={mensagem}
            onChange={(e) => setMensagem(e.target.value)}
            required
          />
        )}
      </Campo>
      <div className="botoes">
        <button type="submit" className="botao botao--primario" disabled={enviando} aria-busy={enviando}>
          {enviando ? 'Enviando…' : 'Enviar mensagem'}
        </button>
        <button type="button" className="link-texto" onClick={aoFechar} disabled={enviando}>
          Fechar
        </button>
      </div>
    </form>
  );
}

const OPCOES_FINALIDADE: readonly Opcao<FinalidadeDeclaracao>[] = [
  { valor: 'geral', rotulo: ROTULOS_FINALIDADE.geral, descricao: 'Comprova o seu vínculo com a APM.' },
  {
    valor: 'amb_prova_titulo',
    rotulo: ROTULOS_FINALIDADE.amb_prova_titulo,
    descricao: 'Disponível a partir de 1 mês de associação.',
  },
];

const OBSERVACAO_MAX = 200;

function FormularioDeclaracao({ aoFechar }: { aoFechar: () => void }) {
  const { mostrar, mostrarErro } = useToast();
  const [chave, setChave] = useState(novaChaveIdempotencia);
  const [finalidade, setFinalidade] = useState<FinalidadeDeclaracao | null>(null);
  const [observacao, setObservacao] = useState('');
  const [erros, setErros] = useState<Record<string, string>>({});
  const [liberaEm, setLiberaEm] = useState<Date | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [criada, setCriada] = useState<Solicitacao | null>(null);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (!finalidade) {
      setErros({ finalidade: 'Escolha qual declaração você precisa.' });
      return;
    }
    setErros({});
    setLiberaEm(null);
    setEnviando(true);
    try {
      const obs = observacao.trim();
      const solicitacao = await criarSolicitacao({
        tipo_servico: 'declaracao_associado',
        campos: obs ? { finalidade, observacao: obs } : { finalidade },
        chave_idempotencia: chave,
      });
      setCriada(solicitacao);
      setChave(novaChaveIdempotencia());
      mostrar('Pedido de declaração enviado');
    } catch (falha) {
      const data = liberaEmDe(falha);
      if (data) {
        setLiberaEm(data);
        registrarErroExibido(falha);
      } else {
        setErros(errosDe(falha));
        mostrarErro(falha);
      }
    } finally {
      setEnviando(false);
    }
  };

  if (criada) {
    return (
      <Confirmacao
        titulo="Recebemos seu pedido de declaração"
        texto="A equipe da APM prepara a declaração e avisa você quando estiver pronta. Você acompanha cada etapa em Minhas solicitações."
        solicitacao={criada}
        aoFechar={aoFechar}
      />
    );
  }

  return (
    <form className="formulario" onSubmit={(e) => void enviar(e)} noValidate>
      <RadioGroup
        nome="declaracao-finalidade"
        legenda="Qual declaração você precisa?"
        opcoes={OPCOES_FINALIDADE}
        valor={finalidade}
        aoMudar={(v) => {
          setFinalidade(v);
          setLiberaEm(null);
        }}
        erro={erros.finalidade}
      />
      {liberaEm ? (
        <div className="aviso aviso--libera" role="alert">
          <SeloEstado estado="libera_em" liberaEm={liberaEm} />
          <p>
            Esta declaração fica disponível depois de 1 mês de associação. Volte a partir de {dataBR(liberaEm)} ou fale com a
            Central se precisar antes.
          </p>
        </div>
      ) : null}
      <Campo id="declaracao-observacao" rotulo="Observação (opcional)" erro={erros.observacao} dica={`${observacao.length} de ${OBSERVACAO_MAX} caracteres`}>
        {(a) => (
          <input
            {...a}
            className="campo__entrada"
            maxLength={OBSERVACAO_MAX}
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
          />
        )}
      </Campo>
      <div className="botoes">
        <button type="submit" className="botao botao--primario" disabled={enviando} aria-busy={enviando}>
          {enviando ? 'Enviando…' : 'Solicitar declaração'}
        </button>
        <button type="button" className="link-texto" onClick={aoFechar} disabled={enviando}>
          Fechar
        </button>
      </div>
    </form>
  );
}

function PainelPedido({ pedido, aoFechar }: { pedido: Pedido; aoFechar: () => void }) {
  const titulo = useRef<HTMLHeadingElement>(null);
  useEffect(() => titulo.current?.focus(), [pedido]);
  const texto =
    pedido.tipo === 'declaracao'
      ? { titulo: 'Pedir uma declaração', apoio: 'A declaração é enviada pela equipe da APM.' }
      : { titulo: 'Escrever para a Central', apoio: 'Conte o que você precisa. A resposta chega em Minhas solicitações.' };
  return (
    <section className="cartao secao-ajuda" aria-labelledby="titulo-pedido">
      <h2 ref={titulo} className="secao__titulo" id="titulo-pedido" tabIndex={-1}>
        {texto.titulo}
      </h2>
      <p className="secao__subtitulo">{texto.apoio}</p>
      {pedido.tipo === 'declaracao' ? (
        <FormularioDeclaracao aoFechar={aoFechar} />
      ) : (
        <FormularioDuvida assuntoInicial={pedido.assunto} aoFechar={aoFechar} />
      )}
    </section>
  );
}

function BlocoPedidosComuns({ aoAbrir, solicitacoesDisponiveis }: { aoAbrir: (p: Pedido) => void; solicitacoesDisponiveis: boolean }) {
  return (
    <section className="secao-ajuda" aria-labelledby="titulo-pedidos">
      <h2 className="secao__titulo" id="titulo-pedidos">
        Pedidos comuns
      </h2>
      <ul className="grade-pedidos">
        <li className="pedido cartao">
          <span className="pedido__icone" aria-hidden="true">
            <Icon nome="usuario" tamanho={20} />
          </span>
          <b className="pedido__titulo">Atualizar meus dados</b>
          <span className="pedido__texto">Celular, endereço, e-mail e foto ficam em Meu perfil.</span>
          <Link to="/perfil" className="link-texto pedido__acao">
            Atualizar cadastro
            <Icon nome="seta" tamanho={14} />
          </Link>
        </li>
        {solicitacoesDisponiveis ? (
          <>
            <li className="pedido cartao">
              <span className="pedido__icone" aria-hidden="true">
                <Icon nome="documento" tamanho={20} />
              </span>
              <b className="pedido__titulo">Declaração</b>
              <span className="pedido__texto">Declaração de associado ou da AMB para prova de título.</span>
              <button type="button" className="link-texto pedido__acao" onClick={() => aoAbrir({ tipo: 'declaracao' })}>
                Solicitar declaração
                <Icon nome="seta" tamanho={14} />
              </button>
            </li>
            <li className="pedido cartao">
              <span className="pedido__icone" aria-hidden="true">
                <Icon nome="sacola" tamanho={20} />
              </span>
              <b className="pedido__titulo">Dúvida sobre benefício</b>
              <span className="pedido__texto">Pergunte como usar, quem pode usar ou o que está incluído.</span>
              <button type="button" className="link-texto pedido__acao" onClick={() => aoAbrir({ tipo: 'duvida', assunto: 'beneficio' })}>
                Enviar dúvida
                <Icon nome="seta" tamanho={14} />
              </button>
            </li>
          </>
        ) : null}
      </ul>
    </section>
  );
}

/* ---------------------------------------------------------- cancelamento */

const OPCOES_MOTIVO: readonly Opcao<MotivoCancelamento>[] = MOTIVOS.map((m) => ({ valor: m, rotulo: ROTULOS_MOTIVO[m] }));

/** Pedido de cancelamento da associação (RF-AJ-04): motivo obrigatório, conversa opcional, step-up no servidor. */
function BlocoCancelamento() {
  const { mostrar, mostrarErro } = useToast();
  const idFormulario = useId();
  const [aberto, setAberto] = useState(false);
  const [desligado, setDesligado] = useState(false);
  const [chave, setChave] = useState(novaChaveIdempotencia);
  const [motivo, setMotivo] = useState<MotivoCancelamento | null>(null);
  const [querConversa, setQuerConversa] = useState(false);
  const [comentario, setComentario] = useState('');
  const [erros, setErros] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [criada, setCriada] = useState<Solicitacao | null>(null);
  const tituloConfirmacao = useRef<HTMLHeadingElement>(null);
  const formulario = useRef<HTMLFormElement>(null);
  const prazoCriada = dataDaApi(criada?.prazo_em);

  useEffect(() => {
    if (criada) tituloConfirmacao.current?.focus();
  }, [criada]);

  useEffect(() => {
    // O botão que abriu o formulário some: o foco vai para o primeiro motivo.
    if (aberto) formulario.current?.querySelector<HTMLInputElement>('input')?.focus();
  }, [aberto]);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (!motivo) {
      setErros({ motivo: 'Escolha um motivo para continuar.' });
      return;
    }
    setErros({});
    setEnviando(true);
    try {
      const solicitacao = await pedirCancelamento({ motivo, quer_conversa: querConversa, comentario, chave_idempotencia: chave });
      setCriada(solicitacao);
      setChave(novaChaveIdempotencia());
      mostrar('Pedido de cancelamento enviado');
    } catch (falha) {
      if (falha instanceof ApiError && falha.erro === 'reautenticacao_necessaria') {
        // Step-up (RF-AU-11): senha de novo no Login APM e volta para esta página.
        window.location.assign(urlReautenticacaoAjuda());
        return;
      }
      if (falha instanceof ApiError && falha.erro === 'recurso_desligado') setDesligado(true);
      setErros(errosDe(falha));
      mostrarErro(falha);
    } finally {
      setEnviando(false);
    }
  };

  if (desligado) return null;

  return (
    <section className="cartao secao-ajuda" aria-labelledby="titulo-cancelamento">
      <h2 className="secao__titulo" id="titulo-cancelamento">
        Cancelar a associação
      </h2>
      {criada ? (
        <div className="confirmacao">
          <h3 ref={tituloConfirmacao} className="confirmacao__titulo" tabIndex={-1}>
            <Icon nome="check" tamanho={18} />
            Recebemos seu pedido de cancelamento
          </h3>
          <p>
            {querConversa
              ? 'A Central de Relacionamento vai procurar você para conversar antes de concluir.'
              : 'A Central de Relacionamento conclui o cancelamento e confirma com você por e-mail.'}{' '}
            Enquanto ele não for concluído, você pode desistir em Minhas solicitações.
          </p>
          {prazoCriada ? <p>Prazo de retorno: {dataBR(prazoCriada)}.</p> : null}
          <div className="botoes">
            <LinkInterno para={`/solicitacoes/${criada.id}`} className="botao botao--primario">
              Acompanhar o pedido
            </LinkInterno>
          </div>
        </div>
      ) : (
        <>
          <p className="secao__subtitulo">
            Se decidir sair, faça o pedido por aqui. A Central de Relacionamento recebe o pedido, conclui o cancelamento e
            confirma com você por e-mail.
          </p>
          {!aberto ? (
            <div className="botoes">
              <button type="button" className="botao botao--secundario" aria-expanded={false} aria-controls={idFormulario} onClick={() => setAberto(true)}>
                Quero cancelar minha associação
              </button>
            </div>
          ) : (
            <form ref={formulario} id={idFormulario} className="formulario" onSubmit={(e) => void enviar(e)} noValidate>
              <RadioGroup
                nome="cancelamento-motivo"
                legenda="Por que você quer cancelar?"
                opcoes={OPCOES_MOTIVO}
                valor={motivo}
                aoMudar={setMotivo}
                erro={erros.motivo}
              />
              <div className={querConversa ? 'opcao opcao--marcada' : 'opcao'}>
                <input
                  id="cancelamento-conversa"
                  className="opcao__entrada"
                  type="checkbox"
                  checked={querConversa}
                  onChange={(e) => setQuerConversa(e.target.checked)}
                />
                <label className="opcao__rotulo" htmlFor="cancelamento-conversa">
                  <span className="opcao__texto">Quero conversar com a Central antes de cancelar</span>
                  <span className="opcao__descricao">Opcional. Talvez a gente consiga resolver o que está incomodando.</span>
                </label>
              </div>
              <Campo
                id="cancelamento-comentario"
                rotulo="Quer contar mais? (opcional)"
                erro={erros.comentario}
                dica={`${comentario.length} de ${COMENTARIO_CANCELAMENTO_MAX} caracteres`}
              >
                {(a) => (
                  <textarea
                    {...a}
                    className="campo__entrada campo__entrada--texto"
                    rows={3}
                    maxLength={COMENTARIO_CANCELAMENTO_MAX}
                    value={comentario}
                    onChange={(e) => setComentario(e.target.value)}
                  />
                )}
              </Campo>
              <p className="campo__dica">
                Por segurança, o Login APM pode pedir sua senha de novo antes do envio. Depois você volta para esta página.
              </p>
              <div className="botoes">
                <button type="submit" className="botao botao--destrutivo" disabled={enviando} aria-busy={enviando}>
                  {enviando ? 'Enviando…' : 'Pedir cancelamento'}
                </button>
                <button type="button" className="link-texto" onClick={() => setAberto(false)} disabled={enviando}>
                  Desistir
                </button>
              </div>
            </form>
          )}
        </>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ tela */

export function PaginaAjuda() {
  const { sessao } = useSessao();
  const [pedido, setPedido] = useState<Pedido | null>(null);
  // Remonta o formulário a cada abertura: estado e chave de idempotência novos.
  const [abertura, setAbertura] = useState(0);
  const solicitacoesDisponiveis = sessao.recursos?.solicitacoes === true;

  const abrir = useCallback((p: Pedido) => {
    setPedido(p);
    setAbertura((n) => n + 1);
  }, []);
  const fechar = useCallback(() => setPedido(null), []);

  return (
    <>
      <BlocoFaq />
      <BlocoCentral formularioDisponivel={solicitacoesDisponiveis} aoEscrever={() => abrir({ tipo: 'duvida', assunto: 'outro' })} />
      <BlocoPedidosComuns aoAbrir={abrir} solicitacoesDisponiveis={solicitacoesDisponiveis} />
      {pedido && solicitacoesDisponiveis ? <PainelPedido key={abertura} pedido={pedido} aoFechar={fechar} /> : null}
      {sessao.flags.cancelamento_online && solicitacoesDisponiveis ? <BlocoCancelamento /> : null}
    </>
  );
}
