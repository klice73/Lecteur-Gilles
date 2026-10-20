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
_LONGS = ('chapitre', 'chap.', 'partie', 'livre', 'tome', 'section', 'annexe', 'appendice')
# Espaces reconnus : liste explicite, identique dans Reperes.kt (\s differe entre Python et Java).
_ESP = ' \t    \x0b\x0c\x85'
_E = '[' + _ESP + ']'
_MOTS_RE = '|'.join(re.escape(m) for m in sorted(_MOTS_TITRE, key=len, reverse=True))
_ORDINAUX = (r'premi[eè]re?|deuxi[eè]me|seconde?|troisi[eè]me|quatri[eè]me|cinqui[eè]me|'
             r'sixi[eè]me|septi[eè]me|huiti[eè]me|neuvi[eè]me|dixi[eè]me|derni[eè]re?')
_APRES = '(?=$|' + _E + r'|[.:,–—-])'
_RE_MOT_TITRE = re.compile('(?i)^(' + _MOTS_RE + ')' + _APRES)
_RE_ORDINAL = re.compile('(?i)^(?:' + _ORDINAUX + ')' + _E + '+(partie|chapitre|livre|tome|section)' + _APRES)
# « Chapitre 3 », « Annexe A », « Partie II » seuls sur la ligne : toujours un titre
_RE_TITRE_NU = re.compile('(?i)^(?:(?:' + _ORDINAUX + ')' + _E + '+)?(?:' + _MOTS_RE + ')' + _E + r'+([0-9]{1,3}|[ivxlc]{1,7}|[a-z])[.:]?$')
# numero de titre : « 2. Portrait », « II) Methode », « 1 Introduction » (sans ponctuation : mot d'au moins 2 lettres)
_RE_NUMERO = re.compile(r'^([0-9]{1,2}(?:\.[0-9]{1,2}){0,2}|[IVXLC]{1,7})(?:[.)]' + _E + '+|' + _E + '+(?=[A-ZÀ-Ý][^' + _ESP + r'.,]))(?=[A-ZÀ-Ý])')
_RE_ROMAIN_SEUL = re.compile(r'^([IVXLC]{1,7})\.?$')
_RE_POINTILLES = re.compile(r'(?:\.{2,}|…|\t)' + _E + r'*[0-9]{1,4}$')   # « ... 12 » : entree de table imprimee
_RE_FIN_NOMBRE = re.compile(_E + r'[0-9]{1,4}$')
_RE_ESPACES = re.compile(_E + '+')
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


def _nettoyer(ligne):
    return ligne.strip(_ESP + '\r')


def _mots(s):
    return len([m for m in _RE_ESPACES.split(s) if m])


def _valeur(num):
    """Valeur du dernier niveau d'un numero : « 2.3 » -> 3, « IV » -> 4."""
    der = num.split('.')[-1]
    return int(der) if der.isdigit() else _romain(der)


def _dans_liste(k, numero, profondeur, av, ap):
    v = _valeur(numero[k].group(1))
    for j, pas in ((av, -1), (ap, 1)):
        if j is not None and j == k + pas and numero[j] and profondeur[j] == profondeur[k] \
                and numero[j].group(1)[0].isdigit() == numero[k].group(1)[0].isdigit() \
                and _valeur(numero[j].group(1)) == v + pas:
            return True
    return False


_NOMBRES_MOTS = ('UN', 'DEUX', 'TROIS', 'QUATRE', 'CINQ', 'SIX', 'SEPT', 'HUIT', 'NEUF', 'DIX', 'ONZE', 'DOUZE',
                 'TREIZE', 'QUATORZE', 'QUINZE', 'SEIZE', 'DIX-SEPT', 'DIX-HUIT', 'DIX-NEUF', 'VINGT')
# chiffre seul sur sa ligne, eventuellement entre tirets : « 3 », « – 3 – »
_RE_NOMBRE_SEUL = re.compile('^(?:[–—-]' + _E + '*)?([0-9]{1,3})(?:' + _E + '*[–—-])?$')
# apres « Chapitre », « Partie »... : un numero, un nombre en lettres, une ponctuation, ou rien
_RE_SUITE_LONG = re.compile('(?i)^(?:$|' + _E + '*[:.–—-](?:$|' + _E + ')|' + _E + r'+(?:[0-9]{1,4}|[ivxlc]{1,7}|[a-z]|premi[eè]re?|premier|derni[eè]re?|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt)(?=$|' + _E + '|[.:)–—,-]))')


