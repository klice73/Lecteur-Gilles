"""Ajoute à une voix Piper la durée de chaque son comme seconde sortie (surlignage mot à mot exact sous Windows).
Même principe que piper.patch_voice_with_alignment (Piper 1.8) ; l'audio n'est pas modifié.
Usage : python aligner_voix.py entree.onnx sortie.onnx"""
import sys
import onnx

def aligner(entree, sortie):
    modele = onnx.load(entree)
    ceil = [o for n in modele.graph.node if n.op_type == 'Ceil' for o in n.output]
    if len(ceil) != 1:
        raise SystemExit('Sortie de durée introuvable ou ambiguë : %s' % ceil)
    if ceil[0] not in [o.name for o in modele.graph.output]:
        modele.graph.output.append(onnx.helper.make_tensor_value_info(ceil[0], onnx.TensorProto.FLOAT, None))
    onnx.save(modele, sortie)
    return ceil[0]

if __name__ == '__main__':
    print('Durées exposées :', aligner(sys.argv[1], sys.argv[2]))
