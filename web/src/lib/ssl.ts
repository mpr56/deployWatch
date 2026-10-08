// SSL expiry helpers. Warn at 14 days; certificates on auto-renew (Let's
// Encrypt, Vercel, Railway) renew at 30, so a warning means renewal failed.

export const SSL_WARN_DAYS = 14;

export function sslDaysLeft(expires: string | null): number | null {
  if (!expires) return null;
  return Math.floor((new Date(expires).getTime() - Date.now()) / 86_400_000);
}

/** null when there is nothing worth showing. */
export function sslWarning(expires: string | null, error: string | null): string | null {
  if (error) return `SSL: ${error}`;
  const days = sslDaysLeft(expires);
  if (days == null || days > SSL_WARN_DAYS) return null;
  return days < 0 ? "SSL expired" : `SSL expires in ${days}d`;
}
