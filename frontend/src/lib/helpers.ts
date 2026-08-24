export function formatRupee(amount: number): string {
  if (isNaN(amount)) return 'Rs. 0';
  
  const absAmount = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';

  if (absAmount >= 10000000) {
    return `${sign}Rs. ${(absAmount / 10000000).toFixed(1).replace(/\.0$/, '')}Cr`;
  } else if (absAmount >= 100000) {
    return `${sign}Rs. ${(absAmount / 100000).toFixed(1).replace(/\.0$/, '')}L`;
  } else if (absAmount >= 1000) {
    return `${sign}Rs. ${(absAmount / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  } else {
    return `${sign}Rs. ${absAmount.toLocaleString('en-IN')}`;
  }
}

export function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export const API_BASE = 'https://ttl5233zd1.execute-api.ap-south-1.amazonaws.com/prod';
