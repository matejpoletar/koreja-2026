"""Parses Food.md (meal options per day, neighbourhoods, dish catalog) into data for the meal picker."""
import re

REGION = {'🏛️': 'gyeongju', '🌊': 'busan', '🏯': 'suwon', '🏙️': 'seoul', '✈️': 'seoul'}
HANGUL = re.compile(r'[\uac00-\ud7a3]')
# dishes that can be found almost anywhere, by meal type (matched against catalog names)
FALLBACK = {
    'breakfast': ['Korejski tost', 'Trgovina', 'Food court', 'Kimbap i'],
    'main': ['BBQ buffet', 'Samgyeopsal', 'Chimaek', 'Jjimdak', 'Bibimbap', 'Donkatsu', 'Budae jjigae', 'Jjajangmyeon', 'Kalguksu', 'Bunsik', 'Food court', 'Trgovina'],
    'snack': ['Hotteok', 'Bungeoppang', 'Korejski corn dog', 'Fluffy', 'Dakgangjeong', 'Trgovina'],
    'late': ['Chimaek', 'Hof', 'Pojangmacha', 'Makgeolli', 'Trgovina'],
}

def kind_of(k):
    k = k.upper()
    if 'DORUČAK' in k: return 'breakfast'
    if any(x in k for x in ('KASNO', 'NOĆ')): return 'late'
    if any(x in k for x in ('UŽINA', 'POPODNE', 'PODNE', 'POSLIJE', 'PIKNIK')): return 'snack'
    return 'main'

def date_of(s):
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.', s)
    return f'{int(m.group(1))}.{int(m.group(2))}' if m else None

def dates_in(s):
    out = set()
    for m in re.finditer(r'((?:\d{1,2}\.(?:,| i)\s*)*)(\d{1,2})\.(\d{1,2})\.', s):
        mo = int(m.group(3))
        out.add(f'{int(m.group(2))}.{mo}')
        out.update(f'{int(x)}.{mo}' for x in re.findall(r'(\d{1,2})\.', m.group(1)))
    return sorted(out)

def split_name(name):
    """'Tteokgalbi (떡갈비)' -> ('Tteokgalbi', '떡갈비'); emoji flags are pulled out."""
    price = '💸' in name
    name = re.sub(r'^[^\w(]+', '', name.replace('💸', '')).strip()
    ko = ''
    m = next((m for m in re.finditer(r'\s*\(([^)]*)\)', name) if HANGUL.search(m.group(1))), None)
    if m:
        ko = m.group(1); name = (name[:m.start()] + name[m.end():]).strip()
    return name, ko, price

def split_text(text):
    """Body · ⚠️ warning · 🔎 Naver terms."""
    naver = []
    if '🔎' in text:
        text, n = text.split('🔎', 1)
        naver = [x.strip() for x in n.split(',') if x.strip()]
    warn = ''
    if '⚠️' in text:
        text, warn = text.split('⚠️', 1)
    return text.strip(), warn.strip(), naver

OPT = re.compile(r'^\*\*(🟢|🟡|🔴|☕)\s*(.+?)\*\*(.*)$')

def parse_option(head, rest_lines):
    m = OPT.match(head)
    tag, bold, tail = m.group(1), m.group(2), m.group(3)
    plan = '*(plan)*' in tail
    tail = tail.replace('*(plan)*', '').strip()
    title, _, short = bold.partition(' — ')
    name, ko, price = split_name(title)
    body, warn, naver = split_text(' '.join([tail] + rest_lines).strip())
    return {'tag': {'🟢': 'g', '🟡': 'y', '🔴': 'r', '☕': 'g'}[tag], 'name': name.rstrip('.'), 'ko': ko, 'price': price, 'plan': plan,
            'short': short.strip().rstrip('.'), 'body': body, 'warn': warn, 'naver': naver}

