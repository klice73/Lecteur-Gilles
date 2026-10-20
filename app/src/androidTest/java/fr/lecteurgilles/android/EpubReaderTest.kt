package fr.lecteurgilles.android
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

@RunWith(AndroidJUnit4::class)
class EpubReaderTest {
    private fun book(encrypted:String?=null):File {
        val file=File.createTempFile("epub-test-",".epub",InstrumentationRegistry.getInstrumentation().targetContext.cacheDir)
        ZipOutputStream(file.outputStream()).use{zip->
            fun put(name:String,text:String){zip.putNextEntry(ZipEntry(name));zip.write(text.toByteArray(Charsets.UTF_8));zip.closeEntry()}
            put("META-INF/container.xml","""<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>""")
            put("OPS/book.opf","""<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/><item id="a" href="chapitre%20un.xhtml#debut" media-type="application/xhtml+xml"/><item id="extra" href="extra.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/><itemref idref="extra" linear="no"/><itemref idref="b"/></spine></package>""")
            put("OPS/b.xhtml","<html><body><p>Deuxième chapitre.</p></body></html>")
            put("OPS/chapitre un.xhtml","<html><head><style>INVISIBLE_STYLE</style></head><body><h1>Premier chapitre</h1><p>Bonjour à tous &amp; bienvenue.</p><script>INVISIBLE_SCRIPT</script></body></html>")
            put("OPS/extra.xhtml","<p>ANNEXE_HORS_PARCOURS</p>")
            if(encrypted!=null)put("META-INF/encryption.xml","""<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><EncryptedData xmlns="http://www.w3.org/2001/04/xmlenc#"><CipherData><CipherReference URI="$encrypted"/></CipherData></EncryptedData></encryption>""")
        };return file
    }
    @Test fun readsSpineAndTextOnly(){
        val file=book()
        try{
            val text=EpubReader.read(file)
            assertTrue(text.indexOf("Premier chapitre")<text.indexOf("Deuxième chapitre"))
            assertTrue(text.contains("Bonjour à tous & bienvenue."))
            assertFalse(text.contains("INVISIBLE"));assertFalse(text.contains("ANNEXE_HORS_PARCOURS"))
        }finally{file.delete()}
    }
    @Test fun rejectsEncryptedTextButAllowsObfuscatedFonts(){
        val protected=book("OPS/chapitre%20un.xhtml")
        try{try{EpubReader.read(protected);fail("Encrypted chapter accepted")}catch(e:IllegalArgumentException){assertTrue(e.message.orEmpty().contains("protégé"))}}finally{protected.delete()}
        val fonts=book("OPS/font.ttf")
        try{assertTrue(EpubReader.read(fonts).contains("Premier chapitre"))}finally{fonts.delete()}
    }
}
