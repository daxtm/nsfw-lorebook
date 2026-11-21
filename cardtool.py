#!/usr/bin/env python3
"""cardtool.py - build, unpack, lint and read SillyTavern character cards.

  python3 cardtool.py build  NAME.card.txt [--image art.png] [--crop] [--out-dir DIR]
  python3 cardtool.py unpack CARD.png|CARD.json [--out NAME.card.txt]
  python3 cardtool.py lint   NAME.card.txt|CARD.png|CARD.json [--profile small|local|frontier] [--scenario]
  python3 cardtool.py read   CARD.png                       # print the embedded JSON
  python3 cardtool.py book   NAME.card.txt|CARD.* --out BOOK.json   # standalone World Info file

Writes Character Card V2 JSON (with V1 mirror fields, like SillyTavern exports) and a PNG
carrying it in tEXt 'chara' (V2) and 'ccv3' (V3) chunks. Stdlib only; Pillow is used only to
convert non-PNG art or when --crop is given.
"""
import argparse, base64, hashlib, io, json, re, struct, sys, zlib
from pathlib import Path

SEC = re.compile(r'^=== *([a-z_]+) *=== *$')
TEXT = ['description', 'personality', 'scenario', 'first_mes', 'mes_example', 'creator_notes',
        'system_prompt', 'post_history_instructions', 'depth_prompt']
POS = {'before_char': 0, 'after_char': 1, 'an_top': 2, 'an_bottom': 3, 'at_depth': 4, 'em_top': 5, 'em_bottom': 6}
ROLES = {'system': 0, 'user': 1, 'assistant': 2}
LOGIC = {'and_any': 0, 'not_all': 1, 'not_any': 2, 'and_all': 3}
MATCH = {'persona': 'match_persona_description', 'description': 'match_character_description',
         'personality': 'match_character_personality', 'depth_prompt': 'match_character_depth_prompt',
         'scenario': 'match_scenario', 'creator_notes': 'match_creator_notes'}
# entry header key -> (extensions key, default); written only when different from default
ENTRY_OPT = {'probability': ('probability', 100), 'sticky': ('sticky', 0), 'cooldown': ('cooldown', 0),
             'delay': ('delay', 0), 'group': ('group', ''), 'group_weight': ('group_weight', 100),
             'group_override': ('group_override', False), 'scan_depth': ('scan_depth', None),
             'case_sensitive': ('case_sensitive', None), 'match_whole_words': ('match_whole_words', None),
             'use_group_scoring': ('use_group_scoring', None), 'prevent_recursion': ('prevent_recursion', False),
             'exclude_recursion': ('exclude_recursion', False), 'delay_until_recursion': ('delay_until_recursion', False),
             'vectorized': ('vectorized', False), 'automation_id': ('automation_id', ''), 'ignore_budget': ('ignore_budget', False)}
BOOL_OPT = {'group_override', 'prevent_recursion', 'exclude_recursion', 'vectorized', 'ignore_budget'}
TRI_OPT = {'case_sensitive', 'match_whole_words', 'use_group_scoring'}
PNG_SIG = b'\x89PNG\r\n\x1a\n'


def die(msg):
    sys.exit(f'error: {msg}')


# ---------- source format ----------
def kv(lines, where):
    out = {}
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        if ':' not in s:
            die(f'{where}: expected "key: value", got {s[:60]!r}')
        k, v = s.split(':', 1)
        out[k.strip().lower()] = v.strip()
    return out


def flag(v, default=False):
    if v is None or v == '':
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('true', 'yes', 'y', '1', 'on')


def tri(v):
    return None if v in (None, '') else flag(v)


def num(v, default=None):
    if v in (None, ''):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        die(f'expected a number, got {v!r}')
    return int(f) if f.is_integer() else f


def split_keys(s):
    """Comma-separated keys; /regex/flags items may contain commas."""
    out, cur, in_re = [], '', False
    s = s or ''
    for i, c in enumerate(s):
        if c == '/' and not in_re and not cur.strip():
            in_re = True
        elif c == '/' and in_re and s[i - 1] != '\\':
            in_re = False
        elif c == ',' and not in_re:
            out.append(cur.strip())
            cur = ''
            continue
        cur += c
    out.append(cur.strip())
    return [k for k in out if k]


def parse_src(text):
    secs, cur = [], None
    for n, ln in enumerate(text.splitlines(), 1):
        m = SEC.match(ln)
        if m:
            cur = (m.group(1), [])
            secs.append(cur)
            continue
        if cur is None:
            if ln.strip():
                die(f'line {n}: text before the first "=== section ===" header')
            continue
        cur[1].append(ln)
    src = {'meta': {}, 'alts': [], 'groups': [], 'entries': [], 'extra': {}}
    for name, lines in secs:
        body = '\n'.join(lines).strip('\n')
        if name == 'meta':
            src['meta'].update(kv(lines, 'meta'))
        elif name in TEXT:
            if name in src:
                die(f'section "{name}" appears twice')
            src[name] = body
        elif name == 'alternate_greeting':
            src['alts'].append(body)
        elif name == 'group_greeting':
            src['groups'].append(body)
        elif name == 'lorebook_entry':
            stripped = [l.strip() for l in lines]
            if '---' not in stripped:
                die(f'lorebook_entry #{len(src["entries"]) + 1}: needs a "---" line between settings and content')
            i = stripped.index('---')
            e = kv(lines[:i], f'lorebook_entry #{len(src["entries"]) + 1}')
            e['content'] = '\n'.join(lines[i + 1:]).strip('\n')
            src['entries'].append(e)
        elif name == 'extra_json':
            src['extra'] = json.loads(body) if body.strip() else {}
        else:
            die(f'unknown section "{name}"')
    if not src['meta'].get('name'):
        die('the meta section needs "name: ..."')
    return src


