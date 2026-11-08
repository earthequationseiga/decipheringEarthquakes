# Quake Sorter

A website where people upload an earthquake catalogue, draw a study area on a map, and get stochastic declustering results: fitted parameters, how many events are certain background, uncertain or certain aftershocks, a histogram of each event's chance of being an aftershock, and maps of the events and of the background rate.

**Status: local prototype.** Upload, polygon drawing and results work; with `server.py` the fits are real (run on your own machine). Not hosted yet.

## Try it

- Mockup (made-up results): open `index.html` in a browser.
- Real fits on your own machine: run `python server.py` with the Python environment that has [`steqpy`](../stochastic_declustering_improvement)'s dependencies (numpy, numba), then open http://127.0.0.1:8765/. Each run is kept in `jobs/` (catalogue, polygon, steqpy config, results).

Both need an internet connection for the map library, map tiles and font.

Desktop browsers only: drawing the study area needs a computer.

## Catalogue format

CSV with a header row naming the time, longitude, latitude and magnitude columns, in any order. Common names such as `origin_time`, `lat`, `lon`, `mag` are recognised, and other columns are ignored. Depth is optional, because the model does not use it. Times without a time zone are read as UTC.

## Planned

- Backend: a web server that answers polls, and one worker that runs [`steqpy`](../stochastic_declustering_improvement) one job at a time.
- Each job runs as a subprocess with a time limit, and its result is shown only if p > 1 and q > 1.

## Credits

Map library: MapLibre GL JS. Map tiles: OpenFreeMap, with data from OpenStreetMap. Earthquake marker sizes and age colours follow the USGS Latest Earthquakes map.
