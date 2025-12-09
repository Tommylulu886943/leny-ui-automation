"""
LLM Service - Natural Language to Test Script Conversion

This module integrates with OpenAI API to:
1. Convert natural language test descriptions to structured test steps
2. Analyze page DOM to suggest element locators
3. Generate assertions based on expected behavior

Cost optimization strategies:
- Prompt caching for repeated system prompts
- Model routing (simple tasks → gpt-4o-mini, complex → gpt-4o)
- Result caching for identical requests
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = structlog.get_logger()


class TaskComplexity(str, Enum):
    """Task complexity levels for model routing."""

    SIMPLE = "simple"  # Element identification, basic actions
    MEDIUM = "medium"  # Test script generation
    COMPLEX = "complex"  # Complex logic analysis, multi-step flows


class TestStepType(str, Enum):
    """Types of test steps."""

    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    HOVER = "hover"
    WAIT = "wait"
    ASSERT_TEXT = "assert_text"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_HIDDEN = "assert_hidden"
    ASSERT_VALUE = "assert_value"
    PRESS_KEY = "press_key"
    SCREENSHOT = "screenshot"


class ElementLocator(BaseModel):
    """Element locator with multiple strategies."""

    name: str
    description: str | None = None
    data_testid: str | None = None
    id: str | None = None
    aria_label: str | None = None
    role: str | None = None
    css: str | None = None
    text: str | None = None
    xpath: str | None = None
    placeholder: str | None = None


class TestStep(BaseModel):
    """A single test step."""

    step_number: int
    action: TestStepType
    description: str
    element: ElementLocator | None = None
    value: str | None = None  # For fill, type, select, assert_text
    timeout: int | None = None  # Override timeout
    metadata: dict[str, Any] = {}


class TestCase(BaseModel):
    """A complete test case with multiple steps."""

    name: str
    description: str
    tags: list[str] = []
    steps: list[TestStep]
    setup_steps: list[TestStep] = []
    teardown_steps: list[TestStep] = []


class LLMResponse(BaseModel):
    """Response from LLM service."""

    success: bool
    data: Any = None
    error: str | None = None
    tokens_used: int = 0
    model_used: str = ""
    cached: bool = False
    duration_ms: float = 0


# Simple in-memory cache (replace with Redis in production)
_cache: dict[str, tuple[Any, datetime]] = {}


def _get_cache_key(prompt: str, model: str) -> str:
    """Generate cache key from prompt and model."""
    content = f"{model}:{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()


def _get_cached(key: str) -> Any | None:
    """Get cached result if not expired."""
    if key in _cache:
        result, timestamp = _cache[key]
        age = (datetime.utcnow() - timestamp).total_seconds()
        if age < settings.llm_cache_ttl:
            return result
        del _cache[key]
    return None


def _set_cache(key: str, value: Any) -> None:
    """Cache a result."""
    _cache[key] = (value, datetime.utcnow())


class LLMService:
    """
    Service for LLM-powered test generation and analysis.
    """

    # System prompts for different tasks
    SYSTEM_PROMPT_TEST_GENERATION = """You are an expert QA automation engineer.
Your task is to convert natural language test descriptions into structured test steps.

Rules:
1. Each step should be atomic and testable
2. Use descriptive element names (e.g., "login_button" not "btn1")
3. Include assertions to verify expected outcomes
4. Suggest multiple locator strategies when possible
5. Consider edge cases and error scenarios

Output format: JSON matching the TestCase schema."""

    SYSTEM_PROMPT_ELEMENT_ANALYSIS = """You are an expert at analyzing web page DOM structure.
Your task is to suggest robust element locators based on HTML content.

Prioritize locators in this order:
1. data-testid (most stable)
2. id (if unique and semantic)
3. aria-label (accessibility-friendly)
4. role with name
5. CSS selector (if simple and stable)
6. text content (for buttons, links)
7. XPath (last resort)

