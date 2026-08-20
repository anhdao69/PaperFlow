# PaperFlow iPhone — Final UI/UX Implementation Specification

> **Resolved-contract revision: 2026-08-20.** This version is aligned with the authoritative technical plan for public abstracts/URLs, publication-timezone Today behavior, personal timestamps, Unsave/resave retention, progress wording, unique topic totals, and Saved-only search.

## 0. Purpose of This Document

This document is the **authoritative UI/UX implementation guide for the PaperFlow iPhone application**.

The coding agent should use this specification together with the existing PaperFlow technical implementation plan.

The goal is **not** merely to reproduce a static mockup.

The implementation should reproduce:

- the visual hierarchy;
- navigation;
- screen structure;
- information density;
- reusable components;
- typography;
- spacing;
- card hierarchy;
- interaction behavior;
- loading states;
- saved/review state;
- swipe behavior;
- offline behavior;
- accessibility behavior;
- navigation persistence;
- daily-use ergonomics.

The final application should feel like a **native premium iOS research companion**, not a dashboard, social feed, or generic AI application.

The product should optimize for one recurring workflow:

**Discover → Triage → Save → Deep Read → Finish**

The three permanent bottom navigation tabs are:

1. **Today**
2. **Topics**
3. **Saved**

Do not introduce additional primary tabs.

## 0.1 Reference-board boundaries

The PNG boards are composition references, not product-data or feature contracts.

- Topic names, subtopic names, paper titles, counts, authors, timestamps, and figures shown in the boards are illustrative. Runtime taxonomy and counts come only from published JSON derived from `configs/topics.yaml`.
- Do not implement the boards' streak, all-time counter, quote, confetti, tomorrow preview, topic analytics/recent activity, Import from arXiv, Add from Topics, or fabricated reading percentages in core V1.
- Do not add a control merely because it appears in a board. A written interaction and real backing data are required.
- Use the boards for information hierarchy, approximate density, spacing, component relationships, and restrained visual tone.

---

# 1. Core Product Philosophy

PaperFlow should feel extremely easy to open and use every day.

The user should never need to think:

> “Where am I supposed to go?”

The three tabs have distinct mental models.

### Today

Answers:

> What arrived today?

Primary purpose:

- daily discovery;
- daily review progress;
- Browse today's papers;
- Swipe today's unread papers;
- reopen previous dates.

---

### Topics

Answers:

> What exists in this research area?

Primary purpose:

- explore research taxonomy;
- access complete topic/subtopic history;
- Browse a research area;
- Swipe unread papers inside a research area.

---

### Saved

Answers:

> What have I decided is worth deeper attention?

Primary purpose:

- personal paper library;
- Deep Read Queue;
- Reading state;
- Done state;
- notes;
- rating;
- long-term paper management.

---

# 2. UX Principles

## 2.1 Optimize for daily use, not maximum information density

Do not attempt to fit every possible piece of information on screen.

Prefer:

- fewer elements;
- larger tap targets;
- stronger hierarchy;
- readable titles;
- one obvious primary action;
- progressive disclosure.

Avoid:

- dense dashboards;
- excessive statistics;
- too many badges;
- tiny fonts;
- several competing buttons;
- excessive gradients;
- decorative cards that do not communicate information.

---

## 2.2 Content should dominate the interface

PaperFlow exists for papers.

The interface should visually prioritize:

1. paper title;
2. figure/thumbnail when available;
3. TL;DR;
4. topic labels;
5. review/save state;
6. relevance/novelty;
7. secondary metadata.

Author names, timestamps, arXiv IDs, etc. should remain visually secondary.

---

## 2.3 Separate discovery from deep reading

Today and Topics are primarily **discovery/triage environments**.

Saved is primarily a **deep-reading environment**.

Do not overload Today with notes, ratings, reading progress, etc.

Do not overload Saved with daily discovery metrics.

---

# 3. Overall Visual Language

## 3.1 General feel

Target visual character:

- premium;
- quiet;
- clean;
- research-oriented;
- friendly;
- highly readable;
- Apple-native;
- slightly futuristic but not flashy.

The application should feel closer to:

- Apple Reminders;
- Apple News;
- Things;
- Arc Search;
- Readwise Reader;

than to:

- a business analytics dashboard;
- a social media feed;
- a crypto application;
- a colorful productivity gamification app.

---

# 4. Color System

Use semantic colors rather than scattering literal colors throughout SwiftUI.

Suggested token names:

```text
PFBackground
PFSurface
PFSurfaceSecondary
PFPrimary
PFPrimarySoft
PFTextPrimary
PFTextSecondary
PFTextTertiary
PFDivider
PFSuccess
PFSuccessSoft
PFDanger
PFDangerSoft
PFWarning
```

## 4.1 Main accent

The primary PaperFlow identity color is a blue-purple / indigo.

Approximate light-mode target:

```text
Primary:
#6554F6

Primary Strong:
#5A45F5

Primary Soft:
#F1EFFF

Primary Very Soft:
#F8F7FF
```

Do not aggressively saturate the entire interface.

Purple should primarily communicate:

- selection;
- navigation;
- active state;
- saved state;
- progress;
- primary button.

---

## 4.2 Neutral palette

Approximate:

```text
Background:
#FAFAFC or systemGroupedBackground

Primary Surface:
#FFFFFF

Secondary Surface:
#F7F7FA

Primary Text:
#11131A

Secondary Text:
#65697A

Tertiary Text:
#9699A6

Divider:
#EAEAEE
```

Prefer iOS semantic colors where possible.

---

## 4.3 Functional colors

### Save / positive action

Use green only when it conveys a meaningful action or successful state.

```text
Success:
#25A56A

Success Soft:
#EDF9F3
```

Use for:

- Save button in swipe deck;
- Done indicator;
- completed state.

---

### Skip / destructive-ish triage action

Skip is not destructive to canonical PaperFlow data.

Still use a gentle red:

```text
Danger:
#E74F58

Danger Soft:
#FFF1F2
```

Use for:

- Skip button;
- Remove from Saved confirmation.

Never make Skip visually alarming.

---

# 5. Typography

Use **Apple system fonts only**.

SwiftUI:

```swift
.system(...)
```

Do not bundle custom fonts.

Recommended hierarchy:

### Large screen title

```text
28–32 pt
Semibold/Bold
```

Examples:

- Today
- Topics
- Saved

---

### Navigation title

```text
17 pt
Semibold
```

Examples:

