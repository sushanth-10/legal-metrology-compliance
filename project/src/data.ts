import type { Scan, Complaint, User, BoundingBox } from '@/types';

export const defaultUser: User = {
  name: 'Aarav Sharma',
  role: 'consumer',
  email: 'aarav.sharma@example.in',
  location: 'Bengaluru, Karnataka',
  joined: 'Jan 2024',
};

export const officerUser: User = {
  name: 'Inspector Meera Iyer',
  role: 'officer',
  email: 'meera.iyer@legalmetrology.gov.in',
  location: 'Bengaluru South Zone',
  officerId: 'LM-KA-04427',
  joined: 'Aug 2022',
};

const biscuitBoxes: BoundingBox[] = [
  { x: 8, y: 12, w: 42, h: 12, label: 'Manufacturer' },
  { x: 52, y: 12, w: 38, h: 12, label: 'Product Name' },
  { x: 8, y: 30, w: 30, h: 11, label: 'Net Quantity' },
  { x: 42, y: 30, w: 24, h: 11, label: 'MRP' },
  { x: 70, y: 30, w: 24, h: 11, label: 'Mfg Date' },
  { x: 8, y: 78, w: 84, h: 12, label: 'Consumer Care', missing: true },
];

const soapBoxes: BoundingBox[] = [
  { x: 8, y: 10, w: 84, h: 14, label: 'Manufacturer' },
  { x: 8, y: 28, w: 84, h: 14, label: 'Product Name' },
  { x: 8, y: 48, w: 40, h: 12, label: 'Net Quantity' },
  { x: 52, y: 48, w: 40, h: 12, label: 'MRP' },
  { x: 8, y: 66, w: 40, h: 12, label: 'Mfg Date' },
  { x: 52, y: 66, w: 40, h: 14, label: 'Consumer Care' },
];

const juiceBoxes: BoundingBox[] = [
  { x: 8, y: 10, w: 60, h: 13, label: 'Manufacturer' },
  { x: 70, y: 10, w: 22, h: 13, label: 'Product Name' },
  { x: 8, y: 28, w: 30, h: 11, label: 'Net Quantity' },
  { x: 42, y: 28, w: 26, h: 11, label: 'MRP' },
  { x: 72, y: 28, w: 20, h: 11, label: 'Mfg Date', missing: true },
  { x: 8, y: 70, w: 84, h: 14, label: 'Consumer Care' },
];

