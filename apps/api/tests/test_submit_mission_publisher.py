import asyncio

from starlette.requests import Request

from app.auth.dependencies import AuthContext
from app.routers.orders import submit_mission_endpoint
from app.services.store import store
from app.services.ui_store_service import create_order, manual_assign


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[dict[str, str]] = []

    def publish_mission_intent(self, payload: dict[str, str]) -> None:
        self.published.append(payload)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/orders/placeholder/submit-mission-intent",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def test_submit_mission_endpoint_calls_publisher_once() -> None:
    store.orders.clear()
    store.events.clear()
    store.jobs.clear()
    store.idempotency_records.clear()

    auth = AuthContext(user_id="ops-1", role="OPS")
    order = create_order(auth, customer_name="Mission customer")
    manual_assign(auth, order["id"], "DR-3")

    publisher = FakePublisher()
    response = asyncio.run(
        submit_mission_endpoint(
            order_id=order["id"],
            request=_request(),
            idempotency_key=None,
            auth=auth,
            publisher=publisher,
        )
    )

    assert response.order_id == order["id"]
    assert len(publisher.published) == 1
    assert publisher.published[0]["order_id"] == order["id"]
    assert publisher.published[0]["mission_intent_id"].startswith("mi_")
