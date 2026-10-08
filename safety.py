from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def allowed_test_url(url, settings):
    parsed = urlparse(url)
    if url in ("about:blank", "about:srcdoc"):
        return True
    if parsed.scheme == "file":
        return not parsed.netloc or parsed.netloc == "localhost"
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return False
    if parsed.hostname in LOCAL_HOSTS:
        return True
    return settings.get("authorized_testing") is True and parsed.hostname in settings.get("authorized_test_hosts", [])


def local_ollama_url(url):
    parsed = urlparse(url or "")
    return parsed.scheme in ("http", "https") and parsed.hostname in LOCAL_HOSTS and not parsed.username and not parsed.password