export const sampleScans: Scan[] = [
  {
    id: 'sc-1001',
    product: 'XYZ Biscuits 200g',
    image:
      'https://images.pexels.com/photos/1337825/pexels-photo-1337825.jpeg?auto=compress&cs=tinysrgb&w=900',
    date: 'Today, 4:32 PM',
    status: 'non-compliant',
    violations: 2,
    declaredMrp: '₹30',
    referenceMrp: '₹20',
    mrpMismatch: true,
    category: 'Food / Packaged',
    location: 'Bengaluru',
    declarations: [
      { key: 'manufacturer', label: 'Manufacturer / Packer', detected: true, value: 'XYZ Foods Pvt Ltd, Bengaluru', confidence: 0.97, region: biscuitBoxes[0] },
      { key: 'productName', label: 'Product Name', detected: true, value: 'XYZ Chocolate Biscuits', confidence: 0.95, region: biscuitBoxes[1] },
      { key: 'netQuantity', label: 'Net Quantity', detected: true, value: '200 g', confidence: 0.93, region: biscuitBoxes[2] },
      { key: 'mrp', label: 'MRP', detected: true, value: '₹30', confidence: 0.91, region: biscuitBoxes[3] },
      { key: 'manufactureDate', label: 'Date of Manufacture', detected: true, value: 'Jul 2026', confidence: 0.88, region: biscuitBoxes[4] },
      { key: 'consumerCare', label: 'Consumer Care Details', detected: false, value: '—', confidence: 0, region: biscuitBoxes[5] },
    ],
    violationList: [
      {
        id: 'v1',
        title: 'Missing Consumer Care Details',
        explanation: 'No consumer care contact (toll-free number or email) was detected on the label.',
        requirement: 'Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 6(1)(c): name and address of the manufacturer/packer/importer must include consumer care details.',
        evidence: 'Bottom region of label returned no detectable contact information.',
        severity: 'medium',
      },
      {
        id: 'v2',
        title: 'Potential MRP Discrepancy',
        explanation: 'Declared MRP (₹30) appears higher than the reference MRP (₹20) for comparable products.',
        requirement: 'Rule 6(1)(e): MRP must be declared and should not be misleading. Requires officer verification.',
        evidence: 'MRP region reads ₹30; reference database lists ₹20 for equivalent pack size.',
        severity: 'high',
      },
    ],
  },
  {
    id: 'sc-1002',
    product: 'ABC Soap 75g',
    image:
      'https://images.pexels.com/photos/4202325/pexels-photo-4202325.jpeg?auto=compress&cs=tinysrgb&w=900',
    date: 'Today, 2:15 PM',
    status: 'compliant',
    violations: 0,
    declaredMrp: '₹35',
    referenceMrp: '₹35',
    category: 'Personal Care',
    location: 'Bengaluru',
    declarations: [
      { key: 'manufacturer', label: 'Manufacturer / Packer', detected: true, value: 'ABC Consumer Products Ltd', confidence: 0.96, region: soapBoxes[0] },
      { key: 'productName', label: 'Product Name', detected: true, value: 'ABC Neem Soap', confidence: 0.94, region: soapBoxes[1] },
      { key: 'netQuantity', label: 'Net Quantity', detected: true, value: '75 g', confidence: 0.92, region: soapBoxes[2] },
      { key: 'mrp', label: 'MRP', detected: true, value: '₹35', confidence: 0.9, region: soapBoxes[3] },
      { key: 'manufactureDate', label: 'Date of Manufacture', detected: true, value: 'May 2026', confidence: 0.86, region: soapBoxes[4] },
      { key: 'consumerCare', label: 'Consumer Care Details', detected: true, value: '1800-123-4567', confidence: 0.89, region: soapBoxes[5] },
    ],
    violationList: [],
  },
  {
    id: 'sc-1003',
    product: 'Fresh Juice 1L',
    image:
      'https://images.pexels.com/photos/96974/pexels-photo-96974.jpeg?auto=compress&cs=tinysrgb&w=900',
    date: 'Yesterday',
    status: 'needs-review',
    violations: 1,
    declaredMrp: '₹120',
    referenceMrp: '₹120',
    category: 'Beverages',
    location: 'Mysuru',
    declarations: [
      { key: 'manufacturer', label: 'Manufacturer / Packer', detected: true, value: 'Fresh Beverages Pvt Ltd', confidence: 0.9, region: juiceBoxes[0] },
      { key: 'productName', label: 'Product Name', detected: true, value: 'Fresh Orange Juice', confidence: 0.82, region: juiceBoxes[1] },
      { key: 'netQuantity', label: 'Net Quantity', detected: true, value: '1 L', confidence: 0.88, region: juiceBoxes[2] },
      { key: 'mrp', label: 'MRP', detected: true, value: '₹120', confidence: 0.85, region: juiceBoxes[3] },
      { key: 'manufactureDate', label: 'Date of Manufacture', detected: false, value: '—', confidence: 0, region: juiceBoxes[4] },
      { key: 'consumerCare', label: 'Consumer Care Details', detected: true, value: 'care@freshbev.in', confidence: 0.8, region: juiceBoxes[5] },
    ],
    violationList: [
      {
        id: 'v3',
        title: 'Date of Manufacture not clearly visible',
        explanation: 'The date of manufacture / packing could not be read confidently.',
        requirement: 'Rule 6(1)(d): month and year of manufacture/packing must be declared.',
        evidence: 'Region appears smudged or low-contrast; manual review recommended.',
        severity: 'low',
      },
    ],
  },
];

