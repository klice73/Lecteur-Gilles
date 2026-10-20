"""Additional book formats; optional conversion uses a separately installed calibre."""
from pathlib import Path
import os, shutil, subprocess, tempfile, zipfile
import xml.etree.ElementTree as ET

CONVERTIBLE={'.mobi','.azw','.azw3','.azw4','.prc','.pdb','.lit','.lrf','.rtf','.djvu','.htmlz','.txtz','.tcr','.snb','.rb','.pml','.chm'}
def fictionbook(path):
    from documents import _sortie, reperes_texte
    if str(path).lower().endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            if len(z.infolist())>1000 or sum(x.file_size for x in z.infolist())>50*1024*1024:raise ValueError('Archive trop volumineuse.')
            books=[x for x in z.namelist() if x.lower().endswith('.fb2')]
            if len(books)!=1:raise ValueError('Ouvrez une archive contenant un seul livre FB2.')
            data=z.read(books[0])
    else:
        if path.stat().st_size>50*1024*1024:raise ValueError('Livre trop volumineux.')
        data=path.read_bytes()
    root=ET.fromstring(data)
    def name(e):return e.tag.rsplit('}',1)[-1]
    if name(root)!='FictionBook':raise ValueError('Ce fichier ne contient pas un FictionBook.')
    parts=[]; table=[];pos=0
    def visit(e,level):
        nonlocal pos
        tag=name(e)
        if tag in ('title','p','v','subtitle','text-author'):
            s=''.join(e.itertext()).strip()
            if s:
                if tag=='title':table.append((s,max(1,level),pos))
                parts.append(s);pos+=len(s)+1
        else:
            for c in e:visit(c,level+(name(c)=='section'))
    for body in root:
        if name(body)=='body':visit(body,0)
    text='\n'.join(parts)
    return text, _sortie(text,[],table,'titres') if table else reperes_texte(text)

def calibre():
    candidates=[Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Calibre2/ebook-convert.exe',Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Calibre2/ebook-convert.exe',Path(__file__).resolve().parent/'calibre/Calibre/ebook-convert.exe']
    for p in candidates:
        if p.is_file():return str(p)
    return shutil.which('ebook-convert')

def convert(path):
    from documents import extract
    exe=calibre()
    if not exe:raise ValueError('Ce format nécessite calibre. Installez calibre depuis calibre-ebook.com, puis rouvrez ce livre, ou convertissez-le en EPUB. Sur Android, transférez ensuite cet EPUB.')
    temp=Path(__file__).resolve().parent/'temp';temp.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='livre-',dir=temp) as d:
        dest=Path(d)/'livre.epub'
        try:
            with open(Path(d)/'conversion.log','wb') as log:
                p=subprocess.run([exe,str(path.resolve()),str(dest)],stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except subprocess.TimeoutExpired:raise ValueError('La conversion dépasse trois minutes. Essayez de convertir ce livre dans calibre.')
        if p.returncode or not dest.exists():raise ValueError('calibre ne peut pas convertir ce livre (format endommagé, non pris en charge ou protégé). Essayez un export EPUB sans protection depuis votre librairie.')
        result=extract(dest)
        result['name']=path.name
        result['warning']='Livre converti en EPUB par calibre. Le fichier original est conservé.'
        return result
