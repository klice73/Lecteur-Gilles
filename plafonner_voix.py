# -*- coding: utf-8 -*-
"""Plafonne la duree de chaque jeton dans le modele Piper fr_FR-gilles-low.

Cause du « charabia » (mesure du 19 octobre 2026) : sur certaines phrases, le
predicteur de durees de ce modele attribue jusqu'a plusieurs secondes a des
jetons sans son (debut « ^ », silence « _ », fin « $ »). Le decodeur remplit
alors ce temps avec du bredouillement, avant ou apres la parole.

Sur du texte normal, un phoneme dure au plus environ 7 trames (99 % des cas),
une pause de ponctuation au plus environ 21 trames, un jeton sans son au plus
environ 8 trames. Les plafonds sont donc 20 trames (phonemes, ponctuation) et
8 trames (jetons sans son), multiplies par length_scale (le reglage de
vitesse), inseres juste apres le noeud /Ceil du graphe. Le texte, les phonemes et la voix ne changent
pas ; seules les durees aberrantes sont ramenees a une valeur normale.

Usage : python plafonner_voix.py entree.onnx sortie.onnx [--alignement]
--alignement (voix Windows, version 1.5) : expose aussi la duree plafonnee de
chaque son comme seconde sortie du modele. Piper s'en sert pour fournir
l'alignement exact des mots (surlignage mot a mot). Sans effet sur l'audio.
Le fichier .onnx.json de la voix reste le meme (copier-le a cote de la sortie).
"""
import sys

import onnx
from onnx import TensorProto, helper

PLAFOND_TRAMES = 20.0     # phonemes et ponctuation (pauses legitimes jusqu'a ~21)
PLAFOND_SPECIAUX = 8.0    # jetons sans son « _ », « ^ », « $ » (sains : <= 8 dans 99 % des cas)
MARQUE = 'lecteur_gilles_plafond_durees'


def _exposer(m):
    if any(o.name == 'duree_plafonnee' for o in m.graph.output):
        return False
    info = onnx.ValueInfoProto()
    info.name = 'duree_plafonnee'
    m.graph.output.append(info)
    return True


def plafonner(entree, sortie, alignement=False):
    m = onnx.load(entree)
    g = m.graph
    if any(p.key == MARQUE for p in m.metadata_props):
        ajoute = alignement and _exposer(m)
        onnx.save(m, sortie)
        return 'deja plafonne' + (' ; alignement expose' if ajoute else '')
    ceil = [n for n in g.node if n.op_type == 'Ceil']
    gather = [n for n in g.node if n.output and n.output[0] == '/Gather_1_output_0' and 'scales' in n.input]
    if len(ceil) != 1 or len(gather) != 1:
        raise SystemExit('Structure du modele inattendue : correctif non applique.')
    duree = ceil[0].output[0]
    lenteur = gather[0].output[0]
    consommateurs = [n for n in g.node if duree in n.input]
    def cst(nom, typ, val, forme=()):
        return helper.make_node('Constant', [], [nom], value=helper.make_tensor(nom + '_v', typ, list(forme), val))
    # jetons sans son : 0 « _ » (silence entre phonemes), 1 « ^ » (debut), 2 « $ » (fin)
    nouveaux = [
        cst('pl_trois', TensorProto.INT64, [3]),
        cst('pl_axe', TensorProto.INT64, [1], (1,)),
        cst('pl_base', TensorProto.FLOAT, [PLAFOND_TRAMES]),
        cst('pl_reduction', TensorProto.FLOAT, [PLAFOND_TRAMES - PLAFOND_SPECIAUX]),
        helper.make_node('Less', ['input', 'pl_trois'], ['pl_special_b']),
        helper.make_node('Cast', ['pl_special_b'], ['pl_special_f'], to=TensorProto.FLOAT),
        helper.make_node('Unsqueeze', ['pl_special_f', 'pl_axe'], ['pl_special']),
        helper.make_node('Mul', ['pl_special', 'pl_reduction'], ['pl_moins']),
        helper.make_node('Sub', ['pl_base', 'pl_moins'], ['pl_trames']),
        helper.make_node('Mul', ['pl_trames', lenteur], ['plafond_effectif']),
        helper.make_node('Min', [duree, 'plafond_effectif'], ['duree_plafonnee']),
    ]
    for n in consommateurs:
        for i, nom in enumerate(n.input):
            if nom == duree:
                n.input[i] = 'duree_plafonnee'
    position = list(g.node).index(ceil[0]) + 1
    for k, n in enumerate(nouveaux):
        g.node.insert(position + k, n)
    m.metadata_props.add(key=MARQUE, value='%g/%g' % (PLAFOND_TRAMES, PLAFOND_SPECIAUX))
    # le modele d'origine a deja des metadonnees en double : verifier le graphe sur une copie
    verif = onnx.ModelProto()
    verif.CopyFrom(m)
    del verif.metadata_props[:]
    onnx.checker.check_model(verif)
    if alignement:
        _exposer(m)
    onnx.save(m, sortie)
    return 'plafond insere (%d consommateurs rebranches)%s' % (len(consommateurs), ' ; alignement expose' if alignement else '')


if __name__ == '__main__':
    print(plafonner(sys.argv[1], sys.argv[2], '--alignement' in sys.argv[3:]))
