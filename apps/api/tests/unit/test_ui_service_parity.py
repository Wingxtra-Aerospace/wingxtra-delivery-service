from app.auth.dependencies import AuthContext
from app.services import ui_db_service, ui_store_service
from app.services.store import store


def test_create_order_response_schema_parity(db_session):
    auth = AuthContext(user_id="ops-1", role="OPS")
    store.orders.clear()
    store.events.clear()
    store.jobs.clear()

    db_order = ui_db_service.create_order(auth=auth, db=db_session, customer_name="db")
    store_order = ui_store_service.create_order(auth=auth, customer_name="store")

    assert set(db_order.keys()) == set(store_order.keys())
    assert db_order["status"] == "CREATED"
    assert store_order["status"] == "CREATED"


def test_manual_assign_transition_parity(db_session):
    auth = AuthContext(user_id="ops-1", role="OPS")
    store.orders.clear()
    store.events.clear()
    store.jobs.clear()

    db_order = ui_db_service.create_order(auth=auth, db=db_session, customer_name="db")
    st_order = ui_store_service.create_order(auth=auth, customer_name="store")

    db_assigned = ui_db_service.manual_assign(auth, db_session, db_order["id"], "DR-3")
    st_assigned = ui_store_service.manual_assign(auth, st_order["id"], "DR-3")

    assert db_assigned["status"] == st_assigned["status"] == "ASSIGNED"

    db_events = [
        item["type"] for item in ui_db_service.list_events(auth, db_session, db_order["id"])
    ]
    st_events = [item["type"] for item in ui_store_service.list_events(auth, st_order["id"])]
    assert db_events == st_events == ["CREATED", "VALIDATED", "QUEUED", "ASSIGNED"]
