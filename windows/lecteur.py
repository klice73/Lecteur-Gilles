"""Lecteur local Piper. Interface et moteur isolés pour permettre l'arrêt."""
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
    parts = (p for p in text_parts(data['text']) if p.strip())
    if streaming:
        folder = Path(output)
        folder.mkdir(parents=True, exist_ok=True)
        count = 0
        for count, part in enumerate(parts, 1):
            # At most three ready audio passages, even while the listener pauses.
            while sum(1 for _ in folder.glob('part-*.wav')) >= 3:
                time.sleep(0.1)
            pending = folder / 'preparation.tmp'
            with wave.open(str(pending), 'wb') as audio:
                voice.synthesize_wav(part, audio, syn_config=config)
            pending.replace(folder / ('part-%06d.wav' % count))
        (folder / 'done').write_text(str(count), encoding='ascii')
    else:
        # Stream PCM into one file; never accumulate the book's audio in memory.
        with wave.open(str(output), 'wb') as audio:
            initialized = False
            for part in parts:
                for chunk in voice.synthesize(part, syn_config=config):
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
    app.title('Piper — Lecture naturelle')
    app.geometry('920x680')
    app.minsize(700, 480)
    app.configure(bg='#eef3f7')
    style = ttk.Style(app)
    style.theme_use('clam')
    style.configure('TButton', font=('Segoe UI', 11), padding=9)
    style.configure('TLabel', font=('Segoe UI', 11), background='#eef3f7')
    box = ttk.Frame(app, padding=20)
    box.pack(fill='both', expand=True)
    ttk.Label(box, text='Votre texte, à voix haute', font=('Segoe UI', 23, 'bold')).pack(anchor='w')
    ttk.Label(box, text='Voix française Siwis • lecture locale • sans quota').pack(anchor='w', pady=(4, 16))
    bar = ttk.Frame(box)
    bar.pack(fill='x', pady=(0, 10))
    editor = ScrolledText(box, wrap='word', undo=True, font=('Segoe UI', 14),
                          padx=16, pady=16, relief='flat', height=16)
    editor.pack(fill='both', expand=True)
    editor.insert('1.0', 'Bonjour ! Bienvenue dans votre lecteur Piper.\n\nCollez votre texte ici, puis cliquez sur Lire. La voix est produite sur votre ordinateur, sans envoyer votre texte sur Internet.')
    status = tk.StringVar(value='Prêt. Collez un texte ou ouvrez un fichier .txt.')
    speed = tk.StringVar(value='1.0')
    controls = ttk.Frame(box)
    controls.pack(fill='x', pady=14)
    ttk.Label(box, textvariable=status, wraplength=820).pack(anchor='w')
    ttk.Label(box, text='Les PDF et documents Word : copiez leur texte dans cette fenêtre.',
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
        status.set('Arrêté. Vous pouvez modifier le texte.')

    def paste():
        try:
            content = app.clipboard_get()
        except tk.TclError:
            messagebox.showinfo('Presse-papiers', 'Aucun texte à coller.')
            return
        stop()
        editor.delete('1.0', 'end')
        editor.insert('1.0', content)
        status.set('Texte collé. Cliquez sur Lire.')

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
            messagebox.showinfo('Texte vide', 'Collez ou saisissez un texte à lire.')
            return
        if not VOICE.is_file():
            messagebox.showerror('Voix manquante', 'Le modèle français est absent du dossier voix.')
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
            messagebox.showerror('Démarrage impossible', str(error))
            return
        editor.configure(state='disabled')
        status.set('Préparation de la voix… Le texte reste visible. Arrêter permet d’annuler.')

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
                status.set('La génération a échoué.')
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
                        status.set('Audio enregistré : ' + str(target))
                    else:
                        with wave.open(str(audio), 'rb') as wav:
                            duration = wav.getnframes() / wav.getframerate()
                        winsound.PlaySound(str(audio), winsound.SND_FILENAME | winsound.SND_ASYNC)
                        state['playing_until'] = time.monotonic() + duration
                        status.set('Lecture en cours — cliquez sur Arrêter pour interrompre.')
                except Exception as error:
                    status.set('Erreur de lecture ou d’enregistrement.')
                    messagebox.showerror('Audio', str(error))
        elif process is not None:
            elapsed = int(time.monotonic() - state['started'])
            status.set('Préparation de la voix : {} s. Un texte long demande plus de temps.'.format(elapsed))
        if state['playing_until'] and time.monotonic() >= state['playing_until']:
            state['playing_until'] = 0
            status.set('Lecture terminée.')
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
    ttk.Button(controls, text='▶ Lire', command=lambda: start('play')).pack(side='left', padx=(0, 8))
    ttk.Button(controls, text='■ Arrêter', command=stop).pack(side='left', padx=(0, 8))
    ttk.Button(controls, text='Enregistrer en WAV', command=lambda: start('save')).pack(side='left')
    app.protocol('WM_DELETE_WINDOW', close)
    app.after(200, poll)
    app.mainloop()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] in ('--synthesize', '--stream'):
        synthesize(sys.argv[2], sys.argv[3], streaming=sys.argv[1] == '--stream')
    else:
        main()
