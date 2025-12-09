"""
Test case CRUD endpoints.

Note: MVP version uses in-memory storage.
Production version should use PostgreSQL via SQLAlchemy.
"""

from datetime import datetime
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, Query

from app.schemas.test import (
    TestCaseCreate,
    TestCaseResponse,
    TestCaseUpdate,
    ExecutionStatus,
)

router = APIRouter()

# In-memory storage for MVP (replace with database in production)
_test_cases: dict[str, dict[str, Any]] = {}


def _test_to_response(test_id: str, test_data: dict) -> TestCaseResponse:
    """Convert stored test data to response schema."""
    return TestCaseResponse(
        id=test_id,
        name=test_data["name"],
        description=test_data["description"],
        tags=test_data["tags"],
        steps=test_data["steps"],
        setup_steps=test_data.get("setup_steps", []),
        teardown_steps=test_data.get("teardown_steps", []),
        created_at=test_data["created_at"],
        updated_at=test_data["updated_at"],
        last_run_status=test_data.get("last_run_status"),
        last_run_at=test_data.get("last_run_at"),
    )


@router.get("", response_model=list[TestCaseResponse])
async def list_tests(
    skip: int = Query(0, ge=0, description="Number of tests to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum tests to return"),
    tag: str | None = Query(None, description="Filter by tag"),
):
    """
    List all test cases with pagination and optional tag filtering.
    """
    tests = list(_test_cases.items())

    # Filter by tag if specified
    if tag:
        tests = [(tid, t) for tid, t in tests if tag in t.get("tags", [])]

    # Sort by updated_at descending
    tests.sort(key=lambda x: x[1]["updated_at"], reverse=True)

    # Apply pagination
    tests = tests[skip : skip + limit]

    return [_test_to_response(tid, t) for tid, t in tests]


@router.post("", response_model=TestCaseResponse, status_code=201)
async def create_test(test_case: TestCaseCreate):
    """
    Create a new test case.
    """
    test_id = str(uuid.uuid4())
    now = datetime.utcnow()

    test_data = {
        **test_case.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    _test_cases[test_id] = test_data

    return _test_to_response(test_id, test_data)


@router.get("/{test_id}", response_model=TestCaseResponse)
async def get_test(test_id: str):
    """
    Get a specific test case by ID.
    """
    if test_id not in _test_cases:
        raise HTTPException(status_code=404, detail=f"Test case {test_id} not found")

    return _test_to_response(test_id, _test_cases[test_id])


@router.put("/{test_id}", response_model=TestCaseResponse)
async def update_test(test_id: str, update: TestCaseUpdate):
    """
    Update an existing test case.
    """
    if test_id not in _test_cases:
        raise HTTPException(status_code=404, detail=f"Test case {test_id} not found")

    test_data = _test_cases[test_id]

    # Update only provided fields
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        test_data[key] = value

    test_data["updated_at"] = datetime.utcnow()

    return _test_to_response(test_id, test_data)


@router.delete("/{test_id}", status_code=204)
async def delete_test(test_id: str):
    """
    Delete a test case.
    """
    if test_id not in _test_cases:
        raise HTTPException(status_code=404, detail=f"Test case {test_id} not found")

    del _test_cases[test_id]


@router.post("/{test_id}/duplicate", response_model=TestCaseResponse, status_code=201)
async def duplicate_test(test_id: str):
    """
    Create a copy of an existing test case.
    """
    if test_id not in _test_cases:
        raise HTTPException(status_code=404, detail=f"Test case {test_id} not found")

    original = _test_cases[test_id]
    new_id = str(uuid.uuid4())
    now = datetime.utcnow()

    new_test = {
        **original,
        "name": f"{original['name']} (Copy)",
        "created_at": now,
        "updated_at": now,
        "last_run_status": None,
        "last_run_at": None,
    }

    _test_cases[new_id] = new_test

    return _test_to_response(new_id, new_test)


# Export storage for use by execution module
def get_test_storage() -> dict:
    """Get reference to test storage for execution module."""
    return _test_cases
