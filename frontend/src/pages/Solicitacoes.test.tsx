import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { _reiniciarAnalytics, enviarFila } from '../lib/analytics';
import { ID_SOLICITACAO, resumo, solicitacao } from '../test/fabricas';
import { fabricarSessao, montarApp, respostaJson } from '../test/utilidades';

const API_ANDAMENTO = '/api/v1/solicitacoes?situacao=andamento&limite=20';
const API_ENCERRADAS = '/api/v1/solicitacoes?situacao=encerradas&limite=20';
const API_DETALHE = `/api/v1/solicitacoes/${ID_SOLICITACAO}`;
const PRONTA = fabricarSessao({ recursos: { solicitacoes: true, ajuda: true } });

type Chamada = { url: string; init: RequestInit | undefined };
const corpoUso = (chamadas: Chamada[]) =>
  chamadas
    .filter((c) => c.url === '/api/v1/uso')
    .flatMap((c) => (JSON.parse(String(c.init?.body)) as { eventos: Record<string, unknown>[] }).eventos);
const corpo = (init: RequestInit | undefined) => JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;
const cabecalho = (init: RequestInit | undefined, nome: string) => (init?.headers as Record<string, string>)[nome];

/** O `role=alert` com conteúdo (o do toast sempre existe, vazio). */
const alertaCom = (texto: string) =>
  waitFor(() => {
    const alerta = screen.getAllByRole('alert').find((a) => a.textContent?.includes(texto));
    expect(alerta).toBeDefined();
    return alerta as HTMLElement;
  });

