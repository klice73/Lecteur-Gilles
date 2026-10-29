"""Prépare une voix Piper pour Sherpa-ONNX (Android) : métadonnées dans le modèle et tokens.txt.
Même format que les paquets vits-piper-* publiés par Sherpa-ONNX ; poids et audio inchangés.
Usage : python preparer_voix_sherpa.py voix.onnx voix.onnx.json dossier_sortie"""
import json, shutil, sys
from pathlib import Path
import onnx

def preparer(modele, config, sortie):
    sortie = Path(sortie); sortie.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path(config).read_text(encoding='utf-8'))
    m = onnx.load(modele)
    meta = {'model_type': 'vits', 'comment': 'piper', 'language': 'French', 'voice': cfg['espeak']['voice'],
            'has_espeak': '1', 'n_speakers': str(cfg['num_speakers']), 'sample_rate': str(cfg['audio']['sample_rate'])}
    del m.metadata_props[:]
    for k, v in meta.items():
        m.metadata_props.add(key=k, value=v)
    nom = Path(modele).name
    onnx.save(m, str(sortie / nom))
    with open(sortie / 'tokens.txt', 'w', encoding='utf-8', newline='\n') as f:
        for sym, ids in sorted(cfg['phoneme_id_map'].items()):
            if len(sym) != 1:   # Sherpa lit un seul caractère par ligne ; Piper découpe les phonèmes caractère par caractère
                continue
            f.write(f'{sym} {ids[0]}\n')
    shutil.copy(config, sortie / (nom + '.json'))
    return meta

if __name__ == '__main__':
    print(preparer(*sys.argv[1:4]))
