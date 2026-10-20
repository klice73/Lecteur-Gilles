"""Lecteur local Piper. Interface et moteur isolÃ©s pour permettre l'arrÃªt."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import wave
import time
import re


def text_parts(text, limit=800):
    """Keep every character, but never send a whole book to the phonemizer."""
    offset = 0
    while offset < len(text):
        end = min(len(text), offset + limit)
        if end < len(text):
            piece = text[offset:end]
            boundaries = list(re.finditer(r'[.!?;]\s+|\n+', piece))
            cut = boundaries[-1].end() if boundaries else piece.rfind(' ') + 1
            if cut > limit // 3:
                end = offset + cut
        yield text[offset:end]
        offset = end

def indexed_parts(text):
    """Offsets use UTF-16 code units, matching Windows controls (including emoji)."""
    offset = 0
    for part in text_parts(text):
        size = len(part.encode('utf-16-le', errors='surrogatepass')) // 2
        if part.strip():
            yield offset, offset + size, part
        offset += size


# --- Minutage mot a mot (version 1.5) ---------------------------------------
# Chaque phrase est synthetisee seule : son debut et sa fin dans l'audio sont
# donc exacts. Dans la phrase, la zone parlee (sans les silences de bord) est
# repartie entre les mots selon leur longueur ; les virgules comptent comme
# une petite pause. Meme regle dans l'application Android (Minutage.kt).
_PHRASE = re.compile(r'[^\S\n]*(?:[.!?…]+["»”)\]]*\s+|\n[^\S\n]*\n\s*)')
_L = r"(?:[^\W\d_]|[\u0300-\u036f])"  # lettres, accents decomposes compris (copie de PDF)
_MOT = re.compile(_L + r"+(?:['\u2019-]" + _L + r"+)*|\d+(?:[.,\u00a0\u202f ]\d+)*", re.UNICODE)


def u16(texte):
    return len(texte.encode('utf-16-le', errors='surrogatepass')) // 2


def phrases(texte):
    """(debut, fin) en caracteres Python des phrases contenant au moins un mot."""
    res, debut = [], 0
    for m in _PHRASE.finditer(texte):
        if m.end() > debut:
            res.append((debut, m.end()))
            debut = m.end()
    if debut < len(texte):
        res.append((debut, len(texte)))
    return [(a, b) for a, b in res if _MOT.search(texte, a, b)]


_VOY = 'aeiouy\u00e0\u00e2\u00e4\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f6\u00f9\u00fb\u00fc\u0153\u00e6'
_GROUPES = ('eau', 'ou', 'au', 'ai', 'ei', 'oi', 'ch', 'ph', 'gn', 'qu', 'll', 'ss', 'tt', 'nn', 'mm', 'rr', 'pp')


def sons(mot):
    """Nombre approximatif de sons d'un mot francais ecrit (lettres muettes et
    groupes comme « eau », « ch », voyelles nasales). Sert a estimer la duree."""
    import unicodedata
    w = unicodedata.normalize('NFC', mot).lower()
    if re.fullmatch(r'\d[\d .,\u00a0\u202f]*', w):
        return 3.0 * len(re.findall(r'\d', w))
    w = re.sub(r"^[^\W\d_]['\u2019]", '', w)
    w = re.sub(r"['\u2019-]", '', w)
    if len(w) > 3:
        w = re.sub(r'(ent|es|s|x)$', '', w)
    if len(w) > 2:
        w = re.sub(r'e$', '', w)
    w = re.sub('(?<=[' + _VOY + '])[tdzp]$', '', w)
    for g in _GROUPES:
        w = w.replace(g, '#')
    w = re.sub('(?<=[' + _VOY + '])[nm](?=[^' + _VOY + ']|$)', '', w)
    w = w.replace('h', '')
    return float(max(1, len(w)))


def poids_mots(phrase):
    """Liste (debut, fin, pause_avant, poids_mot) ; pause_avant = pause de ponctuation qui precede."""
    mots, precedent = [], 0
    for m in _MOT.finditer(phrase):
        entre = phrase[precedent:m.start()]
        pause = 6.0 if re.search(r'[,;:]', entre) else (2.0 if re.search('[\u2013\u2014()\u00ab\u00bb"]', entre) else 0.0)
        mots.append((m.start(), m.end(), pause if mots else 0.0, 1.0 + sons(m.group())))
        precedent = m.end()
    return mots


def zone_parlee(audio, sr):
    """(premier, dernier) echantillon parle, d'apres l'energie par tranches de 10 ms."""
    import numpy as np
    trame = max(1, sr // 100)
    k = len(audio) // trame
    if k == 0:
        return 0, len(audio)
    x = audio[:k * trame].astype(np.float64).reshape(k, trame)
    rms = np.sqrt((x ** 2).mean(1))
    seuil = max(rms.max() * 10 ** (-35 / 20), 1e-9)
    actif = np.flatnonzero(rms >= seuil)
    if len(actif) == 0:
        return 0, len(audio)
    return int(actif[0]) * trame, min(len(audio), (int(actif[-1]) + 1) * trame)


def _energie(audio, sr):
    import numpy as np
    trame = max(1, sr // 100)
    k = len(audio) // trame
    x = audio[:k * trame].astype(np.float64).reshape(k, trame)
    return np.sqrt((x ** 2).mean(1)), trame


def minuter(phrase, audio, sr):
    """Pour une phrase et son audio : [(t0, t1, debut, fin)] par mot, temps en echantillons.
    Estimation (quand la voix ne donne pas ses durees) : la zone parlee est repartie
    selon le nombre de sons des mots ; chaque pause de ponctuation est ancree sur le
    vrai silence le plus proche dans l'audio (au moins 80 ms sous -30 dB)."""
    mots = poids_mots(phrase)
    if not mots:
        return []
    a, b = zone_parlee(audio, sr)
    rms, trame = _energie(audio, sr)
    silences = []
    if len(rms):
        muet = rms < rms.max() * 10 ** (-30 / 20)
        i, fin = a // trame, b // trame
        while i < fin:
            if muet[i]:
                j = i
                while j < fin and muet[j]:
                    j += 1
                if j - i >= 8 and j < fin:
                    silences.append(((i + j) / 2.0 * trame, j * trame))   # (centre, fin) en echantillons
                i = j
            else:
                i += 1
    debut_poids, cumul = [], 0.0
    for _, _, p, w in mots:
        cumul += p
        debut_poids.append(cumul)
        cumul += w
    total = cumul
    est = [a + (b - a) * s / total for s in debut_poids]
    ancres = [(0, float(a), 0.0)]
    for k in range(1, len(mots)):
        if mots[k][2] > 0 and silences:
            j = min(range(len(silences)), key=lambda q: abs(silences[q][0] - est[k]))
            if abs(silences[j][0] - est[k]) < 0.25 * (b - a):
                ancres.append((k, float(silences[j][1]), debut_poids[k]))
                centre = silences[j][0]
                silences = [s for s in silences if s[0] > centre]
    ancres.append((len(mots), float(b), total))
    for (k0, t0, s0), (k1, t1, s1) in zip(ancres, ancres[1:]):
        fin_poids = debut_poids[k1 - 1] + mots[k1 - 1][3]
        if k1 <= k0 or t1 <= t0 or fin_poids <= s0:
            continue
        for k in range(k0, k1):
            est[k] = t0 + (t1 - t0) * (debut_poids[k] - s0) / (fin_poids - s0)
    for k in range(1, len(est)):
        est[k] = max(est[k], est[k - 1])
    res = []
    for k, (d, f, _, _) in enumerate(mots):
        t0 = 0 if k == 0 else int(est[k])
        t1 = len(audio) if k == len(mots) - 1 else int(est[k + 1])
        res.append((t0, t1, d, f))
    return res


