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
# Version 1.9 : voix Tom (homme, qualité moyenne, 44,1 kHz, licence AGPLv3), choisie par l'utilisateur
tom=download('https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fr_FR-tom-medium.tar.bz2',ROOT/'.downloads/tom.tar.bz2')
assets=ROOT/'app/src/main/assets'
assets.mkdir(parents=True,exist_ok=True)
import shutil
# Version 1.10 : l'ancien Gilles (sans nasales) ne sert plus que sous Windows ; il est préparé hors de l'APK.
WIN=ROOT/'.voix-windows'
shutil.rmtree(assets/'vits-piper-fr_FR-gilles-low',ignore_errors=True)
for paquet,nom,dest in [(archive,'vits-piper-fr_FR-gilles-low',WIN),(tom,'vits-piper-fr_FR-tom-medium',assets)]:
    if not (dest/nom).exists():
        dest.mkdir(parents=True,exist_ok=True)
        with tarfile.open(paquet) as tar: tar.extractall(dest,filter='data')
lock=ROOT/'downloads.sha256.json'
actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [aar,archive,tom]}
if lock.exists():
    if json.loads(lock.read_text())!=actual: raise RuntimeError('La somme de contrôle des composants a changé')
else:lock.write_text(json.dumps(actual,indent=2)+'\n')
# Version 1.4 : plafonner les durées aberrantes du modèle (cause du « charabia »).
# Voir plafonner_voix.py. Nécessite le paquet Python onnx.
import sys
sys.path.insert(0,str(ROOT))
from plafonner_voix import plafonner
modele=WIN/'vits-piper-fr_FR-gilles-low'/'fr_FR-gilles-low.onnx'
print('Ancien Gilles (Windows) :',plafonner(str(modele),str(modele)),flush=True)
# Version 1.10 : Gilles réentraîné (nasales), voir modeles/LISEZ-MOI.md ; préparé pour Sherpa-ONNX
from preparer_voix_sherpa import preparer
GM=assets/'vits-piper-fr_FR-gilles-medium'
shutil.rmtree(GM,ignore_errors=True)
print('Gilles nouveau (Android) :',preparer(str(ROOT/'modeles'/'fr_FR-gilles-medium.onnx'),str(ROOT/'modeles'/'fr_FR-gilles-medium.onnx.json'),str(GM)),flush=True)
shutil.copytree(WIN/'vits-piper-fr_FR-gilles-low'/'espeak-ng-data',GM/'espeak-ng-data')
shutil.copy(ROOT/'modeles'/'LISEZ-MOI.md',GM/'MODEL_CARD')
# Version 1.11 : dictionnaire français corrigé (voir langue/LISEZ-MOI.md) pour les deux voix de l'APK
for voix in ('vits-piper-fr_FR-gilles-medium','vits-piper-fr_FR-tom-medium'):
    shutil.copy(ROOT/'langue'/'fr_dict',assets/voix/'espeak-ng-data'/'fr_dict')
print('Gilles (nouveau), Tom et moteur prêts.',flush=True)
