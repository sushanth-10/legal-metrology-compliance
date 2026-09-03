export type Role = 'organization' | 'officer' | 'admin';

export type AuthRoute = 'login' | 'admin-login' | 'signup' | 'signup-organization' | 'signup-officer';

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
export type OfficerReviewStatus = 'Verified' | 'Requires Further Verification' | 'Non-Compliant Confirmed' | 'No Violation Found';

export interface OfficerReview {
  officer_name: string;
  designation: string;
  department: string;
  inspection_location: string;
  inspection_date: string;
  inspection_remarks: string;
  recommended_action: string;
  review_status: OfficerReviewStatus;
}

export type ReportStatus = 'compliant' | 'non-compliant' | 'needs-review';

export interface ReportCheck {
  id: string;
  name: string;
  status: ReportStatus;
  value: string;
  requirement: string;
  explanation: string;
  evidence: string;
  confidence?: number | null;
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
  report_id?: string;
  scanDate?: string;
  officerName?: string;
  pdfUrl?: string;
  extractedData?: Record<string, unknown>;
  designation?: string;
  department?: string;
  inspectionRemarks?: string;
  recommendedAction?: string;
  reviewStatus?: string;
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
  images?: string[];
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
  scan_id?: string;
  extractedData?: Record<string, unknown>;
  checks?: Array<{ id: string | number; label: string; status: string; value: string; reference: string; explanation: string; evidence?: string; confidence?: number | null }>;
  complianceScore?: number;
  officerReview?: Partial<OfficerReview>;
}

export type ComplaintStatus = 'new' | 'viewed' | 'in-progress' | 'review' | 'investigating' | 'action-taken' | 'resolved' | 'closed';

export interface ComplaintStatusEvent {
  id: string;
  previousStatus?: string | null;
  newStatus: string;
  changedBy?: string | null;
  changedAt: string;
  administrativeRemark?: string | null;
}

export interface ComplaintFilters {
  search?: string;
  state?: string;
  district?: string;
  status?: string;
  category?: string;
  date?: string;
}

export interface OrganizationRegistration {
  organizationName: string;
  organizationType: string;
  officialEmail: string;
  officialMobile: string;
  registeredAddress: string;
  state: string;
  district: string;
  pinCode: string;
  gstin: string;
  registrationNumber: string;
  representativeName: string;
  representativeDesignation: string;
  representativeContact: string;
  password: string;
  confirmPassword: string;
  website?: string;
  industry?: string;
}

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
  organizationId?: string | null;
  organizationName?: string | null;
  scanId?: string | null;
  reportId?: string | null;
  state?: string | null;
  district?: string | null;
  adminRemark?: string | null;
  updatedAt?: string;
  evidenceImages?: string[];
  history?: ComplaintStatusEvent[];
  relatedScan?: {
    id: string;
    product: string;
    status: string;
    complianceScore?: number | null;
    scannedAt?: string | null;
  } | null;
  relatedReport?: {
    id: string;
    generatedAt?: string | null;
    status?: string | null;
  } | null;
}

export interface User {
  name: string;
  role: Role;
  email: string;
  location: string;
  officerId?: string;
  organizationId?: string;
  organizationName?: string;
  organizationType?: string;
  state?: string;
  district?: string;
  joined: string;
  designation?: string;
  department?: string;
}

export interface AuthSession {
  isAuthenticated: boolean;
  user: User | null;
}
