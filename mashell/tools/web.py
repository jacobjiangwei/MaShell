"""Web crawling tools using Crawl4AI."""

from typing import Any

from mashell.tools.base import BaseTool, ToolResult


class CrawlTool(BaseTool):
    """Crawl web pages and extract LLM-friendly content using Crawl4AI."""

    name = "crawl"
    description = """Crawl a web page and extract clean, LLM-ready Markdown content.

## When to Use
- Extract content from any website as clean Markdown
- Scrape news articles, documentation, product pages
- Handle JavaScript-heavy sites (uses real browser)
- Get structured data from web pages

## Examples
- crawl("https://github.com/trending") - Get trending repos
- crawl("https://news.ycombinator.com") - Get HN front page
- crawl("https://example.com/article", extract_links=True) - Get content + links

## Output
Returns clean Markdown text optimized for LLM processing.

## Notes
- Uses headless Chromium browser
- Handles JavaScript rendering automatically
- Returns clean Markdown, not raw HTML
- Removes popups and overlay elements"""

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to crawl"},
            "extract_links": {
                "type": "boolean",
                "description": "Also extract all links from the page (default: false)",
            },
            "wait_for": {
                "type": "string",
                "description": "CSS selector to wait for before extracting (for dynamic content)",
            },
            "css_selector": {
                "type": "string",
                "description": "Focus on specific CSS selector (e.g. '.main-content')",
            },
            "screenshot": {
                "type": "boolean",
                "description": "Take a screenshot of the page (default: false)",
            },
        },
        "required": ["url"],
    }

    requires_permission = True
    permission_level = "always_ask"

    async def execute(
        self,
        url: str,
        extract_links: bool = False,
        wait_for: str | None = None,
        css_selector: str | None = None,
        screenshot: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Crawl a web page using Crawl4AI."""
        try:
            import importlib.util

            if importlib.util.find_spec("crawl4ai") is None:
                raise ImportError("crawl4ai not found")
        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="crawl4ai not installed. Run: pip install crawl4ai && crawl4ai-setup",
            )

        return await self._crawl_with_crawl4ai(
            url, extract_links, wait_for, css_selector, screenshot
        )

    async def _crawl_with_crawl4ai(
        self,
        url: str,
        extract_links: bool,
        wait_for: str | None,
        css_selector: str | None,
        screenshot: bool,
    ) -> ToolResult:
        """Crawl using Crawl4AI (full browser rendering)."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

        # Configure browser
        browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
        )

        # Configure crawler
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            remove_overlay_elements=True,
            wait_for=wait_for,
            css_selector=css_selector,
            screenshot=screenshot,
        )

        # Run crawler
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)

        if not result.success:
            return ToolResult(
                success=False,
                output="",
                error=f"Crawl failed: {result.error_message or 'Unknown error'}",
            )

        return self._format_crawl4ai_result(result, url, extract_links)

    def _format_crawl4ai_result(self, result: Any, url: str, extract_links: bool) -> ToolResult:
        """Format Crawl4AI result."""
        output_parts = []

        # Add title if available
        title = result.metadata.get("title", "") if result.metadata else ""
        if title:
            output_parts.append(f"# {title}\n")

        # Add markdown content
        markdown_content = result.markdown
        if markdown_content:
            if hasattr(markdown_content, "raw_markdown"):
                content = markdown_content.raw_markdown
            elif hasattr(markdown_content, "fit_markdown"):
                content = markdown_content.fit_markdown
            else:
                content = str(markdown_content)

            content = content.strip()
            if len(content) > 50000:
                content = content[:50000] + "\n\n... (truncated)"
            output_parts.append(content)

        # Add links if requested
        if extract_links and result.links:
            links_section = "\n\n---\n## Extracted Links\n"
            internal = result.links.get("internal", [])
            external = result.links.get("external", [])

            if internal:
                links_section += f"\n### Internal Links ({len(internal)} found)\n"
                for link in internal[:30]:
                    if isinstance(link, dict):
                        href = link.get("href", "")
                        text = link.get("text", "").strip()[:50]
                    else:
                        href = str(link)
                        text = ""
                    links_section += f"- [{text or href}]({href})\n"

            if external:
                links_section += f"\n### External Links ({len(external)} found)\n"
                for link in external[:20]:
                    if isinstance(link, dict):
                        href = link.get("href", "")
                        text = link.get("text", "").strip()[:50]
                    else:
                        href = str(link)
                        text = ""
                    links_section += f"- [{text or href}]({href})\n"

            output_parts.append(links_section)

        # Add media info
        if result.media:
            images = result.media.get("images", [])
            videos = result.media.get("videos", [])
            if images or videos:
                output_parts.append(f"\n---\n*Media: {len(images)} images, {len(videos)} videos*")

        output = "\n".join(output_parts)

        if not output.strip():
            output = f"Page crawled successfully but no content extracted. URL: {url}"

        return ToolResult(
            success=True,
            output=output,
        )


class FetchPageTool(BaseTool):
    """Simple HTTP fetch for static pages (no JavaScript)."""

    name = "fetch_page"
    description = """Fetch a web page using simple HTTP request (no JavaScript).

## When to Use
- Quick fetch of static HTML pages
- API endpoints that return JSON/text
- When you don't need JavaScript rendering
- Faster alternative to crawl() for simple pages

## When NOT to Use
- JavaScript-heavy sites (use crawl instead)
- Sites with anti-bot protection
- Need to interact with forms/buttons

## Examples
- fetch_page("https://api.github.com/users/octocat")
- fetch_page("https://httpbin.org/json")"""

    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds (default: 30)",
            },
        },
        "required": ["url"],
    }

    requires_permission = True
    permission_level = "always_ask"

    async def execute(
        self,
        url: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> ToolResult:
        """Fetch a web page."""
        try:
            import httpx

            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, headers={"User-Agent": ua}
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")

                if "json" in content_type:
                    # Return formatted JSON
                    import json

                    try:
                        data = response.json()
                        return ToolResult(
                            success=True,
                            output=json.dumps(data, indent=2, ensure_ascii=False),
                        )
                    except Exception:
                        pass

                # Return text content
                text = response.text

                # Try to extract main text from HTML
                if "html" in content_type:
                    text = self._extract_text_from_html(text)

                # Truncate if too long
                if len(text) > 50000:
                    text = text[:50000] + "\n\n... (truncated)"

                return ToolResult(
                    success=True,
                    output=text,
                )

        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                output="",
                error=f"Request timed out after {timeout}s",
            )
        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Fetch error: {str(e)}",
            )

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from HTML."""
        try:
            # Try BeautifulSoup if available
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Get text
            text = soup.get_text(separator="\n", strip=True)

            # Clean up multiple newlines
            import re

            text = re.sub(r"\n{3,}", "\n\n", text)

            return text

        except ImportError:
            # Fallback: basic regex extraction
            import re

            # Remove script/style tags
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
            # Remove all other tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Decode HTML entities
            import html as html_module

            text = html_module.unescape(text)
            # Clean whitespace
            text = re.sub(r"\s+", " ", text).strip()
            return text
