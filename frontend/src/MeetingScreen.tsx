import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import {
  IconArrowDown,
  IconArrowLeft,
  IconArrowUp,
  IconCheck,
  IconFileTypePdf,
  IconLock,
  IconLockOpen,
  IconPencil,
  IconPlus,
  IconSearch,
  IconSend,
  IconTrash,
} from '@tabler/icons-react'
import {
  ConfirmModal,
  ErrorBanner,
  Field,
  LoadingSpinner,
  Modal,
  PageHead,
  Seg,
  useT,
  useToast,
} from '@hubra/plugin-sdk'
import {
  QK,
  addItem,
  closeMeeting,
  deleteItem,
  deleteMeeting,
  errorText,
  formatDay,
  getAttendance,
  getMeeting,
  getOptions,
  invite,
  openPdf,
  orderItems,
  saveItem,
  saveMeeting,
  setPresent,
  type AgendaItem,
  type Meeting,
  type Options,
} from './api'
import { MeetingStatus, formatWhen, toLocalInput } from './BoardScreen'

/** One general meeting: agenda, invitation, sign-in and minutes. */
export function MeetingScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const id = Number(useParams().id)
  const meeting = useQuery({ queryKey: QK.meeting(id), queryFn: () => getMeeting(id) })
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  const m = meeting.data
  const manage = !!m?.canManage
  const [mode, setMode] = useState<'prepare' | 'run'>('prepare')
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState<'invite' | 'delete' | null>(null)
  useEffect(() => {
    if (m?.invitedAt && !m.closedAt && new Date(m.startsAt).getTime() - Date.now() < 12 * 3600_000) setMode('run')
    // Only when the meeting first loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m?.id])

  const put = (next: Meeting) => {
    qc.setQueryData(QK.meeting(id), { ...next, canManage: manage })
    qc.invalidateQueries({ queryKey: QK.meetings })
  }
  const run = async (fn: () => Promise<Meeting | void>, ok?: string) => {
    try {
      const next = await fn()
      if (next) put(next)
      else qc.invalidateQueries({ queryKey: QK.meeting(id) })
      if (ok) notify('success', ok)
    } catch (err) {
      notify('error', errorText(err))
    }
  }
  const pdf = (kind: 'invitation' | 'minutes') => openPdf(id, kind).catch((err) => notify('error', errorText(err)))

  if (meeting.isLoading) return <LoadingSpinner />
  if (meeting.error || !m)
    return <ErrorBanner message={errorText(meeting.error ?? 'not found')} onRetry={() => meeting.refetch()} />

  const agenda = m.agenda ?? []
  const closed = !!m.closedAt
  const running = manage && mode === 'run'

  return (
    <>
      <PageHead
        back={
          <Anchor component="button" size="sm" onClick={() => navigate('/app/board/meetings')}>
            <Group gap={4}>
              <IconArrowLeft size={14} /> {t('board.tabs.meetings')}
            </Group>
          </Anchor>
        }
        title={m.title}
        desc={`${formatWhen(m.startsAt)}${m.place ? ` · ${m.place}` : ''}`}
        actions={
          <Group gap="xs">
            <Button variant="default" leftSection={<IconFileTypePdf size={16} />} onClick={() => pdf('invitation')}>
              {t('board.meetings.invitationPdf')}
            </Button>
            {(manage || closed) && (
              <Button variant="default" leftSection={<IconFileTypePdf size={16} />} onClick={() => pdf('minutes')}>
                {t('board.meetings.minutesPdf')}
              </Button>
            )}
            {manage && !m.invitedAt && (
              <Button leftSection={<IconSend size={16} />} onClick={() => setConfirm('invite')} disabled={!agenda.length}>
                {t('board.meetings.sendInvitation')}
              </Button>
            )}
          </Group>
        }
      />
      <Stack gap="md">
        <Group justify="space-between" wrap="wrap">
          <Group gap="xs">
            <MeetingStatus meeting={m} />
            {m.quorum > 0 && (m.invitedAt || closed) && (
              <Badge variant="light" color={m.quorate ? 'green' : 'orange'} style={{ textTransform: 'none' }}>
                {t('board.meetings.presentOf', { present: m.present, quorum: m.quorum })}
              </Badge>
            )}
            {!m.quorum && m.present > 0 && (
              <Badge variant="light" color="gray" style={{ textTransform: 'none' }}>
                {t('board.meetings.presentCount', { count: m.present })}
              </Badge>
            )}
          </Group>
          {manage && (
            <Group gap="xs">
              <Seg
                options={[
                  { value: 'prepare', label: t('board.meetings.prepare') },
                  { value: 'run', label: t('board.meetings.run') },
                ]}
                value={mode}
                onChange={(v) => setMode(v as typeof mode)}
              />
              <ActionIcon variant="default" size="lg" onClick={() => setEditing(true)} aria-label={t('board.edit')}>
                <IconPencil size={16} />
              </ActionIcon>
              <ActionIcon variant="default" size="lg" color="red" onClick={() => setConfirm('delete')} aria-label={t('board.delete')}>
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          )}
        </Group>

        {manage && !m.invitedAt && (
          <Alert color={new Date(m.inviteBy) < new Date() ? 'red' : 'violet'} variant="light">
            {t('board.meetings.inviteHint', { day: formatDay(m.inviteBy), days: m.inviteDays })}
          </Alert>
        )}

        {m.intro && (
          <Paper withBorder p="md" radius="md">
            <Text style={{ whiteSpace: 'pre-wrap' }}>{m.intro}</Text>
          </Paper>
        )}

        {running ? (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md" style={{ alignItems: 'start' }}>
            <Stack gap="sm">
              <Title order={4}>{t('board.meetings.agenda')}</Title>
              {agenda.map((item) => (
                <MinutesItem key={item.id} item={item} disabled={closed} onSaved={put} />
              ))}
              <Group>
                {closed ? (
                  <Button variant="default" leftSection={<IconLockOpen size={16} />} onClick={() => run(() => closeMeeting(id, true))}>
                    {t('board.meetings.reopen')}
                  </Button>
                ) : (
                  <Button leftSection={<IconLock size={16} />} onClick={() => run(() => closeMeeting(id), t('board.meetings.closedToast'))}>
                    {t('board.meetings.close')}
                  </Button>
                )}
              </Group>
            </Stack>
            <AttendancePanel meeting={m} disabled={closed} />
          </SimpleGrid>
        ) : (
          <AgendaList
            meeting={m}
            manage={manage && !closed}
            options={options.data}
            onChange={(fn) => run(fn)}
          />
        )}
      </Stack>

      {editing && <MeetingModal meeting={m} onClose={() => setEditing(false)} onSaved={put} />}
      <ConfirmModal
        open={confirm === 'invite'}
        title={t('board.meetings.sendInvitation')}
        body={t('board.meetings.inviteConfirm')}
        confirmLabel={t('board.meetings.send')}
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          setConfirm(null)
          try {
            const next = await invite(id)
            put(next)
            notify('success', t('board.meetings.sent', { count: next.sent ?? 0 }))
          } catch (err) {
            notify('error', errorText(err))
          }
        }}
      />
      <ConfirmModal
        open={confirm === 'delete'}
        title={t('board.meetings.deleteTitle')}
        body={m.title}
        confirmLabel={t('board.delete')}
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          setConfirm(null)
          try {
            await deleteMeeting(id)
            qc.invalidateQueries({ queryKey: QK.all })
            navigate('/app/board/meetings')
          } catch (err) {
            notify('error', errorText(err))
          }
        }}
      />
    </>
  )
}

