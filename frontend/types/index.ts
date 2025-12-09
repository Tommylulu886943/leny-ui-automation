/**
 * Type definitions for Leny UI Automation
 */

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'passed'
  | 'failed'
  | 'skipped'
  | 'error';

export type TestStepType =
  | 'navigate'
  | 'click'
  | 'fill'
  | 'type'
  | 'select'
  | 'check'
  | 'uncheck'
  | 'hover'
  | 'wait'
  | 'assert_text'
  | 'assert_visible'
  | 'assert_hidden'
  | 'assert_value'
  | 'press_key'
  | 'screenshot';

export interface ElementLocator {
  name: string;
  description?: string;
  data_testid?: string;
  id?: string;
  aria_label?: string;
  role?: string;
  css?: string;
  text?: string;
  xpath?: string;
  placeholder?: string;
}

export interface TestStep {
  step_number: number;
  action: TestStepType;
  description: string;
  element?: ElementLocator;
  value?: string;
  timeout?: number;
  metadata?: Record<string, unknown>;
}

export interface TestCase {
  id: string;
  name: string;
  description: string;
  tags: string[];
  steps: TestStep[];
  setup_steps: TestStep[];
  teardown_steps: TestStep[];
  created_at: string;
  updated_at: string;
  last_run_status?: ExecutionStatus;
  last_run_at?: string;
}

export interface TestCaseCreate {
  name: string;
  description: string;
  tags: string[];
  steps: TestStep[];
  setup_steps?: TestStep[];
  teardown_steps?: TestStep[];
}

export interface StepResult {
  step_number: number;
  description: string;
  status: ExecutionStatus;
  action_type: string;
  duration_ms: number;
  error_message?: string;
  element_name?: string;
  has_screenshot: boolean;
}

export interface TestExecution {
  execution_id: string;
  test_name: string;
  status: ExecutionStatus;
  started_at: string;
  completed_at?: string;
  duration_ms: number;
  passed_steps: number;
  failed_steps: number;
  total_steps: number;
  step_results: StepResult[];
  error_message?: string;
  page_url?: string;
}

export interface GeneratedTestResponse {
  success: boolean;
  test_case?: TestCaseCreate;
  error?: string;
  tokens_used: number;
  model_used: string;
}

export interface NaturalLanguageRequest {
  description: string;
  context?: Record<string, unknown>;
}

export interface ExecutionRequest {
  test_id?: string;
  test_case?: TestCaseCreate;
  browser?: 'chromium' | 'firefox' | 'webkit';
  headless?: boolean;
  timeout?: number;
  stop_on_failure?: boolean;
}
