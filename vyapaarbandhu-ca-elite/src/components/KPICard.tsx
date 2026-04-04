import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface KPICardProps {
  icon: string;
  label: string;
  value?: string;
  numericValue?: number;
  prefix?: string;
  subtitle: string;
  subtitleColor?: 'success' | 'warning' | 'destructive' | 'muted';
  accentColor?: 'primary' | 'success' | 'warning' | 'destructive';
  delay?: number;
  loading?: boolean;
}

const accentMap = {
  primary:     { border: 'border-l-4 border-l-blue-600',     glow: 'hover:shadow-md',     text: 'gradient-text-primary'  },
  success:     { border: 'border-l-4 border-l-emerald-600',  glow: 'hover:shadow-md',     text: 'gradient-text-accent'   },
  warning:     { border: 'border-l-4 border-l-amber-600',    glow: 'hover:shadow-md',     text: 'gradient-text-warning'  },
  destructive: { border: 'border-l-4 border-l-red-600',      glow: 'hover:shadow-md',     text: 'gradient-text-primary'  },
};

const subtitleColors = {
  success:     'text-emerald-600',
  warning:     'text-amber-600',
  destructive: 'text-red-600',
  muted:       'text-gray-600',
};

const KPICard = ({
  icon, label, value, numericValue, prefix = '',
  subtitle, subtitleColor = 'muted',
  accentColor = 'primary', delay = 0, loading = false,
}: KPICardProps) => {
  const [displayValue, setDisplayValue] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  useEffect(() => {
    if (!numericValue || !visible) return;
    const duration = 900;
    const steps = 40;
    const increment = numericValue / steps;
    let current = 0;
    const interval = setInterval(() => {
      current += increment;
      if (current >= numericValue) { setDisplayValue(numericValue); clearInterval(interval); }
      else setDisplayValue(Math.floor(current));
    }, duration / steps);
    return () => clearInterval(interval);
  }, [numericValue, visible]);

  const accent = accentMap[accentColor];

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 border-l-4 border-l-gray-300">
        <div className="flex items-center justify-between mb-4">
          <div className="skeleton w-8 h-8 rounded-lg" />
          <div className="skeleton w-20 h-3 rounded" />
        </div>
        <div className="skeleton w-28 h-8 rounded mb-2" />
        <div className="skeleton w-24 h-3 rounded" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        'bg-white rounded-lg border border-gray-200 shadow-sm p-5 transition-all duration-300 cursor-default group',
        'hover:shadow-md hover:-translate-y-1',
        accent.border, accent.glow,
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      )}
      style={{ transitionDelay: `${delay}ms`, transitionProperty: 'all' }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xl">{icon}</span>
        <span className="text-[10px] text-gray-500 font-medium uppercase tracking-widest font-display">
          {label}
        </span>
      </div>

      <div className={cn('text-4xl font-bold mb-1.5 font-display text-gray-900', accent.text)}>
        {numericValue != null
          ? <>{prefix}{displayValue.toLocaleString('en-IN')}</>
          : value}
      </div>

      <div className={cn('text-xs font-medium', subtitleColors[subtitleColor])}>
        {subtitle}
      </div>
    </div>
  );
};

export default KPICard;
