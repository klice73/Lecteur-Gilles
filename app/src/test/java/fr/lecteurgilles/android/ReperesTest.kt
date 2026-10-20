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
    @Test fun casDeLAuditCommePython() {
        // mêmes cas que windows/tests/test_reperes.py
        fun titres(s:String)=Reperes.chapitresDevines(s).map{it.titre}
        for(seul in listOf("Chapitre 3","CHAPITRE 12","Partie 2","Annexe 1","Chapitre 1 : Le lac numéro 1"))
            assertEquals(listOf(seul),titres("Texte avant.\n$seul\nTexte apres."))
        assertEquals(listOf("Sommaire","Chapitre 1 La neige","I","II"),
            titres("Sommaire\nChapitre 1 La neige 7\nChapitre 2 Le lac 19\n\nChapitre 1 La neige\nTexte.\nI\nUn.\nEncore.\nII\nDeux.\nEncore."))
        assertEquals(listOf("1. Introduction","2. Portrait","2.1 Détails","3. Fin"),
            titres("1. Introduction\nTexte :\n1. Un\n2. Deux\n3. Trois\n2. Portrait\n2.1 Détails\nTexte.\n3. Fin\nTexte."))
        assertEquals(listOf("Notes"),titres("Ingrédients\n1 L de bouillon\nConclusion : ils étaient perdus, mais ensemble.\nNotes"))
        // contre-audit (mêmes cas que test_reperes.py)
        assertEquals(listOf("Première partie","Chapitre 1","Chapitre 2","Deuxième partie","Chapitre 1","Chapitre 2"),titres("Première partie\nChapitre 1\nTexte.\nChapitre 2\nTexte.\nDeuxième partie\nChapitre 1\nTexte.\nChapitre 2\nTexte."))
        assertEquals(listOf("Première partie","I","II","Deuxième partie","I","II"),titres("Première partie\nI\nTexte.\nSuite.\nII\nTexte.\nSuite.\nDeuxième partie\nI\nTexte.\nSuite.\nII\nTexte.\nSuite."))
        assertEquals(listOf("Chapitre 1"),titres("Chapitre 1\nTexte.\nPartie depuis trois jours.\nLivre-moi ça.\nTexte."))
        assertEquals(listOf("1","2","– 3 –"),titres("1\n\nTexte.\nSuite.\n\n2\n\nTexte.\nSuite.\n– 3 –\nTexte.\nSuite."))
        assertEquals(listOf("Sommaire","Chapitre 1 La neige"),titres("Sommaire\nChapitre 1 La neige 7\n\nChapitre 1 La neige\nTexte."))
        assertEquals(listOf("Chapitre 1","Chapitre 2","Chapitre 12"),titres("Chapitre 1\nTexte.\nChapitre 1\nTexte.\nChapitre 2\nTexte.\nChapitre 12\nTexte."))
        assertEquals(listOf<String>("Première partie","1","2","3","Deuxième partie","4","5"),titres("Première partie\n1\nTexte.\nSuite.\nFin.\n2\nTexte.\nSuite.\nFin.\n3\nTexte.\nSuite.\nFin.\nDeuxième partie\n4\nTexte.\nSuite.\nFin.\n5\nTexte.\nSuite.\nFin.\n"))
        assertEquals(listOf<String>(),titres("Préparation\n1\n\nCouper.\n\n2\n\nCuire.\n\n3\n\nServir."))
        assertEquals(listOf<String>("Chapitre 1","Chapitre premier"),titres("Chapitre 1\nTexte.\nLivre a été publié.\nPartie un peu tôt.\nTome deux arrive.\nChapitre premier\nTexte."))
        assertEquals(listOf<String>(),titres("Il dit :\nUN\nTexte.\nSuite."))
        assertEquals(listOf<String>(),titres((1..30).joinToString(""){"Une ligne.\nUne autre.\nEt il marchait vers\n$it\nla ville.\n"}))   // numéros de page qui coupent les phrases
        val s=(1..6).joinToString(""){"Texte.\nSuite.\nFin.\n$it\n"}
        assertEquals(emptyList<Titre>(),Reperes.chapitresDevines(s,(0 until 6).map{s.indexOf("Texte",it*(s.length/6))}))
        // recherche d'un signet : la ligne qui est le titre, pas sa première mention
        val t="Il pense au soir.\nLe soir\nTexte."
        assertEquals(t.indexOf("Le soir"),Reperes.chercher(t,"le soir",0,t.length))
        // table remise dans l'ordre du texte
        assertEquals(listOf(5,9),Reperes(emptyList(),listOf(Titre("b",1,9),Titre("a",1,5)),"signets").table.map{it.debut})
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
