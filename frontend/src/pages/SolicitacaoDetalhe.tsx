import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { ApiError } from '../api/client';
import {
  COMENTARIO_AVALIACAO_MAX,
  MOTIVO_CANCELAMENTO_MAX,
  RESPOSTA_MAX,
  avaliarSolicitacao,
  cancelarSolicitacao,
  obterSolicitacao,
  responderSolicitacao,
  type Solicitacao,
  type ValorCampo,
} from '../api/solicitacoes';
import { ROTULOS_ASSUNTO, ROTULOS_FINALIDADE, ROTULOS_MOTIVO } from '../api/rotulos';
import { Avaliacao } from '../components/Avaliacao';
import { Campo } from '../components/Campo';
import { Dialogo } from '../components/Dialogo';
import { EstadoErro } from '../components/EstadoErro';
import { EstadoVazio } from '../components/EstadoVazio';
import { Icon } from '../components/Icon';
import { LinhaDoTempo } from '../components/LinhaDoTempo';
import { Skeleton } from '../components/Skeleton';
import { StatusSolicitacao } from '../components/StatusSolicitacao';
import { registrarErroExibido } from '../lib/erros';
import { dataBR, dataDaApi } from '../lib/formato';
import { useDefinirTituloPagina } from '../shell/TituloPagina';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';
import { ContatoSolicitacao, FAIXA_AGUARDANDO_PARCEIRO, abortado, data, mensagemDe, requestIdDe } from './SolicitacaoComum';

/** Texto do 409 de ação concorrente (RF-SO-04; proposta). */
export const MENSAGEM_MUDOU_SITUACAO = 'Esta solicitação mudou de situação. Atualizamos a página.';

/** 409 que significam "o estado mudou desde que a tela carregou": mensagem fixa e recarga. */
const ERROS_ESTADO_MUDOU = new Set(['estado_invalido', 'ja_avaliada']);

const ROTULOS_CAMPO: Record<string, string> = {
  assunto: 'Assunto',
  mensagem: 'Mensagem',
  finalidade: 'Finalidade',
  observacao: 'Observação',
  motivo: 'Motivo',
  quer_conversa: 'Quer conversar antes',
  comentario: 'Comentário',
  alteracoes: 'Alterações pedidas',
  justificativa: 'Justificativa',
  titulo: 'Título',
  area_interesse: 'Área de interesse',
  categoria: 'Assunto',
};

const ROTULOS_VALOR: Record<string, Readonly<Record<string, string>>> = {
  assunto: ROTULOS_ASSUNTO,
  categoria: ROTULOS_ASSUNTO,
  finalidade: ROTULOS_FINALIDADE,
  motivo: ROTULOS_MOTIVO,
};

function rotuloCampo(chave: string): string {
  const conhecido = ROTULOS_CAMPO[chave];
  if (conhecido) return conhecido;
  const texto = chave.replace(/_/g, ' ').trim();
  return texto ? texto.charAt(0).toUpperCase() + texto.slice(1) : chave;
}

function textoValor(chave: string, valor: Exclude<ValorCampo, Record<string, unknown>>): string {
  if (valor === null || valor === '') return '—';
  if (typeof valor === 'boolean') return valor ? 'Sim' : 'Não';
  if (typeof valor === 'number') return String(valor);
  return ROTULOS_VALOR[chave]?.[valor] ?? valor;
}

