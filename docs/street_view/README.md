# Street View survey of Caversham

Kept for later review. The text files (views.tsv, result.json, notes.md per section) are in git under
docs/street_view/; the screenshots (img/) are only in .downloads/ref/sv/, which git ignores (about 30 MB).

One folder per section of town (and part of a section, `_a`, `_b`, ...), each surveyed by one helper:

- `views.tsv`: street, view id (`<point>_<heading>`), Google Street View URL. Points are spread along the
  street's mapped centre line; each point is looked at 60 degrees either side of the road's direction.
- `img/<street>__<view>.jpg`: the screenshot of that view as the helper saw it (missing where it never loaded).
- `result.json`: per street, the helper's estimate from all its views (see below).
- `notes.md`: anything the helper noticed that doesn't fit the fields.

Fields in `result.json` (shares are fractions of the houses seen, summing to 1):
walls {red_brick, orange_brick, buff_brick, grey_brick, white_render, cream_render, pebbledash, tile_hung, timber},
upper_differs + upper (an upper floor in a different finish), tudor (mock-Tudor share), roof {red_tile, dark_tile,
brown_tile, grey_tile, slate}, bungalows, form {detached, semi, terrace, flats}, era, front (hedge, low_brick_wall,
fence, open, mixed), trees, road (free text: centre line, humps, width...), shops (town streets: fascia colours,
storeys over the shops), confidence (high/medium/low/none), note.

The Caversham Heights survey (2026-11-18, same fields, no screenshots kept) is in docs/heights_survey.json.
tools/styles.py merges every `result.json` here plus that file into docs/street_styles.json.
