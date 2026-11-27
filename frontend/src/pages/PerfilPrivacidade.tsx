import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { urlReautenticacao } from '../api/perfil';
import {
  PALAVRA_CONFIRMACAO,
  decidirConsentimento,
  exportarDados,
  listarConsentimentos,
  listarPedidosTitular,
  obterPergunta,
  obterPreferencias,
  pedirExclusao,
  salvarPreferencias,
  type CamposPreferencias,
  type Consentimento,
  type PedidoTitular,
  type PedidosTitular,
  type Pergunta,
  type Preferencias,
} from '../api/privacidade';
import { novaChaveIdempotencia } from '../api/solicitacoes';
import type { TamanhoFonte } from '../api/tipos';
import { Campo } from '../components/Campo';
import { ControleFonte } from '../components/ControleFonte';
import { Dialogo } from '../components/Dialogo';
import { CheckboxGroup, RadioGroup } from '../components/GrupoOpcoes';
import { LinkInterno } from '../components/LinkInterno';
import { PerguntaPerfil } from '../components/PerguntaPerfil';
import { baixarJson, nomeArquivoDados } from '../lib/baixar';
import { dataBR, dataDaApi, dataHoraBR } from '../lib/formato';
import { aplicarFonte, useSessao } from '../state/SessaoContext';
import { useToast } from '../state/ToastContext';

type Carga<T> = { fase: 'carregando' } | { fase: 'erro' } | { fase: 'pronto'; dados: T };

function quando(valor: string | null, comHora = false): string {
  const d = dataDaApi(valor);
  if (!d) return '';
  return comHora ? dataHoraBR(d) : dataBR(d);
}

function Carregando({ texto }: { texto: string }) {
  return (
    <p className="carregando" role="status" aria-busy="true">
      {texto}
    </p>
  );
}

function ErroDeCarga({ texto, aoTentar }: { texto: string; aoTentar: () => void }) {
  return (
    <div className="aviso" role="alert">
      <p>{texto}</p>
      <div className="botoes">
        <button type="button" className="botao botao--secundario" onClick={aoTentar}>
          Tentar novamente
        </button>
      </div>
    </div>
  );
}

/* --------------------------------------------------- complete seu perfil */
function SecaoCompletePerfil({ aoResponder }: { aoResponder: (p: Preferencias) => void }) {
  const [pergunta, setPergunta] = useState<Pergunta | null>(null);

  useEffect(() => {
    let ativo = true;
    obterPergunta()
      .then((r) => {
        if (ativo) setPergunta(r.pergunta);
      })
      // Sem pergunta a tela segue igual: o perfil inteiro continua editável logo abaixo.
      .catch(() => undefined);
    return () => {
      ativo = false;
    };
  }, []);

  if (pergunta === null) return null;
  // Uma pergunta por visita (P13): respondida ou pulada, o bloco some até a próxima.
  return (
    <section className="cartao secao-perfil secao-perfil--destaque" aria-labelledby="titulo-complete">
      <h2 className="secao__titulo" id="titulo-complete">
        Complete seu perfil
      </h2>
      <p className="secao__subtitulo">Uma pergunta por vez. Com as respostas, as recomendações ficam mais próximas da sua rotina.</p>
      <PerguntaPerfil
        pergunta={pergunta}
        aoResponder={(p) => {
          setPergunta(null);
          aoResponder(p);
        }}
        aoPular={() => setPergunta(null)}
      />
    </section>
  );
}

/* ----------------------------------------------------------- preferências */
function iguais(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((valor, i) => valor === b[i]);
}

