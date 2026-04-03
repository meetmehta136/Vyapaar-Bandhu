import { useEffect, useState } from 'react';
import AppLayout from '@/components/AppLayout';
import { getClients, getInvoices } from '@/lib/api';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const COLORS = ['hsl(239,84%,67%)', 'hsl(38,92%,50%)', 'hsl(160,84%,39%)', 'hsl(0,84%,60%)', 'hsl(280,84%,67%)'];
const tooltip = { background: '#111', border: '1px solid #1a1a1a', borderRadius: '8px', fontSize: '11px', color: '#f8fafc' };

const AnalyticsPage = () => {
  const [clients, setClients] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getClients(), getInvoices()]).then(([c, inv]) => {
      setClients(c || []);
      setInvoices(inv || []);
      setLoading(false);
    });
  }, []);

  const totalItc = clients.reduce((s: number, c: any) => s + (c.itcThisMonth || 0), 0);
  const avgRisk = clients.length > 0 ? Math.round(clients.reduce((s: number, c: any) => s + (c.riskScore || 0), 0) / clients.length) : 0;
  const topClients = [...clients].sort((a, b) => (b.itcThisMonth || 0) - (a.itcThisMonth || 0));

  // Category distribution from real invoices
  const categoryMap: Record<string, number> = {};
  invoices.forEach((inv: any) => {
    const cat = inv.aiCategory || 'General';
    categoryMap[cat] = (categoryMap[cat] || 0) + 1;
  });
  const categoryDistribution = Object.entries(categoryMap).map(([name, value], i) => ({ name, value, color: COLORS[i % COLORS.length] }));

  // ITC by state from real clients
  const stateMap: Record<string, number> = {};
  clients.forEach((c: any) => {
    const state = c.state || 'Unknown';
    stateMap[state] = (stateMap[state] || 0) + (c.itcThisMonth || 0);
  });
  const itcByState = Object.entries(stateMap).map(([state, itc]) => ({ state, itc }));

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64 text-muted-foreground animate-pulse text-sm">
        Loading analytics from live database...
      </div>
    </AppLayout>
  );

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">📈 Analytics</h1>
          <p className="text-xs text-success-val mt-1">● Live data — {clients.length} clients, {invoices.length} invoices</p>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Clients', value: clients.length },
          { label: 'Total Invoices', value: invoices.length },
          { label: 'ITC Facilitated', value: `₹${totalItc.toLocaleString('en-IN')}` },
          { label: 'Avg Risk Score', value: `${avgRisk}/100` },
        ].map((s) => (
          <div key={s.label} className="card-surface p-4">
            <div className="text-xl font-bold text-foreground">{s.value}</div>
            <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Top Clients by ITC */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Top Clients by ITC</h3>
          {topClients.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-8">No client data yet</p>
          ) : (
            <div className="space-y-2">
              {topClients.slice(0, 6).map((c: any, i: number) => (
                <div key={c.id} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-muted-foreground w-5">#{i + 1}</span>
                    <span className="text-xs text-foreground font-medium">{c.name}</span>
                  </div>
                  <span className="text-xs text-accent-val font-semibold">₹{(c.itcThisMonth || 0).toLocaleString('en-IN')}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Category Distribution */}
        <div className="card-surface p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Invoice Category Distribution</h3>
          {categoryDistribution.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-8">No invoice data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={categoryDistribution} cx="50%" cy="50%" outerRadius={70} dataKey="value" paddingAngle={2}>
                  {categoryDistribution.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Legend formatter={(value) => <span style={{ color: '#94a3b8', fontSize: '10px' }}>{value}</span>} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ITC by State */}
      <div className="card-surface p-5 mb-6">
        <h3 className="text-sm font-semibold text-foreground mb-4">ITC by State</h3>
        {itcByState.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No state data yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={itcByState} layout="vertical">
              <XAxis type="number" stroke="hsl(215,16%,47%)" fontSize={10} tickLine={false} axisLine={false} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
              <YAxis dataKey="state" type="category" stroke="hsl(215,16%,47%)" fontSize={10} tickLine={false} axisLine={false} width={80} />
              <Tooltip contentStyle={tooltip} formatter={(v: number) => [`₹${v.toLocaleString('en-IN')}`, 'ITC']} />
              <Bar dataKey="itc" radius={[0, 6, 6, 0]} fill="hsl(38,92%,50%)" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </AppLayout>
  );
};

export default AnalyticsPage;