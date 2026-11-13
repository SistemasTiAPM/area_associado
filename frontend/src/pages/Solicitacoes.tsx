import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import {
  listarSolicitacoes,
  type ResumoSolicitacao,
  type SituacaoLista,
} from '../api/solicitacoes';
import { EstadoErro } from '../components/EstadoErro';
import { EstadoVazio } from '../components/EstadoVazio';
import { Icon } from '../components/Icon';
import { LinkInterno } from '../components/LinkInterno';
import { Skeleton } from '../components/Skeleton';
import { StatusSolicitacao } from '../components/StatusSolicitacao';
import { Tabs } from '../components/Tabs';
import { registrarErroExibido } from '../lib/erros';
import type { PropsPagina } from '../App';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';
import {
  ContatoSolicitacao,
  FAIXA_AGUARDANDO_PARCEIRO,
  abortado,
  data,
  mensagemDe,
  requestIdDe,
} from './SolicitacaoComum';
import { NovaSolicitacao } from './NovaSolicitacao';
import { DetalheSolicitacao } from './SolicitacaoDetalhe';

/**
 * Minhas solicitações (P05; RF-SO-01, 07, 08, 09, 15). Lista por cursor em duas
 * abas; item com status (texto, nunca só cor), faixa "Aguardando o parceiro" e
 * prazo/contato quando houver. `/solicitacoes/{id}` abre o detalhe (sub-rota
 * pessoal: o protocolo não vai ao analytics). Eventos: só `pagina_ver` e
 * `erro_exibido` — criar, cancelar, responder e avaliar são registrados pelo servidor.
 * Textos fora da spec: proposta (P-44), voz §3.3.
 *
 * Com a flag `solicitacoes_crm` (ADR-0024, paridade com o App APM): botão "Nova
 * solicitação" (`/solicitacoes/nova`), o que foi aberto pelo App aparece na mesma lista
 * (marca "Aberta pelo app"), o rótulo é o do App, há selo de resposta nova e aviso quando
 * a lista veio parcial (CRM fora).
 */
export function PaginaSolicitacoes({ parametro }: PropsPagina) {
  if (parametro === ROTA_NOVA) return <NovaSolicitacao />;
  if (parametro !== undefined) return <DetalheSolicitacao id={parametro} />;
  return <ListaSolicitacoes />;
}

/** Segmento reservado da sub-rota: nunca é um id de solicitação (ids são UUID). */
const ROTA_NOVA = 'nova';

const NOVA_RESPOSTA: Record<string, string> = {
  central: 'Nova resposta da Central',
  apm: 'Nova resposta da APM',
};

const ABAS: readonly { id: SituacaoLista; rotulo: string }[] = [
  { id: 'andamento', rotulo: 'Em andamento' },
  { id: 'encerradas', rotulo: 'Encerradas' },
];

type EstadoLista =
  | { fase: 'carregando' }
  | { fase: 'erro'; falha: unknown }
  | { fase: 'pronta'; itens: ResumoSolicitacao[]; cursor: string | null; carregandoMais: boolean; parcial: boolean };

