import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const root = join(dirname(fileURLToPath(import.meta.url)), '../..')

describe('offline page', () => {
  it('shows HomeLab Monitor and Server Offline without caching API', () => {
    const html = readFileSync(join(root, 'public/offline.html'), 'utf8')
    expect(html).toContain('<h1>HomeLab Monitor</h1>')
    expect(html).toContain('Server Offline')
    expect(html).toContain('/offline.css')
    expect(html).not.toContain('/api/')
  })
})
