import { describe, expect, it } from 'vitest'
import cases from '../../../shared/public-url-cases.json'
import { loadPublicUrlRules, publicUrlRejectionReason, validatePublicUrl } from './publicUrl'

describe('shared public URL rules', () => {
  it('loads the shared rule file', () => {
    const rules = loadPublicUrlRules()
    expect(rules.schemes.allow).toEqual(['http', 'https'])
    expect(rules.hosts.reject_exact).toContain('dashboard')
    expect(rules.hosts.reject_suffixes).toContain('.internal')
    expect(rules.hosts.allow_exact).toEqual([])
    expect(rules.hosts.allow_wildcards).toEqual([])
    expect(rules.overrides).toHaveProperty('development')
    expect(rules.overrides).toHaveProperty('production')
  })

  it.each(cases)('matches golden case $url', (item) => {
    const reason = publicUrlRejectionReason(item.url)
    const accepted = validatePublicUrl(item.url) !== null
    expect(accepted).toBe(item.accept)
    expect(reason).toBe(item.reason)
  })
})
