import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppLayout from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const UploadInvoicePage = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setResult(null);

    try {
      const token = localStorage.getItem('vb_token');
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${BASE_URL}/ocr/upload`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (data.success) {
        setResult(data);
        toast({ title: 'Invoice processed ✅', description: 'Fields extracted successfully.' });
      } else {
        toast({ title: 'OCR failed', description: data.error || 'Unknown error', variant: 'destructive' });
      }
    } catch (e: any) {
      toast({ title: 'Upload error', description: e.message, variant: 'destructive' });
    }
    setUploading(false);
  };

  const fields = result?.fields || {};
  const compliance = result?.compliance;

  return (
    <AppLayout>
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/invoices')} className="text-muted-foreground hover:text-foreground text-sm transition-colors">← Back to Invoices</button>
        <h1 className="text-2xl font-bold text-foreground">Upload Invoice</h1>
      </div>

      <div className="card-surface p-6 max-w-2xl mx-auto">
        <div className="mb-6">
          <label className="block text-sm font-medium text-foreground mb-2">Select Invoice Image (JPEG, PNG, PDF)</label>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary/20 file:text-primary-val hover:file:bg-primary/30"
          />
        </div>

        <Button
          variant="indigo"
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full rounded-lg"
        >
          {uploading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Processing...
            </span>
          ) : 'Upload & Extract'}
        </Button>

        {uploading && (
          <div className="mt-6 p-4 rounded-lg bg-muted/30">
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full animate-pulse" style={{ width: '60%' }} />
            </div>
            <p className="text-xs text-muted-foreground mt-2">Running OCR + classification + compliance check...</p>
          </div>
        )}

        {result && (
          <div className="mt-6 space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Extracted Fields</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Seller', key: 'seller_name' },
                { label: 'Seller GSTIN', key: 'seller_gstin' },
                { label: 'Invoice No', key: 'invoice_no' },
                { label: 'Date', key: 'invoice_date' },
                { label: 'Taxable Amount', key: 'taxable_amount', prefix: '₹' },
                { label: 'CGST', key: 'cgst', prefix: '₹' },
                { label: 'SGST', key: 'sgst', prefix: '₹' },
                { label: 'IGST', key: 'igst', prefix: '₹' },
                { label: 'Total', key: 'total_amount', prefix: '₹' },
              ].map(f => {
                const val = fields[f.key]?.value;
                return (
                  <div key={f.key} className="p-3 rounded-lg bg-muted/30">
                    <div className="text-[10px] text-muted-foreground">{f.label}</div>
                    <div className="text-sm font-semibold text-foreground mt-0.5">
                      {val != null ? `${f.prefix || ''}${typeof val === 'number' ? val.toLocaleString('en-IN') : val}` : '—'}
                    </div>
                  </div>
                );
              })}
            </div>

            {compliance && (
              <div className={`p-4 rounded-lg ${compliance.status === 'pass' ? 'bg-success/10 border border-success/30' : compliance.status === 'blocked' ? 'bg-destructive/10 border border-destructive/30' : 'bg-warning/10 border border-warning/30'}`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">
                    {compliance.status === 'pass' ? '✅ ITC Eligible' : compliance.status === 'blocked' ? '🚫 ITC Blocked' : '⚠️ Warning'}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{compliance.reason || compliance.message}</p>
                {compliance.itc_eligible > 0 && (
                  <p className="text-xs text-success-val mt-1">ITC Eligible: ₹{compliance.itc_eligible.toLocaleString('en-IN')}</p>
                )}
                {compliance.itc_blocked > 0 && (
                  <p className="text-xs text-destructive-val mt-1">ITC Blocked: ₹{compliance.itc_blocked.toLocaleString('en-IN')}</p>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => { setFile(null); setResult(null); }} className="flex-1 rounded-lg">
                Upload Another
              </Button>
              <Button variant="indigo" onClick={() => navigate('/invoices')} className="flex-1 rounded-lg">
                View All Invoices
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default UploadInvoicePage;