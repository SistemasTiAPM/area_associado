import { useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { pularPergunta, responderPergunta, type Pergunta, type Preferencias } from '../api/privacidade';
import { useToast } from '../state/ToastContext';
import { Campo } from './Campo';
import { CheckboxGroup, RadioGroup } from './GrupoOpcoes';

interface Props {
  pergunta: Pergunta;
  /** Respondida: devolve o perfil declarado atualizado. */
  aoResponder: (preferencias: Preferencias) => void;
  /** Pulada: a pergunta some desta visita. */
  aoPular: () => void;
}

/**
 * Uma pergunta do perfil progressivo (P13: "uma pergunta por visita, em vez de
 * formulário longo"). Usada no "Complete seu perfil" e, na Onda 4, no bloco 3 da
 * home. O título e a ajuda vêm do servidor e dizem o que melhora com a resposta.
 */
export function PerguntaPerfil({ pergunta, aoResponder, aoPular }: Props) {
  const { mostrar, mostrarErro } = useToast();
  const [texto, setTexto] = useState('');
  const [escolhas, setEscolhas] = useState<string[]>([]);
  const [escolha, setEscolha] = useState<string | null>(null);
  const [erro, setErro] = useState<string | undefined>();
  const [ocupado, setOcupado] = useState(false);

  const resposta = pergunta.tipo === 'texto' ? texto.trim() : pergunta.tipo === 'multipla' ? escolhas : escolha;
  const vazia = resposta === null || resposta.length === 0;
  const nome = `pergunta-${pergunta.chave}`;

  const tratar = (falha: unknown) => {
    const detalhe = falha instanceof ApiError ? falha.detalhes?.[0]?.mensagem : undefined;
    setErro(detalhe);
    mostrarErro(falha);
  };

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (vazia || resposta === null) return;
    setOcupado(true);
    setErro(undefined);
    try {
      aoResponder(await responderPergunta(pergunta.chave, resposta));
      mostrar('Perfil atualizado');
    } catch (falha) {
      tratar(falha);
    } finally {
      setOcupado(false);
    }
  };

  const pular = async () => {
    setOcupado(true);
    try {
      await pularPergunta(pergunta.chave);
      aoPular();
    } catch (falha) {
      tratar(falha);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <form className="formulario pergunta-perfil" onSubmit={(e) => void enviar(e)} noValidate>
      {pergunta.tipo === 'texto' ? (
        <Campo id={nome} rotulo={pergunta.titulo} dica={pergunta.ajuda} erro={erro}>
          {(a) => (
            <input {...a} className="campo__entrada" type="text" autoComplete="honorific-prefix"
              maxLength={pergunta.maximo ?? 40} value={texto} onChange={(e) => setTexto(e.target.value)} />
          )}
        </Campo>
      ) : pergunta.tipo === 'multipla' ? (
        <CheckboxGroup nome={nome} legenda={pergunta.titulo} dica={pergunta.ajuda} erro={erro}
          opcoes={pergunta.opcoes} valores={escolhas} aoMudar={setEscolhas} />
      ) : (
        <RadioGroup nome={nome} legenda={pergunta.titulo} dica={pergunta.ajuda} erro={erro}
          opcoes={pergunta.opcoes} valor={escolha} aoMudar={setEscolha} />
      )}
      <div className="botoes">
        <button type="submit" className="botao botao--primario" disabled={ocupado || vazia}>
          Salvar resposta
        </button>
        <button type="button" className="link-texto" disabled={ocupado} onClick={() => void pular()}>
          Responder depois
        </button>
      </div>
    </form>
  );
}
