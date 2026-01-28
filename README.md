# MaShell

```
███╗   ███╗ █████╗ ███████╗██╗  ██╗███████╗██╗     ██╗     
████╗ ████║██╔══██╗██╔════╝██║  ██║██╔════╝██║     ██║     
██╔████╔██║███████║███████╗███████║█████╗  ██║     ██║     
██║╚██╔╝██║██╔══██║╚════██║██╔══██║██╔══╝  ██║     ██║     
██║ ╚═╝ ██║██║  ██║███████║██║  ██║███████╗███████╗███████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
```

**🐚 Your AI-Powered Command Line Assistant — Any Model, Anywhere**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Overview

MaShell is an intelligent command-line tool that brings the power of any Large Language Model—cloud-based or local—directly to your terminal. It can execute commands, write and debug code, browse and edit files, install packages, and accomplish virtually any task that can be done via the command line.

Built with modern Python architecture, MaShell features an **interactive permission system** that keeps you in control while allowing AI to work autonomously when needed.

---

## ✨ Features

- **🤖 Any Model Support** — Works with OpenAI, Anthropic, Google, Mistral, Ollama, LM Studio, and any OpenAI-compatible API
- **⚡ Agentic Command Execution** — Runs shell commands to accomplish goals, with smart output parsing
- **🔐 Interactive Permission Approver** — Review and approve/deny commands before execution
- **📁 Full File Operations** — Read, write, edit, browse, and search files and directories
- **🛠️ Code Assistant** — Write, debug, refactor, and run code in any language
- **⏳ Long-Running Task Support** — Handles background processes, waits for output, and engages when needed
- **📦 Self-Extending** — Can install new CLI tools and packages to expand its capabilities
- **🎨 Beautiful CLI** — Clean interface with the MaShell logo on startup

---

## 🚀 Installation

```bash
pip install mashell
```

Or install from source:

```bash
git clone https://github.com/yourusername/MaShell.git
cd MaShell
pip install -e .
```

### Requirements

- Python 3.11+
- A supported LLM provider (API key or local model)

---

## 🔧 Configuration

MaShell needs 4 parameters to connect to any LLM:

| Parameter | Description | Required |
|-----------|-------------|----------|
| `--provider` | LLM provider type | ✅ Yes |
| `--url` | API endpoint URL | ✅ Yes |
| `--key` | API key | ⚠️ Depends (not needed for local) |
| `--model` | Model name | ✅ Yes |

### Cloud Providers

```bash
# OpenAI
mashell --provider openai \
        --url https://api.openai.com/v1 \
        --key sk-... \
        --model gpt-4o

# Azure OpenAI
mashell --provider azure \
        --url https://your-resource.openai.azure.com \
        --key your-azure-api-key \
        --model your-deployment-name

# Anthropic
mashell --provider anthropic \
        --url https://api.anthropic.com \
        --key sk-ant-... \
        --model claude-sonnet-4-20250514

# Any OpenAI-compatible API
mashell --provider openai \
        --url https://your-custom-endpoint.com/v1 \
        --key your-api-key \
        --model your-model-name
```

### Local LLM (Ollama)

Ollama runs locally—no API key needed:

```bash
# First, start Ollama and pull a model
ollama serve
ollama pull llama3

# Run MaShell with Ollama (no --key needed)
mashell --provider ollama \
        --url http://localhost:11434 \
        --model llama3
```

### Environment Variables

To avoid typing keys every time, set environment variables:

```bash
# Add to ~/.bashrc or ~/.zshrc
export MASHELL_PROVIDER="openai"
export MASHELL_URL="https://api.openai.com/v1"
export MASHELL_KEY="sk-..."
export MASHELL_MODEL="gpt-4o"
```

Then just run:
```bash
mashell "your prompt here"
```

### Config File (Optional)

Create `~/.mashell/config.yaml` for multiple provider profiles:

```yaml
default: anthropic

profiles:
  openai:
    provider: openai
    url: https://api.openai.com/v1
    key: ${OPENAI_API_KEY}
    model: gpt-4o
  
  azure:
    provider: azure
    url: https://your-resource.openai.azure.com
    key: ${AZURE_OPENAI_KEY}
    model: your-deployment-name
  
  anthropic:
    provider: anthropic
    url: https://api.anthropic.com
    key: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4-20250514
  
  ollama:
    provider: ollama
    url: http://localhost:11434
    model: llama3
    # no key needed for local

permissions:
  auto_approve:
    - read_file
    - list_directory
  always_ask:
    - execute_command
    - write_file
    - delete_file
```