def debuts_alignes(voice, bouts):
    """Debut (en echantillons) de chaque mot prononce, d'apres les durees exactes
    fournies par la voix (seconde sortie du modele). None si indisponible."""
    espace = voice.config.phoneme_id_map.get(' ', [None])[0]
    muets = {i for s in ('_', '^', '$') for i in voice.config.phoneme_id_map.get(s, [])}
    debuts, n = [], 0
    for x in bouts:
        ech = x.phoneme_id_samples
        if ech is None or x.phoneme_ids is None or len(ech) != len(x.phoneme_ids):
            return None
        t, nouveau = 0, True
        for i, d in zip(x.phoneme_ids, ech):
            if i == espace:
                nouveau = True
            elif nouveau and i not in muets:
                debuts.append(n + t)
                nouveau = False
            t += int(d)
        n += len(x.audio_int16_bytes) // 2
    return debuts


def _premier_son(phonemes):
    for c in phonemes:
        if c.isalpha() and c not in 'ˈˌː':  # accents toniques et allongement : pas des sons
            return c
    return ''


def correspondance_sure(voice, phrase, mots, bouts):
    """Les mots du texte et les mots phonetiques vont-ils bien un a un ?
    Controle : chaque mot lu seul doit commencer par le meme son que le mot
    phonetique associe (sinon espeak a fusionne ou ajoute des mots, ex. « 50 % »)."""
    phon = []
    for x in bouts:
        phon += [w for w in ''.join(x.phonemes or []).split(' ') if any(c.isalpha() for c in w)]
    if len(phon) != len(mots):
        return False
    for (d, f, _, _), w in zip(mots, phon):
        seul = [m for s in voice.phonemize(phrase[d:f]) for m in ''.join(s).split(' ') if any(c.isalpha() for c in m)]
        if not seul or _premier_son(seul[0]) != _premier_son(w):
            return False
    return True


