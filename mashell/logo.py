"""ASCII art logo display with running horses animation."""

import shutil
import sys
import time

from rich.console import Console
from rich.text import Text

# The good horse from before - 2 frames for running animation (full size!)
HORSE_FRAME_1 = [
    r"                   >>\.                ",
    r"                  /_  )`.              ",
    r"                 /  _)`^)`.   _.---. _ ",
    '                (_,\' \\  `^-)""      `.\\',
    r"                      |  | \           ",
    r"                      \              / |",
    r"                     / \  /.___.'\  (\ (_",
    r"                    < ,'||     \ |`. \`-'",
    r"                     \\ ()      )|  )/  ",
    r"                     |_>|>     /_] //   ",
    r"                       /_]       /_]    ",
]

HORSE_FRAME_2 = [
    r"                   >>\.                ",
    r"                  /_  )`.              ",
    r"                 /  _)`^)`.   _.---. _ ",
    '                (_,\' \\  `^-)""      `.\\',
    r"                      |  | \           ",
    r"                      \              / |",
    r"                     / \  /.___.'\  (\ (_",
    r"                    <  '||     \ |`. \`-'",
    r"                      \()      )|   )/  ",
    r"                     |>/_]    /_]| //   ",
    r"                       /_]       /_]    ",
]

LOGO = r"""
███╗   ███╗ █████╗ ███████╗██╗  ██╗███████╗██╗     ██╗
████╗ ████║██╔══██╗██╔════╝██║  ██║██╔════╝██║     ██║
██╔████╔██║███████║███████╗███████║█████╗  ██║     ██║
██║╚██╔╝██║██╔══██║╚════██║██╔══██║██╔══╝  ██║     ██║
██║ ╚═╝ ██║██║  ██║███████║██║  ██║███████╗███████╗███████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
"""

LOGO_WITH_HORSE = r"""
                   >>\.
                  /_  )`.
                 /  _)`^)`.   _.---. _
                (_,' \  `^-)""      `.\
                      |  | \
                      \              / |
                     / \  /.___.'\  (\ (_
                    < ,"||     \ |`. \`-'
                     \\ ()      )|  )/
                     |_>|>     /_] //
                       /_]       /_]

███╗   ███╗ █████╗ ███████╗██╗  ██╗███████╗██╗     ██╗
████╗ ████║██╔══██╗██╔════╝██║  ██║██╔════╝██║     ██║
██╔████╔██║███████║███████╗███████║█████╗  ██║     ██║
██║╚██╔╝██║██╔══██║╚════██║██╔══██║██╔══╝  ██║     ██║
██║ ╚═╝ ██║██║  ██║███████║██║  ██║███████╗███████╗███████╗
╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
"""

TAGLINE = "🐴 Your AI-Powered Command Line Assistant"


def clear_screen_area(lines: int) -> None:
    """Move cursor up and clear lines."""
    for _ in range(lines):
        sys.stdout.write("\033[F")  # Move up
        sys.stdout.write("\033[K")  # Clear line


def display_logo(console: Console | None = None, animate: bool = True) -> None:
    """Display the MaShell logo with optional stampede animation."""
    if console is None:
        console = Console()

    console.print()

    if animate and console.is_terminal:
        # Get terminal width
        term_width = shutil.get_terminal_size().columns

        # Horse stampede animation - horses running from right to left
        horse_frames = [HORSE_FRAME_1, HORSE_FRAME_2]
        horse_width = len(HORSE_FRAME_1[0])
        horse_height = len(HORSE_FRAME_1)
        num_horses = 3  # Number of horses in the stampede
        spacing = 45  # Space between horses (wider for bigger horses)

        # Start position (off screen to the right)
        start_pos = term_width + 10
        end_pos = -spacing * num_horses - horse_width - 10

        # Animation frames
        frame_count = 0

        # Create empty lines for animation area
        for _ in range(horse_height + 1):
            console.print()

        # Run the stampede
        pos = start_pos
        speed = 5  # Pixels per frame

        while pos > end_pos:
            # Clear the animation area
            clear_screen_area(horse_height + 1)

            # Build the frame with multiple horses
            lines = ["" for _ in range(horse_height)]

            for horse_idx in range(num_horses):
                horse_pos = pos + horse_idx * spacing

                # Choose animation frame (alternate for running effect)
                frame_idx = (frame_count + horse_idx) % 2
                horse = horse_frames[frame_idx]

                for line_idx, horse_line in enumerate(horse):
                    if -horse_width < horse_pos < term_width + horse_width:
                        # Calculate where to place this horse in the line
                        current_len = len(lines[line_idx])
                        if horse_pos > current_len:
                            # Add padding
                            lines[line_idx] += " " * (horse_pos - current_len)

                        # Clip horse to visible area
                        visible_start = max(0, -horse_pos)
                        visible_end = min(horse_width, term_width - horse_pos)
                        if visible_start < visible_end:
                            if horse_pos < 0:
                                lines[line_idx] = horse_line[visible_start:visible_end]
                            else:
                                lines[line_idx] += horse_line[visible_start:visible_end]

            # Print the frame
            for line in lines:
                console.print(line[:term_width], style="bold cyan")
            console.print()  # Extra line for spacing

            sys.stdout.flush()
            time.sleep(0.06)

            pos -= speed
            frame_count += 1

        # Clear the horse area
        clear_screen_area(horse_height + 1)

        # Small pause before text appears
        time.sleep(0.2)

        # Now reveal MASHELL text with a typing effect
        logo_lines = LOGO.strip().split("\n")

        # Print empty lines first
        for _ in range(len(logo_lines)):
            console.print()

        # Reveal from left to right
        max_width = max(len(line) for line in logo_lines)

        for reveal_pos in range(0, max_width + 1, 4):  # Reveal 4 chars at a time
            clear_screen_area(len(logo_lines))
            for line in logo_lines:
                revealed = line[:reveal_pos]
                console.print(Text(revealed, style="bold cyan"))
            sys.stdout.flush()
            time.sleep(0.02)

        console.print()
    else:
        # No animation - just show the final logo
        logo_text = Text(LOGO_WITH_HORSE, style="bold cyan")
        console.print(logo_text)

    console.print(f"  {TAGLINE}", style="dim")
    console.print()
