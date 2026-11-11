import { Badge, Group, Select, Text } from '@mantine/core'
import { IconUser, IconUsersGroup } from '@tabler/icons-react'
import { Field, MemberPicker, Seg, useT } from '@hubra/plugin-sdk'
import { daysUntil, formatDay, type Options } from './api'

/** Who a task, duty or contract is for: a person, or a function's holders. */
export interface WhoValue {
  ownerId: number | null
  functionId: number | null
}

export function WhoField({
  value,
  onChange,
  options,
}: {
  value: WhoValue
  onChange: (v: WhoValue) => void
  options: Options | undefined
}) {
  const { t } = useT()
  const mode = value.functionId ? 'function' : 'person'
  const functions = options?.functions ?? []
  return (
    <Field label={t('board.who')} hint={mode === 'function' ? t('board.whoFunctionHint') : undefined}>
      <div>
        <Seg
          options={[
            { value: 'person', label: t('board.person') },
            { value: 'function', label: t('board.function') },
          ]}
          value={mode}
          onChange={(m) =>
            onChange(
              m === 'function'
                ? { ownerId: null, functionId: functions[0]?.id ?? null }
                : { ownerId: null, functionId: null },
            )
          }
        />
        <div style={{ marginTop: 8 }}>
          {mode === 'person' ? (
            <MemberPicker
              aria-label={t('board.person')}
              value={value.ownerId}
              noneLabel={t('board.nobody')}
              onChange={(id) => onChange({ ownerId: id ? Number(id) : null, functionId: null })}
            />
          ) : (
            <Select
              aria-label={t('board.function')}
              data={functions.map((f) => ({ value: String(f.id), label: f.name }))}
              value={value.functionId ? String(value.functionId) : null}
              onChange={(id) => onChange({ ownerId: null, functionId: id ? Number(id) : null })}
              placeholder={functions.length ? undefined : t('board.noFunctions')}
              searchable
              clearable
            />
          )}
        </div>
      </div>
    </Field>
  )
}

/** The person or function shown in a list. */
export function WhoLabel({ ownerName, functionName }: { ownerName: string | null; functionName: string | null }) {
  const { t } = useT()
  if (functionName)
    return (
      <Group gap={4} wrap="nowrap">
        <IconUsersGroup size={14} />
        <Text size="sm">{functionName}</Text>
      </Group>
    )
  if (ownerName)
    return (
      <Group gap={4} wrap="nowrap">
        <IconUser size={14} />
        <Text size="sm">{ownerName}</Text>
      </Group>
    )
  return (
    <Text size="sm" c="dimmed">
      {t('board.nobody')}
    </Text>
  )
}

/** A due date, red when past, orange within two weeks. */
export function DueBadge({ day, done, label }: { day: string | null; done?: boolean; label?: string }) {
  const { t } = useT()
  if (!day) return null
  const left = daysUntil(day) ?? 0
  const color = done ? 'gray' : left < 0 ? 'red' : left <= 14 ? 'orange' : 'gray'
  const hint = done
    ? ''
    : left < 0
      ? ` · ${t('board.overdue')}`
      : left === 0
        ? ` · ${t('board.today')}`
        : left <= 14
          ? ` · ${t('board.inDays', { count: left })}`
          : ''
  return (
    <Badge variant="light" color={color} style={{ textTransform: 'none' }}>
      {label ? `${label} ` : ''}
      {formatDay(day)}
      {hint}
    </Badge>
  )
}
