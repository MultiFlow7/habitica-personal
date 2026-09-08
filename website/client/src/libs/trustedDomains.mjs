// Configuration may contain bare hostnames as well as complete URLs.
export function parseTrustedDomains (value = '') {
  return value.split(',').flatMap(entry => {
    const text = entry.trim();
    if (!text) return [];
    try {
      const url = new URL(text.includes('://') ? text : `https://${text}`);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
        ? [url] : [];
    } catch (error) {
      return [];
    }
  });
}