// ── Agenda (prepare) ─────────────────────────────────────────────────────────

function AgendaList({
  meeting,
  manage,
  options,
  onChange,
}: {
  meeting: Meeting
  manage: boolean
  options: Options | undefined
  onChange: (fn: () => Promise<Meeting | void>) => void
}) {
  const { t } = useT()
  const agenda = meeting.agenda ?? []
  const [form, setForm] = useState<AgendaItem | 'new' | null>(null)
  const [deleting, setDeleting] = useState<AgendaItem | null>(null)
  const move = (index: number, by: number) => {
    const ids = agenda.map((i) => i.id)
    const [it] = ids.splice(index, 1)
    ids.splice(index + by, 0, it)
    onChange(() => orderItems(meeting.id, ids))
  }

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Title order={4}>{t('board.meetings.agenda')}</Title>
        {manage && (
          <Button variant="light" leftSection={<IconPlus size={16} />} onClick={() => setForm('new')}>
            {t('board.meetings.addItem')}
          </Button>
        )}
      </Group>
      {!agenda.length && (
        <Text c="dimmed" size="sm">
          {t('board.meetings.noAgenda')}
        </Text>
      )}
      {agenda.map((item, index) => (
        <Paper key={item.id} withBorder p="sm" radius="md">
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Group gap="sm" wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
              <Text fw={700} c="dimmed" w={22} ta="right">
                {item.position}.
              </Text>
              <div style={{ minWidth: 0 }}>
                <Text fw={600}>{item.title}</Text>
                {item.description && (
                  <Text size="sm" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
                    {item.description}
                  </Text>
                )}
                {item.pollQuestion && (
                  <Badge mt={4} variant="light" color="violet" style={{ textTransform: 'none' }}>
                    {t('board.meetings.vote')}: {item.pollQuestion}
                  </Badge>
                )}
                {item.decision && (
                  <Text size="sm" mt={4}>
                    <strong>{t('board.meetings.decision')}:</strong> {item.decision}
                  </Text>
                )}
              </div>
            </Group>
            {manage && (
              <Group gap={2} wrap="nowrap">
                <ActionIcon variant="subtle" color="gray" disabled={index === 0} onClick={() => move(index, -1)} aria-label={t('board.up')}>
                  <IconArrowUp size={16} />
                </ActionIcon>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  disabled={index === agenda.length - 1}
                  onClick={() => move(index, 1)}
                  aria-label={t('board.down')}
                >
                  <IconArrowDown size={16} />
                </ActionIcon>
                <ActionIcon variant="subtle" color="gray" onClick={() => setForm(item)} aria-label={t('board.edit')}>
                  <IconPencil size={16} />
                </ActionIcon>
                <ActionIcon variant="subtle" color="red" onClick={() => setDeleting(item)} aria-label={t('board.delete')}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            )}
          </Group>
        </Paper>
      ))}
      {form && (
        <ItemModal
          item={form === 'new' ? null : form}
          polls={options?.polls ?? []}
          onClose={() => setForm(null)}
          onSave={(body) => onChange(() => (form === 'new' ? addItem(meeting.id, body) : saveItem(form.id, body)))}
        />
      )}
      <ConfirmModal
        open={!!deleting}
        title={t('board.meetings.deleteItem')}
        body={deleting?.title ?? ''}
        confirmLabel={t('board.delete')}
        onClose={() => setDeleting(null)}
        onConfirm={() => {
          if (deleting) onChange(() => deleteItem(deleting.id))
          setDeleting(null)
        }}
      />
    </Stack>
  )
}

