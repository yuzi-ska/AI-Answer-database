# OCS网课助手AI+题库API

基于AI和题库的智能答题API，兼容OCS网课助手的AnswererWrapper接口。

## 功能特点

- AI+题库混合答题
- 支持OpenAI兼容接口（OpenAI、DeepSeek、通义千问等）
- 完全兼容OCS AnswererWrapper接口
- 支持GET和POST两种请求方式
- 异步高并发处理
- 本地SQLite数据库存储
- 灵活的缓存方案（内存/Redis）
- 可配置的API版本和响应格式
- 统一的响应格式标准

## 缓存方案对比

### 内存缓存（默认）
- ✅ 无需额外服务
- ✅ 配置简单
- ❌ 服务重启后缓存丢失
- ❌ 多实例无法共享缓存

### Redis缓存
- ✅ 持久化存储
- ✅ 多实例共享缓存
- ✅ 支持集群部署
- ✅ 更高的缓存性能
- ❌ 需要Redis服务
- ❌ 配置稍复杂

## 安装和运行

```bash
# 安装依赖
pip install -r requirements.txt

# 如果使用Redis缓存，需要安装Redis
# Windows: 下载Redis for Windows或使用Docker
# Linux/Mac: sudo apt-get install redis-server 或 brew install redis

# 启动Redis服务（如果使用Redis缓存）
redis-server

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 环境配置

创建 `.env` 文件：

```env
# 数据库
DATABASE_URL=sqlite:///./ocs_api.db

# AI模型（OpenAI兼容接口）
AI_MODEL_API_KEY=your-api-key
AI_MODEL_PROVIDER=openai
AI_MODEL_NAME=gpt-3.5-turbo
AI_MODEL_BASE_URL=https://api.openai.com/v1

# DeepSeek示例
# AI_MODEL_PROVIDER=deepseek
# AI_MODEL_NAME=deepseek-chat
# AI_MODEL_BASE_URL=https://api.deepseek.com/v1

# 其他OpenAI兼容模型示例
# AI_MODEL_PROVIDER=custom
# AI_MODEL_NAME=qwen-plus
# AI_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 缓存配置
# 使用内存缓存（默认）
USE_REDIS_CACHE=false
MEMORY_CACHE_SIZE=1000
CACHE_TTL=3600

# 使用Redis缓存（取消注释以下配置）
# USE_REDIS_CACHE=true
# REDIS_URL=redis://localhost:6379/0
# REDIS_PASSWORD=your-redis-password
# REDIS_DB=0
# CACHE_TTL=3600

# 日志
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/ocs_api.log

# 允许的来源
ALLOWED_ORIGINS=*

# API接口配置
API_VERSION=v1
API_PREFIX=/api
ENABLE_DOCS=true
ENABLE_REDOC=true

# 响应配置
RESPONSE_CODE_SUCCESS=1
RESPONSE_CODE_ERROR=0
RESPONSE_MSG_SUCCESS=成功
RESPONSE_MSG_ERROR=失败
```

## API接口

### OCS搜索接口（推荐）

**GET** `/api/search?q=问题内容&type=single&options=A.选项1 B.选项2`

参数说明：
- `q` - 问题内容（支持URL编码）
- `type` - 题目类型（single/multiple/judgment/completion等）
- `options` - 选项内容（支持URL编码）

响应格式：
```json
{
  "code": 1,
  "results": [
    {
      "question": "问题内容",
      "answer": "A"
    }
  ]
}
```

### POST答案接口

**POST** `/api/v1/answer`

兼容OCS AnswererWrapper格式，支持灵活的请求参数：

```json
{
  "question": "问题内容",
  "question_type": "single",
  "options": "A.选项1\nB.选项2",
  "use_ai": true,
  "use_question_bank": true
}
```

### 管理接口

- **GET** `/health` - 主应用状态
- **GET** `/api/v1/health` - API模块状态
- **GET** `/api/v1/cache/clear` - 清空缓存
- **POST** `/api/v1/config/validate` - 验证OCS配置
- **GET** `/api/v1/config/example` - 获取配置示例
- **GET** `/api/v1/status` - 获取题库状态
- **POST** `/api/v1/status` - 刷新题库状态

### API文档

- **GET** `/docs` - Swagger UI文档（可配置开关）
- **GET** `/redoc` - ReDoc文档（可配置开关）

## 响应格式说明

所有API接口统一使用以下响应格式：

### 成功响应
```json
{
  "code": 1,
  "results": [
    {
      "question": "问题内容",
      "answer": "答案内容"
    }
  ]
}
```

### 错误响应
```json
{
  "code": 0,
  "results": []
}
```

### 多选题响应
```json
{
  "code": 1,
  "results": [
    {
      "question": "问题内容",
      "answer": "A#B#C"
    }
  ]
}
```

- 单选题：`answer` 包含单个选项字母
- 多选题：`answer` 包含多个选项字母，用#分隔
- 其他题型：`answer` 包含完整答案文本

## 查询优先级

1. 缓存 → 2. 本地数据库 → 3. OCS题库 → 4. AI模型

## OCS网课助手配置

### 推荐配置（使用搜索接口）

```json
[{"url": "http://localhost:8000/api/search?q=${title}&type=${type}&options=${options}", "name": "OCS AI+题库API", "method": "get", "contentType": "json", "handler": "return (res)=> res.code === 1 && res.results.length > 0 ? [res.results[0].question, res.results[0].answer] : undefined"}]
```

### 备选配置（使用POST接口）

```json
[{"url": "http://localhost:8000/api/v1/answer", "name": "OCS AI+题库API", "data": {"question": "${title}", "question_type": "${type}", "options": "${options}", "use_ai": true, "use_question_bank": true}, "method": "post", "contentType": "json", "handler": "return (res) => res.answer ? [res.question, res.answer] : undefined"}]
```

## API测试

```bash
# 测试搜索接口
curl "http://localhost:8000/api/search?q=1+1等于几&type=single&options=A.1 B.2 C.3 D.4"

