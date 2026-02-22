from app.routers import jobs as jobs_router


def test_jobs_endpoint_passes_db_and_pagination_args(client, db_session, monkeypatch):
    captured: dict[str, object] = {}

    def fake_list_jobs(auth, db, active_only, page, page_size, order_id):
        captured["auth"] = auth
        captured["db"] = db
        captured["active_only"] = active_only
        captured["page"] = page
        captured["page_size"] = page_size
        captured["order_id"] = order_id
        return [], 0

    monkeypatch.setattr(jobs_router, "list_jobs", fake_list_jobs)

    response = client.get("/api/v1/jobs?active=true&page=2&page_size=5")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 2,
        "page_size": 5,
        "total": 0,
        "pagination": {"page": 2, "page_size": 5, "total": 0},
    }
    assert captured["db"] is db_session
    assert captured["active_only"] is True
    assert captured["page"] == 2
    assert captured["page_size"] == 5
    assert captured["order_id"] is None
