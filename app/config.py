"""Configurações da aplicação (pydantic-settings).

Única fonte de leitura de ambiente. Nada de `os.getenv` espalhado: campo novo
entra aqui, tipado, com alias igual ao nome da variável.

Os validadores no fim são a lei do projeto: combinações inseguras (modo stub em
produção, TLS do banco sem verificação em produção) impedem o container de subir.
"""

import re
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENVS = ("production", "staging", "development", "test")
_AUTH_MODES = ("oidc", "stub")
_MIN_SECRET_LEN = 32
# Chave de flag: minúsculas, dígitos e sublinhado (mesmo formato da tabela feature_flag).
_FLAG_KEY = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
# Número do WhatsApp em formato E.164 sem o "+": DDI + DDD + número.
_WHATSAPP = re.compile(r"^[1-9][0-9]{9,14}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Banco de dados (RDS MySQL) — schema EXCLUSIVO `area_associado`.     #
    # ------------------------------------------------------------------ #
    db_host: str = Field(..., alias="DB_HOST")
    db_port: int = Field(3306, alias="DB_PORT")
    db_user: str = Field(..., alias="DB_USER")
    db_pass: str = Field(..., alias="DB_PASS")
    db_name: str = Field(..., alias="DB_NAME")
    db_ssl_ca: str = Field("/etc/ssl/rds/global-bundle.pem", alias="DB_SSL_CA")
    db_ssl_verify: bool = Field(True, alias="DB_SSL_VERIFY")
    db_pool_size: int = Field(5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(1800, alias="DB_POOL_RECYCLE")

    # ------------------------------------------------------------------ #
    # Aplicação                                                          #
    # ------------------------------------------------------------------ #
    app_env: str = Field("production", alias="APP_ENV")
    secret_key: str = Field(..., alias="SECRET_KEY")
    session_max_age: int = Field(28800, alias="SESSION_MAX_AGE")          # 8 h deslizante
    session_absolute_max: int = Field(43200, alias="SESSION_ABSOLUTE_MAX")  # 12 h desde o login
    public_base_url: str = Field("https://minha.apm.org.br", alias="PUBLIC_BASE_URL")

    # ------------------------------------------------------------------ #
    # Autenticação: `oidc` (login_associado) ou `stub` (construção).      #
    # ------------------------------------------------------------------ #
    auth_mode: str = Field("oidc", alias="AUTH_MODE")
    dev_stub_token: str | None = Field(None, alias="DEV_STUB_TOKEN")

    # ------------------------------------------------------------------ #
    # OIDC — esta app como Relying Party do login.apm.org.br.             #
    # ------------------------------------------------------------------ #
    oidc_issuer: str = Field("https://login.apm.org.br", alias="OIDC_ISSUER")
    oidc_backchannel_base_url: str = Field(
        "http://login_associado:8000", alias="OIDC_BACKCHANNEL_BASE_URL"
    )
    oidc_client_id: str = Field("area-associado", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(None, alias="OIDC_CLIENT_SECRET")
    oidc_scopes: str = Field("openid profile email cpf carteirinha", alias="OIDC_SCOPES")
    oidc_pending_ttl: int = Field(600, alias="OIDC_PENDING_TTL")
    oidc_jwks_ttl: int = Field(300, alias="OIDC_JWKS_TTL")
    oidc_http_timeout: float = Field(10.0, alias="OIDC_HTTP_TIMEOUT")
    oidc_leeway: int = Field(60, alias="OIDC_LEEWAY")

    # ------------------------------------------------------------------ #
    # Auditoria                                                          #
    # ------------------------------------------------------------------ #
    log_hash_key: str | None = Field(None, alias="LOG_HASH_KEY")
    evento_log_table: str = Field("evento_log", alias="EVENTO_LOG_TABLE")

    # ------------------------------------------------------------------ #
    # Sessão cifrada (ADR-0011). Lista separada por vírgula: a PRIMEIRA   #
    # cifra; todas decifram (rotação sem derrubar sessões). Ausente fora  #
    # de produção → derivada de SECRET_KEY por HKDF.                      #
    # ------------------------------------------------------------------ #
    session_enc_keys: str | None = Field(None, alias="SESSION_ENC_KEYS")

    # ------------------------------------------------------------------ #
    # Interface (SPA) — configurações entregues em GET /api/v1/sessao.    #
    # ------------------------------------------------------------------ #
    whatsapp_central: str = Field("551131886200", alias="WHATSAPP_CENTRAL")
    show_whatsapp: bool = Field(True, alias="SHOW_WHATSAPP")
    animations: bool = Field(True, alias="ANIMATIONS")
    # Flags forçadas desligadas: vencem a tabela feature_flag (ADR-0007).
    flags_forcar_desligadas: str = Field(
        "mensalidade_zero,fatura_valor,patrocinio", alias="FLAGS_FORCAR_DESLIGADAS"
    )
    flags_cache_ttl: int = Field(60, alias="FLAGS_CACHE_TTL")
    # Origens https permitidas em img-src (CSP) e no filtro de imagens do job do portal.
    csp_img_hosts: str = Field("https://www.apm.org.br", alias="CSP_IMG_HOSTS")

    # ------------------------------------------------------------------ #
    # mcp_hub (ADR-0002) — único caminho até o CRM/ERP. `stub` = dados    #
    # determinísticos em memória, proibido em produção.                   #
    # ------------------------------------------------------------------ #
    hub_mode: str = Field("stub", alias="HUB_MODE")
    hub_base_url: str = Field("http://mcp_hub:8000", alias="HUB_BASE_URL")
    hub_public_host: str = Field("mcp.apm.org.br", alias="HUB_PUBLIC_HOST")
    hub_client_id: str = Field("area-associado", alias="HUB_CLIENT_ID")
    hub_client_secret: str | None = Field(None, alias="HUB_CLIENT_SECRET")
    hub_timeout: float = Field(10.0, alias="HUB_TIMEOUT")
    # Escrita: acima do timeout das ferramentas de escrita do hub (25 s).
    hub_timeout_escrita: float = Field(30.0, alias="HUB_TIMEOUT_ESCRITA")
    # Edição do cadastro (contato, e-mail, foto). Desligada = o token do hub
    # pede só `ferramentas:ler` (a conta nasce sem `escrever` até a P-29) e as
    # rotas de escrita respondem 404 `recurso_desligado` sem chamar o hub.
    hub_escrita_habilitada: bool = Field(False, alias="HUB_ESCRITA_HABILITADA")

    # ------------------------------------------------------------------ #
    # E-mail (código de troca de e-mail e aviso ao endereço antigo).      #
    # `stub` não envia nada; fora de produção devolve o código na API.    #
    # ------------------------------------------------------------------ #
    smtp_mode: str = Field("stub", alias="SMTP_MODE")
    smtp_host: str | None = Field(None, alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str | None = Field(None, alias="SMTP_USER")
    smtp_password: str | None = Field(None, alias="SMTP_PASSWORD")
    smtp_from: str = Field("Associação Paulista de Medicina <naoresponda@apm.org.br>", alias="SMTP_FROM")
    smtp_starttls: bool = Field(True, alias="SMTP_STARTTLS")
    smtp_timeout: float = Field(20.0, alias="SMTP_TIMEOUT")

    # ------------------------------------------------------------------ #
    # Perfil, foto e carteirinha (Fase 2).                                #
    # ------------------------------------------------------------------ #
    carteirinha_hmac_key: str | None = Field(None, alias="CARTEIRINHA_HMAC_KEY")
    perfil_cache_ttl: int = Field(86400, alias="PERFIL_CACHE_TTL")
    reauth_max_idade: int = Field(900, alias="REAUTH_MAX_IDADE")
    # Step-up também para trocar o CELULAR (`PUT /perfil/contato`). Nasce
    # desligado: ligar no dia em que o IdP passar a mandar OTP por celular —
    # a partir daí trocar o número é trocar o canal de recuperação de senha
    # (mesmo raciocínio da ADR-0015 para o e-mail; TI-09).
    celular_exige_reauth: bool = Field(False, alias="CELULAR_EXIGE_REAUTH")
    foto_max_bytes: int = Field(5 * 1024 * 1024, alias="FOTO_MAX_BYTES")
    email_codigo_ttl: int = Field(600, alias="EMAIL_CODIGO_TTL")
    # Verificação pública em tempo quase real (TI-45, DEC-09): a leitura de
    # `associado.situacao` no hub vale VERIFICACAO_CACHE_TTL; vencida, a rota
    # pública consulta o hub de novo, no máximo VERIFICACAO_HUB_POR_MINUTO
    # vezes por minuto POR PROCESSO (2 workers → até 2×), para não esgotar a
    # cota da conta no hub (P-41). Estourado, vale o cache (RF-CA-08).
    verificacao_cache_ttl: int = Field(600, alias="VERIFICACAO_CACHE_TTL")
    verificacao_hub_por_minuto: int = Field(60, alias="VERIFICACAO_HUB_POR_MINUTO")

    # ------------------------------------------------------------------ #
    # Serviço de jobs `area-associado-jobs` (ADR-0019; docs/JOBS.md).     #
    # O web ignora estas chaves (só `CENTRAL_EMAIL` é lida pelo job de    #
    # comunicação). Segredos SÓ de job (conta do hub `area-associado-jobs`)#
    # vão em `.env.jobs`, que o compose carrega por cima do `.env`.        #
    # ------------------------------------------------------------------ #
    # Dry-run por padrão: com False, jobs com efeito EXTERNO (escrita no CRM,
    # e-mail) só registram o que fariam. Jobs de efeito local rodam sempre.
    jobs_aplicar: bool = Field(False, alias="JOBS_APLICAR")
    jobs_heartbeat: str = Field("/tmp/jobs.heartbeat", alias="JOBS_HEARTBEAT")
    # Intervalos (segundos) dos jobs periódicos; jitter de até 10% (≤ 30 s).
    jobs_intervalo_espelho: int = Field(60, alias="JOBS_INTERVALO_ESPELHO")
    jobs_intervalo_sync: int = Field(300, alias="JOBS_INTERVALO_SYNC")
    jobs_intervalo_sem_retorno: int = Field(900, alias="JOBS_INTERVALO_SEM_RETORNO")
    jobs_intervalo_comunicacao: int = Field(60, alias="JOBS_INTERVALO_COMUNICACAO")
    # Itens por execução no espelho e na comunicação (disjuntor da cota do hub/SMTP).
    jobs_lote: int = Field(50, alias="JOBS_LOTE")
    # Situação das carteirinhas: diário às JOBS_SITUACAO_HORA (hora local,
    # America/Sao_Paulo), lotes de até 200, pausa entre chamadas ao hub.
    jobs_situacao_hora: int = Field(3, alias="JOBS_SITUACAO_HORA")
    jobs_situacao_lote: int = Field(200, alias="JOBS_SITUACAO_LOTE")
    jobs_situacao_rodadas: int = Field(5, alias="JOBS_SITUACAO_RODADAS")
    jobs_situacao_pausa: float = Field(1.0, alias="JOBS_SITUACAO_PAUSA")
    # Destino dos avisos internos (A05 equipe, A16 Central). Ausente = o
    # aviso interno é suprimido (`sem_credencial`), nunca vai a outro lugar.
    central_email: str | None = Field(None, alias="CENTRAL_EMAIL")

    # ------------------------------------------------------------------ #
    # Propriedades derivadas                                             #
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def session_https_only(self) -> bool:
        """Cookie Secure em tudo que não seja desenvolvimento local."""
        return self.app_env != "development"

    @property
    def expose_openapi(self) -> bool:
        return self.app_env == "development"

    @property
    def effective_issuer(self) -> str:
        """Issuer sem barra final — comparado byte a byte com o claim `iss`."""
        return self.oidc_issuer.rstrip("/")

    @property
    def effective_backchannel(self) -> str:
        return self.oidc_backchannel_base_url.rstrip("/")

    @property
    def backchannel_host_header(self) -> str | None:
        """Host do issuer quando o back-channel usa outro endereço (rede Docker)."""
        issuer_host = urlsplit(self.effective_issuer).netloc
        back_host = urlsplit(self.effective_backchannel).netloc
        return issuer_host if issuer_host != back_host else None

    @property
    def effective_public_base_url(self) -> str:
        return self.public_base_url.rstrip("/")

    @property
    def redirect_uri(self) -> str:
        return f"{self.effective_public_base_url}/auth/callback"

    @property
    def post_logout_redirect_uri(self) -> str:
        return f"{self.effective_public_base_url}/"

    @property
    def scope_list(self) -> list[str]:
        return [s for s in self.oidc_scopes.split() if s]

    @property
    def effective_log_hash_key(self) -> str:
        return self.log_hash_key or self.secret_key

    @property
    def session_cookie_name(self) -> str:
        """`__Host-` exige Secure, Path=/ e nenhum Domain — impede que um
        subdomínio irmão sobrescreva o cookie. Em development (http) o
        navegador recusaria o prefixo, então usa nome simples."""
        return "area_sessao" if self.app_env == "development" else "__Host-area"

    @property
    def session_enc_key_list(self) -> list[str]:
        return [k.strip() for k in (self.session_enc_keys or "").split(",") if k.strip()]

    @property
    def flags_forcadas(self) -> frozenset[str]:
        return frozenset(f.strip().lower() for f in self.flags_forcar_desligadas.split(",") if f.strip())

    @property
    def csp_img_host_list(self) -> list[str]:
        return [h.strip().rstrip("/") for h in self.csp_img_hosts.split(",") if h.strip()]

    @property
    def effective_hub_base_url(self) -> str:
        return self.hub_base_url.rstrip("/")

    @property
    def effective_carteirinha_key(self) -> bytes:
        """Chave do token público da carteirinha (ADR-0014). Fora de produção,
        derivada de SECRET_KEY com separação de domínio."""
        if self.carteirinha_hmac_key:
            return self.carteirinha_hmac_key.encode("utf-8")
        import hashlib
        import hmac as _hmac

        return _hmac.new(self.secret_key.encode("utf-8"), b"area_associado/carteirinha/v1", hashlib.sha256).digest()

    @property
    def sqlalchemy_dsn(self) -> str:
        # Senha vai por connect_args (database.py), nunca na URL.
        return (
            f"mysql+pymysql://{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}"
            "?charset=utf8mb4"
        )

    # ------------------------------------------------------------------ #
    # Coerência — combinações inseguras derrubam o boot de propósito.     #
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _coerencia(self) -> "Settings":
        self.app_env = self.app_env.lower().strip()
        self.auth_mode = self.auth_mode.lower().strip()
        if self.app_env not in _ENVS:
            raise ValueError(f"APP_ENV inválido: {self.app_env!r} (use {', '.join(_ENVS)})")
        if self.auth_mode not in _AUTH_MODES:
            raise ValueError(f"AUTH_MODE inválido: {self.auth_mode!r} (use oidc|stub)")
        if len(self.secret_key) < _MIN_SECRET_LEN:
            raise ValueError(f"SECRET_KEY precisa de ao menos {_MIN_SECRET_LEN} caracteres")
        if self.auth_mode == "stub":
            if self.is_production:
                raise ValueError("AUTH_MODE=stub é proibido com APP_ENV=production")
            if not self.dev_stub_token or len(self.dev_stub_token) < _MIN_SECRET_LEN:
                raise ValueError("AUTH_MODE=stub exige DEV_STUB_TOKEN com ao menos 32 caracteres")
        if self.auth_mode == "oidc" and not self.oidc_client_secret:
            raise ValueError("AUTH_MODE=oidc exige OIDC_CLIENT_SECRET")
        if self.is_production and not self.db_ssl_verify:
            raise ValueError("DB_SSL_VERIFY=0 é proibido com APP_ENV=production")
        if not self.effective_issuer.startswith("https://"):
            raise ValueError("OIDC_ISSUER precisa ser https://")
        if not self.effective_public_base_url.startswith("https://") and self.app_env != "development":
            raise ValueError("PUBLIC_BASE_URL precisa ser https:// fora de development")
        if self.session_absolute_max < self.session_max_age:
            raise ValueError("SESSION_ABSOLUTE_MAX deve ser >= SESSION_MAX_AGE")
        self._validar_sessao_e_interface()
        self._validar_jobs()
        return self

    def _validar_sessao_e_interface(self) -> None:
        # Import local: cryptography só é necessária para validar o formato.
        from cryptography.fernet import Fernet

        chaves = self.session_enc_key_list
        if self.is_production and not chaves:
            raise ValueError("SESSION_ENC_KEYS é obrigatória com APP_ENV=production")
        for chave in chaves:
            try:
                Fernet(chave.encode("ascii"))
            except (ValueError, UnicodeEncodeError) as exc:
                raise ValueError(
                    "SESSION_ENC_KEYS contém chave inválida (gere com "
                    "`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`)"
                ) from exc
        if not _WHATSAPP.match(self.whatsapp_central):
            raise ValueError("WHATSAPP_CENTRAL deve ter só dígitos, com DDI e DDD (ex.: 551131886200)")
        for flag in self.flags_forcadas:
            if not _FLAG_KEY.match(flag):
                raise ValueError(f"FLAGS_FORCAR_DESLIGADAS contém chave inválida: {flag!r}")
        self._validar_integracoes()
        if not 5 <= self.flags_cache_ttl <= 3600:
            raise ValueError("FLAGS_CACHE_TTL deve ficar entre 5 e 3600 segundos")
        for host in self.csp_img_host_list:
            partes = urlsplit(host)
            # Só origem https, sem caminho, curinga, query ou credencial: o valor
            # vai literalmente para o cabeçalho CSP.
            if (partes.scheme != "https" or not partes.netloc or partes.path or partes.query
                    or partes.fragment or "@" in partes.netloc or "*" in host
                    or not re.fullmatch(r"[A-Za-z0-9.-]+(:[0-9]{1,5})?", partes.netloc)):
                raise ValueError(f"CSP_IMG_HOSTS aceita só origens https sem caminho: {host!r}")


    def _validar_integracoes(self) -> None:
        self.hub_mode = self.hub_mode.lower().strip()
        self.smtp_mode = self.smtp_mode.lower().strip()
        if self.hub_mode not in ("real", "stub"):
            raise ValueError("HUB_MODE inválido (use real|stub)")
        if self.smtp_mode not in ("real", "stub"):
            raise ValueError("SMTP_MODE inválido (use real|stub)")
        if self.is_production:
            if self.hub_mode == "stub":
                raise ValueError("HUB_MODE=stub é proibido com APP_ENV=production")
            if self.smtp_mode == "stub":
                raise ValueError("SMTP_MODE=stub é proibido com APP_ENV=production")
            if not self.carteirinha_hmac_key or len(self.carteirinha_hmac_key) < _MIN_SECRET_LEN:
                raise ValueError("CARTEIRINHA_HMAC_KEY (>= 32) é obrigatória com APP_ENV=production")
        elif self.carteirinha_hmac_key is not None and len(self.carteirinha_hmac_key) < _MIN_SECRET_LEN:
            raise ValueError("CARTEIRINHA_HMAC_KEY precisa de ao menos 32 caracteres")
        if self.hub_mode == "real":
            if not self.hub_client_secret or len(self.hub_client_secret) < 16:
                raise ValueError("HUB_MODE=real exige HUB_CLIENT_SECRET")
            partes = urlsplit(self.effective_hub_base_url)
            # https sempre; http só para nome de serviço da rede Docker (sem ponto),
            # que nunca sai da máquina.
            interno = partes.scheme == "http" and partes.hostname and "." not in partes.hostname
            if not (partes.scheme == "https" or interno) or partes.path or partes.query or "@" in partes.netloc:
                raise ValueError("HUB_BASE_URL deve ser https:// (ou http:// de serviço Docker interno), sem caminho")
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", self.hub_public_host):
                raise ValueError("HUB_PUBLIC_HOST inválido")
        if self.smtp_mode == "real":
            if not (self.smtp_host and self.smtp_user and self.smtp_password and self.smtp_from):
                raise ValueError("SMTP_MODE=real exige SMTP_HOST, SMTP_USER, SMTP_PASSWORD e SMTP_FROM")
            if not self.smtp_starttls and self.smtp_port != 465:
                raise ValueError("SMTP sem STARTTLS só na porta 465 (TLS implícito)")
        if not 1.0 <= self.hub_timeout <= 30.0 or not 1.0 <= self.smtp_timeout <= 60.0:
            raise ValueError("HUB_TIMEOUT/SMTP_TIMEOUT fora da faixa")
        if not max(5.0, self.hub_timeout) <= self.hub_timeout_escrita <= 60.0:
            raise ValueError("HUB_TIMEOUT_ESCRITA deve ficar entre max(5, HUB_TIMEOUT) e 60 segundos")
        if not 60 <= self.reauth_max_idade <= 3600:
            raise ValueError("REAUTH_MAX_IDADE deve ficar entre 60 e 3600 segundos")
        if not 300 <= self.perfil_cache_ttl <= 7 * 86400:
            raise ValueError("PERFIL_CACHE_TTL deve ficar entre 300 s e 7 dias")
        if not 256 * 1024 <= self.foto_max_bytes <= 10 * 1024 * 1024:
            raise ValueError("FOTO_MAX_BYTES deve ficar entre 256 KiB e 10 MiB")
        if not 120 <= self.email_codigo_ttl <= 1800:
            raise ValueError("EMAIL_CODIGO_TTL deve ficar entre 120 e 1800 segundos")
        if not 60 <= self.verificacao_cache_ttl <= 3600:
            raise ValueError("VERIFICACAO_CACHE_TTL deve ficar entre 60 e 3600 segundos")
        if not 1 <= self.verificacao_hub_por_minuto <= 600:
            raise ValueError("VERIFICACAO_HUB_POR_MINUTO deve ficar entre 1 e 600")

    def _validar_jobs(self) -> None:
        """Serviço de jobs (ADR-0019). Efeito externo com integração simulada
        só em development/test: em staging/production, `JOBS_APLICAR=1` com o
        hub simulado gravaria `crm_id` falso em pedidos reais."""
        caminho = self.jobs_heartbeat
        if (not caminho.startswith("/") or ".." in caminho.split("/")
                or not re.fullmatch(r"/[A-Za-z0-9._/-]{1,200}", caminho)):
            raise ValueError("JOBS_HEARTBEAT deve ser um caminho absoluto simples (ex.: /tmp/jobs.heartbeat)")
        for nome, valor, minimo, maximo in (
            ("JOBS_INTERVALO_ESPELHO", self.jobs_intervalo_espelho, 30, 3600),
            ("JOBS_INTERVALO_SYNC", self.jobs_intervalo_sync, 60, 3600),
            ("JOBS_INTERVALO_SEM_RETORNO", self.jobs_intervalo_sem_retorno, 60, 86400),
            ("JOBS_INTERVALO_COMUNICACAO", self.jobs_intervalo_comunicacao, 30, 3600),
            ("JOBS_LOTE", self.jobs_lote, 1, 200),
            ("JOBS_SITUACAO_HORA", self.jobs_situacao_hora, 0, 23),
            ("JOBS_SITUACAO_LOTE", self.jobs_situacao_lote, 1, 200),
            ("JOBS_SITUACAO_RODADAS", self.jobs_situacao_rodadas, 1, 50),
        ):
            if not minimo <= valor <= maximo:
                raise ValueError(f"{nome} deve ficar entre {minimo} e {maximo}")
        if not 0.1 <= self.jobs_situacao_pausa <= 10.0:
            raise ValueError("JOBS_SITUACAO_PAUSA deve ficar entre 0.1 e 10 segundos")
        if self.jobs_aplicar and self.app_env not in ("development", "test") and self.hub_mode == "stub":
            raise ValueError("JOBS_APLICAR=1 com HUB_MODE=stub só em development/test")
        if self.central_email is not None:
            self.central_email = self.central_email.strip().lower() or None
        if self.central_email is not None:
            from .integracoes.email import email_valido  # import local: email.py importa config

            if not email_valido(self.central_email):
                raise ValueError("CENTRAL_EMAIL inválido (um endereço, sem nome nem vírgula)")


@lru_cache
def get_settings() -> Settings:
    return Settings()