def chapitres_devines(texte, pages=None):
    """Titres reconnus dans un texte sans table : « Chapitre 3 », « Premiere partie »,
    « Introduction », « II. La methode », « III » ou « 3 » seuls... Lignes courtes seulement.
    Ecartes : entrees d'une table imprimee (pointilles, ou suite de lignes finissant
    par un numero de page), listes (lignes numerotees de meme niveau qui se suivent),
    phrases ; numeros seuls en haut ou en bas d'une page (pages = debuts des pages, PDF).
    Meme regle dans Reperes.kt. -> [(titre, niveau, position)]"""
    lignes = texte.split('\n')
    nets = [_nettoyer(l) for l in lignes]
    numero = [_RE_NUMERO.match(s) for s in nets]
    profondeur = [m.group(1).count('.') if m else -1 for m in numero]
    def voisin(k, pas):
        j = k + pas
        while 0 <= j < len(nets) and not nets[j]:
            j += pas
        return j if 0 <= j < len(nets) else None
    fin_nombre = [bool(_RE_FIN_NOMBRE.search(s)) for s in nets]
    # lignes en bord de page (premiere ou derniere ligne non vide) : numeros de page probables
    bord = set()
    if pages:
        import bisect
        debuts_lignes, pos = [], 0
        for l in lignes:
            debuts_lignes.append(pos)
            pos += len(l) + 1
        page_de = [bisect.bisect_right(pages, d) for d in debuts_lignes]
        for k in range(len(lignes)):
            if nets[k]:
                av, ap = voisin(k, -1), voisin(k, 1)
                if av is None or page_de[av] != page_de[k] or ap is None or page_de[ap] != page_de[k]:
                    bord.add(k)
    res, pos = [], 0   # (titre, niveau, position, ligne)
    majeur = {'arabe': 0, 'romain': 0, 'seul': 0, 'nombre': 0, 'mot': 0}
    for k, ligne in enumerate(lignes):
        debut = pos
        pos += len(ligne) + 1
        s = nets[k]
        if not (2 <= len(s) <= 90) and not _RE_ROMAIN_SEUL.match(s) and not _RE_NOMBRE_SEUL.match(s):
            continue
        if not s or s[-1] in ',;' or _RE_POINTILLES.search(s):
            continue
        av, ap = voisin(k, -1), voisin(k, 1)
        suite_table = fin_nombre[k] and ((av is not None and fin_nombre[av]) or (ap is not None and fin_nombre[ap]))
        ici = debut + (len(ligne) - len(ligne.lstrip(_ESP + '\r')))
        mots = _mots(s)
        m = _RE_MOT_TITRE.match(s) or _RE_ORDINAL.match(s)
        mot = m.group(1).lower() if m else ''
        if _RE_TITRE_NU.match(s):
            res.append((s, 1 if mot in _NIVEAU_UN else 2, ici, k))
        elif m:
            if suite_table:
                continue
            if mot in _LONGS:
                # « Partie depuis trois jours. », « Livre-moi ça. » : pas des titres
                if not _RE_SUITE_LONG.match(s[m.end(1):]) or (s.endswith('.') and mots > 6):
                    continue
            elif len(s) > 60 or (s[-1] in '.!?' and mots > 2):
                continue
            res.append((s, 1 if mot in _NIVEAU_UN else 2, ici, k))
        else:
            r = _RE_ROMAIN_SEUL.match(s)
            c = _RE_NOMBRE_SEUL.match(s)
            if r or c or s in _NOMBRES_MOTS:
                if k in bord:
                    continue
                sorte, v = ('seul', _romain(r.group(1))) if r else ('nombre', int(c.group(1))) if c else ('mot', _NOMBRES_MOTS.index(s) + 1)
                if v == majeur[sorte] + 1:
                    majeur[sorte] = v
                    res.append((s, 2, ici, k))
                continue
            n = numero[k]
            if not n or mots > 12 or s[-1] in '.:' or suite_table:
                continue
            if _dans_liste(k, numero, profondeur, av, ap):
                continue   # liste : lignes numerotees qui se suivent (1, 2, 3...) au meme niveau
            num = n.group(1)
            if '.' in num:
                if majeur['arabe'] and int(num.split('.')[0]) == majeur['arabe']:
                    res.append((s, 3, ici, k))
                continue
            sorte = 'arabe' if num[0].isdigit() else 'romain'
            v = int(num) if sorte == 'arabe' else _romain(num)
            if v == majeur[sorte] + 1:
                majeur[sorte] = v
                res.append((s, 2, ici, k))
            continue
        if res[-1][1] == 1:
            for x in majeur:   # nouvelle partie : la numerotation des chapitres repart
                majeur[x] = 0
    # numeros seuls trop rapproches (moins de 1500 caracteres en moyenne) : numeros de page, pas des chapitres
    seuls = [x for x in res if _RE_NOMBRE_SEUL.match(x[0])]
    if len(seuls) >= 10 and (seuls[-1][2] - seuls[0][2]) / (len(seuls) - 1) < 1500:
        res = [x for x in res if not _RE_NOMBRE_SEUL.match(x[0])]
    # Doublons. 1) meme titre repete sans autre titre entre (en-tete courant) : garder le premier.
    # 2) table imprimee (au moins 3 titres sur des lignes qui se suivent, ou suite d'un « Sommaire ») :
    #    retirer ses entrees qui reapparaissent plus loin dans le livre.
    def cle(titre):
        return ' '.join(m for m in _RE_ESPACES.split(titre.lower()) if m)
    def cle_table(titre):   # « Chapitre 1 La neige 7 » (entree de table) = « Chapitre 1 La neige »
        c = cle(titre)
        return _RE_FIN_NOMBRE.sub('', c) if c.count(' ') >= 2 else c
    garde = []
    for x in res:
        if garde and cle(garde[-1][0]) == cle(x[0]):
            continue
        garde.append(x)
    blocs, bloc = [], []
    for x in garde:
        if bloc and voisin(bloc[-1][3], 1) == x[3]:
            bloc.append(x)
        else:
            if bloc:
                blocs.append(bloc)
            bloc = [x]
    if bloc:
        blocs.append(bloc)
    retires = set()
    for b in blocs:
        sommaire = (_RE_MOT_TITRE.match(b[0][0]) or _RE_ORDINAL.match(b[0][0]))
        sommaire = sommaire and sommaire.group(1).lower() in ('sommaire', 'table des matières')
        if len(b) < 3 and not (sommaire and len(b) >= 2):
            continue
        for x in b[1:] if sommaire else b:
            if any(cle_table(y[0]) == cle_table(x[0]) and y[3] > x[3] for y in garde):
                retires.add(x[3])
    final = [(a, n, p) for a, n, p, k in garde if k not in retires][:2000]
    if final and min(n for _, n, _ in final) > 1:
        decale = min(n for _, n, _ in final) - 1
        final = [(a, n - decale, p) for a, n, p in final]
    return final


