# Minha APM · Especificação funcional para a TI · v2 · 30/09/2026

> **Transcrição fiel** do PDF `ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.pdf` (APM × Comunicação
> Encantada, "Documento para a TI da APM", 34 páginas). Feita em 2026-10-29 para permitir `grep`,
> citação por linha e diff com versões futuras. Numeração de seções e identificadores (P01–P17,
> B01–B13, A01–A20, tipos 1–6, códigos ACE/HOM/…) são os do original. Onde o PDF traz figura
> (arquitetura em camadas, §5.1; ordem dos blocos, §7.2) há apenas a legenda. Os números entre
> parênteses são os do original e **não** são fonte de dados para o produto (regra 19 do
> `CLAUDE.md`). A leitura técnica está em [`../LEVANTAMENTO-TECNICO-spec-v2.md`](../LEVANTAMENTO-TECNICO-spec-v2.md);
> o índice de identificadores em [`INDICE-IDS.md`](INDICE-IDS.md).

Capa: *Minha APM: especificação funcional — Funcionalidades, usabilidade, página por página,
personalização da home, backoffice, dados para análise e automação de comunicação, com fases e
sprints para a construção pela equipe interna.*

---

## 1. O que é o Minha APM e o problema que resolve

O Minha APM é a experiência digital de ser associado da APM: um só lugar, no celular e no
computador, onde a médica ou o médico entra com o CPF, encontra benefícios, serviços, defesa
profissional, ciência, eventos e rotinas financeiras, ativa o que precisa, acompanha cada etapa e
entende o valor que a associação entrega. Para a APM, é a camada que transforma cada interação em
inteligência associativa: interesse, ativação, uso confirmado, economia comprovada e sinais de
permanência. Benefícios são uma porta concreta de valor; não substituem a representação, o
conhecimento e o pertencimento que diferenciam a associação.

### 1.1 O que acontece hoje

- **O acesso trava.** Na home do portal, cerca de 21% dos toques (44 mil na amostra do mapa de
  calor) são tentativas de acesso do associado. O Clarity registra 286 logons em 15 meses. O número
  real é maior, porque o login acontece em um domínio sem medição, mas a área logada recebe pouco
  uso, e a área restrita pede recadastro a quem já é sócio.
- **Logado ou não, a experiência é a mesma.** Não há painel, extrato de uso, situação de carência
  nem histórico. O catálogo de serviços termina em "Associe-se", inclusive para quem já é associado.
- **O uso não vira dado.** Filiação, eventos, benefícios e parceiros funcionam em sistemas
  separados. Pedidos saem por landing page, telefone e WhatsApp, sem registro de origem nem de
  retorno.
- **Quem não usa, sai.** Entre 52% e 62% dos cancelamentos citam "não utiliza". Só 24% a 28% dos
  pedidos de cancelamento são revertidos desde 2020, e 6% dos novos associados cancelam em até dois
  meses.
- **O celular manda, e é lento.** Cerca de 70% do tráfego é mobile. O carregamento principal leva
  4,2 s (LCP), acima do limite de 2,5 s.
- **O básico falha.** A busca de segunda via de boleto, uma das páginas mais visitadas, tem erro de
  JavaScript em produção.

### 1.2 O que o Minha APM precisa entregar

- **Para o associado:** entrar sem atrito, entender o que tem e quando libera, usar em poucos
  toques, acompanhar o que pediu, ver o valor individual entregue e acessar a atuação profissional e
  coletiva da APM.
- **Para a equipe da APM:** operar benefícios, parceiros e solicitações sem planilha paralela,
  atender com a visão completa do associado e publicar conteúdo sem depender da TI.
- **Para a diretoria:** dado de interesse, ativação, uso confirmado e valor por associado,
  benefício e parceiro; cobertura de mensuração do catálogo; evidências para renovação e
  patrocínio; e as quatro métricas pedidas pela presidência, com definição única de denominador e
  fonte.

### 1.3 Como vamos saber que funcionou

| Meta | Alvo | Hoje |
|---|---|---|
| Associados do piloto que entram sem ajuda | 90% ou mais | — |
| Solicitações com status final registrado (rastro) | 100% | — |
| Novos associados com pelo menos um uso em 30 dias | acima de 30% | — |
| Pedidos de cancelamento revertidos | acima de 35% | 24% a 28% |
| Cancelamento em até 90 dias | abaixo de 3% | cerca de 6% em dois meses |
| Cancelamentos com motivo "não utiliza" | abaixo de 40% | 52% a 62% |
| Carregamento principal no celular (LCP) | abaixo de 2,5 s | 4,2 s |

---

## 2. Tese de produto e modelo de valor

A Minha APM não é um clube de descontos. É a camada de relacionamento da associação: concentra as
portas de acesso, reduz fricção, torna o valor visível e permite que a APM conheça interesses, usos
e barreiras reais da base.

### 2.1 Três dimensões de valor

- **Valor individual.** Economia comprovada, proteção incluída e serviços utilizados pelo
  associado; é a única dimensão que pode compor o Meu valor em reais.
- **Valor profissional.** Defesa profissional, atualização científica, orientação e soluções para
  a prática; entra em reais apenas quando houver serviço individual prestado e valor de referência
  aprovado.
- **Valor coletivo.** Atuação institucional, defesa do ato médico, honorários, ciência e
  pertencimento; aparece como impacto da APM e nunca como valor financeiro artificialmente somado
  ao extrato individual.

### 2.2 Centralização com evidência

Todos os benefícios e serviços relevantes ficam em um único catálogo, inclusive os que ainda não
têm integração. O que muda é a maturidade do dado: visualização, interesse, solicitação, uso
confirmado e economia comprovada são estados diferentes e precisam aparecer assim nos painéis e no
Meu valor.

Nenhuma promessa de acesso único, patrocínio, cashback, cartão ou dado de economia é exibida ao
associado antes de contrato, prova técnica e regra de negócio aprovados. O rascunho navegável é
referência de visão futura; a fase de cada item é a fonte oficial de escopo.

---

## 3. Princípios de produto e usabilidade

1. **Celular primeiro.** Cerca de 70% do acesso é pelo celular. Toda tela nasce para 360 px de
   largura; o computador é a adaptação.
2. **Quem já é associado não se recadastra.** O primeiro acesso confirma a identidade com o que a
   APM já tem: CPF, data de nascimento e código no contato cadastrado.
3. **Três toques até ativar.** Da home ao benefício ativado, no máximo três toques.
4. **Tudo começa aqui dentro.** Na F1, toda ação começa no Minha APM e gera um registro, mesmo
   quando termina em ambiente externo; se ainda não houver integração, o sistema faz um
   encaminhamento rastreado. Na F2, o retorno de status e de uso passa a ser integrado. É assim que
   interesse, uso e valor deixam de se confundir.
5. **Valor visível e honesto.** Mostrar em reais apenas o valor individual comprovado e a proteção
   incluída, sempre separados do potencial e do estimado. Atuação coletiva, ciência e representação
   aparecem como impacto, não como dinheiro artificialmente somado.
6. **Regra à vista.** O que está bloqueado aparece com o motivo e a data em que libera. Ninguém
   descobre carência no balcão.
7. **Uma porta para o clube.** Na F1, o acesso parte do Minha APM por encaminhamento rastreado;
   acesso único e retorno de resgates só entram na F2, depois da integração com o fornecedor.
8. **Editável sem desenvolvedor.** Benefícios, textos, destaques, perguntas frequentes e segmentos
   são geridos no backoffice.
9. **Medido desde o primeiro dia.** Nenhuma funcionalidade vai ao ar sem os eventos de uso
   instrumentados.
10. **Legível para todas as idades.** 58% dos associados efetivos têm 51 anos ou mais: fonte
    ajustável, contraste AA, botões grandes, zero jargão.

### 3.1 Navegação

- **Celular:** barra inferior com cinco itens: Início, Benefícios, Carteirinha, Meu valor e Mais.
  "Mais" abre Financeiro, Minhas solicitações, Clube de vantagens, Eventos, Notícias e ciência,
  Perfil e privacidade, Ajuda e Sair.
- **Computador:** menu lateral com os mesmos itens, na mesma ordem.
- **Topo fixo:** marca da APM, busca, notificações (F2) e acesso ao perfil.
- **Busca global:** benefícios, parceiros, eventos, notícias e perguntas frequentes, com sugestões
  enquanto digita.
- **Carteirinha e busca a um toque de qualquer tela.**

### 3.2 O que tem destaque

Em todas as telas, a atenção segue esta ordem. É ela que decide o que fica no topo, o que ganha cor
e o que vira texto secundário.

1. Pendência que exige ação (pagamento, documento, solicitação que pede algo do associado), porque
   resolve o que trava o uso.
2. Valor individual recebido, porque dá visibilidade concreta ao que a associação entrega e apoia a
   renovação.
3. Próximo passo, porque a ativação nos primeiros 90 dias define a permanência.
4. Defesa e representação, quando houver ação, conquista, consulta ou serviço relevante para a
   especialidade ou regional do associado, porque tornam visível o valor coletivo da APM.
5. Recomendações, agenda e conteúdo, porque levam a um novo uso e constroem hábito e pertencimento.

Além da ordem, quatro regras visuais:

