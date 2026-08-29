import {
  LayoutDashboard,
  ScanLine,
  History,
  MessageSquareWarning,
  BarChart3,
  MapPin,
  FileText,
  User as UserIcon,
  Settings,
  LogOut,
  ShieldCheck,
  X,
} from 'lucide-react';
import type { PageKey } from '@/types';
import { useApp } from '@/store';

const officerOnly: PageKey[] = ['analytics', 'violation-map', 'reports'];

const nav: { key: PageKey; label: string; icon: typeof LayoutDashboard }[] = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'scan', label: 'Scan Product', icon: ScanLine },
  { key: 'history', label: 'Scan History', icon: History },
  { key: 'complaints', label: 'Complaints', icon: MessageSquareWarning },
  { key: 'analytics', label: 'Analytics', icon: BarChart3 },
  { key: 'violation-map', label: 'Violation Map', icon: MapPin },
  { key: 'reports', label: 'Reports', icon: FileText },
  { key: 'profile', label: 'Profile', icon: UserIcon },
  { key: 'settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const { user, role, view, setPage, mobileNavOpen, setMobileNavOpen, logout } = useApp();
  const page = view;

  const items = nav.filter((n) => role === 'officer' || !officerOnly.includes(n.key));

  return (
    <>
      {mobileNavOpen && (
        <div
          className="fixed inset-0 bg-ink-950/40 z-40 lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden
        />
      )}
      <aside
        className={`fixed lg:sticky top-0 left-0 z-50 lg:z-30 h-screen w-[260px] shrink-0 bg-white border-r border-ink-200 flex flex-col transition-transform duration-300 ${
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="px-5 pt-5 pb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center shadow-sm">
              <ShieldCheck className="w-5.5 h-5.5 text-white" strokeWidth={2.2} />
            </div>
            <div>
              <p className="font-display font-extrabold text-ink-900 text-lg leading-none tracking-tight">
                NIRIKSHA
              </p>
              <p className="text-[11px] text-ink-500 mt-1 leading-none">
                AI-Powered Product Compliance
              </p>
            </div>
          </div>
          <button
            className="lg:hidden text-ink-500 hover:text-ink-800 p-1"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-2 overflow-y-auto scrollbar-thin">
          <p className="px-3 pt-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-400">
            Menu
          </p>
          <ul className="space-y-0.5">
            {items.map((item) => {
              const active = page === item.key;
              const officerTag = officerOnly.includes(item.key);
              return (
                <li key={item.key}>
                  <button
                    onClick={() => setPage(item.key)}
                    className={`nav-item w-full no-tap-highlight ${active ? 'nav-item-active' : ''}`}
                  >
                    <item.icon className="w-[18px] h-[18px] shrink-0" strokeWidth={2} />
                    <span className="flex-1 text-left">{item.label}</span>
                    {officerTag && (
                      <span className="text-[9px] font-bold uppercase tracking-wide text-brand-500 bg-brand-50 px-1.5 py-0.5 rounded">
                        Officer
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-3 border-t border-ink-200">
          <div className="flex items-center gap-3 px-2 py-2 mb-1">
            <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold text-sm">
              {user.name.split(' ').map((w) => w[0]).join('').slice(0, 2)}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink-800 truncate">{user.name}</p>
              <p className="text-xs text-ink-500 truncate capitalize">{role === 'officer' ? 'Officer' : 'Consumer'}</p>
            </div>
          </div>
          <button onClick={logout} className="nav-item w-full text-danger-600 hover:bg-danger-50">
            <LogOut className="w-[18px] h-[18px]" />
            <span>Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
}
