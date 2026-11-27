import { Link } from 'react-router';
import { EstadoVazio } from '../components/EstadoVazio';
import { Icon, type NomeIcone } from '../components/Icon';
import { LinkInterno } from '../components/LinkInterno';
import { useSessao } from '../state/SessaoContext';

/** Atalhos só para telas que já existem; nada de contagem ou valor sem fonte (regra 19, LA-14). */
const ATALHOS: readonly { para: string; icone: NomeIcone; titulo: string; texto: string }[] = [
  {
    para: '/carteirinha',
    icone: 'cartao',
    titulo: 'Carteirinha digital',
    texto: 'Seu QR de verificação para parceiros, eventos e consultório.',
  },
  {
    para: '/perfil',
    icone: 'usuario',
    titulo: 'Meu perfil',
    texto: 'Contato, e-mail e foto do seu cadastro na APM.',
  },
];

/**
 * Início no visual do "Painel" do mockup (ADR-0017), com dados reais da sessão.
 * Os blocos de valor, agenda e recomendações chegam com as suas fontes (Fase 4).
 */
export function Inicio() {
  const { sessao } = useSessao();
  const { nome_exibicao, tipo, status } = sessao.associado;
  // Como a pessoa pediu para ser chamada (P13); sem isso, o primeiro nome, sem título (DEC-26).
  const nome = sessao.preferencias.tratamento ?? nome_exibicao;
  const selo = [tipo, status].filter(Boolean).join(' · ');

  return (
    <>
      <section className="hero-inicio" aria-labelledby="hero-inicio-titulo">
        <div className="hero-inicio__conteudo">
          {selo ? <span className="selo vidro--escuro">{selo}</span> : null}
          <h2 id="hero-inicio-titulo" className="hero-inicio__titulo">
            {`Olá${nome ? `, ${nome}` : ''}. O cuidado com a sua prática também aparece nos detalhes.`}
          </h2>
          <p className="hero-inicio__texto">
            Aqui você acompanha o que a APM coloca à sua disposição, em um só lugar.
          </p>
          {/* Um único botão principal por bloco; a ação secundária vira link de texto (spec v2 §3.2). */}
          <div className="botoes">
            <Link to="/carteirinha" className="botao botao--claro">
              Ver minha carteirinha
            </Link>
            <Link to="/perfil" className="link-texto link-texto--claro">
              Atualizar meu perfil
              <Icon nome="seta" tamanho={14} />
            </Link>
          </div>
        </div>
      </section>

      <div className="grade-atalhos">
        {ATALHOS.map((a) => (
          <LinkInterno key={a.para} para={a.para} className="atalho vidro">
            <span className="atalho__topo">
              <span className="atalho__icone" aria-hidden="true">
                <Icon nome={a.icone} tamanho={20} />
              </span>
              <span className="atalho__seta" aria-hidden="true">
                <Icon nome="seta" tamanho={18} />
              </span>
            </span>
            <span className="atalho__titulo">{a.titulo}</span>
            <span className="atalho__texto">{a.texto}</span>
          </LinkInterno>
        ))}
      </div>

      <EstadoVazio titulo="Mais da Minha APM a caminho">
        Benefícios, clube de vantagens, notícias, eventos e solicitações chegam nas próximas entregas.
      </EstadoVazio>
    </>
  );
}
