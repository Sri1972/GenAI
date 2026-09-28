# PRD.md
## Bookmark Manager — Product Requirements Document

**Document Owner:** Product Management
**Status:** Draft for Engineering Review
**Version:** 1.0

---

## 1. Executive Summary

Bookmark Manager is a simple, focused web application that lets users save links, organize them with tags, and retrieve them quickly through search and filtering. The product's core value proposition is **speed and simplicity**: saving a link should take one action, and finding a saved link should take seconds — not the folder-nesting complexity of browser-native bookmarks or the heavyweight feature sets of "read-it-later" and knowledge-management tools.

This PRD defines the minimum viable product (MVP) scope, the data and validation rules required to make that scope reliable, and the success metrics by which we'll judge the launch.

---

## 2. Problem Statement

Users who consume a high volume of links (articles, tools, references, videos) across browsers and devices struggle to:

1. **Save quickly** — native browser bookmarks require multiple clicks and manual folder decisions at the moment of saving, creating friction that causes users to abandon the habit or default to "leave 40 tabs open."
2. **Organize meaningfully** — folder hierarchies force a single rigid categorization per link, when a link often belongs to multiple contexts (e.g., a link is both "work" and "read-later").
3. **Retrieve reliably** — once saved, links get buried. Native bookmark bars/menus don't support fast full-text or tag-based search, so users re-Google content they already saved.
4. **Trust the system** — broken links, blank titles, and duplicate saves erode confidence that the tool is a reliable system of record.

**Who feels this most:** knowledge workers, researchers, and individual professionals who save 10+ links per week and currently rely on browser bookmarks, notes apps, or messaging themselves links as a workaround.

**Why now:** [ASSUMPTION] No competitive or market timing signal was provided in prior discussion; this PRD treats the opportunity as evergreen (bookmark chaos is a persistent, not a newly emerging, problem) rather than tied to a market trigger. This assumption should be validated with user research before go-to-market planning.

---

## 3. User Personas

### Persona 1: "Research Rita" — The Knowledge Worker
- **Role:** Analyst / consultant / grad student who researches topics across many sources.
- **Behavior:** Opens 15–30 tabs a day; saves links "to read later" and rarely returns to them because there's no organization system.
- **Core need:** A fast way to tag a link with a topic/project so it resurfaces when she searches that topic later.
- **Pain today:** Browser bookmark folders don't scale past ~50 items; she loses track of what's saved.
- **Success looks like:** She saves a link in under 5 seconds and can find "everything tagged #client-x" in one search.

### Persona 2: "Tool-collector Tom" — The Individual Professional
- **Role:** Developer / marketer / freelancer who bookmarks tools, references, and articles for reuse across projects.
- **Behavior:** Bookmarks tend to be reused repeatedly (a pricing calculator, a style guide) rather than "read once."
- **Core need:** Reliable, permanent storage of a curated set of links with tags, accessible from any device via the web.
- **Pain today:** Bookmarks are trapped in one browser profile; switching machines means losing access.
- **Success looks like:** He can log in from any browser and immediately find his saved tools by tag.

### Persona 3: "Casual Casey" — The Light User
- **Role:** Any user who saves links infrequently (a few per week) but wants zero friction when they do.
- **Behavior:** Doesn't want to learn a taxonomy or workflow; wants "save it and it'll be fine."
- **Core need:** A dead-simple save action with sensible defaults (auto-title, auto-favicon) that requires no setup.
- **Pain today:** Tools aimed at power users (nested folders, complex metadata) feel like overkill and get abandoned.
- **Success looks like:** She saves a link with zero mandatory fields beyond the URL and can still find it later by searching roughly what she remembers about it.

---

## 4. Goals & Success Metrics

### Product Goals
1. Make saving a link fast enough that it becomes a default habit, not a chore.
2. Make tagging flexible enough to support multi-context organization without mandatory taxonomy setup.
3. Make retrieval fast and reliable enough that users trust the tool as their system of record for links.

### Success Metrics (targets for first full release cycle post-launch)

