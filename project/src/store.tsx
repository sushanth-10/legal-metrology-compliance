import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import type { PageKey, Role, Scan, Complaint, User, View, AuthRoute, GeneratedReport, ComplaintFilters, OrganizationRegistration } from '@/types';
import { apiBaseUrl, apiJson } from '@/lib/api';
import { languageOptions, translate, type LanguageCode, type TranslationKey } from '@/lib/i18n';

const STORAGE_KEY = 'niriksha_session';
const PREFERENCES_KEY = 'niriksha_preferences';

export interface AppPreferences {
  darkMode: boolean;
  language: LanguageCode;
}

const defaultPreferences: AppPreferences = { darkMode: false, language: 'en' };
const languageCodes = new Set(languageOptions.map((option) => option.code));

function loadPreferences(): AppPreferences {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    if (!raw) return defaultPreferences;
    const parsed = JSON.parse(raw) as Partial<AppPreferences>;
    const language = typeof parsed.language === 'string' && languageCodes.has(parsed.language as LanguageCode)
      ? parsed.language as LanguageCode
      : defaultPreferences.language;
    return { darkMode: parsed.darkMode === true, language };
  } catch {
    return defaultPreferences;
  }
}

function savePreferences(preferences: AppPreferences) {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
  } catch {
    /* ignore */
  }
}