describe('Minhas solicitações — lista (P05; RF-SO-01, 07, 08, 09, 15)', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('recurso indisponível: "em construção" sem chamar a API', async () => {
    const { chamadas } = montarApp('/solicitacoes', fabricarSessao());
    expect(await screen.findByText(/está em construção/)).toBeInTheDocument();
    expect(chamadas.some((c) => c.url.startsWith('/api/v1/solicitacoes'))).toBe(false);
  });

  it('carregando: anuncia o estado e não mostra lista', async () => {
    montarApp('/solicitacoes', PRONTA, (url) => (url === API_ANDAMENTO ? (new Promise(() => {}) as never) : undefined));
    expect(await screen.findByText('Carregando suas solicitações…')).toBeInTheDocument();
    expect(screen.getByText('Carregando suas solicitações…').closest('[role=status]')).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByRole('list', { name: /Solicitações/ })).toBeNull();
  });

  it('vazio: voz §3.3, caminho para a Ajuda e sem "em breve"', async () => {
    montarApp('/solicitacoes', PRONTA, (url) => (url === API_ANDAMENTO ? respostaJson({ itens: [], proximo_cursor: null }) : undefined));
    expect(await screen.findByText('Você não tem solicitações em andamento')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /falar com a Central na Ajuda/ })).toHaveAttribute('href', '/ajuda');
    expect(document.body.textContent).not.toMatch(/em breve|!/i);
  });

  it('erro: mensagem, request_id, tentar novamente e erro_exibido', async () => {
    const usuario = userEvent.setup();
    let tentativas = 0;
    const { chamadas } = montarApp('/solicitacoes', PRONTA, (url) => {
      if (url !== API_ANDAMENTO) return undefined;
      tentativas += 1;
      return tentativas === 1
        ? respostaJson({ erro: 'recurso_indisponivel', mensagem: 'As solicitações estão indisponíveis agora. Tente de novo em instantes.', request_id: 'abcdef0123456789' }, 503)
        : respostaJson({ itens: [resumo()], proximo_cursor: null });
    });
    const alerta = await alertaCom('As solicitações estão indisponíveis agora');
    expect(alerta).toBeDefined();
    expect(within(alerta as HTMLElement).getByText('abcdef0123456789')).toBeInTheDocument();
    await usuario.click(within(alerta as HTMLElement).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('link', { name: /Outro assunto/ })).toBeInTheDocument();
    enviarFila(true);
    expect(corpoUso(chamadas)).toContainEqual(
      expect.objectContaining({ acao: 'erro_exibido', detalhes: expect.objectContaining({ codigo: 'recurso_indisponivel', request_id: 'abcdef0123456789' }) }),
    );
  });

  it('sucesso: status por texto, faixa do parceiro, prazo, contato, destaque e "Carregar mais"', async () => {
    const usuario = userEvent.setup();
    const pagina1 = [
      resumo({ status: 'pendente_associado', rotulo_status: 'O parceiro precisa de algo seu', pode_responder: true }),
      resumo({
        id: 'b2',
        status: 'em_atendimento',
        rotulo_status: 'Em atendimento',
        aguardando_parceiro: true,
        prazo_em: '2026-11-05',
        beneficio: { slug: 'escola-de-idiomas', titulo: 'Escola de idiomas' },
        tipo: { codigo: 'beneficio', rotulo: 'Benefício' },
        contato: { canal: 'telefone', texto: '(11) 3188-6200' },
      }),
    ];
    const { chamadas } = montarApp('/solicitacoes', PRONTA, (url) => {
      if (url === API_ANDAMENTO) return respostaJson({ itens: pagina1, proximo_cursor: 'c1' });
      if (url === `${API_ANDAMENTO}&cursor=c1`) return respostaJson({ itens: [resumo({ id: 'c3', tipo: { codigo: 'declaracao_associado', rotulo: 'Declaração de associado' } })], proximo_cursor: null });
      return undefined;
    });
    const lista = await screen.findByRole('list', { name: 'Solicitações em andamento' });
    const itens = within(lista).getAllByRole('listitem');
    expect(within(itens[0] as HTMLElement).getByText('O parceiro precisa de algo seu')).toBeInTheDocument();
    expect(within(itens[0] as HTMLElement).getByText('Precisa de uma resposta sua')).toBeInTheDocument();
    expect(within(itens[0] as HTMLElement).getByRole('link', { name: /Outro assunto/ })).toHaveAttribute('href', `/solicitacoes/${ID_SOLICITACAO}`);
    const segundo = itens[1] as HTMLElement;
    expect(within(segundo).getByText('Aguardando o parceiro, a APM já está cobrando')).toBeInTheDocument();
    expect(within(segundo).getByText('05/11/2026')).toBeInTheDocument();
    expect(within(segundo).getByRole('link', { name: '(11) 3188-6200' })).toHaveAttribute('href', 'tel:1131886200');
    expect(within(segundo).getByRole('link', { name: /Escola de idiomas/ })).toBeInTheDocument();

    await usuario.click(screen.getByRole('button', { name: 'Carregar mais' }));
    const novo = await screen.findByRole('link', { name: /Declaração de associado/ });
    await waitFor(() => expect(novo).toHaveFocus());
    expect(within(novo.closest('li') as HTMLElement).getByText('informado após o envio')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).toBeNull();
    expect(screen.getByText('1 solicitação carregada.')).toBeInTheDocument();
    // Nenhuma ação de solicitação sai da UI (o servidor registra); pagina_ver da lista vai sem id.
    enviarFila(true);
    const eventos = corpoUso(chamadas);
    expect(eventos.some((e) => String(e.acao).startsWith('solicitacao_'))).toBe(false);
    expect(eventos).toContainEqual({ acao: 'pagina_ver', entidade: 'rota', entidade_id: '/area/solicitacoes' });
  });

  it('aba "Encerradas" busca a outra situação', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp('/solicitacoes', PRONTA, (url) => {
      if (url === API_ANDAMENTO) return respostaJson({ itens: [], proximo_cursor: null });
      if (url === API_ENCERRADAS)
        return respostaJson({ itens: [resumo({ status: 'concluida_negativa', rotulo_status: 'Não seguiu', pode_cancelar: false })], proximo_cursor: null });
      return undefined;
    });
    await screen.findByText('Você não tem solicitações em andamento');
    await usuario.click(screen.getByRole('tab', { name: 'Encerradas' }));
    expect(await screen.findByText('Não seguiu')).toBeInTheDocument();
    expect(chamadas.some((c) => c.url === API_ENCERRADAS)).toBe(true);
  });

  it('contador do menu usa solicitacoes_aguardando', async () => {
    montarApp('/solicitacoes', fabricarSessao({ recursos: { solicitacoes: true, ajuda: true }, solicitacoes_aguardando: 2 }), (url) =>
      url === API_ANDAMENTO ? respostaJson({ itens: [], proximo_cursor: null }) : undefined,
    );
    const menu = await screen.findByRole('navigation', { name: 'Menu principal' });
    expect(within(menu).getByRole('link', { name: 'Minhas solicitações, 2 solicitações aguardando você' })).toBeInTheDocument();
  });
});

