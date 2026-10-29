#!/usr/bin/env python3
"""Builds the site into _site/. Standard library only.

Each app is one folder in apps/: app.toml (the data), icon.svg and shot.html (a small HTML picture
of the app, drawn for a square). The script reads every folder, gets the latest release of each
download from the GitHub API, and writes one HTML page with the CSS inline: a wall of squares, and
one close-up popover per app.

    python3 build.py             # needs network; set GITHUB_TOKEN to avoid the rate limit
    python3 build.py --offline   # no network; download links go to the releases page
"""

import gzip
import html
import json
import os
import re
import shutil
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"
OFFLINE = "--offline" in sys.argv

FONTS = [  # (family, style, file); all are preloaded, the page needs them all within a second
    ("R", "normal", "Redaction-Regular.woff2"),
    ("R20", "normal", "Redaction20-Regular.woff2"),
    ("R50", "normal", "Redaction50-Regular.woff2"),
    ("R100", "normal", "Redaction100-Regular.woff2"),
]

esc = html.escape


# ---------------------------------------------------------------- data

def load_apps():
    apps = []
    for folder in sorted((ROOT / "apps").iterdir()):
        toml = folder / "app.toml"
        if not toml.is_file():
            continue
        app = tomllib.loads(toml.read_text())
        app["slug"] = folder.name
        app["icon"] = (folder / "icon.svg").read_text() if (folder / "icon.svg").is_file() else ""
        shot = (folder / "shot.html").read_text() if (folder / "shot.html").is_file() else ""
        # A <style> block in shot.html moves into the page CSS, so app-specific rules stay in the app folder.
        # Its #<folder> selectors apply to the close-up (that id) and to the back of the square (.t-<folder>).
        css = "".join(re.findall(r"<style>(.*?)</style>", shot, flags=re.S))
        app["shot_css"] = re.sub(rf"#{re.escape(folder.name)}(?![\w-])", f":is(#{folder.name},.t-{folder.name})", css)
        app["shot"] = re.sub(r"<style>.*?</style>", "", shot, flags=re.S)
        apps.append(app)
    apps.sort(key=lambda a: (a.get("order", 999), a["name"].lower()))
    return apps


_releases = {}


def releases(repo):
    if repo not in _releases:
        _releases[repo] = []
        if not OFFLINE:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases?per_page=20",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "apps.turtlecute.org build"},
            )
            token = os.environ.get("GITHUB_TOKEN")
            if token:
                request.add_header("Authorization", f"Bearer {token}")
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    _releases[repo] = json.load(response)
            except Exception as error:  # a failed fetch must not break the build
                print(f"warning: {repo}: {error}", file=sys.stderr)
    return _releases[repo]


def resolve(download):
    """The newest non-draft release asset that matches the pattern, or a link to the releases page."""
    pattern = re.compile(download["asset"])
    for release in releases(download["repo"]):
        if release.get("draft"):
            continue
        for asset in release.get("assets", []):
            if pattern.search(asset["name"]):
                return {
                    "url": asset["browser_download_url"],
                    "size": asset["size"],
                    "version": release["tag_name"].lstrip("v"),
                    "pre": release.get("prerelease", False),
                }
    return {"url": f"https://github.com/{download['repo']}/releases", "size": None, "version": None, "pre": False}


def size(n):
    if n is None:
        return ""
    return f"{n / 1024:.0f} KB" if n < 1_000_000 else f"{n / 1_000_000:.1f} MB"


# ---------------------------------------------------------------- markup

def svg(source, slug, cls):
    """Inline an icon: ids get the app prefix (every logo uses id="bg"), size comes from CSS."""
    source = re.sub(r"<\?xml[^>]*>\s*", "", source)
    source = re.sub(r"<title>.*?</title>\s*", "", source, flags=re.S)
    source = re.sub(r'\sid="([^"]+)"', lambda m: f' id="{slug}-{m.group(1)}"', source)
    source = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{slug}-{m.group(1)})", source)
    source = re.sub(r'<svg\b([^>]*?)\s(width|height)="[^"]*"', r"<svg\1", source)
    source = re.sub(r'<svg\b([^>]*?)\s(width|height)="[^"]*"', r"<svg\1", source)
    source = source.replace("<svg", f'<svg class="{cls}" aria-hidden="true" focusable="false"', 1)
    return re.sub(r">\s+<", "><", source.strip())


