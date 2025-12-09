'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Plus, Play, MoreVertical, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { formatRelativeTime } from '@/lib/utils';
import type { TestCase } from '@/types';

export default function TestsPage() {
  const {
    data: tests,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['tests'],
    queryFn: () => api.listTests(),
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
              <h1 className="text-lg font-medium text-slate-900">Tests</h1>
            </div>
            <Link href="/tests/new">
              <Button>
                <Plus className="w-4 h-4" />
                New Test
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search & Filters */}
        <div className="mb-6 flex gap-4">
          <div className="flex-1 max-w-md">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Search tests..."
                className="pl-10"
              />
            </div>
          </div>
        </div>

        {/* Test List */}
        {isLoading ? (
          <div className="text-center py-12">
            <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-slate-500">Loading tests...</p>
          </div>
        ) : error ? (
          <Card>
            <CardContent className="text-center py-12">
              <p className="text-red-600 mb-2">Failed to load tests</p>
              <p className="text-slate-500 text-sm">
                Make sure the backend is running at http://localhost:8000
              </p>
            </CardContent>
          </Card>
        ) : tests && tests.length > 0 ? (
          <div className="space-y-4">
            {tests.map((test) => (
              <TestCard key={test.id} test={test} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="text-center py-12">
              <p className="text-slate-900 font-medium mb-2">No tests yet</p>
              <p className="text-slate-500 text-sm mb-4">
                Create your first test to get started
              </p>
              <Link href="/tests/new">
                <Button>
                  <Plus className="w-4 h-4" />
                  Create Test
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

function TestCard({ test }: { test: TestCase }) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="flex items-center justify-between py-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <Link
              href={`/tests/${test.id}`}
              className="font-medium text-slate-900 hover:text-primary-600 transition truncate"
            >
              {test.name}
            </Link>
            {test.last_run_status && (
              <StatusBadge status={test.last_run_status} />
            )}
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-500">
            <span>{test.steps.length} steps</span>
            {test.tags.length > 0 && (
              <span className="flex gap-1">
                {test.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    className="px-1.5 py-0.5 bg-slate-100 rounded text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </span>
            )}
            <span>Updated {formatRelativeTime(test.updated_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <Button variant="ghost" size="sm">
            <Play className="w-4 h-4" />
            Run
          </Button>
          <Button variant="ghost" size="sm">
            <MoreVertical className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
