import { registerPlugin } from '@hubra/plugin-sdk'
import { IconBriefcase } from '@tabler/icons-react'
import { BoardScreen } from './BoardScreen'
import { MeetingScreen } from './MeetingScreen'
import { NextMeetingCard } from './NextMeetingCard'
import translations from './translations.json'

registerPlugin({
  id: 'board',
  routes: [
    { path: 'board', module: 'board', perm: 'board.tasks.read', component: BoardScreen },
    { path: 'board/planner', module: 'board', perm: 'board.tasks.read', component: BoardScreen },
    { path: 'board/contracts', module: 'board', perm: 'board.contracts.read', component: BoardScreen },
    // Members open an invitation from the bell; the API decides what they see.
    { path: 'board/meetings', module: 'board', component: BoardScreen },
    { path: 'board/meetings/:id', module: 'board', component: MeetingScreen },
  ],
  slots: [{ slot: 'account.cards', module: 'board', component: NextMeetingCard }],
  // The nav entry in hubra_board/__init__.py names this icon.
  icons: { briefcase: IconBriefcase },
  translations,
})
