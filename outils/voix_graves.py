"""Cherche les voix d'homme les plus graves parmi les 125 locuteurs de MLS, mesure Tom et Pierre,
et prépare des variantes plus graves et plus posées de Tom et Pierre.
Usage : voix_graves.py phrases.json voix/ sortie/"""
import json, sys, wave
from pathlib import Path
import numpy as np, librosa, soundfile as sf
from piper import PiperVoice, SynthesisConfig
phrases = json.load(open(sys.argv[1], encoding='utf-8'))
voix, sortie = Path(sys.argv[2]), Path(sys.argv[3]); sortie.mkdir(parents=True, exist_ok=True)
TEST = phrases[3]

def dire(v, texte, sid=None, lent=1.0):
    morceaux = [np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in
                v.synthesize(texte, syn_config=SynthesisConfig(speaker_id=sid, length_scale=lent))]
    return np.concatenate(morceaux).astype(np.float32) / 32768, v.config.sample_rate

def hauteur(a, sr):
    f0, voise, _ = librosa.pyin(a, fmin=60, fmax=400, sr=sr, frame_length=2048)
    f0 = f0[voise & ~np.isnan(f0)]
    return float(np.median(f0)) if len(f0) else float('nan')

def ecrire(nom, a, sr):
    sf.write(str(sortie / (nom + '.wav')), a, sr, subtype='PCM_16')

mesures = {}
mls = PiperVoice.load(str(voix / 'fr_FR-mls-medium.onnx'))
for nom, sid in mls.config.speaker_id_map.items():
    a, sr = dire(mls, TEST, sid)
    mesures['mls-' + nom] = hauteur(a, sr)
for fichier, sid, nom in [('fr_FR-tom-medium.onnx', None, 'tom'), ('fr_FR-upmc-medium.onnx', 1, 'pierre'),
                          ('fr_FR-gilles-low.onnx', None, 'gilles'), ('fr_FR-mls_1840-low.onnx', None, 'mls_1840')]:
    v = PiperVoice.load(str(voix / fichier))
    a, sr = dire(v, TEST, sid)
    mesures[nom] = hauteur(a, sr)
classement = sorted((h, n) for n, h in mesures.items() if not np.isnan(h))
json.dump({'phrase_mesuree': TEST, 'hauteur_mediane_hz': {n: round(h, 1) for h, n in classement}},
          open(sortie / 'hauteurs.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
graves = [n for h, n in classement if n.startswith('mls-')][:6]
print('plus graves MLS :', [(n, round(mesures[n])) for n in graves])
for n in graves + ['mls_1840']:
    if n == 'mls_1840':
        v, sid = PiperVoice.load(str(voix / 'fr_FR-mls_1840-low.onnx')), None
    else:
        v, sid = mls, mls.config.speaker_id_map[n[4:]]
    for i, t in enumerate(phrases, 1):
        a, sr = dire(v, t, sid); ecrire(f'{n}-{i}', a, sr)
# Tom et Pierre : un ton plus bas et un peu plus lents (variantes possibles dans le lecteur)
for fichier, sid, nom in [('fr_FR-tom-medium.onnx', None, 'tom'), ('fr_FR-upmc-medium.onnx', 1, 'pierre')]:
    v = PiperVoice.load(str(voix / fichier))
    for i, t in enumerate(phrases, 1):
        a, sr = dire(v, t, sid, lent=1.12)
        ecrire(f'{nom}-pose-{i}', a, sr)
        ecrire(f'{nom}-grave-{i}', librosa.effects.pitch_shift(a, sr=sr, n_steps=-2), sr)
json.dump({'graves': graves}, open(sortie / 'choix.json', 'w'), indent=1)
