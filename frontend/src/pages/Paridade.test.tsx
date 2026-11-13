import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Conversa, MensagemConversa, TipoCatalogo } from '../api/solicitacoes';
import { esperaPorExtenso } from '../components/Conversa';
import { _reiniciarAnalytics } from '../lib/analytics';
import { ID_SOLICITACAO, resumo, solicitacao } from '../test/fabricas';
import { fabricarSessao, montarApp, respostaJson } from '../test/utilidades';
import { organizarCatalogo } from './NovaSolicitacao';

/** Paridade com o App APM (ADR-0024; flag `solicitacoes_crm`): catálogo, lista dos dois canais e conversa. */

const API_TIPOS = '/api/v1/solicitacoes/tipos';
const API_ANDAMENTO = '/api/v1/solicitacoes?situacao=andamento&limite=20';
const API_DETALHE = `/api/v1/solicitacoes/${ID_SOLICITACAO}`;
const API_MENSAGENS = `${API_DETALHE}/mensagens`;
const LIGADA = fabricarSessao({ recursos: { solicitacoes: true, ajuda: true }, flags: { solicitacoes_crm: true } });
const DESLIGADA = fabricarSessao({ recursos: { solicitacoes: true, ajuda: true } });

const tipo = (codigo: string, rotulo: string, ordem: number, extra: Partial<TipoCatalogo> = {}): TipoCatalogo => ({
  codigo,
  rotulo,
  grupo: null,
  grupo_rotulo: null,
  ordem,
  responde: 'apm',
  carencia_meses: 0,
  ...extra,
});
const SEGUROS = { grupo: 'seguros', grupo_rotulo: 'Seguros' };
const CATALOGO: TipoCatalogo[] = [
  tipo('duvida', 'Dúvidas e perguntas', 110, { responde: 'central' }),
  tipo('seguro_carro', 'Seguro Auto', 22, SEGUROS),
  tipo('planos_de_saude', 'Planos de Saúde', 10),
  tipo('seguro_vida', 'Seguro de Vida', 20, SEGUROS),
];

const mensagem = (parcial: Partial<MensagemConversa> = {}): MensagemConversa => ({
  id: '11111111-1111-4111-8111-111111111111',
  autor: 'central',
  texto: 'Bom dia! Pode nos enviar o documento?',
  quando: '2026-11-13T15:00:00Z',
  estado: 'enviada',
  ...parcial,
});
const conversa = (parcial: Partial<Conversa> = {}): Conversa => ({
  mensagens: [],
  pode_enviar: true,
  motivo_bloqueio: null,
  responde: 'central',
  truncado: false,
  ...parcial,
});
const NO_CRM = {
  status: 'enviada' as const,
  na_central: true,
  situacao: 'aberta' as const,
  rotulo_status: 'Aberta',
  canal: 'minha_apm' as const,
  responde: 'central' as const,
  pode_enviar_mensagem: true,
  pode_cancelar: false,
  protocolo: 'CAS-285497-M7P9T5',
};

const corpo = (init: RequestInit | undefined) => JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;

