package fr.lecteurgilles.android
import org.junit.Assert.*
import org.junit.Test
class TextChunksTest {
    @Test fun noWordsLost() {
        val text = (1..1000).joinToString(" ") { "mot$it" }
        val chunks = TextChunks.split(text)
        assertEquals(text, chunks.joinToString(" "))
        assertTrue(chunks.all { it.length <= 600 })
    }
    @Test fun longWordAndEmpty() {
        assertTrue(TextChunks.split("").isEmpty())
        assertEquals("a".repeat(1500), TextChunks.split("a".repeat(1500)).joinToString(""))
    }
}
