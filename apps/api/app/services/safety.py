from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.config import is_production_mode, resolved_ui_service_mode


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True


def _is_placeholder_order_id(order_id: str) -> bool:
    return order_id.startswith("ord-")


def assert_production_safe(*, order_id: str | None = None) -> None:
    if not is_production_mode():
        return

    mode = resolved_ui_service_mode()
    if mode != "db":
        raise RuntimeError("APP_MODE=production requires WINGXTRA_UI_SERVICE_MODE=db")

    if order_id is not None:
        if _is_placeholder_order_id(order_id) or not _is_uuid(order_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Production mode requires UUID order IDs",
            )