# 测试POST接口
curl -X POST http://localhost:8000/api/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "1+1等于几", "question_type": "single", "options": "A.1 B.2 C.3 D.4"}'

# 获取配置示例
curl http://localhost:8000/api/v1/config/example
```

## AI回答模式

### 选择题模式
当提供选项时，AI会：
- 单选题：只返回选项字母（如：A、B、C、D）
- 多选题：用#连接选项字母（如：A#B#C）
- 不进行任何解释或讲解

### 问答题模式
当不提供选项时，AI会返回详细的解答内容。

## 配置说明

### 缓存配置

#### 内存缓存（默认）
```env
USE_REDIS_CACHE=false
MEMORY_CACHE_SIZE=1000
CACHE_TTL=3600
```

#### Redis缓存
```env
USE_REDIS_CACHE=true
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password
REDIS_DB=0
CACHE_TTL=3600
```

**Redis连接格式说明：**
- `redis://localhost:6379/0` - 本地Redis，数据库0
- `redis://:password@localhost:6379/0` - 带密码的Redis
- `redis://username:password@host:port/db` - 完整连接字符串

**Redis配置参数：**
- `REDIS_URL` - Redis连接字符串
- `REDIS_PASSWORD` - Redis密码（可选）
- `REDIS_DB` - Redis数据库编号（默认0）
- `CACHE_TTL` - 缓存过期时间（秒）

### CORS配置
- 默认允许所有来源（`ALLOWED_ORIGINS=*`）
- 可根据需要限制特定域名

### API版本控制
- 通过 `API_VERSION` 配置版本号
- 通过 `API_PREFIX` 配置路径前缀
- 支持多版本并存

### 文档控制
- `ENABLE_DOCS` 控制Swagger UI显示
- `ENABLE_REDOC` 控制ReDoc显示
- 生产环境可关闭文档访问

### 响应格式定制
- `RESPONSE_CODE_SUCCESS` 成功响应码
- `RESPONSE_CODE_ERROR` 错误响应码

## 数据库管理

### 清除数据库数据

如果需要清除数据库中的所有数据，让所有请求都从AI开始回答：

```python
# 创建清除脚本 clear_database.py
from app.models import SessionLocal, QuestionAnswer

def clear_database():
    db = SessionLocal()
    try:
        count = db.query(QuestionAnswer).count()
        db.query(QuestionAnswer).delete()
        db.commit()
        print(f"已清除 {count} 条记录")
    finally:
        db.close()

clear_database()
```

运行脚本：
```bash
python clear_database.py
```

### 查询优先级

系统按以下优先级查询答案：
1. **缓存** - 最快响应
2. **本地数据库** - 历史AI答案和手动添加的题目
3. **OCS题库** - 外部题库接口
4. **AI模型** - 最后的答案来源

AI生成的答案会自动保存到本地数据库，供后续查询使用。

## 注意事项

- 确保OCS题库URL可访问
- CORS已配置为允许所有来源
- AI API需要有效的密钥
- 本地数据库自动创建和更新
- 推荐使用GET接口，更简洁高效
- POST接口支持更复杂的参数组合
- 所有响应格式统一，便于前端处理
- 日志中会记录完整的响应信息
- 清除数据库后，所有请求将直接使用AI回答
- AI回答会自动保存到数据库，提高后续响应速度

### Redis缓存注意事项
- 使用Redis缓存前，确保Redis服务已启动
- 生产环境推荐使用Redis以获得更好的性能
- Redis密码应使用强密码，确保安全
- 定期监控Redis内存使用情况
- 可以通过Redis CLI命令管理缓存：`redis-cli FLUSHALL` 清空所有缓存"# AI-Answer-database" 
