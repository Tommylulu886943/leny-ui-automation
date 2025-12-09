'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/Badge';
import { formatDuration, formatRelativeTime } from '@/lib/utils';
import type { TestExecution } from '@/types';

export default function ExecutionsPage() {
  const {
    data: executions,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['executions'],
    queryFn: () => api.listExecutions(50),
  });

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <Link href="/" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-lg">L</span>
                </div>
                <span className="font-semibold text-xl text-slate-900">
                  Leny
                </span>
              </Link>
              <span className="text-slate-300">/</span>
              <h1 className="text-lg font-medium text-slate-900">Executions</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading ? (
          <div className="text-center py-12">
            <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-slate-500">Loading executions...</p>
          </div>
        ) : error ? (
          <Card>
            <CardContent className="text-center py-12">
              <p className="text-red-600 mb-2">Failed to load executions</p>
              <p className="text-slate-500 text-sm">
                Make sure the backend is running at http://localhost:8000
              </p>
            </CardContent>
          </Card>
        ) : executions && executions.length > 0 ? (
          <div className="space-y-4">
            {executions.map((execution) => (
              <ExecutionCard key={execution.execution_id} execution={execution} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="text-center py-12">
              <p className="text-slate-900 font-medium mb-2">
                No executions yet
              </p>
              <p className="text-slate-500 text-sm">
                Run a test to see execution history here
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

function ExecutionCard({ execution }: { execution: TestExecution }) {
  const StatusIcon = {
    passed: CheckCircle,
    failed: XCircle,
    error: AlertCircle,
    running: Clock,
    pending: Clock,
    skipped: AlertCircle,
  }[execution.status];

  const statusColor = {
    passed: 'text-green-600',
    failed: 'text-red-600',
    error: 'text-red-600',
    running: 'text-blue-600',
    pending: 'text-yellow-600',
    skipped: 'text-slate-400',
  }[execution.status];

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="flex items-center gap-4 py-4">
        <StatusIcon className={`w-6 h-6 ${statusColor} flex-shrink-0`} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-medium text-slate-900 truncate">
              {execution.test_name}
            </span>
            <StatusBadge status={execution.status} />
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-500">
            <span>
              {execution.passed_steps}/{execution.total_steps} steps passed
            </span>
            <span>{formatDuration(execution.duration_ms)}</span>
            <span>{formatRelativeTime(execution.started_at)}</span>
          </div>
          {execution.error_message && (
            <p className="text-sm text-red-600 mt-1 truncate">
              {execution.error_message}
            </p>
          )}
        </div>

        {execution.page_url && (
          <span className="text-xs text-slate-400 truncate max-w-[200px]">
            {execution.page_url}
          </span>
        )}
      </CardContent>
    </Card>
  );
}
