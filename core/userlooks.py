"""Your own looks for the ApoDesign Style node. Pure Python (no torch).

A look is a small JSON file in a looks folder. Every *.json file in the
folder (and its sub-folders) is read; files and folders whose name starts
with "_" or "." are ignored. One file may hold one look, a list of looks, or
{"looks": [...]}.

    {
      "name": "My neon arcade",
      "description": "Optional one-liner.",
      "extends": "Arcade 16-colour",          optional: start from another look
      "all":       {"palette_preset": "pico8"},   widgets for every node that has them
      "bitmap":    {"method": "blue_noise"},
      "ascii":     {"columns": 90},
      "pixel_art": {"target_width": 200}
    }

Widget names and values are checked against the same specs the nodes use;
mistakes are reported (never raised) and the rest of the look still works.
"""
import hashlib
import json
import os
import re

from . import ascii_specs, bitmap_specs, pixel_specs
from .params import coerce, defaults

SECTIONS = ("bitmap", "ascii", "pixel_art")
SPEC_MAPS = {
    "bitmap": {s.name: s for s in bitmap_specs.SPECS},
    "ascii": {s.name: s for s in ascii_specs.SPECS},
    "pixel_art": {s.name: s for s in pixel_specs.SPECS},
}
PREFIX = "★ "      # user looks show as "★ Name" at the end of the dropdown

# never written into a saved look: they belong to one run, not to a style
NOT_SAVED = {"text_frame", "glyph_mask_output", "ink_mask_output", "transparency",
             "invert_mask", "style_prompt", "prompt_priority"}

_HERE = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.normpath(os.path.join(_HERE, ".."))
DEFAULT_DIR = os.path.join(PKG_DIR, "looks")
CONFIG_FILE = os.path.join(PKG_DIR, "looks_folder.txt")


# --------------------------------------------------------------------------
# where the looks live
# --------------------------------------------------------------------------
def _clean_path(p):
    p = (p or "").strip().strip('"').strip("'").strip()
    return os.path.expanduser(p) if p else ""


def resolve_dir(p):
    """A folder as typed -> absolute path. A bare or relative name such as
    'test1' means a sub-folder of the built-in looks folder (never ComfyUI's
    own working folder)."""
    p = _clean_path(p)
    if not p:
        return ""
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:", p) or p.startswith(("\\\\", "//")):
        return p
    return os.path.normpath(os.path.join(DEFAULT_DIR, p))


def configured_dirs():
    """Folders named in looks_folder.txt (one per line, # = comment) and in the
    APODESIGN_LOOKS environment variable, in that order."""
    out = []
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.strip().startswith("#"):
                    p = resolve_dir(line)
                    if p:
                        out.append(p)
    except OSError:
        pass
    for p in os.environ.get("APODESIGN_LOOKS", "").split(os.pathsep):
        p = resolve_dir(p)
        if p:
            out.append(p)
    return out


def looks_dirs():
    """Every folder that is scanned: the configured ones, then the built-in
    'looks' folder next to the nodes. Only folders that exist."""
    seen, out = set(), []
    for p in configured_dirs() + [DEFAULT_DIR]:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen and os.path.isdir(p):
            seen.add(key)
            out.append(p)
    return out


def save_dir():
    """Where new looks are saved: the first configured folder, else the
    built-in 'looks' folder."""
    cfg = configured_dirs()
    return cfg[0] if cfg else DEFAULT_DIR


def add_dir_to_config(path):
    """Remember `path` in looks_folder.txt so the Style node scans it.
    Returns True when a line was added."""
    path = resolve_dir(path)
    if not path:
        return False
    key = os.path.normcase(os.path.abspath(path))
    if any(os.path.normcase(os.path.abspath(p)) == key for p in configured_dirs()):
        return False
    if key == os.path.normcase(os.path.abspath(DEFAULT_DIR)):
        return False
    try:
        with open(CONFIG_FILE, "a", encoding="utf-8") as f:
            f.write(path + "\n")
        return True
    except OSError:
        return False


