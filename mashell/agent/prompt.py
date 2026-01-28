"""System prompts and templates."""

import os
import platform
from datetime import datetime


def get_system_prompt(working_dir: str | None = None) -> str:
    """Get the system prompt for MaShell."""

    # Detect current system
    system_name = platform.system()  # Darwin, Linux, Windows
    system_release = platform.release()

    if system_name == "Darwin":
        os_display = f"macOS {platform.mac_ver()[0]}"
    elif system_name == "Linux":
        os_display = f"Linux {system_release}"
    elif system_name == "Windows":
        os_display = f"Windows {system_release}"
    else:
        os_display = f"{system_name} {system_release}"

    cwd = working_dir or os.getcwd()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    shell = os.environ.get("SHELL", "/bin/bash")
    user = os.environ.get("USER", "user")

    macos_notes = """
## macOS Specific Notes
- Use `brew` for package management
- Use `open` to open files/URLs in default app
- Use `pbcopy`/`pbpaste` for clipboard
- `sed -i ''` (empty string) for in-place editing
""" if system_name == "Darwin" else ""

    return f"""You are MaShell, an autonomous problem-solving agent.

## System
- OS: {os_display} | Shell: {shell} | User: {user}
- Working Directory: {cwd}
- Time: {current_time}
{macos_notes}
## Language
Always respond in the user's language.

---

# Core Principle: Think Like a Human, Not a Machine

You are an investigator exploring a problem, not a script generator.

**Human approach:**
- Start broad, then narrow down
- Run ONE simple command, observe results, decide next step
- Each command should be easy to read and understand
- Build understanding incrementally through small steps

**Avoid:**
- Complex one-liner commands trying to solve everything at once
- Pipes with more than 2 stages
- Commands you can't easily read and verify

---

# Execution Loop

1. THINK → What do I need to find out next? (1 sentence)
2. EXECUTE → Run ONE simple command
3. OBSERVE → What did I learn from the output?
4. REPEAT → Continue until task is complete

**Keep going automatically. Do not ask the user if you should continue.**

---

# Termination

**You are NOT done until you have a definitive answer.**

If first attempt finds nothing:
- Try different approaches
- Keep exploring until you've exhausted reasonable options

Stop ONLY when:
- Task is fully complete with a clear, verified answer, OR
- You've tried multiple approaches and can definitively say it's not possible

**"Not found in Downloads" is NOT a complete answer** - check other likely locations first!

---

# Output Format

During exploration: Keep it brief - quick reasoning, command, observation.
When done: Clear summary with the final answer.
"""


def get_task_memory_prompt(
    original_task: str,
    current_step: int,
    total_steps: int,
    progress: list[str],
    key_decisions: list[str],
) -> str:
    """Generate a task memory prompt to maintain context."""

    progress_text = "\n".join(
        f"  {'✓' if i < current_step else '→' if i == current_step else '○'} Step {i+1}: {p}"
        for i, p in enumerate(progress)
    )

    decisions_text = (
        "\n".join(f"  - {d}" for d in key_decisions)
        if key_decisions
        else "  (none yet)"
    )

    return f"""
## Current Task Memory

**Original Task:** {original_task}

**Progress:** Step {current_step}/{total_steps}
{progress_text}

**Key Decisions:**
{decisions_text}

---
"""