| Metric | Target | Rationale |
|---|---|---|
| Median time to save a bookmark (from action start to confirmed save) | ≤ 5 seconds | Directly tests "fast save" goal |
| % of bookmarks saved with at least one tag | ≥ 60% within 30 days of user signup | Tests whether tagging is adopted, not ignored |
| 7-day retention (users who save ≥1 bookmark and return within 7 days) | ≥ 40% | Tests habitual use, not one-time trial |
| Search/filter success rate (user finds the bookmark they were looking for without abandoning) | ≥ 90% | [ASSUMPTION: measured via a "did you find what you were looking for" or successful-click-through proxy, exact instrumentation to be defined] |
| Duplicate-save confusion rate (support tickets or negative feedback tagged "duplicate/confusing") | < 2% of active users per month | Tests reliability of duplicate handling |
| Title/metadata blank-or-broken rate | < 1% of saved bookmarks show blank title after fallback logic | Tests metadata reliability requirement from BA input |

---

## 5. Feature Requirements

Prioritization uses MoSCoW mapped to P0 (Must — we do not ship without this), P1 (Should — high value, ship soon after if not at launch), P2 (Could — nice to have, backlog). **No more than 5 P0 features**, per prioritization discipline.

---

### P0 — Must Have (Launch Blockers)

#### P0.1 — Save a Bookmark by URL
**Description:** User can save a link by providing a URL. This is the core action of the product and must work with minimal required input.

**Requirements:**
- Only the URL is a required field to complete a save; all other fields (title override, tags, description) are optional.
- The system validates the URL is a syntactically valid web address (http/https at minimum) before accepting it. [ASSUMPTION: support for non-http(s) schemes such as `mailto:` or app-specific URIs is deferred — see Open Questions]
- On invalid URL format, the user sees an inline, specific error message (e.g., "This doesn't look like a valid web address") and the save is rejected — never silently stripped, altered, or partially saved.
- The save action completes and confirms success **without waiting on** title-fetch, favicon-fetch, or any other metadata enrichment. Metadata is filled in asynchronously after the URL is saved.
- Maximum URL length is enforced (recommended: 2048 characters); URLs exceeding this are rejected with a clear error, not silently truncated.

**Acceptance Criteria:**
- Given a valid URL and no other input, when the user submits, then the bookmark is saved and confirmed in ≤5 seconds median, independent of the target site's response time.
- Given an invalid URL, when the user submits, then the save is rejected with an inline, specific error and no partial record is created.
- Given a URL longer than the defined maximum, when the user submits, then the save is rejected with a clear "URL too long" error.

---

#### P0.2 — Tag a Bookmark
**Description:** User can attach one or more free-text tags to a bookmark to support multi-context organization, at save time or afterward.

**Requirements:**
- Tags are free-text (no forced taxonomy).
- Tags are normalized as **case-insensitive** for matching and de-duplication purposes ("Work" and "work" are treated as the same tag).
- A bookmark can have multiple tags; a defined maximum tag count per bookmark applies (recommended default: 20) to prevent abuse/errors — exact number is a product decision, not hardcoded in this PRD as final.
- Duplicate tags on the same bookmark are automatically de-duplicated on save (no error shown to user; silently merged).
- Tags can be added, edited, or removed after the bookmark is saved (tagging is not a one-time, save-only action).
- A defined maximum tag length applies to prevent abuse (exact character limit is an open question — see Section 9).

**Acceptance Criteria:**
- Given a user enters "Work" and later "work" as two separate tags on the same bookmark, then the system stores/displays this as a single tag.
- Given a user attempts to add more tags than the defined maximum, then the system prevents the addition and communicates the limit.
- Given a saved bookmark, when the user edits its tags, then the change is reflected immediately without requiring a re-save of the whole bookmark.

---

#### P0.3 — View and Retrieve Bookmarks (List + Search/Filter by Tag)
**Description:** User can see all their saved bookmarks and narrow the list by tag and/or keyword search, so saved links are actually retrievable — not just archived.

