import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import type { PageKey, Role, Scan, Complaint, User, View, AuthRoute } from '@/types';
import { defaultUser, officerUser, sampleScans, sampleComplaints } from '@/data';
import { mockCredentials } from '@/lib/validation';

const STORAGE_KEY = 'niriksha_session';

interface StoredSession {
  isAuthenticated: boolean;
  role: Role;
  name: string;
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
  logout: () => void;
  scans: Scan[];
  addScan: (s: Scan) => void;
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
  const [scans, setScans] = useState<Scan[]>(sampleScans);
  const [complaints, setComplaints] = useState<Complaint[]>(sampleComplaints);
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const s = loadSession();
    if (s?.isAuthenticated) {
      setAuthed(true);
      setRole(s.role);
      setViewRaw('dashboard');
    }
  }, []);

  const user: User = role === 'officer' ? officerUser : { ...defaultUser, name: loadSession()?.name ?? defaultUser.name };

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
      saveSession({ isAuthenticated: true, role: r, name: displayName });
      navigate('dashboard');
      showToast('success', 'Logged in successfully.');
    },
    [navigate, showToast]
  );

  const logout = useCallback(() => {
    saveSession(null);
    setAuthed(false);
    setRole('consumer');
    setSelectedScanId(null);
    setMobileNavOpen(false);
    navigate('login');
    showToast('success', 'Logged out successfully.');
  }, [navigate, showToast]);

  const addScan = useCallback((s: Scan) => setScans((prev) => [s, ...prev]), []);
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
        logout,
        scans,
        addScan,
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
