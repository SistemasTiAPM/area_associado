# ADR-0026: Consentimento versionado append-only e perfil declarado no servidor (tratamento e tamanho de fonte)

- **Status:** Aceita
- **Data:** 2026-11-19
- **Decisores:** Sistemas TI (William) · Claude Code (Atlas/Sentinela/Maestro/Vitrine)
- **Relacionadas:** ADR-0004 (UPDATE por tabela), ADR-0007 e ADR-0021 (flags), ADR-0013 (CSP sem inline),
  ADR-0017 (visual), ADR-0025 (direitos do titular). Fecha DEC-26 e DEC-27 do levantamento.

## Contexto

P13 da spec v2 pede "como prefere ser chamado", área de atuação, temas, canais e frequência, consentimentos
por finalidade com histórico e o perfil progressivo ("uma pergunta por visita"). A spec §14 pede texto
ampliável; a SPA tinha todo `font-size` em px. A regra 13 proíbe estado em `localStorage`.

## Decisão

Decisões do William em 19/11: **DEC-26** — o tratamento é um campo que o próprio associado preenche, com
padrão neutro; **DEC-27** — o tamanho de fonte é guardado no servidor.

1. **Consentimento é trilha.** `consentimento` só recebe `INSERT`: conceder e retirar são linhas novas; o
   estado é a última linha de (associado, finalidade, canal) — `vw_consentimento_atual`. Sem linha = não
   concedido.
2. **Texto por versão, imutável.** `consentimento_texto(finalidade, versao)`; texto novo = versão nova. A
   vigente é a de maior `vigente_desde` já alcançado. Cada decisão aponta (chave estrangeira) a versão que a
   pessoa viu. O `PUT` exige essa versão: se mudou, `409 versao_desatualizada` e a tela recarrega.
   Autorização dada sobre texto antigo aparece desmarcada, com aviso, até a pessoa confirmar o novo.
3. **Finalidades da spec §11.6:** `ofertas_parceiros` (e-mail) e `whatsapp_relacionamento` (WhatsApp).
   Mensagem transacional não pede consentimento. Finalidade só aparece se o canal existe (regra 19): o
   WhatsApp fica oculto e recusado até a P-64. Semente `v0` é **provisória** (P-54).
4. **Perfil declarado ≠ cadastro.** `perfil_declarado` guarda o que o associado diz de si, com `UPDATE` por
   coluna, nos campos do REQUISITOS §9.1. Catálogos fechados no servidor (`app/dominio/preferencias.py`) e
   entregues à SPA na resposta: atuação (as seis da spec), frequência (`normal` = todas as novidades,
   `minima` = só o essencial), canal preferido (só e-mail; a tela nem pergunta enquanto houver um só) e temas
   (lista **provisória**: as oito categorias de benefícios, em JSON na própria linha, até existir
   `associado_tema` na Fase 5). Região de interesse, especialidade e regional ficam de fora: vêm do CRM (P-56).
5. **Tratamento (DEC-26).** Texto livre de 2 a 40 caracteres, só letras, espaço, ponto, apóstrofo e hífen
   (sem dígito: barra CPF e telefone; mesmo critério no CHECK). Vazio = saudação neutra com o primeiro nome.
   O gênero do CRM não é usado. Vai em `GET /sessao` (`preferencias.tratamento`) para o shell saudar.
6. **Tamanho de fonte (DEC-27, TI-64).** Todo `font-size` da SPA passa a `rem`; três passos (`padrao`,
   `grande` 112,5 %, `maior` 125 %) aplicados por `data-fonte` no `<html>` — atributo, nunca estilo inline.
   O valor vem em `GET /sessao` e vale em qualquer aparelho. A tela só aplica depois de o servidor aceitar.
7. **Perfil progressivo.** `GET /perfil/pergunta` devolve o primeiro campo sem resposta que não foi pulado
   nos últimos 30 dias nem três vezes; `pergunta_perfil` guarda só os pulos. Respondida ou pulada, o bloco
   some até a próxima visita.
8. **Flags.** `perfil_preferencias` (nova, desligada) para preferências, pergunta e fonte;
   `lgpd_consentimentos` (existente) para consentimentos. Desligada ou `sql/017` ausente: 404/503, seção
   oculta, sessão com o padrão sem tocar o banco.
9. **Rastro sem conteúdo.** `evento_uso` `perfil_declarado_atualizar` e `consentimento_alterar` e o
   `evento_log` levam nomes de campos, finalidade, canal, valor e versão — nunca o texto digitado.

## Consequências

- A frequência e o consentimento de ofertas ainda **não mudam o que é enviado**: quem consome é a outbox de
  comunicação para o RD Station (TI-53, rodada 2 da Onda 3). `consentimento.concedido()` já existe e falha
  fechado. Ligar as flags antes disso mostra controles cujo efeito ainda não existe — decisão de quem liga.
- A lista de temas é proposta nossa; a agência confirma (P-86). Quando `associado_tema` nascer (Fase 5), os
  temas migram para lá por migração própria.
- Diferenças em relação ao REQUISITOS v0.2, registradas nele: flag própria `perfil_preferencias` (em vez de
  tudo sob `lgpd_consentimentos`), `PUT /perfil/consentimentos` (em vez de `POST`), rotas do titular sob
  `/perfil/dados/` e catálogo de perguntas no código (a tabela `pergunta_perfil` guarda só os pulos).
- A conversão para `rem` não muda nada no tamanho padrão (16 px de base), mas layouts com altura fixa podem
  apertar em 125 %: o e2e confere reflow e axe nos três viewports; teste com associados continua na P-45.
- O texto `v0` não tem validade jurídica.

## Alternativas rejeitadas

- **Consentimento como coluna mutável:** perde a prova de quando e sobre qual texto.
- **Tratamento pelo gênero do CRM:** dado que a pessoa não escolheu para este fim, e erra.
- **Tamanho de fonte em `localStorage` ou cookie:** contraria a regra 13 e não acompanha a pessoa entre aparelhos.
- **Só o zoom do navegador:** a spec pede controle próprio para um público majoritariamente acima de 50 anos.
