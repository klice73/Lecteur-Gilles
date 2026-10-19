package fr.lecteurgilles.android
import org.junit.Assert.*
import org.junit.Test
class TextChunksTest {
    @Test fun noWordsLost() {
        val text=(1..1000).joinToString(" "){"mot$it"}
        val chunks=TextChunks.split(text)
        assertEquals(text,chunks.joinToString(" "))
        assertTrue(chunks.all{it.length<=600})
    }
    @Test fun longWordAndEmpty(){
        assertTrue(TextChunks.split("").isEmpty())
        assertEquals("a".repeat(1500),TextChunks.split("a".repeat(1500)).joinToString(""))
    }
    @Test fun rangesPreserveSpacingAndUnicode(){
        val text="  Bonjour 😀.  \nLa suite.  ".repeat(120)
        val parts=TextChunks.ranges(text)
        assertTrue(parts.size>1)
        var previous=0
        for(part in parts){
            assertTrue(text.substring(previous,part.start).isBlank())
            assertEquals(part.text,text.substring(part.start,part.end))
            assertFalse(Character.isHighSurrogate(part.text.last()))
            previous=part.end
        }
        assertTrue(text.substring(previous).isBlank())
    }
}