- Aug 20, 2026
- World Models
- Video World Models
- Queue
- Reading

---

### Paper title — list

```text
15–17 pt
Semibold
```

Maximum approximately:

```text
2–3 lines
```

Do not reduce the font simply to force longer titles onto one line.

---

### Swipe card title

```text
22–25 pt
Bold
```

Maximum:

```text
3 lines
```

---

### Paper Detail title

```text
24–28 pt
Bold
```

Allow flexible wrapping.

---

### Section header

```text
13–15 pt
Semibold
```

---

### Body / TL;DR

```text
14–16 pt
Regular
lineSpacing ≈ 2–4 pt
```

---

### Metadata

```text
11–13 pt
Regular/Medium
secondary color
```

Never rely heavily on text below ~11 pt.

---

# 6. Spacing System

Use an 8-point-derived spacing system.

Suggested tokens:

```text
space2   = 2
space4   = 4
space6   = 6
space8   = 8
space12  = 12
space16  = 16
space20  = 20
space24  = 24
space32  = 32
```

Main horizontal page padding:

```text
16 pt
```

Large screens may occasionally use:

```text
20 pt
```

Card internal padding:

```text
12–16 pt
```

Vertical space between major sections:

```text
20–28 pt
```

---

# 7. Corner Radius

Use consistent radii.

```text
Small controls:
8–10 pt

Tags:
7–9 pt

Standard cards:
14–16 pt

Large feature cards:
18–20 pt

Bottom floating primary button:
14–18 pt
```

Avoid arbitrary radius values throughout the codebase.

---

# 8. Borders and Shadows

Cards should mostly be separated through:

- subtle background difference;
- hairline borders;
- spacing.

Recommended:

```text
Border:
0.5–1 pt
very light gray
```

Avoid heavy shadows.

If shadow is used:

```text
low opacity
small blur
minimal vertical offset
```

PaperFlow should not look like a stack of floating material-design cards.

---

# 9. Global Bottom Navigation

Permanent tabs:

```text
Today
Topics
Saved
```

SF Symbols examples:

```text
Today  → calendar / house-like daily icon
Topics → square.grid.2x2
Saved  → bookmark
```

Selected state:

- primary purple icon;
- primary purple label;
- very subtle purple pill/background behind selected icon if desired.

Unselected:

- secondary gray.

Bottom navigation should remain visually quiet.

Do not place large badges on the tab bar except potentially a very small Saved count in a future version.

---

# 10. Shared Navigation Rules

Each root tab maintains its own navigation stack.

Switching:

```text
Today → Topics → Today
```

should return the user to their previous position in Today whenever reasonable.

Examples:

If the user is browsing:

```text
Today
→ Aug 20
→ Browse
→ scroll position 17/42
```

then temporarily switches to Saved and comes back:

```text
Today should ideally restore Browse near position 17/42.
```

Do not reset the navigation stack unnecessarily.

---

# 11. GLOBAL PAPER STATES

Visual state should reflect the private personal model.

Possible state combinations include:

```text
Unreviewed + Unsaved
Reviewed + Unsaved
Reviewed + Saved + Queue
Reviewed + Saved + Reading
Reviewed + Saved + Done
```

Never visually imply that Skip deletes the paper.

---

# 12. Shared Paper Card Component

Create one reusable component conceptually similar to:

```text
PaperListCard
```

Variants:

```text
compact
standard
saved
reading
done
```

Do not create unrelated visual implementations for every page.

---

## 12.1 Standard paper card

Layout:

```text
┌──────────────────────────────────────┐
│ ┌──────────┐  Paper Title           │
│ │          │  up to 2–3 lines       │
│ │ Figure   │                         │
│ │          │  [World Models] [Video]│
│ └──────────┘                         │
│               TL;DR one or two lines│
│                                     │
│ ● High relevance        🔖 Saved    │
└──────────────────────────────────────┘
```

Approximate image:

```text
76–90 pt wide
76–90 pt high
```

Aspect ratio may depend on source figure.

Use:

```text
scaledToFill / clipped
```

for thumbnails.

---

## 12.2 Missing figure

Do not collapse the figure area unpredictably.

Use a consistent placeholder.

Placeholder:

- very light purple;
- minimal document/figure icon;
- no large explanatory text.

Future real figures should replace this component without changing card geometry.

---

# 13. Paper Topic Pills

Topic tags should use:

```text
small capsule
soft tinted background
colored/neutral text
```

Example:

```text
[World Models] [Video]
```

Recommended:

```text
font: 10–12 pt Medium
horizontal padding: 7–9
vertical padding: 3–5
```

Maximum visible tags in lists:

```text
2–3
```

If more exist:

```text
+2
```

Do not allow tags to dominate the card.

---

# 14. TODAY TAB

---

# 14.1 Today Home

This is the default screen when PaperFlow opens.

The screen should answer within roughly one second:

1. How many papers arrived?
2. How much have I reviewed?
3. What should I do next?

“Today” always means the current calendar date in the PaperFlow publication timezone supplied by `feed_index.json`. It is not an alias for the newest successful historical feed, and device travel does not change feed-day identity. Date text may still use the user's locale formatting.

If the current date exists in the feed index, show its exact payload, including a legitimate zero-paper result. If it is absent but an older successful day exists, show:

```text
Today's feed isn't available yet.

Latest Available
Tue, Aug 19 · 35 papers
```

The older day may be prefetched and opened, but must not be labeled as today. If cached data is being shown, add the standard Offline/Last Updated context. Use “No papers matched your research interests today” only when the server explicitly published the current date with `paper_count = 0`.

---

## Layout

```text
Navigation
────────────────────────

PaperFlow

Today
Wednesday, Aug 20

TODAY'S PAPERS CARD
────────────────────────
42 papers

43%
18 reviewed
24 remaining

[ Browse ]        [ Swipe ]

Previous Days                     See All

Aug 19
35 papers                   71% reviewed >

Aug 18
51 papers                   61% reviewed >

Aug 17
46 papers                   37% reviewed >

...

────────────────────────

Today       Topics       Saved
```

---

## 14.1.1 Header

Top-left small brand:

```text
PaperFlow
```

Purple.

Below:

```text
Today
```

Large bold title.

Subtitle:

```text
Wednesday, Aug 20
```

Use current day formatting based on locale if convenient.

The Today root has no trailing Search or Settings buttons in V1. Search is local to Saved, and no Settings behavior is currently specified. Do not place inactive or speculative icons in the header.

---

