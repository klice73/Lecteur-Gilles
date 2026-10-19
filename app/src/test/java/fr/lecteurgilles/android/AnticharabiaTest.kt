package fr.lecteurgilles.android
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

class AnticharabiaTest {
    @Test fun phrasesCourtesRegroupees() {
        val g=Anticharabia.regrouper("Merci. Le centre offre un accompagnement aux personnes qui traversent une période difficile.")
        assertEquals(listOf("Merci, Le centre offre un accompagnement aux personnes qui traversent une période difficile."),g)
    }
    @Test fun aucunGroupeTropCourtSaufTexteEntier() {
        val texte="Introduction\n\nOui. Non ! Table des matières\nChapitre 1 ............ 12\n12\n— Salut. Elle répondit qu'elle viendrait demain matin, après le travail. Fin."
        val g=Anticharabia.regrouper(texte)
        assertTrue(g.isNotEmpty())
        assertTrue(g.joinToString(" | "),g.all{Anticharabia.mots(it)>=Anticharabia.MOTS_MIN})
        assertFalse(g.any{it.contains("...")})
        assertEquals(listOf("Merci."),Anticharabia.regrouper("Merci."))
    }
    @Test fun aucunMotPerdu() {
        val texte="Le chat dort. Oui. La pluie tombe doucement sur les toits de la vieille ville endormie. Fin."
        val avant=Regex("(?U)\\w+").findAll(texte).map{it.value}.toList()
        val apres=Regex("(?U)\\w+").findAll(Anticharabia.regrouper(texte).joinToString(" ")).map{it.value}.toList()
        assertEquals(avant,apres)
    }
    @Test fun motsComposes() {
        assertEquals(3,Anticharabia.mots("d'aide dit-il 12"))
    }
    private fun voix(s:Double,sr:Int)=FloatArray((s*sr).toInt()){(0.5*sin(2*PI*180*it/sr)).toFloat()}
    @Test fun charabiaCoupeAuSilence() {
        val sr=16000
        val audio=voix(0.6,sr)+FloatArray((0.6*sr).toInt())+voix(2.5,sr)
        val out=Anticharabia.couper(audio,sr,"Merci.")
        assertTrue("coupé trop tard : ${out.size}",out.size<(0.9*sr).toInt())
        assertTrue("coupé trop tôt : ${out.size}",out.size>=(0.6*sr).toInt())
    }
    @Test fun phraseNormaleIntacte() {
        val sr=16000
        val texte="Le gouvernement a présenté hier un nouveau projet de loi sur la protection de l'environnement."
        val audio=voix(2.0,sr)+FloatArray((0.3*sr).toInt())+voix(2.5,sr)
        assertSame(audio,Anticharabia.couper(audio,sr,texte))
    }
}
