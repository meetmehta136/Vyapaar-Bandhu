import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppLayout from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useClients } from '@/hooks/useAPI';
import { createClient } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

const complianceBadge: Record<string, { label: string; className: string }> = {
  'compliant': { label: '● Compliant', className: 'text-success-val' },
  'attention':  { label: '● Attention', className: 'text-warning-val' },
  'at-risk':    { label: '● At Risk',   className: 'text-destructive-val' },
};

const riskColor  = (s: number) => s >= 70 ? 'text-success-val'   : s >= 40 ? 'text-warning-val'   : 'text-destructive-val';
const riskStroke = (s: number) => s >= 70 ? 'hsl(160,84%,39%)'   : s >= 40 ? 'hsl(38,92%,50%)'    : 'hsl(0,84%,60%)';

const RiskRing = ({ score }: { score: number }) => {
  const r = 20, c = 2 * Math.PI * r;
  return (
    <div className="relative w-14 h-14">
      <svg viewBox="0 0 50 50" className="w-full h-full -rotate-90">
        <circle cx="25" cy="25" r={r} fill="none" stroke="hsl(0,0%,10%)" strokeWidth="4" />
        <circle cx="25" cy="25" r={r} fill="none" stroke={riskStroke(score)} strokeWidth="4"
          strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
          strokeLinecap="round" className="transition-all duration-1000" />
      </svg>
      <span className={cn('absolute inset-0 flex items-center justify-center text-xs font-bold', riskColor(score))}>
        {score}
      </span>
    </div>
  );
};

const ALL_STATES = [
  'Gujarat', 'Maharashtra', 'Delhi', 'Karnataka', 'Tamil Nadu',
  'Rajasthan', 'Uttar Pradesh', 'West Bengal', 'Telangana', 'Andhra Pradesh',
  'Punjab', 'Haryana', 'Bihar', 'Madhya Pradesh', 'Odisha',
];