function ItemSolicitacao({ item }: { item: ResumoSolicitacao }) {
  // No CRM vale a situação (a mesma do App); fora dele, o status da área.
  const pendente = item.situacao ? item.situacao === 'aguardando_associado' : item.status === 'pendente_associado';
  const titulo = item.beneficio?.titulo || item.tipo.rotulo;
  const novaResposta = item.nova_resposta ? NOVA_RESPOSTA[item.responde ?? 'apm'] ?? NOVA_RESPOSTA.apm : null;
  return (
    <li className={pendente || novaResposta ? 'item-solicitacao cartao item-solicitacao--destaque' : 'item-solicitacao cartao'}>
      <div className="item-solicitacao__topo">
        <StatusSolicitacao status={item.status} rotulo={item.rotulo_status} situacao={item.situacao} />
        {novaResposta ? (
          <span className="item-solicitacao__chamada">{novaResposta}</span>
        ) : pendente ? (
          <span className="item-solicitacao__chamada">Precisa de uma resposta sua</span>
        ) : null}
      </div>
      <h2 className="item-solicitacao__titulo">
        <LinkInterno para={`/solicitacoes/${item.id}`} className="item-solicitacao__link">
          {titulo}
          <Icon nome="seta" tamanho={16} />
        </LinkInterno>
      </h2>
      {item.beneficio ? <p className="item-solicitacao__tipo">{item.tipo.rotulo}</p> : null}
      {item.canal === 'app' ? <p className="item-solicitacao__tipo">Aberta pelo app</p> : null}
      {item.aguardando_parceiro ? (
        <p className="faixa-cobranca">
          <Icon nome="relogio" tamanho={16} />
          {FAIXA_AGUARDANDO_PARCEIRO}
        </p>
      ) : null}
      <dl className="item-solicitacao__dados">
        <div>
          <dt>Aberta em</dt>
          <dd>{data(item.criada_em)}</dd>
        </div>
        <div>
          <dt>Atualizada em</dt>
          <dd>{data(item.atualizada_em)}</dd>
        </div>
        {item.protocolo ? (
          <div>
            <dt>Protocolo</dt>
            <dd className="dado-protocolo">{item.protocolo}</dd>
          </div>
        ) : null}
        {item.prazo_em ? (
          <div>
            <dt>Prazo de retorno</dt>
            <dd>{data(item.prazo_em)}</dd>
          </div>
        ) : item.status === 'criada' ? (
          <div>
            <dt>Prazo de retorno</dt>
            <dd>informado após o envio</dd>
          </div>
        ) : null}
        {item.contato ? (
          <div>
            <dt>Contato</dt>
            <dd>
              <ContatoSolicitacao contato={item.contato} />
            </dd>
          </div>
        ) : null}
      </dl>
    </li>
  );
}

