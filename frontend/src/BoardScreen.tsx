import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
} from '@mantine/core'
import { IconCalendarRepeat, IconFileCertificate, IconId, IconListCheck, IconPencil, IconPlus, IconTrash, IconUsers } from '@tabler/icons-react'
import {
  ConfirmModal,
  EmptyState,
  ErrorBanner,
  Field,
  LoadingSpinner,
  Modal,
  PageHead,
  Seg,
  Tabs,
  formatCHF,
  useT,
  useToast,
} from '@hubra/plugin-sdk'
import {
  QK,
  deleteContract,
  deleteDuty,
  deleteTask,
  errorText,
  finishTask,
  formatDay,
  getOptions,
  listContracts,
  listDuties,
  listBoardMembers,
  listMeetings,
  listTasks,
  saveContract,
  saveDuty,
  saveMeeting,
  saveTask,
  type Contract,
  type ContractKind,
  type CostPeriod,
  type Duty,
  type Options,
  type Task,
} from './api'
import { DueBadge, WhoField, WhoLabel, type WhoValue } from './common'

type TabId = 'tasks' | 'members' | 'planner' | 'contracts' | 'meetings'

/** Vorstand: tasks, year planner, contracts and the general meetings. */
export function BoardScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  const can = options.data?.can
  const part = location.pathname.split('/app/board')[1]?.replace(/^\//, '') ?? ''
  const tabs = [
    { id: 'tasks', label: t('board.tabs.tasks'), icon: <IconListCheck size={16} />, show: can?.tasksRead },
    { id: 'members', label: t('board.tabs.members'), icon: <IconId size={16} />, show: true },
    { id: 'planner', label: t('board.tabs.planner'), icon: <IconCalendarRepeat size={16} />, show: can?.tasksRead },
    { id: 'contracts', label: t('board.tabs.contracts'), icon: <IconFileCertificate size={16} />, show: can?.contractsRead },
    { id: 'meetings', label: t('board.tabs.meetings'), icon: <IconUsers size={16} />, show: true },
  ].filter((tb) => tb.show)
  const active = (tabs.find((tb) => tb.id === part)?.id ?? tabs[0]?.id ?? 'tasks') as TabId

  if (options.isLoading) return <LoadingSpinner />
  if (options.error) return <ErrorBanner message={errorText(options.error)} onRetry={() => options.refetch()} />

  return (
    <>
      <PageHead title={t('board.title')} desc={t('board.desc')} />
      <Tabs
        tabs={tabs}
        activeTab={active}
        onTabChange={(id) => navigate(id === 'tasks' ? '/app/board' : `/app/board/${id}`)}
      />
      {active === 'tasks' && <TasksTab options={options.data} />}
      {active === 'members' && <MembersTab />}
      {active === 'planner' && <PlannerTab options={options.data} />}
      {active === 'contracts' && <ContractsTab options={options.data} />}
      {active === 'meetings' && <MeetingsTab options={options.data} />}
    </>
  )
}

// ── Vorstand ─────────────────────────────────────────────────────────────────

