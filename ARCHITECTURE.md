# MaShell Architecture Document

## Overview

MaShell is an AI-powered command-line assistant built with modern Python (3.11+). It provides an agentic interface to LLMs that can execute shell commands, manipulate files, and accomplish complex tasks autonomously while keeping users in control through an interactive permission system.

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER                                     │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    CLI Interface                         │    │
│  │         (argparse / rich console / logo)                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Agent Core                             │    │
│  │        (conversation loop / tool orchestration)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│           │                    │                    │            │
│           ▼                    ▼                    ▼            │
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────┐     │
│  │  Provider   │    │   Tool System   │    │  Permission  │     │
│  │   Layer     │    │                 │    │   Manager    │     │
│  └─────────────┘    └─────────────────┘    └──────────────┘     │
│           │                    │                    │            │
│           ▼                    ▼                    ▼            │
│  ┌─────────────┐    ┌─────────────────┐    ┌──────────────┐     │
│  │ OpenAI     │    │ • shell         │    │ • approve    │     │
│  │ Azure      │    │ • run_background│    │ • deny       │     │
│  │ Anthropic  │    │ • check_bg      │    │ • edit       │     │
│  │ Ollama     │    │                 │    │ • always     │     │
│  └─────────────┘    └─────────────────┘    └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mashell/
├── __init__.py
├── __main__.py              # Entry point: python -m mashell
├── cli.py                   # CLI argument parsing & main loop
├── config.py                # Configuration loading & validation
├── logo.py                  # ASCII art logo display
│
├── agent/
│   ├── __init__.py
│   ├── core.py              # Main agent loop & orchestration
│   ├── context.py           # Context management & compression
│   └── prompt.py            # System prompts & templates
│
├── providers/
│   ├── __init__.py
│   ├── base.py              # Abstract base provider
│   ├── openai.py            # OpenAI provider
│   ├── azure.py             # Azure OpenAI provider
│   ├── anthropic.py         # Anthropic provider
│   └── ollama.py            # Ollama (local) provider
│
├── tools/
│   ├── __init__.py
│   ├── base.py              # Base tool class & registry
│   ├── shell.py             # Universal shell command execution
│   └── background.py        # Long-running task management
│
├── permissions/
│   ├── __init__.py
│   ├── manager.py           # Permission checking & prompting
│   ├── rules.py             # Permission rule definitions
│   └── ui.py                # Permission prompt UI
│
└── utils/
    ├── __init__.py
    ├── console.py           # Rich console utilities
    ├── process.py           # Subprocess management
    └── paths.py             # Path utilities
```

---

## Core Components

### 1. CLI Interface (`cli.py`)

处理命令行参数解析和主入口。

**职责：**
- 解析 `--provider`, `--url`, `--key`, `--model`, `--profile` 等参数
- 显示 Logo
- 启动 Agent（单次 prompt 或交互模式）

### 2. Configuration (`config.py`)

管理配置，优先级：CLI 参数 > 环境变量 > 配置文件

**数据结构：**
- `ProviderConfig`: provider, url, key, model
- `PermissionConfig`: auto_approve 列表, always_ask 列表
- `Config`: 汇总所有配置

### 3. Provider Layer (`providers/`)

LLM 提供商的抽象接口。

**支持的 Provider：**
| Provider | URL | Key 需要 | Tool Call |
|----------|-----|---------|-----------|
| OpenAI | `https://api.openai.com/v1` | ✅ | ✅ |
| Azure OpenAI | `https://{resource}.openai.azure.com` | ✅ | ✅ |
| Anthropic | `https://api.anthropic.com` | ✅ | ✅ |
| Ollama | `http://localhost:11434` | ❌ | ✅ (qwen2.5, llama3.1+) |

**BaseProvider 接口：**
- `chat(messages, tools)` → Response (content + tool_calls)

---

## Fundamental Design Principles

### 原则 1: Native File Awareness（原生文件感知）

**不依赖 shell 命令来读取文件和目录。**

#### 为什么这很重要