function ItemModal({
  item,
  polls,
  onClose,
  onSave,
}: {
  item: AgendaItem | null
  polls: { id: number; question: string }[]
  onClose: () => void
  onSave: (body: Record<string, unknown>) => void
}) {
  const { t } = useT()
  const [title, setTitle] = useState(item?.title ?? '')
  const [description, setDescription] = useState(item?.description ?? '')
  const [pollId, setPollId] = useState<string | null>(item?.pollId ? String(item.pollId) : null)
  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    onSave({ title, description, pollId: pollId ? Number(pollId) : null })
    onClose()
  }
  return (
    <Modal
      open
      onClose={onClose}
      onSubmit={submit}
      title={item ? t('board.meetings.editItem') : t('board.meetings.addItem')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('board.cancel')}
          </Button>
          <Button type="submit" disabled={!title.trim()}>
            {t('board.save')}
          </Button>
        </>
      }
    >
      <Field label={t('board.titleField')}>
        <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} data-autofocus />
      </Field>
      <Field label={t('board.meetings.itemDescription')} hint={t('board.meetings.itemDescriptionHint')}>
        <Textarea autosize minRows={3} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
      </Field>
      <Field label={t('board.meetings.vote')} hint={t('board.meetings.voteHint')}>
        <Select
          clearable
          searchable
          data={polls.map((p) => ({ value: String(p.id), label: p.question }))}
          value={pollId}
          onChange={setPollId}
          placeholder={t('board.meetings.noVote')}
        />
      </Field>
    </Modal>
  )
}