def build_entry(e, i):
    where = f'lorebook entry #{i + 1} ({e.get("comment") or e.get("keys", "")[:30]})'
    pos = (e.get('position') or 'after_char').lower()
    role = (e.get('role') or 'system').lower()
    logic = (e.get('logic') or 'and_any').lower()
    for val, table, label in ((pos, POS, 'position'), (role, ROLES, 'role'), (logic, LOGIC, 'logic')):
        if val not in table:
            die(f'{where}: {label} must be one of {", ".join(table)}')
    ext = {'position': POS[pos], 'depth': num(e.get('depth'), 4), 'role': ROLES[role],
           'selectiveLogic': LOGIC[logic], 'display_index': i, 'useProbability': True,
           'triggers': split_keys(e.get('triggers', '')), 'outlet_name': ''}
    for k, (xk, default) in ENTRY_OPT.items():
        v = e.get(k)
        if k in BOOL_OPT:
            ext[xk] = flag(v, default)
        elif k in TRI_OPT:
            ext[xk] = tri(v)
        elif isinstance(default, str):
            ext[xk] = v if v is not None else default
        else:
            ext[xk] = num(v, default)
    for src_name in split_keys(e.get('match_sources', '')):
        if src_name not in MATCH:
            die(f'{where}: match_sources items must be among {", ".join(MATCH)}')
        ext[MATCH[src_name]] = True
    for xk in MATCH.values():
        ext.setdefault(xk, False)
    if e.get('extra'):
        ext.update(json.loads(e['extra']))
    keys = split_keys(e.get('keys', ''))
    constant = flag(e.get('constant'))
    if not keys and not constant and not ext.get('vectorized'):
        print(f'warning: {where} has no keys and is not constant; it will never fire', file=sys.stderr)
    return {'id': i, 'keys': keys, 'secondary_keys': split_keys(e.get('secondary_keys', '')),
            'comment': e.get('comment', ''), 'content': e.get('content', ''), 'constant': constant,
            'selective': True, 'insertion_order': num(e.get('order'), 100), 'enabled': flag(e.get('enabled'), True),
            'position': 'before_char' if POS[pos] == 0 else 'after_char', 'use_regex': True, 'extensions': ext}


def build_card(src):
    m, extra = src['meta'], src.get('extra') or {}
    ext = dict(extra.get('extensions') or {})
    ext.update({'talkativeness': num(m.get('talkativeness'), 0.5), 'fav': False,
                'world': (m.get('lorebook_name') or f"{m['name']}'s Lorebook") if src['entries'] else '',
                'depth_prompt': {'prompt': src.get('depth_prompt', ''), 'depth': num(m.get('depth_prompt_depth'), 4),
                                 'role': (m.get('depth_prompt_role') or 'system').lower()}})
    data = dict(extra.get('data') or {})
    data.update({k: src.get(k, '') for k in TEXT if k != 'depth_prompt'})
    data.update({'name': m['name'], 'alternate_greetings': src['alts'], 'group_only_greetings': src['groups'],
                 'tags': [t.strip() for t in m.get('tags', '').split(',') if t.strip()],
                 'creator': m.get('creator', ''), 'character_version': m.get('character_version', ''),
                 'extensions': ext})
    if m.get('nickname'):
        data['nickname'] = m['nickname']
    if src['entries']:
        book = {'name': ext['world'], 'extensions': {},
                'entries': [build_entry(e, i) for i, e in enumerate(src['entries'])]}
        for k in ('scan_depth', 'token_budget'):
            if m.get(f'lorebook_{k}'):
                book[k] = num(m[f'lorebook_{k}'])
        if m.get('lorebook_recursive'):
            book['recursive_scanning'] = flag(m['lorebook_recursive'])
        data['character_book'] = book
    card = {k: data[k] for k in ('name', 'description', 'personality', 'scenario', 'first_mes', 'mes_example')}
    card.update({'creatorcomment': data['creator_notes'], 'avatar': 'none', 'talkativeness': ext['talkativeness'],
                 'fav': False, 'tags': data['tags'], 'spec': 'chara_card_v2', 'spec_version': '2.0', 'data': data})
    return card