| Shell 方式 (`cat`, `ls`) | Native 方式 (Python I/O) |
|-------------------------|-------------------------|
| 命令回显噪声，浪费 token | 直接返回内容 |
| 每次读取需要权限确认 | 读取自动批准，写入才确认 |
| 二进制文件会乱码 | 检测并优雅处理 |
| 无法带行号 | 可标注行号便于 patch |
| 需要多轮探索 | Agent 预先"感知"workspace |

#### 读写分离原则

```
读取操作 (低风险) → 自动批准
├── read_file      读文件内容
├── list_dir       列目录
└── search_files   搜索/grep

执行操作 (高风险) → 需要确认
├── shell          执行任意命令
├── write_file     写入/修改文件
└── run_background 后台任务
```

#### 设计细节

1. **智能截断**：文件过长时保留头尾，中间标记 `[... N lines omitted ...]`
2. **二进制检测**：检测到二进制返回 `[Binary file, N bytes]` 而非乱码
3. **行号标注**：便于后续生成精确的 patch/diff
4. **编码处理**：自动检测 UTF-8/Latin-1，失败时返回错误而非乱码

### 原则 2: Diff-First Output（优先输出 Diff）

**修改文件时，优先生成可 apply 的 patch，而非完整文件。**

#### 为什么

- **Token 效率**：100 行文件改 2 行，只需输出 ~10 行 diff，而非 100 行
- **安全性**：小 diff 易于人工审核，不容易"幻觉删除"代码
- **可逆性**：patch 可以轻松 revert

#### 工具设计

```python
# write_file 支持两种模式：
write_file(path, content)           # 完整覆盖（新文件）
write_file(path, patch, mode="patch")  # 应用 unified diff
```

### 原则 3: Human-in-the-Loop for Mutations（写操作必须确认）

**任何可能改变系统状态的操作，都需要人工确认。**

| 操作类型 | 权限级别 | 原因 |
|---------|---------|------|
| 读取文件/目录 | `auto` | 无副作用 |
| 搜索文件内容 | `auto` | 无副作用 |
| 写入/删除文件 | `always_ask` | 不可逆 |
| 执行 shell 命令 | `always_ask` | 可能有任意副作用 |
| 安装包 | `always_ask` | 改变系统状态 |

---

### 4. Tool System (`tools/`)

基于上述原则设计的工具系统。

**工具列表：**
| Tool | 描述 | 需要权限 |
|------|------|---------|
| `read_file` | 读取文件内容（带行号） | ❌ 自动 |
| `list_dir` | 列出目录内容 | ❌ 自动 |
| `search_files` | 搜索文件内容 (grep) | ❌ 自动 |
| `write_file` | 写入/修改文件 | ✅ 需确认 |
| `shell` | 执行任意 shell 命令 | ✅ 需确认 |
| `run_background` | 启动后台长任务 | ✅ 需确认 |
| `check_background` | 检查后台任务输出 | ❌ 自动 |

**shell 工具的定位变化：**

Shell 现在专注于**执行操作**，而非文件读取：
- 运行代码: `python script.py`, `node app.js`
- 安装: `pip install pkg`, `brew install tool`
- Git: `git status`, `git commit -m "msg"`
- 构建: `make`, `npm run build`
- 网络: `curl`, `wget`

**不再推荐用 shell 做的事：**
- ~~读文件: `cat`, `head`, `tail`~~ → 用 `read_file`
- ~~列目录: `ls`, `find`, `tree`~~ → 用 `list_dir`
- ~~搜索: `grep`, `rg`~~ → 用 `search_files`

### 5. Permission System (`permissions/`)

交互式权限管理系统。

**权限级别：**
- `auto_approve`: 自动批准（如读文件）
- `always_ask`: 每次询问（如执行命令）

**用户选项：**
- `y` - 批准这次
- `n` - 拒绝
- `e` - 编辑命令后执行
- `a` - 本次会话始终批准此类操作

### 6. Agent Core (`agent/`)

核心编排循环，协调所有组件。

**agent/core.py 职责：**
- 初始化 provider, tools, permissions
- 主循环: 发送消息 → 解析响应 → 执行工具 → 继续

**agent/context.py 职责：**
- Context 窗口管理
- 历史消息压缩
- 任务记忆保持

