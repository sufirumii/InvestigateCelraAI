# Sign-in and personalisation

## What happens on first open

1. **Splash**, held for a minimum of four seconds. It is a floor, not a fixed
   delay — if the API took longer than that, the wait has already elapsed and
   the desk continues immediately.
2. **Five sign-in steps**: name, remit, therapy areas, event priorities,
   companies.
3. **Configuration playback**, four seconds, listing what was actually applied.
4. **The desk**.

Steps 2 to 5 appear only until preferences have been set. After that the
splash goes straight to the front page, and priorities are changed from
**Adjust priorities** in the left rail.

## Every option comes from the corpus

`GET /api/preferences` returns both the stored preferences and the
vocabularies to choose from. Therapy areas are the sectors the pipeline
actually detected, with live story counts. Event classes are the taxonomy from
`lexicons.py`. Companies are the entities the corpus contains, ordered by how
many stories mention them, each with its real ticker from the gazetteer.

The sign-in screen therefore cannot offer a therapy area or a company that
does not exist in the data currently loaded. If the first fetch is still
running, those steps say so and can be skipped.

## Preferences shift the ranking; they do not filter

This is the important design decision. A chosen therapy area does not hide the
others — it raises its own. An analyst who stops seeing adjacent areas stops
noticing threats, which is the opposite of what a competitive intelligence
desk is for.

Mechanically, the choices feed a `preference_fit` term into the **portfolio**
component of the signal score:

```
preference_fit = (0.40·sector_match + 0.35·event_match + 0.25·company_match)
                 ÷ (sum of the weights actually stated)

portfolio = min(1, 0.45·on_watchlist + 0.30·relevance + 0.35·preference_fit)
```

Three properties, each pinned by a test:

- **An unconfigured desk is unchanged.** `fit` returns a neutral 0.5, so the
  baseline ordering is exactly what it was before this feature existed and any
  movement is attributable to a stated choice.
- **Unstated dimensions are ignored, not penalised.** Choosing only a therapy
  area divides by that weight alone, so a story is never punished on an axis
  the analyst never mentioned.
- **A preference cannot dominate.** Portfolio is one of six components and
  carries 0.10 of the total. A preference match alone scores lower than a
  watchlisted, highly relevant story.

Companies chosen at sign-in are mirrored onto the watchlist, so the two stay in
step rather than drifting apart.

## Storage

A single JSON blob in the `meta` table, written by `POST /api/preferences`,
which also re-ranks the corpus before returning. The response carries the
statements the configuration screen plays back, so what the analyst reads is
generated from what was applied rather than written in the frontend.
