

import time
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import api_router

# 1. Instantiate FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)


# 2. Configure Cross-Origin Resource Sharing (CORS) Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust allowed origins for production deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def add_timing_and_request_id_middleware(request: Request, call_next) -> Response:

    start_time = time.time()
    
    # Extract existing request ID header or generate a new UUID4
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Process request down the route handler stack
    response: Response = await call_next(request)
    
    # Compute elapsed process duration in seconds
    process_time = time.time() - start_time
    
    # Inject tracing headers into the HTTP response
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    
    return response


# 4. Include Master API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


# 5. System Health Check Endpoint
@app.get("/health", tags=["Health Check"])
def health_check():
   
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION
    }