# 14.2 Today's Papers Card

The most visually important element on Today Home.

Approximate height:

```text
150–180 pt
```

Contents:

### Header

```text
Today's Papers                   42 papers
```

### Progress section

Large circular progress:

```text
43%
```

Next to:

```text
18 reviewed
24 remaining
```

Do not display fake analytics.

Progress formula:

```text
reviewed / total
```

Server count and personal review count remain conceptually separate.

---

## Primary actions

Two equal width buttons:

```text
Browse
Swipe
```

Browse:

- subtle purple;
- book/list icon.

Swipe:

- subtle green or neutral;
- card/swipe icon;
- small helper text may say `Quick triage`.

Neither should look dramatically more important than the other.

The product intentionally supports both workflows.

---

# 14.3 Previous Days

Section title:

```text
Previous Days
```

Optional:

```text
See All
```

Each row:

```text
[calendar]

Tue, Aug 19
35 papers

71% reviewed        >
```

Rows should be approximately:

```text
52–60 pt high
```

Entire row tappable.

Do not require tapping the chevron.

---

## Completed days

If 100% reviewed:

show subtle:

```text
✓
```

or

```text
100% reviewed
```

in success green.

Do not remove completed days.

---

# 14.4 Day Overview

Opened after tapping a day.

Navigation title:

```text
Aug 20, 2026
```

Back returns to Today Home.

---

## Progress summary card

Display:

```text
43%

18 reviewed
24 remaining

42 papers
```

This should remain compact.

---

## Primary mode switch

Very prominent:

```text
[ Browse ]   [ Swipe ]
```

Tapping Browse pushes Day Browse.

Tapping Swipe pushes/resumes Day Swipe.

---

## Deferred Today's Focus

The generated design contains a small card such as:

```text
Today's Focus

Vision & World Models
22 papers
```

Do not implement Today's Focus in core V1. No focus-selection contract exists, and aggregate topic counts are not a recommendation. A later version may add it only with an explicit deterministic or backend-supplied selection contract.

---

## Deferred Recommended Flow helper

The concept may show:

```text
Browse first
Preview papers and find what catches your eye

↓

Swipe to triage
Quickly save or skip
```

Omit this helper from the core V1 home screen. The adjacent Browse and Swipe actions plus onboarding copy are sufficient. Do not force this workflow.

The user may:

- Browse only;
- Swipe only;
- alternate freely.

---

# 15. DAY BROWSE

Navigation:

```text
<       Aug 20, 2026                  Filter
```

Below:

```text
[ All Topics ▾ ]       [ Sort: Relevance ▾ ]

42 papers
```

---

# 15.1 Browse list behavior

Display all papers in the selected day.

Required ordering default:

```text
Relevance descending
```

Required alternative sorts:

```text
Newest
Novelty
Title
```

All sorts use title (localized case-insensitive ascending), then canonical arXiv ID ascending, as deterministic tie-breakers.

---

# 15.2 Day Browse Card

Recommended composition:

```text
┌────────────┐  DreamFlow: Scalable World
│   figure   │  Models for Embodied Agents
│            │
└────────────┘

               [World Models] [Embodied AI]

               We introduce a scalable world
               model for...

● High relevance               🔖 Saved
```

Do not show everything.

Avoid placing:

- full abstract;
- all authors;
- complete arXiv ID;
- 5 summary bullets;

inside the browse card.

Those belong in Paper Detail.

---

# 15.3 Card interaction

Tap anywhere on card:

```text
→ Paper Detail
```

Bookmark icon:

```text
unsaved → Save
saved   → Unsave only after explicit tap
```

Saving from Browse:

```text
saved = true
seen = true
readingStatus = queue
```

unless an existing later reading state needs preservation.

---

# 15.4 Reviewed visual state

Do not dramatically fade reviewed papers.

A subtle indicator is enough:

```text
✓ Reviewed
```

or small secondary label.

Paper remains fully readable.

---

# 16. SWIPE DECK

This screen is the fastest path through papers.

It should be visually much simpler than Browse.

---

# 16.1 Swipe header

```text
<       Aug 20, 2026                 Filter

18 of 42 reviewed
████████░░░░

24 remaining
```

Avoid excessive stats.

Only show:

- current progress;
- context.

---

# 16.2 Swipe Card

Large central card.

Structure:

```text
┌──────────────────────────────────┐
│                                  │
│          HERO FIGURE             │
│                                  │
├──────────────────────────────────┤
│ GeoNav: Geometry-Aware           │
│ Navigation in 3D Environments    │
│                                  │
│ [3D Vision] [Navigation]         │
│                                  │
│ Concise TL;DR / summary          │
│ ideally 2–4 lines                │
│                                  │
│ TL;DR                            │
│ Navigation via geometry-aware... │
│                                  │
│ Relevance          Novelty       │
│ ●●●●●              ●●●●○        │
└──────────────────────────────────┘
```

Target card occupies approximately:

```text
65–75% of available screen height
```

depending on phone size.

---

# 16.3 Gesture behavior

Swipe right:

```text
SAVE
```

Swipe left:

```text
SKIP
```

Do not use swipe up/down for important primary actions.

---

# 16.4 Gesture feedback

As card drags right:

- slight green tint;
- Save icon gradually appears;
- card rotates a few degrees.

As card drags left:

- slight red tint;
- Skip icon gradually appears;
- opposite rotation.

Use light haptic when threshold is crossed.

Do not exaggerate animation.

Recommended card rotation:

```text
maximum around 5–7°
```

---

# 16.5 Swipe buttons

Bottom:

```text
┌────────┐  ┌────────┐  ┌────────┐
│   X    │  │   ↶    │  │   🔖   │
│ Skip   │  │ Undo   │  │ Save   │
└────────┘  └────────┘  └────────┘
```

Buttons must invoke exactly the same commands as gestures.

### Skip

Red-soft background.

### Undo

Neutral gray.

### Save

Green-soft background.

---

# 16.6 Swipe semantics

### Swipe Left / Skip

Must:

```text
seen = true
lastSeenAt = now
```

Must not:

```text
delete paper
remove canonical history
set pipeline state to DROP
silently unsave an existing Saved paper
```

---

### Swipe Right / Save

Must:

```text
seen = true
saved = true
savedAt = now if first save
lastSavedAt = now when saved changes false → true
unsavedAt = nil when saved changes false → true
readingStatus = queue if appropriate
```

If already:

```text
reading
```

or:

```text
done
```

