from pydantic import BaseModel


class TimingMetricStats(BaseModel):
    count: int
    avg_s: float
    max_s: float


class MetricsResponse(BaseModel):
    counters: dict[str, int]
    timings: dict[str, TimingMetricStats]
