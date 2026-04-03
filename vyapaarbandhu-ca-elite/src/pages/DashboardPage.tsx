import { useEffect, useState } from 'react';
import AppLayout from '@/components/AppLayout';
import KPICard from '@/components/KPICard';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { cn } from '@/lib/utils';
import { useDashboardStats, useInvoices } from '@/hooks/useAPI';
import { getClients } from '@/lib/api';

const statusDot: Record<string, string> = { success: 'bg-success', warning: 'bg-warning', danger: 'bg-destructive' };
const riskColors: Record<string, string> = { high: 'text-destructive-val', medium: 'text-warning-val', low: 'text-success-val' };
const riskBg: Record<string, string> = { high: 'bg-destructive/20', medium: 'bg-warning/20', low: 'bg-success/20' };
const categoryColors: Record<string, string> = {
  'Electronics':    'bg-primary/20 text-primary-val',
  'Office':         'bg-accent/20 text-accent-val',
  'Food':           'bg-warning/20 text-warning-val',
  'Pharma':         'bg-success/20 text-success-val',
  'Vehicle':        'bg-destructive/20 text-destructive-val',
  'Clothing':       'bg-destructive/20 text-destructive-val',
  'Travel':         'bg-primary/20 text-primary-val',
  'General':        'bg-muted text-muted-foreground',
  'Other':          'bg-muted text-muted-foreground',
};
const statusBadge: Record<string, string> = {
  confirmed: 'bg-primary/20 text-primary-val',
  pending:   'bg-warning/20 text-warning-val',
  rejected:  'bg-destructive/20 text-destructive-val',
};

const getGreeting = () => {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
};

const getFilingPeriod = () => {
  const now = new Date();
  return now.toLocaleString('en-IN', { month: 'long', year: 'numeric' }) + ' Filing Period';
};