// ── Running the meeting ──────────────────────────────────────────────────────

function MinutesItem({ item, disabled, onSaved }: { item: AgendaItem; disabled: boolean; onSaved: (m: Meeting) => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const [minutes, setMinutes] = useState(item.minutes ?? '')
  const [decision, setDecision] = useState(item.decision ?? '')
  const [saved, setSaved] = useState(false)
  const dirty = minutes !== (item.minutes ?? '') || decision !== (item.decision ?? '')
  const save = async () => {
    if (!dirty) return
    try {
      onSaved(await saveItem(item.id, { minutes, decision }))
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
    } catch (err) {
      notify('error', errorText(err))
    }
  }
  return (
    <Paper withBorder p="sm" radius="md">
      <Group justify="space-between" mb={6}>
        <Text fw={600}>
          {item.position}. {item.title}
        </Text>
        {saved && <IconCheck size={16} color="var(--mantine-color-green-6)" />}
      </Group>
      {item.pollQuestion && (
        <Badge mb={6} variant="light" color="violet" style={{ textTransform: 'none' }}>
          {t('board.meetings.vote')}: {item.pollQuestion}
          {item.pollStatus ? ` (${item.pollStatus})` : ''}
        </Badge>
      )}
      <Stack gap={6}>
        <Textarea
          aria-label={t('board.meetings.minutes')}
          placeholder={t('board.meetings.minutesPlaceholder')}
          autosize
          minRows={2}
          value={minutes}
          disabled={disabled}
          onChange={(e) => setMinutes(e.currentTarget.value)}
          onBlur={save}
        />
        <TextInput
          aria-label={t('board.meetings.decision')}
          placeholder={t('board.meetings.decisionPlaceholder')}
          value={decision}
          disabled={disabled}
          onChange={(e) => setDecision(e.currentTarget.value)}
          onBlur={save}
        />
      </Stack>
    </Paper>
  )
}

function AttendancePanel({ meeting, disabled }: { meeting: Meeting; disabled: boolean }) {
  const { t } = useT()
  const { notify } = useToast()
  const qc = useQueryClient()
  const list = useQuery({ queryKey: QK.attendance(meeting.id), queryFn: () => getAttendance(meeting.id) })
  const [q, setQ] = useState('')
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (list.data?.members ?? []).filter((r) => !needle || r.name.toLowerCase().includes(needle))
  }, [list.data, q])
  const present = list.data?.present ?? meeting.present

  const toggle = async (memberId: number, on: boolean) => {
    try {
      const res = await setPresent(meeting.id, memberId, on)
      qc.setQueryData(QK.attendance(meeting.id), (old: typeof list.data) =>
        old
          ? {
              ...old,
              present: res.present,
              members: old.members.map((r) => (r.memberId === memberId ? { ...r, present: on } : r)),
            }
          : old,
      )
      qc.setQueryData(QK.meeting(meeting.id), (old: Meeting | undefined) =>
        old ? { ...old, present: res.present, quorate: res.quorate } : old,
      )
    } catch (err) {
      notify('error', errorText(err))
    }
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" mb="sm">
        <Title order={4}>{t('board.meetings.signIn')}</Title>
        <Badge size="lg" variant="light" color={meeting.quorum ? (present >= meeting.quorum ? 'green' : 'orange') : 'gray'} style={{ textTransform: 'none' }}>
          {meeting.quorum ? t('board.meetings.presentOf', { present, quorum: meeting.quorum }) : t('board.meetings.presentCount', { count: present })}
        </Badge>
      </Group>
      <TextInput
        leftSection={<IconSearch size={16} />}
        placeholder={t('board.meetings.searchMember')}
        value={q}
        onChange={(e) => setQ(e.currentTarget.value)}
        mb="sm"
        aria-label={t('board.meetings.searchMember')}
      />
      {list.isLoading ? (
        <LoadingSpinner />
      ) : (
        <Stack gap={4} mah={520} style={{ overflowY: 'auto' }}>
          {rows.map((r) => (
            <Checkbox
              key={r.memberId}
              label={r.name}
              checked={r.present}
              disabled={disabled}
              onChange={(e) => toggle(r.memberId, e.currentTarget.checked)}
              py={4}
            />
          ))}
        </Stack>
      )}
    </Paper>
  )
}

