import { useEffect, useState } from 'react';
import AppLayout from '@/components/AppLayout';
import KPICard from '@/components/KPICard';
import { useAuth } from '@/contexts/AuthContext';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { cn } from '@/lib/utils';
import { useDashboardStats, useInvoices } from '@/hooks/useAPI';
import { getClients } from '@/lib/api';

/* ─── helpers ─────────────────────────────────────────────── */
const getGreeting = () => {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
};

const getFilingPeriod = () =>
  new Date().toLocaleString('en-IN', { month: 'long', year: 'numeric' }) +
  ' · Filing Period';

const BASE_URL = (import.meta as any).env?.VITE_API_URL || 'https://vyapaar-bandhu-h53q.onrender.com';

const categoryColors: Record<string, string> = {
  Electronics: 'bg-blue-100 text-blue-800',
  Office:      'bg-emerald-100 text-emerald-800',
  Food:        'bg-amber-100 text-amber-800',
  Pharma:      'bg-emerald-100 text-emerald-800',
  Vehicle:     'bg-red-100 text-red-800',
  Clothing:    'bg-red-100 text-red-800',
  Travel:      'bg-blue-100 text-blue-800',
  General:     'bg-gray-100 text-gray-700',
  Other:       'bg-gray-100 text-gray-700',
};

const statusBadge: Record<string, string> = {
  confirmed: 'bg-emerald-100 text-emerald-800',
  pending:   'bg-amber-100 text-amber-800',
  rejected:  'bg-red-100 text-red-800',
};

const statusDot: Record<string, string> = {
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger:  'bg-red-600',
};

const riskColors: Record<string, string> = {
  high:   'text-red-700',
  medium: 'text-amber-700',
  low:    'text-emerald-700',
};

const riskBg: Record<string, string> = {
  high:   'bg-red-100',
  medium: 'bg-amber-100',
  low:    'bg-emerald-100',
};

/* ─── skeleton row ─────────────────────────────────────────── */
const SkeletonRow = () => (
  <tr className="border-b border-gray-100">
    {[1, 2, 3, 4, 5, 6].map(i => (
      <td key={i} className="py-3 px-3">
        <div className="skeleton h-3 rounded" style={{ width: `${50 + i * 8}%` }} />
      </td>
    ))}
  </tr>
);

const SkeletonBar = ({ w = '100%' }: { w?: string }) => (
  <div className="flex items-center justify-between py-2.5 border-b border-gray-100">
    <div className="flex items-center gap-3 flex-1">
      <div className="skeleton w-2.5 h-2.5 rounded-full flex-shrink-0" />
      <div className="skeleton h-3 rounded flex-1" style={{ maxWidth: w }} />
    </div>
    <div className="skeleton h-3 w-12 rounded ml-4" />
  </div>
);

/* ─── custom tooltip ───────────────────────────────────────── */
const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-gray-600 mb-1">{label}</div>
      <div className="font-bold text-gray-900 font-display">
        ₹{Number(payload[0].value).toLocaleString('en-IN')}
      </div>
    </div>
  );
};

