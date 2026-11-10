import { apiFetch, apiFetchRaw } from '@hubra/plugin-sdk'

export interface Options {
  can: {
    tasks: boolean
    tasksRead: boolean
    contracts: boolean
    contractsRead: boolean
    meetings: boolean
  }
  memberId: number
  functions?: { id: number; name: string }[]
  polls?: { id: number; question: string; status: string }[]
}

/** Someone, or the holders of a function. */
interface Who {
  ownerId: number | null
  ownerName: string | null
  functionId: number | null
  functionName: string | null
}

export interface Task extends Who {
  id: number
  title: string
  notes: string | null
  dueOn: string | null
  done: boolean
  doneAt: string | null
  doneByName: string | null
  fromPlanner: boolean
  mine: boolean
}

export interface Duty extends Who {
  id: number
  title: string
  notes: string | null
  month: number
  day: number
  next: string
  remindDays: number
}

export type ContractKind = 'insurance' | 'rent' | 'licence' | 'service' | 'membership' | 'other'
export type CostPeriod = 'year' | 'quarter' | 'month' | 'once'

export interface Contract extends Who {
  id: number
  title: string
  kind: ContractKind
  party: string | null
  reference: string | null
  cost: number | null
  costPeriod: CostPeriod
  startsOn: string | null
  endsOn: string | null
  currentEnd: string | null
  noticeMonths: number
  renewsMonths: number
  noticeBy: string | null
  daysLeft: number | null
  remindDays: number
  notes: string | null
  ended: boolean
  expired: boolean
}

export interface AgendaItem {
  id: number
  position: number
  title: string
  description: string | null
  pollId: number | null
  pollQuestion: string | null
  pollStatus: string | null
  minutes: string | null
  decision: string | null
}

export interface Meeting {
  id: number
  title: string
  startsAt: string
  place: string | null
  inviteDays: number
  inviteBy: string
  quorum: number
  present: number
  quorate: boolean | null
  invitedAt: string | null
  closedAt: string | null
  chair: string | null
  minuteTaker: string | null
  intro?: string | null
  agenda?: AgendaItem[]
  iAmPresent?: boolean
  canManage?: boolean
  sent?: number
  late?: boolean
}

export interface Attendance {
  present: number
  quorum: number
  members: { memberId: number; name: string; present: boolean; signedInAt: string | null }[]
}

const BASE = '/app/board'
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const QK = {
  all: ['board'] as const,
  options: ['board', 'options'] as const,
  tasks: (show: string) => ['board', 'tasks', show] as const,
  duties: ['board', 'duties'] as const,
  contracts: ['board', 'contracts'] as const,
  meetings: ['board', 'meetings'] as const,
  members: ['board', 'members'] as const,
  meeting: (id: number) => ['board', 'meeting', id] as const,
  attendance: (id: number) => ['board', 'attendance', id] as const,
}

export const getOptions = () => apiFetch<Options>(`${BASE}/options`)

/** A function that gives the Board role, with who holds it now. */
export interface BoardFunction {
  id: number
  name: string
  key: string | null
  description: string | null
  maxHolders: number
  holders: { memberId: number; name: string | null; termStart: string | null; termEnd: string | null; upcoming: boolean }[]
  vacant: boolean
  openTasks: number
}
export const listBoardMembers = () =>
  apiFetch<{ functions: BoardFunction[]; canManage: boolean }>(`${BASE}/members`)

export const listTasks = (show: 'open' | 'done' | 'mine') => apiFetch<Task[]>(`${BASE}/tasks?show=${show}`)
export const saveTask = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Task>(id ? `${BASE}/tasks/${id}` : `${BASE}/tasks`, json(id ? 'PATCH' : 'POST', body))
export const finishTask = (id: number, done: boolean) => apiFetch<Task>(`${BASE}/tasks/${id}/done`, json('POST', { done }))
export const deleteTask = (id: number) => apiFetch<void>(`${BASE}/tasks/${id}`, { method: 'DELETE' })

export const listDuties = () => apiFetch<Duty[]>(`${BASE}/duties`)
export const saveDuty = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Duty>(id ? `${BASE}/duties/${id}` : `${BASE}/duties`, json(id ? 'PATCH' : 'POST', body))
export const deleteDuty = (id: number) => apiFetch<void>(`${BASE}/duties/${id}`, { method: 'DELETE' })

export const listContracts = () => apiFetch<Contract[]>(`${BASE}/contracts`)
export const saveContract = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Contract>(id ? `${BASE}/contracts/${id}` : `${BASE}/contracts`, json(id ? 'PATCH' : 'POST', body))
export const deleteContract = (id: number) => apiFetch<void>(`${BASE}/contracts/${id}`, { method: 'DELETE' })

export const listMeetings = () => apiFetch<Meeting[]>(`${BASE}/meetings`)
export const getMeeting = (id: number) => apiFetch<Meeting>(`${BASE}/meetings/${id}`)
export const saveMeeting = (body: Record<string, unknown>, id?: number) =>
  apiFetch<Meeting>(id ? `${BASE}/meetings/${id}` : `${BASE}/meetings`, json(id ? 'PATCH' : 'POST', body))
export const deleteMeeting = (id: number) => apiFetch<void>(`${BASE}/meetings/${id}`, { method: 'DELETE' })
export const addItem = (meetingId: number, body: Record<string, unknown>) =>
  apiFetch<Meeting>(`${BASE}/meetings/${meetingId}/agenda`, json('POST', body))
export const orderItems = (meetingId: number, ids: number[]) =>
  apiFetch<Meeting>(`${BASE}/meetings/${meetingId}/agenda/order`, json('PUT', { ids }))
export const saveItem = (id: number, body: Record<string, unknown>) =>
  apiFetch<Meeting>(`${BASE}/agenda/${id}`, json('PATCH', body))
export const deleteItem = (id: number) => apiFetch<void>(`${BASE}/agenda/${id}`, { method: 'DELETE' })
export const invite = (id: number) => apiFetch<Meeting>(`${BASE}/meetings/${id}/invite`, { method: 'POST' })
export const getAttendance = (id: number) => apiFetch<Attendance>(`${BASE}/meetings/${id}/attendance`)
export const setPresent = (id: number, memberId: number, present: boolean) =>
  apiFetch<{ present: number; quorate: boolean | null }>(`${BASE}/meetings/${id}/attendance/${memberId}`, {
    method: present ? 'PUT' : 'DELETE',
  })
export const closeMeeting = (id: number, reopen = false) =>
  apiFetch<Meeting>(`${BASE}/meetings/${id}/close`, json('POST', { reopen }))

/** Opens one of a meeting's PDFs in a new tab. */
export async function openPdf(id: number, kind: 'invitation' | 'minutes') {
  // Open the tab first: a browser blocks window.open after an await.
  const tab = window.open('', '_blank')
  const res = await apiFetchRaw(`${BASE}/meetings/${id}/${kind}.pdf?inline=1`)
  const url = URL.createObjectURL(await res.blob())
  if (tab) tab.location.href = url
  else window.location.assign(url)
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export function errorText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}

/** "2026-03-31" as 31.03.2026. */
export function formatDay(iso: string | null | undefined) {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}.${m}.${y}`
}

export function daysUntil(iso: string | null | undefined) {
  if (!iso) return null
  const day = new Date(iso.slice(0, 10) + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((day.getTime() - today.getTime()) / 86_400_000)
}
