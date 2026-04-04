import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';

const navItems = [
  { label: 'Dashboard',   icon: '⬛', path: '/',            emoji: '📊' },
  { label: 'Clients',     icon: '⬛', path: '/clients',     emoji: '👥' },
  { label: 'Invoices',    icon: '⬛', path: '/invoices',    emoji: '📄' },
  { label: 'AI Insights', icon: '⬛', path: '/ai-insights', emoji: '⚡', badge: 'AI' },
  { label: 'Alerts',      icon: '⬛', path: '/alerts',      emoji: '🔔' },
  { label: 'Analytics',   icon: '⬛', path: '/analytics',   emoji: '📈', badge: 'NEW' },
  { label: 'Admin',       icon: '⬛', path: '/admin',       emoji: '🛡️' },
  { label: 'Settings',    icon: '⬛', path: '/settings',    emoji: '⚙️' },
];

const planColors: Record<string, string> = {
  pro:     'bg-primary/20 text-primary-val border border-primary/30',
  starter: 'bg-accent/20 text-accent-val border border-accent/30',
  free:    'bg-muted text-muted-foreground border border-border',
};

const AppSidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, caName, caProfile } = useAuth();

  const displayName = caName.replace(/^CA\s+/i, '');
  const initials = displayName
    .split(' ')
    .map((w: string) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'CA';

  const plan = caProfile?.plan || 'free';
  const planLabel = plan.toUpperCase();

  return (
    <aside className="w-[220px] h-screen flex flex-col flex-shrink-0 sticky top-0"
      style={{ background: 'hsl(0 0% 3%)', borderRight: '1px solid hsl(0 0% 9%)' }}>

      {/* Logo */}
      <div className="px-5 py-5 border-b" style={{ borderColor: 'hsl(0 0% 9%)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs text-white font-display"
            style={{ background: 'linear-gradient(135deg, hsl(239 84% 67%), hsl(239 84% 50%))' }}>
            VB
          </div>
          <div>
            <div className="font-bold text-foreground text-sm font-display leading-tight">VyapaarBandhu</div>
            <div className="text-[10px] text-muted-foreground tracking-wider">CA PORTAL</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive =
            location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path));

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={cn(
                'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all duration-150 group relative',
                isActive
                  ? 'bg-primary/12 text-foreground font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5 font-medium'
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full bg-primary" />
              )}
              <span className="text-base leading-none">{item.emoji}</span>
              <span className="font-display text-[13px]">{item.label}</span>
              {item.badge && (
                <span className={cn(
                  'ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-md tracking-wider font-display',
                  item.badge === 'AI'
                    ? 'bg-primary/20 text-primary-val'
                    : 'bg-accent/20 text-accent-val'
                )}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="mx-4 border-t" style={{ borderColor: 'hsl(0 0% 9%)' }} />

      {/* Profile */}
      <div className="p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold font-display flex-shrink-0 text-primary-val"
            style={{ background: 'hsl(239 84% 67% / 0.15)', border: '1px solid hsl(239 84% 67% / 0.25)' }}>
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold text-foreground truncate font-display leading-tight">
              {displayName || 'CA Portal'}
            </div>
            <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-md font-display', planColors[plan])}>
              {planLabel}
            </span>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-[11px] text-muted-foreground hover:text-destructive-val transition-colors duration-150 text-left font-medium py-1.5 px-2 rounded-lg hover:bg-destructive/8"
        >
          Sign out →
        </button>
      </div>
    </aside>
  );
};

export default AppSidebar;
