package fr.lecteurgilles.android
import org.junit.Assert.*
import org.junit.Test

class ReperesTest {
    @Test fun chapitresDevinesCommePython() {
        // même texte et même résultat que windows/tests/test_reperes.py
        val t="Table des matières\nChapitre 1 La forêt ........ 12\nChapitre 2 Le lac 27\n\n"+
            "Chapitre 1 La forêt\nIl marchait 😀 longtemps.\n1. Préparer la pâte\n2. Cuire le pain\n"+
            "Il attendit.\nI. Les débuts\nIl faisait beau.\nII. La suite\nTexte.\n1.1 Détails\nConclusion\nFin."
        val r=Reperes.chapitresDevines(t)
        assertEquals(listOf("Table des matières","Chapitre 1 La forêt","I. Les débuts","II. La suite","Conclusion"),r.map{it.titre})
        for(x in r)assertEquals(x.titre,t.substring(x.debut,x.debut+x.titre.length))
        assertEquals("Première partie : La forêt",Reperes.chapitresDevines("Intro.\nPremière partie : La forêt\nTexte.").single().titre)
    }
    @Test fun pagesEtPositionCourante() {
        val r=Reperes(listOf("i" to 0,"ii" to 100,"1" to 200,"2" to 300),listOf(Titre("Chapitre 1",1,200),Titre("Chapitre 2",1,320)),"signets")
        assertEquals(100,r.debutPage("II"))
        assertEquals(300,r.debutPage("2"))   // étiquette « 2 » avant le rang 2
        assertEquals(-1,r.debutPage("9"))
        assertEquals("page 2 (4 sur 4) · Chapitre 2",r.ouSuisJe(350,400))
        assertEquals("50 % du texte · Chapitre 1",Reperes(emptyList(),listOf(Titre("Chapitre 1",1,10)),"devinee").ouSuisJe(50,100))
    }
}