def _walk(dirs, top=False):
    """-> [(path, group)]: every look file once. group = the sub-folder the
    file sits in, relative to the folder it was found from ('' at the top),
    joined with '/'. With top=True each listed folder (except the built-in
    'looks' folder) also adds its own name in front, so it shows as a menu.
    A file reachable from two folders keeps the longer group."""
    found = {}
    for d in dirs:
        base = ""
        if top and os.path.normcase(os.path.abspath(d)) != os.path.normcase(os.path.abspath(DEFAULT_DIR)):
            base = os.path.basename(os.path.normpath(d))
        for root, subdirs, names in os.walk(d):
            subdirs[:] = sorted(x for x in subdirs if not x.startswith(("_", ".")))
            rel = os.path.relpath(root, d)
            parts = ([base] if base else []) + ([] if rel == "." else rel.split(os.sep))
            group = "/".join(parts)
            for n in sorted(names):
                if n.lower().endswith(".json") and not n.startswith(("_", ".")):
                    p = os.path.join(root, n)
                    key = os.path.normcase(os.path.realpath(p))
                    if key not in found:
                        found[key] = (p, group)
                    elif len(group) > len(found[key][1]):
                        found[key] = (found[key][0], group)
    return list(found.values())


def _files(dirs):
    return [p for p, _ in _walk(dirs)]


def group_of(path, dirs=None):
    """The menu group a look file falls in ('' = none)."""
    key = os.path.normcase(os.path.realpath(path))
    for p, g in _walk(looks_dirs() if dirs is None else dirs, top=dirs is None):
        if os.path.normcase(os.path.realpath(p)) == key:
            return g
    rel = os.path.relpath(os.path.dirname(os.path.abspath(path)), DEFAULT_DIR)
    return "" if rel == "." or rel.startswith("..") else rel.replace(os.sep, "/")


def display_name(path, name, dirs=None):
    g = group_of(path, dirs)
    return PREFIX + (g + "/" if g else "") + name


