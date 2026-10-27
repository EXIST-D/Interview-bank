"""Optional model access for the hosted Web import. Standard library only; nothing else in the CLI calls a model.

The configuration file names endpoints and models; the API key is read from a file or an environment variable,
never from the command line, and never appears in results, errors or logs.
"""
import base64
import json
import os
import re
import stat
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .errors import BankError
from .schema import require

PROTOCOLS = ("openai", "anthropic")
DEFAULT_KEY_ENV = "INTERVIEW_BANK_AI_KEY"
LIMIT_DEFAULTS = {"max_images_per_job": 12, "max_answers_per_job": 40, "daily_images": 60, "answer_batch": 4}
LIMIT_RANGES = {"max_images_per_job": (1, 30), "max_answers_per_job": (0, 200), "daily_images": (1, 1000), "answer_batch": (1, 10)}
ENDPOINT_FIELDS = {"protocol", "base_url", "model", "api_key_file", "api_key_env", "timeout", "max_tokens", "json_mode", "temperature",
                   "extra_body", "image_encoding"}
# extra_body carries provider switches (DeepSeek/Zhipu "thinking", Qwen "enable_thinking"); it cannot replace the request itself.
RESERVED_BODY = {"model", "messages", "system", "max_tokens", "stream", "response_format"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class AIError(BankError):
    """A model call failed; the message is safe to show the person (no key, no request body)."""


def _endpoint(raw, label, base_dir, inherited=None):
    require(isinstance(raw, dict), f"ai.{label}: expected object")
    require(set(raw) <= ENDPOINT_FIELDS, f"ai.{label}: unknown field {sorted(set(raw) - ENDPOINT_FIELDS)}")
    merged = {**(inherited or {}), **raw}
    protocol = merged.get("protocol", "openai")
    require(protocol in PROTOCOLS, f"ai.{label}.protocol must be openai or anthropic")
    base = merged.get("base_url") or ("https://api.anthropic.com" if protocol == "anthropic" else None)
    require(isinstance(base, str) and base, f"ai.{label}.base_url is required")
    parsed = urlsplit(base)
    require(parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in LOOPBACK),
            f"ai.{label}.base_url must be https (plain http only for a model on this machine)")
    require(not parsed.username and not parsed.password and not parsed.query, f"ai.{label}.base_url must not carry credentials or a query")
    model = merged.get("model")
    require(isinstance(model, str) and model.strip(), f"ai.{label}.model is required")
    timeout = merged.get("timeout", 120)
    max_tokens = merged.get("max_tokens", 4096)
    temperature = merged.get("temperature", 0.2)
    require(type(timeout) in (int, float) and 5 <= timeout <= 600, f"ai.{label}.timeout must be 5..600 seconds")
    require(type(max_tokens) is int and 256 <= max_tokens <= 32768, f"ai.{label}.max_tokens must be 256..32768")
    require(type(temperature) in (int, float) and 0 <= temperature <= 2, f"ai.{label}.temperature must be 0..2")
    require(type(merged.get("json_mode", False)) is bool, f"ai.{label}.json_mode must be true or false")
    extra = merged.get("extra_body", {})
    require(isinstance(extra, dict) and not set(extra) & RESERVED_BODY and len(json.dumps(extra)) <= 4096,
            f"ai.{label}.extra_body: an object of provider options, without {sorted(RESERVED_BODY)}")
    encoding = merged.get("image_encoding", "data_url")
    require(encoding in ("data_url", "base64"), f"ai.{label}.image_encoding must be data_url or base64")
    key_file, key_env = merged.get("api_key_file"), merged.get("api_key_env", DEFAULT_KEY_ENV)
    require(key_file is None or isinstance(key_file, str), f"ai.{label}.api_key_file must be a path")
    require(isinstance(key_env, str) and re.fullmatch(r"[A-Z_][A-Z0-9_]*", key_env), f"ai.{label}.api_key_env must be an environment variable name")
    key = None
    if key_file:
        path = Path(key_file).expanduser()
        path = path if path.is_absolute() else base_dir / path
        require(path.is_file(), f"ai.{label}.api_key_file not found")
        require(os.name == "nt" or not path.stat().st_mode & stat.S_IROTH,
                f"ai.{label}.api_key_file is readable by everyone; chmod 600 or 640 it")
        key = path.read_text(encoding="utf-8").strip()
        require(bool(key) and key.isascii() and key.isprintable() and " " not in key, f"ai.{label}.api_key_file must hold one key")
    else:
        key = os.environ.get(key_env, "").strip() or None
    require(key is not None or parsed.hostname in LOOPBACK,
            f"ai.{label}: no API key (set api_key_file, or the {key_env} environment variable)")
    return {"protocol": protocol, "base_url": base.rstrip("/"), "model": model.strip(), "timeout": timeout,
            "max_tokens": max_tokens, "temperature": temperature, "json_mode": merged.get("json_mode", False),
            "extra_body": extra, "image_encoding": encoding, "_key": key}


