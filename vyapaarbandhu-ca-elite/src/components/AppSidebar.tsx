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
  pro:     'bg-blue-100 text-blue-800 border border-blue-200',
  starter: 'bg-emerald-100 text-emerald-800 border border-emerald-200',
  free:    'bg-gray-100 text-gray-700 border border-gray-200',
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
    <aside className="w-[240px] h-screen flex flex-col flex-shrink-0 sticky top-0 bg-[#1A3C6E] border-r border-[#2a4f8a]">

      {/* Logo */}
      <div className="px-5 py-4 border-b border-[#2a4f8a]">
        <div className="flex items-center gap-3">
          <img
            src="/VBLogo.png"
            alt="VyapaarBandhu"
            className="w-10 h-10 object-contain rounded-xl"
            style={{ background: 'white', padding: '2px' }}
          />
          <div>
            <div className="font-bold text-white text-sm font-display leading-tight">VyapaarBandhu</div>
            <div className="text-[10px] text-slate-400 tracking-wider">CA PORTAL</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-3 space-y-1 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive =
            location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path));

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm transition-all duration-150 group relative',
                isActive
                  ? 'bg-[#2563EB] text-white font-semibold'
                  : 'text-slate-300 hover:text-white hover:bg-white/10 font-medium'
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 rounded-r-full bg-white" />
              )}
              <span className="text-lg leading-none">{item.emoji}</span>
              <span className="font-display text-[14px]">{item.label}</span>
              {item.badge && (
                <span className={cn(
                  'ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-md tracking-wider font-display',
                  item.badge === 'AI'
                    ? 'bg-blue-400/20 text-blue-200'
                    : 'bg-emerald-400/20 text-emerald-200'
                )}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="mx-4 border-t border-[#2a4f8a]" />

      {/* Profile */}
      <div className="p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold font-display flex-shrink-0 text-white"
            style={{ background: 'rgba(255, 255, 255, 0.2)', border: '1px solid rgba(255, 255, 255, 0.3)' }}>
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold text-white truncate font-display leading-tight">
              {displayName || 'CA Portal'}
            </div>
            <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-md font-display', planColors[plan])}>
              {planLabel}
            </span>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-[11px] text-slate-300 hover:text-red-300 transition-colors duration-150 text-left font-medium py-1.5 px-2 rounded-lg hover:bg-red-500/15"
        >
          Sign out →
        </button>
      </div>
    </aside>
  );
};

export default AppSidebar;