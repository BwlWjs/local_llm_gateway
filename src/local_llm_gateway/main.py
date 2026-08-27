from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .admin.routes import router as admin_router
from .config import settings
from .core.errors import GatewayError
from .core.runtime import RuntimeSnapshot
from .core.service import GatewayService
from .facades.anthropic import AnthropicFacade
from .facades.openai import OpenAIFacade
from .models import (
    HealthResponse,
    MessageRequest,
    ModelListResponse,
    OpenAIChatCompletionRequest,
    Scope,
    TokenCountRequest,
    TokenCountResponse,
)
from .security import require_scope
from .storage.sqlite import KeyStore
from .streaming import canonical_error
from .translator import canonical_response_to_anthropic, canonical_response_to_openai

key_store = KeyStore(settings.db_path)
runtime = RuntimeSnapshot(client=httpx.AsyncClient(timeout=settings.request_timeout_s))
service = GatewayService(runtime=runtime)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    runtime.refresh_keys(key_store)
    yield
    if runtime.client is not None:
        await runtime.client.aclose()


app = FastAPI(
    title=settings.gateway_name, version=settings.gateway_version, lifespan=lifespan
)
app.state.runtime = runtime
app.state.key_store = key_store

app.include_router(admin_router)


def _http_exc(exc: GatewayError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "detail": exc.detail, "extra": exc.extra},
    )


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return service.health()


@app.get(
    "/v1/models",
    response_model=ModelListResponse,
    dependencies=[Depends(require_scope(Scope.models_list))],
)
async def list_models() -> ModelListResponse:
    return service.list_models()


@app.post("/v1/messages", dependencies=[Depends(require_scope(Scope.messages_create))])
async def messages(request: MessageRequest):
    try:
        canonical = AnthropicFacade().to_canonical(request, f"req_{uuid4().hex}")
        if canonical.stream:
            stream = service.stream_message(canonical)
            try:
                first_chunk = await anext(stream)
            except StopAsyncIteration:

                async def _empty_stream() -> AsyncIterator[bytes]:
                    if False:
                        yield b""

                return StreamingResponse(
                    _empty_stream(), media_type="text/event-stream"
                )
            except GatewayError as exc:
                raise _http_exc(exc) from exc

            async def _stream_body() -> AsyncIterator[bytes]:
                yield first_chunk
                try:
                    async for chunk in stream:
                        yield chunk
                except GatewayError as exc:
                    yield canonical_error(exc.code, exc.detail, exc.extra)

            return StreamingResponse(_stream_body(), media_type="text/event-stream")
        response = await service.create_message(canonical)
        return canonical_response_to_anthropic(response)
    except GatewayError as exc:
        raise _http_exc(exc) from exc


@app.post(
    "/v1/chat/completions", dependencies=[Depends(require_scope(Scope.messages_create))]
)
async def chat_completions(request: OpenAIChatCompletionRequest):
    try:
        canonical = OpenAIFacade().to_canonical(request, f"req_{uuid4().hex}")
        if canonical.stream:
            raise GatewayError(
                501,
                "stream_not_implemented",
                "openai streaming facade is not implemented yet",
            )
        response = await service.create_message(canonical)
        return canonical_response_to_openai(response)
    except GatewayError as exc:
        raise _http_exc(exc) from exc


@app.post(
    "/v1/messages/count_tokens",
    response_model=TokenCountResponse,
    dependencies=[Depends(require_scope(Scope.tokens_count))],
)
async def count_tokens(request: TokenCountRequest) -> TokenCountResponse:
    try:
        return await service.count_tokens(request)
    except GatewayError as exc:
        raise _http_exc(exc) from exc


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