const DashboardPage = () => {
  const { data: stats, loading: statsLoading } = useDashboardStats();
  const { data: invoicesData, loading: invoicesLoading } = useInvoices();
  const [clients, setClients] = useState<any[]>([]);

  useEffect(() => {
    getClients().then(c => setClients(c || []));
  }, []);

  const invoices      = invoicesData || [];
  const recentInvoices = invoices.slice(0, 5);

  // WhatsApp Activity — derived from real invoices
  const whatsappActivity = invoices.slice(0, 6).map((inv: any) => ({
    client: inv.clientName || inv.clientId || 'Unknown',
    action:
      inv.status === 'confirmed' ? 'Invoice confirmed via WhatsApp' :
      inv.status === 'pending'   ? 'Invoice uploaded — awaiting review' :
      'Invoice rejected',
    amount: `₹${(inv.total || 0).toLocaleString('en-IN')}`,
    time:   (inv.date || '').slice(0, 10),
    status: inv.status === 'confirmed' ? 'success' : inv.status === 'pending' ? 'warning' : 'danger',
  }));

  // AI Deadline Risk — derived from real clients
  const deadlinePredictions = clients.map((c: any) => ({
    client:      c.name,
    probability: c.riskScore,
    risk:        c.riskScore < 40 ? 'high' : c.riskScore < 70 ? 'medium' : 'low',
  }));

  // ITC Trend — grouped by month from real invoices
  const monthMap: Record<string, number> = {};
  invoices.forEach((inv: any) => {
    const month = (inv.date || '').slice(0, 7);
    if (month) monthMap[month] = (monthMap[month] || 0) + (inv.itc || 0);
  });
  const itcTrendData = Object.entries(monthMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-6)
    .map(([month, itc]) => ({ month: month.slice(5), itc: Math.round(itc as number) }));

  // Client Risk Distribution — from real clients
  const compliant = clients.filter((c: any) => c.complianceStatus === 'compliant').length;
  const attention = clients.filter((c: any) => c.complianceStatus === 'attention').length;
  const atRisk    = clients.filter((c: any) => c.complianceStatus === 'at-risk').length;
  const clientRiskData = [
    { name: 'Compliant', value: compliant, color: 'hsl(160,84%,39%)' },
    { name: 'Attention', value: attention, color: 'hsl(38,92%,50%)' },
    { name: 'At Risk',   value: atRisk,    color: 'hsl(0,84%,60%)' },
  ].filter(d => d.value > 0);

  return (
    <AppLayout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground">{getGreeting()}, CA 👋</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {getFilingPeriod()} · {statsLoading ? 'Loading...' : '● Live Data'}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPICard icon="💰" label="Total ITC Saved"      value="" numericValue={stats ? stats.total_itc       : 0} prefix="₹" subtitle={statsLoading ? 'Loading...' : 'This month'}                        subtitleColor="success"     delay={0}   />
        <KPICard icon="📄" label="Invoices Processed"   value="" numericValue={stats ? stats.total_invoices  : 0}            subtitle={stats ? `${stats.pending_invoices} pending review` : 'Loading...'} subtitleColor="warning"     delay={100} />
        <KPICard icon="👥" label="Total Clients"        value="" numericValue={stats ? stats.total_clients   : 0}            subtitle="Registered users"                                                    subtitleColor="success"     delay={200} />
        <KPICard icon="⚠️" label="Pending Invoices"     value="" numericValue={stats ? stats.pending_invoices : 0}           subtitle="Need CA review"                                                      subtitleColor="destructive" delay={300} glowColor="glow-destructive" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        {/* ITC Trend */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">ITC Trend</h3>
          {itcTrendData.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-16">No invoice data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={itcTrendData}>
                <defs>
                  <linearGradient id="itcGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="hsl(239,84%,67%)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="hsl(239,84%,67%)" stopOpacity={0}   />
                  </linearGradient>
                </defs>
                <XAxis dataKey="month" stroke="hsl(215,16%,47%)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="hsl(215,16%,47%)" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#111', border: '1px solid #1a1a1a', borderRadius: '8px', fontSize: '12px', color: '#f8fafc' }}
                  formatter={(v: number) => [`₹${v.toLocaleString('en-IN')}`, 'ITC']}
                />
                <Area type="monotone" dataKey="itc" stroke="hsl(239,84%,67%)" fill="url(#itcGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Client Risk Distribution */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Client Risk Distribution</h3>
          {clientRiskData.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-16">No client data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={clientRiskData} cx="50%" cy="50%" innerRadius={55} outerRadius={80} dataKey="value" paddingAngle={4}>
                  {clientRiskData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Legend formatter={(value) => <span style={{ color: '#f8fafc', fontSize: '12px' }}>{value}</span>} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="text-center -mt-2">
            <span className="text-xs text-muted-foreground">{clients.length} Total Clients</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        {/* WhatsApp Activity */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">📱 WhatsApp Activity Feed</h3>
          {whatsappActivity.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-8">No activity yet. Send an invoice on WhatsApp.</p>
          ) : (
            <div className="space-y-3">
              {whatsappActivity.map((item: any, i: number) => (
                <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors duration-200">
                  <div className={cn('w-2 h-2 rounded-full mt-1.5 flex-shrink-0', statusDot[item.status])} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-medium text-foreground">{item.client}</span>
                      {item.amount && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-accent/20 text-accent-val">{item.amount}</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{item.action}</p>
                  </div>
                  <span className="text-[10px] text-muted-foreground flex-shrink-0">{item.time}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Deadline Risk */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-foreground mb-1">🧠 AI Deadline Risk</h3>
          <p className="text-xs text-muted-foreground mb-4">Based on client risk scores</p>
          {deadlinePredictions.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-8">No client data yet.</p>
          ) : (
            <div className="space-y-4">
              {deadlinePredictions.map((item: any, i: number) => (
                <div key={i}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-medium text-foreground">{item.client}</span>
                    <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-full', riskBg[item.risk], riskColors[item.risk])}>
                      {item.probability}% — {item.risk === 'high' ? 'HIGH RISK' : item.risk === 'medium' ? 'MEDIUM' : 'ON TRACK'}
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all duration-1000',
                        item.risk === 'high' ? 'bg-destructive' : item.risk === 'medium' ? 'bg-warning' : 'bg-success')}
                      style={{ width: `${item.probability}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-muted-foreground mt-4">Based on invoice upload velocity</p>
        </div>
      </div>

      {/* Recent Invoices */}
      <div className="card-surface p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-foreground">Recent Invoices</h3>
          {invoicesLoading  && <span className="text-xs text-muted-foreground animate-pulse">Loading...</span>}
          {!invoicesLoading && <span className="text-xs text-success-val">● Live — {invoices.length} invoices</span>}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium">Client</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium">Invoice No</th>
                <th className="text-right py-2.5 px-3 text-muted-foreground font-medium">Amount</th>
                <th className="text-right py-2.5 px-3 text-muted-foreground font-medium">ITC</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium">Category</th>
                <th className="text-left py-2.5 px-3 text-muted-foreground font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {recentInvoices.length === 0 && !invoicesLoading && (
                <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">No invoices yet. Send an invoice on WhatsApp to get started.</td></tr>
              )}
              {recentInvoices.map((inv: any) => (
                <tr key={inv.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors duration-200">
                  <td className="py-2.5 px-3 text-foreground font-medium">{inv.clientName || 'Unknown'}</td>
                  <td className="py-2.5 px-3 font-mono text-muted-foreground">{inv.invoiceNo || '—'}</td>
                  <td className="py-2.5 px-3 text-right text-foreground">₹{(inv.total || 0).toLocaleString('en-IN')}</td>
                  <td className="py-2.5 px-3 text-right text-accent-val font-semibold">₹{(inv.itc || 0).toLocaleString('en-IN')}</td>
                  <td className="py-2.5 px-3">
                    <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium',
                      categoryColors[inv.aiCategory] || 'bg-muted text-muted-foreground')}>
                      {inv.aiCategory || 'General'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium capitalize',
                      statusBadge[inv.status] || 'bg-muted text-muted-foreground')}>
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppLayout>
  );
};

export default DashboardPage;