do not reset to:

```text
queue
```

---

# 16.7 Undo

Undo is a first-class action.

It should restore:

- previous personal state;
- card position;
- reading state if relevant.

Disable Undo if no action exists.

Do not keep unlimited undo history for V1.

One most recent action is sufficient.

---

# 16.8 Opening Paper Detail during swipe

Tapping card or an explicit detail affordance:

```text
Swipe
→ Paper Detail
```

This alone does **not** finalize the review decision.

Returning:

```text
Paper Detail
→ same card
→ same swipe session
```

unless Save or Skip was explicitly performed from detail.

---

# 16.9 Swipe completion

When no eligible papers remain:

show dedicated completion state.

---

# 17. ALL DONE SCREEN

The screen should be positive but restrained.

Do not over-gamify.

Structure:

```text
        ✓

All caught up for today!

Great work reviewing all 42 papers.

42              18              100%
Reviewed        Saved           Complete
```

Below:

```text
What's next?

Review your saved papers        >
Explore a topic                 >
```

Omit motivational quotes, confetti, and tomorrow preview in core V1. The completion checkmark, reviewed count, saved-in-collection count, and completion percentage provide sufficient feedback.

---

# 18. TOPICS TAB

Topics should feel like a structured scientific library.

Not a recommendation feed.

---

# 18.1 Topics Home

Layout:

```text
Topics

Total Papers
1,247 papers

World Models                         >
438 papers

Embodied AI                          >
312 papers

Robotics                             >
287 papers

Vision                               >
251 papers

...
```

---

# 18.2 Topic row

Each row:

```text
[icon]  World Models
        438 papers                 >
```

Height:

```text
60–68 pt
```

Icons may have subtle topic-specific colors.

Do not make the interface look rainbow-colored.

Recommended approach:

- 3–5 accent families maximum;
- recycle colors;
- muted tints.

The taxonomy source determines rows.

Never hard-code topic names into Swift UI layout.

---

# 18.3 Topics summary

At top:

```text
Total Papers
1,247 papers
```

A small Saved/Deep Read count may appear if useful:

```text
🔖 27
```

but this should not dominate the screen.

`Total Papers` is the unique canonical paper count supplied by `topics.json.total_paper_count`. Do not sum large-topic rows, because a paper may belong to more than one topic.

---

# 19. LARGE TOPIC DETAIL

Example:

```text
World Models
438 papers
```

Optional centered topic icon.

Then:

```text
All papers in this topic          438 >
```

---

## Subtopics

```text
Subtopics

Video World Models               196 >
3D World Models                  102 >
World Model Architectures         66 >
Planning with World Models        72 >
Surveys & Benchmarks              22 >
```

Entire row tappable.

---

# 19.1 Topic quick actions

Bottom or after subtopic list:

```text
[ Browse All ]    [ Swipe Unread ]
```

Browse All:

```text
→ Large Topic History/Browse
```

Swipe Unread:

```text
→ Swipe deck scoped to this Large Topic
```

Only globally unreviewed papers should appear by default.

---

# 20. SUBTOPIC BROWSE

Header:

```text
Video World Models
196 papers
```

Filter segmented control:

```text
All Papers | Unread 27 | Saved
```

Below:

```text
Sort: Relevance ▾       Filters
```

Then standard paper cards.

---

# 20.1 Filtering

### All Papers

Every paper belonging to this subtopic.

### Unread

Papers:

```text
seen == false
```

### Saved

Papers:

```text
saved == true
```

within the current public subtopic membership.

---

# 20.2 History

Topic and subtopic views must preserve historical access.

A user should be able to scroll/load:

```text
Aug 20
Aug 19
Aug 18
...
```

indefinitely according to server history.

Do not limit the UI to newest 80 papers.

---

# 21. SUBTOPIC SWIPE

Same component and logic as Day Swipe.

Only collection context changes.

Header:

```text
Video World Models
```

Progress:

```text
169 of 196 reviewed
27 remaining
```

Deck should default to globally unreviewed papers within that collection.

Because review state is global, a paper already reviewed from Today should not reappear as unread here.

---

# 22. DEFERRED SUBTOPIC OVERVIEW

The generated final board contains an Overview page. Do not implement it in core V1.

It may show:

```text
196 Total
27 Unread
42 Saved
```

plus:

```text
Top Papers
Recent Activity
```

If later specified with real aggregate/event data, its priority remains:

```text
1. Browse
2. Swipe
3. History
4. Overview analytics
```

The app does not need analytics to be useful.

---

# 23. SAVED TAB

Saved should feel calmer than discovery screens.

The user is no longer triaging.

They have intentionally chosen these papers.

The visual atmosphere should support:

```text
focus
organization
continuation
completion
```

---

# 23.1 Saved Home

Header:

```text
PaperFlow

Saved
Your deep-read queue and progress.
```

---

## Status summary

Three columns:

```text
Queue            Reading            Done
40               18                 20

Papers to read   In progress        Completed
```

Each entire column tappable.

Use:

- purple/blue for Queue;
- purple/amber or primary for Reading;
- green for Done.

Keep styling subtle.

---

# 23.2 Saved status selector

Below:

```text
[ Queue ] [ Reading ] [ Done ]
```

This can either:

- navigate to dedicated pages;
- filter within Saved.

For simplicity, implementation may use navigation destinations while preserving identical visual behavior.

---

# 23.3 Deferred Recent Activity

Do not implement Recent Activity in core V1 because the personal model stores current transition timestamps, not an append-only activity log.

Example:

```text
Recent Activity                         See All

Continued reading
Scaling Laws for Neural Language Models
Today, 9:28 AM

Marked as done
MoLeR: Mixture-of-Experts...
Yesterday, 6:40 PM

Added to queue
Retrieval-Augmented Generation...
Yesterday, 2:12 PM
```

A later version may add it only with an explicit append-only personal activity-event contract. Never reconstruct or fabricate a history from current-state timestamps.

---

# 23.4 Remove unsupported quick actions

The generated concept shows:

```text
Import from arXiv
Add from Topics
```

These are not required by the current core PaperFlow workflow.

Do **not** implement them automatically.

The essential way to enter Saved is:

```text
Save from Today
Save from Topics
Save from Paper Detail
```

---

# 24. QUEUE SCREEN

Header:

```text
<    Queue
     40 papers                    Search Filter
```

Sort:

```text
Recently Saved ▾
```

---

# 24.1 Queue paper row

Example:

