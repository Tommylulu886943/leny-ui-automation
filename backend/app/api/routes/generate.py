"""
AI-powered test generation endpoints.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.test import (
    NaturalLanguageTestRequest,
    TestCaseCreate,
    GeneratedTestResponse,
    TestStepSchema,
    ElementLocatorSchema,
)
from app.core.llm_service import get_llm_service, TaskComplexity

router = APIRouter()


@router.post("/from-natural-language", response_model=GeneratedTestResponse)
async def generate_test_from_natural_language(request: NaturalLanguageTestRequest):
    """
    Generate a structured test case from natural language description.

    This uses OpenAI's API to convert human-readable test descriptions
    into executable test steps with element locators.

    Example input:
    "Test the login flow: go to https://example.com/login,
     enter 'testuser' as username and 'testpass' as password,
     click the login button, and verify the dashboard appears."
    """
    llm = get_llm_service()

    response = await llm.generate_test_case(
        natural_language_description=request.description,
        context=request.context,
        complexity=TaskComplexity.MEDIUM,
    )

    if not response.success:
        return GeneratedTestResponse(
            success=False,
            error=response.error,
            tokens_used=response.tokens_used,
            model_used=response.model_used,
        )

    # Convert LLM response to API schema
    try:
        data = response.data
        steps = []

        for step_data in data.get("steps", []):
            element = None
            if step_data.get("element"):
                elem = step_data["element"]
                element = ElementLocatorSchema(
                    name=elem.get("name", "unnamed"),
                    description=elem.get("description"),
                    data_testid=elem.get("data_testid"),
                    id=elem.get("id"),
                    aria_label=elem.get("aria_label"),
                    role=elem.get("role"),
                    css=elem.get("css"),
                    text=elem.get("text"),
                    xpath=elem.get("xpath"),
                    placeholder=elem.get("placeholder"),
                )

            steps.append(
                TestStepSchema(
                    step_number=step_data.get("step_number", len(steps) + 1),
                    action=step_data["action"],
                    description=step_data.get("description", ""),
                    element=element,
                    value=step_data.get("value"),
                    timeout=step_data.get("timeout"),
                    metadata=step_data.get("metadata", {}),
                )
            )

        test_case = TestCaseCreate(
            name=data.get("name", "Generated Test"),
            description=data.get("description", request.description),
            tags=data.get("tags", ["generated"]),
            steps=steps,
            setup_steps=[],  # Could be populated from LLM response
            teardown_steps=[],
        )

        return GeneratedTestResponse(
            success=True,
            test_case=test_case,
            tokens_used=response.tokens_used,
            model_used=response.model_used,
        )

    except Exception as e:
        return GeneratedTestResponse(
            success=False,
            error=f"Failed to parse generated test: {str(e)}",
            tokens_used=response.tokens_used,
            model_used=response.model_used,
        )


@router.post("/analyze-page")
async def analyze_page_elements(
    html_content: str,
    target_elements: list[str] | None = None,
):
    """
    Analyze page HTML and suggest element locators.

    Useful for building tests when you have the page HTML but need
    help identifying robust selectors.
    """
    llm = get_llm_service()

    response = await llm.analyze_page_elements(
        html_content=html_content,
        target_elements=target_elements,
    )

    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)

    return {
        "success": True,
        "elements": response.data,
        "tokens_used": response.tokens_used,
        "model_used": response.model_used,
    }


@router.post("/suggest-assertions")
async def suggest_assertions(
    action_description: str,
    page_context: dict | None = None,
):
    """
    Suggest assertions for a given action.

    After performing an action like "click login button",
    this endpoint suggests what assertions to add to verify success.
    """
    llm = get_llm_service()

    response = await llm.suggest_assertions(
        action_description=action_description,
        page_context=page_context,
    )

    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)

    return {
        "success": True,
        "assertions": response.data,
        "tokens_used": response.tokens_used,
        "model_used": response.model_used,
    }
