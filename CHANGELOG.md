# Board

## Unreleased

- The responsible function can be cleared with × (dropdowns no longer empty themselves on a second click).
- **Funktionen** (new tab): who is on the board. Lists every function that gives the Board role (Präsidium, Aktuar/in, Kassier/in … from Mitglieder › Funktionen), its current holders with their term, "Unbesetzt" when nobody holds it, holders elected for later, and how many of its tasks are open. Every member may see it; "Funktionen verwalten" opens Mitglieder › Funktionen for those who may change them. New `GET /members`.

## 1.1.0

- Gives the standard roles access when a club first switches it on (`role_defaults`, docs/roles.md in hubra-app/hubra): Vorstand Bearbeiten, Aktuar/in Alles. Roles without access don't see it; their own data from it stays on their profile. Needs Hubra 0.2.5 or later.
- Dashboard widgets: **Vorstandsaufgaben** (open tasks, only mine or all, due first) and **Nächste Versammlungen** (meetings ahead with date and place; members without the right to run meetings see only those they were invited to). Both need `board.tasks.read`.

## 1.0.0

First version. What the board (Vorstand) runs, in one place:

- **Tasks** for a person or a function. A function's task passes to whoever holds it next. Open, mine and done lists; a reminder when one is due within three days.
- **Year planner** of recurring duties (date, who, lead time). Each year a duty turns into a task in time.
- **Contracts** and insurances with cost, term, notice period and automatic renewal. Shows the next notice deadline and reminds before it; contracts that ran out show as expired.
- **General meeting (GV)**: standard agenda, the statutory invitation deadline with a reminder, invitation to all members with a PDF, sign-in with quorum, minutes and decisions per item, linked polls, and the minutes as a PDF.
- A card on the member's account page for the next meeting they are invited to.
