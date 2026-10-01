"""Camada de acesso ao banco (SQLAlchemy + PyMySQL) com TLS verificado.

Diferença deliberada em relação ao login_associado: aqui a conexão com o RDS
valida o certificado do servidor contra o bundle de CAs da AWS embutido na
imagem (`DB_SSL_CA`) e confere o hostname. O usuário `apm_area` é criado com
`REQUIRE SSL`, então uma conexão em texto claro é recusada pelos dois lados.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_settings = get_settings()


def _connect_args() -> dict:
    # A senha vai aqui, não na URL: evita URL-encoding e não vaza em logs de DSN.
    args: dict = {"password": _settings.db_pass}
    if _settings.db_ssl_verify:
        ca = Path(_settings.db_ssl_ca)
        if not ca.is_file():
            # Falhar no boot é melhor que cair para uma conexão sem verificação.
            raise FileNotFoundError(f"DB_SSL_CA não encontrado: {ca}")
        args.update(
            ssl_ca=str(ca),
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )
    else:
        # Só fora de produção (config.py recusa em production): TLS sem validar a
        # cadeia. Ainda assim cifra o canal, o que o REQUIRE SSL exige.
        args.update(ssl={"check_hostname": False})
    return args


engine: Engine = create_engine(
    _settings.sqlalchemy_dsn,
    connect_args=_connect_args(),
    pool_pre_ping=True,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_recycle=_settings.db_pool_recycle,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão transacional com commit/rollback/close automáticos."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """Dependência FastAPI."""
    with session_scope() as session:
        yield session


def check_connection() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def tls_status() -> dict[str, str]:
    """Cifra/versão TLS da conexão atual e o usuário efetivo — prova de que o
    canal está cifrado e de que a app não roda com a conta master."""
    with engine.connect() as conn:
        rows = conn.execute(text("SHOW SESSION STATUS WHERE Variable_name IN ('Ssl_cipher','Ssl_version')"))
        status = {r[0]: r[1] for r in rows}
        status["current_user"] = conn.execute(text("SELECT CURRENT_USER()")).scalar_one()
    return status
