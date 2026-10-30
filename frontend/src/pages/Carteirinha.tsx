import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';
import {
  URL_CARTEIRINHA_IMAGEM,
  URL_CARTEIRINHA_PDF,
  compartilharCarteirinha,
  obterCarteirinha,
  type Carteirinha,
} from '../api/carteirinha';
import { ApiError } from '../api/client';
import { EstadoErro } from '../components/EstadoErro';
import { Icon, type NomeIcone } from '../components/Icon';
import { dataBR } from '../lib/formato';
import { registrarUso } from '../lib/analytics';
import { registrarErroExibido } from '../lib/erros';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';

/** Textos do mockup (ADR-0017), neutros em gênero (LA-19). */
const USOS: readonly { icone: NomeIcone; titulo: string; texto: string }[] = [
  { icone: 'loja', titulo: 'Parceiros do clube', texto: 'Mostre no caixa para liberar o desconto da associação.' },
  { icone: 'local', titulo: 'Eventos e congressos', texto: 'Check-in rápido pelo QR code na entrada.' },
  { icone: 'estetoscopio', titulo: 'No consultório', texto: 'Pacientes confirmam a sua associação à APM.' },
];

type Estado = { fase: 'carregando' } | { fase: 'erro'; falha: unknown } | { fase: 'pronta'; dados: Carteirinha };

/** Texto da carteirinha revogada (RF-CA-08; proposta, voz §3.3). */
export const TEXTO_REVOGADA = 'Esta carteirinha está sem validade. Fale com a Central.';

/**
 * Carteirinha digital (spec v2 P07; RF-CA). Validade omitida até P-10;
 * "na APM desde {ano}" no lugar de "associada desde" (gênero não vem do IdP — LA-19).
 * Número de associado e downloads gerados no servidor (RF-CA-07, TI-46: `<a download>`
 * de mesma origem, sem blob); revogada (RF-CA-08, TI-45) = sem QR, sem compartilhar,
 * sem downloads e com caminho para a Central. Os downloads o servidor registra
 * (`carteirinha_baixar`).
 */