```text
[figure] RAG-MoE: Mixture-of-Experts
         Retrieval for Scalable Knowledge...

         Zhang et al.

         [LLM] [RAG] [MoE]

         Saved Aug 20, 2026             🔖
```

The displayed Saved date is the most recent Save membership date (`last_saved_at`). The first-ever `saved_at` remains available for the Oldest Saved sort.

Do not display daily relevance labels unnecessarily here unless useful.

Queue prioritizes:

- paper identity;
- subject;
- when saved.

---

# 24.2 Swipe actions in Saved lists

Optional native row swipe:

Swipe left may reveal:

```text
Remove
```

or:

```text
Mark Reading
```

Do not overload with many actions.

Prefer context menu for secondary actions.

---

# 25. READING SCREEN

Header:

```text
Reading
18 in progress
```

Sort default:

```text
Last Opened
```

`Last Opened` is backed by the personal `last_opened_at` timestamp. If it is absent, fall back to the most recent reading-status transition, then most recent Save.

---

# 25.1 Continue Reading

The first item may be elevated:

```text
Continue Reading

[figure]

Scaling Laws for Neural Language Models

██████████████░░░     65%

Last opened Today, 9:41 AM
```

Only display percentage if PaperFlow actually tracks a meaningful reading progress measurement.

If PDF reading progress is not implemented, do not invent percentages.

Instead use:

```text
Last opened...
```

and state:

```text
Reading
```

---

# 25.2 All In Progress

Standard rows:

```text
[figure] Paper title
         Authors
         Last opened Aug 20, 4:12 PM
```

Tap:

```text
→ Paper Detail
```

---

# 26. DONE SCREEN

Header:

```text
Done
20 completed
```

Sort:

```text
Recently Completed
```

`Recently Completed` is backed by the personal `completed_at` timestamp.

Each row:

```text
[figure] Paper title
         Authors
         [tags]

         Completed Aug 18, 2026       ✓
```

Use subtle green success icon.

Do not reduce opacity dramatically.

Completed papers should remain readable and useful.

---

# 27. PAPER DETAIL

Paper Detail is shared across:

- Today Browse;
- Day Swipe;
- Topic Browse;
- Topic Swipe;
- Saved Queue;
- Reading;
- Done.

Create **one shared PaperDetailView**.

Do not create multiple detail implementations.

When a currently saved paper's detail becomes visible, update `last_opened_at` once for that presentation. Open arXiv and Open PDF also update it. Opening an unsaved paper's detail does not create a last-opened timestamp, and rendering a card never updates it.

---

# 27.1 Detail structure

Recommended order:

```text
Navigation

Figure

Paper Title

Authors
arXiv ID

Topic Tags

Relevance / Novelty

TL;DR

Key Points

Abstract

Why Selected

Personal State
  Reading Status
  Notes
  Rating

External Actions
  Open arXiv
  Open PDF
  Share
```

Some sections may be collapsed by default.

---

# 27.2 Hero figure

Width:

```text
full content width
```

Target height:

```text
180–240 pt
```

depending on aspect ratio.

Use:

```text
aspectFit
```

for scientific figures.

Never crop important diagrams aggressively.

If no figure:

show placeholder of identical approximate layout height.

---

# 27.3 Title area

Example:

```text
Scaling Laws for Neural
Language Models
```

Below:

```text
Hoffmann et al.
arXiv:2001.08361
```

Do not overemphasize arXiv ID.

---

# 27.4 Topic tags

```text
[LLM] [Scaling Laws] [Compute] [+1]
```

Tapping a topic pill may optionally navigate to topic/subtopic later.

Not required for core V1.

---

# 27.5 Relevance and Novelty

Prefer compact two-column cards:

```text
Relevance           Novelty
High                High
```

or numeric:

```text
Relevance
9 / 10

Novelty
8 / 10
```

Use actual backend values.

Do not convert numeric values to labels inconsistently.

Recommended mapping if labels are desired:

```text
1–3   Low
4–6   Moderate
7–8   High
9–10  Very High
```

But numeric display is more transparent.

---

# 27.6 TL;DR

Section:

```text
TL;DR
```

Content should be prominent.

Recommended:

```text
15–16 pt
regular
comfortable line spacing
```

This is the first textual section users should read.

---

# 27.7 Key Points

Show summary bullets:

```text
Key Points

• ...
• ...
• ...
```

Prefer 3–5 bullets.

Do not visually render each bullet as an enormous card.

A clean list is sufficient.

---

# 27.8 Abstract

Initially collapsed if long.

```text
Abstract                         Show More
```

Expanded:

display complete abstract.

If summary generation fails:

abstract becomes the primary content fallback.

---

# 27.9 Why Selected

Optional expandable section:

```text
Why Selected
```

Uses selection reason from backend.

Good for answering:

> Why did PaperFlow think this was relevant to me?

---

# 28. PERSONAL DEEP-READ CONTROLS

Only Saved papers need prominent personal management.

If unsaved:

show:

```text
Save for Deep Read
```

After saving:

show reading status.

---

# 28.1 Reading status

Segmented control:

```text
Queue | Reading | Done
```

Transitions are immediate local updates.

Do not require network availability.

---

# 28.2 Notes

Section:

```text
Notes
```

If empty:

```text
Add a note...
```

Tap opens either:

- inline editor;
- sheet editor.

Prefer sheet/full editor for long notes.

Autosave locally.

Do not use a separate Save button unless technically required.

---

# 28.3 Rating

Section:

```text
My Rating

☆ ☆ ☆ ☆ ☆
```

Tap star:

```text
1–5
```

Tap same selected rating again does not need to clear.

Provide explicit:

```text
Remove rating
```

through context/menu if necessary.

Rating optional.

---

# 29. EXTERNAL ACTIONS

At bottom of Paper Detail:

```text
[ Open arXiv ]     [ Open PDF ]
```

Open PDF should be visually slightly stronger if reading is the likely next action.

Use native browser/Safari behavior unless an in-app PDF reader is explicitly implemented.

Share:

top navigation action or compact tertiary action.

---

# 30. PAPER DETAIL WHEN OPENED FROM SWIPE

This context is special.

If user enters:

```text
Swipe → Detail
```

the detail page should provide triage actions.

Bottom sticky bar:

```text
Skip                        Save
```

Optional:

```text
Back
```

Navigation Back does not count as a decision.

### Save

Equivalent to Swipe Right.

### Skip

Equivalent to Swipe Left.

After action:

