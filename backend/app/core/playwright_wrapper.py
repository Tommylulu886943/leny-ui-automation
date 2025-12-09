"""
Playwright Browser Automation Wrapper

High-level wrapper around Playwright providing:
- Context management for browser lifecycle
- Action execution with automatic screenshots
- Integration with MultiStrategyLocator
- Error handling and retry mechanisms
"""

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator

import structlog
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.locator import (
    ElementConfig,
    MultiStrategyLocator,
    LocatorResult,
)

logger = structlog.get_logger()


class BrowserType(str, Enum):
    """Supported browser types."""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class ActionType(str, Enum):
    """Supported browser actions."""

    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    HOVER = "hover"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    ASSERT_TEXT = "assert_text"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_HIDDEN = "assert_hidden"
    ASSERT_VALUE = "assert_value"
    PRESS = "press"
    SCROLL = "scroll"


@dataclass
class ActionResult:
    """Result of a browser action execution."""

    success: bool
    action_type: ActionType
    element_name: str | None = None
    duration_ms: float = 0
    screenshot_base64: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserOptions:
    """Browser configuration options."""

    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    slow_mo: int = 0
    timeout: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: str | None = None
    locale: str = "en-US"
    timezone: str = "America/New_York"
    record_video: bool = False
    video_dir: str = "./videos"


