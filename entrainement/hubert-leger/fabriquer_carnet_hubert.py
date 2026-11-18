"""Fabrique le carnet Kaggle « Hubert-Leger-Kaggle.ipynb » (etape 2 du Hubert leger, d apres le carnet de Gilles) (tout se fait en une version enregistree)."""
import json, sys, os
ICI = os.path.dirname(os.path.abspath(__file__))
PIPER_COMMIT = "619f513"   # version de piper1-gpl verifiee le 17 oct. 2026 (chaine validee en local)
cellules = []
def md(t): cellules.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)})
def code(t): cellules.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)})

md("""
# Hubert léger, étape 2 : entraîner une voix légère qui lit en direct

Ce carnet apprend à une voix **Piper** (légère, comme Gilles) à parler comme Hubert, à partir des phrases lues à
l'étape 1. Il s'exécute **en entier tout seul** avec **Save Version** ; chaque séance dure au plus environ **10 heures**,
puis s'arrête proprement en gardant ce qui est appris.

**Gardez ce carnet en Private** : il contient la voix clonée.

**Avant la première séance (une seule fois)**, panneau de droite :
1. **Accelerator** : **GPU T4 x2**.
2. **Internet** : **On**.
3. **Add Input** → **Your Work** → **Notebooks** → la **dernière version** du carnet « Hubert-Phrases » (étape 1).

**Séance suivante (reprise)** : **Add Input** → **Your Work** → **Notebooks** → la **dernière version de ce carnet-ci**
(retirez l'ancienne si elle y est déjà). Gardez aussi l'entrée « Hubert-Phrases ». Le carnet trouve tout seul
`points/last.ckpt` et repart de là ; au début du journal, la ligne « Reprise depuis ... (époque, pas) » doit montrer
des chiffres plus grands qu'à la séance précédente.

**Résultat de chaque séance** : onglet **Output** : `fr_FR-hubert-medium.onnx`, `fr_FR-hubert-medium.onnx.json`,
quatre essais `essai-1.wav` à `essai-4.wav` à écouter, et `journal.txt`.
""")

md("## 1. Carte graphique")
code("""
import subprocess
r = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
print(r.stdout or r.stderr)
assert r.returncode == 0, "Pas de carte graphique : panneau de droite, Accelerator = GPU T4 x2, puis Save Version."
import torch, sys, shutil
print('Python du carnet :', sys.executable, '; python du terminal :', shutil.which('python'))
assert torch.cuda.get_device_capability() >= (7, 0), "Carte trop ancienne (P100) : choisir Accelerator = GPU T4 x2"
print(subprocess.run(['df', '-h', '/kaggle/working', '/tmp'], capture_output=True, text=True).stdout)
""")

md("## 2. Installer Piper (environ 5 minutes ; Internet doit être activé)")
code(f"""
%%bash
set -e
if ! curl -sI https://github.com > /dev/null; then echo "PAS D INTERNET : panneau de droite, Internet = On (confirmer le telephone si demande)"; exit 1; fi
apt-get -qq update && apt-get -qq install -y build-essential cmake ninja-build > /dev/null
which python
mkdir -p /kaggle/tmp && cd /kaggle/tmp
[ -d piper1-gpl ] || git clone -q https://github.com/OHF-voice/piper1-gpl.git
cd piper1-gpl
git checkout -q {PIPER_COMMIT}
python -m pip install -q -e '.[train]' 'scikit-build<1' huggingface_hub soundfile lightning==2.6.6 jsonargparse==4.52.0 librosa==0.11.0 pysilero-vad==2.1.1
./build_monotonic_align.sh > /dev/null
grep -q "dynamo=False" src/piper/train/export_onnx.py || sed -i 's/^        verbose=False,$/        verbose=False,\\n        dynamo=False,/' src/piper/train/export_onnx.py
python setup.py build_ext --inplace > /kaggle/tmp/compilation.log 2>&1 || (tail -20 /kaggle/tmp/compilation.log; exit 1)
python -c "import piper.train, torch; from piper import espeakbridge; print('Piper pret, torch', torch.__version__, 'GPU', torch.cuda.is_available())"
""")

