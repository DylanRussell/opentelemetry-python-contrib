from typing import Tuple

import google.auth
from google.auth.transport import requests

from opentelemetry.exporter.otlp.proto.grpc.exporter import (
    BaseAuthHeaderSetter,
)


class GCPAuthHeaderSetter(BaseAuthHeaderSetter):
    def __init__(self):
        self._credentials, _ = google.auth.default() # type: ignore
        self._request = requests.Request()

    def get_auth_header(self) -> Tuple[str, str]:
        if self._credentials.expired: # type: ignore
            self._credentials.refresh(self._request) # type: ignore
        return ("Authorization", f"Bearer: {self._credentials.token}") # type: ignore