**Requirements:**
- All of a user's bookmarks are viewable in a list.
- The user can filter the list by one or more tags.
- The user can search by keyword; search must match against, at minimum, the bookmark's title and URL. [ASSUMPTION: search against description/notes content is in scope only if the Description field itself is confirmed in scope — see P1.3]
- Filtering and search must return results without requiring the user to know exact tag capitalization (consistent with case-insensitive tag normalization in P0.2).
- Empty states are explicitly handled: a new user with zero bookmarks sees guidance to save their first link, not a blank/broken screen. A search/filter with zero matching results shows a clear "no results" state, not an empty blank list indistinguishable from a loading or error state.

**Acceptance Criteria:**
- Given a user with 50+ saved bookmarks, when they filter by a tag, then only bookmarks with that tag (case-insensitive match) are shown.
- Given a user searches a keyword that matches a bookmark's title or URL, then that bookmark appears in results.
- Given zero bookmarks exist for a user, then the list view shows an explicit "no bookmarks yet" empty state with a prompt to save one.
- Given a search or filter returns no matches, then the UI explicitly communicates "no results," distinct from a loading state.

---

#### P0.4 — Automatic Title & Favicon Retrieval with Reliable Fallback
**Description:** When a bookmark is saved, the system attempts to auto-fetch the page title and favicon so users don't have to manually title every link — but this enrichment must never block saving and must never leave a bookmark looking broken.

**Requirements:**
- Title is auto-fetched from the target page when possible; if the user has manually entered a title, the **user-entered title always takes precedence** and is never overwritten by an auto-fetched value.
- If auto-fetch fails for any reason (timeout, unreachable page, blocked by target site, page has no title), the system falls back to using the URL itself as the display title. A bookmark must **never display a blank title.**
- Favicon fetch is asynchronous and best-effort. Before the favicon loads, and if it fails to load, a default placeholder icon is shown — never a broken image state.
- Fetch attempts (title and favicon) must not block or delay the confirmed save from P0.1.

**Acceptance Criteria:**
- Given a page that blocks scraping or times out, when the bookmark is saved, then the bookmark displays the URL as its title and a placeholder icon — not a blank field or error state.
- Given a user manually enters a title before saving, when auto-fetch later completes with a different title, then the user's manual title is preserved and not overwritten.
- Given any title/favicon fetch outcome, then bookmark save confirmation time (per P0.1) is unaffected.

---

#### P0.5 — Duplicate URL Handling
**Description:** When a user saves a URL that already exists in their collection, the system must handle it predictably rather than silently creating confusing duplicate entries.

**Requirements:**
- On detecting an existing identical URL already saved by the same user, the system warns the user ("You've already saved this link") and allows them to proceed rather than blocking the action.
- [ASSUMPTION] Default behavior on "proceed" is to merge into the existing bookmark record (combining/adding any new tags provided) rather than creating a second duplicate entry — this default should be validated with users, as "warn + allow duplicate" was presented as a viable alternative and is not fully resolved.
- Duplicate detection compares exact URL matches; handling of near-duplicate URLs (e.g., with/without trailing slash, tracking parameters) is explicitly **out of scope for v1** (see Section 6).

**Acceptance Criteria:**
- Given a user saves a URL identical to an already-saved bookmark, then the user sees a clear warning before/at the point of duplication rather than a silent second entry appearing with no explanation.
- Given the user proceeds after the warning, then the resulting state (merged record vs. two records) is consistent and predictable, matching the documented default behavior.

---

### P1 — Should Have (High Value, Post-Launch Priority)

#### P1.1 — Edit Bookmark Details After Save
**Description:** User can edit the title, tags, or other saved fields of an existing bookmark after it's been saved (not just at save time).
**Acceptance Criteria:** Given a saved bookmark, when the user edits its title, then the manual edit takes precedence permanently over any future auto-fetch attempt (consistent with P0.4 precedence rule).

#### P1.2 — Delete a Bookmark
**Description:** User can remove a bookmark they no longer want.
**Acceptance Criteria:** Given a saved bookmark, when the user deletes it, then it no longer appears in any list, search, or tag filter, and the user receives confirmation the deletion succeeded.