/** Campos enviados (RF-SO-02): só o que a API devolveu (allowlist do tipo), sem HTML. */
function CamposEnviados({ campos }: { campos: Solicitacao['campos'] }) {
  // `categoria` (código do formulário da Ajuda) repete o `assunto` já gravado com o rótulo.
  const entradas = Object.entries(campos).filter(([chave]) => !(chave === 'categoria' && 'assunto' in campos));
  if (entradas.length === 0) return null;
  return (
    <section className="cartao secao-solicitacao" aria-labelledby="titulo-campos">
      <h2 className="secao__titulo" id="titulo-campos">
        O que você enviou
      </h2>
      <dl className="dados-perfil dados-solicitacao">
        {entradas.map(([chave, valor]) => (
          <div key={chave} className="dados-solicitacao__linha">
            <dt>{rotuloCampo(chave)}</dt>
            <dd>
              {valor !== null && typeof valor === 'object' ? (
                <ul className="dados-solicitacao__lista">
                  {Object.entries(valor).map(([sub, v]) => (
                    <li key={sub}>
                      {rotuloCampo(sub)}: {textoValor(sub, v)}
                    </li>
                  ))}
                </ul>
              ) : (
                textoValor(chave, valor)
              )}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

interface PropsAcao {
  solicitacao: Solicitacao;
  aoConcluir: (atualizada: Solicitacao, aviso: string) => void;
  aoFalhar: (falha: unknown) => Promise<void>;
}

/** Resposta ao parceiro/APM em `pendente_associado` (RF-SO-05): 1 a 2000 caracteres. */
function FormularioResposta({ solicitacao, aoConcluir, aoFalhar }: PropsAcao) {
  const [texto, setTexto] = useState('');
  const [erro, setErro] = useState<string | undefined>(undefined);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    const limpo = texto.trim();
    if (!limpo) {
      setErro('Escreva sua resposta antes de enviar.');
      return;
    }
    setErro(undefined);
    setEnviando(true);
    try {
      aoConcluir(await responderSolicitacao(solicitacao.id, limpo), 'Resposta enviada');
    } catch (falha) {
      const campo = falha instanceof ApiError ? falha.detalhes?.find((d) => d.campo === 'texto') : undefined;
      if (campo) setErro(campo.mensagem);
      await aoFalhar(falha);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="cartao secao-solicitacao" aria-labelledby="titulo-responder">
      <h2 className="secao__titulo" id="titulo-responder">
        Responder
      </h2>
      <form className="formulario" onSubmit={(e) => void enviar(e)} noValidate>
        <Campo id="resposta" rotulo="Sua resposta" erro={erro} dica={`${texto.length} de ${RESPOSTA_MAX} caracteres`}>
          {(a) => (
            <textarea
              {...a}
              className="campo__entrada campo__entrada--texto"
              rows={5}
              maxLength={RESPOSTA_MAX}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              required
            />
          )}
        </Campo>
        <div className="botoes">
          <button type="submit" className="botao botao--primario" disabled={enviando} aria-busy={enviando}>
            {enviando ? 'Enviando…' : 'Enviar resposta'}
          </button>
        </div>
      </form>
    </section>
  );
}

/** Avaliação de 0 a 10 depois de concluída (RF-SO-10); uma vez, dentro do prazo do servidor. */
function FormularioAvaliacao({ solicitacao, aoConcluir, aoFalhar }: PropsAcao) {
  const [nota, setNota] = useState<number | null>(null);
  const [comentario, setComentario] = useState('');
  const [erro, setErro] = useState<string | undefined>(undefined);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (nota === null) {
      setErro('Escolha uma nota de 0 a 10.');
      return;
    }
    setErro(undefined);
    setEnviando(true);
    try {
      aoConcluir(await avaliarSolicitacao(solicitacao.id, nota, comentario), 'Avaliação enviada');
    } catch (falha) {
      await aoFalhar(falha);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="cartao secao-solicitacao" aria-labelledby="titulo-avaliar">
      <h2 className="secao__titulo" id="titulo-avaliar">
        Avaliar o atendimento
      </h2>
      <form className="formulario" onSubmit={(e) => void enviar(e)} noValidate>
        <Avaliacao nome="nota-solicitacao" valor={nota} aoMudar={setNota} erro={erro} desabilitado={enviando} />
        <Campo id="avaliacao-comentario" rotulo="Comentário (opcional)" dica={`${comentario.length} de ${COMENTARIO_AVALIACAO_MAX} caracteres`}>
          {(a) => (
            <textarea
              {...a}
              className="campo__entrada campo__entrada--texto"
              rows={3}
              maxLength={COMENTARIO_AVALIACAO_MAX}
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
            />
          )}
        </Campo>
        <div className="botoes">
          <button type="submit" className="botao botao--primario" disabled={enviando} aria-busy={enviando}>
            {enviando ? 'Enviando…' : 'Enviar avaliação'}
          </button>
        </div>
      </form>
    </section>
  );
}

/** Cancelar em `criada`, `enviada` e `pendente_associado` (RF-SO-04, RF-SO-12), com confirmação. */
function AcaoCancelar({ solicitacao, aoConcluir, aoFalhar }: PropsAcao) {
  const [aberto, setAberto] = useState(false);
  const [motivo, setMotivo] = useState('');
  const [enviando, setEnviando] = useState(false);

  const fechar = useCallback(() => {
    if (!enviando) setAberto(false);
  }, [enviando]);

  const confirmar = async () => {
    setEnviando(true);
    try {
      const atualizada = await cancelarSolicitacao(solicitacao.id, motivo);
      setAberto(false);
      aoConcluir(atualizada, 'Solicitação cancelada');
    } catch (falha) {
      setAberto(false);
      await aoFalhar(falha);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <section className="cartao secao-solicitacao" aria-labelledby="titulo-cancelar">
      <h2 className="secao__titulo" id="titulo-cancelar">
        Não precisa mais?
      </h2>
      <p className="secao__subtitulo">Você pode cancelar enquanto o parceiro ainda não começou o atendimento.</p>
      <div className="botoes">
        <button type="button" className="botao botao--secundario" onClick={() => setAberto(true)}>
          Cancelar solicitação
        </button>
      </div>
      <Dialogo
        aberto={aberto}
        titulo="Cancelar esta solicitação?"
        descricao="Depois de cancelada, ela não volta a andar. Se precisar, você pode fazer um novo pedido."
        aoFechar={fechar}
        destrutivo
        acoes={
          <>
            <button type="button" className="botao botao--destrutivo" onClick={() => void confirmar()} disabled={enviando} aria-busy={enviando}>
              {enviando ? 'Cancelando…' : 'Cancelar solicitação'}
            </button>
            <button type="button" className="botao botao--secundario" onClick={fechar} disabled={enviando}>
              Manter solicitação
            </button>
          </>
        }
      >
        <Campo id="motivo-cancelamento" rotulo="Motivo (opcional)" dica={`${motivo.length} de ${MOTIVO_CANCELAMENTO_MAX} caracteres`}>
          {(a) => (
            <textarea
              {...a}
              className="campo__entrada campo__entrada--texto"
              rows={3}
              maxLength={MOTIVO_CANCELAMENTO_MAX}
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
          )}
        </Campo>
      </Dialogo>
    </section>
  );
}

type Estado =
  | { fase: 'carregando' }
  | { fase: 'nao_encontrada' }
  | { fase: 'erro'; falha: unknown }
  | { fase: 'pronta'; dados: Solicitacao };

/** Detalhe da solicitação (`/solicitacoes/{id}`; RF-SO-02, 04, 05, 10, 13). */
const ENCERRADAS: ReadonlySet<string> = new Set(['concluida_positiva', 'concluida_negativa', 'cancelada']);

export function DetalheSolicitacao({ id }: { id: string }) {
  const { recarregar: recarregarSessao } = useSessao();
  const { mostrar, mostrarErro } = useToast();
  const [estado, setEstado] = useState<Estado>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);
  const idPendencia = useId();
  const montado = useRef(true);

  useDefinirTituloPagina(estado.fase === 'pronta' ? estado.dados.beneficio?.titulo || estado.dados.tipo.rotulo : null);

  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  useEffect(() => {
    const controle = new AbortController();
    setEstado({ fase: 'carregando' });
    obterSolicitacao(id, controle.signal).then(
      (dados) => setEstado({ fase: 'pronta', dados }),
      (falha: unknown) => {
        if (abortado(falha)) return;
        if (falha instanceof ApiError && falha.status === 404) {
          setEstado({ fase: 'nao_encontrada' });
          return;
        }
        registrarErroExibido(falha);
        setEstado({ fase: 'erro', falha });
      },
    );
    return () => controle.abort();
  }, [id, tentativa]);

  /** Recarrega sem tirar a tela do lugar (depois de uma ação ou de um 409). */
  const atualizar = useCallback(async () => {
    try {
      const dados = await obterSolicitacao(id);
      if (montado.current) setEstado({ fase: 'pronta', dados });
    } catch (falha) {
      if (!montado.current) return;
      if (falha instanceof ApiError && falha.status === 404) setEstado({ fase: 'nao_encontrada' });
      else mostrarErro(falha);
    }
  }, [id, mostrarErro]);

  const aoConcluir = useCallback(
    (atualizada: Solicitacao, aviso: string) => {
      if (montado.current) setEstado({ fase: 'pronta', dados: atualizada });
      mostrar(aviso);
      // Contador "aguardando você" no menu (RF-SO-07) muda depois de responder ou cancelar.
      void recarregarSessao();
    },
    [mostrar, recarregarSessao],
  );

  const aoFalhar = useCallback(
    async (falha: unknown) => {
      if (falha instanceof ApiError && falha.status === 409) {
        mostrarErro(
          ERROS_ESTADO_MUDOU.has(falha.erro)
            ? new ApiError(409, falha.erro, MENSAGEM_MUDOU_SITUACAO, falha.requestId)
            : falha,
        );
        await atualizar();
        void recarregarSessao();
        return;
      }
      mostrarErro(falha);
    },
    [atualizar, mostrarErro, recarregarSessao],
  );

  if (estado.fase === 'carregando') return <Skeleton variante="texto" quantidade={5} rotulo="Carregando a solicitação…" />;
  if (estado.fase === 'nao_encontrada') {
    return (
      <EstadoVazio titulo="Não encontramos esta solicitação">
        <p>Confira o endereço ou volte para a lista. Se precisar, fale com a Central.</p>
        <p>
          <Link to="/solicitacoes" className="link-texto">
            <Icon nome="voltar" tamanho={14} />
            Voltar para Minhas solicitações
          </Link>
        </p>
      </EstadoVazio>
    );
  }
  if (estado.fase === 'erro') {
    return (
      <EstadoErro
        titulo="Não conseguimos carregar esta solicitação agora"
        mensagem={mensagemDe(estado.falha)}
        requestId={requestIdDe(estado.falha)}
        aoTentarNovamente={() => setTentativa((t) => t + 1)}
      />
    );
  }

  const s = estado.dados;
  const pendente = s.status === 'pendente_associado';
  // Mensagem pública do pedido ao associado: a mais recente em `pendente_associado`.
  const pedido = pendente
    ? [...s.linha_do_tempo].reverse().find((e) => e.status === 'pendente_associado' && e.mensagem)?.mensagem ?? null
    : null;
  const prazo = dataDaApi(s.prazo_em);
  const avaliadaEm = dataDaApi(s.avaliacao?.avaliada_em);
  // Já no CRM da Central (ADR-0023): a área não leva cancelamento nem resposta até lá.
  const comCentral = s.na_central && !ENCERRADAS.has(s.status);

  return (
    <>
      <p>
        <Link to="/solicitacoes" className="link-texto">
          <Icon nome="voltar" tamanho={14} />
          Voltar para Minhas solicitações
        </Link>
      </p>

      <section className="cartao secao-solicitacao" aria-labelledby="titulo-situacao" aria-describedby={pendente ? idPendencia : undefined}>
        <div className="item-solicitacao__topo">
          <h2 className="secao__titulo" id="titulo-situacao">
            Situação
          </h2>
          <StatusSolicitacao status={s.status} rotulo={s.rotulo_status} />
        </div>
        {pendente && s.na_central ? (
          <div className="aviso aviso--acao" id={idPendencia}>
            <p>
              <strong>A Central precisa de mais informações.</strong> Ela vai falar com você pelos contatos do seu
              cadastro.
            </p>
          </div>
        ) : pendente ? (
          <div className="aviso aviso--acao" id={idPendencia}>
            <p>
              <strong>O parceiro precisa de algo seu.</strong> Responda abaixo para o atendimento continuar.
            </p>
            {pedido ? <p className="aviso__citacao">{pedido}</p> : null}
          </div>
        ) : null}
        {s.aguardando_parceiro ? (
          <p className="faixa-cobranca">
            <Icon nome="relogio" tamanho={16} />
            {FAIXA_AGUARDANDO_PARCEIRO}
          </p>
        ) : null}
        <dl className="dados-perfil">
          <dt>Pedido</dt>
          <dd>{s.tipo.rotulo}</dd>
          {s.beneficio ? (
            <>
              <dt>Benefício</dt>
              <dd>{s.beneficio.titulo}</dd>
            </>
          ) : null}
          {s.protocolo ? (
            <>
              <dt>Protocolo na Central</dt>
              <dd className="dado-protocolo">{s.protocolo}</dd>
            </>
          ) : null}
          <dt>Aberta em</dt>
          <dd>{data(s.criada_em)}</dd>
          <dt>Atualizada em</dt>
          <dd>{data(s.atualizada_em)}</dd>
          {prazo ? (
            <>
              <dt>Prazo de retorno</dt>
              <dd>{dataBR(prazo)}</dd>
            </>
          ) : null}
          {s.contato ? (
            <>
              <dt>Contato</dt>
              <dd>
                <ContatoSolicitacao contato={s.contato} />
              </dd>
            </>
          ) : null}
        </dl>
        {comCentral ? (
          <p className="aviso" id="aviso-central">
            Este pedido já está com a Central de Relacionamento. Para cancelar ou complementar, fale com a Central
            {s.protocolo ? ` e informe o protocolo ${s.protocolo}` : ''}.
          </p>
        ) : null}
      </section>

      {s.pode_responder ? <FormularioResposta key={`r-${s.atualizada_em}`} solicitacao={s} aoConcluir={aoConcluir} aoFalhar={aoFalhar} /> : null}

      {s.linha_do_tempo.length > 0 ? (
        <section className="cartao secao-solicitacao" aria-labelledby="titulo-linha-tempo">
          <h2 className="secao__titulo" id="titulo-linha-tempo">
            Linha do tempo
          </h2>
          <LinhaDoTempo eventos={s.linha_do_tempo} />
        </section>
      ) : null}

      <CamposEnviados campos={s.campos} />

      {s.avaliacao ? (
        <section className="cartao secao-solicitacao" aria-labelledby="titulo-avaliacao">
          <h2 className="secao__titulo" id="titulo-avaliacao">
            Sua avaliação
          </h2>
          <p className="avaliacao-feita">
            Nota {s.avaliacao.nota} de 10{avaliadaEm ? `, enviada em ${dataBR(avaliadaEm)}` : ''}.
          </p>
          {s.avaliacao.comentario ? <p className="aviso__citacao">{s.avaliacao.comentario}</p> : null}
        </section>
      ) : s.pode_avaliar ? (
        <FormularioAvaliacao key={`a-${s.atualizada_em}`} solicitacao={s} aoConcluir={aoConcluir} aoFalhar={aoFalhar} />
      ) : null}

      {s.pode_cancelar ? <AcaoCancelar solicitacao={s} aoConcluir={aoConcluir} aoFalhar={aoFalhar} /> : null}
    </>
  );
}