def to_src(card):
    d = card.get('data') or card
    ext = dict(d.get('extensions') or {})
    dp = ext.pop('depth_prompt', None) or {}
    for k in ('fav', 'world'):
        ext.pop(k, None)
    book = d.get('character_book') or {}
    meta = [('name', d.get('name', '')), ('creator', d.get('creator', '')),
            ('character_version', d.get('character_version', '')), ('tags', ', '.join(d.get('tags') or [])),
            ('talkativeness', ext.pop('talkativeness', card.get('talkativeness', 0.5))),
            ('depth_prompt_depth', dp.get('depth', 4)), ('depth_prompt_role', dp.get('role', 'system'))]
    if d.get('nickname'):
        meta.append(('nickname', d['nickname']))
    if book:
        meta.append(('lorebook_name', book.get('name', '')))
        for k in ('scan_depth', 'token_budget'):
            if book.get(k) is not None:
                meta.append((f'lorebook_{k}', book[k]))
        if 'recursive_scanning' in book:
            meta.append(('lorebook_recursive', book['recursive_scanning']))
    out = ['=== meta ==='] + [f'{k}: {v}' for k, v in meta] + ['']
    for f in TEXT:
        val = dp.get('prompt', '') if f == 'depth_prompt' else d.get(f, '')
        if f == 'creator_notes' and not val:
            val = card.get('creatorcomment', '')
        out += [f'=== {f} ===', val or '', '']
    for g in d.get('alternate_greetings') or []:
        out += ['=== alternate_greeting ===', g, '']
    for g in d.get('group_only_greetings') or []:
        out += ['=== group_greeting ===', g, '']
    rpos, rrole, rlogic = ({v: k for k, v in t.items()} for t in (POS, ROLES, LOGIC))
    for e in book.get('entries') or []:
        x = dict(e.get('extensions') or {})
        p = x.pop('position', None)
        p = p if p is not None else (0 if e.get('position') == 'before_char' else 1)
        hdr = [('comment', e.get('comment', '')), ('keys', ', '.join(e.get('keys') or [])),
               ('secondary_keys', ', '.join(e.get('secondary_keys') or [])),
               ('logic', rlogic.get(x.pop('selectiveLogic', 0), 'and_any')), ('position', rpos.get(p, 'after_char')),
               ('depth', x.pop('depth', 4)), ('role', rrole.get(x.pop('role', 0), 'system')),
               ('order', e.get('insertion_order', 100)), ('constant', bool(e.get('constant'))),
               ('enabled', e.get('enabled', True))]
        for k, (xk, default) in ENTRY_OPT.items():
            v = x.pop(xk, default)
            if v not in (None, '') and v != default and not (default == 0 and v == 0):
                hdr.append((k, v))
        sources = [s for s, xk in MATCH.items() if x.pop(xk, False)]
        if sources:
            hdr.append(('match_sources', ', '.join(sources)))
        trig = x.pop('triggers', [])
        if trig:
            hdr.append(('triggers', ', '.join(trig)))
        for k in ('display_index', 'useProbability'):
            x.pop(k, None)
        if not x.get('outlet_name'):
            x.pop('outlet_name', None)
        if x:
            hdr.append(('extra', json.dumps(x, ensure_ascii=False)))
        out += ['=== lorebook_entry ==='] + [f'{k}: {v}' for k, v in hdr] + ['---', e.get('content', ''), '']
    known = set(TEXT) | {'name', 'alternate_greetings', 'group_only_greetings', 'tags', 'creator',
                         'character_version', 'extensions', 'character_book', 'nickname'}
    extra = {}
    xd = {k: v for k, v in d.items() if k not in known}
    if xd:
        extra['data'] = xd
    if ext:
        extra['extensions'] = ext
    if extra:
        out += ['=== extra_json ===', json.dumps(extra, ensure_ascii=False, indent=2), '']
    text = '\n'.join(out)
    clash = [ln for ln in text.splitlines()[1:] if SEC.match(ln) and ln.strip('= ').lower() not in
             set(TEXT) | {'meta', 'alternate_greeting', 'group_greeting', 'lorebook_entry', 'extra_json'}]
    if clash:
        print(f'warning: card text contains section-like lines: {clash[:3]}', file=sys.stderr)
    return text


# ---------- PNG ----------
def png_chunks(buf):
    if buf[:8] != PNG_SIG:
        die('not a PNG file')
    i, out = 8, []
    while i + 8 <= len(buf):
        ln, typ = struct.unpack('>I4s', buf[i:i + 8])
        out.append((typ, buf[i + 8:i + 8 + ln]))
        i += 12 + ln
    return out


def png_join(chunks):
    return PNG_SIG + b''.join(struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
                              for t, d in chunks)


def is_card_chunk(t, d):
    return t == b'tEXt' and d.split(b'\x00', 1)[0].lower() in (b'chara', b'ccv3')


def embed(png, card):
    ch = [(t, d) for t, d in png_chunks(png) if not is_card_chunk(t, d)]
    v3 = dict(card, spec='chara_card_v3', spec_version='3.0')
    new = [(b'tEXt', b'chara\x00' + base64.b64encode(json.dumps(card, ensure_ascii=False).encode('utf-8'))),
           (b'tEXt', b'ccv3\x00' + base64.b64encode(json.dumps(v3, ensure_ascii=False).encode('utf-8')))]
    iend = next(i for i, (t, _) in enumerate(ch) if t == b'IEND')
    return png_join(ch[:iend] + new + ch[iend:])


def extract(png):
    found = {}
    for t, d in png_chunks(png):
        if t == b'tEXt' and b'\x00' in d:
            k, v = d.split(b'\x00', 1)
            found.setdefault(k.decode('latin-1').lower(), v)
    for k in ('ccv3', 'chara'):  # SillyTavern reads ccv3 first
        if k in found:
            return json.loads(base64.b64decode(found[k]).decode('utf-8'))
    die('no chara/ccv3 card data in this PNG')


def placeholder(name, w=512, h=768):
    hsh = hashlib.sha1(name.encode('utf-8')).digest()
    top, bot = hsh[0:3], hsh[3:6]
    rows = []
    for y in range(h):
        t = y / (h - 1)
        px = bytes(int(top[k] * 0.55 * (1 - t) + bot[k] * 0.25 * t + 18) for k in range(3))
        rows.append(b'\x00' + px * w)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    return png_join([(b'IHDR', ihdr), (b'IDAT', zlib.compress(b''.join(rows), 9)), (b'IEND', b'')])


