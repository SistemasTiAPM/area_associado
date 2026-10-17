import { useCallback, useEffect, useState } from 'react';
import { compartilharCarteirinha, obterCarteirinha, type Carteirinha } from '../api/carteirinha';
import { EstadoVazio } from '../components/EstadoVazio';
import { Icon } from '../components/Icon';
import { dataBR } from '../lib/formato';
import { registrarUso } from '../lib/analytics';
import { useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';

type Estado = { fase: 'carregando' } | { fase: 'erro' } | { fase: 'pronta'; dados: Carteirinha };

/**
 * Carteirinha digital (spec tela 8; RF-CA). Validade omitida até P-10;
 * "na APM desde {ano}" no lugar de "associada desde" (gênero não vem do IdP — LA-19).
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
      mostrarErro(falha);
      setEstado({ fase: 'erro' });
    }
  }, [mostrarErro]);

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
    return (
      <EstadoVazio titulo="Não foi possível carregar sua carteirinha">
        <button type="button" className="botao botao--primario" onClick={() => void carregar()}>
          Tentar novamente
        </button>
      </EstadoVazio>
    );
  }

  const d = estado.dados;
  const crm = d.crm ? `CRM-${d.crm_uf ?? ''} ${d.crm}` : null;
  const desde = d.membro_desde ? `na APM desde ${d.membro_desde}` : null;
  return (
    <div className="grade-carteirinha">
      <figure className="carteirinha" aria-label={`Carteirinha digital de ${d.nome ?? 'associado'}`}>
        <div className="carteirinha__topo">
          <span className="carteirinha__marca">
            <span className="carteirinha__sigla" aria-hidden="true">
              APM
            </span>
            <span className="carteirinha__legenda">Associação Paulista de Medicina</span>
          </span>
          <span className="carteirinha__selo">
            <Icon nome="escudo" tamanho={14} />
            MEMBRO
          </span>
        </div>
        <div className="carteirinha__corpo">
          <div>
            <p className="carteirinha__nome">{d.nome}</p>
            <p className="carteirinha__linha">{[crm, desde].filter(Boolean).join(' · ')}</p>
            <p className="carteirinha__linha">
              {d.tipo_associado ? `${d.tipo_associado} · ` : ''}
              {d.status_associativo ?? 'situação indisponível'}
            </p>
          </div>
          <img className="carteirinha__qr" src={d.qr} alt="QR code de verificação da carteirinha" width={96} height={96} />
        </div>
      </figure>

      <section className="carteirinha-info">
        <h2 className="carteirinha-info__titulo">Sua carteirinha digital</h2>
        <p className="carteirinha-info__texto">
          Apresente em parceiros, eventos e no consultório. O QR code permite que qualquer pessoa confirme que você é membro
          da APM.
        </p>
        {d.verificado_em ? (
          <p className="secao__subtitulo">Situação confirmada no cadastro em {dataBR(new Date(d.verificado_em))}.</p>
        ) : null}
        <div className="botoes">
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
    </div>
  );
}
