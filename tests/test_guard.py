from app.session_guard import safe_next


def test_safe_next_aceita_caminho_relativo():
    assert safe_next("/area/carteirinha?x=1") == "/area/carteirinha?x=1"


def test_safe_next_rejeita_externos_e_lixo():
    for ruim in ("//evil.com", "https://evil.com", "/\\evil", "javascript:alert(1)", "", None, "/a\r\nb",
                 "/auth/login", "x" * 600, "relativo"):
        assert safe_next(ruim) == "/area", ruim
