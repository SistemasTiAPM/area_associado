import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import {
  MENSAGEM_MAX,
  MENSAGEM_MIN,
  enviarMensagem,
  listarMensagens,
  novaChaveIdempotencia,
  type Conversa as DadosConversa,
  type MensagemConversa,
  type QuemResponde,
} from '../api/solicitacoes';
import { registrarErroExibido } from '../lib/erros';
import { dataDaApi, dataHoraBR } from '../lib/formato';
import { useToast } from '../state/ToastContext';
import { Campo } from './Campo';
import { EstadoErro } from './EstadoErro';
import { Icon } from './Icon';
import { LinkInterno } from './LinkInterno';
import { Skeleton } from './Skeleton';

/**
 * Conversa do associado com a Central em uma solicitação (ADR-0024; paridade com o App APM).
 *
 * - As mensagens vêm do CRM (de qualquer canal: App ou Minha APM) e são texto puro.
 * - Enviar grava na fila da área (202): a mensagem aparece como "Enviando…" e chega à
 *   Central em instantes. Sem consulta em intervalo: a conversa é lida ao abrir, depois
 *   de enviar e em "Atualizar".
 * - A caixa de envio só existe quando o servidor diz `pode_enviar`; encerrada = só leitura.
 * - 429 traz `Retry-After`: a tela diz quando dá para enviar de novo e não reenvia sozinha.
 */

const NOMES: Record<QuemResponde, { quem: string; para: string }> = {
  central: { quem: 'Central de Relacionamento', para: 'a Central' },
  apm: { quem: 'Equipe APM', para: 'a APM' },
};

const ESTADO_MENSAGEM: Record<MensagemConversa['estado'], string | null> = {
  enviada: null,
  enviando: 'Enviando…',
  falhou: 'Não enviada',
};

type Estado =
  | { fase: 'carregando' }
  | { fase: 'erro'; falha: unknown }
  | { fase: 'pronta'; dados: DadosConversa; atualizando: boolean };

function abortado(falha: unknown): boolean {
  return falha instanceof DOMException && falha.name === 'AbortError';
}

/** "em 12 minutos" / "em 1 hora" a partir dos segundos do `Retry-After`. */
export function esperaPorExtenso(segundos: number): string {
  if (segundos < 60) return 'em alguns segundos';
  const minutos = Math.ceil(segundos / 60);
  if (minutos < 60) return minutos === 1 ? 'em 1 minuto' : `em ${minutos} minutos`;
  const horas = Math.ceil(minutos / 60);
  return horas === 1 ? 'em 1 hora' : `em ${horas} horas`;
}

function Mensagem({ mensagem, quemResponde }: { mensagem: MensagemConversa; quemResponde: string }) {
  const minha = mensagem.autor === 'voce';
  const quando = dataDaApi(mensagem.quando);
  const estado = ESTADO_MENSAGEM[mensagem.estado];
  const classes = ['conversa__mensagem', minha ? 'conversa__mensagem--minha' : 'conversa__mensagem--central'];
  if (mensagem.estado === 'falhou') classes.push('conversa__mensagem--falhou');
  return (
    <li className={classes.join(' ')} data-estado={mensagem.estado}>
      <p className="conversa__autor">{minha ? 'Você' : quemResponde}</p>
      <p className="conversa__texto">{mensagem.texto}</p>
      <p className="conversa__meta">
        {quando ? <time dateTime={quando.toISOString()}>{dataHoraBR(quando)}</time> : null}
        {estado ? (
          <span className="conversa__estado">
            <Icon nome={mensagem.estado === 'falhou' ? 'alerta' : 'relogio'} tamanho={13} />
            {estado}
          </span>
        ) : null}
      </p>
    </li>
  );
}

interface Props {
  solicitacaoId: string;
  /** Chamado depois de um envio aceito (a situação da solicitação pode ter mudado). */
  aoEnviar?: (() => void) | undefined;
}

