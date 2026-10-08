import autofill
import main
from safety import allowed_test_url, local_ollama_url


def test_remote_urls_require_opt_in_and_exact_host():
    assert not allowed_test_url("https://example.com/form", {})
    assert not allowed_test_url("https://example.com/form", {"authorized_test_hosts": ["example.com"]})
    settings = {"authorized_testing": True, "authorized_test_hosts": ["example.com"]}
    assert allowed_test_url("https://example.com/form", settings)
    assert not allowed_test_url("https://example.com.attacker.invalid", settings)
    assert not allowed_test_url("https://secret@example.com", settings)
    assert not allowed_test_url("file://remote-server/document.html", {})
    assert allowed_test_url("http://127.0.0.1:8000/form", {})


def test_entrypoint_runs_demo_without_private_setup(monkeypatch):
    import demo
    calls = []
    monkeypatch.setattr(demo, "run_demo", lambda **kw: calls.append(kw) or 0)
    monkeypatch.setattr(main.config, "ensure_dirs", lambda: (_ for _ in ()).throw(AssertionError("private setup called")))
    assert main.main(["--headless"]) == 0
    assert calls == [{"headless": True}]


def test_remote_application_is_blocked_before_browser_launch():
    result = autofill.run_application({"apply_url": "https://example.com/form"}, {}, {}, "unused.pdf")
    assert result["outcome"] == "failed"
    assert "disabled" in result["note"]


def test_ollama_is_local_only():
    assert local_ollama_url("http://localhost:11434")
    assert not local_ollama_url("https://example.com")
    assert not local_ollama_url("http://password@localhost:11434")
