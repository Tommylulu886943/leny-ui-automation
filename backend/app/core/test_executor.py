"""
Test Execution Engine

This module orchestrates test execution:
1. Parses test cases (from LLM or manual input)
2. Executes steps using PlaywrightWrapper
3. Collects results, screenshots, and timing data
4. Generates execution reports
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import structlog

from app.core.locator import ElementConfig, MultiStrategyLocator
from app.core.playwright_wrapper import (
    ActionResult,
    ActionType,
    BrowserOptions,
    PlaywrightWrapper,
)
from app.core.llm_service import (
    TestCase,
    TestStep,
    TestStepType,
    ElementLocator,
)

logger = structlog.get_logger()


class ExecutionStatus(str, Enum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepResult:
    """Result of a single step execution."""

    step_number: int
    step_description: str
    status: ExecutionStatus
    action_type: str
    duration_ms: float = 0
    screenshot_base64: str | None = None
    error_message: str | None = None
    element_name: str | None = None
    locator_strategy_used: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Result of a complete test execution."""

    test_id: str
    test_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float = 0
    step_results: list[StepResult] = field(default_factory=list)
    setup_results: list[StepResult] = field(default_factory=list)
    teardown_results: list[StepResult] = field(default_factory=list)
    error_message: str | None = None
    final_screenshot: str | None = None
    page_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_steps(self) -> int:
        return sum(1 for r in self.step_results if r.status == ExecutionStatus.PASSED)

    @property
    def failed_steps(self) -> int:
        return sum(1 for r in self.step_results if r.status == ExecutionStatus.FAILED)

    @property
    def total_steps(self) -> int:
        return len(self.step_results)

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "total_steps": self.total_steps,
            "step_results": [
                {
                    "step_number": r.step_number,
                    "description": r.step_description,
                    "status": r.status.value,
                    "action_type": r.action_type,
                    "duration_ms": r.duration_ms,
                    "error_message": r.error_message,
                    "element_name": r.element_name,
                    "has_screenshot": r.screenshot_base64 is not None,
                }
                for r in self.step_results
            ],
            "error_message": self.error_message,
            "page_url": self.page_url,
            "metadata": self.metadata,
        }


