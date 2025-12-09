'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import Link from 'next/link';
import { ArrowLeft, Wand2, Save, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Input, Textarea } from '@/components/ui/Input';
import type { TestCaseCreate, GeneratedTestResponse } from '@/types';

export default function NewTestPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'natural' | 'manual'>('natural');
  const [naturalLanguage, setNaturalLanguage] = useState('');
  const [generatedTest, setGeneratedTest] = useState<TestCaseCreate | null>(
    null
  );
  const [testName, setTestName] = useState('');

  // Generate test from natural language
  const generateMutation = useMutation({
    mutationFn: (description: string) =>
      api.generateTestFromNaturalLanguage({ description }),
    onSuccess: (data: GeneratedTestResponse) => {
      if (data.success && data.test_case) {
        setGeneratedTest(data.test_case);
        setTestName(data.test_case.name);
      }
    },
  });

  // Save test
  const saveMutation = useMutation({
    mutationFn: (testCase: TestCaseCreate) => api.createTest(testCase),
    onSuccess: (savedTest) => {
      router.push(`/tests/${savedTest.id}`);
    },
  });

  const handleGenerate = () => {
    if (naturalLanguage.trim()) {
      generateMutation.mutate(naturalLanguage);
    }
  };

  const handleSave = () => {
    if (generatedTest) {
      saveMutation.mutate({
        ...generatedTest,
        name: testName || generatedTest.name,
      });
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <Link
                href="/tests"
                className="text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <h1 className="text-lg font-medium text-slate-900">
                Create New Test
              </h1>
            </div>
            {generatedTest && (
              <Button onClick={handleSave} loading={saveMutation.isPending}>
                <Save className="w-4 h-4" />
                Save Test
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Mode Toggle */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setMode('natural')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              mode === 'natural'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-slate-600 border hover:bg-slate-50'
            }`}
          >
            Natural Language
          </button>
          <button
            onClick={() => setMode('manual')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              mode === 'manual'
                ? 'bg-primary-600 text-white'
                : 'bg-white text-slate-600 border hover:bg-slate-50'
            }`}
          >
            Manual Editor
          </button>
        </div>

        {mode === 'natural' ? (
          <div className="space-y-6">
            {/* Natural Language Input */}
            <Card>
              <CardHeader>
                <CardTitle>Describe Your Test</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  placeholder="Example: Go to https://example.com/login, enter 'testuser' as username and 'password123' as password, click the login button, and verify that the dashboard page appears with a welcome message."
                  value={naturalLanguage}
                  onChange={(e) => setNaturalLanguage(e.target.value)}
                  className="min-h-[150px]"
                />
                <Button
                  onClick={handleGenerate}
                  loading={generateMutation.isPending}
                  disabled={!naturalLanguage.trim()}
                >
                  <Wand2 className="w-4 h-4" />
                  Generate Test
                </Button>
              </CardContent>
            </Card>

            {/* Error Display */}
            {generateMutation.isError && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="flex items-start gap-3 py-4">
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-red-900">
                      Failed to generate test
                    </p>
                    <p className="text-sm text-red-700 mt-1">
                      {(generateMutation.error as Error)?.message ||
                        'Please try again or check your API configuration.'}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Generated Test Preview */}
            {generatedTest && (
              <Card>
                <CardHeader>
                  <CardTitle>Generated Test</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Input
                    label="Test Name"
                    value={testName}
                    onChange={(e) => setTestName(e.target.value)}
                  />

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Test Steps ({generatedTest.steps.length})
                    </label>
                    <div className="space-y-2">
                      {generatedTest.steps.map((step, index) => (
                        <div
                          key={index}
                          className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg"
                        >
                          <span className="flex-shrink-0 w-6 h-6 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-medium">
                            {step.step_number}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-900">
                              {step.description}
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {step.action}
                              {step.element && ` → ${step.element.name}`}
                              {step.value && ` = "${step.value}"`}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {generateMutation.data && (
                    <p className="text-xs text-slate-500">
                      Generated using {generateMutation.data.model_used} •{' '}
                      {generateMutation.data.tokens_used} tokens
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-slate-500">
                Manual test editor coming soon. Use natural language mode for
                now.
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
