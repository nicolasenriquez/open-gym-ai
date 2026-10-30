"""Bounded asynchronous provider wire formats; never log request/response contents."""

import asyncio
import json
import re
from urllib.parse import quote, urlsplit

import httpx

from opengym_platform.coach.payload import ASSETS, obj

DEFAULT_BASES = {
    provider: meta["defaultBase"] or ""
    for provider, meta in ASSETS["providers"].items()
}
VERSION = re.compile(r"/v\d+(?:(?:alpha|beta)\d*)?(?=/|$)", re.IGNORECASE)
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}
RESERVED_HEADERS = {
    "authorization",
    "proxy-authorization",
    "content-type",
    "content-length",
    "host",
    "connection",
    "transfer-encoding",
    "upgrade",
    "cookie",
    "set-cookie",
}
versionless_base = None


def endpoint(base, path):
    return base + (
        VERSION.sub("", path, count=1) if VERSION.search(urlsplit(base).path) else path
    )


def base_url(config):
    base = config["options"].get("baseUrl") or DEFAULT_BASES.get(config["provider"], "")
    if not isinstance(base, str):
        return None
    try:
        parsed = urlsplit(base.strip())
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            return None
        _ = parsed.port
    except ValueError:
        return None
    return base.strip().rstrip("/")


def extra_headers(config):
    headers = {}
    for name, value in obj(config["options"].get("headers")).items():
        if len(headers) >= 8:
            break
        if (
            len(name) <= 64
            and re.fullmatch(r"[!#$%&'*+\-.^_`|~0-9a-z]+", name, re.IGNORECASE)
            and name.lower() not in RESERVED_HEADERS
            and isinstance(value, str)
            and value
            and len(value) <= 500
            and "\r" not in value
            and "\n" not in value
        ):
            headers[name.lower()] = value
    return headers


async def models(config, key):
    selected = config["provider"]
    base = base_url(config)
    if not base:
        return {"ok": False, "error": "no endpoint configured", "models": []}
    if not key and selected != "compatible":
        return {"ok": False, "error": "no API key configured", "models": []}
    headers = extra_headers(config)
    if selected == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    elif selected == "gemini":
        headers["x-goog-api-key"] = key
    elif key:
        headers["authorization"] = "Bearer " + key
    path = "/v1beta/models?pageSize=200" if selected == "gemini" else "/v1/models"
    urls = [endpoint(base, path)]
    if selected == "compatible" and base + VERSION.sub("", path, count=1) != urls[0]:
        urls.append(base + VERSION.sub("", path, count=1))
    try:
        async with (
            asyncio.timeout(20),
            httpx.AsyncClient(
                trust_env=False, follow_redirects=False, timeout=20
            ) as client,
        ):
            for url in urls:
                async with client.stream("GET", url, headers=headers) as response:
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > 4 * 1024 * 1024:
                            raise ValueError
                        raw.extend(chunk)
                    if response.status_code == 404 and url != urls[-1]:
                        continue
                    if not 200 <= response.status_code < 300:
                        return {
                            "ok": False,
                            "error": f"provider rejected request ({response.status_code})",
                            "models": [],
                        }
                    data = json.loads(raw)
                    rows = (
                        data.get("models", [])
                        if selected == "gemini"
                        else data.get("data", [])
                    )
                    if not isinstance(rows, list):
                        raise TypeError
                    names = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        if (
                            selected == "gemini"
                            and row.get("supportedGenerationMethods")
                            and "generateContent"
                            not in row["supportedGenerationMethods"]
                        ):
                            continue
                        name = row.get("name" if selected == "gemini" else "id")
                        if (
                            isinstance(name, str)
                            and name
                            and (not key or key not in name)
                        ):
                            names.append(
                                name.removeprefix("models/")
                                if selected == "gemini"
                                else name
                            )
                    return {"ok": True, "models": sorted(names)}
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, AttributeError):
        return {"ok": False, "error": "could not read provider models", "models": []}