Switch profiles easily:
```bash
mashell --profile ollama "write a hello world script"
```

---

## 📖 Usage

### Interactive Mode

Simply run `mashell` to start an interactive session:

```bash
mashell
```

You'll see the MaShell logo and can start chatting with your AI assistant.

### Direct Prompt

Pass a prompt directly:

```bash
mashell "find all Python files larger than 1MB in this directory"
```

### CLI Parameters

```bash
mashell [OPTIONS] [PROMPT]

Options:
  --provider TEXT         LLM provider (openai, azure, anthropic, ollama)
  --url TEXT              API endpoint URL
  --key TEXT              API key (not needed for local models)
  --model TEXT            Model name (or deployment name for Azure)
  --profile TEXT          Use a saved profile from config file
  -c, --config PATH       Path to config file
  -y, --yes               Auto-approve all commands (use with caution)
  -v, --verbose           Enable verbose output
  --no-logo               Skip the startup logo
  -h, --help              Show this help message
```

### Examples

```bash
# Full parameters
mashell --provider openai --url https://api.openai.com/v1 --key sk-... --model gpt-4o "refactor this code"

# Using environment variables (just provide prompt)
mashell "refactor this code to use async/await"

# Use local Ollama model
mashell --provider ollama --url http://localhost:11434 --model codellama "write a backup script"

# Use a saved profile
mashell --profile anthropic "why is my Python script failing?"

# Auto-approve mode for trusted tasks
mashell -y "update all npm packages in this project"
```

---

## 🔐 Permission System

MaShell asks for your approval before executing potentially impactful commands:

```
┌─────────────────────────────────────────────────────────┐
│  🔐 Permission Request                                  │
├─────────────────────────────────────────────────────────┤
│  Action: execute_command                                │
│  Command: rm -rf ./build                                │
│                                                         │
│  [y] Approve  [n] Deny  [e] Edit  [a] Always approve   │
└─────────────────────────────────────────────────────────┘
```

Permission levels:
- **Approve (y)** — Run this command once
- **Deny (n)** — Block this command
- **Edit (e)** — Modify the command before running
- **Always (a)** — Auto-approve this type of action for the session

---

## 🤖 For AI Assistants

> This section helps AI models understand how to invoke and interact with MaShell.

### How to Run MaShell

```bash
# With full parameters
mashell --provider <provider> --url <api-url> --key <api-key> --model <model> "your task"

# With environment variables set
mashell "your task description here"

# With a profile
mashell --profile <profile-name> "your task"

# Ollama (local, no key)
mashell --provider ollama --url http://localhost:11434 --model llama3 "your task"
```

### Capabilities

MaShell can:
1. **Execute shell commands** — Run any CLI command and parse output
2. **Read files** — Access file contents for context
3. **Write/Edit files** — Create or modify files
4. **Browse directories** — List and navigate filesystem
5. **Install tools** — Use package managers (pip, npm, brew, apt, etc.)
6. **Run long tasks** — Execute background processes and monitor output
7. **Chain operations** — Combine multiple steps to achieve complex goals

### Example Invocations

```bash
# Code task (with profile)
mashell --profile openai "create a FastAPI server with user authentication"

# Debug task (with local model)
mashell --provider ollama --url http://localhost:11434 --model codellama "find why tests are failing"

# System task
mashell "set up a Python virtual environment and install requirements.txt"

# File task  
mashell "find all TODO comments in the codebase and list them"
```

### Best Practices for Prompts

- Be specific about the desired outcome
- Mention relevant files or directories
- Specify constraints (e.g., "don't delete any files")
- For complex tasks, break into steps or let MaShell handle autonomously

---

## 🛣️ Roadmap

- [ ] Plugin system for custom tools
- [ ] Session history and resumption
- [ ] Multi-turn conversation memory
- [ ] Web browsing capabilities
- [ ] MCP (Model Context Protocol) support
- [ ] Team collaboration features

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

```bash
git clone https://github.com/yourusername/MaShell.git
cd MaShell
pip install -e ".[dev]"
pytest
```

---

## 📄 License

MaShell is released under the [GNU General Public License v3.0](LICENSE).

---

<p align="center">
  <b>Built with ❤️ for developers who live in the terminal</b>
</p>