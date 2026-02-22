from app.observability import metrics_store


def test_metrics_store_reset_clears_counters_and_timings():
    metrics_store.increment("dispatch_run_total")
    metrics_store.observe("dispatch_run_seconds", 0.25)

    metrics_store.reset()

    snapshot = metrics_store.snapshot()
    assert snapshot.counters == {}
    assert snapshot.timings == {}
