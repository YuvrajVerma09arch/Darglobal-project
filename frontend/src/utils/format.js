/** Formatting helpers shared by citations and property cards. */

export function formatPrice(price, currency = 'SAR') {
  if (price === null || price === undefined || price === '') return null;
  const value = Number(price);
  if (!Number.isFinite(value)) return null;
  const code = typeof currency === 'string' && currency.trim() ? currency.trim() : 'SAR';
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: code,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${code} ${value.toLocaleString('en-US')}`;
  }
}

export function formatArea(area, unit) {
  if (area === null || area === undefined || area === '') return null;
  const suffix = unit ? ` ${unit}` : ' sqm';
  return `${Number(area).toLocaleString('en-US')}${suffix}`;
}

export function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

export function titleCaseSource(source) {
  if (!source) return 'Source';
  const value = String(source);
  if (value.toLowerCase() === 'darglobal') return 'DarGlobal';
  if (value.toLowerCase() === 'wasalt') return 'Wasalt';
  return value;
}
