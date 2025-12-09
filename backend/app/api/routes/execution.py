"""
Test execution endpoints.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.schemas.test import (
    TestExecutionRequest,
    TestExecutionResponse,
    StepResultSchema,
    ExecutionStatus,
    TestCaseCreate,
)
from app.core.playwright_wrapper import BrowserOptions, BrowserType
from app.core.test_executor import TestExecutor, TestResult
from app.core.llm_service import TestCase
from app.api.routes.tests import get_test_storage

router = APIRouter()

# In-memory execution history (replace with database in production)
_execution_history: dict[str, dict[str, Any]] = {}


def _result_to_response(result: TestResult) -> TestExecutionResponse:
    """Convert TestResult to API response."""
    return TestExecutionResponse(
        execution_id=result.test_id,
        test_name=result.test_name,
        status=ExecutionStatus(result.status.value),
        started_at=result.started_at,
        completed_at=result.completed_at,
        duration_ms=result.duration_ms,
        passed_steps=result.passed_steps,
        failed_steps=result.failed_steps,
        total_steps=result.total_steps,
        step_results=[
            StepResultSchema(
                step_number=s.step_number,
                description=s.step_description,
                status=ExecutionStatus(s.status.value),
                action_type=s.action_type,
                duration_ms=s.duration_ms,
                error_message=s.error_message,
                element_name=s.element_name,
                has_screenshot=s.screenshot_base64 is not None,
            )
            for s in result.step_results
        ],
        error_message=result.error_message,
        page_url=result.page_url,
    )


@router.post("/run", response_model=TestExecutionResponse)
async def execute_test(request: TestExecutionRequest):
    """
    Execute a test case and return results.

    Either provide test_id to run an existing test, or test_case for inline execution.
    """
    test_storage = get_test_storage()

    # Get test case
    if request.test_id:
        if request.test_id not in test_storage:
            raise HTTPException(
                status_code=404, detail=f"Test case {request.test_id} not found"
            )
        test_data = test_storage[request.test_id]
        test_case = TestCase(
            name=test_data["name"],
            description=test_data["description"],
            tags=test_data.get("tags", []),
            steps=test_data["steps"],
            setup_steps=test_data.get("setup_steps", []),
            teardown_steps=test_data.get("teardown_steps", []),
        )
    elif request.test_case:
        test_case = TestCase(
            name=request.test_case.name,
            description=request.test_case.description,
            tags=request.test_case.tags,
            steps=[s.model_dump() for s in request.test_case.steps],
            setup_steps=[s.model_dump() for s in request.test_case.setup_steps],
            teardown_steps=[s.model_dump() for s in request.test_case.teardown_steps],
        )
    else:
        raise HTTPException(
            status_code=400, detail="Either test_id or test_case must be provided"
        )

    # Configure browser
    browser_options = BrowserOptions(
        browser_type=BrowserType(request.browser),
        headless=request.headless,
        timeout=request.timeout,
    )

    # Execute test
    executor = TestExecutor(browser_options)
    result = await executor.execute(
        test_case.model_dump(), stop_on_failure=request.stop_on_failure
    )

    # Store execution history
    _execution_history[result.test_id] = result.to_dict()

    # Update test's last run info
    if request.test_id and request.test_id in test_storage:
        test_storage[request.test_id]["last_run_status"] = result.status.value
        test_storage[request.test_id]["last_run_at"] = datetime.utcnow()

    return _result_to_response(result)


@router.get("/history", response_model=list[TestExecutionResponse])
async def list_executions(
    limit: int = 20,
):
    """
    Get execution history.
    """
    executions = list(_execution_history.values())
    executions.sort(key=lambda x: x["started_at"], reverse=True)
    executions = executions[:limit]

    return [
        TestExecutionResponse(
            execution_id=e["test_id"],
            test_name=e["test_name"],
            status=ExecutionStatus(e["status"]),
            started_at=datetime.fromisoformat(e["started_at"]),
            completed_at=datetime.fromisoformat(e["completed_at"])
            if e.get("completed_at")
            else None,
            duration_ms=e["duration_ms"],
            passed_steps=e["passed_steps"],
            failed_steps=e["failed_steps"],
            total_steps=e["total_steps"],
            step_results=[
                StepResultSchema(
                    step_number=s["step_number"],
                    description=s["description"],
                    status=ExecutionStatus(s["status"]),
                    action_type=s["action_type"],
                    duration_ms=s["duration_ms"],
                    error_message=s.get("error_message"),
                    element_name=s.get("element_name"),
                    has_screenshot=s.get("has_screenshot", False),
                )
                for s in e["step_results"]
            ],
            error_message=e.get("error_message"),
            page_url=e.get("page_url"),
        )
        for e in executions
    ]


@router.get("/{execution_id}", response_model=TestExecutionResponse)
async def get_execution(execution_id: str):
    """
    Get details of a specific execution.
    """
    if execution_id not in _execution_history:
        raise HTTPException(
            status_code=404, detail=f"Execution {execution_id} not found"
        )

    e = _execution_history[execution_id]

    return TestExecutionResponse(
        execution_id=e["test_id"],
        test_name=e["test_name"],
        status=ExecutionStatus(e["status"]),
        started_at=datetime.fromisoformat(e["started_at"]),
        completed_at=datetime.fromisoformat(e["completed_at"])
        if e.get("completed_at")
        else None,
        duration_ms=e["duration_ms"],
        passed_steps=e["passed_steps"],
        failed_steps=e["failed_steps"],
        total_steps=e["total_steps"],
        step_results=[
            StepResultSchema(
                step_number=s["step_number"],
                description=s["description"],
                status=ExecutionStatus(s["status"]),
                action_type=s["action_type"],
                duration_ms=s["duration_ms"],
                error_message=s.get("error_message"),
                element_name=s.get("element_name"),
                has_screenshot=s.get("has_screenshot", False),
            )
            for s in e["step_results"]
        ],
        error_message=e.get("error_message"),
        page_url=e.get("page_url"),
    )


@router.get("/{execution_id}/screenshot/{step_number}")
async def get_step_screenshot(execution_id: str, step_number: int):
    """
    Get screenshot for a specific step.

    Note: In MVP, screenshots are stored in memory with the execution.
    Production should store in S3/Supabase Storage.
    """
    # This would retrieve from storage in production
    raise HTTPException(
        status_code=501,
        detail="Screenshot storage not implemented in MVP. Screenshots are available in execution response.",
    )
