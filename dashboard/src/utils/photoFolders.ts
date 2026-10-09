const FOLDER_LABELS: Record<string, string> = {
  '/data/photos': 'Photos',
  '/data/photos/library-a': 'Library A',
  '/data/photos/library-b': 'Library B',
  '/data/photos/library-c': 'Library C',
  '/data/photos/library-d': 'Library D',
  '/data/photos/library-e': 'Library E',
}

const BASENAME_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(FOLDER_LABELS).map(([path, label]) => [path.split('/').pop()?.toLowerCase() ?? '', label]),
)

export function displayFolderName(path: string): string {
  const normalized = path.replace(/\/+$/, '') || path
  if (FOLDER_LABELS[normalized]) {
    return FOLDER_LABELS[normalized]
  }
  const base = normalized.split('/').filter(Boolean).pop() ?? normalized
  return BASENAME_LABELS[base.toLowerCase()] ?? base
}

export function watchFolderList(stats: {
  watch_folders?: string[]
  watch_folder?: string
}): string[] {
  if (stats.watch_folders?.length) {
    return stats.watch_folders
  }
  return stats.watch_folder ? [stats.watch_folder] : []
}
