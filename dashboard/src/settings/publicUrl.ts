import publicUrlRules from '../../../shared/public-url-rules.json'

export type PublicUrlRules = typeof publicUrlRules

export function loadPublicUrlRules(): PublicUrlRules {
  return publicUrlRules
}

function hostList(key: 'reject_exact' | 'reject_prefixes' | 'reject_suffixes' | 'allow_exact' | 'allow_suffixes' | 'allow_wildcards'): string[] {
  const hosts = loadPublicUrlRules().hosts
  return (hosts[key] || []).map((item) => item.toLowerCase())
}

function wildcardMatch(host: string, pattern: string): boolean {
  if (pattern === '*') {
    return true
  }
  if (pattern.startsWith('*.')) {
    const suffix = pattern.slice(1)
    return host.endsWith(suffix)
  }
  return host === pattern
}

function hostAllowed(host: string): boolean {
  if (hostList('allow_exact').includes(host)) {
    return true
  }
  if (hostList('allow_suffixes').some((suffix) => host.endsWith(suffix))) {
    return true
  }
  return hostList('allow_wildcards').some((pattern) => wildcardMatch(host, pattern))
}

function hostRejected(host: string): PublicUrlReason | null {
  if (hostAllowed(host)) {
    return null
  }
  if (hostList('reject_exact').includes(host)) {
    if (host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '0.0.0.0' || host === '[::1]' || host.startsWith('127.')) {
      return 'loopback'
    }
    return 'internal_docker_host'
  }
  for (const prefix of hostList('reject_prefixes')) {
    if (host.startsWith(prefix)) {
      return prefix.startsWith('127.') ? 'loopback' : 'internal_docker_host'
    }
  }
  for (const suffix of hostList('reject_suffixes')) {
    if (host.endsWith(suffix)) {
      return 'private_only_tld'
    }
  }
  if (loadPublicUrlRules().hosts.reject_single_label && !host.includes('.')) {
    return 'internal_docker_host'
  }
  return null
}

export type PublicUrlReason =
  | 'empty'
  | 'invalid'
  | 'missing_http_scheme'
  | 'missing_host'
  | 'loopback'
  | 'internal_docker_host'
  | 'private_only_tld'

export type PublicUrlStatus = 'valid' | 'empty' | 'invalid'

export interface PublicUrlCheck {
  status: PublicUrlStatus
  reason: PublicUrlReason | null
  cleaned: string | null
  label: string
  explanation: string | null
  logReason: string | null
}

const EXPLANATIONS: Record<Exclude<PublicUrlReason, 'empty'>, string> = {
  invalid: 'This URL cannot be opened by Telegram.',
  missing_http_scheme: 'This URL cannot be opened by Telegram.',
  missing_host: 'This URL cannot be opened by Telegram.',
  loopback: 'This URL cannot be opened by Telegram.',
  internal_docker_host: 'This address is only reachable inside Docker.',
  private_only_tld: 'This URL cannot be opened by Telegram.',
}

const LOG_REASON: Record<Exclude<PublicUrlReason, 'empty'>, string> = {
  invalid: 'invalid',
  missing_http_scheme: 'not_http',
  missing_host: 'invalid',
  loopback: 'loopback',
  internal_docker_host: 'docker_internal',
  private_only_tld: 'private_tld',
}

export function publicUrlRejectionReason(url: string | null | undefined): PublicUrlReason | null {
  const text = (url || '').trim()
  if (!text) {
    return 'empty'
  }
  let parsed: URL
  try {
    parsed = new URL(text.includes('://') ? text : `https://${text}`)
  } catch {
    return 'invalid'
  }
  const scheme = parsed.protocol.replace(':', '').toLowerCase()
  const allow = loadPublicUrlRules().schemes.allow.map((item) => item.toLowerCase())
  if (!allow.includes(scheme)) {
    return 'missing_http_scheme'
  }
  const host = (parsed.hostname || '').toLowerCase().replace(/\.$/, '')
  if (!host) {
    return 'missing_host'
  }
  return hostRejected(host)
}

export function validatePublicUrl(url: string | null | undefined): string | null {
  const reason = publicUrlRejectionReason(url)
  const text = (url || '').trim()
  if (reason) {
    return null
  }
  try {
    const parsed = new URL(text.includes('://') ? text : `https://${text}`)
    const cleaned = `${parsed.protocol}//${parsed.host}${parsed.pathname}`.replace(/\/$/, '')
    return cleaned || null
  } catch {
    return null
  }
}

export function inspectPublicUrl(url: string | null | undefined): PublicUrlCheck {
  const reason = publicUrlRejectionReason(url)
  if (reason === 'empty') {
    return {
      status: 'empty',
      reason: 'empty',
      cleaned: null,
      label: 'Empty',
      explanation: null,
      logReason: null,
    }
  }
  if (reason) {
    return {
      status: 'invalid',
      reason,
      cleaned: null,
      label: 'Invalid',
      explanation: EXPLANATIONS[reason],
      logReason: LOG_REASON[reason],
    }
  }
  return {
    status: 'valid',
    reason: null,
    cleaned: validatePublicUrl(url),
    label: 'Valid',
    explanation: null,
    logReason: null,
  }
}

export const PUBLIC_URL_STORAGE_KEY = 'homelab-monitor.telegram-public-urls'

export interface TelegramPublicUrls {
  dashboard: string
  immich: string
  qnap: string
}

export const EMPTY_PUBLIC_URLS: TelegramPublicUrls = {
  dashboard: '',
  immich: '',
  qnap: '',
}

export function loadStoredPublicUrls(): TelegramPublicUrls {
  if (typeof window === 'undefined' || !('localStorage' in window)) {
    return { ...EMPTY_PUBLIC_URLS }
  }
  try {
    const raw = window.localStorage.getItem(PUBLIC_URL_STORAGE_KEY)
    if (!raw) {
      return { ...EMPTY_PUBLIC_URLS }
    }
    const parsed = JSON.parse(raw) as Partial<TelegramPublicUrls>
    return {
      dashboard: typeof parsed.dashboard === 'string' ? parsed.dashboard : '',
      immich: typeof parsed.immich === 'string' ? parsed.immich : '',
      qnap: typeof parsed.qnap === 'string' ? parsed.qnap : '',
    }
  } catch {
    return { ...EMPTY_PUBLIC_URLS }
  }
}

export function persistPublicUrls(urls: TelegramPublicUrls): void {
  if (typeof window === 'undefined' || !('localStorage' in window)) {
    return
  }
  window.localStorage.setItem(PUBLIC_URL_STORAGE_KEY, JSON.stringify(urls))
}

export function publicUrlSaveWarnings(urls: TelegramPublicUrls): string[] {
  const labels: Array<[keyof TelegramPublicUrls, string]> = [
    ['dashboard', 'Dashboard'],
    ['immich', 'Immich'],
    ['qnap', 'QNAP'],
  ]
  return labels.flatMap(([key, name]) => {
    const check = inspectPublicUrl(urls[key])
    if (check.status !== 'invalid') {
      return []
    }
    return [`${name} URL is invalid. Telegram messages will be sent without the ${name} button.`]
  })
}