async def invoke(config, key, prompt, system, schema, timeout):
    global versionless_base
    selected, model = config["provider"], config["model"]
    maximum = config["max_output_tokens"]
    headers = extra_headers(config)
    headers["content-type"] = "application/json"
    rules = ASSETS["system"] + "\n\n" + system
    if selected == "anthropic":
        path = "/v1/messages"
        headers.update(
            {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "anthropic-dangerous-direct-browser-access": "true",
            }
        )
        body = {
            "model": model,
            "max_tokens": maximum,
            "system": [
                {"type": "text", "text": rules, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": prompt}],
        }
    elif selected == "gemini":
        path = "/v1beta/models/" + quote(model, safe="") + ":generateContent"
        headers["x-goog-api-key"] = key
        body = {
            "systemInstruction": {"parts": [{"text": rules}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": maximum,
            },
        }
    else:
        path = "/v1/chat/completions"
        if key:
            headers["authorization"] = "Bearer " + key
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": rules},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "coach_answer", "schema": schema},
            }
            if schema
            else {"type": "json_object"},
            "max_tokens"
            if selected == "compatible"
            else "max_completion_tokens": maximum,
        }
        if selected == "compatible":
            body["temperature"] = 0
    try:
        async with httpx.AsyncClient(
            trust_env=False, follow_redirects=False, timeout=timeout
        ) as client:

            async def send(url):
                async with client.stream(
                    "POST", url, json=body, headers=headers
                ) as response:
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > 4 * 1024 * 1024:
                            raise ValueError("provider body too large")
                        raw.extend(chunk)
                    try:
                        data = json.loads(raw)
                    except ValueError:
                        data = None
                    return response.status_code, data

            base = base_url(config)
            primary = endpoint(base, path)
            bare = base + VERSION.sub("", path, count=1)
            retries, json_fallback = 0, False
            while True:
                urls = [primary]
                if selected == "compatible" and bare != primary:
                    urls = (
                        [bare, primary] if versionless_base == base else [primary, bare]
                    )
                status, data = await send(urls[0])
                if status == 404 and len(urls) == 2:
                    alternate_status, alternate_data = await send(urls[1])
                    if 200 <= alternate_status < 300:
                        status, data = alternate_status, alternate_data
                        versionless_base = base if urls[1] == bare else None
                if 200 <= status < 300:
                    break
                if status in RETRY_STATUSES and retries < 2:
                    await asyncio.sleep((2, 5)[retries])
                    retries += 1
                    continue
                error = obj(data).get("error")
                message = (
                    error
                    if isinstance(error, str)
                    else str(obj(error).get("message", ""))
                )
                if (
                    status == 400
                    and selected in ("openai", "compatible")
                    and not json_fallback
                    and re.search(
                        r"response_format|json_schema|json_object|json mode|structured",
                        message,
                        re.IGNORECASE,
                    )
                ):
                    if obj(body.get("response_format")).get("type") == "json_schema":
                        body["response_format"] = {"type": "json_object"}
                    else:
                        body.pop("response_format", None)
                    json_fallback = True
                    continue
                return {"error": "auth" if status in (401, 403) else "provider"}
    except httpx.TimeoutException:
        return {"error": "timeout"}
    except (httpx.HTTPError, ValueError, TypeError):
        return {"error": "provider"}
    try:
        if selected == "anthropic":
            if data.get("stop_reason") in ("refusal", "max_tokens"):
                return {"error": "provider"}
            text = "".join(
                b.get("text", "")
                for b in data.get("content", [])
                if b.get("type") == "text"
            )
        elif selected == "gemini":
            candidate = data["candidates"][0]
            if candidate.get("finishReason", "STOP") != "STOP":
                return {"error": "provider"}
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"])
        else:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                return {"error": "provider"}
            content = choice["message"]["content"]
            text = (
                content
                if isinstance(content, str)
                else "".join(p.get("text", "") for p in content)
            )
        return {"text": text.strip()}
    except (KeyError, IndexError, TypeError, AttributeError):
        return {"error": "provider"}
