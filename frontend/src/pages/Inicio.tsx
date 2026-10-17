import { EstadoVazio } from '../components/EstadoVazio';
import { useSessao } from '../state/SessaoContext';

/** Início (spec tela 1). Fase 1: saudação; os blocos chegam na Fase 4. */
export function Inicio() {
  const { sessao } = useSessao();
  const nome = sessao.associado.nome_exibicao;
  return (
    <>
      <p className="saudacao">
        Olá{nome ? ', ' : ''}
        {nome ? <strong>{nome}</strong> : null} — bom te ver por aqui.
      </p>
      <EstadoVazio titulo="A Minha APM está em construção">
        Os seus benefícios, a carteirinha digital, notícias e eventos chegam nas próximas entregas.
      </EstadoVazio>
    </>
  );
}