md("## 3. Les phrases lues par Hubert (étape 1)")
code("""
import sys, os, glob, wave
sys.path.insert(0, '/kaggle/tmp/piper1-gpl/src')
metas = [p for p in glob.glob('/kaggle/input/**/hubert-phrases/metadata.csv', recursive=True)]
assert metas, "Phrases introuvables : Add Input, Your Work, Notebooks, la derniere version du carnet Hubert-Phrases (etape 1)"
metas.sort(key=lambda p: sum(1 for _ in open(p, encoding='utf-8')), reverse=True)
AUDIO = os.path.dirname(metas[0])
lignes, ecartes, duree, vus = [], 0, 0.0, set()
for brut in open(metas[0], encoding='utf-8'):
    if '|' not in brut: continue
    nom, texte = brut.rstrip('\\n').split('|', 1)
    chemin = os.path.join(AUDIO, nom)
    if nom in vus or not texte.strip() or not os.path.isfile(chemin):
        ecartes += 1; continue
    with wave.open(chemin) as w: d = w.getnframes() / w.getframerate(); ok = w.getframerate() == 22050
    if not ok or not 0.5 <= d <= 15.0:
        ecartes += 1; continue
    vus.add(nom); lignes.append((nom, texte.strip().replace('|', ' '))); duree += d
assert len(lignes) >= 500, f'Trop peu de phrases ({len(lignes)}) : terminer l etape 1 d abord'
os.makedirs('/kaggle/tmp/hubert', exist_ok=True)
with open('/kaggle/tmp/hubert/metadata.csv', 'w', encoding='utf-8') as f:
    for fichier, texte in lignes:
        f.write(fichier + '|' + texte + '\\n')
print(len(lignes), 'phrases gardées,', ecartes, 'écartées,', round(duree / 3600, 1), 'heures ; dossier', AUDIO)
from piper.phonemize_espeak import EspeakPhonemizer
ph = EspeakPhonemizer().phonemize('fr', 'Un bon vin blanc.')
print('Phonétique :', ph)
assert '\\u0303' in ''.join(''.join(p) for p in ph), 'Signe des nasales absent : ne pas continuer'
""")

md("## 4. Lanceur (suivi lisible, arrêt propre avant la limite de Kaggle)")
code("%%writefile /kaggle/tmp/lancer_piper.py\n" + open(os.path.join(ICI, "..", "lancer_piper.py"), encoding="utf-8").read())

