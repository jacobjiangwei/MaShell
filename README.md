# MaShell

```
███╗   ███╗ █████╗ ███████╗██╗  ██╗███████╗██╗     ██╗     
████╗ ████║██╔══██╗██╔════╝██║  ██║██╔════╝██║     ██║     
██╔████╔██║███████║███████╗███████║█████╗  ██║     ██║     
██║╚██╔╝██║██╔══██║╚════██║██╔══██║██╔══╝  ██║     ██║     
██║ ╚═╝ ██║██║  ██║███████║██║  ██║███████╗███████╗███████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
```

**🐚 Your AI-Powered Command Line Assistant**

MaShell is an AI agent that lives in your terminal. It can run commands, write code, create projects, and accomplish complex tasks — all through natural conversation.

---

## ⚡ Quick Start

```bash
# Install (macOS/Linux)
pipx install mashell

# Or with pip (in a virtual environment)
pip install mashell

# Run (first time will guide you through setup)
mashell
```

> **Note**: On macOS, we recommend `pipx` for installing CLI tools. Install it with `brew install pipx` if you don't have it.

That's it! MaShell will walk you through connecting to your AI provider (OpenAI, Azure, Anthropic, or local Ollama).

---

## � What Can MaShell Do?

| Task | Example |
|------|---------|
| **Find files** | `"find the largest video on my computer"` |
| **Read documents** | `"read my resume.pdf and summarize it"` |
| **Edit Word files** | `"update my resume.docx with new job title"` |
| **Create projects** | `"build a Python web scraper from scratch"` |
| **Run code** | `"run this script and fix any errors"` |
| **Git operations** | `"commit all changes with a good message"` |
| **Web scraping** | `"scrape the HN front page for top stories"` |
| **Install tools** | `"install ffmpeg and convert video.mp4 to gif"` |
| **System tasks** | `"clean up files older than 30 days in Downloads"` |
| **Debug** | `"why is my Python script failing?"` |

### Native File Tools (No Shell Required)

MaShell has built-in tools for file operations — faster and no permission prompts for reading:

| Tool | Description | Permission |
|------|-------------|------------|
| `read_file` | Read any file (supports **PDF**, **Word .docx**, text) | Auto ✅ |
| `list_dir` | List directory contents with sizes | Auto ✅ |
| `search_files` | Search/grep across files | Auto ✅ |
| `write_file` | Write text files | Requires approval |
| `edit_docx` | Edit Word documents (find/replace, update paragraphs) | Requires approval |
| `shell` | Execute any shell command | Requires approval |
| `crawl` | Scrape web pages (JS rendering) | Requires approval |

---

## 🔧 Setup Options

### Option 1: Interactive Setup (Recommended)

Just run `mashell` — if no config exists, it will guide you:

```
🐚 MaShell Configuration Wizard

Step 1: Choose your LLM provider
  1. openai    - OpenAI API (GPT-4o, etc.)
  2. azure     - Azure OpenAI Service
  3. anthropic - Anthropic API (Claude)
  4. ollama    - Local Ollama (no API key needed)

Select provider: 2

Step 2: API Endpoint URL
Enter your Azure OpenAI endpoint: https://your-resource.openai.azure.com/

Step 3: API Key
Enter your API key: ********

Step 4: Model / Deployment Name
Deployment name: gpt-4o

✅ Configuration saved!
```

### Option 2: Command Line Arguments

```bash
# OpenAI
mashell --provider openai --url https://api.openai.com/v1 --key sk-... --model gpt-4o "your task"

# Azure OpenAI
mashell --provider azure --url https://your-resource.openai.azure.com --key xxx --model gpt-4o "your task"

# Anthropic
mashell --provider anthropic --url https://api.anthropic.com --key sk-ant-... --model claude-sonnet-4-20250514 "your task"

# Local Ollama (no key needed)
mashell --provider ollama --url http://localhost:11434 --model llama3 "your task"
```

