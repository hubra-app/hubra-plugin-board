import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Button, Group, Paper, Text } from '@mantine/core'
import { IconUsers } from '@tabler/icons-react'
import { useT } from '@hubra/plugin-sdk'
import { QK, listMeetings } from './api'
import { formatWhen } from './BoardScreen'

/** On the member's own page: the next general meeting they were invited to. */
export function NextMeetingCard() {
  const { t } = useT()
  const navigate = useNavigate()
  const meetings = useQuery({ queryKey: QK.meetings, queryFn: listMeetings })
  const now = Date.now() - 6 * 3600_000
  const next = (meetings.data ?? [])
    .filter((m) => m.invitedAt && !m.closedAt && new Date(m.startsAt).getTime() > now)
    .sort((a, b) => a.startsAt.localeCompare(b.startsAt))[0]
  if (!next) return null
  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="sm" wrap="nowrap">
          <IconUsers size={22} />
          <div>
            <Text fw={600}>{next.title}</Text>
            <Text size="sm" c="dimmed">
              {formatWhen(next.startsAt)}
              {next.place ? ` · ${next.place}` : ''}
            </Text>
          </div>
        </Group>
        <Button variant="light" onClick={() => navigate(`/app/board/meetings/${next.id}`)}>
          {t('board.meetings.showAgenda')}
        </Button>
      </Group>
    </Paper>
  )
}
