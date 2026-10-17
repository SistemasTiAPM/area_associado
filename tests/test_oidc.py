import base64
import hashlib
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import oidc
from app.oidc import JwksCache, OidcError, generate_pkce, mask_cpf, validate_id_token


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def pem(rsa_key):
    return rsa_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


@pytest.fixture
def cache(rsa_key, settings, monkeypatch):
    """JwksCache alimentado sem rede: injeta a chave pública como JWK."""
    pub = rsa_key.public_key()
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(pub))
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    doc = {"keys": [jwk]}
    chamadas = {"n": 0}

    def fake_fetch(self):
        chamadas["n"] += 1
        self._keys = {k["kid"]: jwt.PyJWK(k, algorithm="RS256") for k in doc["keys"]}
        self._fetched_at = time.monotonic()

    monkeypatch.setattr(JwksCache, "_fetch", fake_fetch)
    c = JwksCache(settings)
    c.chamadas = chamadas
    c.doc = doc
    return c


def _idt(pem, settings, *, kid="k1", alg="RS256", **over):
    now = int(time.time())
    claims = {
        "iss": settings.effective_issuer, "sub": "sub-abc", "aud": settings.oidc_client_id,
        "exp": now + 900, "iat": now, "nbf": now, "auth_time": now, "nonce": "n0nce", "azp": settings.oidc_client_id,
        "amr": ["pwd"], "contact_id": "c-1",
    }
    claims.update(over)
    key = pem if alg == "RS256" else b"segredo-hmac"
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


def test_pkce_s256_rfc7636():
    v, c = generate_pkce()
    assert 43 <= len(v) <= 128 and "=" not in v
    esperado = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    assert c == esperado


def test_id_token_valido(pem, settings, cache):
    claims = validate_id_token(_idt(pem, settings), nonce="n0nce", settings=settings, cache=cache)
    assert claims["sub"] == "sub-abc"


@pytest.mark.parametrize("over,codigo", [
    ({"iss": "https://outro.apm.org.br"}, "id_token_invalid"),
    ({"aud": "outro-client"}, "id_token_invalid"),
    ({"azp": "outro-client"}, "id_token_invalid"),
    ({"nonce": "errado"}, "id_token_nonce_mismatch"),
    ({"exp": int(time.time()) - 600}, "id_token_expired"),
    ({"sub": ""}, "id_token_invalid"),
])
def test_id_token_rejeitado(pem, settings, cache, over, codigo):
    with pytest.raises(OidcError) as e:
        validate_id_token(_idt(pem, settings, **over), nonce="n0nce", settings=settings, cache=cache)
    assert e.value.code == codigo


def test_id_token_sem_auth_time_e_rejeitado(pem, settings, cache):
    tok = _idt(pem, settings)
    # remonta sem auth_time
    now = int(time.time())
    claims = {"iss": settings.effective_issuer, "sub": "s", "aud": settings.oidc_client_id,
              "exp": now + 900, "iat": now, "nonce": "n0nce"}
    tok = jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(OidcError) as e:
        validate_id_token(tok, nonce="n0nce", settings=settings, cache=cache)
    assert e.value.code == "id_token_invalid"