#### P1.3 — Description/Notes Field
**Description:** User can optionally add a free-text description or note to a bookmark for personal context beyond the title.
**Status:** [ASSUMPTION] BA input flagged this as an open question ("in scope for v1 or not?"). This PRD provisionally places it in P1 (valuable but not launch-blocking) pending stakeholder confirmation — see Open Questions.
**Acceptance Criteria:** Given a bookmark with a description added, when the user searches a keyword contained only in the description, then the bookmark appears in results (extending P0.3 search scope once this field is confirmed in scope).

#### P1.4 — Bulk Tag Management
**Description:** User can rename a tag across all bookmarks that use it, or bulk-remove a tag, without editing each bookmark individually.
**Acceptance Criteria:** Given a tag used on 20 bookmarks, when the user renames that tag once, then all 20 bookmarks reflect the new tag name.

#### P1.5 — Sort Options for Bookmark List
**Description:** User can sort their bookmark list (e.g., by date saved, alphabetically by title).
**Acceptance Criteria:** Given a list of bookmarks, when the user selects a sort option, then the list re-orders accordingly and the choice persists across the session.

---

### P2 — Could Have (Backlog / Future Consideration)

#### P2.1 — Multi-Tag Boolean Filtering
Filter bookmarks by combinations of tags (AND/OR logic), not just a single tag at a time.

#### P2.2 — Import Existing Bookmarks
Bring in bookmarks from an existing source in bulk rather than saving one at a time.
**Note:** No specific source or format was defined in prior discussion — treat as directional backlog item only, not a committed requirement.

#### P2.3 — Shared/Collaborative Bookmark Collections
Allow bookmarks or tag-based collections to be shared with or viewed by other users.
**Note:** No multi-user/sharing requirement was present in the original product description or BA input; flagged here purely as a plausible future direction, not a validated need.

#### P2.4 — Link Health Checking
Periodic checking of saved links to flag ones that have gone dead (404) over time, distinct from the one-time fetch-at-save behavior in P0.4.

#### P2.5 — Link Safety/Malware Screening
Checking saved URLs against malware/phishing indicators before or after save.
**Explicitly flagged by BA input as needing a scope decision.** This PRD defers it entirely to backlog; it is **not** a v1 commitment. See also Section 6 (Out of Scope) and Section 7 (Risks).

---

## 6. Out of Scope (v1)

To prevent scope creep, the following are explicitly **not** part of this release:

- **Folder/hierarchical organization** — the product deliberately uses flat tagging instead of nested folders; this is a core positioning decision, not an oversight.
- **Near-duplicate URL detection** (e.g., normalizing away tracking parameters, trailing slashes, http vs https as "the same" link) — only exact URL matches are deduplicated in v1.
- **Link safety / malware / phishing screening** — explicitly deferred per BA input; must be clearly communicated to users as not provided, not silently absent.
- **Bulk import from external sources** — moved to P2 backlog, not committed for v1.
- **Sharing or multi-user collaboration on bookmarks or collections** — no requirement for this exists in current scope.
- **Automatic screenshot/visual preview capture of saved pages** — only title and favicon metadata are in scope; visual page previews were not requested in prior discussion.
- **Browser extension or any specific client/integration mechanism** — this PRD defines the product's functional behavior; delivery mechanism (extension, mobile app, etc.) is an implementation/architecture decision outside this document's scope.
- **Periodic re-checking of link health after initial save** — v1 fetch is a one-time, at-save-time attempt only (see P2.4 for future consideration).
- **Support for non-http(s) URI schemes** (e.g., `mailto:`, custom app schemes) — see Open Questions; treated as out of scope pending explicit decision.

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Metadata fetch (title/favicon) becomes a save-blocking bottleneck if not architected as strictly asynchronous | High — directly undermines the "fast save" core value prop and the ≤5s save target | P0.1 and P0.4 explicitly mandate that save confirmation is never blocked on external fetch; this must be enforced as a hard acceptance criterion, not a best-effort goal |
| Duplicate-handling default (merge vs. warn-and-allow) is not yet validated with real users | Medium — wrong default could cause data loss (unwanted merge) or clutter (unwanted duplicates), damaging trust | Ship P0.5 with the documented default but treat it as provisional; instrument and monitor duplicate-related support/feedback signals post-launch and revisit if the < 2% confusion target (Section 4) is missed |
| Absence of link-safety screening could expose users to malicious links with no warning | Medium — reputational/trust risk if a user is harmed by a saved malicious link | Explicitly and clearly disclose to users that no link-safety screening is performed (not a silent gap); revisit as P2 if user feedback or incidents warrant |
| Tag free-text with no taxonomy could lead to tag sprawl (many near-duplicate tags) reducing retrieval usefulness | Medium — undermines the P0.3 retrieval goal over time as a user's tag list grows unmanaged | Case-insensitive normalization (P0.2) is a first mitigation; P1.4 bulk tag rename/cleanup is prioritized as a near-term follow-up specifically to address sprawl |
| Sites that block automated fetching (403/429) or require authentication may cause title/favicon fetch to systematically fail for a meaningful share of links, degrading perceived quality | Medium — could push the <1% blank-title metric off target if fallback isn't robust | P0.4's URL-as-title fallback is mandatory and must be tested against known scraper-blocking sites before launch, not just happy-path sites |
| Casual/light users (Persona 3) may abandon if any field beyond URL is perceived as mandatory, even if technically optional | Low-Medium — affects adoption/retention for the lightest-touch persona | UI must make the single required field (URL) unambiguous; enforced as a product requirement in P0.1, verified via usability testing pre-launch |

