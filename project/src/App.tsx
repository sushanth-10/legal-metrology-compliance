import { AppProvider, useApp, authRoutes } from '@/store';
import { ToastHost } from '@/components/Auth';
import { Sidebar } from '@/components/Sidebar';
import { Topbar } from '@/components/Topbar';
import { Dashboard } from '@/pages/Dashboard';
import { ScanProduct } from '@/pages/ScanProduct';
import { ScanHistory } from '@/pages/ScanHistory';
import { Complaints } from '@/pages/Complaints';
import { Analytics } from '@/pages/Analytics';
import { ViolationMap } from '@/pages/ViolationMap';
import { Reports } from '@/pages/Reports';
import { Profile } from '@/pages/Profile';
import { Settings } from '@/pages/Settings';
import { Login } from '@/pages/Login';
import { Signup } from '@/pages/Signup';
import { AdminLogin } from '@/pages/AdminLogin';
import { OrganizationRegistration } from '@/pages/OrganizationRegistration';
import { OfficerRegistration } from '@/pages/OfficerRegistration';
import { AdminDashboard } from '@/pages/AdminDashboard';
import type { PageKey, View } from '@/types';

const adminOnly: PageKey[] = ['analytics', 'violation-map'];

function AuthPage({ view }: { view: View }) {
  switch (view) {
    case 'login':
      return <Login />;
    case 'admin-login':
      return <AdminLogin />;
    case 'signup':
      return <Signup />;
    case 'signup-organization':
      return <OrganizationRegistration />;
    case 'signup-officer':
      return <OfficerRegistration />;
    default:
      return <Login />;
  }
}

function CurrentPage() {
  const { view, role } = useApp();

  if (authRoutes.includes(view as never)) {
    return <AuthPage view={view} />;
  }

  const page = view as PageKey;

  if (adminOnly.includes(page) && role !== 'admin') {
    return <Dashboard />;
  }

  if (role === 'organization' && (page === 'complaints' || page === 'reports')) {
    return <Dashboard />;
  }

  switch (page) {
    case 'dashboard':
      return role === 'admin' ? <AdminDashboard /> : <Dashboard />;
    case 'scan':
      return <ScanProduct />;
    case 'history':
      return <ScanHistory />;
    case 'complaints':
      return role === 'admin' ? <AdminDashboard initialSection="complaints" /> : <Complaints />;
    case 'analytics':
      return <Analytics />;
    case 'violation-map':
      return <ViolationMap />;
    case 'reports':
      return <Reports />;
    case 'profile':
      return <Profile />;
    case 'settings':
      return <Settings />;
    default:
      return <Dashboard />;
  }
}

function Shell() {
  const { view, isAuthenticated } = useApp();

  const isAuthRoute = authRoutes.includes(view as never);

  // Protect app routes: if not authenticated and trying to access a protected page, redirect to login
  if (!isAuthenticated && !isAuthRoute) {
    return (
      <>
        <Login />
        <ToastHost />
      </>
    );
  }

  // If authenticated but on an auth route, show the app instead
  if (isAuthenticated && isAuthRoute) {
    return (
      <>
        <div className="flex min-h-screen bg-ink-50">
          <Sidebar />
          <div className="flex-1 min-w-0 flex flex-col">
            <Topbar />
            <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-7xl w-full mx-auto">
              <div key="dashboard" className="animate-fade-in">
                <Dashboard />
              </div>
            </main>
          </div>
        </div>
        <ToastHost />
      </>
    );
  }

  if (isAuthRoute) {
    return (
      <>
        <AuthPage view={view} />
        <ToastHost />
      </>
    );
  }

  return (
    <>
      <div className="flex min-h-screen bg-ink-50">
        <Sidebar />
        <div className="flex-1 min-w-0 flex flex-col">
          <Topbar />
          <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-7xl w-full mx-auto">
            <div key={view} className="animate-fade-in">
              <CurrentPage />
            </div>
          </main>
        </div>
      </div>
      <ToastHost />
    </>
  );
}

function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}

export default App;
