# Mesma base do login_associado: Python 3.12 slim tem wheels prontas para
# cryptography/pymysql, dispensando toolchain de compilação na imagem.
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

# Usuário sem privilégios (mesmo uid do login_associado).
RUN useradd --create-home --uid 10001 appuser
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