def test_alg_hs256_e_none_rejeitados(pem, settings, cache):
    with pytest.raises(OidcError):
        validate_id_token(_idt(pem, settings, alg="HS256"), nonce="n0nce", settings=settings, cache=cache)
    header = base64.urlsafe_b64encode(b'{"alg":"none","kid":"k1"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(b'{"sub":"x"}').rstrip(b"=").decode()
    with pytest.raises(OidcError):
        validate_id_token(f"{header}.{body}.", nonce="n0nce", settings=settings, cache=cache)


def test_kid_desconhecido_refaz_fetch_uma_vez(pem, settings, cache):
    cache.kids()
    antes = cache.chamadas["n"]
    with pytest.raises(OidcError) as e:
        validate_id_token(_idt(pem, settings, kid="k2"), nonce="n0nce", settings=settings, cache=cache)
    assert e.value.code == "id_token_unknown_kid"
    assert cache.chamadas["n"] == antes + 1


def test_mask_cpf():
    assert mask_cpf("12345678901") == "***.456.789-**"
    assert mask_cpf("123.456.789-01") == "***.456.789-**"
    assert mask_cpf("123") is None and mask_cpf(None) is None


def test_login_from_callback_valida_state_e_erro_do_idp(settings):
    pending = {"st": "abc", "nonce": "n", "cv": "v", "cc": "c", "exp": int(time.time()) + 60, "next": "/area"}
    with pytest.raises(OidcError) as e:
        oidc.login_from_callback({"state": "xyz", "code": "q"}, pending, settings=settings)
    assert e.value.code == "state_mismatch"
    with pytest.raises(OidcError) as e:
        oidc.login_from_callback({"error": "access_denied", "state": "abc"}, pending, settings=settings)
    assert e.value.code == "idp_access_denied" and e.value.http_status == 403
    with pytest.raises(OidcError) as e:
        oidc.login_from_callback({"state": "abc", "code": "q", "iss": "https://evil"}, pending, settings=settings)
    assert e.value.code == "issuer_mismatch"


def test_fluxo_completo_com_idp_mockado(pem, settings, cache, monkeypatch):
    """Troca de code, id_token e userinfo mockados — prova a orquestração e o
    vínculo sub(id_token) == sub(userinfo)."""
    monkeypatch.setattr(oidc, "jwks_cache", lambda: cache)
    idt = _idt(pem, settings)

    class Resp:
        def __init__(self, status, body):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

        def raise_for_status(self):
            pass

    class FakeHttp:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None, auth=None):
            assert url.endswith("/oauth/token") and auth[0] == settings.oidc_client_id
            assert data["code_verifier"] == "v" and "client_secret" not in data
            return Resp(200, {"access_token": "at", "id_token": idt, "token_type": "Bearer", "expires_in": 900})

        def get(self, url, headers=None):
            assert headers["Authorization"] == "Bearer at"
            return Resp(200, {"sub": "sub-abc", "name": "Maria  Silva", "email": "m@x.org", "cpf": "12345678901",
                              "tipo_associado": "Efetivo", "associado": "Ativo", "num_contato": "80012345",
                              "crm": "123456", "crm_uf": "SP", "data_filiacao": "2014-03-01"})

    monkeypatch.setattr(oidc.httpx, "Client", FakeHttp)
    pending = {"st": "abc", "nonce": "n0nce", "cv": "v", "cc": "c", "exp": int(time.time()) + 60, "next": "/area"}
    a = oidc.login_from_callback({"state": "abc", "code": "q"}, pending, settings=settings)
    assert a.sub == "sub-abc" and a.nome == "Maria Silva" and a.cpf_mask == "***.456.789-**" and a.amr == ["pwd"]
    assert (a.tipo, a.status, a.crm, a.crm_uf, a.data_filiacao) == ("Efetivo", "Ativo", "123456", "SP", "2014-03-01")

    # P-20: escopo carteirinha pedido e cadastro sem tipo/situação → recusa (403)
    FakeHttp.get = lambda self, url, headers=None: Resp(200, {"sub": "sub-abc", "name": "Maria"})
    with pytest.raises(OidcError) as e:
        oidc.login_from_callback({"state": "abc", "code": "q"}, pending, settings=settings)
    assert e.value.code == "persona_incompleta" and e.value.http_status == 403

    # userinfo de outro sub → recusa (nunca identidade parcial)
    FakeHttp.get = lambda self, url, headers=None: Resp(200, {"sub": "outro"})
    with pytest.raises(OidcError) as e:
        oidc.login_from_callback({"state": "abc", "code": "q"}, pending, settings=settings)
    assert e.value.code == "userinfo_sub_mismatch"

    # CRM fora (503) → fail-closed
    FakeHttp.get = lambda self, url, headers=None: Resp(503, {"error": "temporarily_unavailable"})
    with pytest.raises(OidcError) as e:
        oidc.login_from_callback({"state": "abc", "code": "q"}, pending, settings=settings)
    assert e.value.code == "userinfo_unavailable" and e.value.http_status == 503
