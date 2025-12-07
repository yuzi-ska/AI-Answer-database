"""
OCS网课助手AI+题库API主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import answer
from app.core.config import settings
from app.models import create_tables

# 创建FastAPI应用
app = FastAPI(
    title="OCS网课助手AI+题库API",
    description="基于AI和题库的智能答题API",
    version="1.0.0",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_REDOC else None
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(answer.router, prefix=f"{settings.API_PREFIX}/{settings.API_VERSION}", tags=["answer"])
app.include_router(answer.router, prefix=settings.API_PREFIX, tags=["answer"])

@app.on_event("startup")
async def startup_event():
    """应用启动时创建数据库表"""
    create_tables()

@app.get("/")
@app.head("/")
async def root():
    return {
        "message": "OCS网课助手AI+题库API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
@app.head("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)