md("""
## 5. Entraîner

* Première séance : départ depuis **Siwis medium** (voix française de même qualité). Séances suivantes : reprise
  de la sauvegarde trouvée dans les entrées (*Add Input* de la version précédente).
* `HEURES` : temps de calcul de la séance (10 h laisse le temps d'exporter avant la limite de 12 h de Kaggle).
* `EPOQUES` : nombre total de passages sur toutes les phrases ; 100 est un bon objectif (moins de phrases que pour Gilles).
""")
code("""
import os, glob, shutil, subprocess, time, torch
from huggingface_hub import hf_hub_download
HEURES = 10
EPOQUES = 100
LOT = 16
SORTIE = '/kaggle/working'
POINTS = os.path.join(SORTIE, 'points')
os.makedirs(POINTS, exist_ok=True)
def etat(chemin):
    try:
        c = torch.load(chemin, map_location='cpu', weights_only=False, mmap=True)
        return (c.get('epoch', -1), c.get('global_step', -1))
    except Exception as e:
        print('Sauvegarde illisible :', chemin, e)
        return None
candidats = [(etat(p), p) for p in glob.glob('/kaggle/input/**/points/*.ckpt', recursive=True)]
candidats = [c for c in candidats if c[0] is not None]
reprise = max(candidats)[1] if candidats else None
deja = glob.glob('/kaggle/input/**/journal.txt', recursive=True) + glob.glob('/kaggle/input/**/fr_FR-hubert-medium.onnx.json', recursive=True)
if deja and not reprise:
    raise SystemExit("ARRET : une sortie de séance précédente est en entrée mais sans sauvegarde (.ckpt). "
                     "Ajoutez en entrée la version qui contient points/last.ckpt, pour ne pas repartir de zéro.")
commande = [sys.executable, '/kaggle/tmp/lancer_piper.py', 'fit',
            '--data.voice_name', 'hubert',
            '--data.csv_path', '/kaggle/tmp/hubert/metadata.csv',
            '--data.audio_dir', AUDIO,
            '--model.sample_rate', '22050',
            '--data.espeak_voice', 'fr',
            '--data.cache_dir', '/kaggle/tmp/hubert/cache',
            '--data.config_path', os.path.join(SORTIE, 'fr_FR-hubert-medium.onnx.json'),
            '--data.batch_size', str(LOT),
            '--data.num_workers', '3',
            '--data.validation_split', '0.02',
            '--trainer.accelerator', 'gpu', '--trainer.devices', '1',
            '--trainer.max_epochs', str(EPOQUES),
            '--model.mos_metric', 'none',
            '--trainer.enable_progress_bar', 'false',
            '--trainer.default_root_dir', '/kaggle/tmp/journaux']
if reprise:
    print('Reprise depuis', reprise, '(époque, pas) =', max(candidats)[0])
    commande += ['--ckpt_path', reprise]
else:
    SIWIS = hf_hub_download(repo_id='rhasspy/piper-checkpoints', repo_type='dataset',
                            filename='fr/fr_FR/siwis/medium/epoch=3304-step=2050940.ckpt')
    print('Premier départ depuis Siwis medium')
    commande += ['--model.warmstart_ckpt', SIWIS]
env = dict(os.environ, POINTS=POINTS, SUIVI='100', TOUS_LES='1000', BUDGET_S=str(int(HEURES * 3600)), PYTHONUNBUFFERED='1')
journal = open(os.path.join(SORTIE, 'journal.txt'), 'a')
p = subprocess.Popen(commande, cwd='/kaggle/tmp/piper1-gpl', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
for ligne in p.stdout:
    journal.write(ligne); journal.flush()
    if ligne.startswith(('DEBUT', 'SUIVI', 'ARRET')):
        print(time.strftime('%H:%M'), ligne.rstrip(), flush=True)
    elif 'Error' in ligne or 'Traceback' in ligne:
        print(ligne.rstrip()[-300:], flush=True)
code = p.wait()
journal.close()
# ne garder que la sauvegarde la plus avancee, sous le nom last.ckpt (la sortie Kaggle reste petite)
points = [(etat(f), f) for f in glob.glob(os.path.join(POINTS, '*.ckpt'))]
points = [c for c in points if c[0] is not None]
if not points and reprise:
    shutil.copy2(reprise, os.path.join(POINTS, 'last.ckpt'))   # la sortie garde au moins le point de depart
    print('ECHEC avant la premiere sauvegarde : sauvegarde de depart recopiee dans la sortie (rien n est perdu)')
    points = [(etat(os.path.join(POINTS, 'last.ckpt')), os.path.join(POINTS, 'last.ckpt'))]
EXPORT_OK = bool(points)
if not points:
    print(f'Aucune sauvegarde produite (code {code}) : envoyez la fin de journal.txt (onglet Output) à Claude')
    points = [((-1, -1), None)]
meilleur = max(points, key=lambda c: c[0])[1]
for _, f in points:
    if f and f != meilleur:
        os.remove(f)
if meilleur and meilleur != os.path.join(POINTS, 'last.ckpt'):
    os.replace(meilleur, os.path.join(POINTS, 'last.ckpt'))
print('Code', code, '; sauvegarde gardée : points/last.ckpt (époque, pas) =', max(points, key=lambda c: c[0])[0])
if code != 0:
    print('ATTENTION : calcul interrompu par une erreur ; la sauvegarde ci-dessus reste utilisable. Voir journal.txt')
""")

md("## 6. Exporter la voix et faire quatre essais")
code("""
import os, subprocess, wave, traceback
sys.path.insert(0, '/kaggle/tmp/piper1-gpl/src')
ONNX = os.path.join(SORTIE, 'fr_FR-hubert-medium.onnx')
try:
  if not EXPORT_OK:
    raise RuntimeError('pas de sauvegarde à exporter')
  subprocess.run([sys.executable, '-m', 'piper.train.export_onnx', '--checkpoint', os.path.join(POINTS, 'last.ckpt'), '--output-file', ONNX],
                 cwd='/kaggle/tmp/piper1-gpl', check=True)
  from piper import PiperVoice
  voix = PiperVoice.load(ONNX)
  phrases = ["Bonjour, ceci est un essai de lecture.",
           "Un bon vin blanc, du pain, du jambon et des oignons.",
           "Les enfants chantent longtemps dans le vent du printemps.",
           "On pourrait penser que les idées de Freire sont datées ; pourtant, elles sont plus pertinentes que jamais."]
  for i, t in enumerate(phrases):
    with wave.open(os.path.join(SORTIE, f'essai-{i+1}.wav'), 'wb') as w:
        voix.synthesize_wav(t, w)
  print('Voix exportée et essais écrits dans Output :', sorted(os.listdir(SORTIE)))
except Exception:
  traceback.print_exc()
  print('EXPORT IMPOSSIBLE : la sauvegarde points/last.ckpt reste dans Output, la séance suivante repartira de là.')
""")

carnet = {"cells": cellules,
          "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                       "language_info": {"name": "python"},
                       "kaggle": {"accelerator": "gpu", "isInternetEnabled": True, "isGpuEnabled": True}},
          "nbformat": 4, "nbformat_minor": 5}
json.dump(carnet, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('carnet ecrit :', sys.argv[1], len(cellules), 'cellules')
