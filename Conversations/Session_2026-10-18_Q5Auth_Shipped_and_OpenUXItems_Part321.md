# Part 321 — Q5 auth shipped + open auth-UX items (to do later)

Q5 (authentication + recruiter access) shipped this session. This log captures the
**open UX/polish items** the user flagged on 2026-10-18 to be worked on **later** —
nothing in the "Open items" section is implemented yet.

## What shipped (ml-portfolio)
- **Model:** public tools need no login; a **user** logs in (email/password) → the
  real homepage, signed in; the **owner** (identity = `OWNER_EMAIL` env) → `/portfolio`
  (private portfolio + recruiter-link manager); **recruiters** view the portfolio via
  a secret, expiring, revocable **share-link `/r/<token>`** with no login.
- Supabase Auth via `@supabase/ssr`; `supabase/auth.sql` (profiles+RLS) and
  `supabase/recruiter_links.sql`. Gate in `src/proxy.ts`.
- Commits: `d011b8c` (M1 auth), `0ef53d9` (M2a private portfolio + share-links),
  `2fd493e` (M2b owner→/portfolio + user home), `1e59de5` (user→homepage + richer
  public /about).
- Reference docs (local-only): `ml-portfolio/docs/ACCESS_AND_AUTH.md`,
  `ML-Unified/docs/SECURITY_REFERENCE.md`, `docs/LOGGING_OVERVIEW.md`, `docs/prd/`.

## Open items (NOT done — work on later)

**Process the user wants for these:** research patterns online, bring back ideas,
**ask the user**, then implement. (Not: implement blind.)

1. **Sign-out control looks off.** The "Sign out" chip styling is inconsistent with
   the rest of the navbar — restyle so it fits the nav's visual language.

2. **No signed-in identity shown.** The navbar shows "Account / Sign out" but not the
   user's name / email / avatar, so you can't tell *who* is logged in. Add a visible
   identity (name or email + avatar).

3. **Owner landing destination.** Owner login currently lands on `/portfolio` (which
   leads with the personal portfolio / "About"). User questions whether the owner
   should instead land on the **homepage**, with the portfolio reachable from a menu.
   → Decide the intended owner landing + how the portfolio is reached. (Same two
   sub-gripes as #1/#2 noted here too: identity + sign-out styling.)

4. **Recruiter-link manager placement.** The "Recruiter share-links" panel sits at the
   top of `/portfolio` and looks out of place / odd there. → Find a better home for it
   (e.g. an owner settings/"Sharing" area, a dedicated page, or inside a profile menu)
   rather than bolted above the portfolio.

5. **Proper profile menu.** Replace the bare "Account / Sign out" with a real profile
   dropdown (avatar → Account, Settings, Sign out, …), like a normal app. This likely
   subsumes #1, #2, and possibly #4 (manage-sharing could live under it).

## Suggested grouping when we resume
Items 1, 2, 5 are one piece of work: **a proper authenticated navbar/profile menu**
(avatar + identity + dropdown with Account / Settings / Sign out). Items 3 and 4 are
**information-architecture** decisions (owner landing page; where portfolio + the
recruiter-link manager live). Research common SaaS/dashboard patterns, propose 2–3
options with mockups, confirm with the user, then build.

---

## Resolved — 2026-10-19 (auth-UX pass)

Researched SaaS/design-system patterns (Visa, Shopify, WFP, Splunk — converge on
avatar → dropdown with identity header + Sign out as a menu item), proposed options,
user chose via AskUserQuestion, then built. Decisions: **avatar + initials** in the
navbar; **full owner-aware** dropdown; owner **lands on the homepage**; share-links
get a **dedicated page**.

| # | Item | What shipped |
|---|---|---|
| 1 | Sign-out chip styling | Sign out is now a **menu item** inside the dropdown (shares the menu's visual language), not a standalone chip. |
| 2 | No signed-in identity | Navbar shows an **avatar (initials)**; the dropdown header shows **email + role** (Owner / User). |
| 3 | Owner landing | Owner now lands on the **homepage** like everyone (post-login router `/app` → `/`); portfolio reached from the menu. |
| 4 | Recruiter-link placement | Moved off `/portfolio` to a **dedicated `/portfolio/share` page**, opened from the menu (and a "Manage share links" link on `/portfolio`). |
| 5 | Proper profile menu | Avatar → dropdown: identity header, owner's **My portfolio / Share links**, **Account**, **Settings**, **Sign out**. Click-outside + Escape + ARIA. |

New pages/routes: `/account`, `/settings`, `/portfolio/share`, `/api/me` (serves
`{email, role, isOwner}` so the client is owner-aware without `OWNER_EMAIL` ever
reaching the browser). Build + lint green; signed-out navbar verified locally. The
signed-in dropdown needs the owner password to see live → verify on the Vercel
deploy. Full operational detail: `ml-portfolio/docs/ACCESS_AND_AUTH.md` (local-only).
