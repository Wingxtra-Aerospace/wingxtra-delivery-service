# Error analysis (current branch)

## 1) Import-time failure in mission submit route (fixed)

`apps/api/app/routers/orders.py` had `except` blocks without a matching `try` block in
`submit_mission_endpoint`, causing Python to raise a `SyntaxError` before tests could run.

## 2) `ui_service.py` is internally inconsistent and partially duplicated

`apps/api/app/services/ui_service.py` currently contains mixed implementations:

- references to names that are never imported (`timezone`, `os`, `uuid`, `status`,
  `select`, `func`, `and_`, `or_`, `String`, `re`, `ui_store_service`, `ui_db_service`),
- two separate definitions for several public functions (`list_orders`, `manual_assign`,
  `submit_mission`, `create_pod`),
- stray code at module scope that appears to be an accidentally pasted function body.

This produces runtime errors such as `NameError: name '_mode' is not defined`, and causes a
large fraction of API/integration tests to fail.

## 3) Why so many downstream test failures happen

Most failing tests rely on order creation and assignment paths.
When `create_order` in `ui_service.py` crashes early with `NameError`, nearly all integration
flows fail transitively (orders, dispatch, mission submit, tracking, idempotency, readiness).

## 4) Suggested remediation sequence

1. Rebuild `ui_service.py` as a thin orchestrator over `ui_store_service` and `ui_db_service`
   with a single definition for each public function.
2. Ensure any mode helper (`_mode`) is defined exactly once and covered by unit tests.
3. Re-run `pytest` and then fix residual behavioral incompatibilities.