def parse_food(text):
    lines = text.split('\n')
    part = None
    meals, areas, dishes = {}, {}, []
    day = meal = area = dish = None
    region = cat = None
    opt_head, opt_lines = None, []
    stop = False

    def flush_opt():
        nonlocal opt_head, opt_lines
        if opt_head and meal is not None:
            o = parse_option(opt_head, opt_lines)
            if o['tag'] != 'r': meal['options'].append(o)
        opt_head, opt_lines = None, []

    def new_meal(kind, time, where):
        nonlocal meal
        meal = {'kind': kind, 'type': kind_of(kind), 'emoji': '', 'time': time, 'where': where, 'note': '', 'options': []}
        meals.setdefault(day['date'], []).append(meal)

    for line in lines:
        if line.startswith('# '):
            flush_opt()
            t = line[2:]
            part = 'days' if t.startswith('DIO 2') else 'areas' if t.startswith('DIO 3') else 'dishes' if t.startswith('DIO 4') else None
            meal = area = dish = None
            continue
        if part == 'days':
            if line.startswith('## '):
                flush_opt(); meal = None
                h = line[3:]
                day = {'date': date_of(h), 'region': REGION.get(h.split(' ')[0], 'seoul'), 'note': ''}
                meals.setdefault(day['date'], [])
                continue
            if line.startswith('### '):
                flush_opt()
                h = line[4:].strip()
                emoji, _, h = h.partition(' ')
                bits = [x.strip() for x in h.split(' · ')]
                time = next((b for b in bits[1:] if re.search(r'\d:\d\d', b)), '')
                where = ' · '.join(b for b in bits[1:] if b != time)
                new_meal(bits[0], time, where); meal['emoji'] = emoji
                meal['region'] = day['region']
                if day['note']: meal['note'] = day['note']
                continue
            if day is None or line.strip() == '---': continue
            if OPT.match(line):
                flush_opt()
                if meal is None:  # a day without meal headings (airport): one generic meal
                    new_meal('HRANA', '', ''); meal['emoji'] = '🍽️'; meal['region'] = day['region']
                opt_head = line
                continue
            if line.startswith('**Ritam dana'): continue
            if not line.strip():
                flush_opt(); continue
            if opt_head: opt_lines.append(line.strip())
            elif meal is not None: meal['note'] = (meal['note'] + ' ' + line.strip()).strip()
            elif line.startswith('⚠️'): day['note'] = line.strip()
        elif part == 'areas':
            if line.startswith('## '):
                region = REGION.get(line[3:].split(' ')[0], 'seoul'); continue
            if line.startswith('### '):
                name, ko, _ = split_name(line[4:].strip())
                area = {'name': name, 'ko': ko, 'short': '', 'body': '', 'warn': [], 'dates': [], 'any': False, 'naver': []}
                areas.setdefault(region, []).append(area); continue
            if area is None or not line.strip() or line.strip() == '---': continue
            if line.startswith('**Ukratko:**'): area['short'] = line.split('**', 2)[2].strip().rstrip('.')
            elif line.startswith('**Paše za:**'):
                f = line.split('**', 2)[2]
                area['dates'] = dates_in(f); area['any'] = 'bilo' in f
            elif line.startswith('🔎'): area['naver'] = [x.strip() for x in line[1:].split(',') if x.strip()]
            elif line.startswith('- '): area['warn'].append(line[2:].strip())
            elif line.startswith('⚠️'): continue
            else: area['body'] = (area['body'] + ' ' + line.strip()).strip()
        elif part == 'dishes':
            if line.startswith('## '):
                if '🔴' in line: part = None; continue
                cat = line[3:].strip(); continue
            if line.startswith('### '):
                h = line[4:].strip()
                tag = 'y' if h.startswith('🟡') else 'g'
                name, ko, price = split_name(h)
                dish = {'tag': tag, 'name': name, 'ko': ko, 'price': price, 'cat': cat, 'short': '', 'body': '', 'warn': [], 'naver': []}
                dishes.append(dish); continue
            if dish is None or not line.strip() or line.strip() == '---': continue
            if line.startswith('**Ukratko:**'): dish['short'] = line.split('**', 2)[2].strip().rstrip('.')
            elif line.startswith('🔎'): dish['naver'] = [x.strip() for x in line[1:].split(',') if x.strip()]
            elif line.startswith('- '): dish['warn'].append(line[2:].strip())
            elif line.startswith('⚠️'): continue
            else: dish['body'] = (dish['body'] + ' ' + line.strip()).strip()
    flush_opt()
    # areas whose only meaning is "avoid" stay out
    areas = {r: [a for a in v if '🔴' not in a['short']] for r, v in areas.items()}
    for d in dishes:
        d['warn'] = ' · '.join(w for w in d['warn'] if not re.match(r'^(Nema kvake|Ništa posebno)', w))
    for v in areas.values():
        for a in v: a['warn'] = ' · '.join(a['warn'])
    fallback = {k: [i for n in names for i, d in enumerate(dishes) if d['name'].startswith(n)][:len(names)] for k, names in FALLBACK.items()}
    return {'meals': {k: v for k, v in meals.items() if v}, 'areas': areas, 'dishes': dishes, 'fallback': fallback}
