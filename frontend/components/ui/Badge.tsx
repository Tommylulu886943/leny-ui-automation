import { cn } from '@/lib/utils';
import type { ExecutionStatus } from '@/types';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  className?: string;
  children: React.ReactNode;
}

const variantStyles = {
  default: 'bg-slate-100 text-slate-800 border-slate-200',
  success: 'bg-green-100 text-green-800 border-green-200',
  warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  error: 'bg-red-100 text-red-800 border-red-200',
  info: 'bg-blue-100 text-blue-800 border-blue-200',
};

export function Badge({ variant = 'default', className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border',
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({
  status,
  className,
}: {
  status: ExecutionStatus;
  className?: string;
}) {
  const statusVariants: Record<ExecutionStatus, BadgeProps['variant']> = {
    passed: 'success',
    failed: 'error',
    error: 'error',
    running: 'info',
    pending: 'warning',
    skipped: 'default',
  };

  return (
    <Badge variant={statusVariants[status]} className={className}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}
