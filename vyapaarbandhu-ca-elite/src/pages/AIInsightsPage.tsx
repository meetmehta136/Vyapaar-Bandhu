import { useEffect, useState } from 'react';
import AppLayout from '@/components/AppLayout';
import { getInvoices, getClients } from '@/lib/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const sevColor: Record<string, string> = {
  high: 'bg-destructive/20 text-destructive-val',
  medium: 'bg-warning/20 text-warning-val',
  low: 'bg-primary/20 text-primary-val',
};

const BLOCKED_CATEGORIES = ['Food & Beverages', 'Food (Blocked)', 'Personal Vehicle'];

const AIInsightsPage = () => {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getInvoices(), getClients()]).then(([inv, cli]) => {
      setInvoices(inv || []);
      setClients(cli || []);
      setLoading(false);
    });
  }, []);

  // ITC Leakage — real blocked invoices from DB
  const blockedInvoices = invoices.filter((inv: any) => BLOCKED_CATEGORIES.includes(inv.aiCategory));
  const totalLeakage = blockedInvoices.reduce((s: number, inv: any) => s + (inv.itc || 0), 0);

  const leakageByCategory: Record<string, number> = {};
  blockedInvoices.forEach((inv: any) => {
    leakageByCategory[inv.aiCategory] = (leakageByCategory[inv.aiCategory] || 0) + (inv.itc || 0);
  });
  const leakageCategoryData = Object.entries(leakageByCategory).map(([category, amount]) => ({ category, amount }));

  const leakageByClient: Record<string, number> = {};
  blockedInvoices.forEach((inv: any) => {
    const name = inv.clientName || 'Unknown';
    leakageByClient[name] = (leakageByClient[name] || 0) + (inv.itc || 0);
  });
  const leakageClientData = Object.entries(leakageByClient).map(([client, amount]) => ({ client, amount }));

  // Supplier Risk — real GSTINs from invoices
  const supplierMap: Record<string, { times: number; totalItc: number; state: string }> = {};
  invoices.forEach((inv: any) => {
    const gstin = inv.supplierGstin || 'Unknown';
    if (!supplierMap[gstin]) supplierMap[gstin] = { times: 0, totalItc: 0, state: gstin.length >= 2 ? gstin.slice(0, 2) : '?' };
    supplierMap[gstin].times += 1;
    supplierMap[gstin].totalItc += inv.itc || 0;
  });
  const suppliers = Object.entries(supplierMap).map(([gstin, data]) => ({
    gstin,
    ...data,
    valid: gstin.length === 15,
  }));
  const invalidCount = suppliers.filter(s => !s.valid).length;
  const riskItc = suppliers.filter(s => !s.valid).reduce((s, sup) => s + sup.totalItc, 0);

  // Anomalies — real detection from invoice data
  const avgTotal = invoices.length > 0 ? invoices.reduce((s: number, i: any) => s + (i.total || 0), 0) / invoices.length : 0;
  const anomalies = invoices
    .filter((inv: any) => (inv.total || 0) > avgTotal * 2.5)
    .slice(0, 5)
    .map((inv: any) => ({
      client: inv.clientName || 'Unknown',
      invoice: `₹${(inv.total || 0).toLocaleString('en-IN')}`,
      detail: `${((inv.total || 0) / avgTotal).toFixed(1)}x higher than average invoice value`,
      severity: (inv.total || 0) > avgTotal * 4 ? 'high' : 'medium',
    }));

  // At-risk clients from DB
  const atRiskClients = clients.filter((c: any) => c.complianceStatus === 'at-risk' || c.riskScore < 40);

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64 text-muted-foreground animate-pulse text-sm">
        Running AI analysis on live data...
      </div>
    </AppLayout>
  );

  return (
    <AppLayout>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="text-2xl font-bold text-foreground">⚡ AI Insights</h1>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/20 text-primary-val">LIVE</span>
      </div>
      <p className="text-sm text-muted-foreground mb-8">
        Analysis based on {invoices.length} real invoices from {clients.length} clients
      </p>

      {/* ITC Leakage */}
      <div className="card-surface p-6 mb-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">📉 ITC Leakage Report</h2>
        {totalLeakage === 0 ? (
          <div className="p-3 rounded-lg bg-success/10 border border-success/30">
            <span className="text-sm font-bold text-success-val">₹0 leakage detected</span>
            <span className="text-xs text-muted-foreground ml-2">No blocked category invoices found</span>
          </div>
        ) : (
          <>
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 mb-5">
              <span className="text-sm font-bold text-destructive-val">₹{totalLeakage.toLocaleString('en-IN')}</span>
              <span className="text-xs text-muted-foreground ml-2">lost to Section 17(5) this month</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-3">By Category</h4>
                {leakageCategoryData.map((l) => (
                  <div key={l.category} className="flex justify-between py-2 border-b border-border/30">
                    <span className="text-xs text-foreground">{l.category}</span>
                    <span className="text-xs text-destructive-val font-semibold">₹{l.amount.toLocaleString('en-IN')}</span>
                  </div>
                ))}
              </div>
              {leakageClientData.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-3">By Client</h4>
                  <ResponsiveContainer width="100%" height={140}>
                    <BarChart data={leakageClientData}>
                      <XAxis dataKey="client" stroke="hsl(215,16%,47%)" fontSize={10} tickLine={false} axisLine={false} />
                      <YAxis stroke="hsl(215,16%,47%)" fontSize={10} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={{ background: '#111', border: '1px solid #1a1a1a', borderRadius: '8px', fontSize: '11px', color: '#f8fafc' }} />
                      <Bar dataKey="amount" radius={[4, 4, 0, 0]} fill="hsl(0,84%,60%)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Supplier Risk */}
      <div className="card-surface p-6 mb-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">🔍 Supplier Risk Analysis</h2>
        {suppliers.length === 0 ? (
          <p className="text-xs text-muted-foreground">No supplier data yet — upload invoices via WhatsApp.</p>
        ) : (
          <>
            <div className={`p-3 rounded-lg mb-5 ${invalidCount > 0 ? 'bg-warning/10 border border-warning/30' : 'bg-success/10 border border-success/30'}`}>
              <span className={`text-sm font-bold ${invalidCount > 0 ? 'text-warning-val' : 'text-success-val'}`}>
                {invalidCount > 0 ? `${invalidCount} suppliers with invalid GSTINs` : 'All supplier GSTINs valid'}
              </span>
              {invalidCount > 0 && <span className="text-xs text-muted-foreground ml-2">₹{riskItc.toLocaleString('en-IN')} ITC at risk</span>}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 text-muted-foreground font-medium">GSTIN</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Times Invoiced</th>
                    <th className="text-right py-2 px-3 text-muted-foreground font-medium">Total ITC</th>
                    <th className="text-left py-2 px-3 text-muted-foreground font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.slice(0, 8).map((s, i) => (
                    <tr key={i} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="py-2 px-3 font-mono text-muted-foreground">{s.gstin}</td>
                      <td className="py-2 px-3 text-right text-foreground">{s.times}</td>
                      <td className="py-2 px-3 text-right text-accent-val">₹{s.totalItc.toLocaleString('en-IN')}</td>
                      <td className="py-2 px-3">
                        <span className={s.valid ? 'text-success-val' : 'text-destructive-val font-semibold'}>{s.valid ? '✓ Valid' : '✗ Invalid'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* Anomalies */}
      <div className="card-surface p-6 mb-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">🚨 Invoice Anomaly Detection</h2>
        {anomalies.length === 0 ? (
          <div className="p-3 rounded-lg bg-success/10 border border-success/30">
            <span className="text-xs text-success-val">No anomalies detected in current invoice data.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies.map((a, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${sevColor[a.severity]}`}>{a.severity}</span>
                <div>
                  <div className="text-xs font-medium text-foreground">{a.client} — {a.invoice}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{a.detail}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* At Risk Clients */}
      <div className="card-surface p-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">⚠️ At-Risk Clients</h2>
        {atRiskClients.length === 0 ? (
          <div className="p-3 rounded-lg bg-success/10 border border-success/30">
            <span className="text-xs text-success-val">All clients are compliant. Great work!</span>
          </div>
        ) : (
          <div className="space-y-3">
            {atRiskClients.map((c: any) => (
              <div key={c.id} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                <div>
                  <div className="text-xs font-medium text-foreground">{c.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">Risk Score: {c.riskScore}/100 · {c.invoiceCount} invoices</div>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-destructive/20 text-destructive-val">at risk</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default AIInsightsPage;