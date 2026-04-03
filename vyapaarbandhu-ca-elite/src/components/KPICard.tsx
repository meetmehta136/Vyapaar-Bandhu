import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface KPICardProps {
  icon: string;
  label: string;
  value: string;
  numericValue?: number;
  prefix?: string;
  subtitle: string;
  subtitleColor?: 'success' | 'warning' | 'destructive' | 'muted';
  glowColor?: string;
  delay?: number;
}

const KPICard = ({ icon, label, value, numericValue, prefix = '', subtitle, subtitleColor = 'muted', glowColor, delay = 0 }: KPICardProps) => {
  const [displayValue, setDisplayValue] = useState(numericValue ? 0 : null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  useEffect(() => {
    if (!numericValue) return;
    const duration = 1000;
    const steps = 30;
    const increment = numericValue / steps;
    let current = 0;
    const interval = setInterval(() => {
      current += increment;
      if (current >= numericValue) {
        setDisplayValue(numericValue);
        clearInterval(interval);
      } else {
        setDisplayValue(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(interval);
  }, [numericValue]);

  const subtitleColors = {
    success: 'text-success-val',
    warning: 'text-warning-val',
    destructive: 'text-destructive-val',
    muted: 'text-muted-foreground',
  };

  return (
    <div
      className={cn(
        'card-surface p-5 transition-all duration-200 hover:border-primary/30',
        glowColor,
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      )}
      style={{ transition: 'all 0.5s ease-out' }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-2xl">{icon}</span>
        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-3xl font-bold text-foreground mb-1">
        {numericValue != null ? (
          <span className="gradient-text-primary">{prefix}{displayValue?.toLocaleString('en-IN')}</span>
        ) : (
          <span className="gradient-text-primary">{value}</span>
        )}
      </div>
      <div className={cn('text-xs', subtitleColors[subtitleColor])}>{subtitle}</div>
    </div>
  );
};

export default KPICard;
