import type { AtorLinhaDoTempo, EventoLinhaDoTempo } from '../api/solicitacoes';
import { dataDaApi, dataHoraBR } from '../lib/formato';

const ATOR: Record<AtorLinhaDoTempo, string> = {
  voce: 'Você',
  equipe_apm: 'Equipe APM',
  parceiro: 'Parceiro',
  sistema: 'Minha APM',
};

/**
 * Linha do tempo de uma solicitação (RF-SO-02, RF-SO-13): `ol` em ordem
 * cronológica, cada passo com data e hora (America/Sao_Paulo), rótulo, quem fez
 * e a mensagem pública; o passo atual leva `aria-current="step"`. Puro.
 */
export function LinhaDoTempo({ eventos, rotulo = 'Linha do tempo da solicitação' }: { eventos: readonly EventoLinhaDoTempo[]; rotulo?: string }) {
  const ordenados = [...eventos].sort((a, b) => (dataDaApi(a.quando)?.getTime() ?? 0) - (dataDaApi(b.quando)?.getTime() ?? 0));
  const ultimo = ordenados.length - 1;
  return (
    <ol className="linha-tempo" aria-label={rotulo}>
      {ordenados.map((evento, indice) => {
        const quando = dataDaApi(evento.quando);
        const atual = indice === ultimo;
        return (
          <li
            key={`${evento.quando}-${indice}`}
            className={atual ? 'linha-tempo__passo linha-tempo__passo--atual' : 'linha-tempo__passo'}
            aria-current={atual ? 'step' : undefined}
          >
            <span className="linha-tempo__marcador" aria-hidden="true" />
            <div className="linha-tempo__textos">
              <p className="linha-tempo__rotulo">
                {evento.rotulo}
                {atual ? <span className="visualmente-oculto"> (situação atual)</span> : null}
              </p>
              <p className="linha-tempo__meta">
                {quando ? <time dateTime={evento.quando}>{dataHoraBR(quando)}</time> : null}
                {quando ? ' · ' : null}
                {ATOR[evento.ator] ?? 'Minha APM'}
              </p>
              {evento.mensagem ? <p className="linha-tempo__mensagem">{evento.mensagem}</p> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