export function Conversa({ solicitacaoId, aoEnviar }: Props) {
  const { mostrar, mostrarErro } = useToast();
  const [estado, setEstado] = useState<Estado>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);
  const [texto, setTexto] = useState('');
  const [erro, setErro] = useState<string | undefined>(undefined);
  const [enviando, setEnviando] = useState(false);
  const [espera, setEspera] = useState<string | null>(null);
  // Mesma chave em cada nova tentativa da MESMA mensagem; nova só depois de um envio aceito.
  const chave = useRef(novaChaveIdempotencia());
  const montado = useRef(true);
  const idTitulo = useId();

  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  useEffect(() => {
    const controle = new AbortController();
    setEstado({ fase: 'carregando' });
    listarMensagens(solicitacaoId, controle.signal).then(
      (dados) => setEstado({ fase: 'pronta', dados, atualizando: false }),
      (falha: unknown) => {
        if (abortado(falha)) return;
        registrarErroExibido(falha);
        setEstado({ fase: 'erro', falha });
      },
    );
    return () => controle.abort();
  }, [solicitacaoId, tentativa]);

  /** Relê sem tirar a conversa da tela. */
  const atualizar = useCallback(async () => {
    setEstado((atual) => (atual.fase === 'pronta' ? { ...atual, atualizando: true } : atual));
    try {
      const dados = await listarMensagens(solicitacaoId, undefined, true);
      if (montado.current) setEstado({ fase: 'pronta', dados, atualizando: false });
    } catch (falha) {
      if (!montado.current) return;
      mostrarErro(falha);
      setEstado((atual) => (atual.fase === 'pronta' ? { ...atual, atualizando: false } : atual));
    }
  }, [solicitacaoId, mostrarErro]);

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    const limpo = texto.trim();
    if (limpo.length < MENSAGEM_MIN) {
      setErro('Escreva sua mensagem antes de enviar.');
      return;
    }
    setErro(undefined);
    setEspera(null);
    setEnviando(true);
    try {
      await enviarMensagem(solicitacaoId, limpo, chave.current);
      chave.current = novaChaveIdempotencia();
      if (!montado.current) return;
      setTexto('');
      mostrar('Mensagem enviada');
      await atualizar();
      aoEnviar?.();
    } catch (falha) {
      if (!montado.current) return;
      const api = falha instanceof ApiError ? falha : null;
      const campo = api?.detalhes?.find((d) => d.campo === 'texto');
      if (campo) {
        setErro(campo.mensagem);
      } else if (api?.status === 429) {
        setEspera(api.retryAfter ? `${api.message} Você pode enviar de novo ${esperaPorExtenso(api.retryAfter)}.` : api.message);
        registrarErroExibido(falha);
      } else {
        mostrarErro(falha);
        // 409/403: a solicitação fechou ou deixou de aceitar mensagens — a tela relê o estado.
        if (api && (api.status === 409 || api.status === 403)) {
          await atualizar();
          aoEnviar?.();
        }
      }
    } finally {
      if (montado.current) setEnviando(false);
    }
  };

  const corpo = (() => {
    if (estado.fase === 'carregando') return <Skeleton variante="texto" quantidade={3} rotulo="Carregando a conversa…" />;
    if (estado.fase === 'erro') {
      const falha = estado.falha;
      return (
        <EstadoErro
          titulo="Não conseguimos carregar a conversa agora"
          mensagem={falha instanceof ApiError ? falha.message : 'Tente novamente em instantes.'}
          requestId={falha instanceof ApiError ? falha.requestId : null}
          aoTentarNovamente={() => setTentativa((t) => t + 1)}
        />
      );
    }
    const { dados, atualizando } = estado;
    const nomes = NOMES[dados.responde] ?? NOMES.apm;
    return (
      <>
        {dados.truncado ? <p className="conversa__aviso">Mensagens anteriores não exibidas.</p> : null}
        {dados.mensagens.length === 0 ? (
          <p className="conversa__vazia">
            {dados.pode_enviar
              ? `Nenhuma mensagem ainda. Se quiser complementar o pedido, escreva para ${nomes.para}.`
              : 'Nenhuma mensagem nesta solicitação.'}
          </p>
        ) : (
          <ol className="conversa__lista" aria-label="Mensagens da conversa">
            {dados.mensagens.map((m) => (
              <Mensagem key={m.id} mensagem={m} quemResponde={nomes.quem} />
            ))}
          </ol>
        )}
        <div className="botoes">
          <button
            type="button"
            className="botao botao--secundario"
            onClick={() => void atualizar()}
            disabled={atualizando}
            aria-busy={atualizando}
          >
            <Icon nome="recarregar" tamanho={16} />
            {atualizando ? 'Atualizando…' : 'Atualizar conversa'}
          </button>
        </div>

        {dados.pode_enviar ? (
          <form className="formulario conversa__envio" onSubmit={(e) => void enviar(e)} noValidate>
            <Campo
              id={`mensagem-${solicitacaoId}`}
              rotulo={`Escreva para ${nomes.para}`}
              erro={erro}
              dica={`${texto.length} de ${MENSAGEM_MAX} caracteres`}
            >
              {(a) => (
                <textarea
                  {...a}
                  className="campo__entrada campo__entrada--texto"
                  rows={4}
                  maxLength={MENSAGEM_MAX}
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  required
                />
              )}
            </Campo>
            {espera ? (
              <p className="aviso" role="alert">
                {espera}
              </p>
            ) : null}
            <div className="botoes">
              <button type="submit" className="botao botao--primario" disabled={enviando} aria-busy={enviando}>
                {enviando ? 'Enviando…' : 'Enviar mensagem'}
              </button>
            </div>
          </form>
        ) : dados.motivo_bloqueio === 'aguardando_envio' ? (
          <p className="aviso">Sua solicitação está sendo encaminhada. Em instantes você poderá enviar mensagens por aqui.</p>
        ) : dados.motivo_bloqueio === 'encerrada' ? (
          <div className="aviso">
            <p>Esta solicitação foi encerrada.</p>
            <p>
              <LinkInterno para="/solicitacoes/nova" className="link-texto">
                Abrir nova solicitação
                <Icon nome="seta" tamanho={14} />
              </LinkInterno>
            </p>
          </div>
        ) : dados.motivo_bloqueio === 'nao_permitida' ? (
          <div className="aviso">
            <p>Esta conversa foi encerrada pela Central. Para falar conosco, abra uma nova solicitação.</p>
            <p>
              <LinkInterno para="/solicitacoes/nova" className="link-texto">
                Abrir nova solicitação
                <Icon nome="seta" tamanho={14} />
              </LinkInterno>
            </p>
          </div>
        ) : null}
      </>
    );
  })();

  return (
    <section className="cartao secao-solicitacao conversa" aria-labelledby={idTitulo}>
      <h2 className="secao__titulo" id={idTitulo}>
        Conversa
      </h2>
      {corpo}
    </section>
  );
}