class TestExecutor:
    """
    Orchestrates test case execution.

    Usage:
        executor = TestExecutor()
        result = await executor.execute(test_case)
    """

    def __init__(
        self,
        browser_options: BrowserOptions | None = None,
        on_step_complete: Callable[[StepResult], None] | None = None,
    ):
        """
        Initialize test executor.

        Args:
            browser_options: Browser configuration
            on_step_complete: Callback for real-time step updates
        """
        self.browser_options = browser_options or BrowserOptions()
        self.on_step_complete = on_step_complete

    def _convert_element_locator(self, locator: ElementLocator) -> ElementConfig:
        """Convert LLM ElementLocator to core ElementConfig."""
        return MultiStrategyLocator.create_element_config(
            name=locator.name,
            data_testid=locator.data_testid,
            id=locator.id,
            aria_label=locator.aria_label,
            role=locator.role,
            css=locator.css,
            text=locator.text,
            xpath=locator.xpath,
            placeholder=locator.placeholder,
        )

    async def execute(
        self,
        test_case: TestCase | dict,
        stop_on_failure: bool = True,
    ) -> TestResult:
        """
        Execute a test case.

        Args:
            test_case: Test case to execute (TestCase object or dict)
            stop_on_failure: Whether to stop execution on first failure

        Returns:
            TestResult with execution details
        """
        # Convert dict to TestCase if needed
        if isinstance(test_case, dict):
            test_case = TestCase(**test_case)

        test_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        log = logger.bind(test_id=test_id, test_name=test_case.name)
        log.info("test_execution_started")

        result = TestResult(
            test_id=test_id,
            test_name=test_case.name,
            status=ExecutionStatus.RUNNING,
            started_at=started_at,
            metadata={"description": test_case.description, "tags": test_case.tags},
        )

        try:
            async with PlaywrightWrapper(self.browser_options) as browser:
                # Execute setup steps
                if test_case.setup_steps:
                    log.info("executing_setup", step_count=len(test_case.setup_steps))
                    for step in test_case.setup_steps:
                        step_result = await self._execute_step(browser, step)
                        result.setup_results.append(step_result)

                        if step_result.status == ExecutionStatus.FAILED and stop_on_failure:
                            log.warning("setup_failed", step=step.step_number)
                            result.status = ExecutionStatus.FAILED
                            result.error_message = f"Setup failed at step {step.step_number}"
                            break

                # Execute main test steps
                if result.status != ExecutionStatus.FAILED:
                    log.info("executing_main_steps", step_count=len(test_case.steps))

                    for step in test_case.steps:
                        step_result = await self._execute_step(browser, step)
                        result.step_results.append(step_result)

                        if self.on_step_complete:
                            self.on_step_complete(step_result)

                        if step_result.status == ExecutionStatus.FAILED:
                            if stop_on_failure:
                                log.warning("step_failed", step=step.step_number)
                                result.status = ExecutionStatus.FAILED
                                result.error_message = step_result.error_message
                                break

                # Execute teardown (always run)
                if test_case.teardown_steps:
                    log.info("executing_teardown", step_count=len(test_case.teardown_steps))
                    for step in test_case.teardown_steps:
                        step_result = await self._execute_step(browser, step)
                        result.teardown_results.append(step_result)

                # Capture final state
                result.page_url = browser.page.url
                screenshot_result = await browser.screenshot()
                if screenshot_result.success:
                    result.final_screenshot = screenshot_result.screenshot_base64

                # Determine final status
                if result.status == ExecutionStatus.RUNNING:
                    if all(r.status == ExecutionStatus.PASSED for r in result.step_results):
                        result.status = ExecutionStatus.PASSED
                    else:
                        result.status = ExecutionStatus.FAILED

        except Exception as e:
            log.exception("test_execution_error", error=str(e))
            result.status = ExecutionStatus.ERROR
            result.error_message = str(e)

        # Finalize result
        result.completed_at = datetime.utcnow()
        result.duration_ms = (result.completed_at - started_at).total_seconds() * 1000

        log.info(
            "test_execution_completed",
            status=result.status.value,
            duration_ms=round(result.duration_ms, 2),
            passed=result.passed_steps,
            failed=result.failed_steps,
        )

        return result

    async def _execute_step(
        self,
        browser: PlaywrightWrapper,
        step: TestStep,
    ) -> StepResult:
        """Execute a single test step."""
        import time

        start = time.time()
        log = logger.bind(step=step.step_number, action=step.action.value)

        try:
            action_result = await self._dispatch_action(browser, step)

            duration_ms = (time.time() - start) * 1000

            step_result = StepResult(
                step_number=step.step_number,
                step_description=step.description,
                status=ExecutionStatus.PASSED if action_result.success else ExecutionStatus.FAILED,
                action_type=step.action.value,
                duration_ms=duration_ms,
                screenshot_base64=action_result.screenshot_base64,
                error_message=action_result.error_message,
                element_name=action_result.element_name,
                locator_strategy_used=action_result.metadata.get("strategy_used"),
                metadata=action_result.metadata,
            )

            log.info(
                "step_executed",
                status=step_result.status.value,
                duration_ms=round(duration_ms, 2),
            )

            return step_result

        except Exception as e:
            log.exception("step_error", error=str(e))
            return StepResult(
                step_number=step.step_number,
                step_description=step.description,
                status=ExecutionStatus.ERROR,
                action_type=step.action.value,
                duration_ms=(time.time() - start) * 1000,
                error_message=str(e),
            )

    async def _dispatch_action(
        self,
        browser: PlaywrightWrapper,
        step: TestStep,
    ) -> ActionResult:
        """Dispatch step to appropriate browser action."""
        element_config = None
        if step.element:
            element_config = self._convert_element_locator(step.element)

        match step.action:
            case TestStepType.NAVIGATE:
                url = step.value or step.metadata.get("url", "")
                return await browser.navigate(url)

            case TestStepType.CLICK:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.CLICK,
                        error_message="Element required for click action",
                    )
                return await browser.click(element_config)

            case TestStepType.FILL:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.FILL,
                        error_message="Element required for fill action",
                    )
                return await browser.fill(element_config, step.value or "")

            case TestStepType.TYPE:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.TYPE,
                        error_message="Element required for type action",
                    )
                return await browser.type_text(element_config, step.value or "")

            case TestStepType.SELECT:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.SELECT,
                        error_message="Element required for select action",
                    )
                return await browser.select_option(element_config, step.value or "")

            case TestStepType.CHECK:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.CHECK,
                        error_message="Element required for check action",
                    )
                return await browser.check(element_config)

            case TestStepType.HOVER:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.HOVER,
                        error_message="Element required for hover action",
                    )
                return await browser.hover(element_config)

            case TestStepType.WAIT:
                if element_config:
                    return await browser.wait_for_element(
                        element_config,
                        timeout=step.timeout,
                    )
                else:
                    # Wait for a duration
                    wait_time = step.timeout or 1000
                    await asyncio.sleep(wait_time / 1000)
                    return ActionResult(
                        success=True,
                        action_type=ActionType.WAIT,
                        metadata={"wait_ms": wait_time},
                    )

            case TestStepType.ASSERT_TEXT:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.ASSERT_TEXT,
                        error_message="Element required for assert_text action",
                    )
                return await browser.assert_text(
                    element_config,
                    step.value or "",
                    exact=step.metadata.get("exact", False),
                )

            case TestStepType.ASSERT_VISIBLE:
                if not element_config:
                    return ActionResult(
                        success=False,
                        action_type=ActionType.ASSERT_VISIBLE,
                        error_message="Element required for assert_visible action",
                    )
                return await browser.assert_visible(element_config)

            case TestStepType.PRESS_KEY:
                key = step.value or step.metadata.get("key", "")
                return await browser.press_key(key, element_config)

            case TestStepType.SCREENSHOT:
                path = step.metadata.get("path")
                full_page = step.metadata.get("full_page", False)
                return await browser.screenshot(full_page=full_page, path=path)

            case _:
                return ActionResult(
                    success=False,
                    action_type=ActionType.CLICK,  # Default
                    error_message=f"Unsupported action type: {step.action}",
                )


async def run_test_from_natural_language(
    description: str,
    browser_options: BrowserOptions | None = None,
) -> TestResult:
    """
    Convenience function to run a test from natural language description.

    Args:
        description: Natural language test description
        browser_options: Optional browser configuration

    Returns:
        TestResult with execution details
    """
    from app.core.llm_service import get_llm_service

    llm = get_llm_service()

    # Generate test case from natural language
    response = await llm.generate_test_case(description)

    if not response.success:
        return TestResult(
            test_id=str(uuid.uuid4()),
            test_name="Generated Test",
            status=ExecutionStatus.ERROR,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_message=f"Failed to generate test: {response.error}",
        )

    # Execute the generated test
    executor = TestExecutor(browser_options)
    return await executor.execute(response.data)