function SecaoPreferencias({ preferencias, aoSalvar }: { preferencias: Preferencias; aoSalvar: (p: Preferencias) => void }) {
  const { mostrar, mostrarErro } = useToast();
  const { recarregar } = useSessao();
  const [tratamento, setTratamento] = useState(preferencias.tratamento ?? '');
  const [atuacao, setAtuacao] = useState(preferencias.atuacao);
  const [temas, setTemas] = useState(preferencias.temas);
  const [frequencia, setFrequencia] = useState(preferencias.frequencia);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState(false);

  const mudancas: CamposPreferencias = {};
  if (tratamento.trim() !== (preferencias.tratamento ?? '')) mudancas.tratamento = tratamento.trim() || null;
  if (!iguais(atuacao, preferencias.atuacao)) mudancas.atuacao = atuacao;
  if (!iguais(temas, preferencias.temas)) mudancas.temas = temas;
  if (frequencia !== preferencias.frequencia) mudancas.frequencia = frequencia;
  const mudou = Object.keys(mudancas).length > 0;

  const salvar = async (evento: FormEvent) => {
    evento.preventDefault();
    if (!mudou) return;
    setOcupado(true);
    setErros({});
    try {
      const novo = await salvarPreferencias(mudancas);
      aoSalvar(novo);
      mostrar('Preferências salvas');
      // A saudação do shell usa o tratamento: a sessão é relida em silêncio.
      if ('tratamento' in mudancas) await recarregar();
    } catch (falha) {
      if (falha instanceof ApiError && falha.detalhes) {
        setErros(Object.fromEntries(falha.detalhes.map((d) => [d.campo, d.mensagem])));
      }
      mostrarErro(falha);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-preferencias">
      <h2 className="secao__titulo" id="titulo-preferencias">
        Sobre você
      </h2>
      <p className="secao__subtitulo">
        Estas respostas ficam na Minha APM e servem para mostrar primeiro o que combina com a sua rotina. Não alteram o
        seu cadastro.
      </p>
      <form className="formulario" onSubmit={(e) => void salvar(e)} noValidate>
        <Campo id="pref-tratamento" rotulo="Como prefere ser chamado" erro={erros.tratamento}
          dica="Por exemplo: Dra. Ana. Em branco, usamos o seu primeiro nome.">
          {(a) => (
            <input {...a} className="campo__entrada" type="text" autoComplete="honorific-prefix" maxLength={40}
              value={tratamento} onChange={(e) => setTratamento(e.target.value)} />
          )}
        </Campo>
        <CheckboxGroup nome="pref-atuacao" legenda="Onde você atua" erro={erros.atuacao}
          opcoes={preferencias.opcoes.atuacao} valores={atuacao} aoMudar={setAtuacao} />
        <CheckboxGroup nome="pref-temas" legenda="Temas de interesse" erro={erros.temas}
          opcoes={preferencias.opcoes.temas} valores={temas} aoMudar={setTemas} />
        <RadioGroup nome="pref-frequencia" legenda="Novidades da APM" erro={erros.frequencia}
          dica="As novidades chegam pelo seu e-mail de acesso. Avisos sobre seus pedidos e pagamentos chegam sempre."
          opcoes={preferencias.opcoes.frequencia} valor={frequencia} aoMudar={setFrequencia} />
        <div className="botoes">
          <button type="submit" className="botao botao--primario" disabled={ocupado || !mudou}>
            Salvar preferências
          </button>
        </div>
      </form>
    </section>
  );
}

/* --------------------------------------------------------- tamanho do texto */
function SecaoTexto({ preferencias, aoSalvar }: { preferencias: Preferencias; aoSalvar: (p: Preferencias) => void }) {
  const { mostrarErro } = useToast();
  const { recarregar } = useSessao();
  const [ocupado, setOcupado] = useState(false);

  const mudar = async (fonte: TamanhoFonte) => {
    setOcupado(true);
    try {
      const novo = await salvarPreferencias({ fonte });
      // Só depois de o servidor aceitar (nada "otimista"): a tela e a próxima visita ficam iguais.
      aplicarFonte(novo.fonte);
      aoSalvar(novo);
      await recarregar();
    } catch (falha) {
      mostrarErro(falha);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-texto">
      <h2 className="secao__titulo" id="titulo-texto">
        Tamanho do texto
      </h2>
      <p className="secao__subtitulo">Vale para toda a Minha APM, em qualquer aparelho em que você entrar.</p>
      <ControleFonte valor={preferencias.fonte} opcoes={preferencias.opcoes.fonte} aoMudar={(f) => void mudar(f)} ocupado={ocupado} />
    </section>
  );
}

/* ---------------------------------------------------------- consentimentos */
const ROTULO_HISTORICO: Record<string, string> = { concedido: 'Autorizou', retirado: 'Retirou a autorização' };

function ItemConsentimento({ item, aoMudar, aoDesatualizar }: {
  item: Consentimento;
  aoMudar: (novo: Consentimento) => void;
  aoDesatualizar: () => void;
}) {
  const { mostrar, mostrarErro } = useToast();
  const [ocupado, setOcupado] = useState(false);
  const id = `consentimento-${item.finalidade}-${item.canal}`;
  // Autorização dada sobre um texto antigo não vale como marcada: a pessoa confirma o novo.
  const marcado = item.concedido && !item.texto_mudou;

  const decidir = async (concedido: boolean) => {
    setOcupado(true);
    try {
      aoMudar(await decidirConsentimento(item, concedido));
      mostrar(concedido ? 'Autorização registrada' : 'Autorização retirada');
    } catch (falha) {
      mostrarErro(falha);
      if (falha instanceof ApiError && falha.erro === 'versao_desatualizada') aoDesatualizar();
    } finally {
      setOcupado(false);
    }
  };

  return (
    <li className="consentimento">
      <h3 className="consentimento__titulo">{item.titulo}</h3>
      <p className="consentimento__texto" id={`${id}-texto`}>
        {item.texto}
      </p>
      {item.texto_mudou ? (
        <p className="aviso" role="status">
          Este texto foi atualizado depois da sua autorização. Leia a versão nova e confirme de novo, se concordar.
        </p>
      ) : null}
      <label className="consentimento__controle" htmlFor={id}>
        <input id={id} type="checkbox" className="consentimento__caixa" checked={marcado} disabled={ocupado}
          aria-describedby={`${id}-texto`} onChange={(e) => void decidir(e.target.checked)} />
        <span>Autorizo</span>
      </label>
      <p className="consentimento__meta">
        {item.registrado_em
          ? `${marcado ? 'Autorizado' : item.concedido ? 'Autorizado na versão anterior' : 'Autorização retirada'} em ${quando(item.registrado_em, true)} · texto ${item.versao_registrada ?? item.versao}`
          : `Sem autorização registrada · texto ${item.versao}`}
      </p>
      {item.historico.length > 0 ? (
        <details className="consentimento__historico">
          <summary>Histórico</summary>
          <ol className="consentimento__linhas">
            {item.historico.map((h, i) => (
              <li key={`${h.registrado_em ?? ''}-${i}`}>
                {ROTULO_HISTORICO[h.valor] ?? h.valor} em {quando(h.registrado_em, true)} · texto {h.versao}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </li>
  );
}

function SecaoConsentimentos() {
  const [carga, setCarga] = useState<Carga<Consentimento[]>>({ fase: 'carregando' });

  const carregar = useCallback(async () => {
    setCarga({ fase: 'carregando' });
    try {
      setCarga({ fase: 'pronto', dados: (await listarConsentimentos()).itens });
    } catch (falha) {
      if (!(falha instanceof ApiError)) throw falha;
      setCarga({ fase: 'erro' });
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-consentimentos">
      <h2 className="secao__titulo" id="titulo-consentimentos">
        Autorizações
      </h2>
      <p className="secao__subtitulo">
        Você decide o que a APM pode enviar além dos avisos sobre seus pedidos e pagamentos. Pode mudar de ideia quando
        quiser.
      </p>
      {carga.fase === 'carregando' ? (
        <Carregando texto="Carregando suas autorizações…" />
      ) : carga.fase === 'erro' ? (
        <ErroDeCarga texto="Não foi possível carregar suas autorizações." aoTentar={() => void carregar()} />
      ) : carga.dados.length === 0 ? (
        <p>Nenhuma autorização é pedida no momento.</p>
      ) : (
        <ul className="consentimentos">
          {carga.dados.map((item) => (
            <ItemConsentimento
              key={`${item.finalidade}-${item.canal}`}
              item={item}
              aoMudar={(novo) =>
                setCarga({
                  fase: 'pronto',
                  dados: carga.dados.map((c) => (c.finalidade === novo.finalidade && c.canal === novo.canal ? novo : c)),
                })
              }
              aoDesatualizar={() => void carregar()}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

/* --------------------------------------------------------------- meus dados */
const ROTULO_STATUS: Record<PedidoTitular['status'], string> = {
  registrado: 'Recebido',
  em_analise: 'Em análise',
  concluido: 'Concluído',
  recusado: 'Não atendido',
  cancelado: 'Cancelado',
};

function AvisoReautenticacao({ texto }: { texto: string }) {
  return (
    <div className="aviso" role="status">
      <p>{texto} Você volta para esta página em seguida.</p>
      <div className="botoes">
        <a className="botao botao--primario" href={urlReautenticacao()}>
          Confirmar minha identidade
        </a>
      </div>
    </div>
  );
}

function DialogoExclusao({ aberto, aoFechar, aoPedir }: { aberto: boolean; aoFechar: () => void; aoPedir: () => Promise<void> }) {
  const [palavra, setPalavra] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const confirmado = palavra.trim().toUpperCase() === PALAVRA_CONFIRMACAO;

  // Estável: o foco preso do diálogo recomeça quando `aoFechar` muda de identidade,
  // e a cada tecla o foco voltaria ao botão de fechar.
  const fechar = useCallback(() => {
    setPalavra('');
    aoFechar();
  }, [aoFechar]);
  const pedir = async () => {
    setOcupado(true);
    try {
      await aoPedir();
      setPalavra('');
    } finally {
      setOcupado(false);
    }
  };

  return (
    <Dialogo
      aberto={aberto}
      destrutivo
      titulo="Pedir a exclusão dos meus dados"
      descricao="O pedido é analisado pelo encarregado de dados da APM antes de ser atendido."
      aoFechar={fechar}
      rotuloFechar="Desistir"
      acoes={
        <>
          <button type="button" className="botao botao--destrutivo" disabled={!confirmado || ocupado} onClick={() => void pedir()}>
            Pedir exclusão
          </button>
          <button type="button" className="botao botao--secundario" onClick={fechar}>
            Desistir
          </button>
        </>
      }
    >
      <ul className="lista-simples">
        <li>O que a Minha APM guarda sobre você deixa de estar ligado a você: contatos, preferências e textos das suas solicitações.</li>
        <li>Não cancela a sua associação. Para isso, fale com a Central de Relacionamento.</li>
        <li>Se você continuar associado e entrar de novo, a área recria só o cadastro mínimo.</li>
        <li>Depois de atendido, não tem volta. Enquanto estiver em análise, você pode desistir em Solicitações.</li>
      </ul>
      <Campo id="exclusao-confirmacao" rotulo={`Para confirmar, digite ${PALAVRA_CONFIRMACAO}`}>
        {(a) => (
          <input {...a} className="campo__entrada" type="text" autoComplete="off" autoCapitalize="characters" spellCheck={false}
            maxLength={16} value={palavra} onChange={(e) => setPalavra(e.target.value)} />
        )}
      </Campo>
    </Dialogo>
  );
}

function SecaoDados() {
  const { mostrar, mostrarErro } = useToast();
  const [carga, setCarga] = useState<Carga<PedidosTitular>>({ fase: 'carregando' });
  const [precisaReauth, setPrecisaReauth] = useState(false);
  const [dialogo, setDialogo] = useState(false);
  const [baixando, setBaixando] = useState(false);
  const [chave, setChave] = useState(novaChaveIdempotencia);

  const carregar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCarga({ fase: 'carregando' });
    try {
      const dados = await listarPedidosTitular();
      setCarga({ fase: 'pronto', dados });
      setPrecisaReauth(dados.exige_reautenticacao);
    } catch (falha) {
      if (!(falha instanceof ApiError)) throw falha;
      if (!silencioso) setCarga({ fase: 'erro' });
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const fecharDialogo = useCallback(() => setDialogo(false), []);

  const tratar = (falha: unknown) => {
    if (falha instanceof ApiError && falha.erro === 'reautenticacao_necessaria') setPrecisaReauth(true);
    mostrarErro(falha);
  };

  const baixar = async () => {
    setBaixando(true);
    try {
      baixarJson(nomeArquivoDados(), await exportarDados());
      mostrar('Arquivo gerado');
      await carregar(true);
    } catch (falha) {
      tratar(falha);
      if (falha instanceof ApiError && falha.erro === 'limite_negocio') await carregar(true);
    } finally {
      setBaixando(false);
    }
  };

  const excluir = async () => {
    try {
      await pedirExclusao(PALAVRA_CONFIRMACAO, chave);
      setChave(novaChaveIdempotencia());
      setDialogo(false);
      mostrar('Pedido registrado');
      await carregar(true);
    } catch (falha) {
      tratar(falha);
      if (falha instanceof ApiError && falha.erro !== 'sem_conexao') setDialogo(false);
    }
  };

  return (
    <section className="cartao secao-perfil" aria-labelledby="titulo-dados">
      <h2 className="secao__titulo" id="titulo-dados">
        Seus dados
      </h2>
      {carga.fase === 'carregando' ? (
        <Carregando texto="Carregando…" />
      ) : carga.fase === 'erro' ? (
        <ErroDeCarga texto="Não foi possível carregar esta parte agora." aoTentar={() => void carregar()} />
      ) : (
        <>
          {precisaReauth ? (
            <AvisoReautenticacao texto="Por segurança, confirme sua senha no Login APM antes de baixar seus dados ou pedir a exclusão." />
          ) : null}
          <div className="bloco-dados">
            <h3 className="bloco-dados__titulo">Baixar meus dados</h3>
            <p>
              Um arquivo com o que a Minha APM guarda sobre você: cadastro usado pela área, preferências, autorizações,
              solicitações e histórico de uso. Um arquivo a cada 7 dias.
            </p>
            {carga.dados.exportacao_disponivel_em ? (
              <p className="bloco-dados__meta" role="status">
                Você já baixou seus dados. Um novo arquivo fica disponível em {quando(carga.dados.exportacao_disponivel_em, true)}.
              </p>
            ) : null}
            <div className="botoes">
              <button type="button" className="botao botao--secundario"
                disabled={baixando || precisaReauth || carga.dados.exportacao_disponivel_em !== null}
                onClick={() => void baixar()}>
                {baixando ? 'Gerando o arquivo…' : 'Baixar meus dados'}
              </button>
            </div>
          </div>
          <div className="bloco-dados">
            <h3 className="bloco-dados__titulo">Excluir meus dados</h3>
            {carga.dados.exclusao_aberta ? (
              <>
                <p role="status">
                  Seu pedido de exclusão está {ROTULO_STATUS[carga.dados.exclusao_aberta.status].toLowerCase()} desde{' '}
                  {quando(carga.dados.exclusao_aberta.criado_em)}. Protocolo{' '}
                  <strong className="protocolo">{carga.dados.exclusao_aberta.protocolo}</strong>.
                </p>
                {carga.dados.exclusao_aberta.solicitacao_id ? (
                  <LinkInterno className="link-texto" para={`/solicitacoes/${carga.dados.exclusao_aberta.solicitacao_id}`}>
                    Acompanhar ou desistir do pedido
                  </LinkInterno>
                ) : null}
              </>
            ) : (
              <>
                <p>
                  Você pode pedir que a Minha APM deixe de guardar dados ligados a você. O pedido é analisado e você
                  acompanha em Solicitações.
                </p>
                <div className="botoes">
                  <button type="button" className="botao botao--secundario" disabled={precisaReauth} onClick={() => setDialogo(true)}>
                    Pedir exclusão
                  </button>
                </div>
              </>
            )}
          </div>
          <DialogoExclusao aberto={dialogo} aoFechar={fecharDialogo} aoPedir={excluir} />
        </>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------- tela */
function BlocoPreferencias() {
  const [carga, setCarga] = useState<Carga<Preferencias>>({ fase: 'carregando' });

  const carregar = useCallback(async () => {
    setCarga({ fase: 'carregando' });
    try {
      setCarga({ fase: 'pronto', dados: await obterPreferencias() });
    } catch (falha) {
      if (!(falha instanceof ApiError)) throw falha;
      setCarga({ fase: 'erro' });
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (carga.fase === 'carregando') return <Carregando texto="Carregando suas preferências…" />;
  if (carga.fase === 'erro') {
    return <ErroDeCarga texto="Não foi possível carregar suas preferências." aoTentar={() => void carregar()} />;
  }
  const atualizar = (dados: Preferencias) => setCarga({ fase: 'pronto', dados });
  return (
    <>
      {carga.dados.faltam.length > 0 ? <SecaoCompletePerfil aoResponder={atualizar} /> : null}
      {/* `key`: resposta dada no bloco acima repõe os campos do formulário. */}
      <SecaoPreferencias key={carga.dados.atualizado_em ?? 'novo'} preferencias={carga.dados} aoSalvar={atualizar} />
      <SecaoTexto preferencias={carga.dados} aoSalvar={atualizar} />
    </>
  );
}

/**
 * Perfil e privacidade (P13): o que o associado diz de si, o tamanho do texto, as
 * autorizações e os direitos sobre os próprios dados. Cada parte só aparece com a
 * flag ligada E a `sql/017` aplicada (regra 19): desligado = nada na tela, nenhuma chamada.
 */
export function SecoesPrivacidade() {
  const { sessao } = useSessao();
  if (!sessao.recursos.privacidade) return null;
  const preferencias = sessao.flags.perfil_preferencias;
  const lgpd = sessao.flags.lgpd_consentimentos;
  if (!preferencias && !lgpd) return null;
  return (
    <div className="grade-perfil grade-perfil--privacidade">
      {preferencias ? (
        <div className="grade-perfil__coluna">
          <BlocoPreferencias />
        </div>
      ) : null}
      {lgpd ? (
        <div className="grade-perfil__coluna">
          <SecaoConsentimentos />
          <SecaoDados />
        </div>
      ) : null}
    </div>
  );
}
