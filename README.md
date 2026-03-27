# OCS网课助手AI+题库API

基于AI和手动题库的智能答题API，兼容OCS网课助手的AnswererWrapper接口。

## 使用须知

1. **本项目不允许进行商业盈利行为，答案根据所使用AI存在较大波动。**
2. **请使用者遵守相关规定，不进行作弊等行为**

## 功能特点

- AI+手动题库混合答题
- 支持 4 种 AI 接口：OpenAI Chat Completions、OpenAI Responses、DashScope 原生接口、Anthropic Claude
- 兼容OCS AnswererWrapper接口
- 支持GET请求方式
- 异步高并发处理
- **手动题库管理**（JSON文件存储），预防一些刁难题目
- 实时查询
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
# AI模型/接口
# 可选值: openai_chat_completions, openai_responses, dashscope, anthropic
AI_MODEL_API_KEY=your-api-key-here
AI_MODEL_PROVIDER=openai_chat_completions
AI_MODEL_NAME=gpt-3.5-turbo
AI_MODEL_BASE_URL=https://api.openai.com/v1

# thinking 参数：只要配置了该项（true 或 false），都会按对应值默认向上游显式转发；只有完全不配置时才不转发
AI_ENABLE_THINKING_PARAMS=false
# 以下开关默认关闭；只有显式设为 true 且请求显式传参时，才会转发到上游接口
AI_ENABLE_STRUCTURED_OUTPUT_PARAMS=false
AI_ENABLE_STREAMING_PARAMS=false

# OpenAI Responses API 示例
# AI_MODEL_PROVIDER=openai_responses
# AI_MODEL_NAME=gpt-5.4
# AI_MODEL_BASE_URL=https://api.openai.com/v1

# DashScope 原生接口示例
# AI_MODEL_PROVIDER=dashscope
# AI_MODEL_NAME=qwen-plus
# AI_MODEL_BASE_URL=https://dashscope.aliyuncs.com

# Anthropic Claude 接口示例
# AI_MODEL_PROVIDER=anthropic
# AI_MODEL_NAME=claude-sonnet-4-6
# AI_MODEL_BASE_URL=https://api.anthropic.com/v1

# 智能体配置
AI_AGENT_PROMPT=你的AI提示词

# 日志
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/ocs_api.log

# 允许的来源
ALLOWED_ORIGINS=*

# API接口配置
API_VERSION=v1
API_PREFIX=/api

# 响应配置
RESPONSE_CODE_SUCCESS=1
RESPONSE_CODE_ERROR=0
```

### 高级请求参数

搜索接口支持以下可选参数：

- `thinking=true` / `thinking=false`：显式请求开启或关闭深度思考
- `thinking_budget=256`：可选思考预算，仅在思考被转发且上游接口支持启用思考时使用
- `structured_output=true`：请求结构化输出
- `stream=true`：请求流式输出

这些参数默认都会被 API 接收，但转发规则分两类：

- `AI_ENABLE_THINKING_PARAMS`：**只有环境变量完全不存在时**，才不会把 `thinking` 转发到上游；只要配置了这个值（无论是 `true` 还是 `false`），都会按请求值或该 env 默认值，向对应模型接口显式发送“开启/关闭思考”请求
- `AI_ENABLE_STRUCTURED_OUTPUT_PARAMS=true`：开启后才会转发 `structured_output`
- `AI_ENABLE_STREAMING_PARAMS=true`：开启后才会转发 `stream`

具体行为如下：

- `AI_ENABLE_THINKING_PARAMS` 未配置：`thinking` / `thinking_budget` 不会传给上游
- `AI_ENABLE_THINKING_PARAMS=true`：未传 `thinking` 时默认向上游发送“开启思考”；传 `thinking=false` 时会显式发送“关闭思考”
- `AI_ENABLE_THINKING_PARAMS=false`：未传 `thinking` 时默认向上游发送“关闭思考”；传 `thinking=true` 时会显式发送“开启思考”
- `AI_ENABLE_STRUCTURED_OUTPUT_PARAMS=false`：`structured_output` 不会传给上游
- `AI_ENABLE_STREAMING_PARAMS=false`：`stream=true` 也会按普通非流式请求处理

## API接口

### 管理接口

- **GET** `/health` - 主应用状态
- **GET** `/api/v1/health` - API模块状态

### 搜索接口

- **GET** `/api/v1/search` - OCS题库搜索接口

## 响应格式说明

接口有两种响应模式：

### 1. 非流式响应（默认）

当未请求 `stream=true`，或 `AI_ENABLE_STREAMING_PARAMS=false` 时，返回原有 JSON 结构：

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

### 2. 流式响应（SSE）

当请求 `stream=true` 且 `AI_ENABLE_STREAMING_PARAMS=true` 时，接口返回 `text/event-stream`：

- `event: chunk`：模型增量文本片段
- `event: done`：最终汇总结果，包含 `answer`、`source`、`question_type` 等字段

示例：

```text
event: chunk
data: {"text":"A"}

event: done
data: {"code":1,"question":"问题内容","question_type":"single","options":"A.选项1\nB.选项2","answer":"A","source":"ai","confidence":0.8}
```

以下题型示例均对应**非流式 JSON 返回**：
### 单选题响应
```json
{
  "code": 1,
  "results": [
    {
      "question": "问题内容",
      "question_type": "single",
      "options": "A.选项1\nB.选项2\nC.选项3\nD.选项4",
      "answer": "A"
    }
  ]
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

**无缓存配置，需手动在网关缓存**

1. **手动题库**（最高优先级）- 存储在 `manual_question_bank.json`
2. **AI模型** - 最后的答案来源

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

手动题库存储在 `manual_question_bank.json` 文件中，可以直接编辑该文件来管理题库。

### 直接编辑文件

**推荐方式**：直接编辑 `manual_question_bank.json` 文件来管理题库：

```json
{
  "你的题目": {
    "answer": "答案",
    "note": "备注"
  }
}
```

编辑后无需重启服务，题目会立即生效。

## OCS网课助手配置

### 推荐配置（使用搜索接口）

```json
[
    {
        "url": "http://localhost:8000/api/v1/search?q=${title}&type=${type}&options=${options}",
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

# 测试结构化输出（仅在 AI_ENABLE_STRUCTURED_OUTPUT_PARAMS=true 时转发）
curl "http://localhost:8000/api/v1/search?q=中国的首都是哪里&type=single&options=A.上海+B.北京+C.广州+D.深圳&structured_output=true"

# 测试流式输出 SSE（仅在 AI_ENABLE_STREAMING_PARAMS=true 时启用真实流式）
curl -N "http://localhost:8000/api/v1/search?q=中国的首都是哪里&type=single&options=A.上海+B.北京+C.广州+D.深圳&stream=true"

# 健康检查
curl http://localhost:8000/health
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

- 请确定AI API密钥和请求地址正确
- **每次请求都实时查询，不使用缓存**
- 推荐使用GET接口，简洁高效
- 所有响应格式统一，便于前端处理
- 日志中会记录完整的响应信息
- 手动题库存储在 `manual_question_bank.json` 文件中
- `note` 字段仅作为备注，不会嵌入回答