describe('Nova solicitação — catálogo comum com o App (ADR-0024)', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('organiza por ordem e junta o grupo na posição do menor item', () => {
    const entradas = organizarCatalogo(CATALOGO);
    expect(entradas.map((e) => (e.classe === 'tipo' ? e.tipo.codigo : `grupo:${e.codigo}`))).toEqual([
      'planos_de_saude',
      'grupo:seguros',
      'duvida',
    ]);
    const grupo = entradas[1];
    expect(grupo?.classe === 'grupo' ? grupo.tipos.map((t) => t.codigo) : []).toEqual(['seguro_vida', 'seguro_carro']);
  });

  it('flag desligada: sem botão na lista, página não encontrada e nenhuma chamada ao catálogo', async () => {
    const lista = montarApp('/solicitacoes', DESLIGADA, (url) =>
      url === API_ANDAMENTO ? respostaJson({ itens: [], proximo_cursor: null }) : undefined,
    );
    expect(await screen.findByText('Você não tem solicitações em andamento')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Nova solicitação' })).toBeNull();
    lista.unmount();

    const { chamadas } = montarApp('/solicitacoes/nova', DESLIGADA);
    expect(await screen.findByText('Não encontramos esta página')).toBeInTheDocument();
    expect(chamadas.some((c) => c.url === API_TIPOS)).toBe(false);
  });

  it('escolhe um seguro dentro do grupo, envia o texto e leva ao acompanhamento', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp('/solicitacoes/nova', LIGADA, (url, init) => {
      if (url === API_TIPOS) return respostaJson({ itens: CATALOGO });
      if (url === '/api/v1/solicitacoes' && init?.method === 'POST') {
        return respostaJson(
          solicitacao({ tipo: { codigo: 'seguro_carro', rotulo: 'Seguro Auto' }, campos: { mensagem: 'Quero uma cotação.' } }),
          201,
        );
      }
      return undefined;
    });

    const tipos = await screen.findByRole('list', { name: 'Tipos de solicitação' });
    const grupo = within(tipos).getByRole('button', { name: 'Seguros' });
    expect(grupo).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: 'Seguro Auto' })).toBeNull(); // sublista fechada
    await usuario.click(grupo);
    expect(grupo).toHaveAttribute('aria-expanded', 'true');
    await usuario.click(screen.getByRole('button', { name: 'Seguro Auto' }));

    expect(screen.getByRole('heading', { name: 'Seguro Auto' })).toHaveFocus();
    expect(screen.getByText('Quem responde: Equipe APM.')).toBeInTheDocument();
    const campo = screen.getByLabelText('Conte o que você precisa');
    await usuario.type(campo, 'curto');
    await usuario.click(screen.getByRole('button', { name: 'Enviar solicitação' }));
    expect(screen.getByText(/pelo menos 10 caracteres/)).toBeInTheDocument();
    expect(chamadas.some((c) => c.init?.method === 'POST' && c.url === '/api/v1/solicitacoes')).toBe(false);

    await usuario.clear(campo);
    await usuario.type(campo, '  Quero uma cotação para o meu carro.  ');
    expect(screen.getByText(/de 2000 caracteres/)).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Enviar solicitação' }));

    expect(await screen.findByText('Recebemos sua solicitação')).toBeInTheDocument();
    const envio = chamadas.find((c) => c.init?.method === 'POST' && c.url === '/api/v1/solicitacoes');
    expect(corpo(envio?.init)).toMatchObject({ tipo_servico: 'seguro_carro', campos: { mensagem: 'Quero uma cotação para o meu carro.' } });
    expect(String(corpo(envio?.init).chave_idempotencia)).toMatch(/^[0-9a-f-]{36}$/);
    expect((envio?.init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('token-csrf-teste');
    expect(screen.getByRole('link', { name: 'Acompanhar esta solicitação' })).toHaveAttribute('href', `/solicitacoes/${ID_SOLICITACAO}`);
  });

  it('carência mostra a data do servidor; serviço desligado recarrega o catálogo sem o tipo', async () => {
    const usuario = userEvent.setup();
    let catalogos = 0;
    let envios = 0;
    montarApp('/solicitacoes/nova', LIGADA, (url, init) => {
      if (url === API_TIPOS) {
        catalogos += 1;
        return respostaJson({ itens: catalogos === 1 ? CATALOGO : CATALOGO.filter((t) => t.codigo !== 'planos_de_saude') });
      }
      if (url === '/api/v1/solicitacoes' && init?.method === 'POST') {
        envios += 1;
        return envios === 1
          ? respostaJson(
              {
                erro: 'nao_elegivel',
                mensagem: 'Planos de Saúde fica disponível a partir de 01/02/2027, 3 meses depois da filiação.',
                request_id: 'abcdef0123456789',
                detalhes: [{ campo: 'libera_em', mensagem: '2027-02-01' }],
              },
              409,
            )
          : respostaJson(
              { erro: 'servico_indisponivel', mensagem: 'Este serviço não está disponível no momento.', request_id: 'abcdef0123456789' },
              422,
            );
      }
      return undefined;
    });
    await usuario.click(await screen.findByRole('button', { name: 'Planos de Saúde' }));
    await usuario.type(screen.getByLabelText('Conte o que você precisa'), 'Quero conhecer os planos disponíveis.');
    await usuario.click(screen.getByRole('button', { name: 'Enviar solicitação' }));
    expect(await screen.findByText(/disponível a partir de 01\/02\/2027/)).toBeInTheDocument();

    await usuario.click(screen.getByRole('button', { name: 'Enviar solicitação' }));
    await waitFor(() => expect(catalogos).toBe(2));
    expect(await screen.findByRole('list', { name: 'Tipos de solicitação' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Planos de Saúde' })).toBeNull();
    expect(screen.getAllByRole('alert').some((a) => a.textContent?.includes('não está disponível no momento'))).toBe(true);
  });

  it('catálogo vazio e erro de carga', async () => {
    const vazio = montarApp('/solicitacoes/nova', LIGADA, (url) => (url === API_TIPOS ? respostaJson({ itens: [] }) : undefined));
    expect(await screen.findByText('Nenhum serviço disponível para solicitação agora')).toBeInTheDocument();
    vazio.unmount();

    const usuario = userEvent.setup();
    let tentativas = 0;
    montarApp('/solicitacoes/nova', LIGADA, (url) => {
      if (url !== API_TIPOS) return undefined;
      tentativas += 1;
      return tentativas === 1
        ? respostaJson({ erro: 'fonte_indisponivel', mensagem: 'Não foi possível carregar agora.', request_id: 'abcdef0123456789' }, 503)
        : respostaJson({ itens: CATALOGO });
    });
    expect(await screen.findByText('Não conseguimos carregar os tipos de solicitação agora')).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('button', { name: 'Planos de Saúde' })).toBeInTheDocument();
  });
});

