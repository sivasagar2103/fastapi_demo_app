
from contextlib import asynccontextmanager
import asyncio
from rest_api_server.services.job_dispatcher import run_dispatcher
from time import perf_counter
from uuid import uuid4
import logging
from fastapi import FastAPI, Request
from rest_api_server.globals import Database
from rest_api_server.migrations import initialize_schema
from rest_api_server.repositories import Repositories
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from rest_api_server.globals import Settings
from rest_api_server.routers import auth, tenants, organizations, users, employees, employee_groups, exchange_rate_jobs
from rest_api_server.services.seed import seed

logger = logging.getLogger("demo.requests")

def create_app(settings: Settings | None = None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        database = Database(settings)
        app.state.database = database
        dispatcher = None
        try:
            await initialize_schema(database.engine)
            if settings.seed_demo:
                async with database.session_factory() as session:
                    async with session.begin():
                        await seed(Repositories(session), settings.demo_password)
            if settings.rabbitmq_password:
                dispatcher = asyncio.create_task(run_dispatcher(database, settings))
            yield
        finally:
            if dispatcher:
                dispatcher.cancel()
                await asyncio.gather(dispatcher, return_exceptions=True)
            await database.close()

    app = FastAPI(title = "Multi-Tenant Management API",
                  version="1.0.0",
                  lifespan = lifespan)
    app.state.settings = settings

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error: IntegrityError):
        return JSONResponse(status_code = 409,
                            content = {"detail": "Duplicate resource or conflicting database relationship"})

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = str(uuid4())
        start = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%.2f", request_id, request.method, request.url.path, response.status_code, (perf_counter()-start)*1000)
        return response

    @app.get("/health", tags = ["Operations"])
    def health():
        return {"status": "ok"}

    for module in (auth, tenants, organizations, users, employees, employee_groups, exchange_rate_jobs):
        app.include_router(module.router, prefix = "/api/v1")
    return app

app = create_app()
