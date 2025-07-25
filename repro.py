# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fastapi",
#     "opentelemetry-api",
#     "opentelemetry-sdk",
#     "opentelemetry-distro",
#     "opentelemetry-instrumentation",
#     "opentelemetry-exporter-otlp",
#     "uvicorn",
#     "opentelemetry-instrumentation-fastapi",
#     "opentelemetry-instrumentation-asgi",
#     "opentelemetry-util-http",
#     "opentelemetry-semantic-conventions",
# ]
#
# [tool.uv.sources]
# opentelemetry-api = { git = "https://github.com/dylanrussell/opentelemetry-python", branch = "fix_endless_logging", subdirectory = "opentelemetry-api" }
# opentelemetry-sdk = { git = "https://github.com/dylanrussell/opentelemetry-python", branch = "fix_endless_logging", subdirectory = "opentelemetry-sdk" }
# opentelemetry-semantic-conventions = { git = "https://github.com/dylanrussell/opentelemetry-python", branch = "fix_endless_logging", subdirectory = "opentelemetry-semantic-conventions" }
# opentelemetry-exporter-otlp = { git = "https://github.com/open-telemetry/opentelemetry-python", branch = "main", subdirectory = "exporter/opentelemetry-exporter-otlp" }
#
# opentelemetry-instrumentation-fastapi = { git = "https://github.com/open-telemetry/opentelemetry-python-contrib", branch = "main", subdirectory = "instrumentation/opentelemetry-instrumentation-fastapi" }
# opentelemetry-distro = { git = "https://github.com/open-telemetry/opentelemetry-python-contrib", branch = "main", subdirectory = "opentelemetry-distro" }
# opentelemetry-instrumentation = { git = "https://github.com/open-telemetry/opentelemetry-python-contrib", branch = "main", subdirectory = "opentelemetry-instrumentation" }
# opentelemetry-instrumentation-asgi = { git = "https://github.com/open-telemetry/opentelemetry-python-contrib", branch = "main", subdirectory = "instrumentation/opentelemetry-instrumentation-asgi" }
# opentelemetry-util-http = { git = "https://github.com/open-telemetry/opentelemetry-python-contrib", branch = "main", subdirectory = "util/opentelemetry-util-http" }
# ///

import os
import logging

logging.basicConfig(level=0)
os.environ["OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED"] = "true"

from opentelemetry.instrumentation import auto_instrumentation

auto_instrumentation.initialize()

import uvicorn

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    logging.info("Handling request for root endpoint")
    return {"message": "Hello World"}


uvicorn.run(app, host="0.0.0.0", port=3000)