/* ─── main component ───────────────────────────────────────── */
const DashboardPage = () => {
  const { data: stats, loading: statsLoading } = useDashboardStats();
  const { data: invoicesData, loading: invoicesLoading } = useInvoices();
  const { caProfile, token } = useAuth();
  const [clients, setClients]     = useState<any[]>([]);
  const [gstr3bLoading, setGstr3bLoading] = useState(false);
  const [gstr3bError,   setGstr3bError]   = useState('');

  const caFirstName = (caProfile?.name || 'CA')
    .replace(/^CA\s+/i, '')
    .split(' ')[0];

  /* fetch clients */
  useEffect(() => {
    getClients().then(c => setClients(Array.isArray(c) ? c : (c as any)?.clients ?? []));
  }, []);

  /* ── GSTR-3B download (JWT included) ── */
  const downloadGSTR3B = async () => {
    setGstr3bLoading(true);
    setGstr3bError('');
    try {
      const period = new Date().toISOString().slice(0, 7);
      const res = await fetch(`${BASE_URL}/compliance/gstr3b-json/${period}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
      const url  = URL.createObjectURL(blob);
      const a    = Object.assign(document.createElement('a'), { href: url, download: `GSTR3B_${period}.json` });
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); URL.revokeObjectURL(url);
    } catch {
      setGstr3bError('Download failed. Try again.');
    } finally {
      setGstr3bLoading(false);
    }
  };

  /* ── derived data ── */
  const invoices      = Array.isArray(invoicesData) ? invoicesData : (invoicesData as any)?.invoices ?? (invoicesData as any)?.items ?? [];
  const recentInvoices = invoices.slice(0, 6);

  const whatsappActivity = invoices.slice(0, 6).map((inv: any) => ({
    client: inv.clientName || 'Unknown',
    action: inv.status === 'confirmed' ? 'Invoice confirmed' :
            inv.status === 'pending'   ? 'Awaiting review'  : 'Invoice rejected',
    amount: `₹${(inv.total || 0).toLocaleString('en-IN')}`,
    time:   (inv.date || '').slice(0, 10),
    status: inv.status === 'confirmed' ? 'success' : inv.status === 'pending' ? 'warning' : 'danger',
  }));

  const deadlinePredictions = clients.map((c: any) => ({
    client:      c.name,
    probability: c.riskScore,
    risk:        c.riskScore < 40 ? 'high' : c.riskScore < 70 ? 'medium' : 'low',
  }));

  const monthMap: Record<string, number> = {};
  invoices.forEach((inv: any) => {
    const month = (inv.date || '').slice(0, 7);
    if (month) monthMap[month] = (monthMap[month] || 0) + (inv.itc || 0);
  });
  const itcTrendData = Object.entries(monthMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-6)
    .map(([month, itc]) => ({ month: month.slice(5), itc: Math.round(itc as number) }));

  const compliant = clients.filter((c: any) => c.complianceStatus === 'compliant').length;
  const attention = clients.filter((c: any) => c.complianceStatus === 'attention').length;
  const atRisk    = clients.filter((c: any) => c.complianceStatus === 'at-risk').length;
  const clientRiskData = [
    { name: 'Compliant', value: compliant, color: '#10b981' },
    { name: 'Attention', value: attention, color: '#f59e0b' },
    { name: 'At Risk',   value: atRisk,    color: '#ef4444' },
  ].filter(d => d.value > 0);

  /* ── AI classification ── */
  const catMap: Record<string, { count: number; itc: number }> = {};
  invoices.forEach((inv: any) => {
    const cat = inv.aiCategory || 'General';
    if (!catMap[cat]) catMap[cat] = { count: 0, itc: 0 };
    catMap[cat].count += 1;
    catMap[cat].itc   += inv.itc || 0;
  });
  const catEntries = Object.entries(catMap).sort((a, b) => b[1].itc - a[1].itc);
  const avgConf = invoices.length > 0
    ? Math.round(invoices.reduce((s: number, i: any) => s + (i.aiConfidence || 0), 0) / invoices.length * 100)
    : 0;

  /* ─────────────────────────────────── RENDER ───── */
  return (
    <AppLayout>

      {/* ── Hero header ── */}
      <div className="mb-8 flex items-start justify-between flex-wrap gap-4 animate-slide-up">
        <div>
          <p className="text-xs text-gray-500 font-medium tracking-widest uppercase mb-1">
            {getFilingPeriod()}
          </p>
          <h1 className="text-3xl font-bold text-gray-900 font-display">
            {getGreeting()},{' '}
            <span className="gradient-text-primary">{caFirstName}</span> 👋
          </h1>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="live-dot w-2 h-2 rounded-full bg-emerald-500 inline-block" />
            <span className="text-xs text-emerald-700 font-medium">Live Data</span>
            {invoices.length > 0 && (
              <span className="text-xs text-gray-500">· {invoices.length} invoices synced</span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1">
          <button
            onClick={downloadGSTR3B}
            disabled={gstr3bLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold font-display transition-all duration-200
              bg-blue-100 text-blue-700 border border-blue-200 hover:bg-blue-200 hover:border-blue-300
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {gstr3bLoading ? (
              <>
                <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
                Generating...
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                GSTR-3B JSON
              </>
            )}
          </button>
          {gstr3bError && <p className="text-[11px] text-red-600">{gstr3bError}</p>}
        </div>
      </div>

      {/* ── KPI cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPICard
          icon="💰" label="Total ITC Saved"
          numericValue={stats?.total_itc ?? 0} prefix="₹"
          subtitle="Auto-computed this month"
          subtitleColor="success" accentColor="success"
          delay={0} loading={statsLoading}
        />
        <KPICard
          icon="📄" label="Invoices Processed"
          numericValue={stats?.total_invoices ?? 0}
          subtitle={stats ? `${stats.pending_invoices} pending review` : '—'}
          subtitleColor="warning" accentColor="primary"
          delay={80} loading={statsLoading}
        />
        <KPICard
          icon="👥" label="Total Clients"
          numericValue={stats?.total_clients ?? 0}
          subtitle="Active registrations"
          subtitleColor="muted" accentColor="primary"
          delay={160} loading={statsLoading}
        />
        <KPICard
          icon="⚠️" label="Pending Review"
          numericValue={stats?.pending_invoices ?? 0}
          subtitle="Needs CA action"
          subtitleColor="destructive" accentColor="destructive"
          delay={240} loading={statsLoading}
        />
      </div>

      {/* ── AI Classification (MOAT — show it first) ── */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 mb-6">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <h3 className="text-sm font-bold text-gray-900 font-display">AI Classification Engine</h3>
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-display tracking-widest">
                IndicBERT
              </span>
            </div>
            <p className="text-[11px] text-gray-500">
              Every invoice auto-classified for ITC eligibility
            </p>
          </div>
          {invoices.length > 0 && (
            <div className="flex gap-3">
              <div className="text-center px-3 py-1.5 rounded-lg bg-gray-50">
                <div className="text-base font-bold text-gray-900 font-display">{avgConf}%</div>
                <div className="text-[10px] text-gray-600">Avg confidence</div>
              </div>
              <div className="text-center px-3 py-1.5 rounded-lg bg-gray-50">
                <div className="text-base font-bold text-gray-900 font-display">{catEntries.length}</div>
                <div className="text-[10px] text-gray-600">Categories</div>
              </div>
            </div>
          )}
        </div>

        {catEntries.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-6">
            No invoices yet — send one on WhatsApp to activate AI classification.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {catEntries.map(([cat, data]) => {
              const blocked = ['Food & Beverages', 'Food (Blocked)', 'Personal Vehicle', 'Blocked'].includes(cat);
              return (
                <div key={cat}
                  className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200 hover:border-gray-300 transition-colors">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={cn(
                      'shrink-0 w-1.5 h-1.5 rounded-full',
                      blocked ? 'bg-red-600' : 'bg-emerald-600'
                    )} />
                    <span className={cn(
                      'text-xs font-medium px-2 py-0.5 rounded-lg truncate font-display',
                      blocked ? 'bg-red-100 text-red-800 line-through' : categoryColors[cat] || 'bg-gray-200 text-gray-700'
                    )}>
                      {cat}
                    </span>
                    <span className="text-[10px] text-gray-600 shrink-0">{data.count}×</span>
                  </div>
                  <div className="text-right shrink-0 ml-2">
                    <div className={cn('text-xs font-bold font-display', blocked ? 'text-red-600 line-through' : 'text-emerald-700')}>
                      ₹{data.itc.toLocaleString('en-IN')}
                    </div>
                    <div className="text-[9px] text-gray-600">{blocked ? 'blocked' : 'ITC'}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">

        {/* ITC Trend */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-gray-900 font-display mb-1">ITC Trend</h3>
          <p className="text-[11px] text-gray-500 mb-4">Monthly input tax credit flow</p>
          {itcTrendData.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <p className="text-xs text-gray-500">No data yet</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={210}>
              <AreaChart data={itcTrendData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="itcGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#2563eb" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#2563eb" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <XAxis dataKey="month" stroke="#9ca3af" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#9ca3af" fontSize={10} tickLine={false} axisLine={false}
                  tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="itc" stroke="#2563eb"
                  fill="url(#itcGrad)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Client Risk */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-gray-900 font-display mb-1">Client Risk Distribution</h3>
          <p className="text-[11px] text-gray-500 mb-4">Compliance status across all clients</p>
          {clientRiskData.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <p className="text-xs text-gray-500">No clients yet</p>
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={175}>
                <PieChart>
                  <Pie data={clientRiskData} cx="50%" cy="50%"
                    innerRadius={52} outerRadius={74} dataKey="value" paddingAngle={5} strokeWidth={0}>
                    {clientRiskData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Legend
                    formatter={v => <span style={{ color: '#6b7280', fontSize: '11px', fontFamily: 'Outfit' }}>{v}</span>}
                    wrapperStyle={{ paddingTop: '8px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <p className="text-center text-[11px] text-gray-600 -mt-1">{clients.length} Total Clients</p>
            </>
          )}
        </div>
      </div>

      {/* ── Activity + AI Risk ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">

        {/* WhatsApp Activity */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-gray-900 font-display mb-1">📱 WhatsApp Activity</h3>
          <p className="text-[11px] text-gray-500 mb-4">Real-time invoice feed from clients</p>
          {whatsappActivity.length === 0 ? (
            <>
              <SkeletonBar w="70%" />
              <SkeletonBar w="55%" />
              <SkeletonBar w="80%" />
              <p className="text-[10px] text-gray-500 text-center mt-3">Send an invoice on WhatsApp to populate</p>
            </>
          ) : (
            <div className="space-y-2">
              {whatsappActivity.map((item: any, i: number) => (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
                  <div className={cn('w-2 h-2 rounded-full flex-shrink-0', statusDot[item.status])} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold text-gray-900 font-display">{item.client}</span>
                      <span className="text-[10px] font-mono-dm px-1.5 py-0.5 rounded-lg bg-blue-100 text-blue-800">
                        {item.amount}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-600 mt-0.5">{item.action}</p>
                  </div>
                  <span className="text-[10px] text-gray-500 flex-shrink-0 font-mono-dm">{item.time}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Deadline Risk */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-gray-900 font-display mb-1">🧠 AI Deadline Risk</h3>
          <p className="text-[11px] text-gray-500 mb-4">Predicted filing risk per client</p>
          {deadlinePredictions.length === 0 ? (
            <>
              {[80, 60, 45].map((w, i) => (
                <div key={i} className="mb-3">
                  <div className="skeleton h-3 w-32 rounded mb-1.5" />
                  <div className="skeleton h-2 rounded-full" style={{ width: `${w}%` }} />
                </div>
              ))}
            </>
          ) : (
            <div className="space-y-3">
              {deadlinePredictions.map((item: any, i: number) => (
                <div key={i}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-gray-900 font-display">{item.client}</span>
                    <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-lg font-display', riskBg[item.risk], riskColors[item.risk])}>
                      {item.probability}% · {item.risk === 'high' ? 'HIGH' : item.risk === 'medium' ? 'MEDIUM' : 'ON TRACK'}
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all duration-1000',
                        item.risk === 'high' ? 'bg-red-600' : item.risk === 'medium' ? 'bg-amber-500' : 'bg-emerald-600')}
                      style={{ width: `${item.probability}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-gray-600 mt-4">Based on invoice upload velocity</p>
        </div>
      </div>

      {/* ── Recent Invoices ── */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-gray-900 font-display">Recent Invoices</h3>
            <p className="text-[11px] text-gray-500">Latest uploads from all clients</p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn('w-1.5 h-1.5 rounded-full', invoicesLoading ? 'bg-amber-500 animate-pulse' : 'bg-emerald-600')} />
            <span className="text-[11px] text-gray-600 font-medium">
              {invoicesLoading ? 'Syncing...' : `${invoices.length} total`}
            </span>
          </div>
        </div>

        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                {['Client', 'Invoice No', 'Amount', 'ITC', 'Category', 'Status'].map((h, i) => (
                  <th key={h} className={cn(
                    'py-2.5 px-3 text-[10px] text-gray-600 font-semibold uppercase tracking-widest font-display whitespace-nowrap',
                    i >= 2 && i <= 3 ? 'text-right' : 'text-left'
                  )}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {invoicesLoading && [1,2,3,4].map(i => <SkeletonRow key={i} />)}
              {!invoicesLoading && recentInvoices.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-xs text-gray-500">
                    No invoices yet — send one via WhatsApp to get started.
                  </td>
                </tr>
              )}
              {!invoicesLoading && recentInvoices.map((inv: any) => (
                <tr key={inv.id}
                  className="border-b border-gray-100 hover:bg-blue-50/50 transition-colors duration-150 group">
                  <td className="py-3 px-3 font-semibold text-gray-900 font-display whitespace-nowrap">
                    {inv.clientName || 'Unknown'}
                  </td>
                  <td className="py-3 px-3 font-mono-dm text-gray-600 text-[11px]">
                    {inv.invoiceNo || '—'}
                  </td>
                  <td className="py-3 px-3 text-right font-semibold text-gray-900 font-display">
                    ₹{(inv.total || 0).toLocaleString('en-IN')}
                  </td>
                  <td className="py-3 px-3 text-right font-bold text-emerald-700 font-display">
                    ₹{(inv.itc || 0).toLocaleString('en-IN')}
                  </td>
                  <td className="py-3 px-3">
                    <span className={cn('px-2 py-0.5 rounded-lg text-[10px] font-bold font-display whitespace-nowrap',
                      categoryColors[inv.aiCategory] || 'bg-gray-100 text-gray-700')}>
                      {inv.aiCategory || 'General'}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span className={cn('px-2 py-0.5 rounded-lg text-[10px] font-bold font-display capitalize whitespace-nowrap',
                      statusBadge[inv.status] || 'bg-gray-100 text-gray-700')}>
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