- Um único botão principal por bloco, no verde da APM (#009581). Ações secundárias viram texto com
  link.
- Selos "novo", "ativo", "patrocinado" e "libera em" sempre com texto, nunca só com cor.
- Conteúdo patrocinado é sempre sinalizado.
- Bloco sem conteúdo não aparece. Nada de "em breve".

### 3.3 Como o sistema escreve

- Tratar por Dra. ou Dr. e o primeiro nome, ou como a pessoa escolher no perfil. Exemplo: "Olá,
  Dra. Helena".
- "Associado efetivo", nunca "pagante". "Médicas e médicos". Exemplo: "Exclusivo para associado
  efetivo".
- Sem ponto de exclamação e sem jargão de sistema. Nunca "erro 500", "token inválido" ou "payload".
- Botão com verbo: Ativar, Solicitar, Reservar, Inscrever, Baixar, Pagar.
- Número sempre com contexto. Exemplo: "R$ 180 economizados na escola de idiomas em outubro".
- Erro diz o que aconteceu e o que fazer. Exemplo: "Não encontramos este CPF na base de associados.
  Confira os números ou fale com a Central pelo WhatsApp."
- Voz da APM: próxima e humana, primeira pessoa do plural, séria sem ser formal. Exemplo: "Nós
  cuidamos do envio ao parceiro e avisamos você a cada etapa."

---

## 4. Quem usa

### 4.1 Categorias

- **Acadêmico (44.899).** Estudante de Medicina, sem CRM. A documentação pode estar pendente: 6.869
  acadêmicos estão com documentação incompleta no CRM. Tem trilha de ativação própria.
- **Aspirante (10.092).** Recém-formado; a contribuição é isenta na capital nos primeiros anos e
  varia nas regionais. A passagem para efetivo é o momento crítico: de 1.021 aspirantes, 82 viraram
  efetivos em dois meses (8%).
- **Efetivo (11.751).** Associado que paga a mensalidade. 58% têm 51 anos ou mais. É quem renova e
  quem mais precisa ver o valor.
- **Remido (4.660).** Isento por tempo de associação. Acesso pleno, com foco em pertencimento,
  eventos e mentoria.
- **Ex-associado (fora da base ativa).** Entra e vê a página de retorno: o que perdeu e como voltar
  (fluxo 6 da régua).
- **Não associado (fora da base).** Interessado vindo de parceiro, evento ou formulário. Não entra
  na área logada; vira lead (fluxo 1).

*(O original não tem 4.2.)*

### 4.3 Quatro pessoas de referência

Pessoas fictícias, montadas com o que os dados mostram.

**João, 22 anos, acadêmico do 4º ano em São Paulo**
- Quer: não perder benefício por burocracia, academia, preparação para a residência, turma.
- O Minha APM precisa: mostrar a documentação pendente em primeiro lugar; trilha de 90 dias;
  congresso com condição de acadêmico; comunidade de jovens médicos (F3).

**Dra. Camila, 28 anos, aspirante, residente de clínica médica, CRM de 2025**
- Quer: proteção de renda, orientação de carreira, prova de título.
- O Minha APM precisa: mostrar cada carência com data; oferecer a declaração para a prova de
  título; preparar a passagem para efetivo mostrando o que ela ganha.

**Dra. Helena, 46 anos, pediatra, efetiva há 12 anos, consultório próprio**
- Quer: resolver o consultório, plano de saúde da família, tempo.
- O Minha APM precisa: recomendar serviços de consultório; financeiro sem atrito; valor do ano
  claro.

**Dr. Roberto, 61 anos, cardiologista, efetivo há 30 anos**
- Quer: defesa profissional, atualização em cardiologia, planejar a aposentadoria, reconhecimento.
- O Minha APM precisa: fonte grande e poucos passos; valor anual para a renovação; convite para ser
  mentor (F3).

---

## 5. Mapa do produto e arquitetura

### 5.1 Arquitetura em camadas

O núcleo concentra as regras que hoje não existem em lugar nenhum: quem tem direito a quê, o rastro
de cada pedido e o valor de cada associado.

*(Figura: "Arquitetura do Minha APM em camadas. A TI define a tecnologia de cada bloco.")*

### 5.2 Páginas do associado

| ID | Página | Quem vê | Fase |
|---|---|---|---|
| P01 | Acesso (entrar, primeiro acesso, recuperar senha) | Todos | F1 |
| P02 | Início | Associados | F1 com regras, F2 com comportamento |
| P03 | Benefícios | Associados | F1 |
| P04 | Página do benefício e ativação | Associados | F1 para os tipos 1 a 3, F2 para os tipos 4 a 6 |
| P05 | Minhas solicitações | Associados | F1 |
| P06 | Meu valor | Associados | F1 (v1), evolui na F2 |
| P07 | Carteirinha digital e validação pública | Associados, parceiros e eventos | Condicional na F1: só entra após comprovação técnica da fonte de situação e da validação do QR; carteira do celular na F2 |
| P08 | Financeiro | Associados | Condicional na F1: só entra após comprovação técnica da fonte de cobrança e das rotinas de segunda via |
| P09 | Clube de vantagens | Associados | F1 como link, F2 com acesso único e resgates |
| P10 | Eventos e congresso | Associados | F2, com o congresso integrado na F3 |
| P11 | Notícias e ciência | Associados | F2 |
| P12 | Trilha de ativação (90 dias) | Novos associados e acadêmicos | F1 como bloco simples, F2 completa |
| P13 | Perfil, preferências e privacidade | Associados | F1 |
| P14 | Ajuda e atendimento | Todos | F1 |
| P15 | Notificações | Associados | F2 |
| P16 | Comunidade | Associados | F3 |
| P17 | Mensalidade patrocinada e cartão | Associados elegíveis | F3, só com contrato |
| B01 a B13 | Backoffice (seção 9) | Equipe da APM | F1, evolui na F2 |

### 5.3 17 telas (rascunho navegável × especificação)

| Tela do rascunho | Fase | No rascunho | Na especificação |
|---|---|---|---|
| Início | F1 | saudação, faixa da Mensalidade Zero, "7× o que você pagou", congresso, recomendados, categorias, como funciona e notícias | P02 Início, com os blocos da seção 7. A faixa da Mensalidade Zero só aparece com patrocínio contratado (P17). O "N vezes" só aparece quando o valor comprovado supera o que foi pago. Os recomendados saem da pontuação da seção 7.3, não são fixos. |
| Clube de benefícios | F1 | resumo, filtros e 19 benefícios em 4 categorias | P03 Benefícios e P04 Página do benefício. O filtro "Patrocinados" dá lugar a "Disponíveis para mim". O catálogo real são os 30 a 40 benefícios curados; a maioria dos parceiros do rascunho ainda não tem contrato. |
| Fatura de valor | F1 | extrato item a item e carteirinha na mesma tela | Duas páginas: P06 Meu valor (seção 8.6) e P07 Carteirinha, com validação pública do QR. |
| Clube de vantagens | F1 como link, F2 integrado | oferta da semana, uso frequente, economia e cashback | P09 Clube de vantagens, com destaque para as 30 a 40 ofertas curadas. Cashback abatendo a mensalidade depende do cartão (P17). |
| Notícias e ciência | F2 | temas seguidos, filtros, salvos e publicar trabalho | P11 Notícias e ciência. |
| Congresso e eventos | F2, integração na F3 | congresso, trilhas, agenda e aulas gravadas | P10 Eventos e congresso. |
| Inscrição no congresso | F2, integração na F3 | preço por perfil (associado, acadêmico, não associado) | P10 com o tipo de ativação 5 (inscrição). A inscrição nativa com check-in pela carteirinha é a CON-01. |
| Onboarding acadêmico | F1 como bloco, F2 completa | trilha de 90 dias em 6 passos e "o que a sua mensalidade cobre" | P12 Trilha de ativação, para acadêmicos e novos associados de todas as categorias. "Mensalidade R$ 0 patrocinada" só com patrocínio. Os valores por benefício viram valores de referência aprovados pelo Financeiro. |
| Coworking médico | F2, com contrato | busca de sala, reserva e economia na fatura | Página de benefício (P04) com o tipo 4 (reserva). Parceiro a contratar. |
| Banco de plantões | F2, com contrato | vagas, candidatura e perfil de plantonista | Página de benefício com parceiro (P04, tipo 1 ou 2), não um marketplace próprio, como decidido em julho. Parceiro a contratar. |
| Terapia online | F2, com contrato | triagem, psicólogos compatíveis e primeira sessão | Página de benefício (P04, tipo 2). A triagem e o atendimento ficam no parceiro: a APM registra só o uso, de forma agregada, sem dado de saúde (seção 11.6). |
| Marketing médico | F2, com contrato | diagnóstico e serviços no padrão CFM | Página de benefício (P04, tipo 2). Parceiro a contratar. |
| Cartão com cashback | F3 | cartão co-branded com cashback abatendo a mensalidade | P17, CARD-01. Só com banco parceiro contratado. |
| Comunidade | F3 | grupos, conversas, rede de encaminhamento, mentoria e encontros | P16 Comunidade: diretório e grupos moderados primeiro. |
| Mulheres na Medicina | F3 | grupo com publicações, canais e encontros | P16, grupo moderado (COM-01). |
| Mentoria | F3 | mentores, filtros e solicitação | P16, MEN-01. |
| Rede de encaminhamento | F3 | encaminhar paciente, especialistas e status | P16, ENC-01, só depois do parecer jurídico sobre dados de saúde. Antes vem o diretório de especialistas (DIR-01). |

---

## 6. Página por página

<a id="p01"></a>
### P01 · Acesso

**Para que serve.** Entrar em até duas telas. Quem já é associado não refaz cadastro.
**Quem vê.** Todos.

**Precisa ter**
- Campo de CPF com máscara, senha, botão Entrar e "continuar conectado".
- Primeiro acesso: CPF + data de nascimento, código enviado ao e-mail ou celular que a APM já tem
  (mostrado mascarado, como h•••@gmail.com) e criação de senha.
- "Esqueci a senha" por código.
- "Meus dados mudaram": pedido à Central com prazo informado.
- Uma frase sobre o que o associado encontra dentro e o WhatsApp da Central.
- Para quem não é associado: "Conheça a APM e associe-se", levando o CPF para a filiação.

**Em destaque.** CPF e Entrar. Nenhum banner nesta tela.

**Regras**
- Ex-associado entra e vê a página de retorno.
- A tela não confirma se um CPF existe na base antes de a data de nascimento conferir.
- Limite de tentativas por CPF e por rede (ACE-05).

**Exemplo de texto.** Título: "Minha APM". Apoio: "Seus benefícios, sua carteirinha e o valor da
sua associação em um só lugar." Link: "Primeiro acesso? Leva 2 minutos." Erro: "CPF ou senha não
conferem. Tente de novo ou crie uma nova senha."

**Dados e eventos.** `login`, `acesso_primeiro`.
**Casos especiais.** Cadastro sem e-mail nem celular: pedido à Central. Conta bloqueada por
tentativas: tempo de espera informado.
**Fase.** F1 · ACE-01 a ACE-05.

<a id="p02"></a>
### P02 · Início

**Para que serve.** Responder em cinco segundos: o que eu tenho, o que já ganhei e o que faço agora.
**Quem vê.** Associados ativos (acadêmico, aspirante, efetivo, remido).
**Precisa ter.** Saudação com tratamento e categoria, atalho da carteirinha, busca e os blocos 1 a 9
da seção 7.2: pendência, meu valor, próximo passo, defesa e representação, recomendados,
categorias, agenda, notícias e clube.
**Em destaque.** A pendência, quando houver; senão, o valor. Um botão principal por bloco.
**Regras.** Ordem e visibilidade dos blocos pela seção 7. Bloco sem conteúdo não aparece. No máximo
uma recomendação patrocinada entre as quatro primeiras.
**Dados e eventos.** `home_vista`, `home_bloco_clicado`, `recomendacao_dispensada`.
**Casos especiais.** No primeiro acesso, "como funciona" em quatro passos (descobre, ativa aqui,
usa, vira valor). Associado com pendência financeira vê a pendência no topo e os benefícios
suspensos sinalizados.
**Fase.** F1 · HOM-01 (regras). F2 · REC-01, CLU-03, NEWS-01 (comportamento).

<a id="p03"></a>
### P03 · Benefícios

**Para que serve.** Mostrar tudo o que a associação oferece, organizado pelo que o médico precisa.

**Precisa ter**
- Resumo no topo: benefícios ativos, disponíveis e valor no ano.
- Filtros: Todos, Disponíveis para mim, Ativos, Novos.
- Categorias (proposta do rascunho, a ajustar à lista curada): Consultório e prática; Finanças e
  proteção; Defesa profissional e representação; Educação e carreira; Saúde e bem-estar;
  Tecnologia e IA; Vida e lazer; Comunidade.
- Busca.
- Card com nome, condição em uma linha ("até 30% na mensalidade da escola de idiomas"), selo e
  botão.

**Em destaque.** A condição concreta, não o logotipo do parceiro.

**Regras**
- Ordem padrão: disponíveis e ainda não usados (maior afinidade primeiro), depois ativos, depois
  os que liberam em breve.
- Benefício fora da categoria aparece como "exclusivo para associado efetivo", com o caminho para
  mudar.

**Dados e eventos.** `busca`, `beneficio_visto`.
**Casos especiais.** Busca sem resultado sugere categorias e registra o termo: vira ajuste de
catálogo.
**Fase.** F1 · CAT-02, CAT-03.

<a id="p04"></a>
### P04 · Página do benefício e ativação

**Para que serve.** Explicar e ativar no mesmo lugar.

**Precisa ter**
- Nome, parceiro e o que é, em uma frase.
- Condição do associado comparada ao preço de referência (a economia).
- "Como funciona" em até quatro passos.
- Quem tem direito e a situação dele: "disponível para você desde 12/03/2026" ou "libera em
  10/11/2026".
- Botão de ação conforme o tipo de ativação (lista logo depois desta ficha).
- Perguntas frequentes, contato e regras legíveis.
- Quanto ele já aproveitou neste benefício no ano.
- Benefícios relacionados.

**Em destaque.** O botão de ação e a economia.
**Regras.** Nos tipos 1 a 5, os dados do associado vêm do cadastro e ele só confirma; não há cupom
manual. No clube (tipo 6), o resgate pode usar o mecanismo do fornecedor, mas deve nascer no Minha
APM e retornar com evidência de uso quando houver integração. A confirmação sempre mostra prazo e
próximo passo.
**Dados e eventos.** `beneficio_visto`, `solicitacao_criada`.
**Fase.** F1 · CAT-05, SOL-01 (tipos 1 a 3). F2 (tipos 4 a 6).

<a id="tipos-de-ativacao"></a>
#### Tipos de ativação

Cada benefício tem um tipo, configurado no backoffice. O tipo decide o que o botão faz e o que fica
registrado.

| Tipo | Nome | Fase | Exemplos | O botão | Fica registrado |
|---|---|---|---|---|---|
| 1 | Acesso direto | F1 | Portal MBE, biblioteca, conteúdos de parceiro | abre o serviço com acesso único ou código pessoal | o acesso |
| 2 | Encaminhamento ao parceiro | F1 | plano de saúde, seguros, contabilidade, despachante | envia os dados ao parceiro e abre a solicitação | a solicitação, com status até o resultado |
| 3 | Serviço da APM | F1 | defesa profissional, declarações, assessoria para aposentadoria | abre a solicitação para a área responsável | a solicitação, com responsável e prazo |
| 4 | Reserva | F2 | Hotel Fazenda, Residencial APM | mostra disponibilidade e confirma | a reserva e o uso |
| 5 | Inscrição | F2 | eventos, congressos, cursos da IESAPM | inscreve com preço por perfil | inscrição, presença e certificado |
| 6 | Resgate no clube | F2 | ofertas do clube de vantagens | abre a oferta no clube com acesso único | resgate e economia, vindos do clube |

<a id="p05"></a>
### P05 · Minhas solicitações

**Para que serve.** Acompanhar sem ligar.

**Precisa ter**
- Lista com benefício, data, status, prazo e contato.
- Linha do tempo de cada solicitação.
- Cancelar enquanto o parceiro ainda não atendeu.
- Avaliar de 0 a 10 depois de concluída.

**Status que o associado vê.** Recebida pela APM · Enviada ao parceiro · Em atendimento · O
parceiro precisa de algo seu · Concluída · Não seguiu · Aguardando o parceiro (a APM já está
cobrando).
**Em destaque.** O que depende do associado, como "o parceiro pediu um documento".
**Dados e eventos.** `solicitacao_status`.
**Fase.** F1 · SOL-04.

<a id="p06"></a>
### P06 · Meu valor

**Para que serve.** Tornar visível o valor individual entregue no período: economia comprovada,
proteção incluída e serviços utilizados. Quando houver contribuição direta, compara esse valor ao
que o associado pagou. Atende o pedido da presidência sem transformar impacto coletivo em dinheiro
artificial.
**Nome.** Recomendamos "Meu valor" no menu e "Extrato de valor" no título. "Fatura de valor",
usado no rascunho, se confunde com a fatura de cobrança da página Financeiro.

**Precisa ter**
- Período: ano corrente e anteriores.
- Total pago no período, vindo da cobrança.
- Economia comprovada, item a item: data, benefício, economia e fonte.
- Proteção incluída: coberturas que ele tem por ser associado, com o valor de referência.
- Total comprovado, proteção incluída em bloco separado e relação com a contribuição direta.
- Valor por categoria.
- "Como calculamos", sempre visível.
- Benefícios disponíveis que ainda não usou, com valor potencial rotulado como potencial.
- Baixar em PDF.

**Em destaque.** O valor comprovado, a proteção incluída separada e a metodologia de cálculo.
**Regras.** Cálculo pela seção 8.6. Estimativa, valor potencial e impacto coletivo nunca somam ao
comprovado. Todo item mostra fonte, data e modalidade de evidência. "N vezes o que você pagou" só
aparece quando a contribuição direta do associado é maior que R$ 0 e o comprovado mais a proteção
incluída supera esse valor. Com contribuição direta de R$ 0, a página mostra "valor entregue pela
associação" e a composição do patrocínio, sem multiplicador. Com menos de três meses de casa, a
página mostra "o que a sua associação cobre" em vez da relação.
**Dados e eventos.** `meu_valor_visto`, `uso_registrado`.
**Fase.** F1 · VAL-01 (proteção incluída, solicitações concluídas e importações). F2 · CLU-02,
VAL-03 (clube, parceiros com API, PDF anual).

<a id="p07"></a>
### P07 · Carteirinha digital

**Precisa ter.** Nome, categoria, número de associado, "associado desde", situação e QR. Baixar em
imagem ou PDF. Adicionar à carteira do celular (F2).
**Validação pública.** Quem lê o QR vê nome, categoria, situação ("associado ativo") e hora da
verificação. Nunca CPF, e-mail ou telefone.
**Regras.** O QR carrega um identificador assinado, não dados pessoais. A validação consulta a
situação no momento da leitura, então uma imagem salva continua honesta. Filiação cancelada revoga
a carteirinha.
**Em destaque.** O QR e a situação.
**Dados e eventos.** `carteirinha_aberta`, `carteirinha_validada`.
**Fase.** F1 condicionada · CAR-01 a CAR-03, após o gate técnico de dados e validação. F2 · WAL-01.

<a id="p08"></a>
### P08 · Financeiro

**Para que serve.** Resolver mensalidade e documentos sem ligar. A segunda via de boleto é hoje uma
das páginas mais visitadas do portal.

**Precisa ter**
- Situação (em dia ou em atraso) no topo.
- Valor e forma de pagamento.
- Mensalidades do ano com status.
- Segunda via: PDF, linha digitável e Pix, quando a cobrança oferecer.
- Histórico de pagamentos.
- Declarações de associado, inclusive a da AMB para prova de título (carência de 1 mês).
- Pagamento recorrente em cartão (F2, se a cobrança oferecer).

**Em destaque.** A situação e o botão de segunda via quando houver pendência.
**Regras.** Os dados vêm da cobrança (seção 13.2). Se a cobrança estiver fora do ar, a página avisa
e oferece a Central.
**Dados e eventos.** `financeiro_segunda_via`, `pagamento_confirmado`.
**Fase.** F1 condicionada · INT-02, FIN-01, FIN-03, após o gate técnico da cobrança. F2 · FIN-04.

<a id="p09"></a>
### P09 · Clube de vantagens

**Para que serve.** Descontos do dia a dia com a marca APM, a um toque.

**Precisa ter**
- Destaque para as 30 a 40 ofertas curadas para médicos, com descontos de 20% a 30%.
- Oferta da semana.
- Categorias de uso frequente.
- Economia no clube no ano, quando houver dado de resgate.
- "Ver todas as ofertas" para o catálogo amplo do fornecedor.

**Regras.** Na F1, o acesso ao clube é um encaminhamento rastreado e não promete login único nem
retorno de economia. Na F2, o resgate começa no Minha APM, acontece com acesso único e devolve
status e economia para o Meu valor.
**Fase.** F1 como encaminhamento rastreado para a plataforma atual. F2 · CLU-01 a CLU-03, com
acesso único, resgates e retorno de economia.

<a id="p10"></a>
### P10 · Eventos e congresso

**Precisa ter.** Agenda filtrável por especialidade, região e formato; página do evento; inscrição
com preço por perfil (associado, acadêmico, não associado); minhas inscrições; certificados; aulas
gravadas; congresso em destaque quando houver inscrição aberta.
**Regras.** Congressos e cursos de longa duração têm carência de 3 meses. Congressos grandes mantêm
seus sites, com a inscrição partindo do Minha APM e o CPF já preenchido (decisão de 07/07).
**Fase.** F2 · EVE-01, EVE-02. F3 · CON-01.

<a id="p11"></a>
### P11 · Notícias e ciência

**Precisa ter.** Conteúdo filtrado pelos temas seguidos e pela especialidade; filtros (tudo,
notícias, ciência, defesa profissional, eventos); seguir temas; salvar para depois; chamada para
submeter trabalho à revista.
**Fonte.** Portal atual (WordPress), Portal MBE e biblioteca.
**Fase.** F2 · NEWS-01.

<a id="p12"></a>
### P12 · Trilha de ativação (90 dias)

**Para quem.** Todo novo associado e todo acadêmico.
**Precisa ter.** Barra de progresso que começa com o primeiro passo feito (perfil); cinco ou seis
passos por categoria; o que cada passo libera; data de liberação nos passos com carência; "o que a
sua associação cobre".
**Exemplos de passos**
- Acadêmico: completar perfil e documentação; ativar TotalPass; acessar o Portal MBE; garantir
  vaga no congresso; conhecer a Medway.
- Efetivo novo: completar perfil; salvar a carteirinha; ativar o seguro perda de renda (libera no
  2º mês); conhecer a defesa profissional (libera no 3º mês); conhecer o plano de saúde; primeiro
  evento da especialidade.

**Regras.** Passo concluído por evento real (uso registrado, acesso feito), não por clique. A
trilha some ao terminar ou no dia 90.
**Fase.** F1 · bloco simples de três passos na home (HOM-01). F2 · TRI-01.

<a id="p13"></a>
### P13 · Perfil, preferências e privacidade

**Precisa ter**
- Dados do cadastro (alteração de contato segue para o cadastro).
- Como prefere ser chamado.
- Especialidades e área de atuação: consultório próprio, hospital, plantão, pesquisa, gestão,
  docência.
- Região e temas de interesse.
- Canais preferidos (e-mail, WhatsApp, SMS) e frequência.
- Consentimentos por finalidade, com histórico.
- Baixar meus dados e pedir exclusão (LGPD).

**Em destaque.** "Complete seu perfil", dizendo o que melhora: "recomendações para a sua
especialidade".
**Regras.** Perfil progressivo: uma pergunta por visita, no bloco 3 da home, em vez de formulário
longo.
**Fase.** F1 · PER-02, PER-03.

<a id="p14"></a>
### P14 · Ajuda e atendimento

**Precisa ter.** Perguntas frequentes editáveis e com busca; falar com a Central por WhatsApp,
telefone ou formulário, com horário; pedidos comuns (atualização cadastral, declaração, dúvida
sobre benefício); cancelamento.
**Regras do cancelamento.** Acessível sem labirinto. Motivo obrigatório em lista curta (não uso,
preço, mudança de cidade ou de fase, insatisfação com um serviço, outro). Oferta de conversa
opcional. O pedido vai para a Central e dispara o fluxo 6 da régua.
**Fase.** F1 · AJU-01, AJU-02.

<a id="p15"></a>
### P15 · Notificações

**Precisa ter.** Ícone com contagem no topo; tipos: solicitação atualizada, benefício liberado,
evento, pagamento e novidade para o perfil; lida e não lida; atalho para preferências.
**Fase.** F2 · NOT-02.

<a id="p16"></a>
### P16 · Comunidade

**O que o rascunho mostra.** Grupos (Mulheres na Medicina, jovens médicos, especialidades),
mentoria entre titulares e jovens e rede de encaminhamento de pacientes.
**Ordem proposta.** Diretório de especialistas e grupos moderados primeiro; mentoria depois; rede
de encaminhamento só com parecer jurídico sobre dados de saúde.
**Fase.** F3 · DIR-01, COM-01, MEN-01, ENC-01.

<a id="p17"></a>
### P17 · Mensalidade patrocinada e cartão

**Quando entra.** Só com contrato assinado com patrocinador e banco, parecer jurídico aplicável e
critérios de mensuração aprovados. A funcionalidade nasce desligada por chave de configuração e não
aparece na experiência do associado antes desses requisitos.
**Regras.** O associado vê quanto o patrocínio cobre. O patrocinador recebe apenas dado agregado.
Adesão opcional e revogável.
**Fase.** F3 · MZ-01, CARD-01.

---

## 7. Personalização da home

A home é a mesma estrutura para todos, com conteúdo diferente para cada um. A personalização começa
com regras simples e transparentes (F1) e aprende com o comportamento a partir da F2.

### 7.1 Com que dados

- **Categoria** (vem do cadastro). Acadêmico vê a trilha própria; efetivo vê a renovação.
- **Fase de carreira:** até 40, 40 a 55, 55 a 65 e acima (vem da data de nascimento). Assessoria
  para aposentadoria para 55+; prova de título para até 40.
- **Tempo de casa e carências** (vem da data de filiação). "Seu seguro perda de renda libera em
  10/10."
- **Especialidade e área de atuação** (cadastro e perfil). Quem atende em consultório próprio
  recebe contabilidade e vigilância sanitária.
- **Região** (cadastro). Eventos e parceiros da regional.
- **Situação financeira** (cobrança). Pendência no topo; ofertas comerciais suspensas.
- **Comportamento** (eventos de uso). Viu duas vezes e não ativou; leu sobre um tema.
- **Temas seguidos** (perfil). Notícias e agenda.
- **Momento da jornada** (datas). Primeiros 90 dias, renovação em 60 dias, aniversário.

Nenhum dado de saúde do associado entra na personalização.

<a id="blocos-home"></a>
### 7.2 Blocos e regras de exibição

*(Figura: ordem dos blocos da home no celular; valores ilustrativos.)*

| # | Bloco | Aparece quando | Conteúdo | Regra |
|---|---|---|---|---|
| 1 | Pendência | há algo que exige ação | um card | prioridade: pagamento em atraso, depois documentação pendente, depois solicitação que pede algo do associado, depois benefício liberado pela carência nos últimos 7 dias, depois renovação em até 30 dias |
| 2 | Meu valor | sempre | total do ano e relação com o que pagou | até três meses de casa, mostra "o que a sua associação cobre" |
| 3 | Próximo passo | sempre que houver passo ou pergunta pendente | um passo | nos primeiros 90 dias, o passo da trilha de maior valor ainda não feito; depois, uma pergunta de perfil por vez |
| 4 | Recomendados | há benefício disponível e não usado | 3 a 6 cards | pontuação da seção 7.3 |
| 5 | Categorias | sempre | atalhos | fixo |
| 6 | Defesa e representação | há ação, conquista, consulta, conteúdo ou serviço de defesa relevante para a especialidade ou regional | uma atualização principal e atalho para acompanhar ou solicitar apoio | relevância para a especialidade, regional ou pauta seguida; nunca converte impacto coletivo em valor financeiro individual |
| 7 | Agenda | há evento nos próximos 60 dias para a especialidade ou região | até 3 eventos | data mais próxima; congresso primeiro quando houver inscrição aberta |
| 8 | Notícias e ciência (F2) | há conteúdo dos temas | 3 itens | mais recentes dos temas seguidos |
| 9 | Clube (F2) | sempre | oferta da semana | curadoria por segmento |

**Destaque editorial (ADM-05):** a APM pode colocar um aviso por segmento na posição 2, por período
definido, como no Dia do Médico ou na campanha de renovação. Um por vez.

<a id="recomendacao-v1"></a>
### 7.3 Recomendação v1: pontuação por regras

Cada benefício disponível recebe pontos. Os de maior pontuação aparecem primeiro.

| Critério | Pontos |
|---|---|
| Afinidade do benefício com o segmento (matriz editável no backoffice) | 0 a 3 |
| Benefício liberado pela carência nos últimos 30 dias | +2 |
| Página do benefício vista nos últimos 30 dias sem ativação | +2 |
| Benefício novo no catálogo (menos de 30 dias) | +1 |
| Combina com um tema seguido ou com a área de atuação | +1 |
| Patrocinado | +1, com no máximo um entre os quatro primeiros e sempre sinalizado |
| Já ativo ou usado | sai da lista |
| Dispensado pelo associado | sai por 60 dias |
| Não disponível para ele | sai da lista e aparece no catálogo como "libera em" |

Quatro regras de apoio:
- **Desempate:** maior valor de referência.
- **Diversidade:** no máximo dois cards da mesma categoria.
- **Rotação:** um card que aparece por três semanas sem interação perde prioridade.
- **Transparência:** cada card traz "por que estou vendo isto", como "porque você é pediatra e
  atende em consultório próprio".

**Matriz de afinidade (exemplo).** Pontos por fase de carreira: até 40 / 40 a 55 / 55 a 65+. A
matriz real sai da lista curada na Fase 0.

| Benefício | até 40 | 40 a 55 | 55 a 65+ |
|---|---|---|---|
| Seguro perda de renda (DIT) | 3 | 2 | 1 |
| Defesa profissional | 2 | 3 | 3 |
| Contabilidade e serviços de consultório | 1 | 3 | 2 |
| Assessoria para aposentadoria | 0 | 1 | 3 |
| IESAPM e atualização científica | 2 | 2 | 2 |
| Hotel Fazenda APM | 1 | 2 | 3 |
| Escolas de idiomas | 1 | 3 | 1 |

### 7.4 Como a home fica para as quatro pessoas

Valores e textos ilustrativos.

| | João, acadêmico | Dra. Camila, aspirante | Dra. Helena, efetiva, 46 | Dr. Roberto, efetivo, 61 |
|---|---|---|---|---|
| Pendência | "Envie o comprovante de matrícula para liberar seus benefícios" | "Seu seguro perda de renda está liberado desde ontem" | "Mensalidade de setembro em aberto · segunda via" | não aparece |
| Meu valor | "O que a sua associação cobre": TotalPass, Portal MBE, congresso | "R$ 1.180 em proteção incluída em 2026" | "R$ 1.920 em 2026 · 1,1 vez o que você pagou" | "R$ 3.450 em 2026 · 1,9 vez o que você pagou" |
| Próximo passo | "Passo 2 de 6: ative o TotalPass" | "Defesa profissional libera em 10/11: veja como funciona" | "Você atende em consultório próprio?" | "Quer receber a agenda de cardiologia?" |
| Recomendados | TotalPass, Medway, Portal MBE | declaração para prova de título, IESAPM, plano de saúde | contabilidade, vigilância sanitária, plano de saúde | assessoria para aposentadoria, Hotel Fazenda, atualização em cardiologia |
| Agenda | congresso com condição de acadêmico | curso IESAPM da especialidade | encontro de pediatria | encontro de cardiologia |
| Notícias (F2) | residência e carreira | residência, plantão, saúde mental | gestão de consultório e pediatria | cardiologia e honorários |

### 7.5 Evolução e limites

- **v1 · regras (F1).** Pontuação da seção 7.3 e matriz editável. Transparente e fácil de auditar.
- **v2 · comportamento (F2).** Sinais de uso e leitura com peso maior; teste A/B contra a v1
  (REC-01).
- **v3 · modelo (depois de seis meses de dados).** Aprende com uso e renovação. Só entra se a v2
  mostrar ganho.

Limites que valem para todas as versões: sem dado de saúde; patrocinado sinalizado e limitado; o
associado pode dispensar qualquer recomendação; "por que estou vendo isto" sempre disponível.

---

## 8. Regras de negócio

<a id="elegibilidade"></a>
### 8.1 Elegibilidade

Um benefício está **disponível** quando: a categoria do associado está entre as permitidas **e** o
tempo de filiação é maior ou igual à carência **e** a situação financeira permite **e** a região é
atendida (quando o benefício é regional) **e** o benefício está vigente.

Cada benefício assume um de seis estados para cada associado:

| Estado | Condição | O que o associado vê |
|---|---|---|
| Disponível | todas as condições atendidas | o botão de ação |
| Ativo | já ativou ou usa | selo "ativo" e "gerenciar" |
| Libera em N dias | só falta a carência | a data de liberação e o que fazer até lá |
| Não disponível para a categoria | categoria fora das permitidas | "exclusivo para associado efetivo" e como mudar |
| Suspenso | o atraso passou do limite definido | "regularize para voltar a usar" e a segunda via |
| Indisponível na região | região fora da cobertura | benefícios equivalentes, se houver |

<a id="carencias"></a>
### 8.2 Carências

Regulamento de 01/03/2024. A lista de carências é configurável no backoffice (B13), para que uma
mudança de regra não exija desenvolvimento.

| Carência | Benefícios |
|---|---|
| 6 meses | aquisição de veículos |
| 3 meses | locação de apartamentos; assessoria para aposentadoria; defesa profissional; congressos e cursos de longa duração |
| 2 meses | serviços de despachante; serviços de contabilidade; serviços de vigilância sanitária; anúncios nas mídias da APM; diária de incapacidade temporária (DIT) |
| 1 mês | declaração de associado "AMB para prova de título"; escolas de idiomas; Hotel Fazenda APM |

A carência do Clube de vantagens fica pendente de validação formal com Benefícios e Jurídico antes
de ser publicada ou codificada.

### 8.3 Diferença por categoria

Hoje o regulamento diferencia só pelo tempo de filiação: ao passar de aspirante a efetivo, nada
muda além da cobrança. A presidência e o Financeiro vão definir o que muda entre as categorias. O
motor nasce com a matriz benefício × categoria, para que a regra entre por configuração no dia em
que for aprovada. Também é preciso definir se a mudança de categoria reinicia a contagem de
carência. A recomendação é que não reinicie.

### 8.4 Situação financeira

- Parâmetro "dias de atraso que suspendem benefícios", configurável. O valor está pendente (seção
  17 — *sic*; o documento vai até a seção 15).
- Benefícios de proteção seguem a regra da apólice ou do contrato do parceiro.
- Com atraso, o associado vê a pendência no topo e deixa de receber ofertas comerciais (A09) até
  pagar.

<a id="status-solicitacao"></a>
### 8.5 Ciclo da solicitação

Oito status internos, cada um com o texto que o associado vê e quem pode mudá-lo:

| Status interno | O associado vê | Quem muda |
|---|---|---|
| `criada` | Recebida pela APM | o sistema |
| `enviada` | Enviada ao parceiro | o sistema |
| `em_atendimento` | Em atendimento | o parceiro (API, portal ou relatório) ou a APM |
| `pendente_associado` | O parceiro precisa de algo seu | o parceiro ou a APM |
| `concluida_positiva` | Concluída | o parceiro, a importação ou a APM |
| `concluida_negativa` | Não seguiu | o parceiro, a importação ou a APM |
| `cancelada` | Cancelada | o associado ou a APM |
| `sem_retorno` (marcador) | Aguardando o parceiro, a APM já está cobrando | o sistema, quando o prazo do parceiro vence (A05) |

Toda mudança entra no log imutável com data, status anterior, novo status, origem e conteúdo
enviado. Mudança manual exige justificativa.

<a id="calculo-valor"></a>
### 8.6 Cálculo do valor

| Modalidade | Entra como | Regra | Exemplo |
|---|---|---|---|
| Economia por uso | comprovado | preço de referência menos preço pago, por uso registrado | mensalidade de escola de idiomas de R$ 600 com 30% de desconto dá R$ 180 no mês |
| Desconto informado pelo parceiro | comprovado | valor enviado pelo parceiro, por API ou relatório | resgate no clube com R$ 42 de desconto |
| Serviço prestado pela APM | comprovado | valor de referência do serviço no mercado | atendimento da defesa profissional |
| Proteção incluída | separada da economia | valor de referência anual da cobertura, proporcional aos meses de filiação ativa | seguro perda de renda, defesa profissional |
| Estimado | nunca somado | média por perfil quando não há dado | uso típico de um benefício sem retorno do parceiro |

Todo valor de referência tem fonte, data e aprovação do Financeiro no backoffice, com revisão
anual. A relação com o que o associado pagou é (comprovado + proteção incluída) ÷ total pago no
período.

---

## 9. Backoffice para a equipe interna

O backoffice é onde a APM opera o Minha APM sem depender da TI no dia a dia. Todo acesso tem
verificação em duas etapas e toda ação fica registrada.

<a id="perfis-backoffice"></a>
### 9.1 Perfis de acesso

| Perfil | Vê | Altera |
|---|---|---|
| Administrador (TI) | tudo | usuários, integrações e configurações |
| Produto e conteúdo (Marketing APM e Encantada) | painéis, conteúdo, segmentos e prévia | home, destaques, textos, perguntas frequentes, trilha e matriz de afinidade |
| Benefícios e parcerias (área de produtos, serviços e benefícios) | catálogo, parceiros, solicitações e importações | benefícios, parceiros, regras e importações |
| Central de relacionamento (atendimento) | visão 360, solicitações e fila de ligações | status com justificativa; registra contatos e pedidos do associado |
| Financeiro | valores de referência e painéis | aprova valores de referência |
| Diretoria (presidência e diretores) | painéis | nada |
| Regional (distritais) | painel da regional e interessados da região | registra contatos |
| Parceiro (F2) (parceiros sem API) | só os seus encaminhamentos, com dados mínimos | status dos encaminhamentos (PAR-01) |

<a id="modulos-backoffice"></a>
### 9.2 Módulos

| ID | Módulo | Fase | Conteúdo |
|---|---|---|---|
| B01 | Painel do dia | F1 | solicitações sem retorno, importações pendentes, leads novos, pedidos de cancelamento e alertas de integração |
| B02 | Associados, visão 360 | F1 | busca por CPF, nome ou número; cadastro, categoria, carências com datas, situação financeira, benefícios ativos, solicitações, valor no ano, comunicações recebidas, consentimentos, contatos da Central e score (F2). Somente leitura do cadastro |
| B03 | Benefícios | F1 | ficha com nome, categoria, parceiro, descrição curta e longa, condição, preço de referência e regra de cálculo, elegibilidade (categorias, carência, situação financeira, região), tipo de ativação e destino, prazo de retorno, selos, imagens, perguntas frequentes, contatos, vigência, ordem e afinidade por segmento. Rascunho, aprovação, publicação agendada e histórico |
| B04 | Parceiros e contratos | F1 | dados, contatos, contrato e vigência, requisito técnico (API, relatório ou portal), prazo de retorno, repasse ou comissão e documentos |
| B05 | Solicitações e leads | F1 | fila com filtros, prazo, responsável, mudança de status com justificativa, reenvio e exportação; tela de leads de não associados |
| B06 | Importações | F1 | upload do relatório padrão, validação, prévia com erros por linha, confirmação, histórico e devolução ao parceiro |
| B07 | Home e conteúdo | F1, evolui na F2 | destaques por segmento com vigência, avisos, perguntas frequentes, passos da trilha e textos do sistema |
| B08 | Segmentos | F1, evolui na F2 | regras de segmento, matriz de afinidade e prévia "ver como associado" |
| B09 | Comunicação | log na F1, completo na F2 | gatilhos que o Minha APM emite, log de envios, notificações no app, supressões e descadastros |
| B10 | Clube | F2 | curadoria da oferta da semana e das ofertas em destaque por segmento |
| B11 | Eventos | F2 | agenda, integração com as plataformas e inscrições |
| B12 | Painéis e relatórios | v1 na F1 | painéis da seção 11.5 e exportação |
| B13 | Configurações e LGPD | F1 | usuários e perfis, categorias, carências, parâmetros (dias de atraso, prazos), valores de referência, consentimentos e versões, pedidos do titular e auditoria |

---

## 10. Processos da operação

### 10.1 Publicar ou alterar um benefício

**Gatilho:** novo contrato, mudança de condição ou fim de vigência. **Dono:** Benefícios e
parcerias.
1. Benefícios preenche a ficha no backoffice (B03) como rascunho, com o contrato anexado (B04).
2. Financeiro aprova o valor de referência.
3. Marketing revisa texto e imagem na voz da APM.
4. TI configura a integração, se houver API. Sem API, o parceiro recebe o layout do relatório
   padrão.
5. Benefícios publica com data de início e fim e confere a elegibilidade na prévia "ver como
   associado".
6. A novidade entra no aviso do app e no resumo mensal dos segmentos com afinidade alta (A15).

**Exceções:** parceiro sem requisito técnico no contrato só é publicado depois do aditivo.
Benefício que vence sai do catálogo na data, e quem o tinha ativo recebe aviso.
**Métrica:** até 5 dias úteis do contrato à publicação; 100% dos benefícios com valor de referência
aprovado.

### 10.2 Solicitação de ponta a ponta

**Gatilho:** o associado ativa ou solicita um benefício. **Dono:** Benefícios e parcerias
(acompanhamento) e Central (contato com o associado).
1. O sistema registra, confirma ao associado (A04) e envia ao parceiro pelo canal configurado.
2. O parceiro confirma o recebimento por API, pelo portal do parceiro (F2) ou no relatório.
3. Cada mudança de status entra no log e aparece ao associado.
4. Prazo vencido sem retorno: alerta ao responsável (A05), que cobra o parceiro.
5. Dois prazos vencidos: a Central liga para o associado e registra.
6. Concluída: o resultado entra no meu valor e segue a pergunta "como foi?" (A06).

**Exceções:** associado sem direito: o sistema não deixa solicitar e mostra quando libera. Falha no
envio: reenvio automático e alerta. Associado cancela antes do atendimento: status cancelada.
**Métrica:** 100% com status final; prazo mediano de retorno por parceiro; conversão por parceiro.

### 10.3 Importação mensal do plano B

**Gatilho:** até o dia 10, o parceiro sem API envia o relatório do mês anterior. **Dono:**
Benefícios e parcerias.
1. Recebe o arquivo no layout da seção 13.3.
2. Importa no backoffice (B06).
3. Validação automática: CPF, associado, duplicidade, datas e valores.
4. Corrige ou devolve as linhas com erro.
5. Confirma: os registros entram no meu valor e nos painéis.
6. Financeiro concilia repasses e comissões.

**Exceções:** layout fora do padrão: devolver com o modelo. CPF que não é associado vira lead
(10.4). Atraso: cobrança no dia 11 e registro no contrato depois de dois atrasos.
**Métrica:** parceiros que enviam no prazo; linhas válidas na primeira importação.

### 10.4 Interesse de não associado

**Gatilho:** um parceiro consulta um CPF que não é associado, ou alguém preenche formulário ou
participa de evento. **Dono:** Filiação (produtos, serviços e benefícios) e Central.
1. Registro automático na tela de leads: nome, CPF, telefone, e-mail e origem.
2. Envio ao RD Station, fluxo 1 da régua (A17).
3. Contato da Central em até 2 dias úteis.
4. Resultado registrado: associou, não agora, sem contato.
5. Se associou: fluxo 3 e convite para o primeiro acesso.

**Exceções:** lead sem telefone: só e-mail. Lead que já é ex-associado: fluxo 6.
**Métrica:** leads contatados em até 2 dias úteis; conversão de lead em associado por origem.

### 10.5 Fila de ligações da Central

**Gatilho:** diário, às 8h. **Dono:** Central de relacionamento.
1. O sistema gera a fila na ordem da régua de 29/09: renovação, passagem para efetivo, novo
   associado no 3º mês, cadastrado com interesse, ex-associado. Na F2 entra o score de engajamento
   em risco (A12), logo depois da renovação.
2. O atendente liga e registra: atendeu, não atendeu, pediu retorno, resolveu, quer cancelar.
3. O resultado atualiza o score e suprime mensagens repetidas.

**Exceções:** três tentativas sem resposta: sai da fila por 30 dias e segue só pelos canais
digitais.
**Métrica:** ligações por dia; renovação depois de ligação.

<a id="raci"></a>
### 10.6 Quem faz o quê

| Atividade | Executa | Responde pelo resultado | Consultados | Informados |
|---|---|---|---|---|
| Ficha e publicação de benefício | Benefícios | Benefícios | TI, Marketing APM, Encantada e Financeiro | Central |
| Valor de referência | Benefícios | Financeiro | Encantada | TI, Marketing APM e Central |
| Integração com parceiro | TI | TI | Benefícios | Marketing APM, Encantada, Central e Financeiro |
| Acompanhar solicitações e cobrar parceiro | Benefícios | Benefícios | Central | TI, Marketing APM, Encantada e Financeiro |
| Importação mensal | Benefícios | Benefícios | TI e Financeiro | Marketing APM, Encantada e Central |
| Leads de não associados | Central | Benefícios | Marketing APM | TI, Encantada e Financeiro |
| Fila de ligações | Central | Central | Marketing APM e Encantada | TI, Benefícios e Financeiro |
| Home, destaques e textos | Encantada | Marketing APM | TI e Benefícios | Central e Financeiro |
| Segmentos e matriz de afinidade | Encantada | Marketing APM | TI e Benefícios | Central e Financeiro |
| Gatilhos de comunicação | Encantada | Marketing APM | TI e Central | Benefícios e Financeiro |
| Painéis e relatório mensal | Encantada | Marketing APM | TI, Benefícios e Financeiro | Central |
| Pedidos do titular (LGPD) | TI | encarregado de dados da APM | Central | Benefícios, Marketing APM, Encantada e Financeiro |

---

## 11. Dados para análise

<a id="modelo-de-dados"></a>
### 11.1 Modelo de dados

| Entidade | Origem | O que guarda |
|---|---|---|
| Associado | cadastro (leitura) e perfil | identificador interno, CPF, nome, tratamento, nascimento, contatos, CRM e UF, especialidades, regional |
| Filiação | cadastro | categoria, data de filiação, histórico de categorias, situação, isenção ou remição |
| Situação financeira | cobrança | status, dias de atraso, mensalidades, pagamentos, forma de pagamento |
| Perfil declarado | Minha APM | área de atuação, temas, como prefere ser chamado, canais preferidos |
| Consentimento | Minha APM | finalidade, canal, valor, data, origem, versão do texto |
| Benefício | backoffice | a ficha completa do módulo B03 |
| Parceiro e contrato | backoffice | dados, contatos, vigência, requisito técnico, prazo de retorno, repasse |
| Solicitação | Minha APM | associado, benefício, tipo, status, datas, responsável, resultado |
| Log de status | Minha APM, imutável | solicitação, de, para, data, origem, conteúdo, usuário |
| Uso e valor | Minha APM, parceiros e clube | associado, benefício, data, valor de referência, valor pago, economia, fonte, comprovado ou estimado |
| Importação | Minha APM | arquivo, parceiro, período, linhas válidas e com erro, usuário |
| Conteúdo e evento | portal e plataformas | notícias, eventos, temas, inscrições |
| Segmento e bloco | backoffice | regras, prioridade, vigência, matriz de afinidade |
| Comunicação | RD Station e Minha APM | gatilho, canal, data, entregue, aberto, clicado |
| Evento de uso | analytics | nome, propriedades, data e hora |
| Usuário interno e auditoria | Minha APM | perfil, ações, data, valor anterior |

<a id="eventos-de-uso"></a>
### 11.2 Eventos de uso

Propriedades comuns a todo evento: identificador pseudonimizado do associado (nunca o CPF em
texto), categoria, fase de carreira, especialidade, regional, tempo de casa em meses, dispositivo,
origem (UTM), data e hora.

| Evento | Quando dispara | Propriedades | Serve para |
|---|---|---|---|
| `acesso_primeiro` | primeiro acesso concluído | método (e-mail ou celular), dias desde a filiação | ativação; gatilho A02 |
| `login` | entrada com sucesso ou falha | resultado, motivo da falha | taxa de sucesso de acesso |
| `home_vista` | home exibida | blocos exibidos, segmento | personalização |
| `home_bloco_clicado` | clique em bloco da home | bloco, posição, item | recomendação |
| `busca` | busca realizada | termo, quantidade de resultados | busca sem resultado vira ajuste de catálogo |
| `beneficio_visto` | página de benefício aberta | benefício, origem (home, catálogo, busca, e-mail), estado | interesse; gatilho A07 |
| `recomendacao_dispensada` | recomendação dispensada | benefício, motivo | recomendação |
| `solicitacao_criada` | benefício ativado ou solicitado | benefício, tipo de ativação | uso; rastro |
| `solicitacao_status` | status alterado | de, para, origem (sistema, parceiro, importação, usuário) | rastro; prazo do parceiro |
| `uso_registrado` | uso confirmado com valor | benefício, valor de referência, valor pago, economia, fonte | meu valor; painel de parceiros |
| `carencia_vencida` | benefício liberado pela carência | benefício, data | gatilho A03 |
| `carteirinha_aberta` | carteirinha exibida | origem | uso presencial |
| `carteirinha_validada` | QR validado por terceiro | resultado (ativo ou não) | uso em parceiros e eventos |
| `financeiro_segunda_via` | segunda via gerada | competência, forma | autoatendimento |
| `pagamento_confirmado` | pagamento confirmado (vem da cobrança) | competência, forma | gatilho A09 (encerra) |
| `meu_valor_visto` | página de valor aberta | período, valor exibido | percepção de valor |
| `clube_acesso` | entrada no clube | origem | clube |
| `clube_resgate` | resgate de oferta (vem do clube) | oferta, economia | meu valor |
| `evento_inscricao` | inscrição em evento | evento, preço por perfil | eventos |
| `evento_presenca` | presença ou certificado | evento | eventos |
| `conteudo_lido` | notícia ou artigo aberto | conteúdo, tema, tempo de leitura | radar |
| `tema_seguido` | tema seguido ou deixado | tema, ação | radar |
| `trilha_passo` | passo da trilha concluído | passo, dia da jornada | ativação |
| `perfil_atualizado` | campo do perfil preenchido | campo | personalização |
| `consentimento` | consentimento dado ou retirado | finalidade, canal, versão do texto | LGPD |
| `notificacao` | notificação recebida ou aberta | tipo, ação | comunicação |
| `ajuda_contato` | contato com a Central aberto | assunto, canal | atendimento |
| `cancelamento_pedido` | pedido de cancelamento | motivo | retenção; gatilho A16 |

#### 11.2.1 Níveis de evidência e qualidade do dado

A mesma jornada não significa a mesma qualidade de informação. O sistema classifica cada benefício
e cada registro no nível de evidência abaixo; essa classificação determina o que pode entrar nos
painéis, no Meu valor e na comunicação.

| Nível | Nome | Significado |
|---|---|---|
| 1 | Visibilidade | a pessoa viu o benefício ou a oferta. Mede interesse; não é uso nem gera valor em reais |
| 2 | Interesse ou solicitação | a pessoa iniciou uma ativação, encaminhamento ou reserva. Mede intenção e operação; não é uso confirmado |
| 3 | Uso confirmado | a APM, o parceiro ou a importação confirmou a conclusão. Mede uso real e pode alimentar retenção, satisfação e prazo do parceiro |
| 4 | Valor comprovado | há fonte, data, valor de referência ou economia e validação do Financeiro. Só este nível compõe economia comprovada no Meu valor |

Todo benefício do catálogo recebe uma modalidade de mensuração no backoffice: API ou acesso único;
relatório padrão validado; ou encaminhamento rastreado sem retorno de uso. O catálogo é único, mas
a cobertura de mensuração fica explícita nos painéis internos.

**Qualidade do dado.** Os painéis acompanham completude, duplicidade, atraso de retorno, registros
sem associação e taxa de conciliação por parceiro. Dado sem qualidade não entra como prova de
valor.

<a id="indicadores"></a>
### 11.3 Indicadores

| # | Indicador | Periodicidade | Definição | Referência / hipótese |
|---|---|---|---|---|
| 1 | Associados com acesso | mensal | associados com pelo menos 1 acesso no mês ÷ base ativa | linha de base no piloto |
| 2 | Ativação em 30 dias | mensal | novos com pelo menos 1 uso registrado ou solicitação concluída em 30 dias ÷ novos do mês | acima de 30% |
| 3 | Benefícios em uso | mensal | média de benefícios distintos com uso nos últimos 90 dias por associado ativo | linha de base |
| 4 | Valor entregue | mensal | comprovado + proteção incluída por associado, e a relação com o que pagou | linha de base |
| 5 | Rastro | semanal | solicitações com status final ÷ solicitações criadas | 100% |
| 6 | Prazo do parceiro | semanal | mediana de dias entre envio e retorno, por parceiro | prazo do contrato |
| 7 | Conversão por parceiro | mensal | solicitações concluídas positivas ÷ solicitações | linha de base |
| 8 | Novos associados com origem | mensal | filiações do mês por origem (métrica da presidência) | — |
| 9 | Taxa de conversão | mensal | cadastrado → efetivo; aspirante → efetivo; lead → associado | histórico 6% a 7,5% no funil; 8% aspirante→efetivo |
| 10 | Pessoas comunicadas e retorno | mensal | associados que receberam ao menos 1 mensagem; abertura, clique e resposta (métrica da presidência) | — |
| 11 | Renovação por nível de uso | na renovação | renovação de quem usou ≥ 1 benefício × quem não usou, por coorte e tempo de filiação; indicador da tese, não causalidade | — |
| 12 | Cancelamento precoce | mensal | cancelamentos em até 90 dias ÷ novos | abaixo de 3% |
| 13 | Motivo "não utiliza" | mensal | participação nos cancelamentos | abaixo de 40% |
| 14 | Saúde técnica | diária | sucesso de acesso, LCP no celular, erros de JavaScript, disponibilidade | — |

### 11.4 Score de engajamento (F2)

Uma nota de 0 a 100 por associado, recalculada todo dia, somando cinco componentes: recência de
acesso (até 30); benefícios em uso nos últimos 90 dias (até 30); interação com a comunicação
(abertura, clique, resposta; até 15); situação financeira em dia (até 15); eventos e conteúdo (até
10). Faixas: 60 ou mais, saudável; 30 a 59, atenção (o resumo mensal reforça uma recomendação);
abaixo de 30, risco (fila de ligações, A12). Os pesos são calibrados com os cancelamentos reais
depois de três meses de dados.

### 11.5 Painéis

| Painel | Público | Periodicidade | Conteúdo |
|---|---|---|---|
| Diretoria | presidência e diretores | mensal, junto do relatório contratual | indicadores 8, 9, 10, 4 e 11, e investimento × resultado |
| Benefícios e parceiros | Benefícios e Financeiro | mensal | uso por benefício, conversão, prazo e economia gerada; o patrocinador vê só o agregado dele |
| Operação | Benefícios e Central | diário | fila, atrasos, importações, leads e ligações |
| Produto | Marketing, Encantada e TI | semanal | acesso, ativação, busca sem resultado, cliques por bloco e desempenho |
| Regionais | distritais | mensal | associados, novos, uso e interessados da região |

<a id="lgpd"></a>
### 11.6 LGPD e governança

- Base legal por finalidade. Consentimento para ofertas de parceiros e para WhatsApp de
  relacionamento; mensagens transacionais seguem a execução do contrato de associação.
- Minimização: o parceiro recebe só o necessário para atender.
- Dado de saúde fora do sistema. Em serviços sigilosos, a APM registra apenas o fato do uso, de
  forma agregada.
- Parceiros e patrocinadores recebem só agregados, com no mínimo 20 pessoas por recorte, para
  impedir identificação.
- Analytics com identificador pseudonimizado.
- Direitos do titular pelo perfil (baixar dados, pedir exclusão), com fila no backoffice.
- Prazo de guarda de logs de solicitação e auditoria definido pelo jurídico.

---

## 12. Automação de comunicação a partir dos dados

### 12.1 Como funciona

O Minha APM não substitui o RD Station. Ele gera o dado (quem entrou, o que usou, quanto economizou,
o que liberou) e envia campos e eventos ao RD, onde a régua de 29/09 já está montada, com 69 peças
em 8 fluxos. Mensagens transacionais (código de acesso, solicitação, cobrança) saem do próprio
sistema. Notificações no app são do Minha APM. A fila de ligações vive no backoffice.

Evento no Minha APM → campo ou evento no RD Station → fluxo da régua (e-mail, WhatsApp, SMS) →
clique volta com UTM e código do gatilho → novo evento no Minha APM.

<a id="gatilhos"></a>
### 12.2 Gatilhos

Vinte gatilhos, cada um com a condição, a ação e o canal, o fluxo da régua e a fase em que entra.

| ID | Gatilho | Quando | Ação | Fluxo da régua | Fase |
|---|---|---|---|---|---|
| A01 | Filiação confirmada (vem do cadastro) | sempre | e-mail + WhatsApp com link de primeiro acesso | 3 · novo associado (D0) | F1 |
| A02 | Primeiro acesso não feito | 3 dias após A01 | WhatsApp ou SMS com link direto e ajuda da Central | 3 | F1 |
| A03 | Carência vencida | benefício relevante para o segmento | aviso no app + e-mail: "a partir de hoje você tem…" | 3 (1, 2, 3 e 6 meses) | F1 |
| A04 | Solicitação criada | sempre (transacional) | e-mail e aviso no app com prazo e próximo passo | transacional | F1 |
| A05 | Solicitação sem retorno no prazo do parceiro | prazo configurado vencido | alerta interno ao responsável; aviso ao associado de que a APM está cobrando | operação | F1 |
| A06 | Solicitação concluída | resultado registrado | pergunta "como foi?" de 0 a 10 | transacional | F1 |
| A07 | Benefício visto 2 vezes sem ativar | em 14 dias | e-mail ou WhatsApp: tirar dúvida sobre aquele benefício | 4 · efetivo | F2 |
| A08 | Resumo mensal | todo associado ativo, 1 vez por mês | e-mail "o que é seu em {mês}" com números do meu valor | 4 · efetivo | F2 (F1 com proteção incluída) |
| A09 | Mensalidade vencida sem pagamento | 3 dias após o vencimento | lembrete com segunda via direta; suspende ofertas comerciais até pagar | cobrança | F1 |
| A10 | Renovação chegando | 60, 30 e 7 dias; ligação 10 dias após se não renovou | meu valor anual em PDF + ligação da Central | 4 · efetivo | F2 |
| A11 | Sem acesso e sem uso | 90 dias | reativação com 1 benefício recomendado | 4 · efetivo | F2 |
| A12 | Score de engajamento em risco | score abaixo de 30 | entra na fila de ligações da Central | operação | F2 |
| A13 | Mudança de categoria | acadêmico para aspirante (CRM) ou aspirante para efetivo | o que muda, o que passa a ter, novo benefício | 5 · acadêmicos e recém-formados | F2 |
| A14 | Evento da especialidade ou região publicado | segue o tema ou é da região | convite com inscrição em um toque | 4 ou 5 | F2 |
| A15 | Novo benefício com afinidade alta | pontuação alta para o segmento | aviso no app + entra no resumo mensal (sem e-mail isolado) | 4 | F2 |
| A16 | Pedido de cancelamento | sempre | motivo em um toque, oferta de conversa, fluxo de ex-associado | 6 · ex-associados | F1 |
| A17 | Interesse de não associado (parceiro ou formulário) | sempre | registro na tela de leads + fluxo de contato recente | 1 · contato recente | F1 |
| A18 | Aniversário e Dia do Médico | data | mensagem da APM | 4 | F1 (já no RD) |
| A19 | Documentação pendente (acadêmico) | 7 dias após o cadastro | lembrete com envio direto do documento | 5 | F2 |
| A20 | Trilha parada | 7 dias sem novo passo nos primeiros 90 dias | próximo passo sugerido | 3 ou 5 | F2 |

### 12.3 Regras de orquestração

- **Transacional sempre sai** e não conta no limite.
- **Limite de relacionamento:** até duas mensagens por semana por pessoa, somando canais; WhatsApp
  no máximo uma. Proposta a validar com Marketing.
- **Prioridade entre fluxos**, quando alguém cai em dois ao mesmo tempo: 3, depois 5, 4, 6, 1 e 2
  (régua de 29/09).
- **Supressão:** pendência financeira suspende ofertas comerciais; a recomendação de um benefício
  some por 14 dias depois de o associado solicitá-lo; quem pediu cancelamento sai dos fluxos de
  efetivo.
- **Consentimento** por canal e finalidade; descadastro em um toque, refletido no RD na hora.
- **Horário:** 8h às 20h em dias úteis; exceções datadas, como o Dia do Médico.
- **Canal:** o preferido no perfil; sem preferência, o de maior abertura daquela pessoa.
- **Medição:** todo link com UTM e código do gatilho.

---

## 13. Integrações

<a id="integracoes"></a>
### 13.1 Mapa

| Integração | Fase | O que troca | Como | Situação segundo a spec |
|---|---|---|---|---|
| Cadastro de associados (atual; novo em desenvolvimento) | F1 | dados cadastrais, categoria, filiação, regional, especialidade, situação e avisos de mudança | API e avisos automáticos, atrás da camada INT-01 | pendente: contrato de dados (F0-02) |
| Cobrança | F1 | situação, mensalidades, segunda via e pagamentos | API e aviso de pagamento | depende do novo sistema de cobrança |
| Login atual da APM | F1 | contas existentes, reaproveitadas ou migradas sem recadastro | — | decisão na F0-03 |
| API de consulta de associação | F1 | o parceiro confirma se o CPF é associado | — | já existe e está em uso |
| RD Station | F1 | campos e eventos para a régua, e leads | API do RD | contratado |
| Parceiros com API | F1, evolui na F2 | envio da solicitação e retorno de status e uso | API ou aviso automático | definido por parceiro |
| Parceiros sem API | F1 | retorno mensal pelo relatório padrão (13.3) | arquivo | plano B oficial |
| Qualicorp (plano de saúde) | F2 | consulta de CPF, oportunidade e fechamento | API ou relatório | custo da API em levantamento |
| Clube de vantagens (plataforma atual) | F1 como link, F2 integrado | acesso único, ofertas e resgates | acesso único e API ou relatório | a negociar com o fornecedor |
| Plataformas de eventos e IESAPM | F2, evolui na F3 | inscrições, presença e certificados | link ou incorporação e depois API | a mapear na F0-01 |
| Portal (WordPress), Portal MBE e biblioteca | F2 | notícias, conteúdo e acesso | API do WordPress e acesso único | a mapear |
| WhatsApp (API oficial) e SMS | F2 | envios da régua | pelo RD ou direto | pendente de contrato |
| Analytics e painéis | F1 | eventos de uso | ferramenta a definir (F0-06) | o Clarity já está instalado no portal |

<a id="contrato-de-dados"></a>
### 13.2 O que o Minha APM precisa do cadastro e da cobrança

Esta lista é a base do contrato de dados (F0-02) com quem desenvolve o novo sistema de cadastro e
cobrança.

| Grupo | Campos | Serve para |
|---|---|---|
| Identificação | identificador interno estável, CPF, nome, nome social e data de nascimento | acesso, tratamento e fase de carreira |
| Contato | e-mail e celular | código de acesso e comunicação |
| Filiação | categoria atual, data de filiação, histórico de categorias com datas, situação (ativo, suspenso, cancelado), isenção ou remição | elegibilidade e carências |
| Profissional | CRM e UF (quando houver), especialidades, regional ou distrital | personalização |
| Financeiro | situação (em dia ou em atraso, com dias), valor e forma de pagamento, mensalidades (competência, vencimento, valor, status), segunda via (PDF, linha digitável, Pix) e pagamentos do ano | financeiro e meu valor |
| Avisos automáticos | filiação criada, categoria alterada, pagamento confirmado, mensalidade vencida, cancelamento, contato alterado | gatilhos e atualização em tempo real |
| Escrita | atualização de contato feita pelo associado, ou pedido registrado para a equipe do cadastro | perfil |
| Requisitos | homologação com dados anonimizados; documentação da API; consultas respondendo em menos de 1 s; aviso de manutenção | — |

<a id="csv-plano-b"></a>
### 13.3 Relatório padrão do plano B

Arquivo CSV em UTF-8, separado por ponto e vírgula, um por parceiro por mês, enviado até o dia 10
por canal autenticado e protegido; nunca por e-mail comum. Sempre que possível, usa o identificador
interno da APM em vez de CPF. O campo `id_externo` impede duplicidade. A primeira linha do arquivo é
esta:

```
cpf;parceiro_id;beneficio_id;tipo;data_evento;status;valor_referencia;valor_pago;economia;id_externo;observacao
```

| Coluna | Obrigatória | Formato | Exemplo |
|---|---|---|---|
| `cpf` | sim | 11 dígitos, sem pontos | — |
| `parceiro_id` | sim | código APM do parceiro | PAR017 |
| `beneficio_id` | sim | código APM do benefício | BEN042 |
| `tipo` | sim | lead, contratacao, uso ou cancelamento | — |
| `data_evento` | sim | AAAA-MM-DD | 2026-10-14 |
| `status` | sim | em_andamento, ganho, perdido ou usado | — |
| `valor_referencia` | não | reais, com ponto decimal | 600.00 |
| `valor_pago` | não | reais | 420.00 |
| `economia` | não | reais | 180.00 |
| `id_externo` | sim | identificador do registro no parceiro | ESC-99812 |
| `observacao` | não | texto de até 200 caracteres | mensalidade de outubro |

---

<a id="rnf"></a>
## 14. Requisitos não funcionais

- **Celular.** Desenhado a partir de 360 px; alvos de toque com pelo menos 44 px; Safari (iPhone)
  e Chrome (Android) das duas últimas versões. O Safari do iPhone é hoje o navegador mais usado no
  portal.
- **Desempenho.** LCP abaixo de 2,5 s e INP abaixo de 200 ms no percentil 75 do celular; imagens
  otimizadas; páginas principais leves.
- **Instalável.** Aplicativo web instalável (PWA), com ícone na tela inicial. App nativo só se os
  dados de uso justificarem.
- **Segurança.** HTTPS; senhas com hash forte; verificação em duas etapas no backoffice; limite de
  tentativas; proteção contra as falhas mais comuns da lista OWASP; segredos fora do código.
- **LGPD.** Seção 11.6; consentimento versionado; registro de acesso a dados pessoais no
  backoffice.
- **Auditoria.** Log imutável de solicitações e de ações no backoffice.
- **Acessibilidade.** WCAG 2.2 AA; texto ampliável sem quebrar a tela; contraste; navegação por
  teclado; leitor de tela; nenhum estado comunicado só por cor; testes com associadas e associados
  de diferentes faixas etárias.
- **Disponibilidade e monitoramento.** Alertas de erro (há erros de JavaScript em produção no
  portal hoje); cópia de segurança diária com teste de restauração.
- **Ambientes.** Desenvolvimento, homologação com dados anonimizados e produção; publicação
  automatizada.
- **Conteúdo.** Tudo o que muda com frequência é editável no backoffice, sem nova publicação.
- **Chaves de funcionalidade.** Mensalidade patrocinada, cartão, comunidade e novos tipos de
  ativação nascem desligados e são ligados por configuração.
- **Documentação.** API documentada (OpenAPI) e manual de operação do backoffice. Nada só na cabeça
  de uma pessoa.
- **Identidade visual.** Paleta da APM: azul #004165, verde #009581, verde-escuro #00675A, cinza
  #616365. Verdana na interface digital, conforme o brandbook.

---

<a id="governanca"></a>
## 15. Governança, priorização e gates de implementação

### 15.1 Gate de fundação (F0)

- A F1 só começa quando estiverem documentados e aprovados: base conciliada com identificador
  canônico; fonte de autenticação e situação do associado comprovada; catálogo inicial com regras
  e carências validadas; contrato de dados e medição para cada parceiro; destino dos eventos,
  acessos e critérios de LGPD.
- Se algum item não estiver pronto, a funcionalidade fica fora do backlog de desenvolvimento ou
  entra apenas como encaminhamento rastreado. Nunca como integração, uso confirmado ou promessa de
  economia.

### 15.2 Escopo protegido da F1

- A F1 prioriza P01, P02, P03/P04, P05, P06 v1, P09, P13/P14 e o backoffice B01–B06, B12 e B13. É o
  mínimo para concentrar a jornada, iniciar a mensuração e gerir o catálogo com consistência.
- P07 (carteirinha) e P08 (financeiro) só entram na F1 se passarem no gate técnico de dados e
  validação. SSO, resgates, APIs de parceiros, carteira do celular, cartão, cashback, patrocínio e
  comunidade permanecem em fases posteriores ou como hipótese desligada até haver contrato e prova
  técnica.

### 15.3 Governança e decisão

- Marketing APM é dono da decisão de produto e do aceite de experiência, com a Encantada validando
  produto e UX. Benefícios decide o catálogo e suas regras; Financeiro aprova valores de referência
  e impactos de cobrança; TI responde por segurança, integrações e disponibilidade; Jurídico e o
  encarregado de dados validam contratos, privacidade e critérios aplicáveis.
- O comitê semanal registra decisão, dono, prazo, evidência e impacto de cada pendência. Nenhuma
  regra de benefício, carência ou valor entra em produção sem responsável e evidência de aprovação.

### 15.4 Critérios de aceite

- Cada entrega só é aceita quando tiver objetivo de negócio, comportamento esperado do associado,
  estado vazio e de erro, evento de medição, fonte do dado, regra de privacidade e responsável pelo
  aceite. O aceite combina Marketing APM e Encantada para experiência; Benefícios e Financeiro para
  regra de negócio; TI para requisito técnico e segurança.

### 15.5 Decisões pendentes antes da publicação

- Devem ser formalizadas antes de publicar ou desenvolver a primeira versão do catálogo: carência
  do Clube de Vantagens; contagem e categorias da base conciliada; regra de mudança de categoria;
  contratos de patrocínio e cartão; destino dos dados analíticos, acesso aos painéis e contrato de
  dados dos parceiros.

---

*Fim da transcrição. Códigos de item citados no original sem definição própria (ACE-01..05,
HOM-01, CAT-02/03/05, SOL-01/04, VAL-01/03, CAR-01..03, INT-01/02, FIN-01/03/04, CLU-01..03,
EVE-01/02, NEWS-01, TRI-01, PER-02/03, AJU-01/02, NOT-02, REC-01, WAL-01, PAR-01, ADM-05, DIR-01,
COM-01, MEN-01, ENC-01, MZ-01, CARD-01, CON-01, F0-01/02/03/06) estão reunidos em
[`INDICE-IDS.md`](INDICE-IDS.md).*
