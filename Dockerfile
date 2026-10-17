# =====================================================================
# Estágio 1 — build da SPA (ADR-0001). Node existe SÓ aqui: a imagem final
# não tem Node, npm nem node_modules.
# Node 24 (LTS): o npm 11 que acompanha resolve a árvore de pares do
# Vitest/Vite que o npm 10 do Node 22 não resolve (erro "edgesOut").
# =====================================================================
FROM node:24-bookworm-slim AS frontend

ENV npm_config_update_notifier=false \
    npm_config_fund=false \
    npm_config_audit=false

WORKDIR /frontend

# Dependências primeiro (cache de camada): só muda quando o lock muda.
# --ignore-scripts: nenhum pacote roda código na instalação; os binários
# nativos (rolldown) chegam como dependências opcionais por plataforma.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY frontend/ ./
# Portão de qualidade: tipos, lint (regras de CSP/segurança) e testes
# unitários. Se algo falhar, a imagem não é construída.
RUN npm run check && npm run build


# =====================================================================
# Estágio 2 — runtime. Mesma base do login_associado: Python 3.12 slim tem
# wheels prontas para cryptography/pymysql, dispensando toolchain na imagem.
# =====================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl: healthcheck e download do bundle de CAs do RDS.
# O bundle fica embutido na imagem (0444) e é o que permite verificar o
# certificado do RDS (ssl_verify_cert + ssl_verify_identity em database.py).
# Mesmo padrão dos containers PHP (apm-parceiros, totalpass, appapm).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /etc/ssl/rds \
    && curl -fsSL --retry 3 --retry-delay 2 \
         https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
         -o /etc/ssl/rds/global-bundle.pem \
    && chmod 0444 /etc/ssl/rds/global-bundle.pem \
    && grep -q "BEGIN CERTIFICATE" /etc/ssl/rds/global-bundle.pem

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts
# Build da SPA (estágio 1) servido pelo FastAPI em /static/spa (index em /area).
COPY --from=frontend /frontend/dist ./app/static/spa

# Usuário sem privilégios (mesmo uid do login_associado). Os arquivos da
# aplicação ficam do root: o processo lê, não altera (e o container é read_only).
RUN useradd --create-home --uid 10001 appuser \
    && test -f /app/app/static/spa/index.html
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "60"]
