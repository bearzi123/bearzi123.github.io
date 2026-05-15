#!/usr/bin/env python3
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

CONTENT_DIR = Path("content")
ROOT_OUT_DIR = Path("posts")
INDEX_FILE = Path("index.html")
CACHE_FILE = Path(".build-cache.json")

FILE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-(.+)\.(txt|md|jpg|jpeg|png|heic|heif|html|pdf|pptx|odp|odt)$", re.IGNORECASE
)

POST_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — bearzi123</title>
</head>
<body>
    <header>
        <h1><a href="/">bearzi123</a></h1>
    </header>

    <article>
        <h1>{title} — {date}</h1>

        {content}
    </article>

    <a class="back" href="{back}">← back</a>
</body>
</html>
"""

SECTION_INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — bearzi123</title>
</head>
<body>
    <header>
        <h1><a href="/">bearzi123</a></h1>
        <p>{title}</p>
    </header>

    <ul class="post-list">
    </ul>

    <a class="back" href="{back}">← back</a>
</body>
</html>
"""


class _TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in = False
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in = False

    def handle_data(self, data):
        if self._in and self.title is None:
            self.title = data.strip()


def _html_title(html_text):
    p = _TitleParser()
    p.feed(html_text)
    t = p.title or ""
    return t.split(" — ")[0].strip() if " — " in t else t


def _title_from_slug(slug):
    return slug.replace("-", " ").replace("_", " ").capitalize()


def _txt_to_html(text):
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text.strip()) if p.strip()]
    return "\n\n        ".join(
        "<p>{}</p>".format(p.replace("\n", "<br>")) for p in paragraphs
    )


def _out_path(content_file):
    """Map a content/ source file to its output path."""
    parts = content_file.relative_to(CONTENT_DIR).parts
    stem = Path(parts[-1]).stem  # YYYY-MM-DD-slug
    if len(parts) == 1:
        return ROOT_OUT_DIR / (stem + ".html")
    else:
        return Path(parts[0]).joinpath(*parts[1:-1]) / (stem + ".html")


def _dir_title(path):
    return path.name.replace("-", " ").replace("_", " ").title()


def _build_file(src, out):
    m = FILE_PATTERN.match(src.name)
    date_str, slug, ext = m.group(1), m.group(2), m.group(3).lower()
    out.parent.mkdir(parents=True, exist_ok=True)

    back = "../" if out.parent != Path(".") else "/"

    if ext == "md":
        import markdown as _md
        title = _title_from_slug(slug)
        content_html = _md.markdown(src.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
        out.write_text(
            POST_TEMPLATE.format(title=title, date=date_str, content=content_html, back=back),
            encoding="utf-8",
        )
    elif ext == "txt":
        title = _title_from_slug(slug)
        content_html = _txt_to_html(src.read_text(encoding="utf-8"))
        out.write_text(
            POST_TEMPLATE.format(title=title, date=date_str, content=content_html, back=back),
            encoding="utf-8",
        )
    elif ext in ("jpg", "jpeg", "png"):
        shutil.copy2(src, out.parent / src.name)
        title = _title_from_slug(slug)
        content_html = f'<img src="{src.name}" alt="{title}" style="max-width:100%;">'
        out.write_text(
            POST_TEMPLATE.format(title=title, date=date_str, content=content_html, back=back),
            encoding="utf-8",
        )
    elif ext in ("heic", "heif"):
        try:
            import pillow_heif
            from PIL import Image
            pillow_heif.register_heif_opener()
        except ImportError:
            raise SystemExit("HEIC support requires: pip install pillow pillow-heif")
        img_name = Path(src.stem).with_suffix(".jpg").name
        img = Image.open(src)
        img.save(out.parent / img_name, "JPEG", quality=90)
        title = _title_from_slug(slug)
        content_html = f'<img src="{img_name}" alt="{title}" style="max-width:100%;">'
        out.write_text(
            POST_TEMPLATE.format(title=title, date=date_str, content=content_html, back=back),
            encoding="utf-8",
        )
    elif ext == "pdf":
        shutil.copy2(src, out.parent / src.name)
        title = _title_from_slug(slug)
        content_html = (
            f'<object data="{src.name}" type="application/pdf" style="width:100%;height:80vh;">'
            f'<a href="{src.name}">{title}</a>'
            f'</object>'
        )
        out.write_text(
            POST_TEMPLATE.format(title=title, date=date_str, content=content_html, back=back),
            encoding="utf-8",
        )
    elif ext in ("pptx", "odp", "odt"):
        import subprocess
        shutil.copy2(src, out.parent / src.name)
        title = _title_from_slug(slug)
        content_html = None
        try:
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(out.parent), str(src)],
                capture_output=True, timeout=60, check=False,
            )
            pdf_name = src.stem + ".pdf"
            if result.returncode == 0 and (out.parent / pdf_name).exists():
                content_html = (
                    f'<div style="text-align:right;margin-bottom:4px;">'
                    f'<button onclick="var e=document.getElementById(\'pdf-wrap\');'
                    f'(e.requestFullscreen||e.webkitRequestFullscreen).call(e);" '
                    f'style="padding:6px 14px;cursor:pointer;background:#fff;'
                    f'border:1px solid #999;border-radius:4px;font-size:0.85rem;">'
                    f'Fullscreen</button>'
                    f'</div>'
                    f'<div id="pdf-wrap" style="width:100%;height:80vh;">'
                    f'<object data="{pdf_name}" type="application/pdf" style="width:100%;height:100%;">'
                    f'<a href="{src.name}">{title}</a>'
                    f'</object>'
                    f'</div>'
                    f'<style>#pdf-wrap:fullscreen{{width:100%;height:100%;}}</style>'
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        if content_html is None:
            content_html = f'<p><a href="{src.name}">{title}</a> — download to open in LibreOffice</p>'
        out.write_text(
            POST_TEMPLATE.format(title=title, date=date_str, content=content_html, back=back),
            encoding="utf-8",
        )
    else:  # .html — copy as-is
        shutil.copy2(src, out)


def _rebuild_index(content_dir):
    """Build or update index.html for a content directory."""
    if content_dir == CONTENT_DIR:
        posts = []
        for item in content_dir.iterdir():
            if not item.is_file():
                continue
            m = FILE_PATTERN.match(item.name)
            if not m:
                continue
            date_str, slug, ext = m.group(1), m.group(2), m.group(3).lower()
            out = _out_path(item)
            title = _html_title(item.read_text(encoding="utf-8")) or _title_from_slug(slug) if ext == "html" else _title_from_slug(slug)
            posts.append((date_str, title, out))
        _update_post_list(INDEX_FILE, sorted(posts, reverse=True))
        return

    rel_parts = content_dir.relative_to(CONTENT_DIR).parts
    out_dir = Path(*rel_parts)
    index_path = out_dir / "index.html"

    if not index_path.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            SECTION_INDEX_TEMPLATE.format(title=_dir_title(content_dir), back="../"),
            encoding="utf-8",
        )

    posts = []
    for item in content_dir.iterdir():
        if item.is_file():
            m = FILE_PATTERN.match(item.name)
            if not m:
                continue
            date_str, slug, ext = m.group(1), m.group(2), m.group(3).lower()
            out = _out_path(item)
            title = _html_title(item.read_text(encoding="utf-8")) or _title_from_slug(slug) if ext == "html" else _title_from_slug(slug)
            posts.append((date_str, title, out))
        elif item.is_dir():
            sub_files = sorted(
                (f for f in item.rglob("*") if f.is_file() and FILE_PATTERN.match(f.name)),
                key=lambda f: f.name,
                reverse=True,
            )
            if not sub_files:
                continue
            date_str = FILE_PATTERN.match(sub_files[0].name).group(1)
            posts.append((date_str, _dir_title(item), out_dir / item.name / "index.html"))
    _update_post_list(index_path, sorted(posts, reverse=True))


