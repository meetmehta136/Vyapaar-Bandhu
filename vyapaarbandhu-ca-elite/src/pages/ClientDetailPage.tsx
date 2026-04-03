import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '@/components/AppLayout';
import KPICard from '@/components/KPICard';
import { clients, invoices } from '@/data/mockData';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend } from 'recharts';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

const categoryColors: Record<string, string> = {
  'Electronics': 'bg-primary/20 text-primary-val',
  'Office Supplies': 'bg-accent/20 text-accent-val',
  'Food & Beverages': 'bg-warning/20 text-warning-val',
  'Pharmaceuticals': 'bg-success/20 text-success-val',
  'Food (Blocked)': 'bg-destructive/20 text-destructive-val',
  'FMCG': 'bg-primary/20 text-primary-val',
  'Textiles': 'bg-accent/20 text-accent-val',
};

const statusBadge: Record<string, string> = {
  confirmed: 'bg-primary/20 text-primary-val',
  pending: 'bg-warning/20 text-warning-val',
  rejected: 'bg-destructive/20 text-destructive-val',
};

const ClientDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const client = clients.find(c => c.id === id);
  const clientInvoices = invoices.filter(inv => inv.clientId === id);

  if (!client) return <AppLayout><div className="text-foreground">Client not found</div></AppLayout>;

  const totalItc = clientInvoices.reduce((s, i) => s + i.itc, 0);
  const totalCgst = clientInvoices.reduce((s, i) => s + i.cgst, 0);
  const totalSgst = clientInvoices.reduce((s, i) => s + i.sgst, 0);
  const totalIgst = clientInvoices.reduce((s, i) => s + i.igst, 0);

  const itcBreakdown = [
    { name: 'CGST', value: totalCgst, color: 'hsl(239, 84%, 67%)' },
    { name: 'SGST', value: totalSgst, color: 'hsl(38, 92%, 50%)' },
    { name: 'IGST', value: totalIgst, color: 'hsl(160, 84%, 39%)' },
  ].filter(d => d.value > 0);

  const complianceColor = client.complianceStatus === 'compliant' ? 'text-success-val' : client.complianceStatus === 'attention' ? 'text-warning-val' : 'text-destructive-val';

  return (
    <AppLayout>
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/clients')} className="text-muted-foreground hover:text-foreground text-sm transition-colors">← Back</button>
        <h1 className="text-2xl font-bold text-foreground">{client.name}</h1>
        <span className={cn('text-xs font-semibold capitalize', complianceColor)}>● {client.complianceStatus}</span>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KPICard icon="💰" label="Total ITC" value="" numericValue={totalItc} prefix="₹" subtitle="This month" subtitleColor="success" />
        <KPICard icon="📄" label="Invoices" value="" numericValue={clientInvoices.length} subtitle="Total uploaded" subtitleColor="muted" delay={100} />
        <KPICard icon="🎯" label="Risk Score" value={`${client.riskScore}/100`} subtitle={client.riskScore >= 70 ? 'Low risk' : 'Needs attention'} subtitleColor={client.riskScore >= 70 ? 'success' : 'warning'} delay={200} />
        <KPICard icon="🏪" label="State" value={client.state} subtitle={client.gstin} subtitleColor="muted" delay={300} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Invoice Table */}
        <div className="lg:col-span-3 card-surface p-5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-foreground">Invoice History</h3>
            <Button variant="outline" size="sm" className="text-xs border-border text-muted-foreground rounded-lg">Export PDF</Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-2 text-muted-foreground font-medium">Invoice</th>
                  <th className="text-left py-2 px-2 text-muted-foreground font-medium">Date</th>
                  <th className="text-right py-2 px-2 text-muted-foreground font-medium">Total</th>
                  <th className="text-right py-2 px-2 text-muted-foreground font-medium">ITC</th>
                  <th className="text-left py-2 px-2 text-muted-foreground font-medium">Category</th>
                  <th className="text-left py-2 px-2 text-muted-foreground font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {clientInvoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="py-2 px-2 font-mono text-muted-foreground">{inv.invoiceNo}</td>
                    <td className="py-2 px-2 text-muted-foreground">{inv.date}</td>
                    <td className="py-2 px-2 text-right text-foreground">₹{inv.total.toLocaleString('en-IN')}</td>
                    <td className="py-2 px-2 text-right text-accent-val font-semibold">₹{inv.itc.toLocaleString('en-IN')}</td>
                    <td className="py-2 px-2">
                      <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', categoryColors[inv.aiCategory] || 'bg-muted text-muted-foreground')}>{inv.aiCategory}</span>
                    </td>
                    <td className="py-2 px-2">
                      <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium capitalize', statusBadge[inv.status])}>{inv.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-2 space-y-4">
          {/* ITC Breakdown */}
          <div className="card-surface p-5">
            <h3 className="text-sm font-semibold text-foreground mb-3">ITC Breakdown</h3>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={itcBreakdown} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" paddingAngle={4}>
                  {itcBreakdown.map((entry, idx) => <Cell key={idx} fill={entry.color} />)}
                </Pie>
                <Legend formatter={(value) => <span style={{ color: '#f8fafc', fontSize: '11px' }}>{value}</span>} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* ITC Leakage */}
          <div className="card-surface p-5 border-destructive/30">
            <h3 className="text-sm font-semibold text-foreground mb-2">⚠️ ITC Leakage</h3>
            <div className="text-2xl font-bold text-destructive-val mb-2">₹500</div>
            <p className="text-xs text-muted-foreground mb-1">Reason: Team lunch (Section 17(5))</p>
            <p className="text-xs text-success-val">💡 Tip: Get separate bills for eligible items</p>
          </div>

          {/* Supplier Health */}
          <div className="card-surface p-5">
            <h3 className="text-sm font-semibold text-foreground mb-3">Supplier Health</h3>
            {clientInvoices.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                <span className="text-xs text-muted-foreground font-mono">{inv.supplierGstin.slice(0, 15)}</span>
                <span className="text-xs text-success-val">✓ Valid</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ClientDetailPage;