```text
return to swipe deck
advance to next card
```

---

# 31. SEARCH

V1 must support Saved search.

Search should query local Saved metadata:

- title;
- authors;
- displayed summary text (TL;DR or abstract fallback);
- topic names;
- subtopic names;
- notes.

Matching is case- and diacritic-insensitive localized substring matching. Search operates entirely on Saved snapshots/personal data and works offline.

Use native:

```swift
.searchable(...)
```

where appropriate.

Do not build a custom oversized search UI unless necessary.

Search is not shown in the Today or Topics root headers in V1. There is no V1 Settings button because no settings behavior is specified. Global/current-cache search and Settings require a later explicit product specification.

---

# 32. SORTING

Use native menus.

Example:

```text
Sort: Recently Saved ▾
```

Queue:

```text
Recently Saved
Oldest Saved
Relevance
Novelty
Title
```

`Recently Saved` uses `last_saved_at`; `Oldest Saved` uses the first-ever `saved_at`.

Reading:

```text
Last Opened
Recently Saved
Title
```

Done:

```text
Recently Completed
Oldest Completed
Title
```

Browse:

```text
Relevance
Novelty
Newest
Title
```

Sort semantics:

```text
Relevance           relevance DESC
Novelty             novelty DESC
Newest              first_seen_at DESC
Title               localized case-insensitive ASC
Recently Saved      last_saved_at DESC
Oldest Saved        saved_at ASC
Last Opened         last_opened_at DESC, then status change, then last Save
Recently Completed  completed_at DESC
Oldest Completed    completed_at ASC
```

Every sort uses title, then canonical arXiv ID, as deterministic tie-breakers after the listed keys.

---

# 33. FILTERS

Filters should appear in a sheet rather than consume permanent screen space.

Example:

```text
Filters

Topics
[✓] World Models
[ ] Robotics

Status
[✓] Unread
[ ] Reviewed

[Reset]                     [Apply]
```

Required V1 filters:

- Day Browse: dynamic Large Topic multi-select plus `All`, `Unread`, `Reviewed`, or `Saved` status.
- Large Topic Browse: dynamic Subtopic multi-select plus the same status choices.
- Subtopic Browse: the existing `All Papers`, `Unread`, and `Saved` segmented choices. `Reviewed` is available through the filter sheet if needed.
- Swipe: `Unreviewed` (default) or `All Papers / Review Again`; Day and Large Topic Swipe may also apply the same dynamic topic/subtopic selection as Browse.

Do not implement relevance/novelty threshold filters in core V1. The scores remain sort keys and Detail metadata.

For progress, the active collection is the public membership after topic/subtopic filters and before the personal `Unreviewed`/`All Papers` mode is applied. Therefore:

```text
total = active filtered public membership
reviewed = seen papers within that membership
remaining = total - reviewed
```

Reset restores the unfiltered public collection, default sort, and default status/review mode. Apply changes the current view/session deterministically and never changes personal state by itself.

---

# 34. LOADING STATES

Never show a completely blank screen during loading.

Use skeleton placeholders.

Example paper skeleton:

```text
████████      ███████████████
████████      █████████████
████████      ███████

              ████ ████
              █████████████
```

Animate gently.

No strong shimmering necessary.

---

# 35. EMPTY STATES

Every empty state should explain:

1. what happened;
2. whether user action is required.

---

## Today — zero matching papers

```text
No papers matched your research interests today.

Check previous days or explore Topics.
```

Actions:

```text
Browse Topics
```

---

## Swipe — complete

Use All Done screen.

---

## Saved — empty

```text
Nothing saved yet.

Swipe right or tap Save on a paper you want to read later.
```

Action:

```text
Explore Today
```

---

## Queue empty

```text
Your queue is clear.

Saved papers marked for later reading will appear here.
```

---

## Reading empty

```text
Nothing in progress.

Move a saved paper to Reading when you start digging in.
```

---

## Done empty

```text
No completed papers yet.
```

---

# 36. ERROR STATES

Errors should be contextual.

Do not replace cached content with a global error screen.

Example:

```text
Couldn't refresh PaperFlow.

Showing your latest downloaded data.

Last updated 9:41 AM.
```

Action:

```text
Try Again
```

---

# 37. OFFLINE MODE

If cached content exists:

continue displaying it.

Add a subtle status label only when useful:

```text
Offline · Last updated 9:41 AM
```

All personal actions continue to work:

- Save;
- Skip;
- Unsave;
- Queue → Reading;
- Reading → Done;
- notes;
- ratings.

Never disable these simply because public refresh failed.

---

# 38. PULL TO REFRESH

Supported on:

- Today;
- Topics;
- day lists;
- topic history where appropriate.

Use native pull-to-refresh.

On success:

small haptic or subtle refresh state.

Do not display large success banners.

---

# 39. HAPTICS

Use sparingly.

### Save

Light success impact.

### Skip

Light impact.

### Swipe threshold

Very subtle impact.

### Done

Success feedback.

Do not generate haptic feedback while simply scrolling or selecting filters.

---

# 40. ANIMATION

Animations should communicate state, not decorate.

Recommended duration:

```text
0.18–0.30 seconds
```

Use native spring when appropriate.

Examples:

### Save

Bookmark fills smoothly.

### Swipe

Card translates + slight rotation.

Next card moves slightly forward.

### Progress

Progress bar animates after action.

### Tab switching

Native TabView behavior.

Avoid:

- bouncing every card;
- exaggerated spring animations;
- particles;
- constant gradients.

---

# 41. SWIPE DECK STACK

Only visually show:

```text
current card
+ perhaps 1–2 cards underneath
```

Under cards should:

- be slightly scaled;
- vertically offset 4–8 pt;
- not expose meaningful content.

This suggests continuity without creating visual noise.

---

# 42. SAFE AREAS

Respect:

- Dynamic Island;
- bottom home indicator;
- landscape safe areas if supported.

Do not manually hard-code top values based on one iPhone model.

Use:

```text
safeAreaInset
safeAreaPadding
```

where appropriate.

---

# 43. TAP TARGETS

Minimum interactive region:

```text
44 × 44 pt
```

Even tiny visual icons should receive enlarged invisible hit areas.

Especially:

- bookmark;
- filter;
- search;
- overflow;
- back;
- rating stars.

---

# 44. ACCESSIBILITY

Support Dynamic Type where practical.

At larger font sizes:

- allow paper titles to grow vertically;
- allow cards to become taller;
- do not truncate critical content;
- horizontal button groups may stack.