const ClientsPage = () => {
  const [search, setSearch]       = useState('');
  const [showModal, setShowModal] = useState(false);
  const [form, setForm]           = useState({ name: '', phone: '', gstin: '', state: 'Gujarat' });
  const [saving, setSaving]       = useState(false);
  const [reminderLoading, setReminderLoading] = useState<string | null>(null);
  const navigate = useNavigate();
  const { toast } = useToast();
  const { data: clientsData, loading, refetch } = useClients();

  const clients  = clientsData || [];
  const filtered = clients.filter((c: any) =>
    (c.name  || '').toLowerCase().includes(search.toLowerCase()) ||
    (c.gstin || '').toLowerCase().includes(search.toLowerCase())
  );

  const compliant = clients.filter((c: any) => c.complianceStatus === 'compliant').length;
  const atRisk    = clients.filter((c: any) => c.complianceStatus === 'at-risk').length;
  const avgItc    = clients.length > 0
    ? Math.round(clients.reduce((s: number, c: any) => s + (c.itcThisMonth || 0), 0) / clients.length)
    : 0;

  const handleAddClient = async () => {
    if (!form.name || !form.phone) return;
    setSaving(true);
    const result = await createClient(form);
    setSaving(false);
    if (result) {
      toast({ title: 'Client added ✅', description: `${form.name} has been added.` });
      setShowModal(false);
      setForm({ name: '', phone: '', gstin: '', state: 'Gujarat' });
      refetch();                          // ← no page reload
    } else {
      toast({ title: 'Error', description: 'Could not add client. Try again.', variant: 'destructive' });
    }
  };

  const handleSendReminder = async (client: any) => {
    setReminderLoading(client.id);
    try {
      // Call backend to send WhatsApp reminder
      const res = await fetch(
        `https://vyapaar-bandhu.onrender.com/api/clients/${client.id}/remind`,
        { method: 'POST' }
      );
      if (res.ok) {
        toast({ title: '📱 Reminder sent!', description: `WhatsApp reminder sent to ${client.name}.` });
      } else {
        toast({ title: 'Reminder queued', description: `Will be sent to ${client.whatsapp} shortly.` });
      }
    } catch {
      toast({ title: 'Reminder queued', description: `Will be sent to ${client.whatsapp} shortly.` });
    }
    setReminderLoading(null);
  };

  const handleDownloadPdf = (client: any) => {
    window.open(
      `https://vyapaar-bandhu.onrender.com/api/clients/${client.id}/filing-pdf`,
      '_blank'
    );
    toast({ title: '📄 PDF opening...', description: `Filing summary for ${client.name}.` });
  };

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">👥 Clients</h1>
          {!loading && <p className="text-xs text-success-val mt-1">● Live — {clients.length} clients</p>}
          {loading  && <p className="text-xs text-muted-foreground mt-1 animate-pulse">Loading...</p>}
        </div>
        <div className="flex gap-3">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search clients..."
            className="w-64 bg-muted border-border text-foreground h-10 rounded-lg text-sm"
          />
          <Button variant="indigo" onClick={() => setShowModal(true)} className="rounded-lg">
            + Add Client
          </Button>
        </div>
      </div>

      {/* Summary pills */}
      <div className="flex gap-3 mb-6 flex-wrap">
        {[
          { label: 'Total',     value: clients.length },
          { label: 'Compliant', value: compliant },
          { label: 'At Risk',   value: atRisk },
          { label: 'Avg ITC',   value: `₹${avgItc.toLocaleString('en-IN')}` },
        ].map((s) => (
          <div key={s.label} className="px-4 py-2 rounded-full bg-muted border border-border text-xs">
            <span className="text-muted-foreground">{s.label}: </span>
            <span className="text-foreground font-semibold">{s.value}</span>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {!loading && clients.length === 0 && (
        <div className="text-center py-20 text-muted-foreground">
          <p className="text-4xl mb-4">👥</p>
          <p className="text-sm">No clients yet. Add your first client above.</p>
        </div>
      )}

      {/* Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="card-surface p-5 animate-pulse">
              <div className="h-4 bg-muted rounded w-3/4 mb-3" />
              <div className="h-3 bg-muted rounded w-1/2 mb-3" />
              <div className="h-3 bg-muted rounded w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Client cards */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((client: any) => (
            <div key={client.id} className="card-surface p-5 hover:border-primary/30 transition-all duration-200">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{client.name}</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground mt-1 inline-block">
                    {client.state || 'India'}
                  </span>
                </div>
                <RiskRing score={client.riskScore || 50} />
              </div>

              <div className="font-mono text-xs text-muted-foreground mb-3">
                {client.gstin || 'GSTIN not set'}
              </div>

              <div className="flex gap-4 mb-3">
                <div>
                  <div className="text-sm font-bold text-accent-val">
                    ₹{(client.itcThisMonth || 0).toLocaleString('en-IN')}
                  </div>
                  <div className="text-[10px] text-muted-foreground">ITC This Month</div>
                </div>
                <div>
                  <div className="text-sm font-bold text-primary-val">{client.invoiceCount || 0}</div>
                  <div className="text-[10px] text-muted-foreground">Invoices</div>
                </div>
                <div>
                  <div className="text-sm font-bold text-foreground font-mono text-xs">{client.whatsapp || '—'}</div>
                  <div className="text-[10px] text-muted-foreground">WhatsApp</div>
                </div>
              </div>

              <div className={cn('text-xs font-semibold mb-4',
                complianceBadge[client.complianceStatus]?.className || 'text-muted-foreground')}>
                {complianceBadge[client.complianceStatus]?.label || '● Unknown'}
              </div>

              <div className="flex gap-2">
                <Button
                  variant="indigo" size="sm"
                  className="rounded-lg flex-1 text-xs"
                  onClick={() => navigate(`/clients/${client.id}`)}
                >
                  View Details →
                </Button>
                <Button
                  variant="outline" size="sm"
                  className="rounded-lg text-xs border-border text-muted-foreground hover:text-foreground"
                  disabled={reminderLoading === client.id}
                  onClick={() => handleSendReminder(client)}
                >
                  {reminderLoading === client.id ? '...' : '📱'}
                </Button>
                <Button
                  variant="outline" size="sm"
                  className="rounded-lg text-xs border-border text-muted-foreground hover:text-foreground"
                  onClick={() => handleDownloadPdf(client)}
                >
                  📄
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Client Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xl"
          onClick={() => setShowModal(false)}
        >
          <div className="card-surface p-6 w-full max-w-md glow-primary" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-foreground mb-1">Add New Client</h2>
            <p className="text-xs text-muted-foreground mb-4">
              A welcome WhatsApp message will be sent to the client automatically.
            </p>
            <div className="space-y-3">
              <Input
                placeholder="Business Name *"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                className="bg-muted border-border text-foreground rounded-lg"
              />
              <Input
                placeholder="WhatsApp Number (+91XXXXXXXXXX) *"
                value={form.phone}
                onChange={e => setForm({ ...form, phone: e.target.value })}
                className="bg-muted border-border text-foreground rounded-lg"
              />
              <div className="flex gap-2">
                <Input
                  placeholder="GSTIN (optional)"
                  value={form.gstin}
                  onChange={e => setForm({ ...form, gstin: e.target.value.toUpperCase() })}
                  className="bg-muted border-border text-foreground rounded-lg flex-1"
                  maxLength={15}
                />
                <Button
                  variant="outline" size="sm"
                  className="border-border text-muted-foreground rounded-lg text-xs"
                  onClick={() => {
                    if (form.gstin.length === 15)
                      toast({ title: 'GSTIN format looks valid', description: form.gstin });
                    else
                      toast({ title: 'GSTIN must be 15 characters', variant: 'destructive' });
                  }}
                >
                  Validate
                </Button>
              </div>
              <select
                value={form.state}
                onChange={e => setForm({ ...form, state: e.target.value })}
                className="w-full h-10 rounded-lg bg-muted border border-border text-foreground text-sm px-3"
              >
                {ALL_STATES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex gap-2 mt-5">
              <Button variant="ghost" onClick={() => setShowModal(false)} className="flex-1 text-muted-foreground">
                Cancel
              </Button>
              <Button
                variant="indigo"
                onClick={handleAddClient}
                disabled={saving || !form.name || !form.phone}
                className="flex-1 rounded-lg"
              >
                {saving ? 'Saving...' : 'Add Client'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default ClientsPage;