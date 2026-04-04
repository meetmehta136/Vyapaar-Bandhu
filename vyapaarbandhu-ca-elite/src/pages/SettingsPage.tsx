import { useState } from 'react';
import AppLayout from '@/components/AppLayout';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';

const SettingsPage = () => {
  const { toast } = useToast();
  const [brandName, setBrandName] = useState('VyapaarBandhu');
  const [brandColor, setBrandColor] = useState('#6366F1');
  const [tagline, setTagline] = useState('AI-Powered GST Compliance');
  const [notifications, setNotifications] = useState({
    filingDeadline: true,
    itcMismatch: true,
    supplierIssue: true,
    documentPending: false,
  });

  return (
    <AppLayout>
      <h1 className="text-2xl font-bold text-gray-900 mb-8">⚙️ Settings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CA Profile */}
        <div className="card-surface p-6">
          <h2 className="text-sm font-semibold text-foreground mb-5">CA Profile</h2>
          <div className="flex items-center gap-4 mb-5">
            <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary-val text-xl font-bold">RS</div>
            <Button variant="outline" size="sm" className="text-xs border-border text-muted-foreground rounded-lg">Upload Photo</Button>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Full Name</label>
              <Input defaultValue="Rajesh Sharma" className="bg-muted border-border text-foreground rounded-lg" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Firm Name</label>
              <Input defaultValue="Sharma & Associates" className="bg-muted border-border text-foreground rounded-lg" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">CA License No</label>
              <Input defaultValue="FRN-123456W" className="bg-muted border-border text-foreground rounded-lg" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Email</label>
              <Input defaultValue="ca@demo.com" className="bg-muted border-border text-foreground rounded-lg" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Phone</label>
              <Input defaultValue="+91 98765 43210" className="bg-muted border-border text-foreground rounded-lg" />
            </div>
            <Button variant="indigo" className="rounded-lg" onClick={() => toast({ title: 'Saved', description: 'Profile updated.' })}>Save Profile</Button>
          </div>
        </div>

        {/* White Label */}
        <div className="card-surface p-6">
          <h2 className="text-sm font-semibold text-foreground mb-5">White Label Branding</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Brand Name</label>
              <Input value={brandName} onChange={(e) => setBrandName(e.target.value)} className="bg-muted border-border text-foreground rounded-lg" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Primary Color</label>
              <div className="flex gap-2 items-center">
                <input type="color" value={brandColor} onChange={(e) => setBrandColor(e.target.value)} className="w-10 h-10 rounded-lg border-0 cursor-pointer bg-transparent" />
                <Input value={brandColor} onChange={(e) => setBrandColor(e.target.value)} className="bg-muted border-border text-foreground rounded-lg font-mono w-32" />
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">Tagline</label>
              <Input value={tagline} onChange={(e) => setTagline(e.target.value)} className="bg-muted border-border text-foreground rounded-lg" />
            </div>

            {/* Live Preview */}
            <div className="mt-4">
              <label className="text-xs text-muted-foreground mb-2 block">Live Preview</label>
              <div className="p-4 rounded-lg bg-background border border-border">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold text-foreground" style={{ background: brandColor }}>{brandName.slice(0, 2).toUpperCase()}</div>
                  <div>
                    <div className="text-xs font-semibold text-foreground">{brandName}</div>
                    <div className="text-[9px] text-muted-foreground">{tagline}</div>
                  </div>
                </div>
                <div className="space-y-1">
                  {['Dashboard', 'Clients', 'Invoices'].map((item) => (
                    <div key={item} className="text-[10px] text-muted-foreground px-2 py-1 rounded" style={item === 'Dashboard' ? { background: `${brandColor}20`, color: brandColor, borderLeft: `2px solid ${brandColor}` } : {}}>{item}</div>
                  ))}
                </div>
              </div>
            </div>
            <Button variant="indigo" className="rounded-lg" onClick={() => toast({ title: 'Branding saved', description: 'White label settings updated.' })}>Save Branding</Button>
          </div>
        </div>

        {/* Subscription */}
        <div className="card-surface p-6">
          <h2 className="text-sm font-semibold text-foreground mb-4">Subscription</h2>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-lg font-bold gradient-text-primary">PRO</span>
            <span className="text-xs text-muted-foreground">₹999/month</span>
          </div>
          <div className="space-y-2 mb-4">
            <div className="text-xs text-muted-foreground">Usage: <span className="text-foreground">7/50 clients</span></div>
            <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
              <div className="h-full bg-primary rounded-full" style={{ width: '14%' }} />
            </div>
          </div>
          <div className="space-y-1.5 mb-4">
            {['Unlimited invoices', 'AI Insights', 'WhatsApp Integration', 'White Label', 'Priority Support'].map((f) => (
              <div key={f} className="flex items-center gap-2 text-xs">
                <span className="text-success-val">✓</span>
                <span className="text-foreground">{f}</span>
              </div>
            ))}
          </div>
          <Button variant="outline" disabled className="rounded-lg border-border text-muted-foreground text-xs">
            Upgrade — Coming Soon
          </Button>
        </div>

        {/* Notifications */}
        <div className="card-surface p-6">
          <h2 className="text-sm font-semibold text-foreground mb-5">Notifications</h2>
          <div className="space-y-4">
            {[
              { key: 'filingDeadline', label: 'Filing Deadline Alerts' },
              { key: 'itcMismatch', label: 'ITC Mismatch Alerts' },
              { key: 'supplierIssue', label: 'Supplier Issue Alerts' },
              { key: 'documentPending', label: 'Document Pending Alerts' },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between">
                <span className="text-xs text-foreground">{item.label}</span>
                <Switch
                  checked={notifications[item.key as keyof typeof notifications]}
                  onCheckedChange={(checked) => setNotifications(prev => ({ ...prev, [item.key]: checked }))}
                />
              </div>
            ))}
          </div>
          <Button
            variant="outline"
            className="mt-5 rounded-lg border-border text-muted-foreground text-xs"
            onClick={() => toast({ title: '🔔 Test notification', description: 'This is a test notification from VyapaarBandhu.' })}
          >
            Test Notification
          </Button>
        </div>
      </div>
    </AppLayout>
  );
};

export default SettingsPage;
