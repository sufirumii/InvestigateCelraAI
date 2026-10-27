# Working with the knowledge graph

## Four layouts

Each is a pure function from the node list to positions. No coordinates are
stored, nothing is hand-placed, and all geometry derives from node count and
degree — the same code lays out twelve nodes or four hundred.

| Layout | What it is good for |
|---|---|
| **Force** | Finding clusters. Velocity Verlet with repulsion, springs, centring and a light same-kind pull. |
| **Radial** | Comparing entity types. Concentric rings, each sized to seat its own members at a comfortable arc spacing. |
| **Arc** | Reading relationships along one axis, grouped by type, edges drawn as arcs. |
| **Columns** | The readable fallback. One column per type, ranked by connections. |

The force layout starts from a phyllotaxis spiral rather than random
positions, so the same graph lands the same way every time. Random seeding
would move the picture on every render, which is disorienting when you are
trying to point at something in a meeting.

## Reading it

- **Disc size** is how many stories the entity appears in.
- **Colour** is the entity type; the legend toggles each type on and off.
- **Hover** does two things at once. A card appears at the cursor with the
  entity's name, type, link and story counts, its relationship types, and the
  first few things it connects to — so you read the detail where your eye
  already is instead of tracking to the side panel. At the same time the
  neighbourhood is isolated: neighbours keep full opacity, their edges thicken
  and turn violet, and everything else dims to 30% rather than disappearing, so
  you keep your bearings in the wider graph.
- The card flips to the other side of the cursor near an edge so it is never
  clipped, and it is keyboard-reachable — tabbing to a node shows it too.
- **Labels** are placed greedily, biggest nodes first, and a label is drawn
  only if its box clears every label already placed. Nothing overlaps, and the
  most connected entities always keep theirs.

## Controls

| Action | How |
|---|---|
| Pan | Drag the background |
| Zoom | Scroll, or the − / + buttons. Zoom follows the cursor. |
| Reposition a node | Drag it |
| Widen around a node | Double-click it |
| Widen or narrow the neighbourhood | **Expand** / **Contract** (depth 1–5) |
| Clear the focus | **Whole graph** |
| Reset pan and zoom | **Reset** |
| Full window | **Open in new tab** |

Keyboard: every node is focusable, Enter or Space selects.

## The separate window

**Open in new tab** launches `/graph.html` with the current focus, depth,
limit, layout and hidden types in the query string, so the new window opens on
exactly what you were looking at. It uses the same renderer and the same API —
it only supplies a bigger stage and a wider detail panel. The URL is
shareable.

## Honest counts

The toolbar reads, for example, `26 of 214 entities · 44 links · depth 2`. The
first number is what is on screen; the second is the whole graph. A focused
view is a neighbourhood, not the entire dataset, and the toolbar says so
rather than letting the smaller number pass as the total.

## Export

**Export Cypher** emits the whole graph as `MERGE` statements that load into
Neo4j unchanged.
