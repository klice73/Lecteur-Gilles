"""Fabrique le carnet Kaggle « Reentrainer-Gilles-Kaggle.ipynb » (tout se fait en une version enregistree)."""
import json, sys, os
ICI = os.path.dirname(os.path.abspath(__file__))
PIPER_COMMIT = "619f513"   # version de piper1-gpl verifiee le 17 oct. 2026 (chaine validee en local)
cellules = []
def md(t): cellules.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)})
def code(t): cellules.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)})

md("""
# Réentraîner Gilles sur Kaggle (avec les nasales an, on, in)

Ce carnet s'exécute **en entier tout seul** quand vous cliquez sur **Save Version** : vous pouvez ensuite fermer
l'onglet et éteindre l'ordinateur. Chaque séance dure au plus environ **10 heures** de calcul, puis s'arrête
proprement en gardant ce qui est appris.

**Avant la première séance (une seule fois)**, dans le panneau de droite du carnet (*Settings* / *Session options*) :
1. **Accelerator** : choisir **GPU T4 x2** (pas la P100 : elle n'est plus prise en charge par la version actuelle de PyTorch).
2. **Internet** : **On**. Si Kaggle refuse, il faut d'abord confirmer votre numéro de téléphone (lien proposé par Kaggle).
3. **Add Input** : chercher `french single speaker speech dataset` (auteur *bryanpark*) et l'ajouter.

**Séance suivante (reprise)** : ouvrez le carnet (bouton **Edit**). Dans le panneau **Input** à droite, **retirez**
l'ancienne sortie du carnet si elle y est déjà, puis **Add Input** → **Your Work** (ou *Notebook Output*) →
choisissez la **dernière version de ce carnet**. Le carnet trouve tout seul la sauvegarde `points/last.ckpt` et repart de là.
Puis **Save Version** → **Save & Run All (Commit)**. Vérifiez au début du journal que la ligne « Reprise depuis ... (époque, pas) »
montre des chiffres plus grands qu'à la séance précédente.

Kaggle donne environ 30 heures de carte graphique par semaine : au plus 3 séances de 10 heures par semaine.

**Résultat de chaque séance** : onglet **Output** de la version : `fr_FR-gilles-medium.onnx`, `fr_FR-gilles-medium.onnx.json`,
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

md("## 3. Les enregistrements de Gilles et la liste des phrases")
code("""
import sys, os, glob
sys.path.insert(0, '/kaggle/tmp/piper1-gpl/src')
import soundfile as sf
transcripts = glob.glob('/kaggle/input/**/transcript.txt', recursive=True)
assert transcripts, "Enregistrements introuvables : Add Input, chercher « french single speaker speech dataset » (bryanpark), puis Save Version."
AUDIO = '/kaggle/input'
par_nom = {}
for dossier, _, fichiers in os.walk(AUDIO):
    if '/points' in dossier:
        continue
    for f in fichiers:
        if f.lower().endswith('.wav') and not f.startswith('essai-'):
            par_nom.setdefault(f, os.path.join(dossier, f))
lignes, ecartes, duree, vus = [], 0, 0.0, set()
with open(transcripts[0], encoding='utf-8') as f:
    for brut in f:
        champs = brut.rstrip('\\n').split('|')
        if len(champs) < 2:
            continue
        nom = os.path.basename(champs[0].strip())
        texte = (champs[2] if len(champs) >= 3 and champs[2].strip() else champs[1]).strip()
        chemin = par_nom.get(nom)
        if not texte or not chemin or nom in vus:
            ecartes += 1
            continue
        d = sf.info(chemin).duration
        if not 0.5 <= d <= 15.0:
            ecartes += 1
            continue
        vus.add(nom)
        lignes.append((os.path.relpath(chemin, AUDIO), texte.replace('|', ' ')))
        duree += d
assert lignes, f'Aucun extrait gardé ({ecartes} écartés)'
os.makedirs('/kaggle/tmp/gilles', exist_ok=True)
with open('/kaggle/tmp/gilles/metadata.csv', 'w', encoding='utf-8') as f:
    for fichier, texte in lignes:
        f.write(fichier + '|' + texte + '\\n')
print(len(lignes), 'extraits gardés,', ecartes, 'écartés,', round(duree / 3600, 1), 'heures')
from piper.phonemize_espeak import EspeakPhonemizer
ph = EspeakPhonemizer().phonemize('fr', 'Un bon vin blanc.')
print('Phonétique :', ph)
assert '\\u0303' in ''.join(''.join(p) for p in ph), 'Signe des nasales absent : ne pas continuer'
""")

md("## 4. Lanceur (suivi lisible, arrêt propre avant la limite de Kaggle)")
code("%%writefile /kaggle/tmp/lancer_piper.py\n" + open(os.path.join(ICI, "lancer_piper.py"), encoding="utf-8").read())

md("""
## 5. Entraîner

* Première séance : départ depuis **Siwis medium** (voix française de même qualité). Séances suivantes : reprise
  de la sauvegarde trouvée dans les entrées (*Add Input* de la version précédente).
* `HEURES` : temps de calcul de la séance (10 h laisse le temps d'exporter avant la limite de 12 h de Kaggle).
* `EPOQUES` : nombre total de passages sur tous les enregistrements ; 60 est un bon objectif.
""")
code("""
import os, glob, shutil, subprocess, time, torch
from huggingface_hub import hf_hub_download
HEURES = 10
EPOQUES = 60
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
deja = glob.glob('/kaggle/input/**/journal.txt', recursive=True) + glob.glob('/kaggle/input/**/fr_FR-gilles-medium.onnx.json', recursive=True)
if deja and not reprise:
    raise SystemExit("ARRET : une sortie de séance précédente est en entrée mais sans sauvegarde (.ckpt). "
                     "Ajoutez en entrée la version qui contient points/last.ckpt, pour ne pas repartir de zéro.")
commande = [sys.executable, '/kaggle/tmp/lancer_piper.py', 'fit',
            '--data.voice_name', 'gilles',
            '--data.csv_path', '/kaggle/tmp/gilles/metadata.csv',
            '--data.audio_dir', AUDIO,
            '--model.sample_rate', '22050',
            '--data.espeak_voice', 'fr',
            '--data.cache_dir', '/kaggle/tmp/gilles/cache',
            '--data.config_path', os.path.join(SORTIE, 'fr_FR-gilles-medium.onnx.json'),
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
ONNX = os.path.join(SORTIE, 'fr_FR-gilles-medium.onnx')
try:
  if not EXPORT_OK:
    raise RuntimeError('pas de sauvegarde à exporter')
  subprocess.run([sys.executable, '-m', 'piper.train.export_onnx', '--checkpoint', os.path.join(POINTS, 'last.ckpt'), '--output-file', ONNX],
                 cwd='/kaggle/tmp/piper1-gpl', check=True)
  from piper import PiperVoice
  voix = PiperVoice.load(ONNX)
  phrases = ["Bonjour, je m'appelle Gilles.",
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
