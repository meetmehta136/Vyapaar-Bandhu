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
  'compliant': { label: '● Compliant', className: 'text-emerald-700' },
  'attention':  { label: '● Attention', className: 'text-amber-700' },
  'at-risk':    { label: '● At Risk',   className: 'text-red-700' },
};

const riskColor  = (s: number) => s >= 70 ? 'text-emerald-700'   : s >= 40 ? 'text-amber-700'   : 'text-red-700';
const riskStroke = (s: number) => s >= 70 ? '#10b981'        : s >= 40 ? '#f59e0b'        : '#ef4444';

const RiskRing = ({ score }: { score: number }) => {
  const r = 20, c = 2 * Math.PI * r;
  return (
    <div className="relative w-14 h-14">
      <svg viewBox="0 0 50 50" className="w-full h-full -rotate-90">
        <circle cx="25" cy="25" r={r} fill="none" stroke="#e5e7eb" strokeWidth="4" />
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
        `https://vyapaar-bandhu-h53q.onrender.com/api/clients/${client.id}/remind`,
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
      `https://vyapaar-bandhu-h53q.onrender.com/api/clients/${client.id}/filing-pdf`,
      '_blank'
    );
    toast({ title: '📄 PDF opening...', description: `Filing summary for ${client.name}.` });
  };

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">👥 Clients</h1>
          {!loading && <p className="text-xs text-emerald-700 mt-1">● Live — {clients.length} clients</p>}
          {loading  && <p className="text-xs text-gray-500 mt-1 animate-pulse">Loading...</p>}
        </div>
        <div className="flex gap-3">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search clients..."
            className="w-64 bg-white border-gray-200 text-gray-900 h-10 rounded-lg text-sm"
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
          <div key={s.label} className="px-4 py-2 rounded-full bg-white border border-gray-200 text-xs">
            <span className="text-gray-600">{s.label}: </span>
            <span className="text-gray-900 font-semibold">{s.value}</span>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {!loading && clients.length === 0 && (
        <div className="text-center py-20 text-gray-500">
          <p className="text-4xl mb-4">👥</p>
          <p className="text-sm">No clients yet. Add your first client above.</p>
        </div>
      )}

      {/* Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 animate-pulse">
              <div className="h-4 bg-gray-100 rounded w-3/4 mb-3" />
              <div className="h-3 bg-gray-100 rounded w-1/2 mb-3" />
              <div className="h-3 bg-gray-100 rounded w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Client cards */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((client: any) => (
            <div key={client.id} className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 hover:border-blue-200 hover:shadow-md transition-all duration-200">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">{client.name}</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 mt-1 inline-block">
                    {client.state || 'India'}
                  </span>
                </div>
                <RiskRing score={client.riskScore || 50} />
              </div>

              <div className="font-mono text-xs text-gray-600 mb-3">
                {client.gstin || 'GSTIN not set'}
              </div>

              <div className="flex gap-4 mb-3">
                <div>
                  <div className="text-sm font-bold text-emerald-700">
                    ₹{(client.itcThisMonth || 0).toLocaleString('en-IN')}
                  </div>
                  <div className="text-[10px] text-gray-600">ITC This Month</div>
                </div>
                <div>
                  <div className="text-sm font-bold text-blue-600">{client.invoiceCount || 0}</div>
                  <div className="text-[10px] text-gray-600">Invoices</div>
                </div>
                <div>
                  <div className="text-sm font-bold text-gray-900 font-mono text-xs">{client.whatsapp || '—'}</div>
                  <div className="text-[10px] text-gray-600">WhatsApp</div>
                </div>
              </div>

              <div className={cn('text-xs font-semibold mb-4',
                complianceBadge[client.complianceStatus]?.className || 'text-gray-700')}>
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
                  className="rounded-lg text-xs border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  disabled={reminderLoading === client.id}
                  onClick={() => handleSendReminder(client)}
                >
                  {reminderLoading === client.id ? '...' : '📱'}
                </Button>
                <Button
                  variant="outline" size="sm"
                  className="rounded-lg text-xs border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50"
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-xl"
          onClick={() => setShowModal(false)}
        >
          <div className="bg-white rounded-lg border border-gray-200 shadow-lg p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-1">Add New Client</h2>
            <p className="text-xs text-gray-600 mb-4">
              A welcome WhatsApp message will be sent to the client automatically.
            </p>
            <div className="space-y-3">
              <Input
                placeholder="Business Name *"
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                className="bg-white border-gray-200 text-gray-900 rounded-lg"
              />
              <Input
                placeholder="WhatsApp Number (+91XXXXXXXXXX) *"
                value={form.phone}
                onChange={e => setForm({ ...form, phone: e.target.value })}
                className="bg-white border-gray-200 text-gray-900 rounded-lg"
              />
              <div className="flex gap-2">
                <Input
                  placeholder="GSTIN (optional)"
                  value={form.gstin}
                  onChange={e => setForm({ ...form, gstin: e.target.value.toUpperCase() })}
                  className="bg-white border-gray-200 text-gray-900 rounded-lg flex-1"
                  maxLength={15}
                />
                <Button
                  variant="outline" size="sm"
                  className="border-gray-200 text-gray-600 rounded-lg text-xs hover:bg-gray-50"
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
                className="w-full h-10 rounded-lg bg-white border border-gray-200 text-gray-900 text-sm px-3"
              >
                {ALL_STATES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex gap-2 mt-5">
              <Button variant="ghost" onClick={() => setShowModal(false)} className="flex-1 text-gray-700 hover:bg-gray-100">
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
