"""
Pydantic schemas for test-related API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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


class ExecutionStatus(str, Enum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class ElementLocatorSchema(BaseModel):
    """Element locator with multiple strategies."""

    name: str = Field(..., description="Human-readable element name")
    description: str | None = Field(None, description="Element description")
    data_testid: str | None = Field(None, description="data-testid attribute")
    id: str | None = Field(None, description="Element ID")
    aria_label: str | None = Field(None, description="ARIA label")
    role: str | None = Field(None, description="ARIA role (format: role:name)")
    css: str | None = Field(None, description="CSS selector")
    text: str | None = Field(None, description="Text content")
    xpath: str | None = Field(None, description="XPath selector")
    placeholder: str | None = Field(None, description="Placeholder text")

    model_config = {"json_schema_extra": {"example": {
        "name": "login_button",
        "data_testid": "login-submit",
        "id": "login-btn",
        "css": "form.login button[type='submit']",
        "text": "Login"
    }}}


class TestStepSchema(BaseModel):
    """A single test step."""

    step_number: int = Field(..., ge=1, description="Step sequence number")
    action: TestStepType = Field(..., description="Action type")
    description: str = Field(..., description="Human-readable step description")
    element: ElementLocatorSchema | None = Field(None, description="Target element")
    value: str | None = Field(None, description="Value for fill/type/assert actions")
    timeout: int | None = Field(None, ge=0, description="Custom timeout in ms")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TestCaseCreate(BaseModel):
    """Request schema for creating a test case."""

    name: str = Field(..., min_length=1, max_length=200, description="Test case name")
    description: str = Field(default="", description="Test case description")
    tags: list[str] = Field(default_factory=list, description="Test tags for filtering")
    steps: list[TestStepSchema] = Field(..., min_length=1, description="Test steps")
    setup_steps: list[TestStepSchema] = Field(default_factory=list, description="Setup steps")
    teardown_steps: list[TestStepSchema] = Field(default_factory=list, description="Teardown steps")

    model_config = {"json_schema_extra": {"example": {
        "name": "Login Test",
        "description": "Verify user can login with valid credentials",
        "tags": ["login", "smoke"],
        "steps": [
            {
                "step_number": 1,
                "action": "navigate",
                "description": "Go to login page",
                "value": "https://example.com/login"
            },
            {
                "step_number": 2,
                "action": "fill",
                "description": "Enter username",
                "element": {"name": "username_field", "id": "username"},
                "value": "testuser"
            },
            {
                "step_number": 3,
                "action": "fill",
                "description": "Enter password",
                "element": {"name": "password_field", "id": "password"},
                "value": "testpass"
            },
            {
                "step_number": 4,
                "action": "click",
                "description": "Click login button",
                "element": {"name": "login_button", "data_testid": "login-submit"}
            },
            {
                "step_number": 5,
                "action": "assert_visible",
                "description": "Verify dashboard is displayed",
                "element": {"name": "dashboard", "data_testid": "dashboard-container"}
            }
        ]
    }}}


class TestCaseUpdate(BaseModel):
    """Request schema for updating a test case."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] | None = None
    steps: list[TestStepSchema] | None = None
    setup_steps: list[TestStepSchema] | None = None
    teardown_steps: list[TestStepSchema] | None = None


class TestCaseResponse(BaseModel):
    """Response schema for test case."""

    id: str
    name: str
    description: str
    tags: list[str]
    steps: list[TestStepSchema]
    setup_steps: list[TestStepSchema]
    teardown_steps: list[TestStepSchema]
    created_at: datetime
    updated_at: datetime
    last_run_status: ExecutionStatus | None = None
    last_run_at: datetime | None = None


class NaturalLanguageTestRequest(BaseModel):
    """Request to generate test from natural language."""

    description: str = Field(
        ...,
        min_length=10,
        description="Natural language description of the test"
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Additional context (e.g., base URL, credentials)"
    )

    model_config = {"json_schema_extra": {"example": {
        "description": "Test the login flow: go to https://example.com/login, enter 'testuser' as username and 'testpass' as password, click the login button, and verify the dashboard appears.",
        "context": {
            "base_url": "https://example.com"
        }
    }}}


class TestExecutionRequest(BaseModel):
    """Request to execute a test case."""

    test_id: str | None = Field(None, description="ID of existing test to run")
    test_case: TestCaseCreate | None = Field(None, description="Inline test case to run")
    browser: str = Field(default="chromium", description="Browser type")
    headless: bool = Field(default=True, description="Run in headless mode")
    timeout: int = Field(default=30000, ge=1000, le=120000, description="Timeout in ms")
    stop_on_failure: bool = Field(default=True, description="Stop on first failure")

    model_config = {"json_schema_extra": {"example": {
        "test_id": "test-123",
        "browser": "chromium",
        "headless": True,
        "timeout": 30000
    }}}


class StepResultSchema(BaseModel):
    """Result of a single step execution."""

    step_number: int
    description: str
    status: ExecutionStatus
    action_type: str
    duration_ms: float
    error_message: str | None = None
    element_name: str | None = None
    has_screenshot: bool = False


class TestExecutionResponse(BaseModel):
    """Response for test execution."""

    execution_id: str
    test_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float
    passed_steps: int
    failed_steps: int
    total_steps: int
    step_results: list[StepResultSchema]
    error_message: str | None = None
    page_url: str | None = None


class GeneratedTestResponse(BaseModel):
    """Response for generated test case."""

    success: bool
    test_case: TestCaseCreate | None = None
    error: str | None = None
    tokens_used: int = 0
    model_used: str = ""