# --- Lexique de prononciation (version 1.8) ----------------------------------
# Fichier texte modifiable, une ligne par mot :  mot = comment le dire
# (ex. « Bateson = Bétsonne »). Lignes vides et lignes commencant par # ignorees.
# Mot entier, sans tenir compte des majuscules. Meme regle dans Prononciations.kt.
_LETTRES = '0-9A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u024f'


def lire_lexique(texte):
    """[(mot, prononciation)] depuis le contenu du fichier lexique."""
    res = []
    for ligne in texte.replace('\r', '').split('\n'):
        ligne = ligne.strip().lstrip('\ufeff').strip()
        if not ligne or ligne.startswith('#') or '=' not in ligne:
            continue
        mot, dire = (x.strip() for x in ligne.split('=', 1))
        if mot and dire:
            res.append((mot, dire))
    return res


def motif_lexique(lexique):
    if not lexique:
        return None, {}
    table = {}
    for mot, dire in lexique:
        table.setdefault(mot.replace('\u2019', "'").lower(), dire)   # premiere ligne gagnante ; ’ = '
    alternatives = '|'.join(re.escape(m).replace("'", "['\u2019]") for m in sorted(table, key=len, reverse=True))
    motif = re.compile('(?<![' + _LETTRES + '])(?:' + alternatives + ')(?![' + _LETTRES + '])', re.I)
    return motif, table


def appliquer_lexique(texte, motif, table):
    if motif is None:
        return texte
    return motif.sub(lambda m: table.get(m.group(0).replace('\u2019', "'").lower(), m.group(0)), texte)


def charger_lexique():
    f = ROOT / 'prononciations.txt'
    try:
        brut = f.read_bytes()
    except OSError:
        return None, {}
    try:
        contenu = brut.decode('utf-8-sig')
    except UnicodeDecodeError:
        contenu = brut.decode('cp1252', errors='replace')   # enregistre en « ANSI » par le Bloc-notes
    try:
        return motif_lexique(lire_lexique(contenu))
    except Exception:   # un lexique abime ne doit jamais empecher la lecture
        return None, {}
# ---------------------------------------------------------------------------