**agent/prompt.py 职责：**
- System prompt 模板
- 工具使用指南

---

## Context 管理 & 任务记忆

这是让 AI 在长对话中"不迷路"的关键设计。

### 问题

LLM 有 context 窗口限制（如 8K, 32K, 128K tokens）。长任务会：
1. **超出窗口** — 早期消息被截断，AI 忘记最初任务
2. **输出过长** — 命令输出占用大量 token
3. **迷失方向** — 执行多步后忘记最终目标

### 解决方案：三层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Context Window                            │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Layer 1: Task Memory (始终保留)                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ • 原始用户任务                                    │  │  │
│  │  │ • 当前步骤/进度                                   │  │  │
│  │  │ • 关键决策和发现                                  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Layer 2: Summary Memory (压缩后保留)                  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ • 已执行命令的摘要                                │  │  │
│  │  │ • 重要输出的关键信息                              │  │  │
│  │  │ • 错误和解决方案                                  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Layer 3: Recent History (完整保留)                    │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ • 最近 N 轮对话                                   │  │  │
│  │  │ • 当前工具调用和输出                              │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: Task Memory（任务记忆）

**始终保留**，永不压缩。包含：

```
[TASK MEMORY]
Original Task: "帮我创建一个 FastAPI 项目，包含用户认证"
Current Step: 3/5 - 创建数据库模型
Progress:
  ✓ Step 1: 初始化项目结构
  ✓ Step 2: 安装依赖 (fastapi, sqlalchemy, passlib)
  → Step 3: 创建数据库模型
  ○ Step 4: 实现认证路由
  ○ Step 5: 添加 JWT 中间件
Key Decisions:
  - 使用 SQLite 作为开发数据库
  - 密码使用 bcrypt 哈希
```

这段内容会被注入到每次请求的 system prompt 中。

### Layer 2: Summary Memory（摘要记忆）

**压缩历史**。当消息太多时：
1. 保留最近 N 条完整消息
2. 更早的消息压缩成摘要

**压缩前（原始）：**
```
User: 列出当前目录文件
Assistant: [tool_call: shell "ls -la"]
Tool: total 24
drwxr-xr-x  5 user  staff   160 Jan 29 10:00 .
-rw-r--r--  1 user  staff   234 Jan 29 10:00 main.py
-rw-r--r--  1 user  staff   567 Jan 29 10:00 requirements.txt
... (更多输出)
Assistant: 目录包含 main.py 和 requirements.txt...
```

**压缩后（摘要）：**
```
[History Summary]
- Listed directory: found main.py, requirements.txt, models/
- Installed dependencies via pip
- Created database schema in models/user.py
```

### Layer 3: Recent History（近期历史）

**完整保留**最近的交互，保证 AI 有足够上下文执行当前操作。

### 压缩触发条件

```
if total_tokens > max_context * 0.8:
    compress_old_messages()
```

### 输出截断

命令输出可能很长，需要智能截断：

```
输出策略:
1. 短输出 (< 500 chars): 完整保留
2. 中等输出 (500-5000 chars): 保留前后部分 + 行数统计
3. 长输出 (> 5000 chars): 只保留摘要 + 关键行
```

**示例截断：**
```
[Output truncated: 2847 lines total]
First 20 lines:
...
Last 20 lines:
...
Key findings: 3 errors found, 127 warnings
```

### 实现细节

**ContextManager 类：**

| 方法 | 描述 |
|------|------|
| `add_message(msg)` | 添加新消息 |
| `get_context()` | 获取当前 context（包含任务记忆 + 摘要 + 近期） |
| `update_task_progress(step)` | 更新任务进度 |
| `compress_if_needed()` | 检查并压缩历史 |
| `truncate_output(output)` | 截断长输出 |

**压缩方式：**
1. **简单截断** — 删除最老的消息
2. **LLM 摘要** — 用 LLM 生成摘要（更智能但有开销）
3. **规则摘要** — 提取关键信息（命令、结果、错误）

**推荐：先实现规则摘要，后期可加 LLM 摘要**

---

## Data Flow

### Single Prompt Execution

