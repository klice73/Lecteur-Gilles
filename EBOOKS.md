# Livres électroniques — version 1.7

La version 1.7 reprend la version 1.6 (test-20, bae26b3), avec ses corrections de voix, surlignage, reprise de lecture et repères.

| Format | Android | Windows |
|---|---|---|
| EPUB 2/3, KEPUB textuel sans protection | Direct | Direct |
| FictionBook FB2, FB2.ZIP (un livre) | Direct | Direct |
| PDF avec texte, DOCX, ODT, TXT, Markdown, HTML | Direct | Direct |
| MOBI, AZW/AZW3/AZW4, PRC, PDB, LIT, LRF, RTF, DJVU, HTMLZ, TXTZ, TCR, SNB, RB, PML, CHM | Convertir en EPUB sur un ordinateur puis transférer le résultat | Conversion automatique si calibre est installé et sait lire ce fichier |
| KFX | Export EPUB/PDF depuis la librairie, si disponible | Idem |
| ACSM | Bon de téléchargement, pas un livre | Idem |
| Livres protégés | Édition sans protection nécessaire | Idem |
| Scans et BD composés d'images | OCR préalable nécessaire | OCR préalable nécessaire |

Ouvrez le fichier avec **Ouvrir un document**, puis utilisez la lecture habituelle. Les images, vidéos et la mise en page ne sont pas restituées : le lecteur extrait le texte pour la voix. Les EPUB suivent l'ordre de lecture du livre ; les sections marquées non linéaires ne sont pas lues. Sur Android, les repères EPUB sont déduits des titres du texte ; la table EPUB complète et les liens de notes ne sont pas encore importés. FictionBook conserve les titres et leurs niveaux.

Sur Windows, installez calibre séparément depuis https://calibre-ebook.com/download_windows si vous avez besoin des formats supplémentaires. Le lecteur cherche son convertisseur dans les installations habituelles, le PATH ou `calibre/Calibre/ebook-convert.exe` sous le dossier du lecteur. La conversion se fait dans un dossier temporaire local, effacé ensuite, et conserve le livre original. Pour transférer le résultat sur Android, utilisez calibre pour enregistrer un EPUB. Les capacités de conversion dépendent du fichier et de la version de calibre ; ce n'est pas une garantie pour tous les livres d'une extension donnée.

Limites Android : EPUB compressé 100 Mo ; autres fichiers 30 Mo ; EPUB décompressé 250 Mo, chapitre 10 Mo ; FB2.ZIP décompressé 50 Mo. Les livres endommagés ou dépassant ces limites sont refusés avec un message.

Documentation du convertisseur : https://manual.calibre-ebook.com/generated/en/ebook-convert.html
