import inspect
from typing import Tuple

import google.auth
import grpc
from google.auth.transport import requests
from google.auth.transport.grpc import AuthMetadataPlugin
from google.auth.transport.requests import AuthorizedSession

from opentelemetry.exporter.otlp.customizer import (
    BaseOTLPExporters,
    OTLPExporterCustomizerBase,
)


class GoogleOTLPExporterCustomizer(OTLPExporterCustomizerBase):
    def __init__(self):
        credentials, _ = google.auth.default()
        request = requests.Request()
        auth_metadata_plugin = AuthMetadataPlugin(
            credentials=credentials, request=request
        )

        self.authed_session = AuthorizedSession(credentials)
        self.channel_creds = grpc.composite_channel_credentials(
            grpc.ssl_channel_credentials(),
            grpc.metadata_call_credentials(auth_metadata_plugin),
        )

    def customize_exporter(
        self, exporter_class: BaseOTLPExporters
    ) -> Tuple[str, str]:
        params = inspect.signature(exporter_class.__init__).parameters
        if "credentials" in params and isinstance(
            self.channel_creds, params["credentials"].annotation
        ):
            return exporter_class(credentials=self.channel_creds)
        if "session" in params and isinstance(
            self.authed_session, params["session"].annotation
        ):
            return exporter_class(session=self.authed_session)
        raise RuntimeError(
            "OTLP Exporter class {export_class.__name__} does not contain a parameter named `sesion` or `credentials`."
        )