def synthese_minutee(voice, passage, config, lexique=(None, {})):
    """Audio int16 du passage + minutage. Positions en UTF-16 relatives au passage.
    Mots alignes exactement quand la voix fournit ses durees, sinon estimes."""
    import numpy as np
    morceaux, mots, phr, n, sr = [], [], [], 0, None
    exacts = estimes = 0
    for a, b in phrases(passage):
        phrase = passage[a:b]
        dite = appliquer_lexique(phrase, *lexique)   # ce que Gilles prononce ; le surlignage suit la phrase affichee
        bouts = list(voice.synthesize(dite, syn_config=config, include_alignments=True))
        if not bouts:
            continue
        sr = bouts[0].sample_rate
        audio = np.concatenate([np.frombuffer(x.audio_int16_bytes, dtype=np.int16) for x in bouts])
        base = u16(passage[:a])
        minutage = minuter(phrase, audio, sr)
        debuts = debuts_alignes(voice, bouts)
        if (dite == phrase and debuts is not None and len(debuts) == len(minutage) and debuts
                and correspondance_sure(voice, phrase, poids_mots(phrase), bouts)):
            fins = debuts[1:] + [len(audio)]
            minutage = [(t0 if k else 0, t1, d, f) for k, (t0, t1, (_, _, d, f)) in enumerate(zip(debuts, fins, minutage))]
            exacts += 1
        else:
            estimes += 1
        for t0, t1, d, f in minutage:
            mots.append([n + t0, n + t1, base + u16(phrase[:d]), base + u16(phrase[:f])])
        fin_phrase = a + len(phrase.rstrip())
        phr.append([n, n + len(audio), base, u16(passage[:fin_phrase])])
        morceaux.append(audio)
        n += len(audio)
    audio = np.concatenate(morceaux) if morceaux else np.zeros(0, dtype=np.int16)
    sr = sr or voice.config.sample_rate
    ms = lambda v: int(round(v * 1000.0 / sr))
    return audio, sr, {'mots': [[ms(t0), ms(t1), d, f] for t0, t1, d, f in mots],
                       'phrases': [[ms(t0), ms(t1), d, f] for t0, t1, d, f in phr],
                       'exactes': exacts, 'estimees': estimes}
# ---------------------------------------------------------------------------


ROOT = Path(__file__).resolve().parent
VOICE = ROOT / 'voix' / 'fr_FR-siwis-medium.onnx'
os.environ['TCL_LIBRARY'] = str(ROOT / 'tcl' / 'tcl8.6')
os.environ['TK_LIBRARY'] = str(ROOT / 'tcl' / 'tk8.6')


