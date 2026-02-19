from collections import defaultdict

from app.models.domain import Event, Job, Order, now_utc


class InMemoryStore:
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}
        self.events: dict[str, list[Event]] = defaultdict(list)
        self.jobs: list[Job] = []


store = InMemoryStore()


def seed_data() -> None:
    if store.orders:
        return

    created = now_utc()
    order = Order(
        id="ord-1",
        public_tracking_id="TRK001",
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