describe('Minhas solicitações — detalhe (P05; RF-SO-02, 04, 05, 10, 13)', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('linha do tempo em ol com aria-current no passo atual, h1 com o tipo e campos enviados', async () => {
    const { chamadas } = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) =>
      url === API_DETALHE
        ? respostaJson(
            solicitacao({
              status: 'enviada',
              rotulo_status: 'Encaminhada à equipe',
              linha_do_tempo: [
                { quando: '2026-10-21T15:30:00Z', status: 'enviada', rotulo: 'Encaminhada à equipe', ator: 'sistema', mensagem: null },
                { quando: '2026-10-20T13:00:00Z', status: 'criada', rotulo: 'Recebida pela APM', ator: 'voce', mensagem: null },
              ],
            }),
          )
        : undefined,
    );
    expect(await screen.findByRole('heading', { level: 1, name: 'Outro assunto' })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe('Outro assunto · Minha APM'));
    const linha = screen.getByRole('list', { name: 'Linha do tempo da solicitação' });
    expect(linha.tagName).toBe('OL');
    const passos = within(linha).getAllByRole('listitem');
    expect(passos[0]).toHaveTextContent('Recebida pela APM');
    expect(passos[0]).toHaveTextContent('20/10/2026 às 10:00 · Você');
    expect(passos[1]).toHaveAttribute('aria-current', 'step');
    expect(passos[0]).not.toHaveAttribute('aria-current');
    expect(screen.getByText('Como uso o desconto na escola de idiomas?')).toBeInTheDocument();
    expect(screen.getAllByText('Dúvida sobre benefício')).toHaveLength(1); // `categoria` não repete o assunto
    enviarFila(true);
    expect(JSON.stringify(corpoUso(chamadas))).not.toContain(ID_SOLICITACAO);
  });

  it('já na Central (ADR-0023): protocolo, orientação e nada de cancelar ou responder pela área', async () => {
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) =>
      url === API_DETALHE
        ? respostaJson(
            solicitacao({
              status: 'pendente_associado',
              rotulo_status: 'O parceiro precisa de algo seu',
              protocolo: 'CAS-285497-M7P9T5',
              na_central: true,
              pode_cancelar: false,
              pode_responder: false,
              linha_do_tempo: [
                {
                  quando: '2026-10-21T15:30:00Z',
                  status: 'pendente_associado',
                  rotulo: 'O parceiro precisa de algo seu',
                  ator: 'equipe_apm',
                  mensagem: 'A Central de Relacionamento precisa de mais informações. Protocolo: CAS-285497-M7P9T5.',
                },
              ],
            }),
          )
        : undefined,
    );
    expect(await screen.findByText('Protocolo na Central')).toBeInTheDocument();
    expect(screen.getAllByText('CAS-285497-M7P9T5', { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText('A Central precisa de mais informações.')).toBeInTheDocument();
    expect(screen.getByText(/Para cancelar ou complementar, fale com a Central e informe o protocolo CAS-285497-M7P9T5\./))
      .toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar solicitação' })).toBeNull();
    expect(screen.queryByText(/Responda abaixo/)).toBeNull();
  });

  it('não encontrada: 404 sem oráculo, com caminho de volta', async () => {
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) =>
      url === API_DETALHE ? respostaJson({ erro: 'nao_encontrado', mensagem: 'Não encontramos.', request_id: null }, 404) : undefined,
    );
    expect(await screen.findByText('Não encontramos esta solicitação')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Voltar para Minhas solicitações/ })).toHaveAttribute('href', '/solicitacoes');
  });

  it('erro: EstadoErro com request_id', async () => {
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) =>
      url === API_DETALHE ? respostaJson({ erro: 'erro_interno', mensagem: 'Não conseguimos agora.', request_id: '0123456789abcdef' }, 500) : undefined,
    );
    const alerta = await alertaCom('Não conseguimos agora.');
    expect(within(alerta as HTMLElement).getByText('0123456789abcdef')).toBeInTheDocument();
  });

  it('cancelar: diálogo de confirmação, POST com CSRF e motivo, toast e estado novo', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url, init) => {
      if (url === API_DETALHE) return respostaJson(solicitacao());
      if (url === `${API_DETALHE}/cancelar` && init?.method === 'POST')
        return respostaJson(solicitacao({ status: 'cancelada', rotulo_status: 'Cancelada', pode_cancelar: false }));
      return undefined;
    });
    await usuario.click(await screen.findByRole('button', { name: 'Cancelar solicitação' }));
    const dialogo = screen.getByRole('alertdialog', { name: 'Cancelar esta solicitação?' });
    await usuario.type(within(dialogo).getByLabelText('Motivo (opcional)'), 'Resolvi por outro canal');
    await usuario.click(within(dialogo).getByRole('button', { name: 'Cancelar solicitação' }));
    expect(await screen.findByText('Solicitação cancelada')).toBeInTheDocument();
    const envio = chamadas.find((c) => c.url === `${API_DETALHE}/cancelar`);
    expect(corpo(envio?.init)).toEqual({ motivo: 'Resolvi por outro canal' });
    expect(cabecalho(envio?.init, 'X-CSRF-Token')).toBe('token-csrf-teste');
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(screen.getAllByText('Cancelada').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Cancelar solicitação' })).toBeNull();
  });

  it('409: toast "mudou de situação" e recarrega o detalhe', async () => {
    const usuario = userEvent.setup();
    let leituras = 0;
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) => {
      if (url === API_DETALHE) {
        leituras += 1;
        return respostaJson(
          leituras === 1
            ? solicitacao()
            : solicitacao({ status: 'em_atendimento', rotulo_status: 'Em atendimento', pode_cancelar: false }),
        );
      }
      if (url === `${API_DETALHE}/cancelar`)
        return respostaJson({ erro: 'estado_invalido', mensagem: 'Transição inválida.', request_id: null }, 409);
      return undefined;
    });
    await usuario.click(await screen.findByRole('button', { name: 'Cancelar solicitação' }));
    await usuario.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancelar solicitação' }));
    expect(await screen.findByText('Esta solicitação mudou de situação. Atualizamos a página.')).toBeInTheDocument();
    expect(await screen.findByText('Em atendimento', { selector: '.status-solicitacao span' })).toBeInTheDocument();
    expect(leituras).toBe(2);
    expect(screen.queryByRole('button', { name: 'Cancelar solicitação' })).toBeNull();
  });

  it('responder em pendente_associado: destaque com a mensagem do parceiro e envio 1–2000', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) => {
      if (url === API_DETALHE)
        return respostaJson(
          solicitacao({
            status: 'pendente_associado',
            rotulo_status: 'O parceiro precisa de algo seu',
            pode_responder: true,
            linha_do_tempo: [
              { quando: '2026-10-20T13:00:00Z', status: 'criada', rotulo: 'Recebida pela APM', ator: 'voce', mensagem: null },
              { quando: '2026-10-22T13:00:00Z', status: 'pendente_associado', rotulo: 'O parceiro precisa de algo seu', ator: 'parceiro', mensagem: 'Envie o número da matrícula.' },
            ],
          }),
        );
      if (url === `${API_DETALHE}/responder`) return respostaJson(solicitacao({ status: 'em_atendimento', rotulo_status: 'Em atendimento' }));
      return undefined;
    });
    expect(await screen.findByText('O parceiro precisa de algo seu.')).toBeInTheDocument();
    expect(screen.getAllByText('Envie o número da matrícula.').length).toBeGreaterThan(0);
    await usuario.click(screen.getByRole('button', { name: 'Enviar resposta' }));
    expect(screen.getByText('Escreva sua resposta antes de enviar.')).toBeInTheDocument();
    const campo = screen.getByLabelText('Sua resposta');
    expect(campo).toHaveAttribute('maxlength', '2000');
    await usuario.type(campo, '  Matrícula 123  ');
    await usuario.click(screen.getByRole('button', { name: 'Enviar resposta' }));
    expect(await screen.findByText('Resposta enviada')).toBeInTheDocument();
    expect(corpo(chamadas.find((c) => c.url === `${API_DETALHE}/responder`)?.init)).toEqual({ texto: 'Matrícula 123' });
  });

  it('avaliar: radiogroup 0–10 com rótulos, nota obrigatória e comentário opcional', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, PRONTA, (url) => {
      if (url === API_DETALHE)
        return respostaJson(solicitacao({ status: 'concluida_positiva', rotulo_status: 'Concluída', pode_cancelar: false, pode_avaliar: true }));
      if (url === `${API_DETALHE}/avaliar`)
        return respostaJson(
          solicitacao({
            status: 'concluida_positiva',
            rotulo_status: 'Concluída',
            pode_cancelar: false,
            avaliacao: { nota: 9, comentario: 'Rápido', avaliada_em: '2026-10-25T12:00:00Z' },
          }),
        );
      return undefined;
    });
    const grupo = await screen.findByRole('radiogroup', { name: 'Que nota você dá para este atendimento?' });
    expect(within(grupo).getAllByRole('radio')).toHaveLength(11);
    await usuario.click(screen.getByRole('button', { name: 'Enviar avaliação' }));
    expect(screen.getByText('Escolha uma nota de 0 a 10.')).toBeInTheDocument();
    await usuario.click(within(grupo).getByRole('radio', { name: '9' }));
    await usuario.type(screen.getByLabelText('Comentário (opcional)'), 'Rápido');
    await usuario.click(screen.getByRole('button', { name: 'Enviar avaliação' }));
    expect(await screen.findByText('Nota 9 de 10, enviada em 25/10/2026.')).toBeInTheDocument();
    expect(corpo(chamadas.find((c) => c.url === `${API_DETALHE}/avaliar`)?.init)).toEqual({ nota: 9, comentario: 'Rápido' });
  });
});