/** The board: the functions that give the Board role and who holds them. */
function MembersTab() {
  const { t } = useT()
  const navigate = useNavigate()
  const data = useQuery({ queryKey: QK.members, queryFn: listBoardMembers })
  if (data.error) return <ErrorBanner message={errorText(data.error)} onRetry={() => data.refetch()} />
  if (data.isLoading || !data.data) return <LoadingSpinner />
  const { functions, canManage } = data.data
  const manage = canManage ? (
    <Button variant="default" leftSection={<IconPencil size={16} />} onClick={() => navigate('/app/members/functions')}>
      {t('board.members.manage')}
    </Button>
  ) : null
  if (!functions.length)
    return (
      <EmptyState
        icon={<IconId size={28} />}
        title={t('board.members.empty')}
        description={t('board.members.emptyHint')}
        action={canManage ? { label: t('board.members.manage'), onClick: () => navigate('/app/members/functions') } : undefined}
      />
    )
  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Text fz="sm" c="dimmed">
          {t('board.members.hint')}
        </Text>
        {manage}
      </Group>
      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
        {functions.map((f) => (
          <Paper key={f.id} withBorder p="md" radius="md">
            <Group justify="space-between" align="flex-start" gap={8} wrap="nowrap">
              <Text fw={600}>{f.name}</Text>
              {f.vacant && (
                <Badge color="orange" variant="light">
                  {t('board.members.vacant')}
                </Badge>
              )}
            </Group>
            {f.description && (
              <Text fz="xs" c="dimmed" mt={2}>
                {f.description}
              </Text>
            )}
            <Stack gap={4} mt="sm">
              {f.holders.map((h) => (
                <Group key={h.memberId} gap={6} wrap="nowrap">
                  <Text fz="sm">{h.name ?? '—'}</Text>
                  {h.upcoming && h.termStart ? (
                    <Text fz="xs" c="dimmed">
                      {t('board.members.from', { date: formatDay(h.termStart) })}
                    </Text>
                  ) : h.termEnd ? (
                    <Text fz="xs" c="dimmed">
                      {t('board.members.until', { date: formatDay(h.termEnd) })}
                    </Text>
                  ) : null}
                </Group>
              ))}
            </Stack>
            {f.openTasks > 0 && (
              <Button
                variant="subtle"
                size="compact-xs"
                mt="sm"
                leftSection={<IconListCheck size={14} />}
                onClick={() => navigate('/app/board')}
              >
                {t('board.members.openTasks', { count: f.openTasks })}
              </Button>
            )}
          </Paper>
        ))}
      </div>
    </Stack>
  )
}

// ── Tasks ────────────────────────────────────────────────────────────────────

