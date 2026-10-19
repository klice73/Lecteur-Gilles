package fr.lecteurgilles.android
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

class MinutageTest {
    @Test fun phrasesEtMots() {
        val t="Bonjour, Gilles. Ceci est un test !\n\nTitre\nSuite de 1 250 mots, c’est-à-dire peu. 😀 fin"
        val p=Minutage.phrases(t).map{t.substring(it.first,it.last+1).trim()}
        assertEquals(listOf("Bonjour, Gilles.","Ceci est un test !","Titre\nSuite de 1 250 mots, c’est-à-dire peu.","😀 fin"),p)
        val m=Minutage.poidsMots("Suite de 1 250 mots, c’est-à-dire peu.")
        assertEquals(listOf("Suite","de","1 250","mots","c’est-à-dire","peu"),m.map{"Suite de 1 250 mots, c’est-à-dire peu.".substring(it.debut,it.fin)})
        assertEquals(4.0,m[4].pause,0.0)   // virgule avant « c’est-à-dire »
    }
    @Test fun minutageDansLaZoneParlee() {
        val sr=16000
        val audio=FloatArray(sr/2)+FloatArray(2*sr){(0.4*sin(2*PI*200*it/sr)).toFloat()}+FloatArray(sr/2)
        val phrase="Le soleil se couche derrière la montagne."
        val r=Minutage.minuter(phrase,audio,sr)
        assertEquals(7,r.size)
        assertEquals(0,r.first().t0)
        assertEquals(audio.size,r.last().t1)
        for(i in 1 until r.size){assertTrue(r[i].t0>=r[i-1].t0);assertTrue(r[i].t0 in sr/2..(sr/2+2*sr))}
        assertEquals("montagne",phrase.substring(r.last().debut,r.last().fin))
    }
}
