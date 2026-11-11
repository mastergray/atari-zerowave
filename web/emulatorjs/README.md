# Bundled EmulatorJS runtime

ZeroWave hosts this directory alongside its page and ROM. Upload all of it with
the rest of `web/`. Runtime requests stay on the hosting website; the URLs below
are provenance and source references, not runtime dependencies.

## Versions and sources

- [EmulatorJS 4.2.3](https://github.com/EmulatorJS/EmulatorJS/tree/v4.2.3),
  commit `e150dc0491ae747028919fb82d6598954976ede6`. The readable loader, JavaScript,
  CSS, compression workers, localization and license come from this tag.
  The original archive is `sources/emulatorjs-v4.2.3.tar.gz`.
- Stella 2014 core bundles were obtained from
  `https://cdn.emulatorjs.org/4.2.3/data/cores/`. Their unmodified build report is
  `data/cores/reports/stella2014.json`, dated June 14, 2025. Each bundle contains
  its JavaScript, WebAssembly and build/core metadata (core build version 2.0.2).
  WebGL 1/2 and threaded/non-threaded variants are included; ZeroWave defaults
  to non-threaded execution and requires no special isolation headers.
- [Stella 2014 source](https://github.com/EmulatorJS/stella2014-libretro/tree/1f578c36382bb5a86a0fe245973fa557f369738b),
  commit `1f578c36382bb5a86a0fe245973fa557f369738b`, is in
  `sources/stella2014-source.tar.gz`. Its abbreviated commit is embedded in the
  bundled core. The original license is also copied to `licenses/stella2014.txt`.
- The [core build scripts](https://github.com/EmulatorJS/build/tree/b24e5b535034dc7c3428d76f236d4793881969b6)
  and [RetroArch source](https://github.com/EmulatorJS/RetroArch/tree/fc6b1b9fabebdaa1161405512d4a0602f7f65c50)
  are in `sources/core-build-source.tar.gz` and `sources/retroarch-source.tar.gz`.
  These snapshots are the latest upstream commits before the reported core build
  time; the upstream binaries do not record the RetroArch commit. Their READMEs,
  build scripts and original license files are included. RetroArch's license is
  also copied to `licenses/RetroArch.txt`.

`LICENSE` is EmulatorJS's upstream GPL license. Third-party libraries retain
their notices in the supplied source files and archives. `manifest.json` records
the bundled file hashes so copies and updates can be checked.

## Local changes

- `data/loader.js` loads the bundled readable scripts and `emulator.css`, rather
  than a generated minified bundle. Normal core caching remains enabled.
- `data/src/emulator.js` does not perform its remote update check, including on
  localhost. Missing core files report a loading error instead of fetching a CDN
  fallback. Core binaries and other upstream runtime files are unmodified.
- ZeroWave disables the netplay button and leaves experimental netplay disabled.

## Updating

Keep loader, frontend and cores compatible when changing the pinned release.
Preserve the local changes above, upstream licenses and source snapshots, update
the manifest, and run `make web-check` before `make dist`. Packaging includes
this directory in the source archive; it never downloads dependencies at build
or play time. Source snapshots are downloads for readers and are not loaded by
the game at startup.