def _chercher(texte, titre, debut, fin):
    """Position du titre dans texte[debut:fin] : d'abord une ligne qui est exactement le
    titre, puis une ligne qui commence par lui (casse exacte, puis sans casse), sinon
    n'importe ou ; a defaut, debut."""
    mots = [re.escape(m) for m in _RE_ESPACES.split(titre) if m]
    if not mots:
        return debut
    corps = (_E + '+').join(mots)
    fin = max(debut, fin)
    ligne = '(?m)^' + _E + '*(' + corps + ')'
    for motif, options in ((ligne + _E + '*$', 0), (ligne + _E + '*$', re.I), (ligne, 0), (ligne, re.I), ('(' + corps + ')', re.I)):
        m = re.compile(motif, options).search(texte, debut, fin)
        if m:
            return m.start(1)
    return debut


def _sortie(texte, pages, table, source):
    conv = Positions(texte)
    table = sorted(table, key=lambda x: x[2])   # ordre du texte (la recherche de chapitre en depend)
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
    table, dernier = [], {}
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
                depart = dernier.get(n, debuts[n])
                p = _chercher(texte, titre, depart, fin)
                if p == depart and depart != debuts[n]:
                    p = _chercher(texte, titre, debuts[n], fin)
                dernier[n] = p + 1
                table.append((titre, niveau, p))
    try:
        parcourir(reader.outline, 1)
    except Exception:
        table = []
    source = 'signets'
    if not table:
        table, source = chapitres_devines(texte, debuts), 'devinee'
    return _sortie(texte, list(zip(etiquettes, debuts)), table, source)


_RE_CLOTURE = re.compile(r'^(`{3,}|~{3,})')