def sprite(apps):
    """Every icon once, as a <symbol>. The tile and the close-up both point to it with <use>.
    The UI icons that the app pictures use (src/glyphs.svg) go in the same sprite."""
    symbols = []
    for app in apps:
        icon = svg(app["icon"], app["slug"], "")
        view = re.search(r'viewBox="([^"]+)"', icon).group(1)
        inner = re.sub(r"^<svg[^>]*>|</svg>$", "", icon)
        symbols.append(f'<symbol id="i-{app["slug"]}" viewBox="{view}">{inner}</symbol>')
    glyphs = re.sub(r"<!--.*?-->", "", (ROOT / "src" / "glyphs.svg").read_text(), flags=re.S)
    symbols.append(re.sub(r">\s+<", "><", glyphs.strip()))
    return f'<svg class="sprite" aria-hidden="true" focusable="false">{"".join(symbols)}</svg>'


def use(slug, cls):
    return (
        f'<svg class="{cls}" viewBox="0 0 72 72" aria-hidden="true" focusable="false">'
        f'<use href="#i-{slug}" width="72" height="72"/></svg>'
    )


def colours(app):
    return f'--c:{app["color"]};--bg:{app.get("backdrop", app["color"])}'


def tile(app, i):
    """One square on the wall: the logo in front, the app's screens behind, a glass label on top."""
    slug = app["slug"]
    names = [p.split()[0] for p in app["platforms"] if p not in ("arm64", "x86_64")]  # "Android 15+" -> "Android"
    kind = f'{app["noun"]} · ' + (" / ".join(names) if len(names) <= 2 else f"{len(names)} platforms")
    return (
        f'<article class="tile t-{slug}{" l" if app.get("size") == "l" else ""}" style="{colours(app)};--i:{i}">'
        f'<div class="frame"><div class="turn"><div class="flip">'
        f'<div class="face front"><span class="lg">{use(slug, "logo")}</span></div>'
        f'<div class="face back shot" aria-hidden="true">{app["shot"].strip()}</div>'
        f"</div></div>"
        f'<p class="pl"><b>{esc(app["name"])}</b><span>{esc(kind)}</span></p>'
        f'<button class="hit" popovertarget="{slug}" aria-label="{esc(app["name"])}, {esc(app["noun"])}"'
        f' data-umami-event="open-app" data-umami-event-app="{esc(app["name"])}"></button>'
        f"</div></article>"
    )


def panel(app):
    slug = app["slug"]
    downloads = [(d, resolve(d)) for d in app.get("download", [])]
    version = next((r["version"] for _, r in downloads if r["version"]), None)
    pre = next((r["pre"] for _, r in downloads if r["version"]), False)

    facts = [("Runs on", " · ".join(app["platforms"])), ("Asks for", app["asks"]), ("Talks to", app["talks"])]
    if app.get("based_on"):
        facts.append(("Built on", app["based_on"]))
    release = " · ".join(x for x in [version and (version + (" pre-release" if pre else "")), app["license"]] if x)
    facts.append(("Release", release))
    dl = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in facts)

    # data-umami-event*: Umami counts each click as an event with these properties (see README).
    track = f'data-umami-event-app="{esc(app["name"])}"'
    links = "".join(
        f'<a href="{esc(r["url"])}" data-umami-event="download" {track} data-umami-event-platform="{esc(d["label"])}">'
        f'{esc(d["label"])}<small>{size(r["size"])}</small></a>'
        for d, r in downloads
    )
    links += f'<a href="https://github.com/{esc(app["repo"])}" class="src" data-umami-event="source" {track}>Source</a>'
    brew = f'<code class="brew">brew install --cask {esc(app["brew"])}</code>' if app.get("brew") else ""
    points = "".join(f"<li>{esc(p)}</li>" for p in app.get("points", []))
    points = f'<ul class="pts">{points}</ul>' if points else ""
    note = f'<p class="note">{esc(app["note"])}</p>' if app.get("note") else ""

    return (
        f'<section popover id="{slug}" class="p" aria-labelledby="{slug}-t" style="{colours(app)}">'
        f'<button class="x" popovertarget="{slug}" popovertargetaction="hide" aria-label="Close">'
        f'<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 2l6 6M8 2l-6 6"/></svg></button><div class="sc">'
        f'<figure class="shot" aria-hidden="true">{app["shot"].strip()}</figure>'
        f'<div class="info"><header>{use(slug, "pi")}<div><h2 id="{slug}-t">{esc(app["name"])}</h2>'
        f'<p class="kind">{esc(app["noun"])}</p></div></header>'
        f'<p class="line">{esc(app["line"])}</p>{points}'
        f'<nav class="get">{links}</nav>{brew}<dl>{dl}</dl>{note}</div></div></section>'
    )


