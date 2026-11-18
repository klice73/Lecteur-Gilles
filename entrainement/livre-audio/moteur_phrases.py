"""Phrases d'entrainement lues par la voix Hubert (qwentts.cpp), pour entrainer ensuite une voix Piper legere.
Sortie : wavs/hubert_NNNNN.wav (22 050 Hz, mono, 16 bits) + metadata-K.csv (wavs/...|texte) + rejets-K.txt.
Reprise : les dossiers de sortie precedents (marque hubert-phrases.txt) passes avec --reprise sont recopies."""
import argparse, json, os, random, re, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from moteur_livre import trouver_voix, synthese_morceaux, gain

MARQUE = 'hubert-phrases.txt'

def choisir_phrases(transcript, nombre, graine=7):
    vues, res = set(), []
    for brut in Path(transcript).read_text(encoding='utf-8', errors='replace').splitlines():
        c = brut.split('|')
        if len(c) < 2: continue
        t = (c[2] if len(c) >= 3 and c[2].strip() else c[1]).strip()
        t = re.sub(r'\s+', ' ', t.replace('«', '').replace('»', '').replace('_', ' ')).strip()
        if not 25 <= len(t) <= 180 or not re.search(r'[a-zà-ÿ]', t) or re.search(r'[0-9<>{}\[\]#@*=]', t): continue
        if re.search(r'\b(M|Mme|Mlle|MM|Mgr|Dr|St|Ste|etc)\.|\b[IVXLC]{2,}\b|\b[A-Z]{2,}\b', t): continue   # abreviations, chiffres romains, sigles
        if t.lower() in vues: continue
        vues.add(t.lower()); res.append(t)
    random.Random(graine).shuffle(res)
    return res[:nombre]

def rogner(a, seuil=300, marge=2400):
    import numpy as np
    fort = np.nonzero(np.abs(a) > seuil)[0]
    if len(fort) == 0: return a[:0]
    return a[max(0, fort[0] - marge):fort[-1] + marge]

def plus_long_silence(a, seuil=300, fen=480):
    import numpy as np
    n = len(a) // fen
    if n == 0: return 0.0
    rms = np.sqrt((a[:n * fen].astype('float64').reshape(n, fen) ** 2).mean(axis=1))
    plus, cur = 0, 0
    for calme in rms < seuil:
        cur = cur + 1 if calme else 0; plus = max(plus, cur)
    return plus * fen / 24000

def ecrire_wav(pcm24, cible):
    import numpy as np
    a = rogner(np.frombuffer(pcm24, dtype='<i2'))
    if plus_long_silence(a) > 0.8: return -1.0          # longue pause au milieu de la phrase
    tmp = str(cible) + '.part.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'pipe:0',
                    '-af', 'aresample=22050:resampler=soxr', '-map_metadata', '-1', '-fflags', '+bitexact', '-c:a', 'pcm_s16le', tmp], input=a.tobytes(), check=True)
    os.replace(tmp, cible)
    return len(a) / 24000

def reprendre(reprise, sortie):
    (sortie / 'wavs').mkdir(parents=True, exist_ok=True)
    (sortie / MARQUE).write_text('reprise\n', encoding='utf-8')
    if True:
        if reprise:
            vus = {sortie.resolve()}
            for m in Path(reprise).rglob(MARQUE):
                anc = m.parent
                if anc.resolve() in vus: continue
                vus.add(anc.resolve())
                for f in anc.glob('*metadata-*.csv'):
                    for l in f.read_text(encoding='utf-8').splitlines():
                        nom = l.split('|', 1)[0]
                        if (anc / nom).is_file() and not (sortie / nom).exists(): shutil.copy2(anc / nom, sortie / nom)
                for f in list(anc.glob('*metadata-*.csv')) + list(anc.glob('*rejets-*.txt')):
                    cible = sortie / ('ancien-' + f.name if not f.name.startswith('ancien-') else f.name)
                    lignes = {}
                    for src in ([cible] if cible.exists() else []) + [f]:
                        for l in src.read_text(encoding='utf-8').splitlines():
                            if l.strip(): lignes.setdefault(l.split('|', 1)[0], l)
                    cible.write_text(''.join(l + '\n' for l in lignes.values()), encoding='utf-8')