---

## 8. User Journey Summary (Illustrative, Not Exhaustive)

1. **First-time save:** Casey pastes a URL, submits with no other input, sees an immediate save confirmation, and later sees the title/favicon populate automatically.
2. **Habitual tagging save:** Rita saves a link and adds two tags ("client-x", "research") in the same action; she does this multiple times a day.
3. **Retrieval:** A week later, Rita filters her list by "client-x" and finds the link instantly without remembering its exact title.
4. **Duplicate encounter:** Tom accidentally saves a tool link he'd already saved months ago; he's warned and the tags merge into the existing entry rather than creating clutter.
5. **Edit after the fact:** Tom later realizes an auto-fetched title is unhelpful and overrides it manually; the override sticks permanently.
6. **Empty/zero-result states:** A brand-new user sees a clear prompt to save their first bookmark rather than a confusing blank screen; a user whose tag filter matches nothing sees an explicit "no results," not ambiguity.

---

## 9. Open Questions

The following were raised in prior discussion (BA input) and require explicit stakeholder decisions before or shortly after development begins — they are called out here rather than silently assumed away:

1. **URI scheme support:** Should the product accept only http/https, or also `ftp`, `mailto`, or app-specific custom schemes? Current PRD assumes http/https only pending decision.
2. **Duplicate handling default:** Confirm whether "auto-merge tags into existing bookmark" or "warn + allow true duplicate" is the correct default behavior (P0.5 currently assumes merge as a labeled assumption).
3. **Description/Notes field:** Confirm whether this is in scope for the initial launch (would elevate it from P1 to P0) or genuinely deferred (confirming its current P1 placement).
4. **Exact tag limits:** Confirm the maximum number of tags per bookmark and the maximum character length per tag (P0.2 recommends 20 tags as a default but this is not finalized).
5. **URL length limit:** Confirm the exact maximum URL length to enforce (P0.1 recommends 2048 characters based on common browser conventions, not finalized).
6. **Link safety screening timeline:** Confirm whether malware/phishing screening (P2.5) is truly indefinitely deferred or should be scheduled for a near-term follow-up release, given potential trust/liability implications.
7. **Search scope confirmation:** Once the Description field's in/out-of-scope status (Question 3) is resolved, confirm whether search must include it (affects P0.3's final acceptance criteria).
8. **"Why now" / market context:** No competitive or market-trigger rationale was supplied in prior discussion; recommend a lightweight competitive scan (browser-native bookmarks, existing bookmark/read-later tools) before go-to-market messaging is finalized, even though this PRD does not require it to define the v1 feature set itself.