function ListaSolicitacoes() {
  const { sessao } = useSessao();
  const { mostrarErro } = useToast();
  const [aba, setAba] = useState<SituacaoLista>('andamento');
  const [estado, setEstado] = useState<EstadoLista>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);
  const [anuncio, setAnuncio] = useState('');
  // Geração da lista: resposta de "Carregar mais" de outra aba (ou anterior a um recarregamento) é descartada.
  const geracao = useRef(0);
  const lista = useRef<HTMLUListElement>(null);
  const focarIndice = useRef<number | null>(null);

  useEffect(() => {
    const controle = new AbortController();
    geracao.current += 1;
    setEstado({ fase: 'carregando' });
    setAnuncio('');
    listarSolicitacoes(aba, null, controle.signal).then(
      (pagina) =>
        setEstado({
          fase: 'pronta',
          itens: pagina.itens,
          cursor: pagina.proximo_cursor,
          carregandoMais: false,
          parcial: pagina.parcial === true,
        }),
      (falha: unknown) => {
        if (abortado(falha)) return;
        registrarErroExibido(falha);
        setEstado({ fase: 'erro', falha });
      },
    );
    return () => controle.abort();
  }, [aba, tentativa]);

  useEffect(() => {
    // Depois de "Carregar mais", o foco vai para o primeiro item novo (o botão pode sumir).
    if (estado.fase !== 'pronta' || focarIndice.current === null) return;
    const links = lista.current?.querySelectorAll<HTMLElement>('.item-solicitacao__link');
    links?.[focarIndice.current]?.focus();
    focarIndice.current = null;
  }, [estado]);

  const carregarMais = useCallback(async () => {
    if (estado.fase !== 'pronta' || !estado.cursor || estado.carregandoMais) return;
    const minhaGeracao = geracao.current;
    const { itens, cursor, parcial } = estado;
    setEstado({ fase: 'pronta', itens, cursor, carregandoMais: true, parcial });
    try {
      const pagina = await listarSolicitacoes(aba, cursor);
      if (geracao.current !== minhaGeracao) return;
      // Só esta função acrescenta itens e a geração não mudou: `itens` ainda é a lista na tela.
      const vistos = new Set(itens.map((i) => i.id));
      const novos = pagina.itens.filter((i) => !vistos.has(i.id));
      focarIndice.current = novos.length > 0 ? itens.length : null;
      setAnuncio(novos.length === 1 ? '1 solicitação carregada.' : `${novos.length} solicitações carregadas.`);
      setEstado({
        fase: 'pronta',
        itens: [...itens, ...novos],
        cursor: pagina.proximo_cursor,
        carregandoMais: false,
        parcial: parcial || pagina.parcial === true,
      });
    } catch (falha) {
      if (geracao.current !== minhaGeracao) return;
      mostrarErro(falha);
      setEstado((atual) => (atual.fase === 'pronta' ? { ...atual, carregandoMais: false } : atual));
    }
  }, [aba, estado, mostrarErro]);

  const conteudo = (() => {
    if (estado.fase === 'carregando') return <Skeleton variante="lista" quantidade={3} rotulo="Carregando suas solicitações…" />;
    if (estado.fase === 'erro') {
      return (
        <EstadoErro
          titulo="Não conseguimos carregar suas solicitações agora"
          mensagem={mensagemDe(estado.falha)}
          requestId={requestIdDe(estado.falha)}
          aoTentarNovamente={() => setTentativa((t) => t + 1)}
        />
      );
    }
    const avisoParcial = estado.parcial ? (
      <p className="aviso" role="status">
        Não conseguimos consultar a Central agora. As solicitações abertas pelo app podem não aparecer; tente de novo
        em instantes.
      </p>
    ) : null;
    if (estado.itens.length === 0) {
      return aba === 'andamento' ? (
        <>
          {avisoParcial}
          <EstadoVazio titulo="Você não tem solicitações em andamento">
            <p>Quando você fizer um pedido à APM, ele aparece aqui com cada etapa do atendimento.</p>
            {sessao.recursos?.ajuda ? (
              <p>
                <Link to="/ajuda" className="link-texto">
                  Ver pedidos comuns e falar com a Central na Ajuda
                  <Icon nome="seta" tamanho={14} />
                </Link>
              </p>
            ) : null}
          </EstadoVazio>
        </>
      ) : (
        <>
          {avisoParcial}
          <EstadoVazio titulo="Nenhuma solicitação encerrada">
            <p>As solicitações concluídas, que não seguiram ou que foram canceladas ficam guardadas aqui.</p>
          </EstadoVazio>
        </>
      );
    }
    return (
      <>
        {avisoParcial}
        <ul ref={lista} className="lista-solicitacoes" aria-label={aba === 'andamento' ? 'Solicitações em andamento' : 'Solicitações encerradas'}>
          {estado.itens.map((item) => (
            <ItemSolicitacao key={item.id} item={item} />
          ))}
        </ul>
        {estado.cursor ? (
          <div className="botoes lista-solicitacoes__mais">
            <button
              type="button"
              className="botao botao--secundario"
              onClick={() => void carregarMais()}
              disabled={estado.carregandoMais}
              aria-busy={estado.carregandoMais}
            >
              {estado.carregandoMais ? 'Carregando mais…' : 'Carregar mais'}
            </button>
          </div>
        ) : null}
      </>
    );
  })();

  return (
    <>
      {sessao.flags.solicitacoes_crm ? (
        <div className="botoes lista-solicitacoes__nova">
          <Link to="/solicitacoes/nova" className="botao botao--primario">
            Nova solicitação
          </Link>
        </div>
      ) : null}
      <Tabs
        rotulo="Situação das solicitações"
        ativa={aba}
        aoMudar={(id) => setAba(id === 'encerradas' ? 'encerradas' : 'andamento')}
        abas={ABAS.map((a) => ({ id: a.id, rotulo: a.rotulo, conteudo }))}
      />
      <p className="visualmente-oculto" role="status">
        {anuncio}
      </p>
    </>
  );
}
