import type { Role } from '@/types';

export const mockCredentials: Record<Role, { id: string; password: string; name: string }> = {
  consumer: { id: 'consumer@test.com', password: 'password123', name: 'Aarav Sharma' },
  officer: { id: 'OFFICER001', password: 'password123', name: 'Inspector Meera Iyer' },
};

export function validateRequired(value: string, label: string): string | null {
  return value.trim() ? null : `${label} is required`;
}

export function validateMobile(value: string): string | null {
  const digits = value.replace(/\D/g, '');
  return /^[6-9]\d{9}$/.test(digits) ? null : 'Enter a valid 10-digit mobile number';
}

export function validateEmail(value: string): string | null {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()) ? null : 'Enter a valid email address';
}

export function validateAadhaar(value: string): string | null {
  const digits = value.replace(/\D/g, '');
  return /^\d{12}$/.test(digits) ? null : 'Enter a valid 12-digit Aadhaar number';
}

export function validateOtp(value: string): string | null {
  return /^\d{6}$/.test(value) ? null : 'Enter the 6-digit OTP';
}

export function validatePassword(value: string): string | null {
  if (value.length < 8) return 'Password must be at least 8 characters';
  return null;
}

export function validateConfirmPassword(value: string, password: string): string | null {
  return value === password ? null : 'Passwords do not match';
}

export function validateOfficerId(value: string): string | null {
  return /^OFFICER\d{3,}$/i.test(value.trim()) ? null : 'Enter a valid officer ID';
}

export function validateFile(file: File): string | null {
  const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png'];
  const maxSize = 5 * 1024 * 1024;
  if (!allowedTypes.includes(file.type)) return 'Upload a PDF, JPG, or PNG file';
  if (file.size > maxSize) return 'File size must be 5 MB or less';
  return null;
}

export function formatAadhaar(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 12);
  return digits.replace(/(.{4})/g, '$1 ').trim();
}

export function formatMobile(value: string): string {
  return value.replace(/\D/g, '').slice(0, 10);
}