def _update_post_list(index_path, posts):
    index_dir = index_path.parent
    items = "\n".join(
        '        <li><span class="date">{}</span> <a href="{}">{}</a></li>'.format(
            d, out.relative_to(index_dir), t
        )
        for d, t, out in posts
    )
    text = index_path.read_text(encoding="utf-8")
    new_text = re.sub(
        r'(<ul class="post-list">).*?(</ul>)',
        f"\\1\n{items}\n    \\2",
        text,
        flags=re.DOTALL,
    )
    index_path.write_text(new_text, encoding="utf-8")


def build():
    ROOT_OUT_DIR.mkdir(exist_ok=True)

    cache = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())

    new_cache = {}
    changed_dirs = set()

    def _mark_changed(src):
        d = src.parent
        while True:
            changed_dirs.add(d)
            if d == CONTENT_DIR:
                break
            d = d.parent

    # Collect all current content files
    content_files = {
        str(f): f
        for f in CONTENT_DIR.rglob("*")
        if f.is_file() and FILE_PATTERN.match(f.name)
    }

    # Deletions
    for key in cache:
        if key not in content_files:
            out = _out_path(Path(key))
            if out.exists():
                out.unlink()
                print(f"  deleted: {out}")
            _mark_changed(Path(key))

    # Copy static assets (files that don't match the date pattern)
    for src in CONTENT_DIR.rglob("*"):
        if not src.is_file() or FILE_PATTERN.match(src.name):
            continue
        rel = src.relative_to(CONTENT_DIR)
        out = Path(rel.parts[0]).joinpath(*rel.parts[1:]) if len(rel.parts) > 1 else ROOT_OUT_DIR / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists() or src.stat().st_mtime > out.stat().st_mtime:
            shutil.copy2(src, out)
            print(f"  asset: {rel}")

    # Builds
    built = 0
    skipped = 0
    for key, src in sorted(content_files.items()):
        mtime = str(src.stat().st_mtime)
        new_cache[key] = mtime
        if cache.get(key) == mtime:
            skipped += 1
            continue
        out = _out_path(src)
        _build_file(src, out)
        _mark_changed(src)
        print(f"  built: {src.relative_to(CONTENT_DIR)}")
        built += 1

    for content_dir in changed_dirs:
        _rebuild_index(content_dir)

    CACHE_FILE.write_text(json.dumps(new_cache, indent=2))
    print(f"Done: {built} built, {skipped} skipped, {len(cache) - len([k for k in cache if k in new_cache])} deleted.")


if __name__ == "__main__":
    build()
