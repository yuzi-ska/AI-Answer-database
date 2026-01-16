# OCS网课助手AI+题库API

基于AI和题库的智能答题API，兼容OCS网课助手的AnswererWrapper接口。

## 使用须知

1. **本项目不允许进行商业盈利行为，答案根据所使用AI存在较大波动。**
2. **请使用者遵守相关规定，不进行作弊等行为**

## 功能特点

- AI+题库混合答题
- 支持OpenAI兼容接口（OpenAI、DeepSeek、通义千问等）
- 兼容OCS AnswererWrapper接口
- 支持GET请求方式
- 异步高并发处理
- **手动题库管理**（JSON文件存储），预防一些刁难题目
- 实时查询
- 灵活的题库配置
- 统一的响应格式标准

## 安装和运行

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 环境配置

创建 `.env` 文件：

```env
# AI模型（OpenAI兼容接口）
AI_MODEL_API_KEY=your-api-key-here
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

# 智能体配置
AI_AGENT_PROMPT=你的AI提示词

# OCS题库配置
# 单个题库配置示例
# QUESTION_BANK_CONFIG=[{"url":"https://api.example.com/search?q=${title}","name":"示例题库","method":"get","contentType":"json","handler":"return (res)=> res.code === 200 ? [res.data.question, res.data.answer] : undefined"}]

# 多个题库配置示例（取消注释使用）
# QUESTION_BANK_CONFIG=[{"url":"https://api.xinghuo.com/search?q=${title}","name":"星火题库","method":"get","contentType":"json","headers":{"Authorization":"Bearer your-api-key"},"handler":"return (res)=> res.code === 200 ? [res.data.question, res.data.answer] : undefined"},{"url":"https://api.xueersi.com/v1/question/search","name":"学而思题库","method":"post","contentType":"json","data":{"question":"${title}","type":"${type}"},"headers":{"X-API-Key":"your-api-key"},"handler":"return (res)=> res.status === 'success' && res.data ? [res.data.question, res.data.answer] : undefined"}]

# 题库查询超时时间（秒）
QUESTION_BANK_TIMEOUT=10

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
```

## API接口

### 管理接口

- **GET** `/health` - 主应用状态
- **GET** `/api/v1/health` - API模块状态
- **GET** `/api/v1/config/example` - 获取配置示例
- **GET** `/api/v1/status` - 获取题库状态

### 手动题库管理

- **GET** `/api/v1/manual-bank` - 获取手动题库内容
- **POST** `/api/v1/manual-bank/add` - 添加题目
- **DELETE** `/api/v1/manual-bank/remove` - 删除题目
- **DELETE** `/api/v1/manual-bank/clear` - 清空手动题库

### 搜索接口