### Option 3: Environment Variables

```bash
export MASHELL_PROVIDER="openai"
export MASHELL_URL="https://api.openai.com/v1"
export MASHELL_KEY="sk-..."
export MASHELL_MODEL="gpt-4o"

mashell "your task"
```

---

## � See It In Action

### Example 1: Find the Largest Video File

```
You: find biggest video file on my computer

💭 I'll check common video locations first...

▶ Run:
  $ du -sh ~/Documents ~/Downloads ~/Desktop ~/Movies

📋 Output:
342G    /Users/jacob/Documents
5.4G    /Users/jacob/Downloads
4.8G    /Users/jacob/Desktop
12K     /Users/jacob/Movies

💭 Documents is huge. Let me search for videos there...

▶ Run:
  $ find ~/Documents -type f \( -iname "*.mp4" -o -iname "*.mkv" \) -exec ls -lhS {} + | head -10

📋 Output:
-rw-r--r--  3.8G  Peaky Blinders S06E06.mkv
-rw-r--r--  3.7G  The.Brutalist.2024.mp4
-rw-r--r--  3.0G  Mission.Impossible.mkv
...

MaShell: Found it! The biggest video is:
**3.8G** — ~/Documents/Bitcomet/Peaky Blinders S06E06.mkv
```

### Example 2: Build a Project From Scratch

```
You: create a python project that can scrape web pages

💭 I'll set up a proper Python project structure...

▶ Run:
  $ mkdir -p python-scraper/{src,tests,outputs}
✓ Done

▶ Run:
  $ cat << 'EOF' > python-scraper/src/fetch.py
  import httpx
  def fetch(url): ...
  EOF
✓ Done

... (creates requirements.txt, README, .gitignore, venv, installs deps)

▶ Run:
  $ ./run.sh scrape https://example.com
📋 Output:
URL: https://example.com
Status: 200
Title: Example Domain

MaShell: Done! Created a Python web scraper at ./python-scraper

Try it: ./run.sh scrape https://example.com --out outputs/page.html
```

### Example 3: Scrape a Website

```
You: use it to scrape www.cnn.com and see what's happening today

▶ Run:
  $ ./run.sh scrape https://www.cnn.com --out outputs/cnn.html
📋 Output:
Status: 200
Title: Breaking News, Latest News and Videos | CNN
Saved: outputs/cnn.html

💭 Let me extract the headlines...

▶ Run:
  $ python -c "from bs4 import BeautifulSoup; ..."

MaShell: Today's top story: "Trump ramps up rhetoric on ICE despite calls for de-escalation"
```

---

## 🔐 Permission System

MaShell always asks before running commands:

```
╭─────────────────── 🔐 Permission Request ───────────────────╮
│                                                              │
│  Tool: shell                                                 │
│                                                              │
│  Command:                                                    │
│  $ rm -rf ./node_modules                                     │
│                                                              │
╰──────────────────────────────────────────────────────────────╯
   Approve   Deny   Edit   Always approve this session
Choice [y/n/e/a]: 
```

- **y** — Run this command
- **n** — Block it
- **e** — Edit the command first
- **A** — Auto-approve all commands this session (use with caution!)

---

## 💡 Tips

1. **Be specific** — "find large files" → "find video files larger than 1GB in Downloads"

2. **Let it explore** — MaShell thinks step-by-step like a human, checking results before deciding what to do next

3. **Auto-approve mode** — Use `mashell -y "task"` for trusted, quick tasks

4. **Interactive mode** — Just run `mashell` to chat back and forth

---

## 📦 Installation from Source

```bash
git clone https://github.com/anthropics/MaShell.git
cd MaShell
pip install -e .
```

For development:
```bash
python -m mashell "your task"
```

---

## 📄 License

GPL-3.0 — Free to use, modify, and share.

---

<p align="center">
  <b>Built for developers who live in the terminal 🐚</b>
</p>
