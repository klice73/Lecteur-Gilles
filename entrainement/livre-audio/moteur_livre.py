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
    else:
        res = [(Path(fichier).stem, texte)]
    return [(t, c) for t, c in res if c.strip()]

def nom_fichier(i, titre):
    titre = titre.replace('œ', 'oe').replace('Œ', 'Oe').replace('æ', 'ae').replace('Æ', 'Ae')
    s = unicodedata.normalize('NFKD', titre).encode('ascii', 'ignore').decode()
    s = re.sub(r'\s+', ' ', re.sub(r'[^A-Za-z0-9 _-]+', ' ', s)).strip()[:60] or 'chapitre'
    return '%03d - %s' % (i, s)

def synthese(qwen, voix, lignes, device, journal):
    cmd = [qwen, '--model', voix['model'], '--codec', voix['codec'], '--lang', 'French',
           '--ref-spk', voix['spk'], '--ref-rvq', voix['rvq'], '--ref-text', voix['ref'],
           '--seed', '42', '--codec-chunk-dur', str(voix.get('chunk', 4)), '--max-new', '2048',
           '--stream-by-line', '-o', '-']
    if device: cmd[1:1] = ['--device', device]
    entree = ('\n'.join(lignes) + '\n').encode('utf-8')
    with open(journal, 'ab') as log:
        p = subprocess.run(cmd, input=entree, stdout=subprocess.PIPE, stderr=log)
    if p.returncode != 0: raise RuntimeError('qwen-tts code %d (voir %s)' % (p.returncode, journal))
    morceaux = [m for m in p.stdout.split(ENTETE) if m]
    pcm = b''.join(m[44 - len(ENTETE):] for m in morceaux)  # retirer le reste de l'en-tete de 44 octets
    if len(morceaux) != len(lignes): raise RuntimeError('%d lignes envoyees, %d sons recus' % (len(lignes), len(morceaux)))
    return pcm

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

def main():
    a = argparse.ArgumentParser()
    a.add_argument('--qwen', required=True); a.add_argument('--dossier-voix', required=True)
    a.add_argument('--livre', required=True); a.add_argument('--sortie', required=True)
    a.add_argument('--documents', required=True); a.add_argument('--reprise', default='')
    a.add_argument('--lexique', default=''); a.add_argument('--heures', type=float, default=10.0)
    a.add_argument('--device', default=''); a.add_argument('--modele', default='')
    a.add_argument('--premiers', type=int, default=0, help='essai : nombre de passages par chapitre (0 = tout)')
    o = a.parse_args()
    t0 = time.time(); budget = o.heures * 3600
    d = Path(o.dossier_voix)
    cfg = {}
    try: cfg = json.loads((d / 'config.json').read_text(encoding='utf-8'))
    except Exception: pass
    def trouve(cle, motifs):
        if cfg.get(cle) and (d / cfg[cle]).is_file(): return str(d / cfg[cle])
        for m in motifs:
            g = sorted(d.glob(m))
            if g: return str(g[0])
        raise SystemExit('Fichier de voix introuvable : ' + cle)
    voix = {'model': str(d / o.modele) if o.modele else trouve('model', ['Hubert-candidat*.gguf', 'Hubert*.gguf', '*talker*.gguf']),
            'codec': trouve('codec', ['codec*.gguf', '*tokenizer*.gguf']),
            'spk': trouve('spk', ['*.spk']), 'rvq': trouve('rvq', ['*.rvq']), 'ref': trouve('reference', ['reference.txt', '*.txt']),
            'chunk': cfg.get('codec_chunk_seconds', 4)}
    print('Voix :', json.dumps({k: Path(v).name if isinstance(v, str) else v for k, v in voix.items()}), flush=True)
    sortie = Path(o.sortie); sortie.mkdir(parents=True, exist_ok=True)
    livre = Path(o.livre).stem
    caps = chapitres(o.livre, o.documents)
    lex = lexique(o.lexique)
    print('%d chapitres dans « %s »' % (len(caps), livre), flush=True)
    faits = 0; secondes_audio = 0.0
    for i, (titre, contenu) in enumerate(caps, 1):
        cible = sortie / (nom_fichier(i, titre) + '.mp3')
        if not cible.exists() and o.reprise:
            anc = list(Path(o.reprise).rglob(cible.name))
            if anc: shutil.copy2(anc[0], cible)
        if cible.exists():
            print('DEJA FAIT', cible.name, flush=True); faits += 1; continue
        if time.time() - t0 > budget:
            print('ARRET temps alloue ecoule ; relancez avec la sortie en entree pour continuer', flush=True); break
        lignes = [a_dire(p, lex) for p in passages(contenu)]
        lignes = [l for l in lignes if re.search(r'\w', l)]
        if o.premiers: lignes = lignes[:o.premiers]
        debut = time.time()
        pcm = gain(synthese(o.qwen, voix, lignes, o.device, str(sortie / 'journal-moteur.txt')))
        mp3(pcm, cible, titre, livre, i)
        duree = len(pcm) / 2 / 24000; secondes_audio += duree; faits += 1
        print('FAIT %s : %d passages, %.1f min d audio en %.1f min (x%.2f temps reel), seance %.1f h' % (
            cible.name, len(lignes), duree / 60, (time.time() - debut) / 60, duree / max(1, time.time() - debut), (time.time() - t0) / 3600), flush=True)
    (sortie / 'etat.json').write_text(json.dumps({'chapitres': len(caps), 'faits': faits}), encoding='utf-8')
    print('BILAN : %d chapitres sur %d' % (faits, len(caps)), flush=True)

if __name__ == '__main__':
    main()
