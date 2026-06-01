"""
Debug server: check if a CDEK test order exists and view its status.

Run from backend root:
  poetry run python -m test_cdek.server

Open http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from test_cdek.cdek_client import (
    CdekClientError,
    api_base,
    get_order_by_cdek_number,
    get_order_by_uuid,
)
from test_cdek.local_order import fetch_local_order

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")

app = FastAPI(title="CDEK debug tracker", docs_url=None, redoc_url=None)

PORT = int(os.getenv("TEST_CDEK_PORT", "8763"))


def _pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _extract_summary(cdek_payload: dict[str, Any]) -> dict[str, Any]:
    entity = (
        cdek_payload.get("entity") if isinstance(cdek_payload, dict) else None
    )
    if not isinstance(entity, dict):
        entity = cdek_payload if isinstance(cdek_payload, dict) else {}

    requests = (
        cdek_payload.get("requests") if isinstance(cdek_payload, dict) else []
    )
    last_request_state = None
    if isinstance(requests, list) and requests:
        last_request_state = requests[-1].get("state")

    statuses = entity.get("statuses") or []
    last_status = statuses[-1] if statuses else None

    return {
        "uuid": entity.get("uuid"),
        "cdek_number": entity.get("cdek_number"),
        "number": entity.get("number"),
        "tariff_code": entity.get("tariff_code"),
        "delivery_point": entity.get("delivery_point"),
        "planned_delivery_date": entity.get("planned_delivery_date"),
        "delivery_date": entity.get("delivery_date"),
        "last_request_state": last_request_state,
        "last_status": last_status,
        "statuses_count": len(statuses),
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CDEK debug tracker</title>
  <style>
    :root { font-family: system-ui, sans-serif; color: #1a1a1a; background: #f4f6f8; }
    body { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 { font-size: 1.5rem; margin: 0 0 8px; }
    .meta { color: #555; font-size: 14px; margin-bottom: 24px; }
    form { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; background: #fff;
           border: 1px solid #dde2e8; border-radius: 12px; padding: 16px; margin-bottom: 20px; }
    label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; font-weight: 600; }
    input { min-width: 220px; padding: 8px 10px; border: 1px solid #ccd3db; border-radius: 8px; font-size: 14px; }
    button { padding: 9px 16px; border: none; border-radius: 8px; background: #4f83e3; color: #fff;
             font-weight: 600; cursor: pointer; }
    button:hover { background: #3d6fc7; }
    section { background: #fff; border: 1px solid #dde2e8; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    section h2 { margin: 0 0 12px; font-size: 1rem; }
    pre { background: #0f172a; color: #e2e8f0; padding: 14px; border-radius: 8px; overflow: auto;
          font-size: 12px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
    .ok { color: #2e7d32; font-weight: 600; }
    .err { color: #c62828; font-weight: 600; }
    dl { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; font-size: 14px; margin: 0; }
    dt { color: #666; }
    dd { margin: 0; }
    .hint { font-size: 13px; color: #666; margin-top: 8px; }
  </style>
</head>
<body>
  <h1>CDEK debug tracker</h1>
  <p class="meta">API: <code>__API_BASE__</code> · только для локальной отладки</p>

  <form method="get" action="/">
    <label>ID заказа в вашей БД
      <input name="order_id" type="number" min="1" placeholder="42" value="__ORDER_ID__" />
    </label>
    <label>CDEK order UUID
      <input name="cdek_uuid" type="text" placeholder="550e8400-..." value="__CDEK_UUID__" />
    </label>
    <label>Номер накладной CDEK
      <input name="cdek_number" type="text" placeholder="1100123456" value="__CDEK_NUMBER__" />
    </label>
    <button type="submit">Проверить</button>
  </form>
  <p class="hint">Достаточно одного поля. Если указан ID заказа — подтянется <code>cdek_order_uuid</code> из PostgreSQL.</p>

  __CONTENT__
</body>
</html>
"""


def _section(title: str, body: str) -> str:
    return f"<section><h2>{title}</h2>{body}</section>"


def _render_page(
    *,
    order_id: str = "",
    cdek_uuid: str = "",
    cdek_number: str = "",
    content: str = "",
) -> str:
    return (
        HTML_PAGE.replace("__API_BASE__", api_base())
        .replace("__ORDER_ID__", _escape_attr(order_id))
        .replace("__CDEK_UUID__", _escape_attr(cdek_uuid))
        .replace("__CDEK_NUMBER__", _escape_attr(cdek_number))
        .replace("__CONTENT__", content)
    )


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


