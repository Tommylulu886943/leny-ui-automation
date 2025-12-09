"""
Multi-Strategy Element Locator - MVP Core Feature

This module implements intelligent element location with fallback mechanisms.
Instead of relying on a single selector that may break, it tries multiple
strategies in order of stability.

Design Philosophy:
- v1 provides immediate value (more stable than pure XPath)
- Records success/failure data for future ML-based self-healing (v2)
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeout

logger = structlog.get_logger()


class LocatorStrategy(str, Enum):
    """
    Locator strategies ordered by stability.
    Higher priority strategies are tried first.
    """

    DATA_TESTID = "data-testid"  # Most stable - designed for testing
    ID = "id"  # Fast and usually unique
    ARIA_LABEL = "aria-label"  # Accessibility-friendly
    ARIA_ROLE = "role"  # Semantic role-based
    NAME = "name"  # Form element names
    PLACEHOLDER = "placeholder"  # Input placeholders
    CSS = "css"  # Flexible but needs good design
    TEXT = "text"  # Human-readable but may change
    XPATH = "xpath"  # Last resort - most brittle


@dataclass
class ElementConfig:
    """
    Configuration for locating an element using multiple strategies.
    """

    name: str  # Human-readable identifier
    strategies: dict[LocatorStrategy, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if "created" not in self.metadata:
            self.metadata["created"] = datetime.utcnow().isoformat()
        if "success_count" not in self.metadata:
            self.metadata["success_count"] = 0
        if "failure_count" not in self.metadata:
            self.metadata["failure_count"] = 0
        if "last_success_strategy" not in self.metadata:
            self.metadata["last_success_strategy"] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "strategies": {k.value: v for k, v in self.strategies.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ElementConfig":
        strategies = {
            LocatorStrategy(k): v for k, v in data.get("strategies", {}).items()
        }
        return cls(
            name=data["name"],
            strategies=strategies,
            metadata=data.get("metadata", {}),
        )


@dataclass
class LocatorResult:
    """Result of a locate operation."""

    success: bool
    locator: Locator | None = None
    strategy_used: LocatorStrategy | None = None
    strategies_tried: list[LocatorStrategy] = field(default_factory=list)
    error_message: str | None = None
    duration_ms: float = 0


class ElementNotFoundError(Exception):
    """Raised when element cannot be found with any strategy."""

    def __init__(
        self,
        message: str,
        element_name: str,
        tried_strategies: list[LocatorStrategy],
        page_url: str | None = None,
    ):
        super().__init__(message)
        self.element_name = element_name
        self.tried_strategies = tried_strategies
        self.page_url = page_url


class MultiStrategyLocator:
    """
    MVP version of multi-strategy element locator.

    This locator tries multiple strategies in order of stability,
    providing resilience against UI changes while collecting data
    for future ML-based self-healing.
    """

    # Strategy priority order - most stable first
    STRATEGY_PRIORITY = [
        (LocatorStrategy.DATA_TESTID, "Most stable - designed for testing"),
        (LocatorStrategy.ID, "Fast and usually unique"),
        (LocatorStrategy.ARIA_LABEL, "Accessibility-friendly"),
        (LocatorStrategy.ARIA_ROLE, "Semantic role-based"),
        (LocatorStrategy.NAME, "Form element names"),
        (LocatorStrategy.PLACEHOLDER, "Input placeholders"),
        (LocatorStrategy.CSS, "Flexible but needs good design"),
        (LocatorStrategy.TEXT, "Human-readable but may change"),
        (LocatorStrategy.XPATH, "Last resort - most brittle"),
    ]

    def __init__(self, page: Page, timeout: int = 5000):
        """
        Initialize the multi-strategy locator.

        Args:
            page: Playwright Page instance
            timeout: Timeout in milliseconds for each strategy attempt
        """
        self.page = page
        self.timeout = timeout
        self._location_history: list[dict] = []

    async def find_element(
        self,
        element_config: ElementConfig,
        timeout: int | None = None,
    ) -> LocatorResult:
        """
        Find an element using multiple strategies in priority order.

        Args:
            element_config: Configuration with multiple locator strategies
            timeout: Optional override for timeout

        Returns:
            LocatorResult with the found element or error details
        """
        import time

        start_time = time.time()
        effective_timeout = timeout or self.timeout
        strategies_tried = []

        log = logger.bind(element=element_config.name)

        # Try strategies in priority order
        for strategy, description in self.STRATEGY_PRIORITY:
            if strategy not in element_config.strategies:
                continue

            selector_value = element_config.strategies[strategy]
            strategies_tried.append(strategy)

            try:
                locator = await self._locate_by_strategy(
                    strategy, selector_value, effective_timeout
                )

                if locator:
                    duration_ms = (time.time() - start_time) * 1000

                    # Record success for future ML training
                    self._record_success(element_config, strategy)

                    log.info(
                        "element_found",
                        strategy=strategy.value,
                        duration_ms=round(duration_ms, 2),
                    )

                    return LocatorResult(
                        success=True,
                        locator=locator,
                        strategy_used=strategy,
                        strategies_tried=strategies_tried,
                        duration_ms=duration_ms,
                    )

            except PlaywrightTimeout:
                log.debug(
                    "strategy_timeout",
                    strategy=strategy.value,
                    selector=selector_value,
                )
                continue
            except Exception as e:
                log.warning(
                    "strategy_error",
                    strategy=strategy.value,
                    error=str(e),
                )
                continue

        # All strategies failed
        duration_ms = (time.time() - start_time) * 1000
        self._record_failure(element_config, strategies_tried)

        error_msg = (
            f"Cannot locate element '{element_config.name}' "
            f"after trying {len(strategies_tried)} strategies"
        )

        log.error(
            "element_not_found",
            strategies_tried=[s.value for s in strategies_tried],
            duration_ms=round(duration_ms, 2),
        )

        return LocatorResult(
            success=False,
            strategies_tried=strategies_tried,
            error_message=error_msg,
            duration_ms=duration_ms,
        )

    async def _locate_by_strategy(
        self,
        strategy: LocatorStrategy,
        value: str,
        timeout: int,
    ) -> Locator | None:
        """
        Locate element using a specific strategy.
        """
        locator: Locator | None = None

        match strategy:
            case LocatorStrategy.DATA_TESTID:
                locator = self.page.get_by_test_id(value)

            case LocatorStrategy.ID:
                locator = self.page.locator(f"#{value}")

            case LocatorStrategy.ARIA_LABEL:
                locator = self.page.get_by_label(value)

            case LocatorStrategy.ARIA_ROLE:
                # Value format: "role:name" e.g., "button:Submit"
                if ":" in value:
                    role, name = value.split(":", 1)
                    locator = self.page.get_by_role(role, name=name)
                else:
                    locator = self.page.get_by_role(value)

            case LocatorStrategy.NAME:
                locator = self.page.locator(f"[name='{value}']")

            case LocatorStrategy.PLACEHOLDER:
                locator = self.page.get_by_placeholder(value)

            case LocatorStrategy.CSS:
                locator = self.page.locator(value)

            case LocatorStrategy.TEXT:
                locator = self.page.get_by_text(value, exact=False)

            case LocatorStrategy.XPATH:
                locator = self.page.locator(f"xpath={value}")

        if locator:
            # Wait for element and verify it's visible
            await locator.first.wait_for(state="visible", timeout=timeout)
            return locator.first

        return None

    def _record_success(
        self,
        config: ElementConfig,
        strategy: LocatorStrategy,
    ) -> None:
        """
        Record successful location for future ML training.
        """
        config.metadata["success_count"] = config.metadata.get("success_count", 0) + 1
        config.metadata["last_success"] = datetime.utcnow().isoformat()
        config.metadata["last_success_strategy"] = strategy.value

        # Store in history for analytics
        self._location_history.append(
            {
                "element": config.name,
                "strategy": strategy.value,
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
                "page_url": self.page.url,
            }
        )

    def _record_failure(
        self,
        config: ElementConfig,
        tried_strategies: list[LocatorStrategy],
    ) -> None:
        """
        Record failed location attempt for debugging and ML training.
        """
        config.metadata["failure_count"] = config.metadata.get("failure_count", 0) + 1
        config.metadata["last_failure"] = datetime.utcnow().isoformat()

        self._location_history.append(
            {
                "element": config.name,
                "strategies_tried": [s.value for s in tried_strategies],
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
                "page_url": self.page.url,
            }
        )

    async def capture_page_state(self) -> dict:
        """
        Capture current page state for debugging failed locations.
        """
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "viewport": self.page.viewport_size,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_location_history(self) -> list[dict]:
        """Get location history for analytics."""
        return self._location_history.copy()

    @staticmethod
    def create_element_config(
        name: str,
        data_testid: str | None = None,
        id: str | None = None,
        aria_label: str | None = None,
        role: str | None = None,
        css: str | None = None,
        text: str | None = None,
        xpath: str | None = None,
        placeholder: str | None = None,
        element_name: str | None = None,
    ) -> ElementConfig:
        """
        Convenience method to create element configuration.

        Usage:
            config = MultiStrategyLocator.create_element_config(
                name="login_button",
                data_testid="login-submit",
                id="login-btn",
                css="form.login button[type='submit']",
                text="Login"
            )
        """
        strategies = {}

        if data_testid:
            strategies[LocatorStrategy.DATA_TESTID] = data_testid
        if id:
            strategies[LocatorStrategy.ID] = id
        if aria_label:
            strategies[LocatorStrategy.ARIA_LABEL] = aria_label
        if role:
            strategies[LocatorStrategy.ARIA_ROLE] = role
        if element_name:
            strategies[LocatorStrategy.NAME] = element_name
        if placeholder:
            strategies[LocatorStrategy.PLACEHOLDER] = placeholder
        if css:
            strategies[LocatorStrategy.CSS] = css
        if text:
            strategies[LocatorStrategy.TEXT] = text
        if xpath:
            strategies[LocatorStrategy.XPATH] = xpath

        return ElementConfig(name=name, strategies=strategies)


def generate_element_hash(element_config: ElementConfig) -> str:
    """Generate a unique hash for an element configuration."""
    content = json.dumps(element_config.to_dict(), sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:12]