Output format: JSON array of ElementLocator objects."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model_map = {
            TaskComplexity.SIMPLE: "gpt-4o-mini",
            TaskComplexity.MEDIUM: settings.openai_model,
            TaskComplexity.COMPLEX: "gpt-4o",
        }

    def _select_model(self, complexity: TaskComplexity) -> str:
        """Select appropriate model based on task complexity."""
        return self._model_map.get(complexity, settings.openai_model)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_openai(
        self,
        messages: list[dict],
        model: str,
        response_format: dict | None = None,
        temperature: float | None = None,
    ) -> tuple[str, int]:
        """Make OpenAI API call with retry logic."""
        import time

        start = time.time()

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": settings.llm_max_tokens,
            "temperature": temperature or settings.openai_temperature,
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)

        duration_ms = (time.time() - start) * 1000
        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        logger.info(
            "openai_call_complete",
            model=model,
            tokens=tokens,
            duration_ms=round(duration_ms, 2),
        )

        return content, tokens

    async def generate_test_case(
        self,
        natural_language_description: str,
        context: dict[str, Any] | None = None,
        complexity: TaskComplexity = TaskComplexity.MEDIUM,
    ) -> LLMResponse:
        """
        Convert natural language test description to structured test case.

        Args:
            natural_language_description: Human-readable test description
            context: Additional context (e.g., page URL, existing elements)
            complexity: Task complexity for model selection

        Returns:
            LLMResponse containing TestCase or error
        """
        import time

        start = time.time()
        model = self._select_model(complexity)

        # Check cache
        cache_key = _get_cache_key(natural_language_description + str(context), model)
        cached_result = _get_cached(cache_key)
        if cached_result:
            return LLMResponse(
                success=True,
                data=cached_result,
                cached=True,
                model_used=model,
            )

        # Build prompt
        user_prompt = f"""Convert this test description into a structured test case:

---
{natural_language_description}
---
"""
        if context:
            user_prompt += f"\nAdditional context:\n{json.dumps(context, indent=2)}"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT_TEST_GENERATION},
            {"role": "user", "content": user_prompt},
        ]

        try:
            content, tokens = await self._call_openai(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
            )

            # Parse response
            test_data = json.loads(content)
            test_case = TestCase(**test_data)

            # Cache result
            _set_cache(cache_key, test_case.model_dump())

            duration_ms = (time.time() - start) * 1000

            return LLMResponse(
                success=True,
                data=test_case.model_dump(),
                tokens_used=tokens,
                model_used=model,
                duration_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            logger.error("json_parse_error", error=str(e))
            return LLMResponse(
                success=False,
                error=f"Failed to parse LLM response: {str(e)}",
                model_used=model,
            )
        except Exception as e:
            logger.error("llm_error", error=str(e))
            return LLMResponse(
                success=False,
                error=str(e),
                model_used=model,
            )

    async def analyze_page_elements(
        self,
        html_content: str,
        target_elements: list[str] | None = None,
    ) -> LLMResponse:
        """
        Analyze page HTML and suggest element locators.

        Args:
            html_content: Page HTML (can be truncated for cost efficiency)
            target_elements: Optional list of elements to focus on

        Returns:
            LLMResponse containing list of ElementLocator suggestions
        """
        import time

        start = time.time()
        model = self._select_model(TaskComplexity.SIMPLE)

        # Truncate HTML to reduce tokens
        max_html_length = 10000
        if len(html_content) > max_html_length:
            html_content = html_content[:max_html_length] + "\n... [truncated]"

        user_prompt = f"""Analyze this HTML and suggest robust locators for interactive elements:

```html
{html_content}
```
"""
        if target_elements:
            user_prompt += f"\nFocus on these elements: {', '.join(target_elements)}"

        user_prompt += "\n\nReturn a JSON array of element locators."

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT_ELEMENT_ANALYSIS},
            {"role": "user", "content": user_prompt},
        ]

        try:
            content, tokens = await self._call_openai(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
            )

            elements_data = json.loads(content)
            # Handle both {"elements": [...]} and direct array
            if isinstance(elements_data, dict) and "elements" in elements_data:
                elements_list = elements_data["elements"]
            elif isinstance(elements_data, list):
                elements_list = elements_data
            else:
                elements_list = []

            duration_ms = (time.time() - start) * 1000

            return LLMResponse(
                success=True,
                data=elements_list,
                tokens_used=tokens,
                model_used=model,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error("element_analysis_error", error=str(e))
            return LLMResponse(
                success=False,
                error=str(e),
                model_used=model,
            )

    async def suggest_assertions(
        self,
        action_description: str,
        page_context: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """
        Suggest assertions for a given action.

        Args:
            action_description: Description of what action was performed
            page_context: Current page state

        Returns:
            LLMResponse containing suggested assertions
        """
        import time

        start = time.time()
        model = self._select_model(TaskComplexity.SIMPLE)

        user_prompt = f"""After performing this action:
"{action_description}"

Suggest appropriate assertions to verify the action was successful.
Return a JSON array of TestStep objects with assertion actions.
"""
        if page_context:
            user_prompt += f"\nPage context: {json.dumps(page_context)}"

        messages = [
            {
                "role": "system",
                "content": "You are a QA expert. Suggest meaningful assertions that verify user-visible outcomes, not implementation details.",
            },
            {"role": "user", "content": user_prompt},
        ]

        try:
            content, tokens = await self._call_openai(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
            )

            assertions_data = json.loads(content)
            duration_ms = (time.time() - start) * 1000

            return LLMResponse(
                success=True,
                data=assertions_data,
                tokens_used=tokens,
                model_used=model,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error("assertion_suggestion_error", error=str(e))
            return LLMResponse(
                success=False,
                error=str(e),
                model_used=model,
            )

    async def improve_test_step(
        self,
        step: TestStep,
        failure_context: dict[str, Any],
    ) -> LLMResponse:
        """
        Suggest improvements for a failed test step.

        This is the foundation for future self-healing capabilities.

        Args:
            step: The failed test step
            failure_context: Information about the failure

        Returns:
            LLMResponse containing improved TestStep
        """
        import time

        start = time.time()
        model = self._select_model(TaskComplexity.MEDIUM)

        user_prompt = f"""This test step failed:
{json.dumps(step.model_dump(), indent=2)}

Failure context:
{json.dumps(failure_context, indent=2)}

Suggest an improved version of this step that might succeed.
Consider:
1. Alternative locator strategies
2. Adding wait conditions
3. Handling dynamic content

Return an improved TestStep as JSON.
"""

        messages = [
            {
                "role": "system",
                "content": "You are an expert at debugging flaky tests. Suggest practical improvements based on the failure context.",
            },
            {"role": "user", "content": user_prompt},
        ]

        try:
            content, tokens = await self._call_openai(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
            )

            improved_step = json.loads(content)
            duration_ms = (time.time() - start) * 1000

            return LLMResponse(
                success=True,
                data=improved_step,
                tokens_used=tokens,
                model_used=model,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error("step_improvement_error", error=str(e))
            return LLMResponse(
                success=False,
                error=str(e),
                model_used=model,
            )

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "gpt-4o-mini",
    ) -> float:
        """
        Estimate cost for a given number of tokens.

        Prices as of Dec 2024 (per 1M tokens):
        - gpt-4o-mini: $0.15 input, $0.60 output
        - gpt-4o: $2.50 input, $10.00 output
        """
        prices = {
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4o": (2.50, 10.00),
        }

        input_price, output_price = prices.get(model, prices["gpt-4o-mini"])

        cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
        return round(cost, 6)


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