def main():
    a = argparse.ArgumentParser()
    a.add_argument('--qwen', required=True); a.add_argument('--dossier-voix', required=True)
    a.add_argument('--transcript', required=True); a.add_argument('--sortie', required=True)
    a.add_argument('--reprise', default=''); a.add_argument('--nombre', type=int, default=4000)
    a.add_argument('--heures', type=float, default=10.0); a.add_argument('--device', default='')
    a.add_argument('--tranche', default='0/1'); a.add_argument('--bloc', type=int, default=50)
    a.add_argument('--seed', type=int, default=42)
    a.add_argument('--modele', default='')
    a.add_argument('--reprise-seule', action='store_true', help='seulement recopier les seances precedentes (a faire une fois, avant les tranches)')
    o = a.parse_args()
    t0 = time.time(); budget = o.heures * 3600
    k, n = (int(x) for x in o.tranche.split('/'))
    if o.reprise_seule:
        reprendre(o.reprise, Path(o.sortie)); return
    voix = trouver_voix(o.dossier_voix, o.modele)
    print('Voix :', json.dumps({c: Path(v).name if isinstance(v, str) else v for c, v in voix.items()}), flush=True)
    phrases = choisir_phrases(o.transcript, o.nombre)
    sortie = Path(o.sortie); (sortie / 'wavs').mkdir(parents=True, exist_ok=True)
    (sortie / MARQUE).write_text('%d phrases\n' % len(phrases), encoding='utf-8')
    faits = set()
    for f in list(sortie.glob('metadata-*.csv')) + list(sortie.glob('ancien-metadata-*.csv')):
        for l in f.read_text(encoding='utf-8').splitlines():
            if '|' in l and (sortie / l.split('|', 1)[0]).is_file(): faits.add(l.split('|', 1)[0])
    for f in list(sortie.glob('rejets-*.txt')) + list(sortie.glob('ancien-rejets-*.txt')):
        faits.update(l.split('|', 1)[0] for l in f.read_text(encoding='utf-8').splitlines() if l)
    a_faire = [(i, t) for i, t in enumerate(phrases) if i % n == k and 'wavs/hubert_%05d.wav' % i not in faits]
    print('%d phrases au total ; tranche %d/%d : %d a faire' % (len(phrases), k, n, len(a_faire)), flush=True)
    meta = open(sortie / ('metadata-%d.csv' % k), 'a', encoding='utf-8')
    rej = open(sortie / ('rejets-%d.txt' % k), 'a', encoding='utf-8')
    journal = str(sortie / ('journal-phrases-%d.txt' % k))
    durees, gardees, rejetees, audio = [], 0, 0, 0.0
    for j in range(0, len(a_faire), o.bloc):
        bloc = a_faire[j:j + o.bloc]
        reste = budget - (time.time() - t0)
        if reste <= 0 or (durees and 1.3 * max(durees) > reste):
            print('ARRET temps alloue presque ecoule ; relancez avec la sortie en entree pour continuer', flush=True); break
        debut = time.time()
        try:
            sons = synthese_morceaux(o.qwen, voix, [t for _, t in bloc], o.device, journal, o.seed)
        except Exception as e:
            print('bloc %d en echec (%s) : reprise phrase par phrase' % (bloc[0][0], e), flush=True)
            sons = []
            for i, t in bloc:
                try: sons.append(synthese_morceaux(o.qwen, voix, [t], o.device, journal, o.seed)[0])
                except Exception: sons.append(None)
        for (i, t), pcm in zip(bloc, sons):
            nom = 'wavs/hubert_%05d.wav' % i
            if pcm is None:
                rej.write('%s|echec du moteur\n' % nom); rejetees += 1; continue
            d = ecrire_wav(gain(pcm), sortie / nom)
            vitesse = len(t) / d if d > 0 else 0
            if not (0.8 <= d <= 15.0 and 7.0 <= vitesse <= 25.0):   # phrase avalee, repetee, bloquee ou longue pause
                (sortie / nom).unlink(missing_ok=True); rej.write('%s|%.1f s|%.1f car/s\n' % (nom, d, vitesse)); rejetees += 1
                continue
            meta.write('%s|%s\n' % (nom, t)); gardees += 1; audio += d
        meta.flush(); rej.flush()
        durees.append(time.time() - debut)
        print('bloc %d : %d gardees, %d rejetees, %.1f min d audio en tout, %.1f min de calcul pour ce bloc, seance %.2f h' % (
            j // o.bloc + 1, gardees, rejetees, audio / 60, durees[-1] / 60, (time.time() - t0) / 3600), flush=True)
    print('BILAN tranche %d : %d gardees (%.1f min), %d rejetees, %d restent' % (
        k, gardees, audio / 60, rejetees, max(0, len(a_faire) - gardees - rejetees)), flush=True)

if __name__ == '__main__':
    main()
