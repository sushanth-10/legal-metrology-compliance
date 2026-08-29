import { Menu, Bell, Search } from 'lucide-react';
import { useApp } from '@/store';

export function Topbar() {
  const { user, setMobileNavOpen } = useApp();

  return (
    <header className="sticky top-0 z-20 bg-white/85 backdrop-blur border-b border-ink-200">
      <div className="h-16 px-4 sm:px-6 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden btn-ghost -ml-1 p-2"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="hidden sm:flex items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                placeholder="Search products, scans, complaints…"
                className="input pl-9 w-72 max-w-full hidden md:block"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <button className="relative btn-ghost p-2" aria-label="Notifications">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-danger-500 ring-2 ring-white" />
          </button>
          <div className="flex items-center gap-2.5 pl-1 sm:pl-2 sm:border-l sm:border-ink-200">
            <div className="w-9 h-9 rounded-full bg-brand-600 text-white flex items-center justify-center font-semibold text-sm">
              {user.name.split(' ').map((w) => w[0]).join('').slice(0, 2)}
            </div>
            <div className="hidden sm:block leading-tight">
              <p className="text-sm font-semibold text-ink-800">{user.name}</p>
              <p className="text-xs text-ink-500">{user.email}</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