def reperes_markdown(texte):
    table, pos, code = [], 0, ''
    for ligne in texte.split('\n'):
        c = _RE_CLOTURE.match(ligne.lstrip())
        if c:
            if not code:
                code = c.group(1)   # bloc de code ouvert : il se ferme par la meme cloture (au moins aussi longue)
            elif c.group(1)[0] == code[0] and len(c.group(1)) >= len(code):
                code = ''
        m = None if code or c else re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', ligne)
        if m:
            table.append((m.group(2), len(m.group(1)), pos))
        pos += len(ligne) + 1
    return _sortie(texte, [], table, 'titres') if table else reperes_texte(texte)


def docx_styles(archive):
    """styleId -> niveau de titre, d'apres styles.xml (niveau de plan, ou nom « heading N » / « titre N »)."""
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    niveaux = {}
    try:
        racine = ET.fromstring(archive.read('word/styles.xml'))
    except Exception:
        return niveaux
    for st in racine.iter(ns + 'style'):
        sid = st.get(ns + 'styleId', '')
        plan = st.find(ns + 'pPr/' + ns + 'outlineLvl')
        nom = st.find(ns + 'name')
        if plan is not None and plan.get(ns + 'val', '').isdigit() and int(plan.get(ns + 'val')) < 9:
            niveaux[sid] = int(plan.get(ns + 'val')) + 1
        elif nom is not None:
            m = re.match(r'(?i)^(?:heading|titre)\s*(\d)$', nom.get(ns + 'val', ''))
            if m:
                niveaux[sid] = int(m.group(1))
    return niveaux


def docx_reperes(root, styles=None):
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
            sid = style.get(ns + 'val', '')
            m = re.match(r'(?i)^(?:heading|titre|title)\s*(\d?)$', sid)
            if m:
                niveau = int(m.group(1) or 1)
            elif styles and sid in styles:
                niveau = styles[sid]
        if niveau is None and plan is not None and plan.get(ns + 'val', '').isdigit() and int(plan.get(ns + 'val')) < 9:
            niveau = int(plan.get(ns + 'val')) + 1
        if p.find(ns + 'pPr/' + ns + 'pageBreakBefore') is not None and debut > 0:
            pages.append(debut)
        s = []
        taquets = {x for tabs in p.iter(ns + 'tabs') for x in tabs}   # w:tabs/w:tab : taquets, pas du texte
        for n in p.iter():
            if n.tag == ns + 't':
                s.append(n.text or '')
            elif n.tag == ns + 'tab' and n not in taquets:
                s.append('\t')
            elif n.tag in (ns + 'br', ns + 'cr'):
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
    table, suivant = [], {}
    def placer(cible, titre, ancre):
        d, f = debuts[cible]
        depart = suivant.get(cible, d) if ancre else d   # une ancre suit le titre precedent du meme chapitre
        p = _chercher(texte, titre, depart, f)
        if p == depart and depart != d:
            p = _chercher(texte, titre, d, f)
        suivant[cible] = p + 1
        return p
    nav = next((n for n in items if 'nav' in n.get('properties', '').split()), None)
    ncx = next((n for n in items if n.get('media-type') == 'application/x-dtbncx+xml'), None)
    try:
        if nav is not None:
            fichier = posixpath.normpath(posixpath.join(base, unquote(nav.get('href'))))
            arbre = ET.fromstring(archive.read(fichier))
            def lire(ol, niveau):
                for li in [x for x in ol if x.tag.endswith('}li')]:
                    a = next((x for x in li if x.tag.endswith('}a')), None)   # lien propre a l'entree, pas celui d'une sous-entree
                    if a is not None and a.get('href'):
                        titre = ' '.join(''.join(a.itertext()).split())
                        cible = chemin(fichier, a.get('href'))
                        if titre and cible in debuts:
                            table.append((titre, niveau, placer(cible, titre, '#' in a.get('href'))))
                    for sous in [x for x in li if x.tag.endswith('}ol')]:
                        lire(sous, niveau + 1)
            for n in arbre.iter():
                if n.tag.endswith('}nav') and 'toc' in ' '.join(v for k, v in n.attrib.items() if k.endswith('type')):
                    for ol in [x for x in n if x.tag.endswith('}ol')]:
                        lire(ol, 1)
                    break
    except Exception:
        table = []
    try:
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
                            table.append((titre, niveau, placer(cible, titre, '#' in c.get('src', ''))))
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
                text, reperes = docx_reperes(root, docx_styles(archive))
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
    sortie = sys.argv[3] if sys.argv[1] == '--reperes' else sys.argv[2]
    Path(sortie).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
