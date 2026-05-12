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
    r"^(\d{4}-\d{2}-\d{2})-(.+)\.(txt|md|jpg|jpeg|png|heic|heif|html|pdf)$", re.IGNORECASE
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
        <h1>{title}</h1>
        <div class="meta">{date}</div>

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

    <a class="back" href="/">← back</a>
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
        return Path(parts[0]) / (stem + ".html")


def _section(content_file):
    """Return section name or None for root-level files."""
    parts = content_file.relative_to(CONTENT_DIR).parts
    return parts[0] if len(parts) > 1 else None


def _build_file(src, out):
    m = FILE_PATTERN.match(src.name)
    date_str, slug, ext = m.group(1), m.group(2), m.group(3).lower()
    out.parent.mkdir(exist_ok=True)

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
    else:  # .html — copy as-is
        shutil.copy2(src, out)


def _posts_for_section(section):
    src_dir = CONTENT_DIR / section if section else CONTENT_DIR
    posts = []
    for f in src_dir.iterdir():
        if not f.is_file():
            continue
        m = FILE_PATTERN.match(f.name)
        if not m:
            continue
        date_str, slug, ext = m.group(1), m.group(2), m.group(3).lower()
        out = _out_path(f)
        if ext == "html":
            title = _html_title(f.read_text(encoding="utf-8")) or _title_from_slug(slug)
        else:
            title = _title_from_slug(slug)
        posts.append((date_str, title, out))
    return sorted(posts, reverse=True)


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


def _ensure_section_index(section):
    index_path = Path(section) / "index.html"
    if not index_path.exists():
        index_path.parent.mkdir(exist_ok=True)
        title = section.replace("-", " ").replace("_", " ").capitalize()
        index_path.write_text(
            SECTION_INDEX_TEMPLATE.format(title=title), encoding="utf-8"
        )
    return index_path


def build():
    ROOT_OUT_DIR.mkdir(exist_ok=True)

    cache = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())

    new_cache = {}
    changed_sections = set()

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
            changed_sections.add(_section(Path(key)))

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
        changed_sections.add(_section(src))
        print(f"  built: {src.relative_to(CONTENT_DIR)}")
        built += 1

    # Update indexes only for affected sections
    for section in changed_sections:
        posts = _posts_for_section(section)
        if section is None:
            _update_post_list(INDEX_FILE, posts)
        else:
            index_path = _ensure_section_index(section)
            _update_post_list(index_path, posts)

    CACHE_FILE.write_text(json.dumps(new_cache, indent=2))
    print(f"Done: {built} built, {skipped} skipped, {len(cache) - len([k for k in cache if k in new_cache])} deleted.")


if __name__ == "__main__":
    build()
