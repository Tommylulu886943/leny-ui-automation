import Link from 'next/link';
import {
  Play,
  FileText,
  Wand2,
  BarChart3,
  ArrowRight,
  Github,
} from 'lucide-react';

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">L</span>
              </div>
              <span className="font-semibold text-xl text-slate-900">
                Leny
              </span>
            </div>
            <nav className="flex items-center gap-6">
              <Link
                href="/tests"
                className="text-slate-600 hover:text-slate-900 transition"
              >
                Tests
              </Link>
              <Link
                href="/executions"
                className="text-slate-600 hover:text-slate-900 transition"
              >
                Executions
              </Link>
              <Link
                href="/docs"
                className="text-slate-600 hover:text-slate-900 transition"
              >
                Docs
              </Link>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-600 hover:text-slate-900 transition"
              >
                <Github className="w-5 h-5" />
              </a>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl font-bold text-slate-900 mb-6">
            AI-Powered{' '}
            <span className="text-primary-600">UI Test Automation</span>
          </h1>
          <p className="text-xl text-slate-600 mb-8 max-w-2xl mx-auto">
            Write tests in natural language. Execute with confidence. Stop
            fighting brittle selectors.
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/tests/new"
              className="inline-flex items-center gap-2 bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700 transition"
            >
              <Wand2 className="w-5 h-5" />
              Create Test
            </Link>
            <Link
              href="/tests"
              className="inline-flex items-center gap-2 bg-white text-slate-900 px-6 py-3 rounded-lg font-medium border hover:bg-slate-50 transition"
            >
              View Tests
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-slate-900 text-center mb-12">
            Why Leny?
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            <FeatureCard
              icon={<Wand2 className="w-6 h-6" />}
              title="Natural Language Tests"
              description="Write tests in plain English. Our AI converts them to executable automation."
            />
            <FeatureCard
              icon={<Play className="w-6 h-6" />}
              title="Multi-Strategy Locators"
              description="Resilient element finding with automatic fallbacks. No more flaky tests."
            />
            <FeatureCard
              icon={<FileText className="w-6 h-6" />}
              title="Detailed Reports"
              description="Screenshots, timing data, and step-by-step execution logs."
            />
            <FeatureCard
              icon={<BarChart3 className="w-6 h-6" />}
              title="API-First Design"
              description="Integrate with your CI/CD pipeline. Everything is programmable."
            />
          </div>
        </div>
      </section>

      {/* Quick Start */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-slate-900 text-center mb-8">
            Quick Start
          </h2>
          <div className="bg-slate-900 rounded-xl p-6 overflow-x-auto">
            <pre className="text-slate-100 text-sm">
              <code>{`# Generate a test from natural language
curl -X POST http://localhost:8000/api/v1/generate/from-natural-language \\
  -H "Content-Type: application/json" \\
  -d '{
    "description": "Go to example.com, click the login button, enter credentials, verify dashboard"
  }'

# Execute the test
curl -X POST http://localhost:8000/api/v1/execution/run \\
  -H "Content-Type: application/json" \\
  -d '{
    "test_case": { ... }
  }'`}</code>
            </pre>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 sm:px-6 lg:px-8 border-t">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <p className="text-slate-500 text-sm">
            © 2024 Leny UI Automation. MIT License.
          </p>
          <div className="flex gap-4">
            <a href="#" className="text-slate-500 hover:text-slate-700 text-sm">
              Documentation
            </a>
            <a href="#" className="text-slate-500 hover:text-slate-700 text-sm">
              API Reference
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="p-6 rounded-xl border bg-slate-50 hover:bg-white transition">
      <div className="w-12 h-12 bg-primary-100 text-primary-600 rounded-lg flex items-center justify-center mb-4">
        {icon}
      </div>
      <h3 className="font-semibold text-lg text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-600 text-sm">{description}</p>
    </div>
  );
}
