import logoUrl from '../../assets/niriksha-logo.jpeg';

export function Logo({ className = 'h-12 w-auto', alt = 'NIRIKSHA' }: { className?: string; alt?: string }) {
  return <img src={logoUrl} alt={alt} className={`object-contain ${className}`} />;
}