function normalizeScan(scan: Scan): Scan {
  const normalizeImageList = (values?: string[]) =>
    values
      ? values.map((value) => (value && value.startsWith('/') ? `${apiBaseUrl()}${value}` : value))
      : undefined;

  const imageUrls = normalizeImageList(scan.images);
  const primaryImage = scan.image?.startsWith('/') ? `${apiBaseUrl()}${scan.image}` : scan.image;
  return {
    ...scan,
    image: primaryImage,
    images: imageUrls && imageUrls.length > 0 ? imageUrls : primaryImage ? [primaryImage] : undefined,
  };
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

const emptyUser: User = { name: 'Organization', role: 'organization', email: '', location: '', joined: '' };
const activeRoles = new Set<Role>(['organization', 'officer', 'admin']);

function normalizeComplaint(complaint: Complaint): Complaint {
  const images = (complaint.evidenceImages || []).map((value) => value && value.startsWith('/') ? `${apiBaseUrl()}${value}` : value);
  const image = complaint.image?.startsWith('/') ? `${apiBaseUrl()}${complaint.image}` : complaint.image;
  const statusMap: Record<string, Complaint['status']> = { under_review: 'in-progress', review: 'in-progress', investigating: 'in-progress', in_progress: 'in-progress' };
  const status = statusMap[complaint.status] || complaint.status;
  return { ...complaint, status, image: image || images[0] || '', evidenceImages: images.length ? images : image ? [image] : [] };
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
  authenticate: (loginId: string, password: string, role: Role, otp?: string) => Promise<boolean>;
  registerOrganization: (registration: OrganizationRegistration) => Promise<boolean>;
  logout: () => void;
  scans: Scan[];
  scansLoading: boolean;
  addScan: (s: Scan) => void;
  refreshScans: (filters?: { search?: string; status?: string; date?: string }) => Promise<void>;
  reports: GeneratedReport[];
  reportsLoading: boolean;
  addReport: (report: GeneratedReport) => void;
  refreshReports: () => Promise<void>;
  complaints: Complaint[];
  complaintsLoading: boolean;
  refreshComplaints: (filters?: ComplaintFilters) => Promise<void>;
  loadComplaint: (id: string) => Promise<Complaint>;
  addComplaint: (c: Partial<Complaint> & { scanId?: string; evidenceImages?: string[] }) => Promise<boolean>;
  updateComplaintStatus: (id: string, status: Complaint['status'], adminRemark?: string, jurisdiction?: { state?: string; district?: string }) => Promise<void>;
  selectedScanId: string | null;
  setSelectedScanId: (id: string | null) => void;
  mobileNavOpen: boolean;
  setMobileNavOpen: (v: boolean) => void;
  toasts: Toast[];
  showToast: (type: Toast['type'], message: string) => void;
  dismissToast: (id: number) => void;
  preferences: AppPreferences;
  setPreferences: (preferences: AppPreferences) => void;
  t: (key: TranslationKey) => string;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setAuthed] = useState(false);
  const [role, setRole] = useState<Role>('organization');
  const [view, setViewRaw] = useState<View>('login');
  const [scans, setScans] = useState<Scan[]>([]);
  const [scansLoading, setScansLoading] = useState(false);
  const [reports, setReports] = useState<GeneratedReport[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [complaints, setComplaints] = useState<Complaint[]>([]);
  const [complaintsLoading, setComplaintsLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<User>(emptyUser);
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [preferences, setPreferencesState] = useState<AppPreferences>(() => loadPreferences());

  const setPreferences = useCallback((next: AppPreferences) => {
    setPreferencesState(next);
    savePreferences(next);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', preferences.darkMode);
    document.documentElement.lang = preferences.language;
    document.documentElement.dir = preferences.language === 'ur' ? 'rtl' : 'ltr';
  }, [preferences]);

  useEffect(() => {
    const s = loadSession();
    if (s?.isAuthenticated && s.token && activeRoles.has(s.role)) {
      setAuthed(true);
      setRole(s.role);
      if (s.user) setCurrentUser(s.user);
      setViewRaw('dashboard');
    } else if (s?.isAuthenticated) {
      saveSession(null);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setScansLoading(false);
      return;
    }
    const session = loadSession();
    if (!session?.token) {
      setScansLoading(false);
      return;
    }
    let mounted = true;
    setScansLoading(true);
    const loadPersistentData = async () => {
      try {
        const [persistedScans, persistedProfile] = await Promise.all([
          apiJson<Scan[]>('/api/scans'),
          apiJson<User>('/api/profile'),
        ]);
        if (mounted) {
          setScans(persistedScans.map(normalizeScan));
          setCurrentUser(persistedProfile);
          saveSession({ ...session, name: persistedProfile.name, user: persistedProfile });
        }
      } catch (error) {
        console.error(error);
        if (mounted) console.error('Persistent NIRIKSHA data is unavailable:', error);
      } finally {
        if (mounted) setScansLoading(false);
      }
    };
    void loadPersistentData();
    return () => { mounted = false; };
  }, [isAuthenticated]);

  const user: User = currentUser || emptyUser;

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

  const authenticate = useCallback(async (loginId: string, password: string, requestedRole: Role, otp?: string) => {
    try {
      const response = await apiJson<{ token: string; user: { id: string; loginId: string; name: string; role: Role; email: string; location: string; officerId?: string; organizationId?: string; state?: string; district?: string; designation?: string; department?: string } }>('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login_id: loginId, password, role: requestedRole, otp }),
      });
      const profile: User = { name: response.user.name, role: response.user.role, email: response.user.email, location: response.user.location, officerId: response.user.officerId, organizationId: response.user.organizationId, state: response.user.state, district: response.user.district, designation: response.user.designation, department: response.user.department, joined: 'Account' };
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

  const registerOrganization = useCallback(async (registration: OrganizationRegistration) => {
    try {
      const response = await apiJson<{ token: string; user: { role: Role; name: string; email: string; location: string; officerId?: string; organizationId?: string; state?: string; district?: string } }>('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ organization_name: registration.organizationName, organization_type: registration.organizationType, login_id: registration.officialEmail, password: registration.password, name: registration.organizationName, email: registration.officialEmail, official_mobile: registration.officialMobile, address: registration.registeredAddress, state: registration.state, district: registration.district, pin_code: registration.pinCode, gstin: registration.gstin, registration_number: registration.registrationNumber, authorized_representative_name: registration.representativeName, authorized_representative_designation: registration.representativeDesignation, authorized_representative_contact: registration.representativeContact, website: registration.website, industry: registration.industry, role: 'organization' }) });
      const profile: User = { name: response.user.name, role: response.user.role, email: response.user.email, location: response.user.location, officerId: response.user.officerId, organizationId: response.user.organizationId, state: response.user.state, district: response.user.district, joined: 'Account' };
      setAuthed(true); setRole(response.user.role); setCurrentUser(profile);
      saveSession({ isAuthenticated: true, role: response.user.role, name: profile.name, token: response.token, user: profile });
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
    setRole('organization');
    setCurrentUser(emptyUser);
    setScans([]);
    setReports([]);
    setSelectedScanId(null);
    setMobileNavOpen(false);
    navigate('login');
    showToast('success', 'Logged out successfully.');
  }, [navigate, showToast]);

  const addScan = useCallback((s: Scan) => setScans((prev) => [normalizeScan(s), ...prev.filter((item) => item.id !== s.id)]), []);
  const refreshScans = useCallback(async (filters: { search?: string; status?: string; date?: string } = {}) => {
    setScansLoading(true);
    try {
      const query = new URLSearchParams({ limit: '50' });
      Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
      const result = await apiJson<Scan[]>(`/api/scans?${query.toString()}`);
      setScans(result.map(normalizeScan));
    } finally {
      setScansLoading(false);
    }
  }, []);
  const addReport = useCallback((report: GeneratedReport) => {
    setReports((prev) => {
      const next = [report, ...prev.filter((item) => item.scanId !== report.scanId)];
      return next;
    });
  }, []);
  const refreshComplaints = useCallback(async (filters: ComplaintFilters = {}) => {
    setComplaintsLoading(true);
    try {
      const query = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
      const path = query.toString() ? `/api/complaints?${query.toString()}` : '/api/complaints';
      const result = await apiJson<Complaint[]>(path);
      setComplaints(result.map(normalizeComplaint));
    } finally {
      setComplaintsLoading(false);
    }
  }, []);

  const refreshReports = useCallback(async () => {
    setReportsLoading(true);
    try {
      const result = await apiJson<GeneratedReport[]>('/api/reports?limit=50');
      setReports(result);
    } finally {
      setReportsLoading(false);
    }
  }, []);

  const loadComplaint = useCallback(async (id: string) => {
    const result = await apiJson<Complaint>(`/api/complaints/${encodeURIComponent(id)}`);
    return normalizeComplaint(result);
  }, []);

  const addComplaint = useCallback(async (c: Partial<Complaint> & { scanId?: string; evidenceImages?: string[] }) => {
    try {
      const created = await apiJson<Complaint>('/api/complaints', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product: c.product, category: c.category, description: c.description, location: c.location, scan_id: c.scanId, evidence_images: c.evidenceImages || [] }),
      });
      setComplaints((prev) => [normalizeComplaint(created), ...prev.filter((item) => item.id !== created.id)]);
      showToast('success', 'Complaint submitted successfully.');
      return true;
    } catch (error) {
      showToast('error', error instanceof Error ? error.message : 'Complaint could not be submitted.');
      return false;
    }
  }, [showToast]);

  const updateComplaintStatus = useCallback(async (id: string, status: Complaint['status'], adminRemark?: string, jurisdiction?: { state?: string; district?: string }) => {
    const backendStatus = status === 'review' || status === 'in-progress' ? 'IN_PROGRESS' : status === 'action-taken' ? 'ACTION_TAKEN' : status.toUpperCase().replace('-', '_');
    try {
      const updated = await apiJson<{ id: string; status: string; updatedBy: string; remark?: string | null }>(`/api/complaints/${encodeURIComponent(id)}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: backendStatus, admin_remark: adminRemark, state: jurisdiction?.state, district: jurisdiction?.district }),
      });
      setComplaints((prev) => prev.map((c) => (c.id === id ? { ...c, status: (updated.status || status).toLowerCase() as Complaint['status'], adminRemark: updated.remark } : c)));
    } catch (error) {
      console.error(error);
      showToast('error', error instanceof Error ? error.message : 'Complaint status could not be updated.');
      throw error;
    }
  }, [showToast]);

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
        authenticate,
        registerOrganization,
        logout,
        scans,
        scansLoading,
        addScan,
        refreshScans,
        reports,
        reportsLoading,
        addReport,
        refreshReports,
        complaints,
        complaintsLoading,
        refreshComplaints,
        loadComplaint,
        addComplaint,
        updateComplaintStatus,
        selectedScanId,
        setSelectedScanId,
        mobileNavOpen,
        setMobileNavOpen,
        toasts,
        showToast,
        dismissToast,
        preferences,
        setPreferences,
        t: (key) => translate(preferences.language, key),
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

export const authRoutes: AuthRoute[] = ['login', 'admin-login', 'signup', 'signup-organization', 'signup-officer'];
