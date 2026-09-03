"""
FastAPI application entrypoint.

Only wiring lives here: CORS (env-driven, never a wildcard in
production), router registration, and exception handlers that translate
every internal failure into a generic message — no SQL error, stack
trace, DB structure, password hash, or secret is ever allowed to reach a
response body. All business/security logic lives in routers/services/
dependencies, never in this file.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.routers import (
    admin,
    afiliados,
    auth_admin,
    auth_afiliado,
    convenios,
    cupos,
    dashboard,
    documentos,
    inventario,
    plantillas,
    reportes,
    tickets,
    transacciones,
)

logger = logging.getLogger("beetticket")
settings = get_settings()

app = FastAPI(title="BEET Ticket API", version="1.0.0")

if settings.is_production:
    # Fail loudly at startup rather than silently running with an
    # insecure default in production — these placeholders exist only so
    # the app can boot in development without a .env file.
    if "*" in settings.cors_origin_list:
        raise RuntimeError("CORS_ORIGINS no puede incluir '*' en producción. Configura los orígenes exactos permitidos.")
    if settings.jwt_secret == "CHANGE_ME_INSECURE_DEFAULT_DO_NOT_USE_IN_PRODUCTION":
        raise RuntimeError("JWT_SECRET sigue en su valor de desarrollo por defecto. Configura un secreto real antes de producción.")
    if settings.database_url == "postgresql+psycopg2://user:password@localhost:5432/beetticket":
        raise RuntimeError("DATABASE_URL sigue en su valor de desarrollo por defecto. Configura la base de datos real antes de producción.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers hide every response header from cross-origin JS except a
    # small safelist by default — Content-Disposition isn't in it. Without
    # this, the report-export downloads' server-generated dated filename
    # (read via response.headers.get("content-disposition") in
    # apiClient.getBlobWithFilename) is invisible to the frontend even
    # though the header is really there on the wire.
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's own field-level messages are safe to return (they never
    # include DB/internal details) — but we still normalize the shape.
    #
    # BUG FIX: exc.errors() can contain a raw exception object under
    # errors[i]["ctx"]["error"] whenever a @field_validator/@model_validator
    # raises ValueError (e.g. CompraRequest.cuotas_y_firma_solo_con_cupo,
    # ConvenioBase's price/date checks, AffiliateRegisterRequest's
    # passwords_match) — plain json.dumps (what JSONResponse uses) crashes
    # with "TypeError: Object of type ValueError is not JSON serializable"
    # on that shape, turning a validation 422 into an unhandled 500.
    # jsonable_encoder sanitizes it (renders the exception as its message
    # string) before this ever reaches json.dumps.
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Unhandled database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Ocurrió un error interno. Intenta nuevamente más tarde."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        # Let FastAPI's default handling take it from here — HTTPException
        # detail strings are always ones we wrote ourselves.
        raise exc
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Ocurrió un error interno. Intenta nuevamente más tarde."})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth_admin.router)
app.include_router(auth_afiliado.router)
app.include_router(afiliados.router)
app.include_router(convenios.router)
app.include_router(plantillas.router)
app.include_router(inventario.router)
app.include_router(cupos.router)
app.include_router(transacciones.router)
app.include_router(documentos.router)
app.include_router(tickets.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(reportes.router)