export function PaginaCarteirinha() {
  const { sessao } = useSessao();
  const { mostrar, mostrarErro } = useToast();
  const [estado, setEstado] = useState<Estado>({ fase: 'carregando' });
  const [linkManual, setLinkManual] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setEstado({ fase: 'carregando' });
    try {
      setEstado({ fase: 'pronta', dados: await obterCarteirinha() });
    } catch (falha) {
      registrarErroExibido(falha);
      setEstado({ fase: 'erro', falha });
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const compartilhar = async () => {
    try {
      const { url } = await compartilharCarteirinha();
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(url);
          mostrar('Link de verificação copiado');
          return;
        } catch (falha) {
          if (!(falha instanceof DOMException)) throw falha;
        }
      }
      setLinkManual(url); // sem permissão de área de transferência: cópia manual
    } catch (falha) {
      mostrarErro(falha);
      // Revogada entre o carregamento e o clique: a tela passa ao estado sem validade.
      if (falha instanceof ApiError && falha.erro === 'carteirinha_revogada') void carregar();
    }
  };

  if (estado.fase === 'carregando') {
    return (
      <p className="carregando" role="status" aria-busy="true">
        Carregando sua carteirinha…
      </p>
    );
  }
  if (estado.fase === 'erro') {
    const falha = estado.falha;
    return (
      <EstadoErro
        titulo="Não foi possível carregar sua carteirinha"
        mensagem={falha instanceof ApiError ? falha.message : 'Tente novamente em instantes.'}
        requestId={falha instanceof ApiError ? falha.requestId : null}
        aoTentarNovamente={() => void carregar()}
      />
    );
  }

  const d = estado.dados;
  const revogada = d.revogada === true;
  const crm = d.crm ? `CRM-${d.crm_uf ?? ''} ${d.crm}` : null;
  const desde = d.membro_desde ? `na APM desde ${d.membro_desde}` : null;
  return (
    <>
      <div className="grade-carteirinha">
        <figure
          className={revogada ? 'carteirinha carteirinha--revogada' : 'carteirinha'}
          aria-label={`Carteirinha digital de ${d.nome ?? 'associado'}`}
        >
          <div className="carteirinha__topo">
            <span className="carteirinha__marca">
              <span className="carteirinha__sigla" aria-hidden="true">
                APM
              </span>
              <span className="carteirinha__legenda">Associação Paulista de Medicina</span>
            </span>
            <span className="carteirinha__selo vidro--escuro">
              <Icon nome="escudo" tamanho={14} />
              {d.tipo_associado ?? 'Associado'}
            </span>
          </div>
          <div className="carteirinha__corpo">
            <div>
              <p className="carteirinha__nome">{d.nome}</p>
              {d.num_contato ? <p className="carteirinha__linha carteirinha__numero">Associado nº {d.num_contato}</p> : null}
              <p className="carteirinha__linha">{[crm, desde].filter(Boolean).join(' · ')}</p>
              <p className="carteirinha__linha carteirinha__linha--destaque">
                {revogada ? 'Sem validade' : `Situação: ${d.status_associativo ?? 'indisponível'}`}
              </p>
            </div>
            {!revogada && d.qr ? (
              <span className="carteirinha__qr">
                <img src={d.qr} alt="QR code de verificação da carteirinha" width={92} height={92} />
              </span>
            ) : null}
          </div>
        </figure>

        {revogada ? (
          <section className="carteirinha-info cartao" aria-labelledby="carteirinha-info-titulo">
            <h2 className="secao__titulo" id="carteirinha-info-titulo">
              Carteirinha sem validade
            </h2>
            <p className="aviso" role="status">
              {TEXTO_REVOGADA}
            </p>
            <p className="carteirinha-info__texto">
              A Central de Relacionamento confere a sua situação na APM e orienta os próximos passos.
            </p>
            {sessao.recursos?.ajuda ? (
              <div className="carteirinha-info__acoes">
                <Link to="/ajuda" className="botao botao--primario">
                  Falar com a Central
                </Link>
              </div>
            ) : null}
          </section>
        ) : (
          <section className="carteirinha-info cartao" aria-labelledby="carteirinha-info-titulo">
            <h2 className="secao__titulo" id="carteirinha-info-titulo">
              Sempre com você
            </h2>
            <p className="carteirinha-info__texto">
              Apresente em parceiros, eventos e no consultório. O QR code permite que qualquer pessoa confirme a sua
              associação à APM.
            </p>
            {d.verificado_em ? (
              <p className="secao__subtitulo">Situação confirmada no cadastro em {dataBR(new Date(d.verificado_em))}.</p>
            ) : null}
            <div className="carteirinha-info__acoes">
              {sessao.flags.wallet ? (
                <button
                  type="button"
                  className="botao botao--secundario"
                  onClick={() => registrarUso({ acao: 'wallet_adicionar', entidade: 'carteirinha' })}
                >
                  + Adicionar à Wallet
                </button>
              ) : null}
              <button type="button" className="botao botao--primario" onClick={() => void compartilhar()}>
                Compartilhar
              </button>
            </div>
            {/* Downloads de mesma origem (`Content-Disposition: attachment`): sem fetch, sem blob, sem nova aba. */}
            <div className="carteirinha-info__downloads">
              <a className="link-texto" href={URL_CARTEIRINHA_IMAGEM} download>
                <Icon nome="baixar" tamanho={16} />
                Baixar imagem
              </a>
              <a className="link-texto" href={URL_CARTEIRINHA_PDF} download>
                <Icon nome="baixar" tamanho={16} />
                Baixar PDF
              </a>
            </div>
            {linkManual ? (
              <div className="campo">
                <label className="campo__rotulo" htmlFor="link-verificacao">
                  Copie o link de verificação
                </label>
                <input id="link-verificacao" className="campo__entrada" readOnly value={linkManual}
                  onFocus={(e) => e.currentTarget.select()} />
              </div>
            ) : null}
          </section>
        )}
      </div>

      {revogada ? null : (
        <ul className="grade-usos" aria-label="Onde usar a carteirinha">
          {USOS.map((u) => (
            <li key={u.titulo} className="uso cartao">
              <span className="uso__icone" aria-hidden="true">
                <Icon nome={u.icone} tamanho={20} />
              </span>
              <span className="uso__textos">
                <b className="uso__titulo">{u.titulo}</b>
                <span className="uso__texto">{u.texto}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