def signature(dirs=None):
    """Cheap fingerprint of the looks folders (changes when a file is added,
    edited or removed)."""
    dirs = looks_dirs() if dirs is None else dirs
    sig = []
    for f in _files(dirs):
        try:
            st = os.stat(f)
            sig.append((f, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(sig)


def signature_hash():
    return hashlib.md5(repr(signature()).encode("utf-8", "replace")).hexdigest()


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------
def _load_json(text):
    """Parse JSON, tolerating chatter or a code fence around it."""
    try:
        return json.loads(text), None
    except ValueError:
        pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    a = min(starts) if starts else -1
    end = max(text.rfind("}"), text.rfind("]"))
    if a < 0 or end <= a:
        return None, "no JSON found"
    try:
        return json.loads(text[a:end + 1]), None
    except ValueError as e:
        return None, str(e)


def clean_section(sec, raw, problems, label, quiet_unknown=False):
    """Validate one section's widgets -> {name: value}."""
    out = {}
    if not isinstance(raw, dict):
        problems.append("%s: '%s' must be an object" % (label, sec))
        return out
    smap = SPEC_MAPS[sec]
    for k, v in raw.items():
        spec = smap.get(k)
        if spec is None:
            if not quiet_unknown:
                problems.append("%s: %s has no widget '%s'" % (label, sec, k))
            continue
        if not spec.promptable:
            if not quiet_unknown:
                problems.append("%s: %s.%s can't be set by a look" % (label, sec, k))
            continue
        ok, val = coerce(spec, v)
        if not ok:
            problems.append("%s: %s.%s has a bad value (%r)" % (label, sec, k, v))
            continue
        out[k] = val
    return out


def normalise(item, source, lookup, problems, group=""):
    """One parsed look object -> look dict, or None."""
    label = os.path.basename(source)
    if not isinstance(item, dict):
        problems.append("%s: a look must be an object" % label)
        return None
    name = str(item.get("name") or "").strip() or os.path.splitext(label)[0]
    desc = str(item.get("description") or item.get("desc") or "").strip() or "Your look."
    lk = {"name": PREFIX + (group + "/" if group else "") + name, "desc": desc, "source": source, "user": True,
          "problems": [], "bitmap": {}, "ascii": {}, "pixel_art": {}}
    local = []
    ext = str(item.get("extends") or "").strip()
    if ext:
        parent = lookup.get(ext) or lookup.get(PREFIX + ext)
        if parent is None:
            local.append("%s: extends '%s' - no such look" % (label, ext))
        else:
            for sec in SECTIONS:
                lk[sec] = dict(parent[sec])
    shared = item.get("all")
    if shared is not None:
        if isinstance(shared, dict):
            hits = set()
            for sec in SECTIONS:
                part = clean_section(sec, {k: v for k, v in shared.items() if k in SPEC_MAPS[sec]},
                                     local, label, quiet_unknown=True)
                lk[sec].update(part)
                hits.update(k for k in shared if k in SPEC_MAPS[sec])
            for k in shared:
                if k not in hits:
                    local.append("%s: 'all' has no widget '%s' in any node" % (label, k))
        else:
            local.append("%s: 'all' must be an object" % label)
    for sec in SECTIONS:
        if sec in item:
            lk[sec].update(clean_section(sec, item[sec], local, label))
    for key in item:
        if key not in ("name", "description", "desc", "extends", "all") + SECTIONS:
            local.append("%s: unknown key '%s' (ignored)" % (label, key))
    lk["problems"] = local
    problems.extend(local)
    return lk


def scan(lookup=None, dirs=None):
    """Read all user looks -> (list of look dicts, list of problem strings).
    `lookup` maps built-in look names to look dicts (for "extends")."""
    lookup = dict(lookup or {})
    problems, looks, names = [], [], set()
    for path, group in _walk(looks_dirs() if dirs is None else dirs, top=dirs is None):
        label = os.path.basename(path)
        try:
            with open(path, encoding="utf-8-sig") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            problems.append("%s: can't read (%s)" % (label, e))
            continue
        data, err = _load_json(text)
        if err:
            problems.append("%s: %s" % (label, err))
            continue
        items = data.get("looks") if isinstance(data, dict) and isinstance(data.get("looks"), list) \
            else (data if isinstance(data, list) else [data])
        for item in items:
            lk = normalise(item, path, lookup, problems, group)
            if lk is None:
                continue
            base, n = lk["name"], 2
            while lk["name"] in names:
                lk["name"] = "%s (%d)" % (base, n)
                n += 1
            names.add(lk["name"])
            lookup[lk["name"]] = lk
            lookup.setdefault(PREFIX + lk["name"][len(PREFIX):].rsplit("/", 1)[-1], lk)  # "extends" by bare name
            looks.append(lk)
    return looks, problems


_cache = {"sig": None, "value": None}


def scan_cached(lookup=None):
    """scan(), re-reading the files only when something changed on disk."""
    sig = (signature(), tuple(sorted((lookup or {}).keys())))
    if _cache["sig"] != sig:
        _cache["value"] = scan(lookup)
        _cache["sig"] = sig
    return _cache["value"]


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------
def settings_to_recipe(sec, settings, full=False):
    """A node's `settings` output (dict) -> the widgets worth saving: valid,
    settable, and different from the node's default (all of them if full)."""
    dflt = defaults([SPEC_MAPS[sec][k] for k in SPEC_MAPS[sec]])
    out = {}
    for k, v in (settings or {}).items():
        spec = SPEC_MAPS[sec].get(k)
        if spec is None or not spec.promptable or k in NOT_SAVED:
            continue
        ok, val = coerce(spec, v)
        if ok and (full or val != dflt[k]):
            out[k] = val
    return out


def slug(name):
    s = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" ._-")[:80]
    return s or "look"


def save_look(name, description, sections, extends="", shared=None, overwrite=False,
              directory=None, lookup=None):
    """Write a look file. sections: {"bitmap": {...}, ...}.
    -> (ok, message, path, problems)."""
    name = (name or "").strip()
    if not name:
        return False, "Give the look a name.", "", []
    item = {"name": name}
    if description:
        item["description"] = description
    if extends:
        item["extends"] = extends
    if shared:
        item["all"] = shared
    for sec in SECTIONS:
        if sections.get(sec):
            item[sec] = sections[sec]
    if len(item) <= 1 + bool(description):
        return False, "Nothing to save: connect at least one node's settings, or give look_json.", "", []
    problems = []
    normalise(item, "<new>", lookup or {}, problems)
    directory = resolve_dir(directory) or save_dir()
    path = os.path.join(directory, slug(name) + ".json")
    if os.path.exists(path) and not overwrite:
        return False, "A look file with that name already exists (%s). Turn on overwrite, or pick another name." % path, path, problems
    try:
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(item, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as e:
        return False, "Could not write %s (%s)" % (path, e), path, problems
    return True, "Saved: " + path, path, problems