@app.get("/", response_class=HTMLResponse)
async def index(
    order_id: int | None = Query(default=None),
    cdek_uuid: str | None = Query(default=None),
    cdek_number: str | None = Query(default=None),
) -> HTMLResponse:
    oid_str = str(order_id) if order_id else ""
    uuid_str = (cdek_uuid or "").strip()
    number_str = (cdek_number or "").strip()

    if order_id is None and not uuid_str and not number_str:
        return HTMLResponse(_render_page())

    parts: list[str] = []
    local: dict[str, Any] | None = None

    if order_id is not None:
        try:
            local = fetch_local_order(order_id)
        except Exception as exc:
            parts.append(
                _section(
                    "Локальная БД",
                    f'<p class="err">Не удалось прочитать заказ: {exc}</p>',
                )
            )
        else:
            if local is None:
                parts.append(
                    _section(
                        "Локальная БDB",
                        f'<p class="err">Заказ #{order_id} не найден</p>',
                    )
                )
            else:
                rows = "".join(
                    f"<dt>{k}</dt><dd>{local[k] if local[k] is not None else '—'}</dd>"
                    for k in local
                )
                parts.append(_section("Локальная БД", f"<dl>{rows}</dl>"))
                if not uuid_str and local.get("cdek_order_uuid"):
                    uuid_str = str(local["cdek_order_uuid"])

    cdek_payload: dict[str, Any] | None = None
    cdek_error: str | None = None

    try:
        if uuid_str:
            cdek_payload = await get_order_by_uuid(uuid_str)
        elif number_str:
            cdek_payload = await get_order_by_cdek_number(number_str)
        elif local and local.get("cdek_order_uuid"):
            uuid_str = str(local["cdek_order_uuid"])
            cdek_payload = await get_order_by_uuid(uuid_str)
        else:
            cdek_error = "Нет cdek_order_uuid — заказ в CDEK не регистрировался или ошибка при создании."
            if local and local.get("cdek_error"):
                cdek_error += f" cdek_error: {local['cdek_error']}"
    except CdekClientError as exc:
        cdek_error = str(exc)
        if exc.body is not None:
            parts.append(
                _section(
                    "CDEK API — ошибка",
                    f'<p class="err">{cdek_error}</p><pre>{_pretty_json(exc.body)}</pre>',
                )
            )
    except Exception as exc:
        cdek_error = str(exc)
        parts.append(
            _section("CDEK API — ошибка", f'<p class="err">{cdek_error}</p>')
        )

    if cdek_payload is not None:
        summary = _extract_summary(cdek_payload)
        entity = (
            cdek_payload.get("entity")
            if isinstance(cdek_payload, dict)
            else {}
        )
        found = bool(isinstance(entity, dict) and entity.get("uuid"))
        status_line = (
            '<p class="ok">Заказ найден в CDEK</p>'
            if found
            else '<p class="err">Ответ получен, но entity пустой — заказ мог не создаться</p>'
        )
        rows = "".join(
            f"<dt>{k}</dt><dd>{summary[k] if summary[k] is not None else '—'}</dd>"
            for k in summary
        )
        parts.append(
            _section(
                "CDEK — кратко",
                status_line + f"<dl>{rows}</dl>",
            )
        )
        parts.append(
            _section(
                "CDEK — полный JSON",
                f"<pre>{_pretty_json(cdek_payload)}</pre>",
            )
        )

    elif cdek_error and not any("CDEK API" in p for p in parts):
        parts.append(_section("CDEK", f'<p class="err">{cdek_error}</p>'))

    return HTMLResponse(
        _render_page(
            order_id=oid_str,
            cdek_uuid=uuid_str,
            cdek_number=number_str,
            content="\n".join(parts),
        )
    )


@app.get("/api/cdek/order")
async def api_cdek_order(
    cdek_uuid: str | None = Query(default=None),
    cdek_number: str | None = Query(default=None),
) -> JSONResponse:
    try:
        if cdek_uuid:
            data = await get_order_by_uuid(cdek_uuid.strip())
        elif cdek_number:
            data = await get_order_by_cdek_number(cdek_number.strip())
        else:
            return JSONResponse(
                {"error": "cdek_uuid or cdek_number required"}, status_code=400
            )
        return JSONResponse({"summary": _extract_summary(data), "raw": data})
    except CdekClientError as exc:
        return JSONResponse(
            {
                "error": str(exc),
                "body": exc.body,
                "status_code": exc.status_code,
            },
            status_code=502,
        )


def main() -> None:
    uvicorn.run(
        "test_cdek.server:app",
        host=os.getenv("TEST_CDEK_HOST", "127.0.0.1"),
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
