# Notes

Survey 2026-11-19 (tab-10, then tab-14): 58 views saved for Peppard Road, Mayfield Drive, Lowfield Road, Kingsway, Galsworthy Drive, Chiltern Road.
From Grosvenor Road 0_138 on, every page came up blank white: the pane blocked Google Maps' JS/CSS with net::ERR_BLOCKED_BY_CLIENT.
Retried after 30 s, in a fresh tab, and again after 60 s; still blocked, so I stopped.
Views never loaded (72): all of Grosvenor Road, Woods Road, Harlech Avenue, All Hallows Road, Milestone Way, Hawthorne Road,
Queensway, The Horse Close, Holyrood Close, Orchard Grove, Greystoke Road, Osterley Drive, Valentine Crescent, Netley Close, Copse Avenue.
Those streets are in result.json with confidence "none".

## Rerun (2026-11-19)
Google Maps came up blank white again: its JS/CSS were still blocked with net::ERR_BLOCKED_BY_CLIENT.
Tried Grosvenor Road 0_138 (waited a further 8 s), then in a fresh tab Woods Road 0_000 and Harlech Avenue 0_258 (waited 10 s). All three stayed blank, so I stopped.
None of the 72 rerun views loaded: every view of the 15 streets above. They are still in result.json as "Not surveyed", and no screenshots were saved.

## Rerun 2 (2026-11-19, tab-2)
Google Maps loaded again. Surveyed all 15 remaining streets; 76 new screenshots saved (134 in img/).
Views that never loaded (Street View shows "No Street View imagery available here", black panorama, retried):
- Grosvenor Road 0_138, 0_018 (the other Grosvenor views snapped to the B481 and A4155 ends, so the road itself is unseen)
- Greystoke Road 0_048, 0_288, 1_055, 1_295 (no imagery on the whole road; result.json confidence "none")
Notes: Milestone Way views show a gravel lane/footpath and snapped to Harlech Avenue and Northbrook Road.
Osterley Drive views 1_x and 2_x land on the same panorama. Queensway 1_056 caught mid fade-in (pale but usable).