def synthesize(request, output, streaming=False):
    from piper import PiperVoice, SynthesisConfig
    data = json.loads(Path(request).read_text(encoding='utf-8'))
    selected = data.get('voice', 'fr_FR-siwis-medium')
    if selected not in ('fr_FR-siwis-medium', 'fr_FR-gilles-low'):
        raise ValueError('Voix non prise en charge')
    voice = PiperVoice.load(str(ROOT / 'voix' / (selected + '.onnx')))
    config = SynthesisConfig(length_scale=1.0 / data['speed'])
    lexique = charger_lexique()
    parts = (p for p in text_parts(data['text']) if p.strip())
    if streaming:
        folder = Path(output)
        folder.mkdir(parents=True, exist_ok=True)
        count = 0
        for count, (start, end, part) in enumerate(indexed_parts(data['text']), 1):
            # At most three ready audio passages, even while the listener pauses.
            while sum(1 for _ in folder.glob('part-*.wav')) >= 3:
                time.sleep(0.1)
            pending = folder / 'preparation.tmp'
            pcm, sr, minutage = synthese_minutee(voice, part, config, lexique)
            with wave.open(str(pending), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(sr)
                audio.writeframes(pcm.tobytes())
            minutage.update({'start': start, 'end': end})
            (folder / ('part-%06d.json' % count)).write_text(json.dumps(minutage), encoding='utf-8')
            pending.replace(folder / ('part-%06d.wav' % count))
        (folder / 'done').write_text(str(count), encoding='ascii')
    else:
        # Stream PCM into one file; never accumulate the book's audio in memory.
        with wave.open(str(output), 'wb') as audio:
            initialized = False
            for part in parts:
                for chunk in voice.synthesize(appliquer_lexique(part, *lexique), syn_config=config):
                    if not initialized:
                        audio.setframerate(chunk.sample_rate)
                        audio.setsampwidth(chunk.sample_width)
                        audio.setnchannels(chunk.sample_channels)
                        initialized = True
                    pcm = chunk.audio_int16_bytes
                    if audio.getnframes() * audio.getnchannels() * audio.getsampwidth() + len(pcm) > 4_000_000_000:
                        raise ValueError('Limite WAV atteinte. Exportez le livre en plusieurs parties.')
                    audio.writeframes(pcm)


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from tkinter.scrolledtext import ScrolledText
    import winsound
    import shutil
    import time

    app = tk.Tk()
    app.title('Piper â€” Lecture naturelle')
    app.geometry('920x680')
    app.minsize(700, 480)
    app.configure(bg='#eef3f7')
    style = ttk.Style(app)
    style.theme_use('clam')
    style.configure('TButton', font=('Segoe UI', 11), padding=9)
    style.configure('TLabel', font=('Segoe UI', 11), background='#eef3f7')
    box = ttk.Frame(app, padding=20)
    box.pack(fill='both', expand=True)
    ttk.Label(box, text='Votre texte, Ã  voix haute', font=('Segoe UI', 23, 'bold')).pack(anchor='w')
    ttk.Label(box, text='Voix franÃ§aise Siwis â€¢ lecture locale â€¢ sans quota').pack(anchor='w', pady=(4, 16))
    bar = ttk.Frame(box)
    bar.pack(fill='x', pady=(0, 10))
    editor = ScrolledText(box, wrap='word', undo=True, font=('Segoe UI', 14),
                          padx=16, pady=16, relief='flat', height=16)
    editor.pack(fill='both', expand=True)
    editor.insert('1.0', 'Bonjour ! Bienvenue dans votre lecteur Piper.\n\nCollez votre texte ici, puis cliquez sur Lire. La voix est produite sur votre ordinateur, sans envoyer votre texte sur Internet.')
    status = tk.StringVar(value='PrÃªt. Collez un texte ou ouvrez un fichier .txt.')
    speed = tk.StringVar(value='1.0')
    controls = ttk.Frame(box)
    controls.pack(fill='x', pady=14)
    ttk.Label(box, textvariable=status, wraplength=820).pack(anchor='w')
    ttk.Label(box, text='Les PDF et documents Word : copiez leur texte dans cette fenÃªtre.',
              font=('Segoe UI', 9)).pack(anchor='w', pady=(9, 0))
    temp = tempfile.TemporaryDirectory(prefix='lecteur-piper-')
    scratch = Path(temp.name)
    state = {'process': None, 'log': None, 'playing_until': 0, 'action': None,
             'destination': None, 'started': 0}

    def stop():
        process = state['process']
        if process is not None:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
            state['process'] = None
        if state['log']:
            state['log'].close()
            state['log'] = None
        winsound.PlaySound(None, 0)
        state['playing_until'] = 0
        editor.configure(state='normal')
        status.set('ArrÃªtÃ©. Vous pouvez modifier le texte.')

    def paste():
        try:
            content = app.clipboard_get()
        except tk.TclError:
            messagebox.showinfo('Presse-papiers', 'Aucun texte Ã  coller.')
            return
        stop()
        editor.delete('1.0', 'end')
        editor.insert('1.0', content)
        status.set('Texte collÃ©. Cliquez sur Lire.')

    def open_text():
        filename = filedialog.askopenfilename(filetypes=[('Texte', '*.txt'), ('Tous les fichiers', '*.*')])
        if not filename:
            return
        try:
            raw = Path(filename).read_bytes()
            try:
                content = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                content = raw.decode('cp1252')
        except Exception as error:
            messagebox.showerror('Lecture impossible', str(error))
            return
        stop()
        editor.delete('1.0', 'end')
        editor.insert('1.0', content)
        status.set('Ouvert : ' + Path(filename).name)

    def start(action):
        content = editor.get('1.0', 'end-1c').strip()
        if not content:
            messagebox.showinfo('Texte vide', 'Collez ou saisissez un texte Ã  lire.')
            return
        if not VOICE.is_file():
            messagebox.showerror('Voix manquante', 'Le modÃ¨le franÃ§ais est absent du dossier voix.')
            return
        destination = None
        if action == 'save':
            destination = filedialog.asksaveasfilename(defaultextension='.wav',
                initialfile='lecture.wav', filetypes=[('Audio WAV', '*.wav')])
            if not destination:
                return
        stop()
        request = scratch / 'request.json'
        request.write_text(json.dumps({'text': content, 'speed': float(speed.get())}), encoding='utf-8')
        state['action'] = action
        state['destination'] = destination
        state['started'] = time.monotonic()
        state['log'] = open(scratch / 'error.log', 'w', encoding='utf-8')
        try:
            state['process'] = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                '--synthesize', str(request), str(scratch / 'lecture.wav')],
                stdout=state['log'], stderr=state['log'], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as error:
            stop()
            messagebox.showerror('DÃ©marrage impossible', str(error))
            return
        editor.configure(state='disabled')
        status.set('PrÃ©paration de la voixâ€¦ Le texte reste visible. ArrÃªter permet dâ€™annuler.')

    def poll():
        process = state['process']
        if process is not None and process.poll() is not None:
            code = process.returncode
            state['process'] = None
            state['log'].close()
            state['log'] = None
            editor.configure(state='normal')
            if code:
                details = (scratch / 'error.log').read_text(encoding='utf-8', errors='replace')
                status.set('La gÃ©nÃ©ration a Ã©chouÃ©.')
                messagebox.showerror('Erreur Piper', details[-2500:])
            else:
                try:
                    audio = scratch / 'lecture.wav'
                    if state['action'] == 'save':
                        target = Path(state['destination'])
                        fd, staging = tempfile.mkstemp(dir=target.parent, suffix='.wav')
                        os.close(fd)
                        try:
                            shutil.copyfile(audio, staging)
                            os.replace(staging, target)
                        finally:
                            Path(staging).unlink(missing_ok=True)
                        status.set('Audio enregistrÃ© : ' + str(target))
                    else:
                        with wave.open(str(audio), 'rb') as wav:
                            duration = wav.getnframes() / wav.getframerate()
                        winsound.PlaySound(str(audio), winsound.SND_FILENAME | winsound.SND_ASYNC)
                        state['playing_until'] = time.monotonic() + duration
                        status.set('Lecture en cours â€” cliquez sur ArrÃªter pour interrompre.')
                except Exception as error:
                    status.set('Erreur de lecture ou dâ€™enregistrement.')
                    messagebox.showerror('Audio', str(error))
        elif process is not None:
            elapsed = int(time.monotonic() - state['started'])
            status.set('PrÃ©paration de la voix : {} s. Un texte long demande plus de temps.'.format(elapsed))
        if state['playing_until'] and time.monotonic() >= state['playing_until']:
            state['playing_until'] = 0
            status.set('Lecture terminÃ©e.')
        app.after(200, poll)

    def close():
        stop()
        temp.cleanup()
        app.destroy()

    ttk.Button(bar, text='Coller le texte', command=paste).pack(side='left', padx=(0, 8))
    ttk.Button(bar, text='Ouvrir un .txt', command=open_text).pack(side='left')
    ttk.Label(bar, text='Vitesse :').pack(side='left', padx=(20, 6))
    ttk.Combobox(bar, textvariable=speed, values=['0.75', '0.9', '1.0', '1.1', '1.25', '1.5'],
                 width=6, state='readonly').pack(side='left')
    ttk.Button(controls, text='â–¶ Lire', command=lambda: start('play')).pack(side='left', padx=(0, 8))
    ttk.Button(controls, text='â–  ArrÃªter', command=stop).pack(side='left', padx=(0, 8))
    ttk.Button(controls, text='Enregistrer en WAV', command=lambda: start('save')).pack(side='left')
    app.protocol('WM_DELETE_WINDOW', close)
    app.after(200, poll)
    app.mainloop()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] in ('--synthesize', '--stream'):
        synthesize(sys.argv[2], sys.argv[3], streaming=sys.argv[1] == '--stream')
    else:
        main()