- **GET** `/api/v1/search` - OCS题库搜索接口

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
      "question_type": "题目类型",
      "options": "选项内容（如果有）",
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
      "question_type": "multiple",
      "options": "A.选项1\nB.选项2\nC.选项3\nD.选项4",
      "answer": "A#B#C"
    }
  ]
}
```

### 填空题响应
```json
{
  "code": 1,
  "results": [
    {
      "question": "问题内容",
      "question_type": "completion",
      "options": "",
      "answer": "填空答案内容"
    }
  ]
}
```

### 判断题响应
```json
{
  "code": 1,
  "results": [
    {
      "question": "问题内容",
      "question_type": "judgment",
      "options": "",
      "answer": "对"
    }
  ]
}
```

#### 响应字段说明
- `question`: 问题内容（已清理无意义换行符）
- `question_type`: 题目类型（**single/multiple/judgment/completion**）
- `options`: 选项内容（选择题有值，其他题型为空）
- `answer`: 答案内容（根据题型格式化）

#### 答案格式说明
- 单选题：`answer` 包含单个选项字母（如：A、B、C、D）
- 多选题：`answer` 包含多个选项字母，用#分隔（如：A#B#C）
- 判断题：`answer` 包含"对"或"错"
- 填空题：`answer` 包含完整答案文本

## 查询优先级

每次请求都**实时查询**，不使用缓存：

1. **手动题库**（最高优先级）- 存储在 `manual_question_bank.json`
2. **OCS题库** - 外部题库接口
3. **AI模型** - 最后的答案来源

## 手动题库

手动题库使用 `manual_question_bank.json` 文件存储，**note备注不会嵌入回答中**，仅用于记录。

### 文件格式

```json
{
  "题目内容": {
    "answer": "答案",
    "type": "single",  // 可选，指定题型（single/multiple/completion/judgment）
    "note": "备注（可选，仅用于记录，不返回给前端）"
  }
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| answer | 是 | 答案内容 |
| type | 否 | 题目类型（single/multiple/completion/judgment），不指定则默认为single |
| note | 否 | 备注，仅用于记录，不会返回给前端 |

### 完整示例

```json
{
  "中国的首都是？": {
    "answer": "北京",
    "note": "基础地理题"
  },
  "以下哪个是偶数？": {
    "answer": "B",
    "type": "single",
    "note": "单选题示例"
  },
  "中国、美国、英国分别属于哪个大洲？": {
    "answer": "A#C#E",
    "type": "multiple",
    "note": "多选题示例：A.亚洲 B.非洲 C.欧洲 D.大洋洲 E.北美洲"
  },
  "地球的自转方向是？": {
    "answer": "对",
    "type": "judgment",
    "note": "判断题示例：正确答案为对"
  },
  "1+1等于几？": {
    "answer": "2+2=4",
    "type": "completion",
    "note": "填空题示例：相同题目不同题型"
  }
}
```

### 相同题目不同题型

手动题库支持**相同题目配置不同题型**，系统会优先匹配题目+类型都相同的结果：

```json
{
  "1+1等于几？": {
    "answer": "B",
    "type": "single",
    "note": "单选题：1+1等于几？ A.1 B.2 C.3 D.4"
  },
  "1+1等于几？": {
    "answer": "2",
    "type": "completion",
    "note": "填空题：1+1等于（）、（）"
  }
}
```

查询优先级：
1. 题目+类型精确匹配
2. 题目精确匹配
3. 模糊匹配（标题包含）

### 题目类型对应的答案格式

| 题目类型 | answer格式 | 示例 |
|---------|-----------|------|
| single（单选） | 单个选项字母 | `A`、`B`、`C`、`D` |
| multiple（多选） | 用#连接的选项字母 | `A#B#C`、`A#D` |
| completion（填空） | 完整答案文本 | `2`、`北京`、`H2O` |
| judgment（判断） | `对` 或 `错` | `对`、`错` |

### 管理命令

```bash
# 添加题目
curl -X POST "http://localhost:8000/api/v1/manual-bank/add?question=1+1等于几&answer=2"

# 查看题库
curl http://localhost:8000/api/v1/manual-bank

# 删除题目
curl -X DELETE "http://localhost:8000/api/v1/manual-bank/remove?question=1+1等于几"

# 清空题库
curl -X DELETE http://localhost:8000/api/v1/manual-bank/clear
```

### 直接编辑文件

也可以直接编辑 `manual_question_bank.json` 文件：

```json
{
  "你的题目": {
    "answer": "答案",
    "note": "备注"
  }
}
```

编辑后无需重启服务，题目会立即生效。

## OCS题库配置格式

### 基本格式

```json
[
  {
    "url": "http://localhost:8000/api/search?q=${title}",
    "name": "本地题库",
    "method": "get",
    "contentType": "json",
    "handler": "return (res)=> res.code === 1 && res.results.length > 0 ? [res.results[0].question, res.results[0].answer] : undefined"
  }
]
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | 是 | 请求URL，支持占位符 |
| name | string | 是 | 题库名称 |
| handler | string | 是 | JavaScript处理函数 |
| method | string | 否 | get/post，默认get |
| contentType | string | 否 | json/text，默认json |
| headers | object | 否 | 请求头 |
| data | object | 否 | POST请求体（支持占位符） |

### 占位符说明

- `${title}` - 题目内容
- `${type}` - 题目类型（single/multiple/completion/judgment）
- `${options}` - 选项内容

### Handler函数

返回格式：
- 单个结果：`[题目, 答案]`
- 无结果：`undefined`

## OCS网课助手配置

### 推荐配置（使用搜索接口）

```json
[
    {
        "url": "http://localhost:8000/api/search?q=${title}&type=${type}&options=${options}",
        "name": "OCS AI+题库API",
        "method": "get",
        "contentType": "json",
        "handler": "return (res)=> res.code === 1 && res.results.length > 0 ? [res.results[0].question, res.results[0].answer] : undefined"
    }
]
```

## API测试

```bash
# 测试搜索接口（数学题）
curl "http://localhost:8000/api/v1/search?q=1+1等于几&type=single&options=A.1+B.2+C.3+D.4"

# 测试搜索接口（选择题）
curl "http://localhost:8000/api/v1/search?q=中国的首都是哪里&type=single&options=A.上海+B.北京+C.广州+D.深圳"

# 获取配置示例
curl http://localhost:8000/api/v1/config/example

# 健康检查
curl http://localhost:8000/health

# 查看手动题库
curl http://localhost:8000/api/v1/manual-bank
```

## AI回答模式

### 选择题模式
当提供选项时：
- 单选题：只返回选项字母（如：A、B、C、D）
- 多选题：用#连接选项字母（如：A#B#C）
- 不进行任何解释或讲解

### 问答题模式
当不提供选项时，AI会返回详细的解答内容。

## 注意事项

- 确保OCS题库URL可访问
- 请确定AI API密钥和请求地址正确
- **每次请求都实时查询，不使用缓存**
- 推荐使用GET接口，简洁高效
- 所有响应格式统一，便于前端处理
- 日志中会记录完整的响应信息
- 手动题库存储在 `manual_question_bank.json` 文件中
- `note` 字段仅作为备注，不会嵌入回答