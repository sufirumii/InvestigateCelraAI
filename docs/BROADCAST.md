# Broadcast mode

**Initiate slideshow** on the front page opens a full-screen, auto-advancing
run through the edition. It is built for a wall display or the front of a room.

Everything on screen comes from the same `/api/edition` payload the front page
uses. The running order *is* the signal ranking — lead story first, then
features, then briefs, deduplicated. Nothing is curated for the slideshow and
nothing is written for it.

## What each slide shows

| Region | Content |
|---|---|
| Lower third | Event class, therapy area, trial phase — coloured by signal band |
| Headline | The story title, after backronym casing repair |
| Standfirst | The extractive summary |
| Attribution | Company, source, age, corroborating outlet count |
| Right rail | Signal score and band, the next four stories, the story's own stated limitation, and the matched Excelra capability |

The limitation and Excelra blocks are fetched per slide from `/api/items/{id}`
and appear a beat after the headline. If that request fails the run continues —
a slide missing its detail is not worth stopping a broadcast for.

## Controls

| Key | Action |
|---|---|
| Space | Pause / resume |
| ← → | Previous / next story |
| F | Full screen |
| Enter | Leave and open the current story in the reader |
| Esc | Leave |

The same actions are on the control bar. Each story dwells ten seconds, shown by its segment filling in the rundown
strip along the top; the Pause button turns amber while paused. The momentum tape along
the bottom carries every tracked company and loops continuously.

## Nothing scrolls

Broadcast is unattended — it advances itself and nobody is at the keyboard, so
no region may need scrolling to be read. Both columns clip, and the long text
inside them is line-clamped to a length that fits at every supported height:
headline and standfirst to four lines, the limitation quote and the Excelra
paragraph to five, queued headlines to two.

The page behind the overlay is also locked. The desk is several thousand pixels
tall and stayed scrollable underneath, which put a scrollbar down the right of
the slideshow; an `overlay-open` class on `<html>` suppresses it and is removed
on exit. The same lock covers the sign-in and configuration screens.

## Notes

- The clock is live, so a screenshot of the display is self-dating.
- Below 1080px the right rail is dropped and the slide takes the full width.
- `prefers-reduced-motion` disables the slide transition and the tape scroll;
  advancing still works.