function TasksTab({ options }: { options: Options | undefined }) {
  const { t } = useT()
  const { notify } = useToast()
  const qc = useQueryClient()
  const [show, setShow] = useState<'open' | 'mine' | 'done'>('open')
  const tasks = useQuery({ queryKey: QK.tasks(show), queryFn: () => listTasks(show) })
  const [form, setForm] = useState<Task | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Task | null>(null)
  const canEdit = !!options?.can.tasks
  const refresh = () => qc.invalidateQueries({ queryKey: QK.all })

  const toggle = async (task: Task) => {
    try {
      await finishTask(task.id, !task.done)
      refresh()
    } catch (err) {
      notify('error', errorText(err))
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Seg
          options={[
            { value: 'open', label: t('board.tasks.open') },
            { value: 'mine', label: t('board.tasks.mine') },
            { value: 'done', label: t('board.tasks.done') },
          ]}
          value={show}
          onChange={(v) => setShow(v as typeof show)}
        />
        {canEdit && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setForm('new')}>
            {t('board.tasks.new')}
          </Button>
        )}
      </Group>
      {tasks.error ? (
        <ErrorBanner message={errorText(tasks.error)} onRetry={() => tasks.refetch()} />
      ) : tasks.isLoading ? (
        <LoadingSpinner />
      ) : !tasks.data?.length ? (
        <EmptyState
          icon={<IconListCheck size={28} />}
          title={show === 'done' ? t('board.tasks.noneDone') : t('board.tasks.none')}
          description={canEdit && show !== 'done' ? t('board.tasks.noneHint') : undefined}
        />
      ) : (
        <Stack gap="xs">
          {tasks.data.map((task) => (
            <Paper key={task.id} withBorder p="sm" radius="md">
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Group gap="sm" wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
                  <Checkbox
                    mt={2}
                    checked={task.done}
                    disabled={!canEdit && !task.mine}
                    onChange={() => toggle(task)}
                    aria-label={t('board.tasks.markDone')}
                  />
                  <div style={{ minWidth: 0 }}>
                    <Text fw={600} td={task.done ? 'line-through' : undefined}>
                      {task.title}
                    </Text>
                    {task.notes && (
                      <Text size="sm" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
                        {task.notes}
                      </Text>
                    )}
                    <Group gap="xs" mt={6}>
                      <WhoLabel ownerName={task.ownerName} functionName={task.functionName} />
                      <DueBadge day={task.dueOn} done={task.done} />
                      {task.fromPlanner && (
                        <Badge variant="outline" color="gray" style={{ textTransform: 'none' }}>
                          {t('board.tabs.planner')}
                        </Badge>
                      )}
                      {task.done && task.doneByName && (
                        <Text size="xs" c="dimmed">
                          {t('board.tasks.doneBy', { name: task.doneByName, day: formatDay(task.doneAt) })}
                        </Text>
                      )}
                    </Group>
                  </div>
                </Group>
                {canEdit && (
                  <Group gap={4} wrap="nowrap">
                    <ActionIcon variant="subtle" color="gray" onClick={() => setForm(task)} aria-label={t('board.edit')}>
                      <IconPencil size={16} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" color="red" onClick={() => setDeleting(task)} aria-label={t('board.delete')}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                )}
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
      {form && <TaskModal task={form === 'new' ? null : form} options={options} onClose={() => setForm(null)} onDone={refresh} />}
      <ConfirmModal
        open={!!deleting}
        title={t('board.tasks.deleteTitle')}
        body={deleting?.title ?? ''}
        confirmLabel={t('board.delete')}
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          if (!deleting) return
          try {
            await deleteTask(deleting.id)
            refresh()
          } catch (err) {
            notify('error', errorText(err))
          }
          setDeleting(null)
        }}
      />
    </Stack>
  )
}

function TaskModal({
  task,
  options,
  onClose,
  onDone,
}: {
  task: Task | null
  options: Options | undefined
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [title, setTitle] = useState(task?.title ?? '')
  const [notes, setNotes] = useState(task?.notes ?? '')
  const [dueOn, setDueOn] = useState(task?.dueOn ?? '')
  const [who, setWho] = useState<WhoValue>({ ownerId: task?.ownerId ?? null, functionId: task?.functionId ?? null })
  const [busy, setBusy] = useState(false)

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    setBusy(true)
    try {
      await saveTask({ title, notes, dueOn: dueOn || null, ...who }, task?.id)
      notify('success', t('board.saved'))
      onDone()
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
      onClose={onClose}
      onSubmit={submit}
      title={task ? t('board.tasks.edit') : t('board.tasks.new')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('board.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!title.trim()}>
            {t('board.save')}
          </Button>
        </>
      }
    >
      <Field label={t('board.titleField')}>
        <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} required data-autofocus />
      </Field>
      <WhoField value={who} onChange={setWho} options={options} />
      <Field label={t('board.dueOn')}>
        <TextInput type="date" value={dueOn} onChange={(e) => setDueOn(e.currentTarget.value)} />
      </Field>
      <Field label={t('board.notes')}>
        <Textarea autosize minRows={2} value={notes} onChange={(e) => setNotes(e.currentTarget.value)} />
      </Field>
    </Modal>
  )
}

// ── Year planner ─────────────────────────────────────────────────────────────

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

function PlannerTab({ options }: { options: Options | undefined }) {
  const { t, i18n } = useT()
  const { notify } = useToast()
  const qc = useQueryClient()
  const duties = useQuery({ queryKey: QK.duties, queryFn: listDuties })
  const [form, setForm] = useState<Duty | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Duty | null>(null)
  const canEdit = !!options?.can.tasks
  const refresh = () => qc.invalidateQueries({ queryKey: QK.all })
  const monthName = (m: number) =>
    new Date(2000, m - 1, 1).toLocaleDateString(i18n.language || 'de-CH', { month: 'long' })

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Text size="sm" c="dimmed" maw={640}>
          {t('board.planner.hint')}
        </Text>
        {canEdit && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setForm('new')}>
            {t('board.planner.new')}
          </Button>
        )}
      </Group>
      {duties.error ? (
        <ErrorBanner message={errorText(duties.error)} onRetry={() => duties.refetch()} />
      ) : duties.isLoading ? (
        <LoadingSpinner />
      ) : !duties.data?.length ? (
        <EmptyState icon={<IconCalendarRepeat size={28} />} title={t('board.planner.none')} description={t('board.planner.noneHint')} />
      ) : (
        <Table.ScrollContainer minWidth={560}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('board.planner.when')}</Table.Th>
                <Table.Th>{t('board.titleField')}</Table.Th>
                <Table.Th>{t('board.who')}</Table.Th>
                <Table.Th>{t('board.planner.next')}</Table.Th>
                {canEdit && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {duties.data.map((d) => (
                <Table.Tr key={d.id}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    {d.day}. {monthName(d.month)}
                  </Table.Td>
                  <Table.Td>
                    <Text fw={600} size="sm">
                      {d.title}
                    </Text>
                    {d.notes && (
                      <Text size="xs" c="dimmed">
                        {d.notes}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <WhoLabel ownerName={d.ownerName} functionName={d.functionName} />
                  </Table.Td>
                  <Table.Td>
                    <DueBadge day={d.next} />
                  </Table.Td>
                  {canEdit && (
                    <Table.Td>
                      <Group gap={4} wrap="nowrap" justify="flex-end">
                        <ActionIcon variant="subtle" color="gray" onClick={() => setForm(d)} aria-label={t('board.edit')}>
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon variant="subtle" color="red" onClick={() => setDeleting(d)} aria-label={t('board.delete')}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {form && (
        <DutyModal
          duty={form === 'new' ? null : form}
          options={options}
          months={MONTHS.map((m) => ({ value: String(m), label: monthName(m) }))}
          onClose={() => setForm(null)}
          onDone={refresh}
        />
      )}
      <ConfirmModal
        open={!!deleting}
        title={t('board.planner.deleteTitle')}
        body={deleting?.title ?? ''}
        confirmLabel={t('board.delete')}
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          if (!deleting) return
          try {
            await deleteDuty(deleting.id)
            refresh()
          } catch (err) {
            notify('error', errorText(err))
          }
          setDeleting(null)
        }}
      />
    </Stack>
  )
}

function DutyModal({
  duty,
  options,
  months,
  onClose,
  onDone,
}: {
  duty: Duty | null
  options: Options | undefined
  months: { value: string; label: string }[]
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [title, setTitle] = useState(duty?.title ?? '')
  const [notes, setNotes] = useState(duty?.notes ?? '')
  const [month, setMonth] = useState(String(duty?.month ?? 1))
  const [day, setDay] = useState<number | string>(duty?.day ?? 1)
  const [remindDays, setRemindDays] = useState<number | string>(duty?.remindDays ?? 14)
  const [who, setWho] = useState<WhoValue>({ ownerId: duty?.ownerId ?? null, functionId: duty?.functionId ?? null })
  const [busy, setBusy] = useState(false)

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    setBusy(true)
    try {
      await saveDuty({ title, notes, month: Number(month), day: Number(day), remindDays: Number(remindDays), ...who }, duty?.id)
      notify('success', t('board.saved'))
      onDone()
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
      onClose={onClose}
      onSubmit={submit}
      title={duty ? t('board.planner.edit') : t('board.planner.new')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('board.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!title.trim()}>
            {t('board.save')}
          </Button>
        </>
      }
    >
      <Field label={t('board.titleField')}>
        <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} placeholder={t('board.planner.example')} data-autofocus />
      </Field>
      <Group grow>
        <Field label={t('board.planner.day')}>
          <NumberInput min={1} max={31} value={day} onChange={setDay} />
        </Field>
        <Field label={t('board.planner.month')}>
          <Select data={months} value={month} onChange={(v) => v && setMonth(v)} allowDeselect={false} />
        </Field>
      </Group>
      <WhoField value={who} onChange={setWho} options={options} />
      <Field label={t('board.remindDays')} hint={t('board.planner.remindHint')}>
        <NumberInput min={0} max={180} value={remindDays} onChange={setRemindDays} />
      </Field>
      <Field label={t('board.notes')}>
        <Textarea autosize minRows={2} value={notes} onChange={(e) => setNotes(e.currentTarget.value)} />
      </Field>
    </Modal>
  )
}

// ── Contracts ────────────────────────────────────────────────────────────────

const KINDS: ContractKind[] = ['insurance', 'rent', 'licence', 'service', 'membership', 'other']
const PERIODS: CostPeriod[] = ['year', 'quarter', 'month', 'once']

function ContractsTab({ options }: { options: Options | undefined }) {
  const { t } = useT()
  const { notify } = useToast()
  const qc = useQueryClient()
  const contracts = useQuery({ queryKey: QK.contracts, queryFn: listContracts })
  const [form, setForm] = useState<Contract | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Contract | null>(null)
  const canEdit = !!options?.can.contracts
  const refresh = () => qc.invalidateQueries({ queryKey: QK.all })
  const yearly = (contracts.data ?? [])
    .filter((c) => !c.ended && !c.expired && c.cost != null)
    .reduce((sum, c) => sum + perYear(c.cost ?? 0, c.costPeriod), 0)

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Text size="sm" c="dimmed">
          {contracts.data?.length ? t('board.contracts.yearly', { amount: `CHF ${formatCHF(yearly)}` }) : t('board.contracts.hint')}
        </Text>
        {canEdit && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setForm('new')}>
            {t('board.contracts.new')}
          </Button>
        )}
      </Group>
      {contracts.error ? (
        <ErrorBanner message={errorText(contracts.error)} onRetry={() => contracts.refetch()} />
      ) : contracts.isLoading ? (
        <LoadingSpinner />
      ) : !contracts.data?.length ? (
        <EmptyState icon={<IconFileCertificate size={28} />} title={t('board.contracts.none')} description={t('board.contracts.noneHint')} />
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('board.contracts.contract')}</Table.Th>
                <Table.Th>{t('board.contracts.cost')}</Table.Th>
                <Table.Th>{t('board.contracts.runsTo')}</Table.Th>
                <Table.Th>{t('board.contracts.noticeBy')}</Table.Th>
                <Table.Th>{t('board.who')}</Table.Th>
                {canEdit && <Table.Th />}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {contracts.data.map((c) => (
                <Table.Tr key={c.id} style={c.ended || c.expired ? { opacity: 0.55 } : undefined}>
                  <Table.Td>
                    <Text fw={600} size="sm">
                      {c.title}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {[t(`board.kind.${c.kind}`), c.party, c.reference].filter(Boolean).join(' · ')}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    {c.cost != null ? `CHF ${formatCHF(c.cost)} / ${t(`board.period.${c.costPeriod}`)}` : '–'}
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    {c.ended || c.expired ? (
                      <Badge color="gray" variant="light" style={{ textTransform: 'none' }}>
                        {t(c.ended ? 'board.contracts.ended' : 'board.contracts.expired')}
                      </Badge>
                    ) : c.currentEnd ? (
                      <>
                        {formatDay(c.currentEnd)}
                        {c.renewsMonths > 0 && (
                          <Text size="xs" c="dimmed">
                            {t('board.contracts.renews', { count: c.renewsMonths })}
                          </Text>
                        )}
                      </>
                    ) : (
                      <Text size="sm" c="dimmed">
                        {t('board.contracts.openEnded')}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>{c.noticeBy ? <DueBadge day={c.noticeBy} /> : '–'}</Table.Td>
                  <Table.Td>
                    <WhoLabel ownerName={c.ownerName} functionName={c.functionName} />
                  </Table.Td>
                  {canEdit && (
                    <Table.Td>
                      <Group gap={4} wrap="nowrap" justify="flex-end">
                        <ActionIcon variant="subtle" color="gray" onClick={() => setForm(c)} aria-label={t('board.edit')}>
                          <IconPencil size={16} />
                        </ActionIcon>
                        <ActionIcon variant="subtle" color="red" onClick={() => setDeleting(c)} aria-label={t('board.delete')}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {form && <ContractModal contract={form === 'new' ? null : form} options={options} onClose={() => setForm(null)} onDone={refresh} />}
      <ConfirmModal
        open={!!deleting}
        title={t('board.contracts.deleteTitle')}
        body={deleting?.title ?? ''}
        confirmLabel={t('board.delete')}
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          if (!deleting) return
          try {
            await deleteContract(deleting.id)
            refresh()
          } catch (err) {
            notify('error', errorText(err))
          }
          setDeleting(null)
        }}
      />
    </Stack>
  )
}

function perYear(cost: number, period: CostPeriod) {
  return period === 'month' ? cost * 12 : period === 'quarter' ? cost * 4 : period === 'once' ? 0 : cost
}

function ContractModal({
  contract,
  options,
  onClose,
  onDone,
}: {
  contract: Contract | null
  options: Options | undefined
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [v, setV] = useState({
    title: contract?.title ?? '',
    kind: contract?.kind ?? 'insurance',
    party: contract?.party ?? '',
    reference: contract?.reference ?? '',
    cost: contract?.cost ?? ('' as number | string),
    costPeriod: contract?.costPeriod ?? 'year',
    startsOn: contract?.startsOn ?? '',
    endsOn: contract?.endsOn ?? '',
    noticeMonths: contract?.noticeMonths ?? (3 as number | string),
    renewsMonths: contract?.renewsMonths ?? (12 as number | string),
    remindDays: contract?.remindDays ?? (30 as number | string),
    notes: contract?.notes ?? '',
    ended: contract?.ended ?? false,
  })
  const [who, setWho] = useState<WhoValue>({ ownerId: contract?.ownerId ?? null, functionId: contract?.functionId ?? null })
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof typeof v>(key: K, value: (typeof v)[K]) => setV((old) => ({ ...old, [key]: value }))

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    setBusy(true)
    try {
      await saveContract(
        {
          ...v,
          cost: v.cost === '' ? null : v.cost,
          startsOn: v.startsOn || null,
          endsOn: v.endsOn || null,
          ...who,
        },
        contract?.id,
      )
      notify('success', t('board.saved'))
      onDone()
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
      title={contract ? t('board.contracts.edit') : t('board.contracts.new')}
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
      <Group grow align="flex-start">
        <Field label={t('board.titleField')}>
          <TextInput value={v.title} onChange={(e) => set('title', e.currentTarget.value)} placeholder={t('board.contracts.example')} data-autofocus />
        </Field>
        <Field label={t('board.contracts.kind')}>
          <Select
            data={KINDS.map((k) => ({ value: k, label: t(`board.kind.${k}`) }))}
            value={v.kind}
            onChange={(k) => k && set('kind', k as ContractKind)}
            allowDeselect={false}
          />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('board.contracts.party')}>
          <TextInput value={v.party} onChange={(e) => set('party', e.currentTarget.value)} />
        </Field>
        <Field label={t('board.contracts.reference')}>
          <TextInput value={v.reference} onChange={(e) => set('reference', e.currentTarget.value)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('board.contracts.cost')}>
          <NumberInput min={0} decimalScale={2} prefix="CHF " value={v.cost} onChange={(x) => set('cost', x)} />
        </Field>
        <Field label={t('board.contracts.per')}>
          <Select
            data={PERIODS.map((p) => ({ value: p, label: t(`board.period.${p}`) }))}
            value={v.costPeriod}
            onChange={(p) => p && set('costPeriod', p as CostPeriod)}
            allowDeselect={false}
          />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('board.contracts.startsOn')}>
          <TextInput type="date" value={v.startsOn} onChange={(e) => set('startsOn', e.currentTarget.value)} />
        </Field>
        <Field label={t('board.contracts.endsOn')} hint={t('board.contracts.endsOnHint')}>
          <TextInput type="date" value={v.endsOn} onChange={(e) => set('endsOn', e.currentTarget.value)} />
        </Field>
      </Group>
      <Group grow align="flex-start">
        <Field label={t('board.contracts.noticeMonths')}>
          <NumberInput min={0} max={60} value={v.noticeMonths} onChange={(x) => set('noticeMonths', x)} />
        </Field>
        <Field label={t('board.contracts.renewsMonths')} hint={t('board.contracts.renewsHint')}>
          <NumberInput min={0} max={120} value={v.renewsMonths} onChange={(x) => set('renewsMonths', x)} />
        </Field>
        <Field label={t('board.remindDays')}>
          <NumberInput min={0} max={365} value={v.remindDays} onChange={(x) => set('remindDays', x)} />
        </Field>
      </Group>
      <WhoField value={who} onChange={setWho} options={options} />
      <Field label={t('board.notes')}>
        <Textarea autosize minRows={2} value={v.notes} onChange={(e) => set('notes', e.currentTarget.value)} />
      </Field>
      {contract && (
        <Checkbox
          label={t('board.contracts.markEnded')}
          checked={v.ended}
          onChange={(e) => set('ended', e.currentTarget.checked)}
        />
      )}
    </Modal>
  )
}

// ── Meetings ─────────────────────────────────────────────────────────────────

function MeetingsTab({ options }: { options: Options | undefined }) {
  const { t } = useT()
  const navigate = useNavigate()
  const meetings = useQuery({ queryKey: QK.meetings, queryFn: listMeetings })
  const [creating, setCreating] = useState(false)
  const canEdit = !!options?.can.meetings

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        <Text size="sm" c="dimmed" maw={640}>
          {t('board.meetings.hint')}
        </Text>
        {canEdit && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setCreating(true)}>
            {t('board.meetings.new')}
          </Button>
        )}
      </Group>
      {meetings.error ? (
        <ErrorBanner message={errorText(meetings.error)} onRetry={() => meetings.refetch()} />
      ) : meetings.isLoading ? (
        <LoadingSpinner />
      ) : !meetings.data?.length ? (
        <EmptyState icon={<IconUsers size={28} />} title={t('board.meetings.none')} />
      ) : (
        <Stack gap="xs">
          {meetings.data.map((m) => (
            <Paper
              key={m.id}
              withBorder
              p="sm"
              radius="md"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/app/board/meetings/${m.id}`)}
            >
              <Group justify="space-between" wrap="wrap">
                <div>
                  <Text fw={600}>{m.title}</Text>
                  <Text size="sm" c="dimmed">
                    {formatWhen(m.startsAt)}
                    {m.place ? ` · ${m.place}` : ''}
                  </Text>
                </div>
                <MeetingStatus meeting={m} />
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
      {creating && <NewMeetingModal onClose={() => setCreating(false)} onDone={(id) => navigate(`/app/board/meetings/${id}`)} />}
    </Stack>
  )
}

export function formatWhen(iso: string) {
  const d = new Date(iso)
  return `${d.toLocaleDateString('de-CH', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })}, ${d.toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' })}`
}

export function MeetingStatus({ meeting }: { meeting: { invitedAt: string | null; closedAt: string | null; inviteBy: string } }) {
  const { t } = useT()
  if (meeting.closedAt)
    return (
      <Badge color="gray" variant="light">
        {t('board.meetings.closed')}
      </Badge>
    )
  if (meeting.invitedAt)
    return (
      <Badge color="green" variant="light">
        {t('board.meetings.invited')}
      </Badge>
    )
  return <DueBadge day={meeting.inviteBy} label={t('board.meetings.inviteBy')} />
}

/** A local date and time for <input type="datetime-local">. */
export function toLocalInput(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function NewMeetingModal({ onClose, onDone }: { onClose: () => void; onDone: (id: number) => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const qc = useQueryClient()
  const year = new Date().getFullYear()
  const [title, setTitle] = useState(t('board.meetings.defaultTitle', { year }))
  const [startsAt, setStartsAt] = useState('')
  const [place, setPlace] = useState('')
  const [inviteDays, setInviteDays] = useState<number | string>(20)
  const [standard, setStandard] = useState(true)
  const [busy, setBusy] = useState(false)

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    setBusy(true)
    try {
      const m = await saveMeeting({
        title,
        startsAt: new Date(startsAt).toISOString(),
        place,
        inviteDays: Number(inviteDays),
        standardAgenda: standard,
      })
      qc.invalidateQueries({ queryKey: QK.all })
      onDone(m.id)
    } catch (err) {
      notify('error', errorText(err))
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      onSubmit={submit}
      title={t('board.meetings.new')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('board.cancel')}
          </Button>
          <Button type="submit" loading={busy} disabled={!title.trim() || !startsAt}>
            {t('board.meetings.create')}
          </Button>
        </>
      }
    >
      <Field label={t('board.titleField')}>
        <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} data-autofocus />
      </Field>
      <Group grow align="flex-start">
        <Field label={t('board.meetings.startsAt')}>
          <TextInput type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.currentTarget.value)} />
        </Field>
        <Field label={t('board.meetings.inviteDays')} hint={t('board.meetings.inviteDaysHint')}>
          <NumberInput min={0} max={120} value={inviteDays} onChange={setInviteDays} />
        </Field>
      </Group>
      <Field label={t('board.meetings.place')}>
        <TextInput value={place} onChange={(e) => setPlace(e.currentTarget.value)} />
      </Field>
      <Checkbox label={t('board.meetings.standardAgenda')} checked={standard} onChange={(e) => setStandard(e.currentTarget.checked)} />
    </Modal>
  )
}
