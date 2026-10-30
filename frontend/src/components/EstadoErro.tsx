import { Icon } from './Icon';

interface Props {
  /** O que aconteceu (voz §3.3: sem jargão; "não conseguimos…", nunca "erro 500"). */
  titulo?: string;
  /** O que fazer. Vem da API (`mensagem`) ou do chamador. */
  mensagem: string;
  /** `X-Request-Id` da resposta, para a Central localizar o atendimento. */
  requestId?: string | null | undefined;
  /** Sem callback, o botão não aparece (ex.: 404 recurso desligado). */
  aoTentarNovamente?: (() => void) | undefined;
  ocupado?: boolean;
  rotuloBotao?: string;
  className?: string;
}

/**
 * Bloco de erro de uma tela ou de um bloco da tela: `role=alert`, título,
 * mensagem, código de atendimento (`request_id`) e "Tentar novamente". Puro:
 * recebe a mensagem já pronta; quem chama a API decide o que mostrar.
 */
export function EstadoErro({
  titulo = 'Não conseguimos carregar esta parte agora',
  mensagem,
  requestId,
  aoTentarNovamente,
  ocupado = false,
  rotuloBotao = 'Tentar novamente',
  className,
}: Props) {
  return (
    <section className={className ? `cartao estado-erro ${className}` : 'cartao estado-erro'} role="alert">
      <span className="estado-erro__icone" aria-hidden="true">
        <Icon nome="alerta" tamanho={22} />
      </span>
      <div className="estado-erro__textos">
        <h2 className="estado-erro__titulo">{titulo}</h2>
        <p className="estado-erro__mensagem">{mensagem}</p>
        {requestId ? (
          <p className="estado-erro__codigo">
            Código para a Central de Relacionamento: <code>{requestId}</code>
          </p>
        ) : null}
      </div>
      {aoTentarNovamente ? (
        <button type="button" className="botao botao--primario estado-erro__botao" onClick={aoTentarNovamente} disabled={ocupado} aria-busy={ocupado}>
          <Icon nome="recarregar" tamanho={16} />
          {rotuloBotao}
        </button>
      ) : null}
    </section>
  );
}
