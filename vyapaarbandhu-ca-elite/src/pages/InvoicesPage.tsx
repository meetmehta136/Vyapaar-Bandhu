import { useState, useCallback } from 'react';
import AppLayout from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';
import { useInvoices } from '@/hooks/useAPI';
import { approveInvoice, rejectInvoice } from '@/lib/api';

const categoryColors: Record<string, string> = {
  'Electronics': 'bg-primary/20 text-primary-val',
  'Office': 'bg-accent/20 text-accent-val',
  'Food': 'bg-warning/20 text-warning-val',
  'Pharma': 'bg-success/20 text-success-val',
  'Vehicle': 'bg-destructive/20 text-destructive-val',
  'Clothing': 'bg-destructive/20 text-destructive-val',
  'Travel': 'bg-primary/20 text-primary-val',
  'General': 'bg-muted text-muted-foreground',
  'Other': 'bg-muted text-muted-foreground',
};

const statusBadge: Record<string, string> = {
  confirmed: 'bg-primary/20 text-primary-val',
  pending: 'bg-warning/20 text-warning-val',
  rejected: 'bg-destructive/20 text-destructive-val',
};

type TabType = 'all' | 'confirmed' | 'pending' | 'rejected';

const InvoicesPage = () => {
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<TabType>('all');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toast } = useToast();
  const { data: invoicesData, loading, refetch } = useInvoices();

  const invoices = invoicesData || [];

  const filtered = invoices.filter((inv: any) => {
    const matchesSearch =
      (inv.clientName || '').toLowerCase().includes(search.toLowerCase()) ||
      (inv.invoiceNo || '').toLowerCase().includes(search.toLowerCase());
    const matchesTab = tab === 'all' || inv.status === tab;
    return matchesSearch && matchesTab;
  });

  const totalItc = invoices.reduce((s: number, i: any) => s + (i.itc || 0), 0);
  const confirmed = invoices.filter((i: any) => i.status === 'confirmed').length;
  const pending = invoices.filter((i: any) => i.status === 'pending').length;
  const rejected = invoices.filter((i: any) => i.status === 'rejected').length;

  const toggleSelect = (id: string) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  };

  const handleApprove = async (id: string, invoiceNo: string) => {
    setActionLoading(id);
    const result = await approveInvoice(id);
    setActionLoading(null);
    if (result) {
      toast({ title: 'Approved ✅', description: `Invoice ${invoiceNo} approved.` });
      refetch?.();
    } else {
      toast({ title: 'Error', description: 'Could not approve invoice. Try again.', variant: 'destructive' });
    }
  };

  const handleReject = async (id: string, invoiceNo: string) => {
    setActionLoading(id);
    const result = await rejectInvoice(id);
    setActionLoading(null);
    if (result) {
      toast({ title: 'Rejected', description: `Invoice ${invoiceNo} rejected.` });
      refetch?.();
    } else {
      toast({ title: 'Error', description: 'Could not reject invoice. Try again.', variant: 'destructive' });
    }
  };

  const handleApproveSelected = async () => {
    const ids = Array.from(selected);
    let successCount = 0;
    for (const id of ids) {
      const inv = invoices.find((i: any) => i.id === id);
      if (inv?.status === 'pending') {
        const result = await approveInvoice(id);
        if (result) successCount++;
      }
    }
    setSelected(new Set());
    toast({ title: `${successCount} invoices approved ✅`, description: 'Dashboard updated.' });
    refetch?.();
  };

  const handleExportCSV = () => {
    if (invoices.length === 0) {
      toast({ title: 'No data', description: 'No invoices to export.' });
      return;
    }
    const headers = ['ID', 'Client', 'Invoice No', 'Date', 'Supplier GSTIN', 'Total', 'ITC', 'Category', 'Status'];
    const rows = invoices.map((inv: any) => [
      inv.id,
      inv.clientName || 'Unknown',
      inv.invoiceNo || '',
      (inv.date || '').slice(0, 10),
      inv.supplierGstin || '',
      inv.total || 0,
      inv.itc || 0,
      inv.aiCategory || 'General',
      inv.status,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoices-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast({ title: 'Exported ✅', description: `${invoices.length} invoices downloaded as CSV.` });
  };

  const tabs: { key: TabType; label: string }[] = [
    { key: 'all', label: `All (${invoices.length})` },
    { key: 'confirmed', label: `Confirmed (${confirmed})` },
    { key: 'pending', label: `Pending (${pending})` },
    { key: 'rejected', label: `Rejected (${rejected})` },
  ];

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">📄 Invoices</h1>
          {!loading && <p className="text-xs text-success-val mt-1">● Live data — {invoices.length} total invoices</p>}
          {loading && <p className="text-xs text-muted-foreground mt-1 animate-pulse">Loading live data...</p>}
        </div>
        <div className="flex gap-3">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search invoices..."
            className="w-64 bg-muted border-border text-foreground h-10 rounded-lg text-sm"
          />
          <Button
            variant="outline"
            className="border-border text-muted-foreground rounded-lg text-sm"
            onClick={handleExportCSV}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-3 mb-5 flex-wrap">
        {[
          { label: 'Total', value: invoices.length },
          { label: 'Confirmed', value: confirmed },
          { label: 'Pending', value: pending },
          { label: 'Rejected', value: rejected },
          { label: 'Total ITC', value: `₹${totalItc.toLocaleString('en-IN')}` },
        ].map((s) => (
          <div key={s.label} className="px-4 py-2 rounded-full bg-muted border border-border text-xs">
            <span className="text-muted-foreground">{s.label}: </span>
            <span className="text-foreground font-semibold">{s.value}</span>
          </div>
        ))}
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

      {/* Batch action */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-4 p-3 rounded-lg bg-primary/10 border border-primary/30">
          <span className="text-xs text-foreground">{selected.size} selected</span>
          <Button
            variant="indigo"
            size="sm"
            className="text-xs rounded-lg"
            onClick={handleApproveSelected}
          >
            Approve Selected ({selected.size})
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs rounded-lg text-muted-foreground"
            onClick={() => setSelected(new Set())}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="card-surface overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="py-3 px-3 text-left"><input type="checkbox" className="rounded" onChange={(e) => {
                if (e.target.checked) setSelected(new Set(filtered.map((i: any) => i.id)));
                else setSelected(new Set());
              }} /></th>
              <th className="py-3 px-3 text-left text-muted-foreground font-medium">Client</th>
              <th className="py-3 px-3 text-left text-muted-foreground font-medium">Invoice No</th>
              <th className="py-3 px-3 text-left text-muted-foreground font-medium">Date</th>
              <th className="py-3 px-3 text-left text-muted-foreground font-medium">Supplier GSTIN</th>
              <th className="py-3 px-3 text-right text-muted-foreground font-medium">Total</th>
              <th className="py-3 px-3 text-right text-muted-foreground font-medium">ITC</th>
              <th className="py-3 px-3 text-left text-muted-foreground font-medium">Category</th>
              <th className="py-3 px-3 text-left text-muted-foreground font-medium">Status</th>
              <th className="py-3 px-3 text-right text-muted-foreground font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={10} className="py-8 text-center text-muted-foreground animate-pulse">
                  Loading invoices from live database...
                </td>
              </tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={10} className="py-8 text-center text-muted-foreground">
                  No invoices found. Send an invoice photo on WhatsApp to get started.
                </td>
              </tr>
            )}
            {filtered.map((inv: any) => (
              <tr key={inv.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors duration-200">
                <td className="py-2.5 px-3">
                  <input type="checkbox" checked={selected.has(inv.id)} onChange={() => toggleSelect(inv.id)} className="rounded" />
                </td>
                <td className="py-2.5 px-3 text-foreground font-medium">{inv.clientName || 'Unknown'}</td>
                <td className="py-2.5 px-3 font-mono text-muted-foreground">{inv.invoiceNo || '—'}</td>
                <td className="py-2.5 px-3 text-muted-foreground">{(inv.date || '').slice(0, 10)}</td>
                <td className="py-2.5 px-3 font-mono text-muted-foreground text-[10px]">{inv.supplierGstin || '—'}</td>
                <td className="py-2.5 px-3 text-right text-foreground">₹{(inv.total || 0).toLocaleString('en-IN')}</td>
                <td className="py-2.5 px-3 text-right text-accent-val font-semibold">₹{(inv.itc || 0).toLocaleString('en-IN')}</td>
                <td className="py-2.5 px-3">
                  <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', categoryColors[inv.aiCategory] || 'bg-muted text-muted-foreground')}>
                    {inv.aiCategory || 'General'}
                  </span>
                </td>
                <td className="py-2.5 px-3">
                  <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium capitalize', statusBadge[inv.status] || 'bg-muted text-muted-foreground')}>
                    {inv.status}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-right">
                  {inv.status === 'pending' && (
                    <div className="flex gap-1 justify-end">
                      <button
                        disabled={actionLoading === inv.id}
                        className="text-[10px] px-2 py-1 rounded bg-success/20 text-success-val hover:bg-success/30 transition-colors disabled:opacity-50"
                        onClick={() => handleApprove(inv.id, inv.invoiceNo)}
                      >
                        {actionLoading === inv.id ? '...' : '✓'}
                      </button>
                      <button
                        disabled={actionLoading === inv.id}
                        className="text-[10px] px-2 py-1 rounded bg-destructive/20 text-destructive-val hover:bg-destructive/30 transition-colors disabled:opacity-50"
                        onClick={() => handleReject(inv.id, inv.invoiceNo)}
                      >
                        {actionLoading === inv.id ? '...' : '✗'}
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppLayout>
  );
};

export default InvoicesPage;