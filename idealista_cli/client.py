import base64
import json
import os
import time
import uuid
from urllib import error, parse, request


def _expand_path(path):
    return os.path.expanduser(path)


class IdealistaHttpError(RuntimeError):
    def __init__(self, status, message, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "idealista-cli", "config.json")


def cache_path():
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(base, "idealista-cli", "token.json")


def load_config():
    path = config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_config(api_key, api_secret):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "api_key": api_key,
        "api_secret": api_secret,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def load_token_cache():
    path = cache_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_token_cache(token_data):
    path = cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)
    return path


def read_credentials():
    api_key = os.environ.get("IDEALISTA_API_KEY")
    api_secret = os.environ.get("IDEALISTA_API_SECRET")

    if api_key and api_secret:
        return api_key, api_secret

    cfg = load_config()
    api_key = api_key or cfg.get("api_key")
    api_secret = api_secret or cfg.get("api_secret")

    if not api_key or not api_secret:
        raise RuntimeError(
            "Missing credentials. Set IDEALISTA_API_KEY and IDEALISTA_API_SECRET or run 'idealista config set'."
        )
    return api_key, api_secret


def _encode_multipart(fields):
    boundary = "----idealista-cli-" + uuid.uuid4().hex
    lines = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        value = str(value)
        lines.append("--" + boundary)
        lines.append(f'Content-Disposition: form-data; name="{key}"')
        lines.append("")
        lines.append(value)
    lines.append("--" + boundary + "--")
    lines.append("")
    body = "\r\n".join(lines).encode("utf-8")
    return boundary, body


def _parse_retry_after(value):
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _request_json(url, method, headers, body, timeout, max_retries):
    attempt = 0
    backoff_s = 1
    while True:
        try:
            req = request.Request(url, data=body, headers=headers, method=method)
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            status = getattr(exc, "code", None)
            raw = exc.read()
            text = None
            try:
                text = raw.decode("utf-8") if raw else None
            except Exception:
                text = None

            retryable = status in {429, 500, 502, 503, 504}
            if retryable and attempt < max_retries:
                retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
                wait_s = retry_after if retry_after is not None else backoff_s
                time.sleep(wait_s)
                attempt += 1
                backoff_s = min(backoff_s * 2, 30)
                continue

            message = f"HTTP {status} calling {url}"
            if text:
                message = message + f": {text[:500]}"
            raise IdealistaHttpError(status=status, message=message, body=text) from exc
        except error.URLError as exc:
            if attempt < max_retries:
                time.sleep(backoff_s)
                attempt += 1
                backoff_s = min(backoff_s * 2, 30)
                continue
            raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def _http_post(url, headers, body, *, timeout, max_retries):
    return _request_json(url, method="POST", headers=headers, body=body, timeout=timeout, max_retries=max_retries)


def _basic_auth_header(api_key, api_secret):
    raw = f"{api_key}:{api_secret}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"Basic {b64}"


class IdealistaClient:
    def __init__(self, api_key=None, api_secret=None, *, timeout=30, max_retries=3):
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            self.api_key, self.api_secret = read_credentials()
        self.timeout = timeout
        self.max_retries = max_retries

    def get_token(self, scope="read", refresh=False):
        cache = load_token_cache()
        now = int(time.time())
        if not refresh and cache.get("access_token") and cache.get("expires_at", 0) > now + 60:
            return cache["access_token"]

        url = "https://api.idealista.com/oauth/token"
        headers = {
            "Authorization": _basic_auth_header(self.api_key, self.api_secret),
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        data = {
            "grant_type": "client_credentials",
        }
        if scope:
            data["scope"] = scope
        body = parse.urlencode(data).encode("utf-8")
        token_data = _http_post(url, headers, body, timeout=self.timeout, max_retries=self.max_retries)
        expires_in = int(token_data.get("expires_in", 0))
        token_data["expires_at"] = now + expires_in
        save_token_cache(token_data)
        return token_data["access_token"]

    def search(self, country="es", **params):
        token = self.get_token()
        url = f"https://api.idealista.com/3.5/{country}/search"
        boundary, body = _encode_multipart(params)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        return _http_post(url, headers, body, timeout=self.timeout, max_retries=self.max_retries)

    def search_all(self, country="es", pages=None, **params):
        params = dict(params)
        params.setdefault("numPage", 1)
        first = self.search(country=country, **params)
        total_pages = int(first.get("totalPages", 1))
        if pages is None:
            pages = total_pages
        pages = max(1, min(pages, total_pages))
        all_elements = list(first.get("elementList", []))
        for page in range(2, pages + 1):
            params["numPage"] = page
            data = self.search(country=country, **params)
            all_elements.extend(data.get("elementList", []))
        result = dict(first)
        result["elementList"] = all_elements
        result["totalPages"] = pages
        return result