def load_image(path, crop):
    raw = Path(path).read_bytes()
    if raw[:8] == PNG_SIG and not crop:
        return raw
    try:
        from PIL import Image
    except ImportError:
        die('Pillow is needed for non-PNG art or --crop (pip install pillow)')
    im = Image.open(io.BytesIO(raw))
    im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
    if crop:
        w, h = im.size
        if w / h > 2 / 3:
            nw = int(h * 2 / 3)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w * 3 / 2)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        im = im.resize((512, 768), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


def load(path):
    if not Path(path).exists():
        die(f'no such file: {path}')
    b = Path(path).read_bytes()
    if b[:8] == PNG_SIG:
        return extract(b)
    s = b.decode('utf-8-sig')
    if s.lstrip().startswith('{'):
        card = json.loads(s)
        if 'entries' in card and 'data' not in card and 'first_mes' not in card:
            die(f'{path} looks like a World Info file, not a character card')
        return card
    return build_card(parse_src(s))


# ---------- lint ----------
def tok(s):
    return 0 if not s else max(1, round(len(s) / 3.8))


BUDGET = {'small': (800, 1600), 'local': (1200, 2500), 'frontier': (2000, 5000)}
U = r'\{\{user\}\}'
QUOTED = re.compile(r'"[^"\n]*"|“[^”]*”')
USER_WORD = re.compile(U + r"(?!')\s+(?:(\w+ly)\s+)?([A-Za-z']+)", re.I)
VERBS = {'is', 'was', 'has', 'had', 'does', 'did', 'can', 'could', 'will', 'would', 'feels', 'felt', 'thinks',
         'thought', 'says', 'said', 'knows', 'knew', 'wants', 'decides', 'realizes', 'sees', 'saw', 'hears', 'heard',
         'takes', 'took', 'gives', 'gave', 'makes', 'made', 'gets', 'got', 'goes', 'went', 'comes', 'came',
         'sits', 'sat', 'stands', 'stood', 'runs', 'ran', 'holds', 'held', 'lets', 'puts', 'begins', 'began'}
NOT_VERBS = {'towards', 'always', 'afterwards', 'perhaps', 'sometimes', 'whereas', 'unless', 'besides', 'its',
             'his', 'hers', 'yours', 'theirs', 'this', 'thus', 'across', 'news', 'alas', 'less', 'yes'}
YOU_ACT = re.compile(r"\byou\s+(?:\w+ly\s+)?(feel|felt|think|thought|decide|decided|say|said|nod|nodded|smile|smiled|"
                     r"walk|walked|reply|replied|answer|answered|agree|agreed|realize|realized|want|wanted|know|knew|"
                     r"wonder|wondered|sigh|sighed|grin|grinned|laugh|laughed|blush|blushed|reach|reached|step|stepped|"
                     r"turn|turned|freeze|froze|swallow|swallowed|gasp|gasped|shiver|shivered|can't help|find yourself|"
                     r"try to|tried to|take|took|grab|grabbed|follow|followed|enter|entered|sit|sat|stand|stood)\b", re.I)
YOU_SENSE = re.compile(r'\byou\s+(?:\w+ly\s+)?(see|saw|hear|heard|notice|noticed|smell|smelled|spot|spotted)\b', re.I)
USER_SPEAKS = re.compile(r'["”],?\s*(?:' + U + r'|you)\s+(?:say|said|ask|asked|reply|replied|whisper|whispered|'
                         r'shout|shouted|mutter|muttered)\b', re.I)
USER_DESC = re.compile(U + r"\s+(?:is|has|was|looks|wears|works|lives|seems|stands)\b", re.I)
USER_GENDER = re.compile(U + r"(?:'s)?(?:\s+\w+){0,3}?\s+(himself|herself|his own|her own)\b", re.I)
NEG = re.compile(r"\b(never|don't|doesn't|do not|does not|won't|will not|avoid|refuses? to)\b", re.I)
MODEL_INSTR = re.compile(r"\b(do not|don't|never|always|must|avoid|make sure|remember to)\b[^.\n]{0,60}\b(speak|write|act|"
                         r"narrate|describe|respond|reply|roleplay|break character|control|impersonate|mention)\b", re.I)
WPP = re.compile(r'\w[\w ]*\(\s*"[^"]*"\s*(?:\+\s*"[^"]*"\s*)+\)')
PLIST = re.compile(r'\[[^\]\n]{2,40}:\s*[^\]\n]+;[^\]\n]+\]')
SCEN_TIME = re.compile(r"\b(currently|right now|at the moment|today|tonight|this morning|yesterday|just (?:met|arrived|"
                       r"started|walked)|(?:is|are) (?:sitting|standing|walking|waiting|holding|lying|heading))\b", re.I)
HTML_DQ = re.compile(r'<[a-zA-Z][^>]*\s[\w-]+\s*=\s*"')
TAG = re.compile(r'<(/?)([A-Za-z][\w.-]*)(?:\s[^<>]*?)?(/?)>')
VOID = {'br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source', 'start'}
SLOP = [r'shivers? (?:down|up|ran)', r'sent shivers', r'barely above a whisper', r'ministrations', r'eyes sparkl',
        r'with mischief', r'mischievous(?:ly)? glint', r'a mix(?:ture)? of', r'testament to', r'tapestry', r'smirk',
        r'\borbs\b', r"can't help but", r'maybe, just maybe', r'half-lidded', r'padd(?:ed|ing) (?:over|across|toward)',
        r"breath (?:she|he|they|you) didn't know", r'a dance of', r'\bwanton\b', r'pang of', r'unreadable expression',
        r'(?:dripping|laced) with', r'sway(?:ed|ing)? (?:her|his) hips', r'little did', r'thick with tension',
        r'\bpalpable\b', r'\bozone\b', r'electric(?:ity)? (?:between|shot)', r'(?:steel|steeling) (?:her|him)self',
        r'in the grand scheme', r'the weight of (?:her|his|their) words']
PORTABLE = {'char', 'user', 'random', 'pick', 'roll', 'original', 'comment', 'hidden_key', 'reverse'}
ST_ONLY = {'if', 'else', 'setvar', 'getvar', 'addvar', 'incvar', 'decvar', 'hasvar', 'deletevar', 'setglobalvar',
           'getglobalvar', 'addglobalvar', 'incglobalvar', 'decglobalvar', 'hasglobalvar', 'deleteglobalvar',
           'outlet', 'charifnotgroup', 'group', 'groupnotmuted', 'notchar', 'idle_duration', 'idleduration', 'time',
           'date', 'weekday', 'isotime', 'isodate', 'datetimeformat', 'timediff', 'lastmessage', 'lastmessageid',
           'lastusermessage', 'lastcharmessage', 'persona', 'description', 'personality', 'scenario', 'mesexamples',
           'mesexamplesraw', 'charprompt', 'charinstruction', 'chardepthprompt', 'charfirstmessage', 'model', 'newline',
           'space', 'noop', 'trim', 'input', 'banned', 'summary', 'maxprompt', 'charversion', 'charcreatornotes',
           'currentswipeid', 'lastswipeid', 'ismobile'}
HARD_MINOR = re.compile(r'\b(lolis?|lolicon|shota(?:con)?|underage|under-age|pre-?teens?|(?:1[0-7]|[1-9])[- ]years?[- ]old|'
                        r'aged? 1[0-7])\b', re.I)
SOFT_MINOR = re.compile(r'\b(child|children|kids?|minors?|teens?|teenage(?:d|r|rs)?|schoolgirl|schoolboy|'
                        r'(?:elementary|middle|high) school(?:er)?)\b', re.I)
ADULT_AGE = re.compile(r'\b(?:(?:1[89]|[2-9]\d|\d{3,})[- ]years?[- ]old|aged? (?:1[89]|[2-9]\d)|in (?:her|his|their) '
                       r'(?:twenties|thirties|forties|fifties|sixties)|adult)\b', re.I)


def narration(s):
    return QUOTED.sub('""', s or '')


def snippet(s, m, width=70):
    a = max(0, m.start() - 25)
    return ' '.join(s[a:a + width].split())


def user_actions(text):
    """Yield excerpts where narration writes {{user}}'s actions, speech, or feelings."""
    nar = narration(text)
    for m in USER_WORD.finditer(nar):
        w = m.group(2).lower()
        if w in NOT_VERBS:
            continue
        if w in VERBS or (w.endswith('ed') and len(w) > 4) or (
                w.endswith('s') and len(w) > 3 and not w.endswith(('ss', 'us', 'is', 'ous'))):
            yield snippet(nar, m)
    for m in YOU_ACT.finditer(nar):
        yield snippet(nar, m)
    for m in USER_SPEAKS.finditer(text or ''):
        yield snippet(text, m)


def macros(text):
    for m in re.finditer(r'\{\{([^{}]*)\}\}', text or ''):
        inner = m.group(1).strip()
        if inner.startswith(('//', '/', '#')):
            continue
        if inner[:1] in '.$':
            yield 'shorthand', inner
            continue
        yield re.split(r'::|:|\s', inner, maxsplit=1)[0].lower(), inner


def tag_balance(text):
    stack, problems = [], []
    for m in TAG.finditer(re.sub(r'<!--.*?-->', '', text or '', flags=re.S)):
        close, name, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if name in VOID or selfclose:
            continue
        if not close:
            stack.append(name)
        elif stack and stack[-1] == name:
            stack.pop()
        elif name in stack:
            while stack and stack[-1] != name:
                problems.append(f'<{stack.pop()}> not closed')
            stack.pop()
        else:
            problems.append(f'</{name}> without opener')
    return problems + [f'<{n}> not closed' for n in stack]


def lint(card, profile='local', scenario=False):
    d = card.get('data') or card
    ext = d.get('extensions') or {}
    dp = ext.get('depth_prompt') or {}
    name = (d.get('name') or '').strip()
    first = name.split()[0] if name else ''
    desc, pers, scen = d.get('description', ''), d.get('personality', ''), d.get('scenario', '')
    examples, notes = d.get('mes_example', ''), d.get('creator_notes') or card.get('creatorcomment', '')
    sysp, phi, dpt = d.get('system_prompt', ''), d.get('post_history_instructions', ''), dp.get('prompt', '')
    alts = d.get('alternate_greetings') or []
    greetings = [('first_mes', d.get('first_mes', ''))] + [(f'alternate_greeting[{i + 1}]', g) for i, g in enumerate(alts)]
    book = d.get('character_book') or {}
    entries = book.get('entries') or []
    tags = [t.lower() for t in (d.get('tags') or [])]
    issues = []

    def add(sev, field, msg):
        issues.append((sev, field, msg))

    # budget
    perm = {'name': tok(name), 'description': tok(desc), 'personality': tok(pers), 'scenario': tok(scen),
            'depth_prompt': tok(dpt), 'system_prompt': tok(sysp), 'post_history': tok(phi),
            'constant lorebook': sum(tok(e.get('content')) for e in entries if e.get('constant') and e.get('enabled', True))}
    total = sum(perm.values())
    limit = BUDGET[profile][1 if scenario else 0]
    if total > limit:
        add('WARN', 'tokens', f'permanent tokens ~{total} exceed the {profile} {"scenario" if scenario else "character"} '
                              f'budget of {limit}; trim or move conditional detail into lorebook entries')
    # required
    if not name:
        add('ERROR', 'name', 'name is empty')
    if '{{' in name or '<' in name:
        add('ERROR', 'name', 'name must be plain text (macros and tags here break {{char}})')
    if not desc.strip():
        add('WARN', 'description', 'description is empty')
    if not d.get('first_mes', '').strip():
        add('WARN', 'first_mes', 'no first message; the greeting is the strongest style signal')
    # description-like permanent fields
    if first and re.search(r'\{\{char\}\}\s+is\s+(?:named\s+|called\s+)?' + re.escape(first) + r'\b', desc, re.I):
        add('WARN', 'description', '"{{char}} is <name>" reads as "<name> is <name>" to the model')
    for fld, txt in (('description', desc), ('personality', pers)):
        for m in USER_DESC.finditer(txt):
            add('WARN', fld, f'describes {{{{user}}}} (belongs in the user\'s persona): "{snippet(txt, m)}"')
    for m in USER_DESC.finditer(scen):
        add('INFO', 'scenario', f'defines {{{{user}}}}; keep it to their role in the premise: "{snippet(scen, m)}"')
    for fld, txt in (('description', desc), ('scenario', scen), ('first_mes', d.get('first_mes', ''))):
        for m in USER_GENDER.finditer(txt):
            add('INFO', fld, f'gendered wording for {{{{user}}}}; keep the user gender-neutral: "{snippet(txt, m)}"')
    negs = [snippet(desc, m) for m in NEG.finditer(narration(desc))]
    if len(negs) > 3:
        add('WARN', 'description', f'{len(negs)} negative phrasings; state what {{{{char}}}} does instead, '
                                   f'e.g. "{negs[0]}"')
    for fld, txt in (('description', desc), ('personality', pers), ('scenario', scen)):
        for m in MODEL_INSTR.finditer(narration(txt)):
            add('WARN', fld, f'instruction to the model in a character field (system prompt/PHI territory): '
                             f'"{snippet(txt, m)}"')
        if WPP.search(txt):
            add('WARN', fld, 'W++ syntax detected; convert to delimited prose')
        if re.search(r'\{\{random\b', txt, re.I):
            add('INFO', fld, '{{random}} re-rolls every generation; use {{pick}} for facts that must stay stable')
    if PLIST.search(desc):
        add('INFO', 'description', 'PList detected: fine for small models or the depth note; default style is prose')
    for fld, txt in (('description', desc), ('depth_prompt', dpt), ('system_prompt', sysp),
                     ('post_history_instructions', phi)):
        for p in tag_balance(txt):
            add('WARN', fld, f'tag structure: {p}')
    if pers and tok(pers) > 60:
        add('INFO', 'personality', f'~{tok(pers)} tokens; keep this to one line (or empty) and put detail in description')
    if pers and first and first.lower() not in pers.lower() and '{{char}}' not in pers.lower():
        add('INFO', 'personality', 'SillyTavern inserts this field raw, with no label: write a sentence that names {{char}}')
    for m in SCEN_TIME.finditer(scen):
        add('WARN', 'scenario', f'moment-to-moment wording; scenario must stay true for the whole chat and every '
                                f'greeting: "{snippet(scen, m)}"')
    # greetings
    povs = set()
    for fld, g in greetings:
        if not g.strip():
            continue
        t = tok(g)
        if t < 60:
            add('INFO', fld, f'~{t} tokens; very short greetings produce very short replies')
        elif t > 700:
            add('WARN', fld, f'~{t} tokens; long greetings bloat every reply and the opening context')
        for ex in dict.fromkeys(user_actions(g)):
            add('WARN', fld, f'writes for {{{{user}}}} (action, speech or feeling): "{ex}"')
        for m in YOU_SENSE.finditer(narration(g)):
            add('INFO', fld, f'perception for {{{{user}}}}; fine for scene-setting, keep it observable: "{snippet(g, m)}"')
        tail = g.strip()[-300:]
        if '?' not in tail and not re.search(r'["”]\s*$', g.strip()) and '"' not in tail[-120:]:
            add('INFO', fld, 'ends on narration with no question or line of dialogue; make sure it leaves a hook')
        if HTML_DQ.search(g):
            add('WARN', fld, 'HTML attribute in double quotes; SillyTavern treats " as dialogue, use single quotes')
        nar = narration(g)
        you, usr = len(re.findall(r'\byou\b', nar, re.I)), len(re.findall(U, nar))
        if you or usr:
            povs.add('second person' if you >= usr else 'third person {{user}}')
    if len(povs) > 1:
        add('INFO', 'greetings', 'greetings address {{user}} inconsistently (second vs third person)')
    # examples
    if examples.strip():
        if '<START>' not in examples:
            add('WARN', 'mes_example', 'missing <START> separators between example blocks')
        blocks = [b.strip() for b in re.split(r'<START>', examples, flags=re.I) if b.strip()]
        for bi, b in enumerate(blocks, 1):
            if not re.match(r'^(\{\{user\}\}|\{\{char\}\}|<user>|<bot>|[^\n:]{1,40}):', b, re.I):
                add('WARN', 'mes_example', f'block {bi} does not start with "{{{{user}}}}:" or "{{{{char}}}}:"')
            for turn in re.split(r'(?m)^(?=\{\{(?:char|user)\}\}:)', b):
                if turn.lower().startswith('{{char}}:'):
                    for ex in dict.fromkeys(user_actions(turn[9:])):
                        add('WARN', 'mes_example', f'block {bi}: {{{{char}}}} turn writes for {{{{user}}}}: "{ex}"')
        if len(blocks) > 6:
            add('INFO', 'mes_example', f'{len(blocks)} blocks; 2-4 well-chosen blocks usually beat many')
    # overrides and depth note
    for fld, txt in (('system_prompt', sysp), ('post_history_instructions', phi)):
        if txt.strip() and '{{original}}' not in txt:
            add('INFO', fld, 'replaces the user\'s own prompt (Prefer Char. Prompt/Instructions is on by default); '
                             'include {{original}} unless the replacement is deliberate')
    if dpt.strip():
        if tok(dpt) > 120:
            add('WARN', 'depth_prompt', f'~{tok(dpt)} tokens; a depth note should be a short anchor (under ~100)')
        if num(dp.get('depth'), 4) < 2:
            add('INFO', 'depth_prompt', 'depth 0-1 is very strong and can make traits repeat every reply')
    if (dp.get('role') or 'system') not in ROLES:
        add('ERROR', 'depth_prompt', 'role must be system, user or assistant')
    # macros
    st_only = set()
    for fld, txt in [('description', desc), ('personality', pers), ('scenario', scen), ('mes_example', examples),
                     ('depth_prompt', dpt), ('system_prompt', sysp), ('post_history_instructions', phi)] + greetings + \
                    [(f'lorebook:{e.get("comment") or i}', e.get('content', '')) for i, e in enumerate(entries)]:
        for mname, inner in macros(txt):
            if mname == 'shorthand':
                add('INFO', fld, f'{{{{{inner}}}}} uses Macros 2.0 shorthand (SillyTavern experimental engine only)')
            elif mname in ST_ONLY:
                st_only.add(mname)
            elif mname not in PORTABLE:
                add('WARN', fld, f'unknown macro {{{{{inner}}}}} (typo?)')
        if re.search(r'<(?:USER|BOT|CHAR)>', txt):
            add('INFO', fld, 'legacy <USER>/<BOT> markers; prefer {{user}}/{{char}}')
    if st_only:
        add('INFO', 'macros', f'SillyTavern-only macros ({", ".join(sorted(st_only))}); mention it in creator_notes')
    # lorebook
    seen = {}
    for i, e in enumerate(entries):
        x = e.get('extensions') or {}
        label = f'lorebook:{e.get("comment") or ", ".join(e.get("keys") or []) or i}'
        keys, content = e.get('keys') or [], e.get('content', '')
        if not e.get('enabled', True):
            add('INFO', label, 'entry is disabled')
        if not keys and not e.get('constant') and not x.get('vectorized'):
            add('WARN', label, 'no keys and not constant: this entry never fires')
        if not content.strip():
            add('ERROR', label, 'entry body is empty')
        elif '[Example:' not in content:
            add('WARN', label, 'entry has no [Example: ...] line')
        if tok(content) > 320:
            add('WARN', label, f'~{tok(content)} tokens; over the 320 cap')
        for k in keys:
            if k.startswith('/'):
                mm = re.match(r'^/(.+)/([a-z]*)$', k)
                try:
                    re.compile(mm.group(1)) if mm else None
                except re.error:
                    mm = None
                if not mm:
                    add('WARN', label, f'invalid regex key {k!r}')
                continue
            if len(k) < 3 or k.lower() in {'the', 'and', 'you', 'she', 'her', 'him', 'his', 'they', 'it', 'eyes',
                                           'hand', 'door', 'room', 'look', 'said', 'yes', 'no'}:
                add('WARN', label, f'key {k!r} is too short or common; it will fire constantly')
            seen.setdefault(k.lower(), []).append(label)
        if tok(content) > 350:
            add('INFO', label, f'~{tok(content)} tokens; split it or tighten (50-200 is typical)')
        subj = [k for k in keys if not k.startswith('/')]
        if subj and content and not any(k.lower() in content.lower() for k in subj):
            add('INFO', label, 'content never names any of its keys; entries should name their subject (standalone)')
        if x.get('position') in (2, 3):
            add('INFO', label, "Author's Note positions only work if the user's Author's Note is enabled")
        for p in tag_balance(content):
            add('WARN', label, f'tag structure: {p}')
    for k, labels in seen.items():
        if len(labels) > 1:
            add('INFO', 'lorebook', f'key {k!r} is shared by {len(labels)} entries')
    # metadata
    if not tags:
        add('INFO', 'tags', 'no tags (genre, tone, rating, source)')
    if not (notes or '').strip():
        add('INFO', 'creator_notes', 'empty: add a pitch, greeting summaries and recommended settings')
    if not alts:
        add('INFO', 'alternate_greetings', 'none; 1-3 distinct alternates add replay value')
    # content safety
    if any('nsfw' in t or 'nsfl' in t or 'explicit' in t for t in tags):
        corpus = '\n'.join([desc, pers, scen, examples, dpt] + [g for _, g in greetings] +
                           [e.get('content', '') for e in entries])
        for m in HARD_MINOR.finditer(corpus):
            add('ERROR', 'content', f'NSFW card references a minor: "{snippet(corpus, m)}"; sexual content '
                                    f'must involve adults only')
        for m in SOFT_MINOR.finditer(corpus):
            add('WARN', 'content', f'NSFW card mentions "{m.group(0)}"; confirm no minor is sexualized: '
                                   f'"{snippet(corpus, m)}"')
        if not ADULT_AGE.search(corpus):
            add('INFO', 'content', 'NSFW card: state the adult age of the character explicitly')
    # slop
    for fld, txt in [('description', desc), ('mes_example', examples)] + greetings:
        for pat in SLOP:
            m = re.search(pat, txt, re.I)
            if m:
                add('WARN', fld, f'cliche phrase "{m.group(0)}" will be copied into replies')
    stats = {'total': total, 'limit': limit, 'perm': perm, 'first_mes': tok(d.get('first_mes', '')),
             'alts': len(alts), 'examples': tok(examples),
             'blocks': len([b for b in re.split(r'<START>', examples, flags=re.I) if b.strip()]),
             'entries': len(entries), 'constant': sum(1 for e in entries if e.get('constant'))}
    return issues, stats


def report(card, profile, scenario):
    issues, s = lint(card, profile, scenario)
    d = card.get('data') or card
    parts = ', '.join(f'{k} {v}' for k, v in s['perm'].items() if v)
    print(f'cardtool lint: {d.get("name")} (profile {profile}, {"scenario" if scenario else "character"} card)')
    print(f'  permanent ~{s["total"]} / {s["limit"]} tokens  [{parts}]')
    print(f'  first_mes ~{s["first_mes"]} | alternate greetings {s["alts"]} | examples ~{s["examples"]} '
          f'({s["blocks"]} blocks) | lorebook {s["entries"]} entries ({s["constant"]} constant)')
    order = {'ERROR': 0, 'WARN': 1, 'INFO': 2}
    for sev, field, msg in sorted(issues, key=lambda x: order[x[0]]):
        print(f'  {sev:<5} {field}: {msg}')
    n = {k: sum(1 for i in issues if i[0] == k) for k in order}
    print(f'  result: {n["ERROR"]} errors, {n["WARN"]} warnings, {n["INFO"]} info (token counts approximate)')
    return n['ERROR']


def to_world(card):
    d = card.get('data') or card
    entries = {}
    for i, e in enumerate((d.get('character_book') or {}).get('entries') or []):
        x = e.get('extensions') or {}
        entries[str(i)] = {
            'uid': i, 'key': e.get('keys', []), 'keysecondary': e.get('secondary_keys', []),
            'comment': e.get('comment', ''), 'content': e.get('content', ''), 'constant': bool(e.get('constant')),
            'vectorized': x.get('vectorized', False), 'selective': e.get('selective', True),
            'selectiveLogic': x.get('selectiveLogic', 0), 'addMemo': bool(e.get('comment')),
            'order': e.get('insertion_order', 100),
            'position': x.get('position', 0 if e.get('position') == 'before_char' else 1),
            'disable': not e.get('enabled', True), 'ignoreBudget': x.get('ignore_budget', False),
            'excludeRecursion': x.get('exclude_recursion', False), 'preventRecursion': x.get('prevent_recursion', False),
            'matchPersonaDescription': x.get('match_persona_description', False),
            'matchCharacterDescription': x.get('match_character_description', False),
            'matchCharacterPersonality': x.get('match_character_personality', False),
            'matchCharacterDepthPrompt': x.get('match_character_depth_prompt', False),
            'matchScenario': x.get('match_scenario', False), 'matchCreatorNotes': x.get('match_creator_notes', False),
            'delayUntilRecursion': x.get('delay_until_recursion', False), 'probability': x.get('probability', 100),
            'useProbability': x.get('useProbability', True), 'depth': x.get('depth', 4),
            'outletName': x.get('outlet_name', ''), 'group': x.get('group', ''),
            'groupOverride': x.get('group_override', False), 'groupWeight': x.get('group_weight', 100),
            'scanDepth': x.get('scan_depth'), 'caseSensitive': x.get('case_sensitive'),
            'matchWholeWords': x.get('match_whole_words'), 'useGroupScoring': x.get('use_group_scoring'),
            'automationId': x.get('automation_id', ''), 'role': x.get('role', 0), 'sticky': x.get('sticky') or None,
            'cooldown': x.get('cooldown') or None, 'delay': x.get('delay') or None, 'triggers': x.get('triggers', []),
            'displayIndex': x.get('display_index', i), 'characterFilter': {'isExclude': False, 'names': [], 'tags': []}}
    return {'entries': entries}


def main():
    ap = argparse.ArgumentParser(description='SillyTavern character card tool')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('src')
    b.add_argument('--image')
    b.add_argument('--crop', action='store_true', help='center-crop and resize the art to 512x768')
    b.add_argument('--out-dir')
    b.add_argument('--profile', default='local', choices=BUDGET)
    b.add_argument('--scenario', action='store_true')
    u = sub.add_parser('unpack')
    u.add_argument('card')
    u.add_argument('--out')
    li = sub.add_parser('lint')
    li.add_argument('card')
    li.add_argument('--profile', default='local', choices=BUDGET)
    li.add_argument('--scenario', action='store_true')
    r = sub.add_parser('read')
    r.add_argument('card')
    bk = sub.add_parser('book')
    bk.add_argument('card')
    bk.add_argument('--out', required=True)
    a = ap.parse_args()

    if a.cmd == 'build':
        srcp = Path(a.src)
        if not srcp.exists():
            die(f'no such file: {a.src}')
        card = build_card(parse_src(srcp.read_text(encoding='utf-8-sig')))
        stem = re.sub(r'\.card$', '', srcp.stem) or 'card'
        out = Path(a.out_dir) if a.out_dir else srcp.parent
        out.mkdir(parents=True, exist_ok=True)
        (out / f'{stem}.json').write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding='utf-8')
        art = load_image(a.image, a.crop) if a.image else placeholder(card['name'])
        png = embed(art, card)
        (out / f'{stem}.png').write_bytes(png)
        if extract(png)['data'] != card['data']:
            die('round-trip check failed: PNG metadata does not match the card')
        print(f'wrote {out / (stem + ".json")} and {out / (stem + ".png")} (chara + ccv3 chunks verified)')
        sys.exit(1 if report(card, a.profile, a.scenario) else 0)
    elif a.cmd == 'unpack':
        text = to_src(load(a.card))
        if a.out:
            Path(a.out).write_text(text, encoding='utf-8')
            print(f'wrote {a.out}')
        else:
            print(text)
    elif a.cmd == 'lint':
        sys.exit(1 if report(load(a.card), a.profile, a.scenario) else 0)
    elif a.cmd == 'read':
        print(json.dumps(load(a.card), ensure_ascii=False, indent=2))
    elif a.cmd == 'book':
        Path(a.out).write_text(json.dumps(to_world(load(a.card)), ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'wrote {a.out}')


if __name__ == '__main__':
    main()