def load_config(path):
    """{"vision": {...}, "text": {...}?, "limits": {...}?}; text inherits from vision when it is omitted or partial."""
    path = Path(path).expanduser().resolve()
    require(path.is_file(), f"AI configuration not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise BankError(f"AI configuration is not valid JSON: {exc}") from None
    require(isinstance(raw, dict) and set(raw) <= {"schema_version", "vision", "text", "limits"}, "AI configuration: vision, text and limits only")
    require(raw.get("schema_version", 1) == 1, "AI configuration: unsupported schema_version")
    require("vision" in raw, "AI configuration needs a vision endpoint (a model that reads images)")
    vision = _endpoint(raw["vision"], "vision", path.parent)
    inherited = {k: v for k, v in raw["vision"].items()}
    text = _endpoint(raw.get("text", {}), "text", path.parent, inherited) if raw.get("text") is not None else vision
    limits = {**LIMIT_DEFAULTS, **raw.get("limits", {})}
    require(set(limits) == set(LIMIT_DEFAULTS), f"ai.limits: known fields are {sorted(LIMIT_DEFAULTS)}")
    for name, (low, high) in LIMIT_RANGES.items():
        require(type(limits[name]) is int and low <= limits[name] <= high, f"ai.limits.{name} must be {low}..{high}")
    return {"vision": vision, "text": text, "limits": limits}


def describe(config):
    """What the page and the startup line may show: providers and models, never keys or file paths."""
    return {role: {"protocol": config[role]["protocol"], "host": urlsplit(config[role]["base_url"]).hostname,
                   "model": config[role]["model"]} for role in ("vision", "text")}


def _openai_body(endpoint, system, parts):
    content = []
    for part in parts:
        if "image" in part:
            data = base64.b64encode(part["image"]).decode("ascii")
            url = data if endpoint.get("image_encoding") == "base64" else f"data:{part['mime']};base64,{data}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            content.append({"type": "text", "text": part["text"]})
    body = {"temperature": endpoint["temperature"], **endpoint.get("extra_body", {}), "model": endpoint["model"],
            "max_tokens": endpoint["max_tokens"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
    if endpoint["json_mode"]:
        body["response_format"] = {"type": "json_object"}
    return (endpoint["base_url"] + "/chat/completions", body,
            {"Authorization": f"Bearer {endpoint['_key']}"} if endpoint["_key"] else {})


def _anthropic_body(endpoint, system, parts):
    content = []
    for part in parts:
        if "image" in part:
            content.append({"type": "image", "source": {"type": "base64", "media_type": part["mime"],
                                                        "data": base64.b64encode(part["image"]).decode("ascii")}})
        else:
            content.append({"type": "text", "text": part["text"]})
    body = {"temperature": min(endpoint["temperature"], 1), **endpoint.get("extra_body", {}), "model": endpoint["model"],
            "system": system, "max_tokens": endpoint["max_tokens"], "messages": [{"role": "user", "content": content}]}
    base = endpoint["base_url"]
    return (base + ("/messages" if base.endswith("/v1") else "/v1/messages"), body,
            {"x-api-key": endpoint["_key"] or "", "anthropic-version": "2023-06-01"})


def _reply_text(protocol, reply):
    if protocol == "anthropic":
        return "".join(block.get("text", "") for block in reply.get("content", []) if isinstance(block, dict))
    choice = (reply.get("choices") or [{}])[0]
    content = choice.get("message", {}).get("content")
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def parse_json(text):
    """The first JSON object in a reply, tolerating Markdown fences and short prose around it."""
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        value = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise AIError("模型没有返回 JSON 结果，请重试或换一个模型。") from None
        try:
            value = json.loads(text[start:end + 1])
        except ValueError:
            raise AIError("模型返回的 JSON 不完整，请重试（可在配置中调大 max_tokens）。") from None
    if not isinstance(value, dict):
        raise AIError("模型返回的不是 JSON 对象，请重试。")
    return value


STATUS_HINTS = {400: "请求被拒绝：请检查模型名称、是否支持图片，以及 max_tokens", 401: "认证失败：请检查 API Key",
                403: "没有权限：请检查 API Key 的模型权限或余额", 404: "地址或模型不存在：请检查 base_url 和 model",
                413: "图片太大，模型服务拒收", 429: "调用太频繁或额度不足，请稍后再试"}


def _post(url, body, headers, timeout):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "InterviewBank", **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(16 * 1024 * 1024))


def call(endpoint, system, parts, attempts=3, sleep=time.sleep):
    """One request expecting a JSON object back. Retries timeouts, 429 and 5xx with a short backoff."""
    build = _anthropic_body if endpoint["protocol"] == "anthropic" else _openai_body
    url, body, headers = build(endpoint, system, parts)
    for attempt in range(attempts):
        retry = attempt + 1 < attempts
        try:
            reply = _post(url, body, headers, endpoint["timeout"])
            return parse_json(_reply_text(endpoint["protocol"], reply))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and retry:
                sleep(2 * (attempt + 1) ** 2)
                continue
            raise AIError(f"模型服务返回 HTTP {exc.code}：{STATUS_HINTS.get(exc.code, '服务暂时不可用')}。") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if retry:
                sleep(2 * (attempt + 1) ** 2)
                continue
            reason = getattr(exc, "reason", exc)
            raise AIError(f"连不上模型服务（{type(reason).__name__}），请检查网络或 base_url。") from None
        except AIError:
            if retry:
                continue
            raise
        except ValueError:
            raise AIError("模型服务的响应无法解析。") from None
    raise AIError("模型调用失败。")


def check(config, sleep=time.sleep):
    """A tiny text request per distinct endpoint, for deployment checks. Returns models and latency only."""
    results = {}
    for role in ("vision", "text"):
        endpoint = config[role]
        if role == "text" and endpoint is config["vision"]:
            results[role] = {**results["vision"], "same_as": "vision"}
            continue
        started = time.monotonic()
        # Thinking models spend part of the budget before answering, so the check keeps some room.
        reply = call({**endpoint, "max_tokens": min(endpoint["max_tokens"], 2048)}, 'Reply with the JSON object {"ok": true} and nothing else.',
                     [{"text": "ping"}], attempts=1, sleep=sleep)
        results[role] = {**describe(config)[role], "ok": reply.get("ok") is True,
                         "seconds": round(time.monotonic() - started, 2)}
    return results
