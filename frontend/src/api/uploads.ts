import { request } from './http'

export interface UploadResult {
  url: string
  size: number
}

export type UploadPurpose = 'pet' | 'report'

export function validateImage(file: File, maxMb = 10): string | null {
  if (!file.type.startsWith('image/')) return '请选择图片文件'
  if (file.size > maxMb * 1024 * 1024) return `图片不能超过 ${maxMb}MB`
  return null
}

export function uploadImage(
  file: File,
  purpose: UploadPurpose = 'pet',
): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('purpose', purpose)
  return request.post<UploadResult>('/uploads', form, { timeout: 60_000 })
}