class PlaywrightWrapper:
    """
    High-level Playwright wrapper for test automation.

    Usage:
        async with PlaywrightWrapper() as pw:
            await pw.navigate("https://example.com")
            await pw.click(login_button_config)
            await pw.fill(username_config, "user@example.com")
    """

    def __init__(self, options: BrowserOptions | None = None):
        self.options = options or BrowserOptions(
            headless=settings.playwright_headless,
            timeout=settings.playwright_timeout,
            slow_mo=settings.playwright_slow_mo,
        )
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._locator: MultiStrategyLocator | None = None
        self._action_history: list[ActionResult] = []

    @property
    def page(self) -> Page:
        """Get current page, raise if not initialized."""
        if self._page is None:
            raise RuntimeError("Browser not initialized. Use 'async with' context.")
        return self._page

    @property
    def locator(self) -> MultiStrategyLocator:
        """Get locator instance."""
        if self._locator is None:
            raise RuntimeError("Browser not initialized. Use 'async with' context.")
        return self._locator

    async def __aenter__(self) -> "PlaywrightWrapper":
        """Initialize browser on context enter."""
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up browser on context exit."""
        await self._cleanup()

    async def _initialize(self) -> None:
        """Initialize Playwright browser and context."""
        log = logger.bind(browser=self.options.browser_type.value)
        log.info("initializing_browser")

        self._playwright = await async_playwright().start()

        # Select browser type
        browser_launcher = getattr(self._playwright, self.options.browser_type.value)
        self._browser = await browser_launcher.launch(
            headless=self.options.headless,
            slow_mo=self.options.slow_mo,
        )

        # Create context with options
        context_options = {
            "viewport": {
                "width": self.options.viewport_width,
                "height": self.options.viewport_height,
            },
            "locale": self.options.locale,
            "timezone_id": self.options.timezone,
        }

        if self.options.user_agent:
            context_options["user_agent"] = self.options.user_agent

        if self.options.record_video:
            context_options["record_video_dir"] = self.options.video_dir

        self._context = await self._browser.new_context(**context_options)
        self._context.set_default_timeout(self.options.timeout)

        self._page = await self._context.new_page()
        self._locator = MultiStrategyLocator(self._page, timeout=5000)

        log.info("browser_initialized")

    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        logger.info("cleaning_up_browser")

        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    async def navigate(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        take_screenshot: bool = True,
    ) -> ActionResult:
        """
        Navigate to a URL.

        Args:
            url: Target URL
            wait_until: Wait condition (domcontentloaded, load, networkidle)
            take_screenshot: Whether to capture screenshot after navigation
        """
        import time

        start = time.time()
        log = logger.bind(url=url)

        try:
            await self.page.goto(url, wait_until=wait_until)
            duration_ms = (time.time() - start) * 1000

            screenshot = None
            if take_screenshot:
                screenshot = await self._take_screenshot()

            result = ActionResult(
                success=True,
                action_type=ActionType.NAVIGATE,
                duration_ms=duration_ms,
                screenshot_base64=screenshot,
                metadata={"url": url, "title": await self.page.title()},
            )

            log.info("navigation_complete", duration_ms=round(duration_ms, 2))
            self._action_history.append(result)
            return result

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            log.error("navigation_failed", error=str(e))

            result = ActionResult(
                success=False,
                action_type=ActionType.NAVIGATE,
                duration_ms=duration_ms,
                error_message=str(e),
                metadata={"url": url},
            )
            self._action_history.append(result)
            return result

    async def click(
        self,
        element: ElementConfig,
        take_screenshot: bool = True,
    ) -> ActionResult:
        """Click on an element."""
        return await self._execute_action(
            ActionType.CLICK,
            element,
            take_screenshot=take_screenshot,
        )

    async def fill(
        self,
        element: ElementConfig,
        value: str,
        take_screenshot: bool = True,
    ) -> ActionResult:
        """Fill an input field with a value."""
        return await self._execute_action(
            ActionType.FILL,
            element,
            value=value,
            take_screenshot=take_screenshot,
        )

    async def type_text(
        self,
        element: ElementConfig,
        text: str,
        delay: int = 50,
        take_screenshot: bool = True,
    ) -> ActionResult:
        """Type text character by character (useful for triggering input events)."""
        return await self._execute_action(
            ActionType.TYPE,
            element,
            value=text,
            delay=delay,
            take_screenshot=take_screenshot,
        )

    async def select_option(
        self,
        element: ElementConfig,
        value: str | list[str],
        take_screenshot: bool = True,
    ) -> ActionResult:
        """Select option(s) from a dropdown."""
        return await self._execute_action(
            ActionType.SELECT,
            element,
            value=value,
            take_screenshot=take_screenshot,
        )

    async def check(
        self,
        element: ElementConfig,
        take_screenshot: bool = True,
    ) -> ActionResult:
        """Check a checkbox."""
        return await self._execute_action(
            ActionType.CHECK,
            element,
            take_screenshot=take_screenshot,
        )

    async def hover(
        self,
        element: ElementConfig,
        take_screenshot: bool = True,
    ) -> ActionResult:
        """Hover over an element."""
        return await self._execute_action(
            ActionType.HOVER,
            element,
            take_screenshot=take_screenshot,
        )

    async def press_key(
        self,
        key: str,
        element: ElementConfig | None = None,
    ) -> ActionResult:
        """Press a keyboard key."""
        import time

        start = time.time()

        try:
            if element:
                loc_result = await self.locator.find_element(element)
                if not loc_result.success:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.PRESS,
                        element_name=element.name,
                        error_message=loc_result.error_message,
                    )
                await loc_result.locator.press(key)
            else:
                await self.page.keyboard.press(key)

            duration_ms = (time.time() - start) * 1000
            return ActionResult(
                success=True,
                action_type=ActionType.PRESS,
                element_name=element.name if element else None,
                duration_ms=duration_ms,
                metadata={"key": key},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.PRESS,
                error_message=str(e),
            )

    async def wait_for_element(
        self,
        element: ElementConfig,
        state: str = "visible",
        timeout: int | None = None,
    ) -> ActionResult:
        """Wait for an element to reach a specific state."""
        import time

        start = time.time()
        effective_timeout = timeout or self.options.timeout

        try:
            loc_result = await self.locator.find_element(
                element, timeout=effective_timeout
            )

            duration_ms = (time.time() - start) * 1000
            return ActionResult(
                success=loc_result.success,
                action_type=ActionType.WAIT,
                element_name=element.name,
                duration_ms=duration_ms,
                error_message=loc_result.error_message,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.WAIT,
                element_name=element.name,
                error_message=str(e),
            )

    async def assert_text(
        self,
        element: ElementConfig,
        expected_text: str,
        exact: bool = False,
    ) -> ActionResult:
        """Assert element contains expected text."""
        import time

        start = time.time()

        try:
            loc_result = await self.locator.find_element(element)
            if not loc_result.success:
                return ActionResult(
                    success=False,
                    action_type=ActionType.ASSERT_TEXT,
                    element_name=element.name,
                    error_message=loc_result.error_message,
                )

            actual_text = await loc_result.locator.text_content()
            duration_ms = (time.time() - start) * 1000

            if exact:
                matches = actual_text == expected_text
            else:
                matches = expected_text in (actual_text or "")

            return ActionResult(
                success=matches,
                action_type=ActionType.ASSERT_TEXT,
                element_name=element.name,
                duration_ms=duration_ms,
                error_message=None
                if matches
                else f"Expected '{expected_text}', got '{actual_text}'",
                metadata={"expected": expected_text, "actual": actual_text},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.ASSERT_TEXT,
                element_name=element.name,
                error_message=str(e),
            )

    async def assert_visible(
        self,
        element: ElementConfig,
    ) -> ActionResult:
        """Assert element is visible."""
        import time

        start = time.time()

        try:
            loc_result = await self.locator.find_element(element)
            duration_ms = (time.time() - start) * 1000

            return ActionResult(
                success=loc_result.success,
                action_type=ActionType.ASSERT_VISIBLE,
                element_name=element.name,
                duration_ms=duration_ms,
                error_message=loc_result.error_message,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.ASSERT_VISIBLE,
                element_name=element.name,
                error_message=str(e),
            )

    async def screenshot(
        self,
        full_page: bool = False,
        path: str | None = None,
    ) -> ActionResult:
        """Take a screenshot of the current page."""
        import time

        start = time.time()

        try:
            screenshot_bytes = await self.page.screenshot(full_page=full_page)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            if path:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(screenshot_bytes)

            duration_ms = (time.time() - start) * 1000

            return ActionResult(
                success=True,
                action_type=ActionType.SCREENSHOT,
                duration_ms=duration_ms,
                screenshot_base64=screenshot_b64,
                metadata={"full_page": full_page, "path": path},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.SCREENSHOT,
                error_message=str(e),
            )

    async def _execute_action(
        self,
        action_type: ActionType,
        element: ElementConfig,
        value: Any = None,
        take_screenshot: bool = True,
        **kwargs,
    ) -> ActionResult:
        """Execute a browser action on an element."""
        import time

        start = time.time()
        log = logger.bind(action=action_type.value, element=element.name)

        # Find element using multi-strategy locator
        loc_result = await self.locator.find_element(element)

        if not loc_result.success:
            log.error("element_not_found", error=loc_result.error_message)
            result = ActionResult(
                success=False,
                action_type=action_type,
                element_name=element.name,
                duration_ms=loc_result.duration_ms,
                error_message=loc_result.error_message,
            )
            self._action_history.append(result)
            return result

        try:
            # Execute the action
            match action_type:
                case ActionType.CLICK:
                    await loc_result.locator.click()
                case ActionType.FILL:
                    await loc_result.locator.fill(value)
                case ActionType.TYPE:
                    delay = kwargs.get("delay", 50)
                    await loc_result.locator.type(value, delay=delay)
                case ActionType.SELECT:
                    if isinstance(value, list):
                        await loc_result.locator.select_option(value=value)
                    else:
                        await loc_result.locator.select_option(value=value)
                case ActionType.CHECK:
                    await loc_result.locator.check()
                case ActionType.UNCHECK:
                    await loc_result.locator.uncheck()
                case ActionType.HOVER:
                    await loc_result.locator.hover()

            duration_ms = (time.time() - start) * 1000

            screenshot = None
            if take_screenshot:
                screenshot = await self._take_screenshot()

            result = ActionResult(
                success=True,
                action_type=action_type,
                element_name=element.name,
                duration_ms=duration_ms,
                screenshot_base64=screenshot,
                metadata={
                    "strategy_used": loc_result.strategy_used.value
                    if loc_result.strategy_used
                    else None,
                    "value": value if action_type in [ActionType.FILL, ActionType.TYPE] else None,
                },
            )

            log.info("action_complete", duration_ms=round(duration_ms, 2))
            self._action_history.append(result)
            return result

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            log.error("action_failed", error=str(e))

            result = ActionResult(
                success=False,
                action_type=action_type,
                element_name=element.name,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            self._action_history.append(result)
            return result

    async def _take_screenshot(self) -> str | None:
        """Take a screenshot and return base64 encoded string."""
        try:
            screenshot_bytes = await self.page.screenshot()
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception:
            return None

    def get_action_history(self) -> list[ActionResult]:
        """Get history of all executed actions."""
        return self._action_history.copy()

    async def get_page_info(self) -> dict:
        """Get current page information."""
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "viewport": self.page.viewport_size,
        }


@asynccontextmanager
async def create_browser(
    options: BrowserOptions | None = None,
) -> AsyncGenerator[PlaywrightWrapper, None]:
    """
    Convenience context manager for creating a browser session.

    Usage:
        async with create_browser() as browser:
            await browser.navigate("https://example.com")
    """
    wrapper = PlaywrightWrapper(options)
    try:
        await wrapper._initialize()
        yield wrapper
    finally:
        await wrapper._cleanup()
