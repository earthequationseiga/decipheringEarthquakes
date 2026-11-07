# Quake Sorter

A website where people upload an earthquake catalogue, draw a study area on a map, and get stochastic declustering results: fitted parameters, background and triggered counts at a chosen probability cutoff, a histogram, and a map of event probabilities.

**Status: clickable mockup only.** All data is made up in the browser. There is no backend, real upload or declustering yet.

## Try it

Open `index.html` in a browser. It needs an internet connection for the map library, map tiles and font.

## Planned

- Catalogue format: CSV with `time, longitude, latitude, depth, magnitude`. Depth may be empty, because the model does not use it.
- Backend: a web server that answers polls, and one worker that runs [`steqpy`](../stochastic_declustering_improvement) one job at a time.
- Each job runs as a subprocess with a time limit, and its result is shown only if p > 1 and q > 1.

## Credits

Map library: MapLibre GL JS. Map tiles: OpenFreeMap, with data from OpenStreetMap.
