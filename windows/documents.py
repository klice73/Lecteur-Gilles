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
        if empty:
            warning = '{} page(s) sans texte extractible. Les pages scannées nécessitent une reconnaissance de caractères (OCR).'.format(empty)
    elif ext in ('.txt', '.md', '.csv'):
        text = decode(path.read_bytes())
    elif ext in ('.html', '.htm'):
        text = html(path.read_bytes())
    elif ext in ('.docx', '.odt', '.epub'):
        with zipfile.ZipFile(path) as archive:
            if sum(x.file_size for x in archive.infolist()) > 250 * 1024 * 1024:
                raise ValueError('Document trop volumineux après décompression (limite 250 Mo).')
            if ext == '.docx':
                root = ET.fromstring(archive.read('word/document.xml'))
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                text = '\n'.join(''.join((n.text or '') if n.tag == ns+'t' else '\t' if n.tag == ns+'tab' else '\n' if n.tag == ns+'br' else '' for n in p.iter()) for p in root.iter(ns+'p'))
            elif ext == '.odt':
                root = ET.fromstring(archive.read('content.xml'))
                ns = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
                text = '\n'.join(''.join(p.itertext()) for p in root.iter() if p.tag in (ns+'p', ns+'h'))
            else:
                container = ET.fromstring(archive.read('META-INF/container.xml'))
                opf = next(n.attrib['full-path'] for n in container.iter() if n.tag.endswith('}rootfile'))
                root = ET.fromstring(archive.read(opf))
                items = {n.attrib['id']: n.attrib['href'] for n in root.iter() if n.tag.endswith('}item')}
                from urllib.parse import unquote
                chapters = [posixpath.normpath(posixpath.join(posixpath.dirname(opf), unquote(items[n.attrib['idref']].split('#')[0]))) for n in root.iter() if n.tag.endswith('}itemref')]
                text = '\n\n'.join(html(archive.read(chapter)) for chapter in chapters)
    else:
        raise ValueError('Format non pris en charge. Formats : PDF, DOCX, ODT, EPUB, TXT, MD, HTML, CSV. Pour un ancien .doc, enregistrez-le en .docx.')
    if not text.strip():
        raise ValueError(warning or 'Aucun texte trouvé dans ce document.')
    return {'text': text, 'warning': warning, 'name': path.name}

if __name__ == '__main__':
    try:
        result = extract(sys.argv[1], clean_pdf='--clean-pdf' in sys.argv[3:])
    except Exception as error:
        result = {'error': str(error)}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
