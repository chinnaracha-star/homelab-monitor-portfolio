import { describe, expect, it } from 'vitest'
import {
  inspectPublicUrl,
  publicUrlRejectionReason,
  publicUrlSaveWarnings,
  validatePublicUrl,
} from './publicUrl'

describe('validatePublicUrl', () => {
  it('accepts public HTTPS hosts', () => {
    expect(validatePublicUrl('https://example.com')).toBe('https://example.com')
    expect(validatePublicUrl('https://monitor.example.com')).toBe(
      'https://monitor.example.com',
    )
    expect(inspectPublicUrl('https://example.com').status).toBe('valid')
  })

  it('treats empty as omit-button', () => {
    expect(validatePublicUrl('')).toBeNull()
    expect(inspectPublicUrl('   ').status).toBe('empty')
  })

  it('rejects localhost, Docker hostnames, and ftp', () => {
    expect(publicUrlRejectionReason('http://localhost')).toBe('loopback')
    expect(publicUrlRejectionReason('http://127.0.0.1')).toBe('loopback')
    expect(publicUrlRejectionReason('http://dashboard:8080')).toBe('internal_docker_host')
    expect(publicUrlRejectionReason('http://api:8000')).toBe('internal_docker_host')
    expect(publicUrlRejectionReason('ftp://example.com/file')).toBe('missing_http_scheme')
    expect(inspectPublicUrl('http://dashboard:8080').explanation).toContain('Docker')
    expect(inspectPublicUrl('ftp://example.com').explanation).toContain('Telegram')
  })

  it('builds save warnings without blocking', () => {
    const warnings = publicUrlSaveWarnings({
      dashboard: 'http://dashboard:8080',
      immich: 'https://immich.example',
      qnap: '',
    })
    expect(warnings).toEqual([
      'Dashboard URL is invalid. Telegram messages will be sent without the Dashboard button.',
    ])
  })
})
