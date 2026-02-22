from app.models.domain import Event, Job, Order, ProofOfDelivery, now_utc
from app.services.store import reset_store, store


def test_reset_store_clears_runtime_mutations_and_restores_default_drones():
    created = now_utc()
    store.orders["ord-x"] = Order(
        id="ord-x",
        public_tracking_id="track-x",
        merchant_id="merchant-x",
        customer_name="Temp",
        status="CREATED",
        created_at=created,
        updated_at=created,
    )
    store.events["ord-x"].append(
        Event(
            id="evt-x",
            order_id="ord-x",
            type="CREATED",
            message="created",
            created_at=created,
        )
    )
    store.jobs.append(
        Job(
            id="job-x",
            order_id="ord-x",
            assigned_drone_id="DR-X",
            status="ACTIVE",
            created_at=created,
        )
    )
    store.idempotency_records[("user", "route", "key")] = {"request_hash": "abc"}
    store.pods["ord-x"] = ProofOfDelivery(
        order_id="ord-x",
        method="PHOTO",
        otp_code=None,
        operator_name=None,
        photo_url="https://cdn.example/pod.jpg",
        created_at=created,
    )
    store.drones["DR-NEW"] = {"available": True, "battery": 100}

    reset_store()

    assert store.orders == {}
    assert dict(store.events) == {}
    assert store.jobs == []
    assert store.idempotency_records == {}
    assert store.pods == {}
    assert set(store.drones.keys()) == {"DR-1", "DR-2", "DR-3"}


def test_reset_store_returns_fresh_drone_dict_instances():
    baseline_dr1 = store.drones["DR-1"]
    store.drones["DR-1"]["battery"] = 1

    reset_store()

    assert store.drones["DR-1"]["battery"] == 95
    assert store.drones["DR-1"] is not baseline_dr1
