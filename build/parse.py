import re, json, sys, unicodedata

src = open(sys.argv[1], encoding='utf-8').read().split('\n')
out_path = sys.argv[2]

def slug(s, n=48):
    s = unicodedata.normalize('NFKD', re.sub(r'[*_`]', '', s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:n] or 'x'

def date_key(s):
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.', s)
    return f"{int(m.group(1))}.{int(m.group(2))}" if m else None

TIME_RE = re.compile(r'(\d{1,2}:\d{2})')
def time_key(t):
    t = re.sub(r'[*~]', '', t).strip()
    m = TIME_RE.search(t)
    if m:
        h, mm = m.group(1).split(':')
        return f"{int(h):02d}:{mm}"
    return t.lower()

# --- split into top-level parts
parts, cur = [], None
for i, line in enumerate(src):
    if line.startswith('# '):
        cur = {'title': line[2:].strip(), 'lines': []}
        parts.append(cur)
    elif cur is None:
        parts.append({'title': '__header__', 'lines': [line]}); cur = parts[-1]
    else:
        cur['lines'].append(line)

def part(prefix):
    return next(p for p in parts if p['title'].startswith(prefix))

def clean_md(lines):
    while lines and lines[0].strip() in ('', '---'): lines = lines[1:]
    while lines and lines[-1].strip() in ('', '---'): lines = lines[:-1]
    return '\n'.join(lines)

data = {'header': clean_md(parts[0]['lines']), 'days': [], 'cities': {}, 'info': []}

# --- Dio 1 flash
flash, bases, notes = {}, '', []
for line in part('DIO 1')['lines']:
    m = re.match(r'^(?:\* )?\*\*(.+?)\*\* — (.*)$', line)
    dk = date_key(m.group(1).replace(' ', '')) if m else None
    if m and dk:
        flash[dk] = {'label': m.group(1), 'text': m.group(2)}
    elif line.startswith('**Baze:**'):
        bases = line
    elif line.strip() and not line.startswith('#'):
        notes.append(line)
data['bases'] = bases
data['flashNotes'] = clean_md(notes)

# --- Dio 2
days, order = {}, []
city_cur, block = None, None
smjestaj = []
for line in part('DIO 2')['lines']:
    if line.startswith('## '):
        h = line[3:].strip()
        dk = date_key(h)
        if h.startswith('SMJEŠTAJ'):
            block = ('smj', None)
        elif dk:
            block = ('transfer', dk)
            days.setdefault(dk, {'rows': [], 'tables': 0, 'transfer': []})
            days[dk]['transfer'].append('**' + h + '**')
        else:
            cid = slug(h)
            city_cur = cid
            data['cities'][cid] = {'id': cid, 'name': re.sub(r'^[^\wČŠŽ]+', '', h).strip(), 'heading': h, 'intro': [], 'extras': None}
            block = ('city', cid)
        continue
    if line.startswith('### '):
        h = line[4:].strip()
        dk = date_key(h)
        d = days.setdefault(dk, {'rows': [], 'tables': 0, 'transfer': []})
        d['heading'] = h
        d['city'] = city_cur
        d['tables'] = 0
        order.append(dk)
        block = ('day', dk)
        d['_in_table'] = False
        continue
    if block is None: continue
    kind, key = block
    if kind == 'smj': smjestaj.append(line)
    elif kind == 'transfer': days[key]['transfer'].append(line)
    elif kind == 'city': data['cities'][key]['intro'].append(line)
    elif kind == 'day':
        d = days[key]
        if line.startswith('|') or line.startswith('---|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r'-*', c) for c in cells) or (len(cells) == 2 and cells == ['', '']):
                if not d['_in_table']:
                    d['tables'] += 1; d['_in_table'] = True
                continue
            if not d['_in_table']:
                d['tables'] += 1; d['_in_table'] = True
            t = cells[0]
            if len(cells) == 3:
                # A/B day: header row is skipped; column A is the main table, column B becomes the alternative (table 2)
                if '🅰' in cells[1]: continue
                a, b = cells[1], cells[2]
                if b.strip().lower() == 'isto': b = a
                d['rows'].append({'time': t.replace('**', ''), 'text': a, 'table': 1})
                if b: d['rows'].append({'time': t.replace('**', ''), 'text': b, 'table': 2})
                continue
            txt = '|'.join(cells[1:])
            d['rows'].append({'time': t.replace('**', ''), 'text': txt, 'table': d['tables']})
        elif line.strip() == '':
            d['_in_table'] = False
data['smjestaj'] = clean_md(smjestaj)
for c in data['cities'].values():
    c['intro'] = clean_md(c['intro'])

# --- Dio 3
dio3 = part('DIO 3')['lines']
sections, cur = [], None
for line in dio3:
    if line.startswith('## '):
        cur = {'h': line[3:].strip(), 'lines': []}; sections.append(cur)
    elif cur is not None:
        cur['lines'].append(line)
    else:
        sections.append({'h': '__intro__', 'lines': [line]}); cur = sections[-1]

def parse_meta(s):
    s = s.strip().strip('*').strip()
    return [x.strip() for x in s.split(' · ') if x.strip()]

def parse_alt(text):
    meta = []
    m = re.search(r'\s*·\s*\*(⏱[^*]*)\*\s*$', text)
    if m:
        meta = parse_meta(m.group(1)); text = text[:m.start()]
    t = re.match(r'^\*\*(.+?)\*\*\s*(?:[—–-]\s*)?(.*)$', text, re.S)
    if t:
        return {'title': t.group(1), 'text': t.group(2).strip(), 'meta': meta}
    return {'title': '', 'text': text, 'meta': meta}

def parse_slot(head, lines):
    tpart, _, title = head.partition(' — ')
    if not title and tpart.lstrip('⏰ ').lower().startswith('večer prije'):
        title, tpart = tpart.lstrip('⏰ ').strip(), 'Večer prije'
    s = {'timeLabel': tpart.strip(), 'key': time_key(tpart.lstrip('⏰ ').strip()), 'title': title.strip() or tpart.strip(), 'meta': [], 'body': '', 'alts': [], 'altNotes': []}
    body, after, i = [], [], 0
    while i < len(lines) and lines[i].strip() == '': i += 1
    if i < len(lines) and lines[i].strip().startswith('*⏱'):
        s['meta'] = parse_meta(lines[i]); i += 1
    mode = 'body'
    for line in lines[i:]:
        if re.match(r'^\*\*↔ Zamjene', line):
            mode = 'alts'
            note = re.sub(r'^\*\*↔ Zamjene[^*]*\*\*\s*', '', line).strip()
            if note: s['altNotes'].append(note)
            continue
        if mode == 'body':
            body.append(line); continue
        if line.startswith('- **'):
            s['alts'].append(line[2:]); mode = 'alts'
        elif line.startswith('  ') and line.strip().startswith('- ') and s['alts']:
            s['alts'][-1] += '\n' + line[2:]
        elif line.startswith('- '):
            s['altNotes'].append(line[2:])
        elif line.strip() == '':
            continue
        else:
            after.append(line)
    out = []
    for a in s['alts']:
        first, *rest = a.split('\n')
        alt = parse_alt(first)
        if rest: alt['text'] += '\n' + '\n'.join(rest)
        out.append(alt)
    s['alts'] = out
    s['body'] = clean_md(body)
    s['after'] = clean_md(after)
    return s

decisions = []
for sec in sections:
    h = sec['h']
    if h.startswith('⏰ ODLUKE'):
        rows = [l for l in sec['lines'] if l.startswith('|')][2:]
        intro = clean_md([l for l in sec['lines'] if not l.startswith('|')])
        for r in rows:
            c = [x.strip() for x in r.strip().strip('|').split('|')]
            decisions.append({'id': 'd-' + slug(c[0] + ' ' + c[1], 60), 'day': c[0], 'what': c[1], 'options': c[2], 'todo': c[3], 'date': date_key(c[0])})
        data['decisionsIntro'] = intro
        continue
    if h.startswith('🧱'):
        # attach to city of the last parsed day
        last = data['days'][-1] if data['days'] else None
        cid = days[last['date']]['city'] if last else None
        data['cities'][cid]['extras'] = {'heading': h, 'md': clean_md(sec['lines'])}
        continue
    dk = date_key(h)
    if not dk:
        continue
    # day
    sub, curs = [], {'h': None, 'lines': []}
    sub.append(curs)
    for line in sec['lines']:
        if line.startswith('### '):
            curs = {'h': line[4:].strip(), 'lines': []}; sub.append(curs)
        else:
            curs['lines'].append(line)
    intro_lines = sub[0]['lines']
    night = ''
    for j, l in enumerate(intro_lines):
        if l.startswith('**Noćenje') or l.startswith('**Plan:') is False and False:
            pass
    nl = [l for l in intro_lines if l.startswith('**Noćenje')]
    night = nl[0].strip('*') if nl else ''
    intro_lines = [l for l in intro_lines if not l.startswith('**Noćenje')]
    stay = []
    si = next((j for j, l in enumerate(intro_lines) if l.startswith('🏨')), None)
    if si is not None:
        j, seen_list = si + 1, False
        while j < len(intro_lines):
            l = intro_lines[j]
            if l.startswith('- '): seen_list = True
            elif l.strip() and seen_list: break
            j += 1
        stay = intro_lines[si:j]
        intro_lines = intro_lines[:si] + intro_lines[j:]
    day = {'date': dk, 'd3heading': h, 'night': night, 'intro': clean_md(intro_lines), 'stay': clean_md(stay), 'slots': [], 'plans3': [], 'info': [], 'triggers': ''}
    for s in sub[1:]:
        sh = s['h']
        if 'OKIDAČI' in sh:
            day['triggers'] = clean_md(s['lines'])
        elif sh.startswith('🅱️') or sh.startswith('Srednji put'):
            meta = []
            ls = s['lines'][:]
            while ls and ls[0].strip() == '': ls.pop(0)
            if ls and ls[0].strip().startswith('*⏱'):
                meta = parse_meta(ls.pop(0))
            slot = parse_slot('x — x', ls)
            day['plans3'].append({'title': sh.lstrip('🅱️ ').strip(), 'meta': meta, 'md': slot['body'], 'alts': slot['alts'], 'after': slot['after']})
        else:
            stripped = sh.lstrip('⏰ ').strip()
            if TIME_RE.match(stripped.lstrip('~')) or stripped.lower().startswith('večer prije'):
                day['slots'].append(parse_slot(sh, s['lines']))
            else:
                day['info'].append({'title': sh, 'md': clean_md(s['lines']), 'top': sh.startswith('⏰ ODLUKE')})
    data['days'].append(day)

# --- merge Dio 2 rows with Dio 3 slots
PLANS = {
    '20.10': [{'match': None, 'label': 'Verzija 🅱️', 'altTable': 2, 'replaces': 'all'}],
    '23.10': [{'match': 'Delpino', 'label': 'Plan B · Delpino', 'replaces': ['14:00', '15:30']}],
    '24.10': [{'match': 'Plan C', 'label': 'Plan C · Gangneung', 'replaces': ['06:35', '06:55', '08:00', '09:36', '12:30', '13:30', '14:30', '17:00']}],
    '27.10': [{'match': 'Eonyang', 'label': 'Plan B · Eonyang', 'replaces': ['10:00']}],
    '30.10': [{'match': 'Banpo', 'label': 'Plan B · Banpo', 'replaces': ['15:30', '18:00', '19:15', '20:30']},
              {'match': 'Srednji put', 'label': 'Srednji put', 'replaces': ['15:30', '18:00', '19:15', '20:30']}],
    '31.10': [{'match': 'Hongdae', 'label': 'Plan B · Hongdae', 'replaces': ['17:30', '18:00', '19:15', '20:30', '21:15', '22:00']}],
    '2.11': [{'match': 'jumbo', 'label': 'Rezerva · jumbo taksi', 'replaces': ['07:25', '07:45']}],
}
ALT_RE = re.compile(r'\s*·?\s*\*↔[^*]*\*')
report = []
for day in data['days']:
    d2 = days.get(day['date'], {'rows': [], 'transfer': []})
    day['heading'] = d2.get('heading', day['d3heading'])
    day['city'] = d2.get('city')
    day['transfer'] = clean_md(d2.get('transfer', []))
    day['flash'] = flash.get(day['date'])
    main_rows = [r for r in d2['rows'] if r['table'] == 1 and not r['time'].startswith('🅱️')]
    brows = [r for r in d2['rows'] if r['time'].startswith('🅱️')]
    alt_rows = [r for r in d2['rows'] if r['table'] == 2]
    def mkrow(r):
        return {'time': r['time'], 'key': time_key(r['time']), 'text': ALT_RE.sub('', r['text']).strip(), 'altHint': bool(ALT_RE.search(r['text'])), 'slot': None}
    rows = [mkrow(r) for r in main_rows]
    used = set()
    last_idx = -1
    for si, s in enumerate(day['slots']):
        idx = next((i for i, r in enumerate(rows) if r['slot'] is None and r['key'] == s['key'] and i not in used), None)
        if idx is None:
            # A/B days use time ranges ("Jutro 09:30–11:45"); attach the slot to the range row that names it
            w = re.sub(r'[*_]', '', s['title']).split()[0].lower()
            idx = next((i for i, r in enumerate(rows) if r['slot'] is None and '–' in r['time'] and len(w) > 3 and w in re.sub(r'[*_]', '', r['text']).lower()), None)
            if idx is not None:
                rows[idx]['slot'] = si; used.add(idx); last_idx = idx
                continue
        if idx is None:
            newrow = {'time': s['timeLabel'].lstrip('⏰ '), 'key': s['key'], 'text': '**' + s['title'] + '**', 'altHint': False, 'slot': si, 'd3only': True}
            pos = last_idx + 1
            if re.fullmatch(r'\d\d:\d\d', s['key']):
                later = [i for i, r in enumerate(rows) if re.fullmatch(r'\d\d:\d\d', r['key']) and r['key'] > s['key']]
                if later: pos = later[0]
            rows.insert(pos, newrow)
            used = {i + 1 if i >= pos else i for i in used}
            last_idx = pos
            report.append(f"{day['date']}: D3-only slot '{s['timeLabel']} {s['title']}'")
        else:
            rows[idx]['slot'] = si; used.add(idx); last_idx = idx
    for r in rows:
        if r['slot'] is None:
            report.append(f"{day['date']}: D2-only row '{r['time']}'")
    day['rows'] = rows
    # plans
    plans = []
    cfg = PLANS.get(day['date'], [])
    for c in cfg:
        p = {'label': c['label'], 'replaces': c['replaces'], 'summary': '', 'detail': None, 'rows': None}
        if c.get('altTable') and not alt_rows:
            continue
        if c.get('altTable'):
            ar = [mkrow(r) for r in alt_rows]
            for r in ar:
                m = re.search(r'\*\*(.+?)\*\*', r['text'])
                w = m.group(1).split()[0].lower() if m else ''
                si = next((i for i, s in enumerate(day['slots']) if w and w in s['title'].lower()), None)
                r['slot'] = si
            p['rows'] = ar
        else:
            p3 = next((x for x in day['plans3'] if c['match'].lower() in x['title'].lower()), None)
            p['detail'] = p3
            b = next((r for r in brows if c['match'].lower() in r['text'].lower()), None)
            if b: p['summary'] = b['text']; brows.remove(b)
            if not p3: report.append(f"{day['date']}: plan '{c['label']}' has no D3 section")
            if p3: day['plans3'].remove(p3)
        plans.append(p)
    for b in brows: report.append(f"{day['date']}: unassigned B row {b['text'][:50]}")
    for p in day['plans3']: report.append(f"{day['date']}: unassigned D3 plan {p['title']}")
    day['plans'] = plans
    day['leftPlans3'] = day.pop('plans3')
    day['decisions'] = [x['id'] for x in decisions if x['date'] == day['date']]

# Pre-trip notes from Dio 1 fold into the decisions list; a note that repeats an existing decision is merged into it.
MERGE = {'Prijevoz Sokcho': 'Vlak', 'Rezervacije': None, 'Seoraksan': ('Čet 22.10.', 'Seoraksan: uspon i žičara'),
         'Drone show': ('Sub 31.10.', 'Drone show i Halloween'), 'Let 2.': ('Pon 2.11.', 'Let KE937')}
for line in data['flashNotes'].split('\n'):
    m = re.match(r'^- \*\*(.+?):\*\*\s*(.*)$', line)
    if not m: continue
    label, text = m.group(1), m.group(2)
    rule = next((v for k, v in MERGE.items() if label.startswith(k)), None)
    if rule is None and label.startswith('Rezervacije'):
        tgt = next(x for x in decisions if x['what'].startswith('Večer') and x['day'].startswith('Pet 30'))
        tgt['todo'] += ' · Balon Flying Suwon ovisi o vremenu'
        continue
    if isinstance(rule, str):
        tgt = next(x for x in decisions if rule in x['what'])
        tgt['todo'] += ' · ' + text
    elif rule:
        day, what = rule
        decisions.append({'id': 'd-' + slug(day + ' ' + what, 60), 'day': day, 'what': what, 'options': '—', 'todo': text, 'date': date_key(day)})
data['decisions'] = decisions

# --- Dio 4 and Dodaci
def rows_of(lines):
    return [[x.strip() for x in l.strip().strip('|').split('|')] for l in lines if l.startswith('|')]
for p in parts:
    t = p['title']
    if t.startswith('DODATAK A'):
        rs = rows_of(p['lines'])[2:]
        data['reservations'] = [{'id': 'r-' + slug(r[1], 60), 'when': r[0], 'what': r[1], 'detail': r[2], 'who': r[3]} for r in rs if r[0].strip() != '✅']
        data['reservationsIntro'] = clean_md([l for l in p['lines'] if not l.startswith('|')])
    elif t.startswith('DIO 4') or t.startswith('DODATAK'):
        data['info'].append({'id': slug(t.split('—')[0]), 'title': t, 'md': clean_md(p['lines'])})

import os
wip = os.path.join(os.path.dirname(sys.argv[1]), 'KorejaWIP.md')
if os.path.exists(wip):
    wl = open(wip, encoding='utf-8').read().split('\n')
    data['info'].append({'id': 'wip', 'title': wl[0].lstrip('# ').strip(), 'md': clean_md(wl[1:])})
ids = [r['id'] for r in data['reservations']] + [d['id'] for d in decisions]
assert len(ids) == len(set(ids)), 'dup ids'
json.dump(data, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
print('\n'.join(report))
print('days', len(data['days']), 'decisions', len(decisions), 'res', len(data['reservations']), 'cities', list(data['cities']))
for c in data['cities'].values(): print(c['id'], bool(c['extras']))
