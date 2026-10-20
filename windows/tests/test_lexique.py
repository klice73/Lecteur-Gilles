"""Lexique de prononciation (1.8) : memes resultats que Prononciations.kt (voir PrononciationsTest.kt)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lecteur as L

lex = L.lire_lexique("# commentaire\nBateson = Bétsonne\nPOETICS-S = Poétix esse\nPOETICS = Poétix\nFreire=Fréïré\nfreire = ignoré (premiere ligne gagnante)\nsans egal\n = vide\n")
assert len(lex) == 5, lex
motif, table = L.motif_lexique(lex)
cas = {
    "Gregory Bateson et BATESON, Batesonien.": "Gregory Bétsonne et Bétsonne, Batesonien.",
    "Le modèle POETICS-S et POETICS.": "Le modèle Poétix esse et Poétix.",
    "Paulo Freire, l'œuvre de Freire": "Paulo Fréïré, l'œuvre de Fréïré",
    "Rien à changer.": "Rien à changer.",
}
for avant, apres in cas.items():
    assert L.appliquer_lexique(avant, motif, table) == apres, (avant, L.appliquer_lexique(avant, motif, table))
assert L.appliquer_lexique("Bateson", *L.motif_lexique([])) == "Bateson"
print('lexique : tous les tests reussis')
