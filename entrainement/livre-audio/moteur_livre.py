"""Livre audio avec la voix Hubert (qwentts.cpp) : un MP3 par chapitre, reprise possible, arret avant la limite de temps.
Usage : python moteur_livre.py --qwen BIN --dossier-voix DIR --livre FICHIER --sortie DIR [--reprise DIR] [--heures H] [--device CUDA0]"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time, unicodedata
from pathlib import Path

ENTETE = b'RIFF\xff\xff\xff\x7fWAVEfmt '          # en-tete fixe du flux de qwen-tts (-o - --stream-by-line)
GAIN = 1.21275                                      # gain valide pour Hubert (hubert_local.py)

def nombre(n):
    u = ['zéro','un','deux','trois','quatre','cinq','six','sept','huit','neuf','dix','onze','douze','treize','quatorze','quinze','seize','dix-sept','dix-huit','dix-neuf']
    if n < 20: return u[n]
    if n < 70:
        d = ['','','vingt','trente','quarante','cinquante','soixante'][n//10]
        return d if n % 10 == 0 else d + (' et un' if n % 10 == 1 else '-' + u[n % 10])
    if n < 80: return 'soixante et onze' if n == 71 else 'soixante-' + nombre(n-60)
    if n == 80: return 'quatre-vingts'
    if n < 100: return 'quatre-vingt-' + nombre(n-80)
    return str(n)

def lexique(chemin):
    table = {}
    if chemin and Path(chemin).exists():
        for l in Path(chemin).read_text(encoding='utf-8-sig', errors='replace').splitlines():
            l = l.strip()
            if not l or l.startswith('#') or '=' not in l: continue
            a, b = l.split('=', 1)
            if a.strip() and b.strip(): table[a.strip().replace('’', "'").lower()] = b.strip()
    if not table: return lambda t: t
    lettres = r"0-9A-Za-zÀ-ÖØ-öø-ɏ"
    motif = re.compile('(?<![' + lettres + '])(' + '|'.join(sorted((re.escape(k).replace("'", "['’]") for k in table), key=len, reverse=True)) + ')(?![' + lettres + '])', re.I)
    return lambda t: motif.sub(lambda m: table.get(m.group(0).replace('’', "'").lower(), m.group(0)), t)

def a_dire(t, lex):
    t = lex(t)
    t = t.replace('«', '').replace('»', '').replace(' ', ' ').replace(' ', ' ')
    t = re.sub(r'(?i)^\s*chapitre\s+(\d{1,3})\b', lambda m: 'Chapitre ' + nombre(int(m.group(1))), t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def passages(texte, limite=420):
    """Groupes de phrases d'au plus `limite` caracteres, jamais coupes au milieu d'un mot."""
    paras = [p.strip() for p in re.split(r'\n\s*\n|\n', texte) if p.strip()]
    out = []
    for p in paras:
        phrases = re.split(r'(?<=[.!?…»”"])\s+', p)
        cur = ''
        for ph in phrases:
            while len(ph) > limite:                       # phrase tres longue : couper a une virgule ou un espace
                cut = max(ph.rfind(', ', 0, limite), ph.rfind('; ', 0, limite))
                cut = cut + 1 if cut > limite // 3 else ph.rfind(' ', 0, limite)
                if cut <= 0: cut = limite
                if cur: out.append(cur); cur = ''
                out.append(ph[:cut].strip()); ph = ph[cut:].strip()
            if cur and len(cur) + 1 + len(ph) > limite:
                out.append(cur); cur = ph
            else:
                cur = (cur + ' ' + ph).strip()
        if cur: out.append(cur)
    return out

def u16_vers_index(texte, pos):
    return len(texte.encode('utf-16-le')[:2 * pos].decode('utf-16-le', errors='ignore'))

def decouper_long(titre, contenu, maxc=40000):
    """Chapitre trop long (plus de ~45 min) : parties coupees entre deux paragraphes."""
    if len(contenu) <= maxc: return [(titre, contenu)]
    paras = re.split(r'(\n\s*\n|\n)', contenu); parts = []; cur = ''
    for p in paras:
        if len(cur) + len(p) > maxc and cur.strip(): parts.append(cur); cur = ''
        cur += p
    if cur.strip(): parts.append(cur)
    return [('%s (partie %d)' % (titre, k), c) for k, c in enumerate(parts, 1)]

def chapitres(fichier, documents_py):
    sys.path.insert(0, str(Path(documents_py).parent))
    import documents
    r = documents.extract(str(fichier))
    texte = r['text']; table = r.get('table') or []
    if table:
        niveau = min(e[1] for e in table)
        hauts = [e for e in table if e[1] == niveau]
        bornes = [u16_vers_index(texte, e[2]) for e in hauts] + [len(texte)]
        res = [(hauts[i][0], texte[bornes[i]:bornes[i+1]]) for i in range(len(hauts))]
        if bornes[0] > 0 and texte[:bornes[0]].strip(): res.insert(0, ('Debut', texte[:bornes[0]]))
    else:
        res = [(Path(fichier).stem, texte)]
    out = []
    for t, c in res:
        if c.strip(): out += decouper_long(t, c)
    return out

def signature(fichier):
    import hashlib
    return hashlib.sha1(Path(fichier).read_bytes()).hexdigest()[:16]

def dossiers_du_meme_livre(racine, sig):
    """Dossiers de sortie precedents (etat.json) qui portent la signature de ce livre."""
    res = []
    if not racine: return res
    for e in Path(racine).rglob('etat.json'):
        try:
            if json.loads(e.read_text(encoding='utf-8')).get('signature') == sig: res.append(e.parent)
        except Exception: pass
    return res

def nom_fichier(i, titre):
    titre = titre.replace('œ', 'oe').replace('Œ', 'Oe').replace('æ', 'ae').replace('Æ', 'Ae')
    s = unicodedata.normalize('NFKD', titre).encode('ascii', 'ignore').decode()
    s = re.sub(r'\s+', ' ', re.sub(r'[^A-Za-z0-9 _-]+', ' ', s)).strip()[:60] or 'chapitre'
    return '%03d - %s' % (i, s)

def synthese_morceaux(qwen, voix, lignes, device, journal, seed=42):
    cmd = [qwen, '--model', voix['model'], '--codec', voix['codec'], '--lang', 'French',
           '--ref-spk', voix['spk'], '--ref-rvq', voix['rvq'], '--ref-text', voix['ref'],
           '--seed', str(seed), '--codec-chunk-dur', str(voix.get('chunk', 4)), '--max-new', '2048',
           '--stream-by-line', '-o', '-']
    if device: cmd[1:1] = ['--device', device]
    entree = ('\n'.join(lignes) + '\n').encode('utf-8')
    with open(journal, 'ab') as log:
        p = subprocess.run(cmd, input=entree, stdout=subprocess.PIPE, stderr=log)
    if p.returncode != 0: raise RuntimeError('qwen-tts code %d (voir %s)' % (p.returncode, journal))
    morceaux = [m[44 - len(ENTETE):] for m in p.stdout.split(ENTETE) if m]  # retirer le reste de l'en-tete de 44 octets
    if len(morceaux) != len(lignes): raise RuntimeError('%d lignes envoyees, %d sons recus' % (len(lignes), len(morceaux)))
    return morceaux

def synthese(qwen, voix, lignes, device, journal):
    return b''.join(synthese_morceaux(qwen, voix, lignes, device, journal))

def gain(pcm):
    import numpy as np
    a = np.frombuffer(pcm, dtype='<i2').astype('float64') * GAIN
    pic = float(np.max(np.abs(a))) if len(a) else 0
    if pic > 32000: a *= 32000 / pic
    return np.round(a).astype('<i2').tobytes()

def mp3(pcm, cible, titre, livre, num):
    tmp = str(cible) + '.part.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'pipe:0',
                    '-c:a', 'libmp3lame', '-b:a', '64k', '-metadata', 'title=' + titre, '-metadata', 'album=' + livre,
                    '-metadata', 'artist=Hubert (voix de synthese)', '-metadata', 'track=%d' % num, tmp], input=pcm, check=True)
    os.replace(tmp, cible)

def trouver_voix(dossier, modele=''):
    d = Path(dossier)
    cfg = {}
    try: cfg = json.loads((d / 'config.json').read_text(encoding='utf-8'))
    except Exception: pass
    def trouve(cle, motifs):
        if cfg.get(cle) and (d / cfg[cle]).is_file(): return str(d / cfg[cle])
        for m in motifs:
            g = sorted(d.glob(m))
            if g: return str(g[0])
        raise SystemExit('Fichier de voix introuvable : ' + cle)
    return {'model': str(d / modele) if modele else trouve('model', ['Hubert-candidat*.gguf', 'Hubert*.gguf', '*talker*.gguf']),
            'codec': trouve('codec', ['codec*.gguf', '*tokenizer*.gguf']),
            'spk': trouve('spk', ['*.spk']), 'rvq': trouve('rvq', ['*.rvq']), 'ref': trouve('reference', ['reference.txt', '*.txt']),
            'chunk': cfg.get('codec_chunk_seconds', 4)}

def main():
    a = argparse.ArgumentParser()
    a.add_argument('--qwen', required=True); a.add_argument('--dossier-voix', required=True)
    a.add_argument('--livre', required=True); a.add_argument('--sortie', required=True)
    a.add_argument('--documents', required=True); a.add_argument('--reprise', default='')
    a.add_argument('--lexique', default=''); a.add_argument('--heures', type=float, default=10.0)
    a.add_argument('--device', default=''); a.add_argument('--modele', default='')
    a.add_argument('--tranche', default='0/1', help='k/n : ne traiter que les chapitres i avec (i-1) %% n == k (une carte graphique par tranche)')
    a.add_argument('--bloc', type=int, default=40, help='passages par bloc sauvegarde')
    a.add_argument('--premiers', type=int, default=0, help='essai : nombre de passages par chapitre (0 = tout)')
    o = a.parse_args()
    t0 = time.time(); budget = o.heures * 3600
    k, n = (int(x) for x in o.tranche.split('/'))
    voix = trouver_voix(o.dossier_voix, o.modele)
    print('Voix :', json.dumps({kk: Path(v).name if isinstance(v, str) else v for kk, v in voix.items()}), flush=True)
    sortie = Path(o.sortie); sortie.mkdir(parents=True, exist_ok=True)
    parties = sortie / 'parties'; parties.mkdir(exist_ok=True)
    livre = Path(o.livre).stem; sig = signature(o.livre)
    caps = chapitres(o.livre, o.documents)
    lex = lexique(o.lexique)
    anciens = [x for x in dossiers_du_meme_livre(o.reprise, sig) if x.resolve() != sortie.resolve()]
    (sortie / 'etat.json').write_text(json.dumps({'signature': sig, 'livre': Path(o.livre).name, 'chapitres': len(caps)}), encoding='utf-8')
    print('%d chapitres dans « %s » ; tranche %d/%d ; reprise depuis %d dossier(s)' % (len(caps), livre, k, n, len(anciens)), flush=True)
    journal = str(sortie / ('journal-moteur-%d.txt' % k))
    faits = 0; echecs = []; durees_bloc = []; arret = False
    for i, (titre, contenu) in enumerate(caps, 1):
        if (i - 1) % n != k: continue
        cible = sortie / (nom_fichier(i, titre) + '.mp3')
        for anc in anciens:
            if not cible.exists() and (anc / cible.name).is_file(): shutil.copy2(anc / cible.name, cible)
        if cible.exists():
            print('DEJA FAIT', cible.name, flush=True); faits += 1; continue
        try:
            lignes = [a_dire(p, lex) for p in passages(contenu)]
            lignes = [l for l in lignes if re.search(r'\w', l)]
            if o.premiers: lignes = lignes[:o.premiers]
            blocs = [lignes[j:j + o.bloc] for j in range(0, len(lignes), o.bloc)]
            morceaux = []
            for b, lb in enumerate(blocs):
                f = parties / ('%03d-%03d.pcm' % (i, b))
                for anc in anciens:
                    if not f.exists() and (anc / 'parties' / f.name).is_file(): shutil.copy2(anc / 'parties' / f.name, f)
                if not f.exists():
                    reste = budget - (time.time() - t0)
                    prevu = 1.3 * max(durees_bloc) if durees_bloc else 0
                    if reste <= 0 or prevu > reste:
                        arret = True; break
                    debut = time.time()
                    pcm = synthese(o.qwen, voix, lb, o.device, journal)
                    tmp = f.with_suffix('.tmp'); tmp.write_bytes(pcm); os.replace(tmp, f)
                    durees_bloc.append(time.time() - debut)
                    print('  bloc %d/%d du chapitre %d : %.1f min d audio en %.1f min' % (
                        b + 1, len(blocs), i, len(pcm) / 48000 / 60, durees_bloc[-1] / 60), flush=True)
                morceaux.append(f)
            if arret:
                print('ARRET temps alloue presque ecoule (chapitre %d en cours, deja sauvegarde) ; relancez avec la sortie en entree' % i, flush=True)
                break
            pcm = gain(b''.join(m.read_bytes() for m in morceaux))
            mp3(pcm, cible, titre, livre, i)
            for m in morceaux: m.unlink()
            faits += 1
            print('FAIT %s : %.1f min d audio, seance %.1f h' % (cible.name, len(pcm) / 48000 / 60, (time.time() - t0) / 3600), flush=True)
        except Exception as e:
            echecs.append(cible.name); print('ECHEC %s : %s' % (cible.name, e), flush=True)
    mien = [i for i in range(1, len(caps) + 1) if (i - 1) % n == k]
    (sortie / ('bilan-%d.json' % k)).write_text(json.dumps({'chapitres': len(mien), 'faits': faits, 'echecs': echecs}), encoding='utf-8')
    print('BILAN tranche %d : %d chapitres sur %d%s' % (k, faits, len(mien), ('  !!! ECHECS : ' + ', '.join(echecs)) if echecs else ''), flush=True)
    sys.exit(1 if echecs else 0)

if __name__ == '__main__':
    main()