def about(site, apps, turtle):
    """The picture behind the wall label and in its close-up: a profile with the links, a home screen with the apps."""
    links = "".join(
        f'<div class="row card"><i class="av r">{esc(name[0])}</i><div class="tx"><b>{esc(name)}</b>'
        f'<i>{esc(url.split("//", 1)[-1])}</i></div></div>'
        for name, url in site["links"].items()
    )
    icons = "".join(f'<span>{use(a["slug"], "")}<i>{esc(a["name"])}</i></span>' for a in apps)
    return (
        f'<div class="ph" style="left:7%;--ui:#7a5320"><i class="av r me">{turtle}</i>'
        f'<div class="h">{esc(site["handle"])}</div><div class="sub">{esc(site["role"])}</div>'
        f'<div class="stats"><span><b>{len(apps)}</b> apps</span><span><b>0</b> trackers</span><span>open source</span></div>'
        f'<div class="sec"><span>Links</span></div>{links}</div>'
        f'<div class="ph dk home" style="right:7%;top:18cqi"><div class="ic">{icons}</div>'
        f'<div class="sr"><svg class="g"><use href="#g-search"/></svg>Search</div></div>'
    )


def jsonld(site, apps):
    """Structured data for search engines: the author, the site and one SoftwareApplication for each app."""
    base = f"https://{site['domain']}/"
    me = {"@id": base + "#me"}
    items = []
    for i, app in enumerate(apps, 1):
        downloads = [resolve(d) for d in app.get("download", [])]
        item = {
            "@type": "SoftwareApplication",
            "name": app["name"],
            "description": app["line"],
            "applicationCategory": app["category"],
            "operatingSystem": ", ".join(p for p in app["platforms"] if p not in ("arm64", "x86_64")),
            "url": f"https://github.com/{app['repo']}",
            "license": f"https://spdx.org/licenses/{app['license']}.html",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "author": me,
        }
        if app.get("points"):
            item["featureList"] = app["points"]
        if downloads:
            item["downloadUrl"] = downloads[0]["url"]
        version = next((r["version"] for r in downloads if r["version"]), None)
        if version:
            item["softwareVersion"] = version
        items.append({"@type": "ListItem", "position": i, "item": item})
    graph = [
        {"@type": "Person", "@id": me["@id"], "name": site["handle"], "description": site["about"][0],
         "url": next(iter(site["links"].values())), "sameAs": list(site["links"].values())},
        {"@type": "WebSite", "@id": base + "#site", "url": base, "name": site["title"],
         "description": site["description"], "inLanguage": "en", "author": me},
        {"@type": "ItemList", "name": f"Apps by {site['handle']}", "itemListElement": items},
    ]
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))
    return data.replace("</", "<\\/")


def llms(site, apps):
    """/llms.txt: the same facts as plain Markdown, for AI search and assistants."""
    lines = [f"# {site['title']}", "", f"> {site['description']}", ""] + [p + "\n" for p in site["about"][:3]]
    lines += ["## Apps", ""]
    for app in apps:
        lines.append(f"- [{app['name']}](https://github.com/{app['repo']}): {app['noun']} for "
                     f"{', '.join(app['platforms'])}, {app['license']}. {app['line']}")
        lines += [f"  - {p}" for p in app.get("points", [])]
        if app.get("note"):
            lines.append(f"  - {app['note']}")
    lines += ["", "## Links", ""] + [f"- {name}: {url}" for name, url in site["links"].items()]
    return "\n".join(lines) + "\n"


