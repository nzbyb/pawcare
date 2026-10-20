const SPECIES_LABELS: Record<string, string> = {
  dog: '狗狗',
  cat: '猫咪',
  other: '其他',
}

const GENDER_LABELS: Record<string, string> = {
  male: '男孩子',
  female: '女孩子',
  unknown: '未知',
}

const RECORD_TYPE_LABELS: Record<string, string> = {
  vaccine: '疫苗',
  deworm: '驱虫',
  medication: '用药',
  visit: '就诊',
  symptom: '症状',
}

export function formatDate(value?: string | number | Date | null): string {
  if (!value) return '—'
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value
  }
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function today(): string {
  return formatDate(new Date())
}

export function daysUntil(dateString: string): number {
  const [year, month, day] = dateString.split('-').map(Number)
  const target = new Date(year, month - 1, day)
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - now.getTime()) / 86_400_000)
}

export function dueLabel(dateString: string): string {
  const days = daysUntil(dateString)
  if (days === 0) return '今天'
  if (days === 1) return '明天'
  if (days > 1) return `${days} 天后`
  if (days === -1) return '昨天'
  return `已逾期 ${Math.abs(days)} 天`
}

export function petAge(birthday?: string | null): string {
  if (!birthday) return '年龄未知'
  const [year, month, day] = birthday.split('-').map(Number)
  if (!year || !month || !day) return '年龄未知'
  const now = new Date()
  let months = (now.getFullYear() - year) * 12 + (now.getMonth() + 1 - month)
  if (now.getDate() < day) months -= 1
  if (months < 0) return '年龄未知'
  const years = Math.floor(months / 12)
  const rest = months % 12
  if (years === 0) return `${rest} 个月`
  return rest === 0 ? `${years} 岁` : `${years} 岁 ${rest} 个月`
}

export function speciesLabel(species: string): string {
  return SPECIES_LABELS[species] ?? species
}

export function genderLabel(gender: string): string {
  return GENDER_LABELS[gender] ?? gender
}

export function recordTypeLabel(recordType: string): string {
  return RECORD_TYPE_LABELS[recordType] ?? recordType
}
