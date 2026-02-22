from collections import defaultdict

from app.models.domain import Event, Job, Order, ProofOfDelivery, now_utc


class InMemoryStore:
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}
        self.events: dict[str, list[Event]] = defaultdict(list)
        self.jobs: list[Job] = []
        self.idempotency_records: dict[tuple[str, str, str], dict] = {}
        self.pods: dict[str, ProofOfDelivery] = {}
        self.drones: dict[str, dict[str, int | bool]] = {}


store = InMemoryStore()

_DEFAULT_DRONES: dict[str, dict[str, int | bool]] = {
    "DR-1": {"available": True, "battery": 95},
    "DR-2": {"available": True, "battery": 10},
    "DR-3": {"available": True, "battery": 80},
}


def reset_store() -> None:
    store.orders.clear()
    store.events.clear()
    store.jobs.clear()
    store.idempotency_records.clear()
    store.pods.clear()
    store.drones.clear()
    store.drones.update({k: dict(v) for k, v in _DEFAULT_DRONES.items()})


def seed_data() -> None:
    if store.orders:
        return

    created = now_utc()
    order = Order(
        id="ord-1",
        public_tracking_id="11111111-1111-4111-8111-111111111111",
        merchant_id="merchant-1",
        customer_name="Demo Customer",
        status="ASSIGNED",
        created_at=created,
        updated_at=created,
    )
    store.orders[order.id] = order
    store.events[order.id].append(
        Event(
            id="evt-1",
            order_id=order.id,
            type="CREATED",
            message="Order created",
            created_at=created,
        )
    )
    store.jobs.append(
        Job(
            id="job-1",
            order_id=order.id,
            assigned_drone_id="DRONE-1",
            status="ACTIVE",
            created_at=created,
        )
    )


reset_store()