export const sampleComplaints: Complaint[] = [
  {
    id: 'cp-2001',
    product: 'XYZ Biscuits 200g',
    image:
      'https://images.pexels.com/photos/1337825/pexels-photo-1337825.jpeg?auto=compress&cs=tinysrgb&w=900',
    shop: 'Sharma General Store',
    location: 'Jaynagar, Bengaluru',
    category: 'MRP Discrepancy',
    description: 'Shopkeeper charged above printed MRP. Label appears tampered.',
    status: 'new',
    submittedBy: 'Aarav Sharma',
    date: 'Today, 5:10 PM',
    relatedScans: 1,
  },
  {
    id: 'cp-2002',
    product: 'ABC Soap 75g',
    image:
      'https://images.pexels.com/photos/4202325/pexels-photo-4202325.jpeg?auto=compress&cs=tinysrgb&w=900',
    shop: 'Metro Mart',
    location: 'Indiranagar, Bengaluru',
    category: 'Missing Declarations',
    description: 'Consumer care details missing on the packaging.',
    status: 'review',
    submittedBy: 'Riya Verma',
    date: 'Yesterday',
    relatedScans: 0,
  },
  {
    id: 'cp-2003',
    product: 'Fresh Juice 1L',
    image:
      'https://images.pexels.com/photos/96974/pexels-photo-96974.jpeg?auto=compress&cs=tinysrgb&w=900',
    shop: 'QuickMart',
    location: 'Mysuru',
    category: 'Weight Discrepancy',
    description: 'Actual weight less than declared 1L on the label.',
    status: 'investigating',
    submittedBy: 'Karthik N',
    date: '2 days ago',
    relatedScans: 2,
  },
  {
    id: 'cp-2004',
    product: 'Snack Pack 50g',
    image:
      'https://images.pexels.com/photos/1640774/pexels-photo-1640774.jpeg?auto=compress&cs=tinysrgb&w=900',
    shop: 'Daily Needs',
    location: 'Whitefield, Bengaluru',
    category: 'No MRP',
    description: 'MRP not printed on the package.',
    status: 'resolved',
    submittedBy: 'Aarav Sharma',
    date: 'Last week',
    relatedScans: 0,
  },
];

export const analyticsData = {
  totals: {
    inspections: 128,
    compliant: 96,
    violations: 24,
    complaints: 18,
  },
  trend: [
    { label: 'Mon', value: 14 },
    { label: 'Tue', value: 22 },
    { label: 'Wed', value: 18 },
    { label: 'Thu', value: 28 },
    { label: 'Fri', value: 24 },
    { label: 'Sat', value: 12 },
    { label: 'Sun', value: 10 },
  ],
  categories: [
    { label: 'Food / Packaged', value: 58, color: 'bg-brand-500' },
    { label: 'Personal Care', value: 34, color: 'bg-success-500' },
    { label: 'Beverages', value: 22, color: 'bg-warning-500' },
    { label: 'Household', value: 14, color: 'bg-danger-500' },
  ],
  violationTypes: [
    { label: 'Missing MRP', value: 9 },
    { label: 'MRP Discrepancy', value: 6 },
    { label: 'Missing Consumer Care', value: 5 },
    { label: 'Net Quantity Issue', value: 4 },
  ],
};

export const violationMapData = [
  { zone: 'Jaynagar', count: 7, lat: '12.925°N', lng: '77.594°E' },
  { zone: 'Indiranagar', count: 5, lat: '12.971°N', lng: '77.641°E' },
  { zone: 'Whitefield', count: 4, lat: '12.969°N', lng: '77.750°E' },
  { zone: 'Mysuru', count: 3, lat: '12.295°N', lng: '76.639°E' },
  { zone: 'Koramangala', count: 3, lat: '12.935°N', lng: '77.624°E' },
  { zone: 'Yelahanka', count: 2, lat: '13.101°N', lng: '77.596°E' },
];

export const recentActivity = [
  { id: 'a1', text: 'Complaint CP-2001 submitted', time: '5 min ago', type: 'complaint' },
  { id: 'a2', text: 'Scan SC-1002 marked compliant', time: '2 hr ago', type: 'scan' },
  { id: 'a3', text: 'Report generated for XYZ Biscuits', time: '4 hr ago', type: 'report' },
  { id: 'a4', text: 'Officer reviewed Fresh Juice scan', time: 'Yesterday', type: 'scan' },
];
