# ADR-0005: Foto de perfil em `contact.entityimage`, redimensionada no servidor

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0002

## Contexto

O usuário pediu que o associado possa enviar uma foto de perfil, exibida na área e na
carteirinha. O CRM (Dataverse) é a fonte do cadastro do associado; manter a foto fora dele
criaria um atributo de cadastro invisível ao atendimento. O `contact` do Dataverse já possui o
campo padrão `entityimage` (imagem, redimensionada pelo próprio Dataverse para 144×144 em
`entityimage` e armazenada em tamanho maior em `entityimage_url`), mas **nenhum projeto irmão o
utiliza** hoje, portanto não há conector pronto.

O container da área roda `read_only`, com apenas `/tmp` em tmpfs e limite de 400 MB de memória.
Processar imagem em disco é inviável e processar em memória precisa de teto rígido. Uploads de
imagem são vetor clássico de abuso: *decompression bomb*, arquivos poliglotas, metadados EXIF com
geolocalização, extensão falsa.

Pelo ADR-0002, a gravação no CRM passa pelo `mcp_hub` (ferramenta `associado.foto_atualizar`),
que ainda não existe; a área precisa funcionar em `HUB_MODE=stub` sem perder a miniatura local.

## Decisão

1. A foto canônica fica em **`contact.entityimage`**, gravada via hub
   `associado.foto_atualizar(contact_id, jpeg_base64)`.
2. Endpoint `POST /api/v1/perfil/foto`, `multipart/form-data`, campo `foto`, lido **em
   memória** com teto de **5 MB** (verificado por `Content-Length` e por leitura incremental com
   corte). O vhost do porteiro aplica `client_max_body_size 6m` **somente** nessa `location`;
   o resto da área continua com o padrão de 1 MB.
3. Tipo detectado por **magic bytes** (JPEG `FF D8 FF`, PNG `89 50 4E 47`, WebP `RIFF....WEBP`);
   extensão e `Content-Type` do cliente são ignorados. Outro tipo → 415 `tipo_nao_suportado`.
4. Processamento com **Pillow**, em `run_in_threadpool`:
   - `Image.MAX_IMAGE_PIXELS = 25_000_000` (lança `DecompressionBombError` → 413);
   - `ImageOps.exif_transpose` para respeitar a orientação, depois **descarte de todos os
     metadados** (EXIF, ICC, XMP) ao salvar;
   - conversão para RGB, **recorte central quadrado**, redimensionamento com `LANCZOS`;
   - saída **512×512 JPEG qualidade 85** para o CRM (recompressão progressiva até ≤ 256 kB);
   - saída **128×128 JPEG** gravada em `associado_perfil.foto_miniatura` (`VARBINARY(65535)`),
     com `foto_etag CHAR(32)` (md5 do conteúdo) e `foto_atualizada_em`.
5. Miniatura servida por `GET /api/v1/perfil/foto` com `ETag`, `If-None-Match` → 304, e
   `Cache-Control: private, max-age=300`. Sem miniatura → 204 e a UI exibe **avatar com
   iniciais** (cor derivada do `contact_id`, ver ADR-0013 para o mecanismo sem inline).
6. Limite de **5 uploads por hora por associado** (contador em `evento_uso` por `acao =
   'perfil.foto_enviar'` na última hora; excedente → 429).
7. Remoção da foto: `POST /api/v1/perfil/foto/remover` zera `foto_miniatura` e chama
   `associado.foto_atualizar(contact_id, null)`; sem `DELETE` (ADR-0004).
8. A escrita no CRM é **síncrona** dentro da requisição (timeout 10 s); se o hub falhar, a
   miniatura local **não é gravada** e o associado recebe 503 `hub_indisponivel` — evita
   divergência entre a área e o CRM.

## Consequências

### Positivas
- Foto visível no CRM, onde o atendimento já trabalha, sem armazenamento próprio de arquivos.
- Nenhum byte do arquivo original é persistido: o que vai ao CRM e ao MySQL é sempre uma
  imagem regenerada pelo Pillow, sem metadados.
- Superfície de ataque contida: teto de bytes, teto de pixels, tipo por conteúdo, processamento
  isolado em threadpool.

### Negativas / riscos
- Pillow entra em `requirements.txt` (dependência nativa; precisa de atualização regular por
  CVEs).
- Pico de memória por upload (decodificação de até 25 MP ≈ 75 MB em RGB); com 2 workers e
  teto de 400 MB, concorrência de uploads precisa de limite (semáforo de 2 processamentos
  simultâneos por worker, excedente → 503 `ocupado`).
- Dependência síncrona do hub nesse endpoint; indisponibilidade do hub bloqueia a troca de
  foto (aceito: é ação rara).
- `entityimage` tem comportamento próprio no Dataverse (gera `entityimage_url`, tamanho
  máximo de 10 MB); o conector no hub precisa validar isso (P-05 cobre o papel de escrita).

### Obrigações decorrentes
- Migração `sql/00N_associado_perfil.sql` com `GRANT UPDATE` justificado (ADR-0004).
- Vhost: `location = /api/v1/perfil/foto { client_max_body_size 6m; limit_req ... }`.
- Testes: magic bytes vs extensão falsa, *decompression bomb* (PNG 30.000×30.000), EXIF
  removido, orientação aplicada, recorte central, tamanho ≤ 256 kB, 429 no sexto upload,
  rollback da miniatura quando o hub falha.
- Semáforo de processamento documentado em `app/perfil/foto.py` e exposto em `/db-health`
  como contador de rejeições.
- Hub: ferramenta `associado.foto_atualizar` com validação de tamanho e tipo do lado do hub
  (defesa em profundidade).

## Alternativas descartadas

- **S3 privado com URL assinada.** Exigiria credencial AWS no container (nova superfície de
  segredo) e deixaria a foto invisível ao CRM, contrariando o CRM como fonte do cadastro.
- **BLOB da imagem cheia no MySQL.** Infla o RDS com dados binários grandes, duplica a fonte
  da verdade e continua invisível ao atendimento.
