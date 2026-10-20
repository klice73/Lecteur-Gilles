import sys, tempfile, zipfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import documents as D
import ebooks as E

class Books(unittest.TestCase):
    def test_fb2_body_only_and_offsets(self):
        xml='<?xml version="1.0" encoding="utf-8"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><description><title-info><book-title>SECRET metadata</book-title></title-info></description><body><section><title><p>La forêt</p></title><p>Bonjour 😀 <emphasis>Gilles</emphasis>.</p><section><title><p>Le lac</p></title><p>Fin.</p></section></section></body><binary>SECRET image</binary></FictionBook>'
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'livre.fb2';p.write_text(xml,encoding='utf-8')
            r=D.extract(p);self.assertNotIn('SECRET',r['text']);self.assertIn('Bonjour 😀 Gilles.',r['text'])
            self.assertEqual([tuple(x[:2]) for x in r['table']],[('La forêt',1),('Le lac',2)])
            for title,_,offset in r['table']:self.assertTrue(r['text'].encode('utf-16-le')[offset*2:].decode('utf-16-le').startswith(title))
            z=Path(folder)/'livre.fb2.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('livre.fb2',xml)
            self.assertEqual(D.extract(z)['text'],r['text'])
    def test_calibre_missing_and_arguments(self):
        with patch.object(E,'calibre',return_value=None):
            with self.assertRaisesRegex(ValueError,'calibre'):D.extract('livre.mobi')
        with patch.object(E,'calibre',return_value='converter'),patch.object(E.subprocess,'run') as run:
            run.return_value.returncode=1
            with self.assertRaisesRegex(ValueError,'convertir'):D.extract('livre avec espaces.azw3')
            args=run.call_args.args[0];self.assertEqual(args[0],'converter');self.assertTrue(args[1].endswith('livre avec espaces.azw3'));self.assertTrue(args[2].endswith('.epub'))
    def test_epub_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'livre.epub'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('META-INF/container.xml','<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
                z.writestr('book.opf','<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="a" href="a.xhtml"/></manifest><spine><itemref idref="a"/></spine></package>')
                z.writestr('a.xhtml','<p>Bonjour</p>')
                z.writestr('META-INF/encryption.xml','<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><CipherReference xmlns="http://www.w3.org/2001/04/xmlenc#" URI="a.xhtml"/></encryption>')
            with self.assertRaisesRegex(ValueError,'protégé'):D.extract(p)
if __name__=='__main__':unittest.main()
