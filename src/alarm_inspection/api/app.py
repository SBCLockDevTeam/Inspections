"""Minimal health endpoint for the first runnable slice."""

try:
    from fastapi import FastAPI
except ImportError:  # Allows domain tests to run without web dependencies.
    FastAPI = None


def create_app():
    if FastAPI is None:
        raise RuntimeError("Install the 'web' optional dependencies to run the API")
    app = FastAPI(title="Alarm Inspection Processor", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app() if FastAPI is not None else None

