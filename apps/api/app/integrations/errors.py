from dataclasses import dataclass


@dataclass
class IntegrationError(Exception):
    service: str
    code: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.service}:{self.code}:{self.message}"


class IntegrationTimeoutError(IntegrationError):
    def __init__(self, service: str, message: str = "Upstream timeout") -> None:
        super().__init__(service=service, code="TIMEOUT", message=message, retryable=True)


class IntegrationUnavailableError(IntegrationError):
    def __init__(self, service: str, message: str = "Upstream unavailable") -> None:
        super().__init__(service=service, code="UNAVAILABLE", message=message, retryable=True)


class IntegrationBadGatewayError(IntegrationError):
    def __init__(self, service: str, message: str = "Unexpected upstream response") -> None:
        super().__init__(service=service, code="BAD_GATEWAY", message=message, retryable=False)
