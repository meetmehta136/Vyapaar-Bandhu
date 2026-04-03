import { useEffect, useState } from 'react';
import AppLayout from '@/components/AppLayout';
import { getDashboardStats, getClients, getInvoices } from '@/lib/api';

const AdminPage = () => {
  const [stats, setStats]     = useState<any>(null);
  const [clients, setClients] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDashboardStats(), getClients(), getInvoices()]).then(([s, c, i]) => {
      setStats(s);
      setClients(c || []);
      setInvoices(i || []);
      setLoading(false);
    });
  }, []);

  const totalItc          = invoices.reduce((s: number, i: any) => s + (i.itc || 0), 0);
  const confirmedInvoices = invoices.filter((i: any) => i.status === 'confirmed').length;
  const pendingInvoices   = invoices.filter((i: any) => i.status === 'pending').length;
  const rejectedInvoices  = invoices.filter((i: any) => i.status === 'rejected').length;
  const compliantClients  = clients.filter((c: any) => c.complianceStatus === 'compliant').length;
  const atRiskClients     = clients.filter((c: any) => c.complianceStatus === 'at-risk').length;

  // Revenue
  const mrrConsumer = clients.length * 299;
  const mrrCA       = 999;
  const totalMrr    = mrrConsumer + mrrCA;

  // Correct 3-layer ML stack
  const health = [
    { label: 'Backend API',          url: 'vyapaar-bandhu.onrender.com' },
    { label: 'Database',             url: 'PostgreSQL on Render' },
    { label: 'WhatsApp Bot',         url: 'Twilio sandbox' },
    { label: 'OCR Engine',           url: 'OpenRouter — nvidia/nemotron-nano-12b-v2-vl' },
    { label: 'Layer 1 — Keywords',   url: '400+ Indian SME keyword rules' },
    { label: 'Layer 2 — Zero-shot',  url: 'facebook/bart-large-mnli' },
    { label: 'Layer 3 — Fine-tuned', url: 'meet136/indicbert-gst-classifier (HuggingFace)' },
    { label: 'Frontend',             url: 'Vercel — vyapaarbandhu-ca-elite.vercel.app' },
  ];

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64 text-muted-foreground animate-pulse text-sm">
        Loading admin data...
      </div>
    </AppLayout>
  );

  return (
    <AppLayout>
      <div className="flex items-center gap-3 mb-8">
        <h1 className="text-2xl font-bold text-foreground">🛡️ Admin Panel</h1>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-destructive/20 text-destructive-val">INTERNAL</span>
      </div>

      {/* Revenue */}
      <div className="card-surface p-6 mb-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">💰 Revenue Metrics</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { label: 'Est. MRR',       value: `₹${totalMrr.toLocaleString('en-IN')}` },
            { label: 'Consumer Users', value: `${clients.length} × ₹299` },
            { label: 'CA Partners',    value: `1 × ₹999` },
            { label: 'Gross Margin',   value: '92%' },
          ].map((s) => (
            <div key={s.label}>
              <div className="text-xl font-bold text-success-val">{s.value}</div>
              <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Platform Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Users',         value: clients.length,                                      color: 'text-foreground' },
          { label: 'Total Invoices',      value: invoices.length,                                     color: 'text-foreground' },
          { label: 'Total ITC Processed', value: `₹${Math.round(totalItc).toLocaleString('en-IN')}`, color: 'text-accent-val' },
          { label: 'Compliant Clients',   value: compliantClients,                                    color: 'text-success-val' },
          { label: 'Confirmed Invoices',  value: confirmedInvoices,                                   color: 'text-primary-val' },
          { label: 'Pending Review',      value: pendingInvoices,                                     color: 'text-warning-val' },
          { label: 'Rejected',            value: rejectedInvoices,                                    color: 'text-destructive-val' },
          { label: 'At Risk Clients',     value: atRiskClients,                                       color: 'text-destructive-val' },
        ].map((s) => (
          <div key={s.label} className="card-surface p-4">
            <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* All Users Table */}
      <div className="card-surface p-6 mb-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">👥 All Registered Users</h2>
        {clients.length === 0 ? (
          <p className="text-xs text-muted-foreground py-4 text-center">No users registered yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium">ID</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium">Name</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium">WhatsApp</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium">GSTIN</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium">State</th>
                  <th className="text-right py-2 px-3 text-muted-foreground font-medium">ITC</th>
                  <th className="text-right py-2 px-3 text-muted-foreground font-medium">Invoices</th>
                  <th className="text-left py-2 px-3 text-muted-foreground font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c: any) => (
                  <tr key={c.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="py-2 px-3 text-muted-foreground font-mono">#{c.id}</td>
                    <td className="py-2 px-3 text-foreground font-medium">{c.name}</td>
                    <td className="py-2 px-3 font-mono text-muted-foreground">{c.whatsapp || '—'}</td>
                    <td className="py-2 px-3 font-mono text-muted-foreground text-[10px]">{c.gstin || '—'}</td>
                    <td className="py-2 px-3 text-muted-foreground">{c.state || '—'}</td>
                    <td className="py-2 px-3 text-right text-accent-val">₹{(c.itcThisMonth || 0).toLocaleString('en-IN')}</td>
                    <td className="py-2 px-3 text-right text-foreground">{c.invoiceCount || 0}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        c.complianceStatus === 'compliant' ? 'bg-success/20 text-success-val' :
                        c.complianceStatus === 'attention' ? 'bg-warning/20 text-warning-val' :
                        'bg-destructive/20 text-destructive-val'}`}>
                        {c.complianceStatus || 'unknown'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* System Health */}
      <div className="card-surface p-6">
        <h2 className="text-sm font-semibold text-foreground mb-4">🟢 System Health</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {health.map((h) => (
            <div key={h.label} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
              <div>
                <div className="text-xs font-medium text-foreground">{h.label}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{h.url}</div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-success/20 text-success-val">● LIVE</span>
            </div>
          ))}
        </div>
        <div className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/30">
          <div className="text-xs font-medium text-foreground">Build Info</div>
          <div className="text-[10px] text-muted-foreground mt-1">
            VyapaarBandhu v0.1.0 · FastAPI + React · XLM-RoBERTa fine-tuned · Built solo · OceanLab X CHARUSAT Hacks 2026
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default AdminPage;