from app.session_guard import safe_next


def test_safe_next_aceita_caminho_relativo():
    assert safe_next("/area/carteirinha?x=1") == "/area/carteirinha?x=1"


def test_safe_next_rejeita_externos_e_lixo():
    for ruim in ("//evil.com", "https://evil.com", "/\\evil", "javascript:alert(1)", "", None, "/a\r\nb",
                 "/auth/login", "x" * 600, "relativo"):
        assert safe_next(ruim) == "/area", ruim


def test_safe_next_aceita_query_de_campanha_e_trata_next_aninhado_como_texto():
    """TI-11: os parâmetros `utm_*`/`g=` viajam na query do `next` e são lidos UMA vez pela SPA;
    o servidor nunca interpreta a query — um `next` dentro do `next` é só texto."""
    assert safe_next("/area/beneficios/x?utm_source=rd&g=A03") == "/area/beneficios/x?utm_source=rd&g=A03"
    assert safe_next("/area?next=//evil") == "/area?next=//evil"
    assert safe_next("/area?next=https://evil") == "/area?next=https://evil"
    # Esquema só é recusado no caminho; `\\` e `//` iniciais continuam recusados onde quer que estejam no início.
    assert safe_next("//evil?utm_source=rd") == "/area"
    assert safe_next("/area/x\\?g=A01") == "/area"
