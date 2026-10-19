package fr.lecteurgilles.android
import org.junit.Test
import org.junit.Assert.*
class ReadingStartTest {
    @Test fun skipsContentsAndKeepsDocument(){
        val prefix="Table des matières\nPréambule 😀\n"
        val body="Chapitre 1. Le texte choisi.\nChapitre 2. La suite."
        val original=prefix+body
        assertEquals(body,ReadingStart.fromCursor(original,prefix.length,prefix.length))
        assertEquals(body,ReadingStart.fromCursor(original,prefix.length+8,prefix.length))
        assertEquals(body,ReadingStart.fromCursor(original,prefix.length,prefix.length+8))
        assertEquals(prefix+body,original)
        assertEquals("",ReadingStart.fromCursor(original,original.length,original.length))
        assertEquals(original,ReadingStart.fromCursor(original,0,0))
    }
}