Do not use color alone for status.

Example:

Saved should use:

```text
bookmark icon + Saved text
```

not only purple color.

Provide accessibility labels such as:

```text
"Save paper"
"Skip paper"
"Undo previous review action"
"18 of 42 papers reviewed"
```

---

# 45. DARK MODE

Architecture should support semantic colors.

Even if V1 launches visually optimized for light mode, avoid literal colors that make dark-mode migration difficult.

If dark mode is implemented:

- background nearly black, not pure black everywhere;
- cards slightly lighter;
- purple accent retained;
- figures remain visually intact.

---

# 46. COMPONENT ARCHITECTURE

The coding agent should strongly prefer reusable components.

Suggested SwiftUI component hierarchy:

```text
PaperFlowApp

RootTabView
├── TodayNavigationStack
├── TopicsNavigationStack
└── SavedNavigationStack
```

Reusable visual components:

```text
PFNavigationHeader
PFSectionHeader
PFProgressRing
PFProgressBar
PFPrimaryButton
PFSecondaryButton
PFActionButton
PFTag
PFStatCard
PFPaperThumbnail
PFPaperListCard
PFSavedPaperRow
PFReadingPaperRow
PFSwipeCard
PFSwipeActionBar
PFEmptyState
PFErrorBanner
PFLoadingSkeleton
PFReadingStatusPicker
PFRatingControl
PFFigureView
```

Avoid giant screen files with duplicated styling.

---

# 47. RECOMMENDED VIEW STRUCTURE

```text
Views/
│
├── Root/
│   └── RootTabView.swift
│
├── Today/
│   ├── TodayHomeView.swift
│   ├── DayOverviewView.swift
│   ├── DayBrowseView.swift
│   ├── DaySwipeView.swift
│   └── TriageCompleteView.swift
│
├── Topics/
│   ├── TopicsHomeView.swift
│   ├── TopicDetailView.swift
│   ├── TopicBrowseView.swift
│   ├── SubtopicBrowseView.swift
│   └── TopicSwipeView.swift
│
├── Saved/
│   ├── SavedHomeView.swift
│   ├── QueueView.swift
│   ├── ReadingView.swift
│   └── DoneView.swift
│
├── Paper/
│   ├── PaperDetailView.swift
│   ├── PaperSummarySection.swift
│   ├── PaperMetadataSection.swift
│   ├── PaperPersonalStateSection.swift
│   └── PaperExternalActions.swift
│
└── Components/
    ├── PaperListCard.swift
    ├── PaperThumbnail.swift
    ├── TopicTag.swift
    ├── SwipeCard.swift
    ├── ProgressRing.swift
    ├── EmptyState.swift
    └── ...
```

---

# 48. DESIGN TOKENS

Create one central theme layer.

Example conceptual structure:

```text
PaperFlowTheme

Colors
Typography
Spacing
Radius
Shadow
Animation
```

Never place values such as:

```text
.cornerRadius(13)
.padding(.horizontal, 17)
Color(red: ...)
```

randomly throughout the app.

Use reusable constants.

---

# 49. SCROLL BEHAVIOR

Use native vertical scrolling.

Top navigation controls may become compact while scrolling.

Do not make multiple nested vertical scroll views.

For large paper histories:

use lazy structures:

```text
LazyVStack
```

Do not render thousands of paper rows eagerly.

---

# 50. IMAGE LOADING

Scientific figures may arrive remotely.

Implement:

```text
placeholder
→ loading
→ loaded
→ failed fallback
```

Cache images where appropriate.

Prevent layout jumps when image loads.

Use known frame/aspect ratio placeholders.

---

# 51. DATA-TO-UI RULES

Never create separate personal copies of canonical paper identity.

A paper is identified by canonical versionless arXiv ID.

Example:

```text
2608.12345v1
2608.12345v2
```

map to:

```text
2608.12345
```

Therefore:

```text
one paper
one seen state
one Saved state
one reading state
one note
one rating
```

across Today, Topics, and Saved.

---

# 52. CROSS-TAB CONSISTENCY

Example:

User saves paper from:

```text
Today → Swipe
```

Immediately:

```text
Today Browse → Saved
Topics Browse → Saved
Saved Queue → paper appears
Paper Detail → Saved
```

All views must update from the same local personal state.

No manual refresh should be required.

---

# 53. REVIEW CONSISTENCY

Example:

Paper appears in:

```text
Aug 20
World Models
Video World Models
Spatial Intelligence
```

If user skips it from Today:

```text
seen = true
```

Then default Swipe decks under those topics should no longer treat it as unread.

Browse still displays it.

---

# 54. SAVE CONSISTENCY

If paper is saved once:

do not create duplicates.

Saving again should be idempotent.

If state is already:

```text
Reading
```

another Save action must not reset to:

```text
Queue
```

Likewise:

```text
Done
```

must remain Done unless explicitly changed.

---

# 55. UNSAVE CONSISTENCY

Unsave removes paper from Saved.

It does **not** automatically set:

```text
seen = false
```

The paper may remain reviewed.

It also remains in all canonical public history views.

Unsave is non-destructive to personal history:

```text
saved = false
unsavedAt = now
```

It preserves:

- first and most recent Save timestamps;
- reading status and status timestamps;
- last-opened timestamp;
- notes;
- rating;
- offline saved-paper snapshot.

Saving the paper again sets `lastSavedAt = now`, clears `unsavedAt`, and restores the preserved reading state rather than resetting Reading/Done to Queue. Only a separately specified permanent personal-data reset may delete that retained history.

---

# 56. TODAY DAILY WORKFLOW

Ideal everyday interaction:

```text
Open PaperFlow
      ↓
Today
      ↓
42 papers
18 reviewed
24 remaining
      ↓
choose
 ┌──────────────┐
 │              │
Browse         Swipe
 │              │
Inspect         Triage
 │              │
Save interesting papers
      ↓
Saved Queue
      ↓
Read later
```

The UI should make this workflow self-explanatory without tutorials.

---

# 57. TOPIC DISCOVERY WORKFLOW

```text
Topics
   ↓
World Models
   ↓
Video World Models
   ↓
Browse history
      or
Swipe unread
   ↓
Save interesting papers
   ↓
Saved
```

---

# 58. DEEP READ WORKFLOW

```text
Save
  ↓
Queue
  ↓
Reading
  ↓
Done
```

At any point:

```text
Paper Detail
→ Notes
→ Rating
→ PDF
```

