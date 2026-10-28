import os, time
import piper.train.__main__ as m
from lightning.pytorch.callbacks import ModelCheckpoint, Callback

POINTS = os.environ['POINTS']
BUDGET = float(os.environ.get('BUDGET_S', '36000'))   # secondes de calcul avant arret propre
T0 = time.time()

class Suivi(Callback):
    """Une ligne lisible toutes les N lots ; arret propre avec sauvegarde quand le temps alloue est ecoule."""
    def on_train_start(self, trainer, pl_module):
        self.t, self.k = time.time(), 0
        print('DEBUT epoque %d, %d lots par epoque, pas %d' % (trainer.current_epoch, trainer.num_training_batches, trainer.global_step), flush=True)
    def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx):
        self.k += 1
        if self.k % int(os.environ.get('SUIVI', '50')) == 0:
            v = (time.time() - self.t) / self.k
            fait = trainer.current_epoch * trainer.num_training_batches + batch_idx + 1
            reste = max(0, trainer.max_epochs * trainer.num_training_batches - fait) * v / 3600
            print('SUIVI epoque %d lot %d/%d pas %d : %.2f s par lot, reste environ %.1f h (temps de seance utilise %.1f h)' % (
                trainer.current_epoch, batch_idx + 1, trainer.num_training_batches, trainer.global_step, v, reste, (time.time() - T0) / 3600), flush=True)
        if time.time() - T0 > BUDGET and not trainer.should_stop:
            chemin = os.path.join(POINTS, 'last.ckpt')
            trainer.save_checkpoint(chemin + '.partiel')
            os.replace(chemin + '.partiel', chemin)
            print('ARRET temps alloue ecoule ; sauvegarde au pas %d : %s' % (trainer.global_step, chemin), flush=True)
            trainer.should_stop = True

m._DEFAULT_CALLBACKS[:] = [ModelCheckpoint(dirpath=POINTS, save_top_k=0, save_last=True,
                                           every_n_train_steps=int(os.environ.get('TOUS_LES', '1000'))),
                           Suivi()]
m.main()
