# app/models/_init_.py
# Import SQLAlchemy models so they register on Base.metadata
from app.models.delivery_event import DeliveryEvent, DeliveryEventType  # noqa: F401
from app.models.delivery_job import DeliveryJob  # noqa: F401
from app.models.order import Order, OrderStatus  # noqa: F401