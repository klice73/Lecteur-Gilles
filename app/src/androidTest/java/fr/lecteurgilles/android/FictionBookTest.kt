package fr.lecteurgilles.android

import org.junit.Assert.*
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class FictionBookTest {
    private val xml="""<?xml version="1.0" encoding="utf-8"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><description><title-info><book-title>SECRET</book-title></title-info></description><body><section><title><p>La forêt</p></title><p>Bonjour 😀 <emphasis>Gilles</emphasis>.</p><section><title><p>Le lac</p></title><p>Fin.</p></section></section></body><binary>SECRET</binary></FictionBook>"""
    @Test fun bodyTitlesAndZip(){
        val r=FictionBook.read(xml.toByteArray(),false)
        assertFalse(r.texte.contains("SECRET"));assertTrue(r.texte.contains("Bonjour 😀 Gilles."))
        assertEquals(listOf("La forêt","Le lac"),r.reperes.table.map{it.titre})
        assertEquals(listOf(1,2),r.reperes.table.map{it.niveau})
        r.reperes.table.forEach{assertTrue(r.texte.substring(it.debut).startsWith(it.titre))}
        val out=ByteArrayOutputStream();ZipOutputStream(out).use{it.putNextEntry(ZipEntry("livre.fb2"));it.write(xml.toByteArray());it.closeEntry()}
        assertEquals(r.texte,FictionBook.read(out.toByteArray(),true).texte)
        assertEquals(r.texte,Documents.extraire(xml.toByteArray(),"application/x-fictionbook+xml").texte)
    }
    @Test fun rejectsWrongRoot(){
        try{FictionBook.read("<other><body>bad</body></other>".toByteArray(),false);fail("accepted")}catch(_:IllegalArgumentException){}
    }
}