```
User Input
    │
    ▼
┌─────────────────┐
│ Parse CLI Args  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Load Config    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Initialize Agent│
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Send to LLM    │◄────│  Tool Results   │
└────────┬────────┘     └────────▲────────┘
         │                       │
         ▼                       │
┌─────────────────┐     ┌────────┴────────┐
│ Parse Response  │     │ Execute Tool    │
└────────┬────────┘     └────────▲────────┘
         │                       │
         ▼                       │
    Tool Calls? ────Yes──► Permission Check
         │                       │
         No                   Approved?
         │                    │     │
         ▼                   Yes    No
┌─────────────────┐          │     │
│ Display Output  │◄─────────┘     │
└─────────────────┘                │
                                   ▼
                           Return Error
```

### Interactive Mode Loop

```
┌──────────────────────────────────────────────┐
│              Display Logo                     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
              ┌────────────────┐
         ┌───►│ Read User Input│
         │    └───────┬────────┘
         │            │
         │            ▼
         │    ┌────────────────┐
         │    │ Process Input  │ (same as single prompt)
         │    └───────┬────────┘
         │            │
         │            ▼
         │    ┌────────────────┐
         │    │ Display Result │
         │    └───────┬────────┘
         │            │
         └────────────┘ (loop until exit)
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Project structure setup
- [ ] CLI argument parsing
- [ ] Configuration loading
- [ ] Logo display
- [ ] Basic console output

### Phase 2: Provider Layer (Week 2)
- [ ] Base provider interface
- [ ] OpenAI provider implementation
- [ ] Azure OpenAI provider
- [ ] Ollama provider
- [ ] Anthropic provider

### Phase 3: Tool System (Week 3)
- [ ] Tool base class & registry
- [ ] shell tool (universal command execution)
- [ ] run_background tool
- [ ] check_background tool

### Phase 4: Permission System (Week 4)
- [ ] Permission manager
- [ ] Rich UI prompts
- [ ] Session memory (always approve)
- [ ] Config-based rules

### Phase 5: Agent Core (Week 5)
- [ ] Conversation management
- [ ] Tool orchestration loop
- [ ] Error handling
- [ ] System prompts

### Phase 6: Background Tasks (Week 6)
- [ ] Background task manager
- [ ] run_background tool
- [ ] check_background tool
- [ ] Output streaming

### Phase 7: Polish (Week 7)
- [ ] Interactive mode REPL
- [ ] Error messages & help
- [ ] Logging & verbose mode
- [ ] Documentation

### Phase 8: Packaging (Week 8)
- [ ] pyproject.toml setup
- [ ] Entry points
- [ ] PyPI publishing
- [ ] CI/CD pipeline

---

## Dependencies

```toml
[project]
name = "mashell"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.25.0",        # Async HTTP client
    "rich>=13.0.0",         # Beautiful terminal output
    "pyyaml>=6.0",          # Config file parsing
    "prompt-toolkit>=3.0",  # Interactive input
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "ruff>=0.1.0",
    "mypy>=1.0",
]

[project.scripts]
mashell = "mashell.cli:main"
```

---

## Key Design Decisions

### 1. Async-First Architecture
All I/O operations (HTTP, subprocess, file) are async for better concurrency, especially when handling long-running background tasks.

### 2. Provider Abstraction
Clean separation allows easy addition of new LLM providers without touching core logic.

### 3. Tool as First-Class Objects
Each tool is a self-contained class with schema, permissions, and execution logic. Easy to add new tools.

### 4. Permission Granularity
Permissions are per-tool-type, not per-command. This balances security with usability.

### 5. Session Memory
"Always approve" only lasts for the session. No permanent permission grants to avoid security risks.

### 6. Config Priority
CLI args > Environment variables > Config file > Defaults. Users can override at any level.

---

## Security Considerations

1. **No credential storage** — API keys come from env vars or CLI, never saved
2. **Permission prompts** — All destructive operations require explicit approval
3. **Command visibility** — Full command shown before execution
4. **Edit capability** — Users can modify commands before running
5. **No auto-approve persistence** — Session approvals don't persist
6. **Sandboxing (future)** — Consider container-based execution for untrusted commands
