// Router paths stay relative to the application; browser URLs need its prefix.
export const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');

export function appUrl (value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return value;
  if (basePath && (value === basePath || value.startsWith(`${basePath}/`) || value.startsWith(`${basePath}?`))) return value;
  return `${basePath}${value}`;
}

export function appSrcset (value) {
  return value.split(',').map(candidate => appUrl(candidate.trim())).join(', ');
}
