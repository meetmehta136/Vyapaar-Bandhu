import { useState } from 'react';
import AppLayout from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';
import { useAlerts } from '@/hooks/useAPI';

const priorityConfig: Record<string, { icon: string; border: string; text: string; bg: string }> = {
  high: { icon: '🚨', border: 'border-l-destructive', text: 'text-destructive-val', bg: 'bg-destructive/10' },
  medium: { icon: '⚠️', border: 'border-l-warning', text: 'text-warning-val', bg: 'bg-warning/10' },
  low: { icon: 'ℹ️', border: 'border-l-primary', text: 'text-primary-val', bg: 'bg-primary/10' },
};

type FilterTab = 'all' | 'high' | 'medium' | 'low' | 'resolved';

const AlertsPage = () => {
  const [tab, setTab] = useState<FilterTab>('all');
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const { toast } = useToast();
  const { data: alertsData, loading } = useAlerts();

  const allAlerts = alertsData || [];

  const activeAlerts = allAlerts.filter((a: any) => !resolvedIds.has(a.id) && !a.resolved);
  const resolvedAlerts = allAlerts.filter((a: any) => resolvedIds.has(a.id) || a.resolved);

  const highCount = activeAlerts.filter((a: any) => a.priority === 'high').length;
  const mediumCount = activeAlerts.filter((a: any) => a.priority === 'medium').length;

  const filtered = tab === 'resolved'
    ? resolvedAlerts
    : tab === 'all'
    ? activeAlerts
    : activeAlerts.filter((a: any) => a.priority === tab);

  const resolveAlert = (id: string) => {
    setResolvedIds(prev => new Set([...prev, id]));
    toast({ title: 'Alert resolved ✅', description: 'Alert marked as resolved.' });
  };

  const sendReminder = (clientName: string) => {
    toast({ title: 'Reminder sent 📱', description: `WhatsApp reminder sent to ${clientName}.` });
  };

  const tabs: { key: FilterTab; label: string }[] = [
    { key: 'all', label: `All (${activeAlerts.length})` },
    { key: 'high', label: `High (${highCount})` },
    { key: 'medium', label: `Medium (${mediumCount})` },
    { key: 'low', label: 'Low' },
    { key: 'resolved', label: `Resolved (${resolvedAlerts.length})` },
  ];

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-foreground">🔔 Alerts</h1>
        {!loading && (
          <span className="text-xs text-success-val">● Live — {allAlerts.length} alerts</span>
        )}
        {loading && (
          <span className="text-xs text-muted-foreground animate-pulse">Loading...</span>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="card-surface p-4">
          <div className="text-2xl font-bold text-destructive-val">{highCount}</div>
          <div className="text-xs text-muted-foreground">High Priority</div>
        </div>
        <div className="card-surface p-4">
          <div className="text-2xl font-bold text-warning-val">{mediumCount}</div>
          <div className="text-xs text-muted-foreground">Medium</div>
        </div>
        <div className="card-surface p-4">
          <div className="text-2xl font-bold text-success-val">{resolvedAlerts.length}</div>
          <div className="text-xs text-muted-foreground">Resolved This Month</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'px-4 py-2 rounded-lg text-xs font-medium transition-all duration-200',
              tab === t.key ? 'bg-primary/20 text-primary-val' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="card-surface p-4 animate-pulse">
              <div className="h-4 bg-muted rounded w-1/3 mb-2" />
              <div className="h-3 bg-muted rounded w-2/3" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="text-center py-20 text-muted-foreground">
          <p className="text-4xl mb-4">✅</p>
          <p className="text-sm">No alerts in this category.</p>
          <p className="text-xs mt-1">All clients are on track!</p>
        </div>
      )}

      {/* Alert Cards */}
      {!loading && (
        <div className="space-y-3">
          {filtered.map((alert: any) => {
            const config = priorityConfig[alert.priority] || priorityConfig['low'];
            const isResolved = resolvedIds.has(alert.id) || alert.resolved;
            return (
              <div
                key={alert.id}
                className={cn(
                  'card-surface p-4 border-l-4 flex items-start gap-4 transition-all duration-200',
                  config.border,
                  isResolved && 'opacity-60'
                )}
              >
                <span className="text-xl">{config.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-sm font-semibold text-foreground">{alert.clientName}</span>
                    <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', config.bg, config.text)}>
                      {alert.type}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-1">{alert.message}</p>
                  <p className="text-[10px] text-muted-foreground">Due: {alert.dueDate}</p>
                </div>
                <div className="flex flex-col items-end gap-2 flex-shrink-0">
                  <span className={cn(
                    'text-sm font-bold',
                    alert.daysRemaining < 7 ? 'text-destructive-val' : 'text-muted-foreground'
                  )}>
                    {alert.daysRemaining}d
                  </span>
                  {!isResolved && (
                    <div className="flex gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-[10px] h-7 border-border text-muted-foreground rounded-lg"
                        onClick={() => sendReminder(alert.clientName)}
                      >
                        📱 Remind
                      </Button>
                      <Button
                        variant="indigo"
                        size="sm"
                        className="text-[10px] h-7 rounded-lg"
                        onClick={() => resolveAlert(alert.id)}
                      >
                        Resolve
                      </Button>
                    </div>
                  )}
                  {isResolved && (
                    <span className="text-[10px] text-success-val font-medium">✅ Resolved</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
};

export default AlertsPage;