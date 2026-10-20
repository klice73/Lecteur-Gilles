"""Extraction locale, sans exécution de macros ni accès réseau."""
import sys
import json
import zipfile
import posixpath
from pathlib import Path
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
import re
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))

class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if not self.hidden and tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'tr'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)

def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')): return data.decode('utf-16')
    try: return data.decode('utf-8-sig')
    except UnicodeDecodeError: return data.decode('cp1252')

def html(data):
    parser = HTMLText()
    parser.feed(decode(data))
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())

def pdf_pages(reader, clean=False):
    """Remove repeated short margin blocks, never arbitrary numbers in body text."""
    if not clean:
        return [page.extract_text() or '' for page in reader.pages], 0
    pages=[]
    counts=Counter()
    number=re.compile(r'^(?:(?:page|p\.)\s*)?\d+(?:\s*(?:/|sur|of)\s*\d+)?$',re.I)
    for page in reader.pages:
        blocks=[]
        bottom=float(page.cropbox.bottom); top=float(page.cropbox.top)
        def visit(text, cm, tm, font, size):
            if not text:return
            y=tm[4]*cm[1]+tm[5]*cm[3]+cm[5]
            lines=[s.strip() for s in text.splitlines() if s.strip()]
            margin=(y>=top-55 or y<=bottom+45) and not page.rotation
            short=bool(lines) and len(lines)<=2 and len(text)<200
            key=re.sub(r'\d+','#',' '.join(text.split())).casefold() if margin and short else None
            blocks.append((text,key, bool(key and number.fullmatch(' '.join(text.split())))))
        original=page.extract_text(visitor_text=visit) or ''
        # Preserve extraction as-is for unusual PDFs where visitors differ.
        if ''.join(b[0] for b in blocks)!=original:
            blocks=[(original,None,False)]
        pages.append(blocks)
        counts.update(set(key for _,key,_ in blocks if key))
    threshold=max(2, (len(pages)+1)//2)
    removed=0;result=[]
    for blocks in pages:
        keep=[]
        for text,key,isnumber in blocks:
            if isnumber or (key and counts[key]>=threshold):removed+=1
            else:keep.append(text)
        result.append(''.join(keep))
    return result,removed



# --- Reperes (version 1.6) : pages et table des matieres -------------------
# Les positions renvoyees sont en unites UTF-16 (comme la fenetre Windows),
# dans le texte final (lignes separees par \n).
_MOTS_TITRE = ('chapitre', 'chap.', 'partie', 'livre', 'tome', 'section', 'annexe', 'appendice',
               'prologue', '\u00e9pilogue', 'epilogue', 'introduction', 'conclusion', 'pr\u00e9face', 'preface',
               'avant-propos', 'postface', 'remerciements', 'bibliographie', 'r\u00e9f\u00e9rences', 'glossaire',
               'sommaire', 'table des mati\u00e8res', 'r\u00e9sum\u00e9', 'lexique', 'notes')
_NIVEAU_UN = ('partie', 'livre', 'tome')
_RE_MOT_TITRE = re.compile(r'(?i)^(' + '|'.join(re.escape(m) for m in sorted(_MOTS_TITRE, key=len, reverse=True)) + r')(?=$|[\s.:,\u2013\u2014-])')
_RE_ORDINAL = re.compile(r'(?i)^(?:premi[e\u00e8]re?|deuxi[e\u00e8]me|seconde?|troisi[e\u00e8]me|quatri[e\u00e8]me|cinqui[e\u00e8]me|sixi[e\u00e8]me|septi[e\u00e8]me|huiti[e\u00e8]me|neuvi[e\u00e8]me|dixi[e\u00e8]me|derni[e\u00e8]re?)\s+(partie|chapitre|livre|tome|section)(?=$|[\s.:,\u2013\u2014-])')
_RE_NUMERO = re.compile(r'^([0-9]{1,2}(?:\.[0-9]{1,2}){0,2}|[IVXLC]{1,7})[.)]?\s+(?=[A-Z\u00c0-\u00dd])')
_RE_FIN_PAGE = re.compile(r'(?:\.{2,}|\u2026|\s)\s*[0-9]{1,4}$')   # entree de table imprimee : « ... 12 »
_ROMAINS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def _romain(s):
    total, prec = 0, 0
    for c in reversed(s):
        v = _ROMAINS[c]
        total += -v if v < prec else v
        prec = max(prec, v)
    return total


class Positions:
    """Conversion rapide position Python (code point) -> position UTF-16."""
    def __init__(self, texte):
        self.astraux = [i for i, c in enumerate(texte) if ord(c) > 0xFFFF]
    def u16(self, i):
        import bisect
        return i + bisect.bisect_left(self.astraux, i)


def chapitres_devines(texte):
    """Titres reconnus dans un texte sans table : « Chapitre 3 », « Introduction »,
    « II. La methode »... Lignes courtes seulement ; les entrees d'une table imprimee
    (terminees par un numero de page) sont ignorees ; des lignes numerotees qui se
    suivent sont une liste, pas des titres. -> [(titre, niveau, position)]"""
    res, pos, majeur = [], 0, {'arabe': 0, 'romain': 0}
    lignes = texte.split('\n')
    num = [bool(_RE_NUMERO.match(l.strip())) for l in lignes]
    # lignes numerotees qui se suivent = liste (recette, enumeration) : pas des titres
    liste = [num[k] and ((k > 0 and num[k - 1]) or (k + 1 < len(num) and num[k + 1])) for k in range(len(num))]
    for k, ligne in enumerate(lignes):
        debut = pos
        pos += len(ligne) + 1
        s = ligne.strip()
        if not (2 <= len(s) <= 90) or s[-1] in ',;' or _RE_FIN_PAGE.search(s):
            continue
        ici = debut + (len(ligne) - len(ligne.lstrip()))
        m = _RE_MOT_TITRE.match(s) or _RE_ORDINAL.match(s)   # « Chapitre 3 », « Premiere partie »
        if m:
            mot = m.group(1).lower()
            if mot not in ('chapitre', 'chap.', 'partie', 'livre', 'tome', 'section', 'annexe', 'appendice') and len(s) > 60:
                continue
            if s.endswith('.') and len(s.split()) > 6:
                continue
            res.append((s, 1 if mot in _NIVEAU_UN else 2, ici))
            continue
        m = None if liste[k] else _RE_NUMERO.match(s)
        if m and len(s.split()) <= 12 and s[-1] not in '.:':
            num = m.group(1)
            sorte = 'arabe' if num[0].isdigit() else 'romain'
            if '.' in num:
                if majeur['arabe'] and int(num.split('.')[0]) == majeur['arabe']:
                    res.append((s, 3, ici))
                continue
            v = int(num) if sorte == 'arabe' else _romain(num)
            if v == majeur[sorte] + 1:
                majeur[sorte] = v
                res.append((s, 2, ici))
    # meme titre deux fois (table imprimee puis corps du livre) : garder le dernier
    vus, final = {}, []
    for titre, niveau, p in res:
        cle = ' '.join(titre.casefold().split())
        if cle in vus:
            final[vus[cle]] = None
        vus[cle] = len(final)
        final.append((titre, niveau, p))
    final = [x for x in final if x][:500]
    if final and min(n for _, n, _ in final) > 1:
        decale = min(n for _, n, _ in final) - 1
        final = [(a, n - decale, p) for a, n, p in final]
    return final


def _chercher(texte, titre, debut, fin):
    """Position exacte du titre dans texte[debut:fin] (espaces et casse ignores), sinon debut."""
    mots = [re.escape(m) for m in titre.split()]
    if not mots:
        return debut
    m = re.compile(r'\s+'.join(mots), re.I).search(texte, debut, max(debut, fin))
    return m.start() if m else debut


def _sortie(texte, pages, table, source):
    conv = Positions(texte)
    return {'pages': [[str(lbl), conv.u16(p)] for lbl, p in pages],
            'table': [[str(t)[:200], int(n), conv.u16(p)] for t, n, p in table],
            'source_table': source}


def reperes_texte(texte):
    return _sortie(texte, [], chapitres_devines(texte), 'devinee' )
# ---------------------------------------------------------------------------


def reperes_pdf(reader, pages, texte):
    """Pages (etiquettes imprimees si le PDF en a : « iv », « 12 ») et signets du PDF."""
    debuts, pos = [], 0
    for page in pages:
        debuts.append(pos)
        pos += len(page) + 2
    try:
        etiquettes = list(reader.page_labels)
        if len(etiquettes) != len(pages):
            raise ValueError
    except Exception:
        etiquettes = [str(i + 1) for i in range(len(pages))]
    table = []
    def parcourir(elements, niveau):
        for e in elements:
            if isinstance(e, list):
                parcourir(e, niveau + 1)
                continue
            try:
                n = reader.get_destination_page_number(e)
                titre = str(e.title or '').strip()
            except Exception:
                continue
            if 0 <= n < len(pages) and titre:
                fin = debuts[n] + len(pages[n])
                table.append((titre, niveau, _chercher(texte, titre, debuts[n], fin)))
    try:
        parcourir(reader.outline, 1)
    except Exception:
        table = []
    source = 'signets'
    if not table:
        table, source = chapitres_devines(texte), 'devinee'
    return _sortie(texte, list(zip(etiquettes, debuts)), table, source)


def reperes_markdown(texte):
    table, pos = [], 0
    for ligne in texte.split('\n'):
        m = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', ligne)
        if m:
            table.append((m.group(2), len(m.group(1)), pos))
        pos += len(ligne) + 1
    return _sortie(texte, [], table, 'titres') if table else reperes_texte(texte)


def docx_reperes(root):
    """Texte (comme avant), titres (styles Titre/Heading, niveau de plan) et pages
    (sauts de page et derniers sauts calcules par Word : approximatifs)."""
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    parties, table, pages, pos = [], [], [0], 0
    for p in root.iter(ns + 'p'):
        debut = pos
        style = p.find(ns + 'pPr/' + ns + 'pStyle')
        plan = p.find(ns + 'pPr/' + ns + 'outlineLvl')
        niveau = None
        if style is not None:
            m = re.match(r'(?i)^(?:heading|titre|title)\s*(\d?)$', style.get(ns + 'val', ''))
            if m:
                niveau = int(m.group(1) or 1)
        if niveau is None and plan is not None and plan.get(ns + 'val', '').isdigit() and int(plan.get(ns + 'val')) < 9:
            niveau = int(plan.get(ns + 'val')) + 1
        if p.find(ns + 'pPr/' + ns + 'pageBreakBefore') is not None and debut > 0:
            pages.append(debut)
        s = []
        for n in p.iter():
            if n.tag == ns + 't':
                s.append(n.text or '')
            elif n.tag == ns + 'tab':
                s.append('\t')
            elif n.tag == ns + 'br':
                if n.get(ns + 'type') == 'page':
                    pages.append(debut + len(''.join(s)) + 1)
                s.append('\n')
            elif n.tag == ns + 'lastRenderedPageBreak' and (debut + len(''.join(s))) > 0:
                pages.append(debut + len(''.join(s)))
        s = ''.join(s)
        if niveau and s.strip():
            table.append((s.strip(), niveau, debut + (len(s) - len(s.lstrip()))))
        parties.append(s)
        pos += len(s) + 1
    texte = '\n'.join(parties)
    pages = sorted(set(x for x in pages if x < max(1, len(texte))))
    source = 'titres'
    if not table:
        table, source = chapitres_devines(texte), 'devinee'
    if len(pages) < 2:
        pages = []
    return texte, _sortie(texte, [(str(i + 1), x) for i, x in enumerate(pages)], table, source)


def odt_reperes(root):
    ns = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
    parties, table, pages, pos, saut = [], [], [0], 0, False
    for e in root.iter():
        if e.tag == ns + 'soft-page-break':
            saut = True
            continue
        if e.tag not in (ns + 'p', ns + 'h'):
            continue
        if saut and pos > 0:
            pages.append(pos)
        saut = False
        s = ''.join(e.itertext())
        if e.tag == ns + 'h' and s.strip():
            niv = e.get(ns + 'outline-level', '1')
            table.append((s.strip(), int(niv) if niv.isdigit() else 1, pos + (len(s) - len(s.lstrip()))))
        parties.append(s)
        pos += len(s) + 1
    texte = '\n'.join(parties)
    source = 'titres'
    if not table:
        table, source = chapitres_devines(texte), 'devinee'
    if len(pages) < 2:
        pages = []
    return texte, _sortie(texte, [(str(i + 1), x) for i, x in enumerate(pages)], table, source)


def epub_reperes(archive, opf, root, chapitres, textes, texte):
    """Table des matieres du livre (nav EPUB 3 ou toc.ncx EPUB 2). Pas de pages fixes."""
    from urllib.parse import unquote
    debuts, pos = {}, 0
    for nom, t in zip(chapitres, textes):
        debuts.setdefault(nom, (pos, pos + len(t)))
        pos += len(t) + 2
    base = posixpath.dirname(opf)
    items = [n for n in root.iter() if n.tag.endswith('}item')]
    def chemin(fichier, href):
        return posixpath.normpath(posixpath.join(posixpath.dirname(fichier), unquote(href.split('#')[0])))
    table = []
    nav = next((n for n in items if 'nav' in n.get('properties', '').split()), None)
    ncx = next((n for n in items if n.get('media-type') == 'application/x-dtbncx+xml'), None)
    try:
        if nav is not None:
            fichier = posixpath.normpath(posixpath.join(base, unquote(nav.get('href'))))
            arbre = ET.fromstring(archive.read(fichier))
            def lire(ol, niveau):
                for li in [x for x in ol if x.tag.endswith('}li')]:
                    a = next((x for x in li.iter() if x.tag.endswith('}a')), None)
                    if a is not None and a.get('href'):
                        titre = ' '.join(''.join(a.itertext()).split())
                        cible = chemin(fichier, a.get('href'))
                        if titre and cible in debuts:
                            d, f = debuts[cible]
                            table.append((titre, niveau, _chercher(texte, titre, d, f)))
                    for sous in [x for x in li if x.tag.endswith('}ol')]:
                        lire(sous, niveau + 1)
            for n in arbre.iter():
                if n.tag.endswith('}nav') and 'toc' in ' '.join(v for k, v in n.attrib.items() if k.endswith('type')):
                    for ol in [x for x in n if x.tag.endswith('}ol')]:
                        lire(ol, 1)
                    break
        if not table and ncx is not None:
            fichier = posixpath.normpath(posixpath.join(base, unquote(ncx.get('href'))))
            arbre = ET.fromstring(archive.read(fichier))
            def lire_ncx(elem, niveau):
                for np in [x for x in elem if x.tag.endswith('}navPoint')]:
                    titre = ' '.join(''.join(next((x for x in np.iter() if x.tag.endswith('}text')), np).itertext()).split())
                    c = next((x for x in np if x.tag.endswith('}content')), None)
                    if c is not None and titre:
                        cible = chemin(fichier, c.get('src', ''))
                        if cible in debuts:
                            d, f = debuts[cible]
                            table.append((titre, niveau, _chercher(texte, titre, d, f)))
                    lire_ncx(np, niveau + 1)
            carte = next((x for x in arbre.iter() if x.tag.endswith('}navMap')), None)
            if carte is not None:
                lire_ncx(carte, 1)
    except Exception:
        table = []
    source = 'table du livre'
    if not table:
        table, source = chapitres_devines(texte), 'devinee'
    return _sortie(texte, [], table, source)

def extract(filename, clean_pdf=False):
    path = Path(filename)
    ext = path.suffix.lower()
    warning = ''
    if ext == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('Ce PDF est protégé par un mot de passe. Ouvrez une copie déverrouillée.')
        pages, removed = pdf_pages(reader, clean_pdf)
        empty = sum(not p.strip() for p in pages)
        text = '\n\n'.join(pages)
        reperes = reperes_pdf(reader, pages, text)
        if empty:
            warning = '{} page(s) sans texte extractible. Les pages scannées nécessitent une reconnaissance de caractères (OCR).'.format(empty)
    elif ext in ('.txt', '.md', '.csv'):
        # fins de ligne Windows ramenees a \n : la fenetre compte \r\n comme un seul caractere
        text = decode(path.read_bytes()).replace('\r\n', '\n').replace('\r', '\n')
        reperes = reperes_markdown(text) if ext == '.md' else reperes_texte(text)
    elif ext in ('.html', '.htm'):
        text = html(path.read_bytes())
        reperes = reperes_texte(text)
    elif ext in ('.docx', '.odt', '.epub'):
        with zipfile.ZipFile(path) as archive:
            if sum(x.file_size for x in archive.infolist()) > 250 * 1024 * 1024:
                raise ValueError('Document trop volumineux après décompression (limite 250 Mo).')
            if ext == '.docx':
                root = ET.fromstring(archive.read('word/document.xml'))
                text, reperes = docx_reperes(root)
            elif ext == '.odt':
                root = ET.fromstring(archive.read('content.xml'))
                text, reperes = odt_reperes(root)
            else:
                container = ET.fromstring(archive.read('META-INF/container.xml'))
                opf = next(n.attrib['full-path'] for n in container.iter() if n.tag.endswith('}rootfile'))
                root = ET.fromstring(archive.read(opf))
                items = {n.attrib['id']: n.attrib['href'] for n in root.iter() if n.tag.endswith('}item')}
                from urllib.parse import unquote
                chapters = [posixpath.normpath(posixpath.join(posixpath.dirname(opf), unquote(items[n.attrib['idref']].split('#')[0]))) for n in root.iter() if n.tag.endswith('}itemref')]
                textes = [html(archive.read(chapter)) for chapter in chapters]
                text = '\n\n'.join(textes)
                reperes = epub_reperes(archive, opf, root, chapters, textes, text)
    else:
        raise ValueError('Format non pris en charge. Formats : PDF, DOCX, ODT, EPUB, TXT, MD, HTML, CSV. Pour un ancien .doc, enregistrez-le en .docx.')
    if not text.strip():
        raise ValueError(warning or 'Aucun texte trouvé dans ce document.')
    resultat = {'text': text, 'warning': warning, 'name': path.name}
    resultat.update(reperes)
    return resultat

if __name__ == '__main__':
    try:
        if sys.argv[1] == '--reperes':   # texte colle : chapitres devines seulement
            result = reperes_texte(Path(sys.argv[2]).read_text(encoding='utf-8'))
            Path(sys.argv[3]).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            sys.exit(0)
        result = extract(sys.argv[1], clean_pdf='--clean-pdf' in sys.argv[3:])
    except Exception as error:
        result = {'error': str(error)}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
