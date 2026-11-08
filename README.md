# Quake Sorter

A website where people upload an earthquake catalogue, draw a study area on a map, and get stochastic declustering results: fitted parameters, how many events are certain background, uncertain or certain aftershocks, a histogram of each event's chance of being an aftershock, and maps of the events and of the background rate.

**Status: prototype.** The fits run with [`steqpy`](../stochastic_declustering_improvement) on a computer that runs `server.py`. Not hosted with a server yet.

## Two ways to use it

**Demo (GitHub Pages, or any static host).** This is a template of the site: everything up to Process works, but no new fits can run, because a static host has no server.
- Upload your own CSV: the file check, the completeness figure and polygon drawing all run in your browser, and the file is not sent anywhere.
- "Try the sample catalogue" loads a real catalogue (see Sample data), and fits stored in `examples/` open as finished results, each with its own link (`#/examples/<file>`).
- Process explains that fits need the local server and links the stored fits.

**Local server (real fits).** Run `python server.py` with the Python environment that has `steqpy`'s dependencies (numpy, numba), then open http://127.0.0.1:8765/. The page sees the server and fits whatever you upload, one job at a time. Each run is kept in `jobs/` (catalogue, polygon, steqpy config, results), which is not committed. Job links (`#/jobs/<id>`) only open on the computer that ran the job.

Opened straight from disk (`index.html` as a file), the page shows the old mockup with made-up data.

All modes need an internet connection for the map library, map tiles and font. Desktop browsers only: drawing the study area needs a computer.

## Adding a stored fit

Run the fit on the local server, then:

    python save_example.py <job_id> <name> "Title shown on the page" "one-line note"

This writes `examples/<name>.json` and lists it in `examples/index.json`. To remove one, delete its file and its entry in `examples/index.json`. Only store fits of data that may be published.

## Catalogue format

CSV with a header row naming the time, longitude, latitude and magnitude columns, in any order. Common names such as `origin_time`, `lat`, `lon`, `mag` are recognised, and other columns are ignored. Depth is optional: the model does not use it, but it is shown when you click an event. Times without a time zone are read as UTC.

## Sample data

`examples/isc_indonesia_mw.csv`: 4,218 events in Indonesia (18.10°S–4.61°N, 93.08–138.47°E), depth ≤ 50 km, Mw ≥ 4, 1963–2024, from the ISC Bulletin (International Seismological Centre, 2024, On-line Bulletin, https://doi.org/10.31905/D808B830). Location is the ISC prime hypocentre; Mw is GCMT's where available, else NEIC's, else another agency's (no conversion from mb or Ms).

## Planned

- A hosted server (a free Python host, or the local server behind a tunnel), with a shared password, a queue cap and old jobs deleted after some days.

## Credits

Map library: MapLibre GL JS. Map tiles: OpenFreeMap, with data from OpenStreetMap. Earthquake marker sizes and age colours follow the USGS Latest Earthquakes map. Colour maps: Oslo and Bilbao by Fabio Crameri (Scientific colour maps).
