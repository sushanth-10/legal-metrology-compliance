import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import type { PageKey, Role, Scan, Complaint, User, View, AuthRoute, GeneratedReport } from '@/types';
import { defaultUser, officerUser, sampleComplaints } from '@/data';
import { mockCredentials } from '@/lib/validation';
import { apiBaseUrl, apiJson } from '@/lib/api';

const STORAGE_KEY = 'niriksha_session';

function normalizeScan(scan: Scan): Scan {
  return scan.image?.startsWith('/') ? { ...scan, image: `${apiBaseUrl()}${scan.image}` } : scan;
}

interface StoredSession {
  isAuthenticated: boolean;
  role: Role;
  name: string;
  token?: string;
  user?: User;
}

function loadSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

function saveSession(s: StoredSession | null) {
  try {
    if (s) localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export interface Toast {
  id: number;
  type: 'success' | 'error' | 'info';
  message: string;
}

interface AppState {
  user: User;
  role: Role;
  isAuthenticated: boolean;
  view: View;
  setView: (v: View) => void;
  setPage: (p: PageKey) => void;
  navigate: (v: View) => void;
  login: (role: Role, name?: string) => void;
  authenticate: (loginId: string, password: string, role: Role) => Promise<boolean>;
  register: (loginId: string, password: string, name: string, email: string) => Promise<boolean>;
  logout: () => void;
  scans: Scan[];
  addScan: (s: Scan) => void;
  reports: GeneratedReport[];
  addReport: (report: GeneratedReport) => void;
  complaints: Complaint[];
  addComplaint: (c: Complaint) => void;
  updateComplaintStatus: (id: string, status: Complaint['status']) => void;
  selectedScanId: string | null;
  setSelectedScanId: (id: string | null) => void;
  mobileNavOpen: boolean;
  setMobileNavOpen: (v: boolean) => void;
  toasts: Toast[];
  showToast: (type: Toast['type'], message: string) => void;
  dismissToast: (id: number) => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setAuthed] = useState(false);
  const [role, setRole] = useState<Role>('consumer');
  const [view, setViewRaw] = useState<View>('login');
  const [scans, setScans] = useState<Scan[]>([]);
  const [reports, setReports] = useState<GeneratedReport[]>([]);
  const [complaints, setComplaints] = useState<Complaint[]>(sampleComplaints);
  const [currentUser, setCurrentUser] = useState<User>(defaultUser);
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const s = loadSession();
    if (s?.isAuthenticated && s.token) {
      setAuthed(true);
      setRole(s.role);
      if (s.user) setCurrentUser(s.user);
      setViewRaw('dashboard');
    } else if (s?.isAuthenticated) {
      saveSession(null);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    const session = loadSession();
    if (!session?.token) return;
    let mounted = true;
    const loadPersistentData = async () => {
      try {
        const persistedScans = await apiJson<Scan[]>('/api/scans');
        if (mounted) setScans(persistedScans.map(normalizeScan));
        if (role === 'officer') {
          const persistedReports = await apiJson<GeneratedReport[]>('/api/reports');
          if (mounted) setReports(persistedReports);
        } else if (mounted) {
          setReports([]);
        }
      } catch (error) {
        console.error(error);
        if (mounted) console.error('Persistent NIRIKSHA data is unavailable:', error);
      }
    };
    void loadPersistentData();
    return () => { mounted = false; };
  }, [isAuthenticated, role, view]);

  const user: User = currentUser || (role === 'officer' ? officerUser : defaultUser);

  const showToast = useCallback((type: Toast['type'], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const navigate = useCallback((v: View) => {
    setViewRaw(v);
    setMobileNavOpen(false);
    if (typeof window !== 'undefined') window.scrollTo(0, 0);
  }, []);

  const setPage = useCallback((p: PageKey) => navigate(p), [navigate]);

  const setView = useCallback((v: View) => navigate(v), [navigate]);

  const login = useCallback(
    (r: Role, name?: string) => {
      setAuthed(true);
      setRole(r);
      const displayName = name ?? mockCredentials[r].name;
      const profile = r === 'officer' ? { ...officerUser, name: displayName } : { ...defaultUser, name: displayName };
      setCurrentUser(profile);
      saveSession({ isAuthenticated: true, role: r, name: displayName, user: profile });
      navigate('dashboard');
      showToast('success', 'Logged in successfully.');
    },
    [navigate, showToast]
  );

  const authenticate = useCallback(async (loginId: string, password: string, requestedRole: Role) => {
    try {
      const response = await apiJson<{ token: string; user: { id: string; loginId: string; name: string; role: Role; email: string; location: string; officerId?: string } }>('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login_id: loginId, password, role: requestedRole }),
      });
      const profile: User = { name: response.user.name, role: response.user.role, email: response.user.email, location: response.user.location, officerId: response.user.officerId, joined: 'Demo account' };
      setAuthed(true);
      setRole(response.user.role);
      setCurrentUser(profile);
      saveSession({ isAuthenticated: true, role: response.user.role, name: response.user.name, token: response.token, user: profile });
      navigate('dashboard');
      showToast('success', 'Logged in successfully.');
      return true;
    } catch (error) {
      showToast('error', error instanceof Error ? error.message : 'Unable to sign in.');
      return false;
    }
  }, [navigate, showToast]);

  const register = useCallback(async (loginId: string, password: string, name: string, email: string) => {
    try {
      const response = await apiJson<{ token: string; user: { role: Role; name: string; email: string; location: string; officerId?: string } }>('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login_id: loginId, password, name, email, role: 'consumer' }) });
      const profile: User = { name: response.user.name, role: response.user.role, email: response.user.email, location: response.user.location, officerId: response.user.officerId, joined: 'Today' };
      setAuthed(true); setRole('consumer'); setCurrentUser(profile);
      saveSession({ isAuthenticated: true, role: 'consumer', name: profile.name, token: response.token, user: profile });
      navigate('dashboard');
      showToast('success', 'Account created successfully.');
      return true;
    } catch (error) {
      showToast('error', error instanceof Error ? error.message : 'Unable to create the account.');
      return false;
    }
  }, [navigate, showToast]);

  const logout = useCallback(() => {
    saveSession(null);
    setAuthed(false);
    setRole('consumer');
    setCurrentUser(defaultUser);
    setScans([]);
    setReports([]);
    setSelectedScanId(null);
    setMobileNavOpen(false);
    navigate('login');
    showToast('success', 'Logged out successfully.');
  }, [navigate, showToast]);

  const addScan = useCallback((s: Scan) => setScans((prev) => [normalizeScan(s), ...prev.filter((item) => item.id !== s.id)]), []);
  const addReport = useCallback((report: GeneratedReport) => {
    setReports((prev) => {
      const next = [report, ...prev.filter((item) => item.scanId !== report.scanId)];
      return next;
    });
  }, []);
  const addComplaint = useCallback((c: Complaint) => setComplaints((prev) => [c, ...prev]), []);
  const updateComplaintStatus = useCallback((id: string, status: Complaint['status']) => {
    setComplaints((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)));
  }, []);

  return (
    <Ctx.Provider
      value={{
        user,
        role,
        isAuthenticated,
        view,
        setView,
        setPage,
        navigate,
        login,
        authenticate,
        register,
        logout,
        scans,
        addScan,
        reports,
        addReport,
        complaints,
        addComplaint,
        updateComplaintStatus,
        selectedScanId,
        setSelectedScanId,
        mobileNavOpen,
        setMobileNavOpen,
        toasts,
        showToast,
        dismissToast,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

export const authRoutes: AuthRoute[] = ['login', 'signup', 'signup-consumer', 'signup-officer'];
