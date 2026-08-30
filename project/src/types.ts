export type Role = 'consumer' | 'officer';

export type AuthRoute = 'login' | 'signup' | 'signup-consumer' | 'signup-officer';

export type PageKey =
  | 'dashboard'
  | 'scan'
  | 'history'
  | 'complaints'
  | 'analytics'
  | 'violation-map'
  | 'reports'
  | 'profile'
  | 'settings';

export type View = AuthRoute | PageKey;

export type ComplianceStatus = 'compliant' | 'non-compliant' | 'needs-review';

export type ReportStatus = 'compliant' | 'non-compliant' | 'needs-review';

export interface ReportCheck {
  id: string;
  name: string;
  status: ReportStatus;
  value: string;
  requirement: string;
  explanation: string;
  evidence: string;
}

export interface GeneratedReport {
  id: string;
  scanId: string;
  productName: string;
  generatedAt: string;
  applicationName: string;
  reportTitle: string;
  overallStatus: ComplianceStatus;
  summary: {
    violations: number;
    review: number;
    compliant: number;
    total: number;
  };
  checks: ReportCheck[];
  location?: string;
  category?: string;
  imageUrl?: string;
}

export type DeclarationKey =
  | 'manufacturer'
  | 'productName'
  | 'netQuantity'
  | 'mrp'
  | 'manufactureDate'
  | 'consumerCare';

export interface Declaration {
  key: DeclarationKey;
  label: string;
  detected: boolean;
  value: string;
  confidence: number;
  region?: BoundingBox;
}

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  missing?: boolean;
}

export interface Violation {
  id: string;
  title: string;
  explanation: string;
  requirement: string;
  evidence: string;
  severity: 'high' | 'medium' | 'low';
}

export interface Scan {
  id: string;
  product: string;
  image: string;
  date: string;
  status: ComplianceStatus;
  violations: number;
  declarations: Declaration[];
  violationList: Violation[];
  declaredMrp?: string;
  referenceMrp?: string;
  mrpMismatch?: boolean;
  category?: string;
  location?: string;
}

export type ComplaintStatus = 'new' | 'review' | 'investigating' | 'resolved';

export interface Complaint {
  id: string;
  product: string;
  image: string;
  shop: string;
  location: string;
  category: string;
  description: string;
  status: ComplaintStatus;
  submittedBy: string;
  date: string;
  relatedScans?: number;
}

export interface User {
  name: string;
  role: Role;
  email: string;
  location: string;
  officerId?: string;
  joined: string;
}

export interface AuthSession {
  isAuthenticated: boolean;
  user: User | null;
}