This is the core personal knowledge lifecycle.

---

# 59. WHAT NOT TO IMPLEMENT

Do not add simply because it might look sophisticated:

- social feeds;
- likes;
- comments;
- followers;
- badges;
- leaderboards;
- excessive streak mechanics;
- recommendation carousels;
- AI chat on every screen;
- giant analytics dashboard;
- unnecessary floating action buttons;
- fourth navigation tab;
- redundant Feed tab;
- separate Swipe tab;
- mandatory global search tab;
- nested topic hierarchy beyond the configured two levels.

---

# 60. REMOVE OVERLY GAMIFIED ELEMENTS

The generated Today design contains:

```text
Streak
All-time days
motivational quote
confetti
```

These are visual exploration ideas, not required core UI.

For the production app:

### Keep

- clear completion checkmark;
- progress percentage;
- reviewed count.

### Avoid initially

- streak counter;
- all-time day count;
- inspirational quote;
- heavy confetti.

PaperFlow should feel rewarding because the work is complete, not because the user is collecting points.

---

# 61. RESPONSIVE PRIORITY

For narrow screens, information priority is:

```text
1. Paper title
2. TL;DR
3. Figure
4. Save/review state
5. Topic tags
6. Relevance / novelty
7. Date
8. Authors
```

When space becomes limited, remove/lower-priority metadata before shrinking important text.

---

# 62. DEFERRED FIRST-LAUNCH EXPERIENCE

Core V1 opens directly to Today and requires no account or onboarding flow. The three-tab structure, Browse/Swipe actions, and empty-state guidance must be understandable without a tutorial.

If onboarding is explicitly added later, keep it extremely short.

Potential 3-screen onboarding:

### Screen 1

```text
Your daily research radar
```

### Screen 2

```text
Browse or swipe
```

### Screen 3

```text
Save papers for deep reading
```

Then:

```text
Get Started
```

Do not require an account for local V1 functionality if architecture permits.

---

# 63. NAVIGATION MAP

Final map:

```text
ROOT
│
├── TODAY
│   │
│   ├── Today Home
│   │
│   └── Day Overview
│       │
│       ├── Day Browse
│       │   └── Paper Detail
│       │
│       └── Day Swipe
│           └── Paper Detail
│
├── TOPICS
│   │
│   └── Topics Home
│       │
│       └── Large Topic
│           │
│           ├── Browse All
│           │   └── Paper Detail
│           │
│           ├── Swipe Unread
│           │   └── Paper Detail
│           │
│           └── Subtopic
│               │
│               ├── Browse
│               │   └── Paper Detail
│               │
│               └── Swipe
│                   └── Paper Detail
│
└── SAVED
    │
    ├── Saved Home
    │
    ├── Queue
    │   └── Paper Detail
    │
    ├── Reading
    │   └── Paper Detail
    │
    └── Done
        └── Paper Detail
```

---

# 64. INITIAL IMPLEMENTATION PRIORITY

The coding agent should implement in this order.

## UI Foundation

1. Theme/design tokens
2. Root TabView
3. reusable Paper Card
4. reusable tags
5. reusable figure placeholder
6. reusable progress components

---

## Today

7. Today Home
8. Day Overview
9. Browse
10. Paper Detail
11. Swipe
12. Undo
13. completion screen

---

## Topics

14. Topics Home
15. Large Topic Detail
16. Subtopic Browse
17. Topic/Subtopic Swipe

---

## Saved

18. Saved Home
19. Queue
20. Reading
21. Done
22. Reading status
23. Notes
24. Rating

---

## Polish

25. loading states
26. empty states
27. error/offline states
28. animations
29. haptics
30. accessibility
31. navigation-state restoration

---

# 65. VISUAL ACCEPTANCE CRITERIA

Before considering the UI complete, verify:

- Today / Topics / Saved are the only permanent bottom tabs.
- Today and Topics have no speculative Search or Settings icons.
- Main screens use approximately 16 pt horizontal padding consistently.
- Titles remain easily readable.
- No paper list requires tiny text.
- Browse cards show enough information to make a quick decision.
- Swipe cards contain significantly less information than full Paper Detail.
- Save is represented consistently everywhere.
- Topic pills use one reusable visual component.
- Figures use one consistent display/placeholder system.
- Purple is used as accent, not as the background of the whole application.
- Cards use subtle separation instead of heavy shadows.
- Bottom navigation looks native.
- Every primary button has at least a 44 pt touch area.
- No screen looks like an analytics dashboard.
- No screen contains unnecessary decorative information.
- Long titles and Dynamic Type do not break layouts.

---

# 66. FUNCTIONAL ACCEPTANCE CRITERIA

Verify:

- Today displays exact paper count.
- Today uses the current local date; an older successful feed is labeled Latest Available.
- Only a published current-day zero count uses the zero-matching empty state.
- Reviewed count updates immediately.
- Browse does not mark visible cards reviewed.
- Save from Browse marks paper saved/reviewed.
- Swipe Left marks reviewed but not Saved.
- Swipe Right marks reviewed + Saved.
- Save is idempotent.
- Existing Reading/Done state is preserved.
- Undo restores exact previous personal state.
- Swipe session resumes.
- Topic swipe uses global seen state.
- Saved contains each canonical paper at most once.
- Queue/Reading/Done persist.
- Reading uses real `last_opened_at`; Done uses real `completed_at`.
- Notes persist.
- Rating persists.
- Unsave retains personal history/snapshot and resave restores the prior reading state.
- Personal actions work offline.
- Public refresh failure does not destroy local personal state.
- Saved paper remains usable even if old public feed cache is unavailable.
- Paper Detail opened from Swipe returns to the same swipe session.
- Opening Detail alone does not finalize a swipe decision.

---

# 67. FINAL PRODUCT CHARACTER

When implementation is finished, PaperFlow should feel like this:

### Today

> “Show me what matters today.”

### Browse

> “Let me scan quickly.”

### Swipe

> “Let me decide quickly.”

### Topics

> “Let me explore my research space.”

### Saved / Queue

> “These are worth my time.”

### Reading

> “These are what I am actively studying.”

### Done

> “These are papers I have finished.”

### Paper Detail

> “Give me enough information to understand, decide, and continue reading.”

The application should never feel complicated despite potentially containing thousands of papers.

The interface should consistently hide system complexity behind a very simple user mental model:

**Today → Decide → Save → Read → Done.**

That simplicity is the primary design requirement.
