# Quake Sorter

A website where people upload an earthquake catalogue, draw a study area on a map, and get stochastic declustering results: fitted parameters, background and triggered counts at a chosen probability cutoff, a histogram, and a map of event probabilities.

**Status: clickable mockup.** Uploading a real catalogue works (it is read and checked in the browser), but there is no backend or declustering yet: the results are made up.

## Try it

Open `index.html` in a browser. It needs an internet connection for the map library, map tiles and font.

Desktop browsers only: drawing the study area needs a computer.

## Catalogue format

CSV with a header row naming the time, longitude, latitude and magnitude columns, in any order. Common names such as `origin_time`, `lat`, `lon`, `mag` are recognised, and other columns are ignored. Depth is optional, because the model does not use it. Times without a time zone are read as UTC.

## Planned

- Backend: a web server that answers polls, and one worker that runs [`steqpy`](../stochastic_declustering_improvement) one job at a time.
- Each job runs as a subprocess with a time limit, and its result is shown only if p > 1 and q > 1.

## Credits

Map library: MapLibre GL JS. Map tiles: OpenFreeMap, with data from OpenStreetMap. Earthquake marker sizes and age colours follow the USGS Latest Earthquakes map.