// ── Details ──────────────────────────────────────────────────────────────────

function MeetingModal({ meeting, onClose, onSaved }: { meeting: Meeting; onClose: () => void; onSaved: (m: Meeting) => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const [v, setV] = useState({
    title: meeting.title,
    startsAt: toLocalInput(meeting.startsAt),
    place: meeting.place ?? '',
    inviteDays: meeting.inviteDays as number | string,
    quorum: meeting.quorum as number | string,
    chair: meeting.chair ?? '',
    minuteTaker: meeting.minuteTaker ?? '',
    intro: meeting.intro ?? '',
  })
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof typeof v>(key: K, value: (typeof v)[K]) => setV((old) => ({ ...old, [key]: value }))
  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    setBusy(true)
    try {
      onSaved(
        await saveMeeting(
          { ...v, startsAt: new Date(v.startsAt).toISOString(), inviteDays: Number(v.inviteDays), quorum: Number(v.quorum) },
          meeting.id,
        ),
      )
      onClose()
    } catch (err) {
      notify('error', errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      open
      wide
      onClose={onClose}
      onSubmit={submit}
      title={t('board.meetings.details')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('board.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!v.title.trim()}>
            {t('board.save')}
          </Button>
        </>
      }
    >
      <Field label={t('board.titleField')}>
        <TextInput value={v.title} onChange={(e) => set('title', e.currentTarget.value)} />
      </Field>
      <Group grow align="flex-start">
        <Field label={t('board.meetings.startsAt')}>
          <TextInput type="datetime-local" value={v.startsAt} onChange={(e) => set('startsAt', e.currentTarget.value)} />
        </Field>
        <Field label={t('board.meetings.place')}>
          <TextInput value={v.place} onChange={(e) => set('place', e.currentTarget.value)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('board.meetings.inviteDays')} hint={t('board.meetings.inviteDaysHint')}>
          <NumberInput min={0} max={120} value={v.inviteDays} onChange={(x) => set('inviteDays', x)} />
        </Field>
        <Field label={t('board.meetings.quorum')} hint={t('board.meetings.quorumHint')}>
          <NumberInput min={0} value={v.quorum} onChange={(x) => set('quorum', x)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('board.meetings.chair')}>
          <TextInput value={v.chair} onChange={(e) => set('chair', e.currentTarget.value)} />
        </Field>
        <Field label={t('board.meetings.minuteTaker')}>
          <TextInput value={v.minuteTaker} onChange={(e) => set('minuteTaker', e.currentTarget.value)} />
        </Field>
      </Group>
      <Field label={t('board.meetings.intro')} hint={t('board.meetings.introHint')}>
        <Textarea autosize minRows={3} value={v.intro} onChange={(e) => set('intro', e.currentTarget.value)} />
      </Field>
    </Modal>
  )
}
