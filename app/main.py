"""
OCS网课助手AI+题库API主入口
每次请求实时查询，不使用缓存和数据库存储
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import answer
from app.core.config import settings

# 创建FastAPI应用
app = FastAPI(
    title="OCS网课助手AI+题库API",
    description="基于AI和题库的智能答题API（实时查询模式）",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
app.include_router(answer.router, prefix="/api/v1", tags=["answer"])

@app.get("/")
async def root():
    return {
        "message": "OCS网课助手AI+题库API",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)