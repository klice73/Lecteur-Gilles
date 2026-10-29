package fr.lecteurgilles.android
import org.junit.Assert.*
import org.junit.Test

class PrononciationsTest {
    @Test fun commeLecteurPy() {
        // mêmes cas que windows/tests/test_lexique.py
        val p=Prononciations.lire("# commentaire\nBateson = Bétsonne\nPOETICS-S = Poétix esse\nPOETICS = Poétix\nFreire=Fréïré\nfreire = ignoré (premiere ligne gagnante)\nsans egal\n = vide\n")
        assertEquals(4,p.taille)
        assertEquals("Gregory Bétsonne et Bétsonne, Batesonien.",p.appliquer("Gregory Bateson et BATESON, Batesonien."))
        assertEquals("Le modèle Poétix esse et Poétix.",p.appliquer("Le modèle POETICS-S et POETICS."))
        assertEquals("Paulo Fréïré, l'œuvre de Fréïré",p.appliquer("Paulo Freire, l'œuvre de Freire"))
        assertEquals("Rien à changer.",p.appliquer("Rien à changer."))
        assertEquals("Bateson",Prononciations.lire("").appliquer("Bateson"))
        // apostrophe typographique et BOM (audit 1.8), comme test_lexique.py
        assertEquals("Fréïré book, Fréïré, Bétsonne",Prononciations.lire("\uFEFFFreire's = Fréïré\nBateson = Bétsonne").appliquer("Freire’s book, Freire's, Bateson"))
        // 1.11 : corrections automatiques du moteur, mêmes cas que test_lexique.py
        val vide=Prononciations.lire("")
        assertEquals("Plus qu' hier, qu' histoire, Qu' Hector.",vide.appliquer("Plus qu'hier, qu’histoire, Qu'Hector."))
        assertEquals("jusqu'hier, lorsqu'il, qu'il",vide.appliquer("jusqu'hier, lorsqu'il, qu'il"))
        assertEquals("quoiqu' habile, Quoiqu' Henri",vide.appliquer("quoiqu'habile, Quoiqu’Henri"))
        assertEquals("d'aujourdhui, D’aujourdhui, aujourd'hui",vide.appliquer("d'aujourd'hui, D’aujourd’hui, aujourd'hui"))
    }
}
