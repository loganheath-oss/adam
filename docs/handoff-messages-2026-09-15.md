# Messages to send, 2026-09-15

Drafts only. Nothing here has been sent. Paste into Slack and edit freely.

These people are not reachable from `logan@storysellers.co` (a Gmail search for Leon, Haresh, Max,
Elise, Adrie and Bree returns nothing but automated Upwork platform mail), so these are written for
Slack rather than email.

Order matters. The first two have third-party lead times and **12 working days** remain before
2026-09-30. The third unblocks Elise this week.

---

## 1. Leon Zhao: ownership transfer

> Leon, I'm at 12 working days on the contract and there are four things that have to move off my
> personal accounts before the 30th. None of them can be done after my access ends, so I'd rather
> start them now than discover a blocker on the last week.
>
> 1. The GitHub repo. It's `loganheath-oss/adam` on my personal account today. It needs to move to
> an Upwork or CM org, and then Railway's deploy source needs repointing at the new location.
> 2. The Railway project. `angelic-liberation`, currently sitting in my personal workspace, billed
> to CM. The project and the billing both need to transfer. Worth knowing: the sprint volume lives
> there and it fills up periodically, which strands runs until someone prunes it. Whoever holds
> Railway owns that chore.
> 3. The MCP connector. This is the one I'd flag hardest. It's registered in my personal Claude Max
> account, and Adrie drives the approval gates through it. Upwork is on Anthropic Enterprise so
> connectors are allowed, but my role can't add one, so it needs an admin to register it at the org
> level. When my account goes, her workflow goes with it.
> 4. The Figma token. Library photo lookup and the template lint both run on my personal token.
> Needs replacing with a team one. The Figma file itself is already Upwork-owned, it's just the
> token that isn't.
>
> Who should I be working with on each of these? Happy to do the legwork, I just need the accounts
> on the other end.

---

## 2. Haresh's team: LLM Gateway

> We still don't have the LLM Gateway values, and that's now the item most likely to miss.
>
> What I need is the endpoint, the key, and the model identifiers. The scaffolding is already in the
> stage modules behind `LLM_GATEWAY_*` environment variables, so once I have real values it's
> configuration rather than a build.
>
> The arithmetic: my contract ends 2026-09-30, which is 12 working days out. Integration and a test
> run need a few of those days on my side, so values arriving in the last week land after I can do
> anything useful with them. Routing LLM traffic through the gateway is a hard production
> requirement, so if it doesn't happen before I go it becomes Max's problem on a system he's still
> learning.
>
> Is there a date you can commit to, or is there someone else I should be asking?

---

## 3. Elise: updated plugin, and what changed

> New plugin is up, version 2026.09.16. Grab it from the /plugin page on the ADAM site, unzip, then
> Plugins, Development, Import plugin from manifest. Importing over the old one is fine.
>
> Reddit should actually assemble now. It couldn't before, and it wasn't close. Four things were
> stacked up: the plugin only ever looked for the Meta board master, the spec cards' text labels were
> shadowing your Reddit_Adtype containers so no template could be found, the slot wrappers are about
> 116px taller than the templates because of the size label so nothing matched on size, and Reddit's
> single copy panel didn't fit the Meta two-panel shape. All four are fixed. I verified it against
> the live file rather than by running it, so your first run is the real test.
>
> On the pills reading "Ad Concept # 1" and "Photo Hero": that wasn't the plugin update you
> installed. Those two labels are the only text in the board master set in Neue Montreal rather than
> PP Neue Montreal, and when that font isn't available the plugin was failing silently and leaving
> the placeholder. It now falls back to PP Neue Montreal and says so in the log, so it should just
> work regardless.
>
> Two questions that would close it out properly:
> - Does Figma show a missing-fonts badge when you open the test file?
> - Were the 8/31 and 9/8 runs done in the same file and on the same machine?
>
> A few things on your side when you get a chance:
> - Add a `Generated Tests` **section** to whatever page you run the plugin from. Without one the
> plugin searches the whole document, finds the section on the Template Library page, and builds
> there. That's why your output kept landing somewhere else.
> - `Reddit_Adtype_Split-Screen` has two Rules cards, a blank one and the finished one. Whichever
> gets read first wins, and a harvest read the blank one and marked the whole ad type as blocked. Can
> you delete the stale one?
> - Five Reddit containers have two frames with the same name and size (Meme, Graphic-With-Text,
> Person-With-Text, Person-Only, Search-and-Checkbox). The plugin takes whichever it finds first, so
> if they differ it's a coin flip.
> - Graphic-With-Text and Text-with-Icons are each missing copy layers on their landscape size only.
> The portrait versions are correct, so it looks fine until half the run comes out empty.
> - Us-vs-Them only has one headline and one set of bullets, but the spec calls for both sides.
>
> Two heads-ups rather than asks:
> - Your Reddit copy panel has a CTA row, and the plugin deliberately hides CTA rows because Meta
> uses a platform CTA button. If Reddit ads need a visible CTA in that panel, tell me and I'll change
> it.
> - Don't run "normalize layer names" on the Reddit board. It renames any slot called 1440x1080 to
> 1440x1800, which is a Meta-specific repair that would break yours.
>
> Also: the cleanup button now only deletes boards on the page you're on. It used to walk the whole
> file, which meant one click could wipe other people's output.

---

## 4. Logan's own checklist

- [ ] Share the three role guide Google Docs. They're private in Drive and need "Anyone with the
      link, Commenter" before the Slack drop.
- [ ] Rotate the Figma and Railway tokens shared during the build.
- [ ] Confirm the Drive folders (Brand / Sprints / Approved) are team-accessible, IDs are in
      `configs/upwork_config.json`.
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON` is still unset, so the delivery stage has never run.
- [ ] Reply on Natelise's three Figma threads so she sees why they were closed.