def minify_css(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    return css.replace(";}", "}").strip()


# ---------------------------------------------------------------- build

def main():
    site = tomllib.loads((ROOT / "site.toml").read_text())
    apps = load_apps()

    wall = "".join(tile(app, i) for i, app in enumerate(apps))
    panels = "".join(panel(app) for app in apps)
    css = minify_css((ROOT / "src" / "style.css").read_text() + "".join(a["shot_css"] for a in apps))
    fonts = "".join(
        f'@font-face{{font-family:{f};font-style:{s};font-display:{"swap" if f == "R" else "block"};'
        f'src:url(fonts/{file}) format("woff2")}}'
        for f, s, file in FONTS
    )
    preload = "".join(
        f'<link rel="preload" href="fonts/{file}" as="font" type="font/woff2" crossorigin>' for _, _, file in FONTS
    )
    links = "".join(
        f'<a href="{esc(url)}" rel="me" data-umami-event="link" data-umami-event-to="{esc(name)}">{esc(name)}</a>'
        for name, url in site["links"].items()
    )
    lead = " ".join(f'<span style="--i:{i}">{esc(w)}</span>' for i, w in enumerate((site["lead"] + ".").split()))
    turtle = (ROOT / "src" / "turtle.svg").read_text().strip()

    page = (ROOT / "src" / "index.html").read_text()
    for key, value in {
        "{{title}}": esc(site["title"]),
        "{{description}}": esc(site["description"]),
        "{{tagline}}": esc(site["tagline"]),
        "{{jsonld}}": jsonld(site, apps),
        "{{domain}}": esc(site["domain"]),
        "{{preload}}": preload,
        "{{css}}": fonts + css,
        "{{sprite}}": sprite(apps),
        "{{turtle}}": turtle,
        "{{about}}": about(site, apps, turtle),
        "{{count}}": str(len(apps)),
        "{{lead}}": lead,
        "{{wall}}": wall,
        "{{panels}}": panels,
        "{{handle}}": esc(site["handle"]),
        "{{role}}": esc(site["role"]),
        "{{bio}}": "".join(
            f'<p class="{"line" if i == 0 else "bio"}">{esc(text)}</p>' for i, text in enumerate(site["about"])
        ),
        "{{links}}": links,
    }.items():
        page = page.replace(key, value)
    page = re.sub(r">\s*\n\s*<", "><", page)  # only line breaks: inline text needs its spaces

    # Empty _site/ but keep the folder, so a local server that runs in it keeps working.
    OUT.mkdir(exist_ok=True)
    for child in OUT.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    (OUT / "fonts").mkdir()
    for _, _, file in FONTS:
        shutil.copy(ROOT / "fonts" / file, OUT / "fonts" / file)
    shutil.copy(ROOT / "fonts" / "OFL.txt", OUT / "fonts" / "OFL.txt")
    shutil.copy(ROOT / "src" / "favicon.svg", OUT / "favicon.svg")
    shutil.copy(ROOT / "src" / "og.png", OUT / "og.png")
    (OUT / "CNAME").write_text(site["domain"] + "\n")
    base = f"https://{site['domain']}/"
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}sitemap.xml\n")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base}</loc></url></urlset>\n'
    )
    (OUT / "llms.txt").write_text(llms(site, apps))

    # The weight line counts what a first visit downloads: the gzipped page, the fonts, the icon.
    # The Umami script (about 1.5 KB) comes from umami.priorato.org and is not in the count.
    # Two passes, because the line is part of the page it measures.
    files = 2 + len(FONTS)
    weight = "{{weight}}"
    for _ in range(2):
        text = page.replace("{{weight}}", weight)
        total = len(gzip.compress(text.encode(), 9)) + sum((OUT / "fonts" / f).stat().st_size for _, _, f in FONTS)
        total += len(gzip.compress((OUT / "favicon.svg").read_bytes(), 9))
        weight = f"{total / 1024:.0f} KB · {files} files + Umami analytics"
    page = page.replace("{{weight}}", weight)
    (OUT / "index.html").write_text(page)
    print(f"{len(apps)} apps, {weight}")


if __name__ == "__main__":
    main()