describe('Minhas solicitações com a paridade ligada', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('lista: botão, registro do app, rótulo do App, protocolo, selo de resposta e aviso de lista parcial', async () => {
    montarApp('/solicitacoes', LIGADA, (url) =>
      url === API_ANDAMENTO
        ? respostaJson({
            parcial: true,
            proximo_cursor: null,
            itens: [
              resumo({
                ...NO_CRM,
                id: '22222222-2222-4222-8222-222222222222',
                tipo: { codigo: 'duvida', rotulo: 'Dúvidas e perguntas' },
                canal: 'app',
                situacao: 'aguardando_associado',
                rotulo_status: 'A Central aguarda seu retorno',
                nova_resposta: true,
              }),
              resumo({ ...NO_CRM, tipo: { codigo: 'seguro_carro', rotulo: 'Seguro Auto' }, responde: 'apm', protocolo: null }),
            ],
          })
        : undefined,
    );
    const lista = await screen.findByRole('list', { name: 'Solicitações em andamento' });
    expect(screen.getByRole('link', { name: 'Nova solicitação' })).toHaveAttribute('href', '/solicitacoes/nova');
    const [doApp, daArea] = within(lista).getAllByRole('listitem');
    expect(within(doApp as HTMLElement).getByText('Aberta pelo app')).toBeInTheDocument();
    expect(within(doApp as HTMLElement).getByText('A Central aguarda seu retorno').closest('[data-situacao]')).toHaveAttribute(
      'data-situacao',
      'aguardando_associado',
    );
    expect(within(doApp as HTMLElement).getByText('Nova resposta da Central')).toBeInTheDocument();
    expect(within(doApp as HTMLElement).getByText('CAS-285497-M7P9T5')).toBeInTheDocument();
    expect(doApp).toHaveClass('item-solicitacao--destaque');
    expect(within(daArea as HTMLElement).queryByText('Aberta pelo app')).toBeNull();
    expect(within(daArea as HTMLElement).getByText('Aberta')).toBeInTheDocument();
    expect(screen.getByText(/abertas pelo app podem não aparecer/)).toBeInTheDocument();
  });

  it('detalhe: conversa, envio com chave de idempotência e releitura', async () => {
    const usuario = userEvent.setup();
    let leituras = 0;
    const enviada = mensagem({ id: '33333333-3333-4333-8333-333333333333', autor: 'voce', texto: 'Segue o documento.', estado: 'enviando' });
    const { chamadas } = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url, init) => {
      if (url === API_DETALHE) return respostaJson(solicitacao({ ...NO_CRM, situacao: 'aguardando_associado', rotulo_status: 'A Central aguarda seu retorno' }));
      if (url.startsWith(API_MENSAGENS) && init?.method === 'POST') return respostaJson(enviada, 202);
      if (url.startsWith(API_MENSAGENS)) {
        leituras += 1;
        return respostaJson(conversa({ mensagens: leituras === 1 ? [mensagem()] : [mensagem(), enviada], truncado: leituras === 1 }));
      }
      return undefined;
    });

    const lista = await screen.findByRole('list', { name: 'Mensagens da conversa' });
    const [daCentral] = within(lista).getAllByRole('listitem');
    expect(within(daCentral as HTMLElement).getByText('Central de Relacionamento')).toBeInTheDocument();
    expect(within(daCentral as HTMLElement).getByText('13/11/2026 às 12:00')).toBeInTheDocument(); // horário de Brasília
    expect(screen.getByText('Mensagens anteriores não exibidas.')).toBeInTheDocument();
    expect(screen.getByText(/aguarda seu retorno\./)).toBeInTheDocument();
    expect(screen.getByText('Para complementar ou cancelar este pedido, escreva na conversa abaixo.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Responder' })).toBeNull(); // no CRM a resposta é a conversa

    await usuario.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(screen.getByText('Escreva sua mensagem antes de enviar.')).toBeInTheDocument();
    await usuario.type(screen.getByLabelText('Escreva para a Central'), ' Segue o documento. ');
    await usuario.click(screen.getByRole('button', { name: 'Enviar mensagem' }));

    await waitFor(() => expect(within(screen.getByRole('list', { name: 'Mensagens da conversa' })).getAllByRole('listitem')).toHaveLength(2));
    const envio = chamadas.find((c) => c.url === API_MENSAGENS && c.init?.method === 'POST');
    expect(corpo(envio?.init).texto).toBe('Segue o documento.');
    expect(String(corpo(envio?.init).chave_idempotencia)).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect((envio?.init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('token-csrf-teste');
    const minha = within(screen.getByRole('list', { name: 'Mensagens da conversa' })).getAllByRole('listitem')[1] as HTMLElement;
    expect(within(minha).getByText('Você')).toBeInTheDocument();
    expect(within(minha).getByText('Enviando…')).toBeInTheDocument();
    expect(screen.getByLabelText('Escreva para a Central')).toHaveValue('');
    expect(chamadas.filter((c) => c.url === API_DETALHE).length).toBeGreaterThanOrEqual(2); // situação relida
    // Depois de enviar, a releitura pede ao servidor para conferir no CRM (o resto vem do cache dele).
    const leiturasFeitas = chamadas.filter((c) => c.url.startsWith(API_MENSAGENS) && c.init?.method !== 'POST').map((c) => c.url);
    expect(leiturasFeitas).toEqual([API_MENSAGENS, `${API_MENSAGENS}?atualizar=true`]);
  });

  it('limite de mensagens: mostra quando dá para enviar de novo e mantém o texto', async () => {
    const usuario = userEvent.setup();
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url, init) => {
      if (url === API_DETALHE) return respostaJson(solicitacao(NO_CRM));
      if (url.startsWith(API_MENSAGENS) && init?.method === 'POST') {
        return new Response(
          JSON.stringify({ erro: 'limite_mensagens', mensagem: 'Você atingiu o limite de mensagens por hora.', request_id: 'abcdef0123456789' }),
          { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '1500' } },
        );
      }
      if (url.startsWith(API_MENSAGENS)) return respostaJson(conversa({ responde: 'apm' }));
      return undefined;
    });
    expect(await screen.findByText(/Nenhuma mensagem ainda/)).toBeInTheDocument();
    await usuario.type(screen.getByLabelText('Escreva para a APM'), 'Qual é o prazo?');
    await usuario.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(await screen.findByText(/limite de mensagens por hora\. Você pode enviar de novo em 25 minutos\./)).toBeInTheDocument();
    expect(screen.getByLabelText('Escreva para a APM')).toHaveValue('Qual é o prazo?');
  });

  it('encerrada: só leitura, com caminho para abrir outra; falha e fila aparecem com texto', async () => {
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url) => {
      if (url === API_DETALHE) {
        return respostaJson(solicitacao({ ...NO_CRM, situacao: 'concluida', rotulo_status: 'Concluída', pode_enviar_mensagem: false, status: 'concluida_positiva' }));
      }
      if (url.startsWith(API_MENSAGENS)) {
        return respostaJson(
          conversa({
            pode_enviar: false,
            motivo_bloqueio: 'encerrada',
            mensagens: [mensagem({ id: '44444444-4444-4444-8444-444444444444', autor: 'voce', texto: 'Cheguei tarde.', estado: 'falhou' })],
          }),
        );
      }
      return undefined;
    });
    expect(await screen.findByText('Esta solicitação foi encerrada.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Abrir nova solicitação' })).toHaveAttribute('href', '/solicitacoes/nova');
    expect(screen.queryByRole('button', { name: 'Enviar mensagem' })).toBeNull();
    expect(screen.getByText('Não enviada')).toBeInTheDocument();
    expect(screen.queryByText(/escreva na conversa abaixo/)).toBeNull();
  });

  it('mensagens bloqueadas pela Central ou CRM já encerrado: sem caixa de envio e sem convite para escrever', async () => {
    const bloqueada = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url) => {
      if (url === API_DETALHE) return respostaJson(solicitacao({ ...NO_CRM, pode_enviar_mensagem: false }));
      if (url.startsWith(API_MENSAGENS)) return respostaJson(conversa({ pode_enviar: false, motivo_bloqueio: 'nao_permitida' }));
      return undefined;
    });
    expect(await screen.findByText('Nenhuma mensagem nesta solicitação.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Enviar mensagem' })).toBeNull();
    expect(screen.getByText(/Para cancelar ou complementar, fale com a Central e informe o protocolo CAS-285497-M7P9T5/)).toBeInTheDocument();
    // Registro aberto com as mensagens bloqueadas (coluna `pode_enviar_mensagem` do hub): o texto do App.
    expect(
      screen.getByText('Esta conversa foi encerrada pela Central. Para falar conosco, abra uma nova solicitação.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Abrir nova solicitação/ })).toHaveAttribute('href', '/solicitacoes/nova');
    bloqueada.unmount();

    // O CRM já encerrou, mas o status da área ainda não acompanhou: nada de "fale com a Central".
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url) => {
      if (url === API_DETALHE) {
        return respostaJson(solicitacao({ ...NO_CRM, situacao: 'cancelada', rotulo_status: 'Cancelada', pode_enviar_mensagem: false }));
      }
      if (url.startsWith(API_MENSAGENS)) return respostaJson(conversa({ pode_enviar: false, motivo_bloqueio: 'encerrada' }));
      return undefined;
    });
    expect(await screen.findByText('Esta solicitação foi encerrada.')).toBeInTheDocument();
    expect(screen.queryByText(/fale com a Central/)).toBeNull();
  });

  it('ainda não chegou à Central: sem conversa; flag desligada: tela da Onda 2', async () => {
    const pendente = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url) =>
      url === API_DETALHE ? respostaJson(solicitacao({ na_central: false, situacao: null })) : undefined,
    );
    expect(await screen.findByRole('heading', { name: 'Situação' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Conversa' })).toBeNull();
    expect(pendente.chamadas.some((c) => c.url.startsWith(API_MENSAGENS))).toBe(false);
    pendente.unmount();

    const antiga = montarApp(`/solicitacoes/${ID_SOLICITACAO}`, DESLIGADA, (url) =>
      url === API_DETALHE ? respostaJson(solicitacao({ status: 'enviada', na_central: true, protocolo: 'CAS-285497-M7P9T5' })) : undefined,
    );
    expect(await screen.findByText(/Para cancelar ou complementar, fale com a Central/)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Conversa' })).toBeNull();
    expect(antiga.chamadas.some((c) => c.url.startsWith(API_MENSAGENS))).toBe(false);
  });

  it('erro ao carregar a conversa não derruba o detalhe', async () => {
    const usuario = userEvent.setup();
    let leituras = 0;
    montarApp(`/solicitacoes/${ID_SOLICITACAO}`, LIGADA, (url) => {
      if (url === API_DETALHE) return respostaJson(solicitacao(NO_CRM));
      if (url.startsWith(API_MENSAGENS)) {
        leituras += 1;
        return leituras === 1
          ? respostaJson({ erro: 'mensagens_indisponiveis', mensagem: 'Mensagens temporariamente indisponíveis.', request_id: 'abcdef0123456789' }, 503)
          : respostaJson(conversa());
      }
      return undefined;
    });
    expect(await screen.findByText('Não conseguimos carregar a conversa agora')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Situação' })).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByLabelText('Escreva para a Central')).toBeInTheDocument();
  });

  it('espera por extenso', () => {
    expect(esperaPorExtenso(20)).toBe('em alguns segundos');
    expect(esperaPorExtenso(60)).toBe('em 1 minuto');
    expect(esperaPorExtenso(1500)).toBe('em 25 minutos');
    expect(esperaPorExtenso(3600)).toBe('em 1 hora');
    expect(esperaPorExtenso(7000)).toBe('em 2 horas');
  });
});
