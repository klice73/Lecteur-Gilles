"""Lit les mêmes phrases avec plusieurs voix Piper (comparaison d'écoute). Usage : echantillons.py phrases.json sortie/ voix1.onnx[:locuteur] ..."""
import json, sys, wave
from pathlib import Path
from piper import PiperVoice, SynthesisConfig
phrases = json.load(open(sys.argv[1], encoding='utf-8'))
sortie = Path(sys.argv[2]); sortie.mkdir(parents=True, exist_ok=True)
for arg in sys.argv[3:]:
    chemin, _, locuteur = arg.partition(':')
    v = PiperVoice.load(chemin)
    nom = Path(chemin).stem.replace('fr_FR-', '') + (('-' + locuteur) if locuteur else '')
    sid = None
    if locuteur:
        sid = v.config.speaker_id_map.get(locuteur) if v.config.speaker_id_map else int(locuteur)
    print(nom, 'locuteurs :', v.config.speaker_id_map, 'id', sid, 'Hz', v.config.sample_rate)
    for i, t in enumerate(phrases, 1):
        with wave.open(str(sortie / f'{nom}-{i}.wav'), 'wb') as w:
            v.synthesize_wav(t, w, syn_config=SynthesisConfig(speaker_id=sid))
