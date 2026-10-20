"""Tests des reperes (pages et table des matieres). Lancer depuis windows/ : python tests/test_reperes.py"""
import sys, json
from pathlib import Path
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import documents as D

def lire(r, o, n):
    return r['text'].encode('utf-16-le')[2 * o:2 * (o + n)].decode('utf-16-le')

def verifier(nom, pages, table, source, clean=False):
    r = D.extract(str(ICI / nom), clean_pdf=clean)
    assert r['source_table'] == source, (nom, r['source_table'])
    assert [p[0] for p in r['pages']] == pages, (nom, r['pages'])
    assert [(t, n) for t, n, _ in r['table']] == table, (nom, r['table'])
    for t, n, o in r['table']:
        debut = lire(r, o, len(t) + 3)
        assert t.split()[0].lower() in debut.lower(), (nom, t, debut)
    offs = [o for _, o in r['pages']]
    assert offs == sorted(offs) and (not offs or offs[0] == 0), (nom, offs)
    return r

verifier('livre.pdf', ['i', 'ii', '1', '2', '3', '4'], [('Chapitre 1 La neige', 1), ('La cabane', 2), ('Chapitre 2 Le lac', 1)], 'signets', clean=True)
verifier('livre.pdf', ['i', 'ii', '1', '2', '3', '4'], [('Chapitre 1 La neige', 1), ('La cabane', 2), ('Chapitre 2 Le lac', 1)], 'signets')
verifier('sans-signets.pdf', ['1', '2', '3', '4'], [('Introduction', 1), ('Chapitre 1 La neige', 1), ('Chapitre 2 Le lac', 1), ('Conclusion', 1)], 'devinee')
verifier('document.docx', ['1', '2'], [('Premiere partie', 1), ('Le depart', 2), ('Deuxieme partie', 1)], 'titres')
verifier('document.odt', ['1', '2'], [('Premier titre', 1), ('Sous-titre', 2), ('Second titre', 1)], 'titres')
verifier('livre3.epub', [], [('Chapitre 1 : Le départ', 1), ('Le soir', 2), ('Chapitre 2 : Le retour', 1)], 'table du livre')
verifier('livre2.epub', [], [('Chapitre 1 : Le départ', 1), ('Chapitre 2 : Le retour', 1)], 'table du livre')
r = verifier('notes.md', [], [('Mon carnet', 1), ('Lundi', 2), ('Mardi', 2)], 'titres')
# texte colle : table imprimee ignoree, liste numerotee ignoree, titres retrouves
t = ("Table des matières\nChapitre 1 La forêt ........ 12\nChapitre 2 Le lac 27\n\n"
     "Chapitre 1 La forêt\nIl marchait \U0001F600 longtemps.\n1. Préparer la pâte\n2. Cuire le pain\n"
     "Il attendit.\nI. Les débuts\nIl faisait beau.\nII. La suite\nTexte.\n1.1 Détails\nConclusion\nFin.")
g = D.reperes_texte(t)
assert [x[0] for x in g['table']] == ['Table des matières', 'Chapitre 1 La forêt', 'I. Les débuts', 'II. La suite', 'Conclusion'], g['table']
u = t.encode('utf-16-le')
for titre, _, o in g['table']:
    assert u[2 * o:2 * (o + len(titre))].decode('utf-16-le') == titre, (titre, o)
# constats de l'audit 1.6
r = verifier('ancres.epub', [], [('Le d\u00e9part', 2), ('Le soir', 3), ('Le retour', 1)], 'table du livre')
assert lire(r, r['table'][1][2], 7) == 'Le soir' and lire(r, r['table'][1][2] - 1, 1) == '\n', 'ancre : titre et non premiere occurrence'
verifier('style-perso.docx', [], [('Mon grand titre perso', 1), ('Un titre normal', 2)], 'titres')
verifier('code.md', [], [('Vrai titre', 1), ('Second', 2)], 'titres')
for titre_seul in ('Chapitre 3', 'CHAPITRE 12', 'Partie 2', 'Annexe 1', 'Chapitre 1 : Le lac num\u00e9ro 1'):
    g = D.reperes_texte('Texte avant.\n' + titre_seul + '\nTexte apres.')
    assert [x[0] for x in g['table']] == [titre_seul], (titre_seul, g['table'])
g = D.reperes_texte('Sommaire\nChapitre 1 La neige 7\nChapitre 2 Le lac 19\n\nChapitre 1 La neige\nTexte.\nI\nUn.\nII\nDeux.')
assert [x[0] for x in g['table']] == ['Sommaire', 'Chapitre 1 La neige', 'I', 'II'], g['table']
g = D.reperes_texte('1. Introduction\nTexte :\n1. Un\n2. Deux\n3. Trois\n2. Portrait\n2.1 D\u00e9tails\nTexte.\n3. Fin\nTexte.')
assert [x[0] for x in g['table']] == ['1. Introduction', '2. Portrait', '2.1 D\u00e9tails', '3. Fin'], g['table']
g = D.reperes_texte('Ingr\u00e9dients\n1 L de bouillon\nConclusion : ils \u00e9taient perdus, mais ensemble.\nNotes')
assert [x[0] for x in g['table']] == ['Notes'], g['table']
print('reperes : tous les tests reussis')
