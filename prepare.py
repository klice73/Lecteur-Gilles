"""Télécharge les composants officiels. Aucun document utilisateur n'est inclus."""
from pathlib import Path
import urllib.request
import zipfile
import tarfile
import hashlib
import json

ROOT=Path(__file__).resolve().parent
def download(url,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        temp=path.with_suffix(path.suffix+'.part')
        with urllib.request.urlopen(url,timeout=90) as response, temp.open('wb') as out:
            while block:=response.read(1024*1024): out.write(block)
        temp.replace(path)
    return path
aar=download('https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar',ROOT/'app/libs/sherpa-onnx-1.13.8.aar')
archive=download('https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fr_FR-gilles-low.tar.bz2',ROOT/'.downloads/gilles.tar.bz2')
assets=ROOT/'app/src/main/assets'
assets.mkdir(parents=True,exist_ok=True)
if not (assets/'vits-piper-fr_FR-gilles-low').exists():
    with tarfile.open(archive) as tar: tar.extractall(assets,filter='data')
lock=ROOT/'downloads.sha256.json'
actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [aar,archive]}
if lock.exists():
    if json.loads(lock.read_text())!=actual: raise RuntimeError('La somme de contrôle des composants a changé')
else:lock.write_text(json.dumps(actual,indent=2)+'\n')
# Version 1.4 : plafonner les durées aberrantes du modèle (cause du « charabia »).
# Voir plafonner_voix.py. Nécessite le paquet Python onnx.
import sys
sys.path.insert(0,str(ROOT))
from plafonner_voix import plafonner
modele=assets/'vits-piper-fr_FR-gilles-low'/'fr_FR-gilles-low.onnx'
print('Voix :',plafonner(str(modele),str(modele)),flush=True)
print('Gilles et moteur prêts.',flush=True)
