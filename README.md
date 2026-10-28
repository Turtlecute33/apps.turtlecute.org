# apps.turtlecute.org

A wall of squares, one per app: the logo in front, the app's screens behind, a glass label on top.
Click a square for the close-up with downloads; the last square (the turtle) opens the links. Static, no
JavaScript, no third-party requests.

## Add an app

Make a folder in `apps/` with three files:

| File | What it is |
|---|---|
| `app.toml` | The data. Copy one from another app and change the values. |
| `icon.svg` | The app icon, 72×72 tile (`viewBox="18 18 72 72"`), the same as the `docs/logo.svg` files. |
| `shot.html` | A small HTML picture of the app, drawn for a square (the back of the tile and the close-up). Use the classes in `src/style.css` (`.ph` phone, `.win` window, `.row`, `.card`, `.bt`, `.sw` …) and the icons in `src/glyphs.svg` (`<svg class="g"><use href="#g-chev"/></svg>`). On a phone 1em is 14 sp, in a window 1em is 13 pt. A `<style>` block in this file moves into the page CSS; start its selectors with `#<folder>`. The build applies them to the close-up and to the back of the square. |

`app.toml` fields:

```toml
name = "Plico"
noun = "mail client"          # the kind of app, on the label
category = "CommunicationApplication"   # schema.org applicationCategory, for search engines
order = 1                     # place on the wall
size = "l"                    # optional: large square (default: medium)
color = "#3F51B5"             # underline, panel tint, picture background
backdrop = "#1E1E2E"          # optional: picture background, if not `color`
line = "The pitch: what the app does better than the app it replaces."
points = ["Three short highlights", "with numbers from the repo", "one line each"]   # optional
note = "Not made by …"         # optional: small print under the facts
platforms = ["Android 15+"]
license = "GPL-3.0"
asks = "network, background push"   # permissions, in plain words
talks = "your mail server"          # where it connects
based_on = "HeliBoard"              # optional
repo = "Turtlecute33/Plico"
brew = "turtlecute33/tap/x"         # optional

[[download]]                  # one block per platform
label = "Android"
repo = "Turtlecute33/Plico"
asset = '\.apk$'              # regex for the release asset name
```

The build gets the version, size and link of each download from the newest release that has a
matching asset (pre-releases too).

## Build

```zsh
GITHUB_TOKEN=$(gh auth token) python3 build.py   # writes _site/
python3 build.py --offline                       # no network; links go to the releases page
```

Python 3.11 or later, standard library only. The GitHub Action builds on each push and once a day,
so a new app release shows on the site within a day.

## Notes

- Font: [Redaction](https://github.com/jeremymickel/Redaction) by MCKL, SIL OFL 1.1 (`fonts/OFL.txt`).
  The files are subset to Latin with `pyftsubset`.
- Names decode through the Redaction cuts (100, 50, 20, Regular) as a square comes into view.
  Do not put `text-wrap: pretty` on text that runs this animation: together they crash WebKit at
  phone widths.
- The wall packs large (6×6) and medium (3×3) squares on a 12-column grid; the wall label fills the
  last gap. With 9 apps, large squares at places 3 and 5 (now Ombra and Fonte) leave no holes on
  desktop, tablet or phone. Check the wall after you add an app or change `size`.
- Search: `title`, `description` and `tagline` in `site.toml` make the search result and the share
  card. The build also writes JSON-LD (the author and one `SoftwareApplication` for each app),
  `robots.txt`, `sitemap.xml` and `llms.txt`. `src/og.png` is the share image (1200×630); make it
  again when you add an app.
- Icons are inlined once as `<symbol>`s; the square and the close-up point to them with `<use>`. The UI
  icons for the pictures (`src/glyphs.svg`) go in the same sprite.
- Draw each picture from the real app: run it in the emulator with made-up data, or use the banner in
  its repo. Do not use personal data. A claim in `line` or `points` must have a source in the app repo.
- The wall label is a square like the apps: `src/turtle.svg` (a 24×10 pixel drawing with two leg frames)
  walks the front, and its close-up (`#about`) holds `role`, the `about` paragraphs and the `[links]` from
  `site.toml`. On touch screens one square
  turns every 3.5 s; the loop in `src/style.css` is 35 s for 10 squares. Change it when you add an app.
- Animate `transform`, not `translate`, on an `<svg>`: Chromium keeps `translate` on the main thread.
