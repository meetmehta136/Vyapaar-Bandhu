import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';

const navItems = [
  { label: 'Dashboard',   icon: '📊', path: '/' },
  { label: 'Clients',     icon: '👥', path: '/clients' },
  { label: 'Invoices',    icon: '📄', path: '/invoices' },
  { label: 'AI Insights', icon: '⚡', path: '/ai-insights', isNew: true },
  { label: 'Alerts',      icon: '🔔', path: '/alerts' },
  { label: 'Analytics',   icon: '📈', path: '/analytics', isNew: true },
  { label: 'Admin',       icon: '🛡️', path: '/admin',     isNew: true },
  { label: 'Settings',    icon: '⚙️', path: '/settings' },
];

const AppSidebar = () => {
  const location  = useLocation();
  const navigate  = useNavigate();
  const { logout, caName, caProfile } = useAuth();

  const initials = caName
    .replace(/^CA\s+/i, '')
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'CA';

  const planBadge = caProfile?.plan === 'pro' ? 'PRO' : caProfile?.plan === 'starter' ? 'STARTER' : 'FREE';

  return (
    <aside className="w-60 h-screen bg-background border-r border-border flex flex-col flex-shrink-0 sticky top-0">

      {/* Logo */}
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm">
            VB
          </div>
          <div>
            <div className="font-semibold text-foreground text-sm">VyapaarBandhu</div>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-sm bg-accent/20 text-accent-val uppercase tracking-wider">
              CA Portal
            </span>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive =
            location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path));
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200',
                isActive
                  ? 'bg-primary/10 text-foreground border-l-2 border-primary'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )}
            >
              <span className="text-base">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
              {item.isNew && (
                <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-primary/20 text-primary-val uppercase">
                  New
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Profile */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center text-primary-val font-semibold text-sm flex-shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-foreground truncate">{caName}</div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-sm bg-accent/20 text-accent-val">
                {planBadge}
              </span>
              {caProfile?.email && (
                <span className="text-[10px] text-muted-foreground truncate">{caProfile.email}</span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={logout}
          className="mt-3 w-full text-xs text-muted-foreground hover:text-destructive-val transition-colors duration-200 text-left"
        >
          Sign Out →
        </button>
      </div>
    </aside>
  );
};

export default AppSidebar;