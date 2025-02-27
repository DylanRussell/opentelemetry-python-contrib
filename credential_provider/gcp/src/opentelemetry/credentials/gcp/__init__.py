import google.auth
import grpc
from google.auth.transport import requests
from google.auth.transport.grpc import AuthMetadataPlugin
from google.auth.transport.requests import AuthorizedSession
from requests import Session


def channel_credentials_provider() -> grpc.ChannelCredentials:
    credentials, _ = google.auth.default()
    return grpc.composite_channel_credentials(
        grpc.ssl_channel_credentials(),
        grpc.metadata_call_credentials(
            AuthMetadataPlugin(
                credentials=credentials, request=requests.Request()
            )
        ),
    )


def session_provider() -> Session:
    credentials, _ = google.auth.default()
    return AuthorizedSession(credentials)