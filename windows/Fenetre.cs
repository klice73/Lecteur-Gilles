using System;
using System.IO;
using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;
using System.Media;
using System.Web.Script.Serialization;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

class Lecteur : Form {
    RichTextBox texte = new RichTextBox();
    int debutLecture, surligneDebut=-1, surligneLongueur;
    bool changeSurlignage;
    // Version 1.5 : surlignage phrase (clair) + mot (fonce), suivi du temps audio.
    int phraseDebut=-1, phraseLongueur;
    int[][] minuteMots, minutePhrases; int passageDebut, motCourant=-1, phraseCourante=-1;
    static readonly Color CouleurPhrase=Color.FromArgb(255,246,196), CouleurMot=Color.FromArgb(255,213,79);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr fenetre, int message, IntPtr w, IntPtr l);
    // Version 1.5 : texte et position conserves dans le dossier « session » du lecteur.
    // La position ne vaut que pour le texte dont l'empreinte est empreintePosition :
    // recoller ou rouvrir le meme document la retrouve, un autre texte ne la detruit pas.
    int positionLecture=-1; bool texteModifie=true, chargement, positionModifiee;
    string empreinteSauvee, empreintePosition, empreinteTexte, empreinteLecture;
    DateTime derniereSauvegarde=DateTime.MinValue, dernierControle=DateTime.MinValue;
    Button reprendre;
    Label statut = new Label();
    ComboBox vitesse = new ComboBox();
    Process travail;
    ComboBox voix = new ComboBox();
    CheckBox nettoyerPdf = new CheckBox { Text="Ignorer les en-têtes et numéros de page (PDF)", Checked=true, AutoSize=true, Margin=new Padding(14,10,0,0) };
    Button lire, pause, lireCurseur;
    bool audioOuvert, suspendu;
    readonly string alias = "piper" + Guid.NewGuid().ToString("N");
    [DllImport("winmm.dll", CharSet=CharSet.Unicode)] static extern int mciSendString(string command, StringBuilder result, int size, IntPtr callback);
    [DllImport("winmm.dll", CharSet=CharSet.Unicode)] static extern bool mciGetErrorString(int code, StringBuilder message, int size);
    string Audio(string commande) {
        var result=new StringBuilder(512);int code=mciSendString(commande,result,result.Capacity,IntPtr.Zero);
        if(code!=0) {var error=new StringBuilder(512);mciGetErrorString(code,error,error.Capacity);throw new Exception(error.ToString());}
        return result.ToString();
    }
    void FermerAudio() {
        if(audioOuvert) {Audio("close "+alias);audioOuvert=false;}
        suspendu=false;if(lire!=null)lire.Text="▶ Lire tout";if(pause!=null)pause.Enabled=false;
    }
    void LireAudio(string fichier) {
        FermerAudio();Audio("open \""+fichier+"\" type waveaudio alias "+alias);audioOuvert=true;
        Audio("set "+alias+" time format milliseconds");Audio("play "+alias);pause.Enabled=true;
        statut.Text="Lecture en cours. Ⅱ Pause suspend la voix ; ▶ Continuer la reprend.";
    }
    void Continuer() {
        if(suspendu && audioOuvert) {Audio("resume "+alias);suspendu=false;lire.Text="▶ Lire tout";pause.Enabled=true;statut.Text="Lecture reprise.";}
        else if(audioOuvert && Audio("status "+alias+" mode")=="playing")return;
        else if(travail==null)Demarrer(false);
    }
    void Pauser() {
        if(!audioOuvert || suspendu)return;
        Audio("pause "+alias);suspendu=true;lire.Text="▶ Continuer";pause.Enabled=false;statut.Text="En pause. Cliquez sur ▶ Continuer pour reprendre au même endroit.";
        SauverSession(true);
    }
    string destination, erreur = "";
    string racine = AppDomain.CurrentDomain.BaseDirectory;
    string temp = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "temp", "Piper-" + Guid.NewGuid().ToString("N"));
    Timer timer = new Timer();
    DateTime debut;
    bool importation;
    bool lectureProgressive;
    int passage;
    string dossierLecture, audioCourant;
    string documentOuvert;
    const string Formats = "Documents lisibles|*.pdf;*.docx;*.odt;*.epub;*.txt;*.md;*.html;*.htm;*.csv|PDF|*.pdf|Word|*.docx|Livres EPUB|*.epub|OpenDocument|*.odt|Texte|*.txt;*.md;*.csv|Pages HTML|*.html;*.htm";
    public Lecteur() {
        Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        Text = "Piper — Lecture naturelle"; Size = new Size(940,700); MinimumSize = new Size(740,500);
        Font = new Font("Segoe UI", 11); BackColor = Color.FromArgb(240,244,248);
        var grille = new TableLayoutPanel { Dock=DockStyle.Fill, Padding=new Padding(20), RowCount=5, ColumnCount=1 };
        grille.RowStyles.Add(new RowStyle(SizeType.Absolute,70));
        grille.RowStyles.Add(new RowStyle(SizeType.Absolute,95));
        grille.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        grille.RowStyles.Add(new RowStyle(SizeType.Absolute,110));
        grille.RowStyles.Add(new RowStyle(SizeType.Absolute,55));
        Controls.Add(grille);
        grille.Controls.Add(new Label { Text="Votre texte, à voix haute\nVoix françaises • lecture locale • sans quota", Dock=DockStyle.Fill, Font=new Font("Segoe UI",15) },0,0);
        var outils=new FlowLayoutPanel {Dock=DockStyle.Fill}; grille.Controls.Add(outils,0,1);
        Ajouter(outils,"Coller le texte",delegate { Arreter(); if(Clipboard.ContainsText()) texte.Text=Clipboard.GetText(); });
        Ajouter(outils,"Ouvrir un document",delegate { using(var d=new OpenFileDialog {Filter=Formats}) if(d.ShowDialog()==DialogResult.OK) Importer(d.FileName); });
        outils.Controls.Add(new Label { Text="Vitesse", AutoSize=true, Margin=new Padding(16,12,4,0) });
        vitesse.DropDownStyle=ComboBoxStyle.DropDownList; vitesse.Width=75;
        vitesse.Items.AddRange(new object[]{"0.75","0.9","1.0","1.1","1.25","1.5"}); vitesse.SelectedIndex=2; outils.Controls.Add(vitesse);
        outils.SetFlowBreak(vitesse,true);
        outils.Controls.Add(new Label {Text="Voix",AutoSize=true,Margin=new Padding(4,10,10,0)});
        voix.DropDownStyle=ComboBoxStyle.DropDownList;voix.Width=180;voix.Items.AddRange(new object[]{"Gilles", "Siwis"});voix.SelectedIndex=0;outils.Controls.Add(voix);
        outils.Controls.Add(nettoyerPdf);
        texte.Multiline=true; texte.ScrollBars=RichTextBoxScrollBars.Vertical; texte.Dock=DockStyle.Fill; texte.Font=new Font("Segoe UI",14); texte.DetectUrls=false;
        texte.Text="Bonjour ! Bienvenue dans votre lecteur Piper.\r\n\r\nCollez votre texte ici, puis cliquez sur Lire."; grille.Controls.Add(texte,0,2);
        var actions=new FlowLayoutPanel {Dock=DockStyle.Fill, Padding=new Padding(0,10,0,0)}; grille.Controls.Add(actions,0,3);
        lire=Ajouter(actions,"▶ Lire tout",delegate { Continuer(); }); pause=Ajouter(actions,"Ⅱ Pause",delegate { Pauser(); });pause.Enabled=false; Ajouter(actions,"■ Arrêter",delegate { Arreter(); });
        lireCurseur=Ajouter(actions,"▶ Lire à partir du curseur",delegate { LireDepuisCurseur(); });
        reprendre=Ajouter(actions,"⟲ Reprendre où j'étais",delegate { Reprendre(); });reprendre.Enabled=false;
        actions.SetFlowBreak(reprendre,true);
        Ajouter(actions,"Enregistrer en WAV",delegate { Demarrer(true); });
        Ajouter(actions,"À propos et licences",delegate { AfficherLicences(); });
        var aide=new ToolTip();aide.SetToolTip(lireCurseur,"Cliquez dans le texte. Si du texte est sélectionné, la lecture commence au début de la sélection et continue jusqu’à la fin du document.");
        statut.Dock=DockStyle.Fill; statut.Text="Ouvrez ou glissez un PDF, DOCX, EPUB, ODT, HTML ou fichier texte."; grille.Controls.Add(statut,0,4);
        texte.MaxLength=int.MaxValue;
        texte.TextChanged+=delegate {
            if(changeSurlignage)return;
            texteModifie=true;empreinteTexte=null;
            if(audioOuvert) {FermerAudio();statut.Text="Texte modifié. Cliquez sur ▶ Lire pour recommencer.";}
        };
        voix.SelectedIndexChanged+=delegate {if(audioOuvert)FermerAudio();statut.Text="Voix choisie : "+voix.Text+". Appliquée à la prochaine lecture.";};
        vitesse.SelectedIndexChanged+=delegate {if(audioOuvert)FermerAudio();statut.Text="Vitesse modifiée. Appliquée à la prochaine lecture.";};
        AllowDrop=true;
        DragEnter+=delegate(object s,DragEventArgs e) {if(e.Data.GetDataPresent(DataFormats.FileDrop))e.Effect=DragDropEffects.Copy;};
        DragDrop+=delegate(object s,DragEventArgs e) {try {var files=(string[])e.Data.GetData(DataFormats.FileDrop);if(files.Length>0)Importer(files[0]);}catch(Exception error){MessageBox.Show(error.Message,"Piper");}};
        Directory.CreateDirectory(temp); timer.Interval=50; timer.Tick+=Poll; timer.Start();
        FormClosing+=delegate { Arreter(); SauverSession(true); timer.Stop(); try {Directory.Delete(temp,true);} catch {} };
        ChargerSession();
        Shown+=delegate { if(PositionValide()) {texte.Select(positionLecture,0);texte.ScrollToCaret();} };
    }
    // ---- Session : texte et position de lecture (version 1.5) ----
    string DossierSession { get { return Path.Combine(racine,"session"); } }
    static string Empreinte(string s) {
        ulong h=14695981039346656037UL;
        foreach(char c in s) {h^=c;h*=1099511628211UL;}
        return s.Length+"-"+h.ToString("x16");
    }
    static void EcrireSur(string chemin,string contenu) {
        string tmp=chemin+".tmp";File.WriteAllText(tmp,contenu,new UTF8Encoding(false));
        if(File.Exists(chemin))File.Replace(tmp,chemin,null);else File.Move(tmp,chemin);
    }
    void SauverSession(bool forcer) {
        if(chargement)return;
        if(!forcer && !texteModifie && !positionModifiee)return;
        if(!forcer && (DateTime.Now-derniereSauvegarde).TotalSeconds<2)return;
        try {
            Directory.CreateDirectory(DossierSession);
            if(texteModifie || empreinteSauvee==null) {
                string t=texte.Text;string h=Empreinte(t);
                if(h!=empreinteSauvee) {EcrireSur(Path.Combine(DossierSession,"texte.txt"),t);empreinteSauvee=h;}
                empreinteTexte=h;texteModifie=false;
            }
            EcrireSur(Path.Combine(DossierSession,"position.txt"),(empreintePosition??"")+"\n"+positionLecture+"\n"+(documentOuvert??""));
            positionModifiee=false;derniereSauvegarde=DateTime.Now;
        } catch(Exception) {}
    }
    void ChargerSession() {
        string fichierTexte=Path.Combine(DossierSession,"texte.txt"),fichierPosition=Path.Combine(DossierSession,"position.txt");
        if(!File.Exists(fichierTexte))return;
        chargement=true;
        try {
            string t=File.ReadAllText(fichierTexte,Encoding.UTF8);
            texte.Text=t;
            string h=Empreinte(texte.Text);empreinteSauvee=Empreinte(t)==h?h:null;texteModifie=empreinteSauvee==null;empreinteTexte=h;
            if(File.Exists(fichierPosition)) {
                string[] l=File.ReadAllText(fichierPosition,Encoding.UTF8).Split('\n');
                int p;
                if(l.Length>=2 && l[0].Length>0 && int.TryParse(l[1],out p) && p>=0) {positionLecture=p;empreintePosition=l[0];}
                if(l.Length>=3 && l[2].Trim().Length>0) {documentOuvert=l[2].Trim();Text="Piper — "+Path.GetFileName(documentOuvert);}
            }
            statut.Text=PositionValide()?"Texte et position de lecture retrouvés. Cliquez sur ⟲ Reprendre où j'étais.":"Texte précédent retrouvé.";
        } catch(Exception) {} finally {chargement=false;}
    }
    void Reprendre() {
        if(travail!=null || audioOuvert || lectureProgressive) {statut.Text="Arrêtez la lecture en cours avant de reprendre.";return;}
        if(!PositionValide()) {statut.Text="Aucune position de lecture enregistrée pour ce texte.";return;}
        Demarrer(false,null,positionLecture);
    }
    void NoterPosition(int position) {
        if(position!=positionLecture || empreintePosition!=empreinteLecture) {positionLecture=position;empreintePosition=empreinteLecture;positionModifiee=true;}
    }
    string EmpreinteActuelle() {
        if(empreinteTexte==null) {empreinteTexte=Empreinte(texte.Text);}
        return empreinteTexte;
    }
    bool PositionValide() {
        return positionLecture>=0 && positionLecture<texte.TextLength && empreintePosition!=null && empreintePosition==EmpreinteActuelle();
    }
    Button Ajouter(Control parent,string nom,Action action) {
        var b=new Button {Text=nom,AutoSize=true,Height=36,Padding=new Padding(8,3,8,3)};
        b.Click+=delegate {try {action();} catch(Exception e) {MessageBox.Show(e.Message,"Piper");}}; parent.Controls.Add(b);return b;
    }
    void Colorer(int debut,int longueur,Color couleur) {
        if(debut<0 || longueur<=0 || debut+longueur>texte.TextLength)return;
        texte.Select(debut,longueur);texte.SelectionBackColor=couleur;
    }
    /// Efface le surlignage (debut &lt; 0).
    void Surligner(int debut,int longueur) {Surligner(debut,longueur,debut,longueur);}
    /// Phrase en jaune clair, mot en cours en jaune fonce. Fait defiler seulement si le mot sort de l'ecran.
    void Surligner(int pDebut,int pLongueur,int mDebut,int mLongueur) {
        changeSurlignage=true;
        SendMessage(texte.Handle,0x000B,IntPtr.Zero,IntPtr.Zero); // WM_SETREDRAW off : pas de clignotement
        try {
            if(phraseDebut!=pDebut || phraseLongueur!=pLongueur) {
                Colorer(phraseDebut,phraseLongueur,texte.BackColor);
                Colorer(surligneDebut,surligneLongueur,texte.BackColor);
                if(pDebut>=0)Colorer(pDebut,pLongueur,CouleurPhrase);
            } else if(surligneDebut>=0) Colorer(surligneDebut,surligneLongueur,pDebut>=0?CouleurPhrase:texte.BackColor);
            phraseDebut=pDebut;phraseLongueur=pLongueur;surligneDebut=mDebut;surligneLongueur=mLongueur;
            if(mDebut>=0) {
                Colorer(mDebut,mLongueur,CouleurMot);
                texte.Select(mDebut,0);
            }
        } finally {
            SendMessage(texte.Handle,0x000B,new IntPtr(1),IntPtr.Zero);
            if(mDebut>=0) {
                Point p=texte.GetPositionFromCharIndex(mDebut);
                if(p.Y<0 || p.Y>texte.ClientSize.Height-2*texte.Font.Height)texte.ScrollToCaret();
            }
            texte.Invalidate();
            changeSurlignage=false;
        }
    }
    static int[][] Tableau(object valeur) {
        var liste=valeur as System.Collections.ArrayList;
        if(liste==null)return new int[0][];
        var res=new int[liste.Count][];
        for(int i=0;i<liste.Count;i++) {
            var l=(System.Collections.ArrayList)liste[i];
            res[i]=new int[l.Count];for(int k=0;k<l.Count;k++)res[i][k]=Convert.ToInt32(l[k]);
        }
        return res;
    }
    /// Indice du dernier element dont le debut (ms) est &lt;= temps ; 0 si aucun.
    static int IndiceAuTemps(int[][] liste,int temps) {
        int bas=0,haut=liste.Length-1,res=0;
        while(bas<=haut) {int m=(bas+haut)/2;if(liste[m][0]<=temps){res=m;bas=m+1;}else haut=m-1;}
        return res;
    }
    /// Met le surlignage au mot prononce a l'instant « temps » (ms) du passage en cours.
    void SuivreTemps(int temps) {
        if(minuteMots==null || minuteMots.Length==0)return;
        int m=IndiceAuTemps(minuteMots,temps);
        int p=minutePhrases!=null && minutePhrases.Length>0?IndiceAuTemps(minutePhrases,temps):-1;
        if(m==motCourant && p==phraseCourante)return;
        motCourant=m;phraseCourante=p;
        int md=debutLecture+passageDebut+minuteMots[m][2],ml=minuteMots[m][3]-minuteMots[m][2];
        int pd=md,pl=ml;
        if(p>=0) {pd=debutLecture+passageDebut+minutePhrases[p][2];pl=minutePhrases[p][3]-minutePhrases[p][2];}
        Surligner(pd,pl,md,ml);
        NoterPosition(pd);
    }
    void Arreter() {
        if(IsDisposed || texte.IsDisposed)return;
        int position=texte.SelectionStart;int selection=texte.SelectionLength;
        Surligner(-1,0);texte.Select(position,selection);
        minuteMots=null;minutePhrases=null;motCourant=-1;phraseCourante=-1;
        if(lectureProgressive)SauverSession(true);
        lectureProgressive=false;
        if(travail!=null) { if(!travail.HasExited) {
            var kill=new ProcessStartInfo("taskkill.exe","/PID "+travail.Id+" /T /F") {UseShellExecute=false,CreateNoWindow=true};
            using(var p=Process.Start(kill))p.WaitForExit(5000);
            travail.WaitForExit(5000);
        } travail.Dispose(); travail=null; }
        FermerAudio();
        if(dossierLecture!=null && Directory.Exists(dossierLecture)) foreach(var f in Directory.GetFiles(dossierLecture)) try {File.Delete(f);} catch(IOException) {}
        audioCourant=null;
        vitesse.Enabled=true;voix.Enabled=true;
        texte.ReadOnly=false; statut.Text="Arrêté. Vous pouvez modifier le texte.";
    }
    void LireDepuisCurseur() {
        if(travail!=null || audioOuvert || lectureProgressive) {statut.Text="Arrêtez la lecture avant de choisir un nouveau départ.";return;}
        int depart=texte.SelectionStart;
        if(string.IsNullOrWhiteSpace(texte.Text.Substring(depart))) {statut.Text="Le curseur est à la fin du texte. Placez-le avant le passage à lire.";return;}
        Demarrer(false,null,depart);
    }
    void AfficherLicences() {
        string dossier=Path.Combine(racine,"licences");
        if(!Directory.Exists(dossier)) {MessageBox.Show("Les licences ne sont pas installées.","Gilles");return;}
        using(var fenetre=new Form {Text="Gilles — licences et sources",Size=new Size(850,650),StartPosition=FormStartPosition.CenterParent}) {
            var liste=new ComboBox {Dock=DockStyle.Top,DropDownStyle=ComboBoxStyle.DropDownList};
            var contenu=new TextBox {Dock=DockStyle.Fill,Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Both,Font=new Font("Segoe UI",10)};
            string[] fichiers=Directory.GetFiles(dossier,"*",SearchOption.AllDirectories);Array.Sort(fichiers);
            foreach(string fichier in fichiers)liste.Items.Add(fichier.Substring(dossier.Length+1));
            liste.SelectedIndexChanged+=delegate {contenu.Text=File.ReadAllText(fichiers[liste.SelectedIndex]).Replace("\r\n","\n").Replace("\n","\r\n");};
            fenetre.Controls.Add(contenu);fenetre.Controls.Add(liste);if(fichiers.Length>0)liste.SelectedIndex=0;fenetre.ShowDialog(this);
        }
    }
    void Demarrer(bool sauver, string exportPath=null, int depart=0) {
        if(importation && travail!=null) {MessageBox.Show("Attendez la fin de l'ouverture du document ou cliquez sur Arrêter.");return;}
        if(string.IsNullOrWhiteSpace(texte.Text)) {MessageBox.Show("Collez ou saisissez un texte."); return;}
        string chemin=exportPath;
        if(sauver && chemin==null) using(var d=new SaveFileDialog {Filter="Audio WAV|*.wav",FileName="lecture.wav",DefaultExt="wav"}) {if(d.ShowDialog()!=DialogResult.OK)return; chemin=d.FileName;}
        Arreter(); debutLecture=depart; importation=false; destination=chemin; erreur="";
        empreinteLecture=EmpreinteActuelle();
        var donnees=new Dictionary<string,object>(); donnees["text"]=texte.Text.Substring(depart); donnees["speed"]=double.Parse((string)vitesse.SelectedItem,System.Globalization.CultureInfo.InvariantCulture);
        donnees["voice"]=voix.SelectedIndex==0?"fr_FR-gilles-low":"fr_FR-siwis-medium";
        File.WriteAllText(Path.Combine(temp,"request.json"),new JavaScriptSerializer {MaxJsonLength=int.MaxValue}.Serialize(donnees),new System.Text.UTF8Encoding(false));
        var info=new ProcessStartInfo(Path.Combine(racine,"runtime","Scripts","python.exe"));
        lectureProgressive=!sauver;passage=0;audioCourant=null;
        dossierLecture=Path.Combine(temp,"passages");Directory.CreateDirectory(dossierLecture);
        info.Arguments="\""+Path.Combine(racine,"lecteur.py")+"\" "+(lectureProgressive?"--stream":"--synthesize")+" \""+Path.Combine(temp,"request.json")+"\" \""+(lectureProgressive?dossierLecture:Path.Combine(temp,"lecture.wav"))+"\"";
        info.UseShellExecute=false; info.CreateNoWindow=true; info.RedirectStandardError=true;
        info.EnvironmentVariables["TEMP"]=temp;info.EnvironmentVariables["TMP"]=temp;
        travail=new Process {StartInfo=info}; travail.ErrorDataReceived+=delegate(object s,DataReceivedEventArgs e){if(e.Data!=null)erreur+=e.Data+Environment.NewLine;};
        travail.Start(); travail.BeginErrorReadLine(); debut=DateTime.Now; texte.ReadOnly=true;
        vitesse.Enabled=false;voix.Enabled=false;
        statut.Text="Préparation de la voix… Arrêter permet d’annuler.";
    }
    void Importer(string fichier) {
        Arreter(); importation=true; erreur=""; documentOuvert=fichier;
        var info=new ProcessStartInfo(Path.Combine(racine,"runtime","Scripts","python.exe"));
        info.Arguments="\""+Path.Combine(racine,"documents.py")+"\" \""+fichier+"\" \""+Path.Combine(temp,"document.json")+"\""+(nettoyerPdf.Checked?" --clean-pdf":"");
        info.UseShellExecute=false;info.CreateNoWindow=true;info.RedirectStandardError=true;
        info.EnvironmentVariables["TEMP"]=temp;info.EnvironmentVariables["TMP"]=temp;
        travail=new Process {StartInfo=info};travail.ErrorDataReceived+=delegate(object s,DataReceivedEventArgs e){if(e.Data!=null)erreur+=e.Data+Environment.NewLine;};
        travail.Start();travail.BeginErrorReadLine();debut=DateTime.Now;texte.ReadOnly=true;
        statut.Text="Ouverture du document…";
    }
    void Poll(object sender,EventArgs args) {
        lireCurseur.Enabled=travail==null && !audioOuvert && !lectureProgressive;
        if(!lireCurseur.Enabled) reprendre.Enabled=false;
        else if((DateTime.Now-dernierControle).TotalMilliseconds>=500) {dernierControle=DateTime.Now;reprendre.Enabled=PositionValide();}
        SauverSession(false);
        if(lectureProgressive) {PollLecture();return;}
        if(travail==null) {
            if(audioOuvert && !suspendu)try {if(Audio("status "+alias+" mode")=="stopped") {FermerAudio();statut.Text="Lecture terminée.";}}catch(Exception e){statut.Text=e.Message;}
            return;
        }
        if(!travail.HasExited) {statut.Text=(importation?"Ouverture du document : ":"Préparation de la voix : ")+(int)(DateTime.Now-debut).TotalSeconds+" s. Le texte reste visible."; return;}
        travail.WaitForExit(); int code=travail.ExitCode; travail.Dispose(); travail=null; texte.ReadOnly=false;vitesse.Enabled=true;voix.Enabled=true;
        if(code!=0){statut.Text="Le traitement a échoué."; MessageBox.Show(erreur,"Piper");return;}
        if(importation) {
            importation=false;
            try {
                var data=new JavaScriptSerializer {MaxJsonLength=int.MaxValue}.Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(temp,"document.json")));
                if(data.ContainsKey("error")) {statut.Text="Document non importé. Votre texte précédent est conservé.";MessageBox.Show(data["error"],"Ouverture du document");return;}
                texte.Text=data["text"].Replace("\r\n","\n").Replace("\n","\r\n");
                Text="Piper — "+Path.GetFileName(documentOuvert);
                statut.Text="Document prêt : "+data["name"]+". Cliquez sur Lire.";
                if(!string.IsNullOrEmpty(data["warning"])) {statut.Text=data["warning"];MessageBox.Show(data["warning"],"Document importé partiellement");}
            }catch(Exception error){statut.Text="Erreur d'ouverture.";MessageBox.Show(error.Message,"Document");}
            return;
        }
        try {
            string audio=Path.Combine(temp,"lecture.wav");
            if(destination!=null) {File.Copy(audio,destination,true);statut.Text="Audio enregistré : "+destination;}
            else {LireAudio(audio);}
        } catch(Exception e) {statut.Text="Erreur audio.";MessageBox.Show(e.Message);}
    }
    void PollLecture() {
        try {
            if(travail!=null && travail.HasExited) {
                travail.WaitForExit();int code=travail.ExitCode;travail.Dispose();travail=null;
                if(code!=0) {Arreter();statut.Text="La préparation a échoué.";MessageBox.Show(erreur,"Piper");return;}
            }
            if(audioOuvert) {
                if(suspendu)return;
                if(Audio("status "+alias+" mode")!="stopped") {
                    int temps;if(int.TryParse(Audio("status "+alias+" position"),out temps))SuivreTemps(temps);
                    return;
                }
                FermerAudio();if(audioCourant!=null) {File.Delete(audioCourant);File.Delete(Path.ChangeExtension(audioCourant,"json"));}audioCourant=null;
            }
            string prochain=Path.Combine(dossierLecture,"part-"+(passage+1).ToString("D6")+".wav");
            if(File.Exists(prochain)) {
                passage++;audioCourant=prochain;
                var limites=new JavaScriptSerializer {MaxJsonLength=int.MaxValue}.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.ChangeExtension(prochain,"json")));
                passageDebut=Convert.ToInt32(limites["start"]);int passageFin=Convert.ToInt32(limites["end"]);
                minuteMots=limites.ContainsKey("mots")?Tableau(limites["mots"]):new int[0][];
                minutePhrases=limites.ContainsKey("phrases")?Tableau(limites["phrases"]):new int[0][];
                motCourant=-1;phraseCourante=-1;
                LireAudio(prochain);
                if(minuteMots.Length>0)SuivreTemps(0);
                else {Surligner(debutLecture+passageDebut,passageFin-passageDebut);NoterPosition(debutLecture+passageDebut);}
                statut.Text="Lecture du passage "+passage+". Le reste du livre se prépare progressivement.";
            } else if(travail==null && File.Exists(Path.Combine(dossierLecture,"done"))) {
                lectureProgressive=false;Surligner(-1,0);minuteMots=null;minutePhrases=null;texte.ReadOnly=false;vitesse.Enabled=true;voix.Enabled=true;statut.Text="Lecture terminée.";
                NoterPosition(-1);SauverSession(true);
            } else statut.Text="Préparation du passage "+(passage+1)+"… Arrêter permet d’annuler.";
        } catch(Exception e) {Arreter();statut.Text="Erreur de lecture : "+e.Message;}
    }
    /// Test sans carte son : surlignage mot/phrase selon le temps, et texte + position conserves a la reouverture.
    static int TesterMinutage(string jsonPython) {
        string racine=AppDomain.CurrentDomain.BaseDirectory,session=Path.Combine(racine,"session"),copie=session+"-avant-test";
        string rapport=Path.Combine(racine,"verification-minutage.txt");
        bool existait=true,deplace=false;
        try {
            if(Directory.Exists(copie))throw new Exception("Un dossier "+copie+" existe deja (test precedent interrompu) : le remettre a la place de « session » avant de relancer le test. Rien n'a ete modifie.");
            existait=Directory.Exists(session);
            if(existait) {Directory.Move(session,copie);deplace=true;}
            string t="Première phrase ici, 😀 bien sûr. Deuxième phrase là.";
            using(var f=new Lecteur()) {
                f.Opacity=0;f.ShowInTaskbar=false;f.Show();Application.DoEvents();
                f.texte.Text=t;f.debutLecture=0;f.passageDebut=0;f.empreinteLecture=f.EmpreinteActuelle();
                int i2=t.IndexOf("ici"),iE=t.IndexOf("😀"),iB=t.IndexOf("bien"),iD=t.IndexOf("Deuxième");
                f.minuteMots=new int[][]{new[]{0,300,0,8},new[]{300,600,9,15},new[]{600,800,i2,i2+3},new[]{800,1000,iB,iB+4},new[]{1000,1300,iD,iD+8},new[]{1300,1600,iD+9,iD+16},new[]{1600,2000,iD+17,iD+19}};
                f.minutePhrases=new int[][]{new[]{0,1000,0,iD-1},new[]{1000,2000,iD,t.Length}};
                f.SuivreTemps(0);
                if(f.surligneDebut!=0 || f.surligneLongueur!=8 || f.phraseDebut!=0)throw new Exception("Mot initial");
                f.SuivreTemps(650);
                if(f.surligneDebut!=i2)throw new Exception("Mot a 650 ms : "+f.surligneDebut);
                f.texte.Select(i2,1);if(f.texte.SelectionBackColor.ToArgb()!=CouleurMot.ToArgb())throw new Exception("Couleur du mot");
                f.texte.Select(0,1);if(f.texte.SelectionBackColor.ToArgb()!=CouleurPhrase.ToArgb())throw new Exception("Couleur de phrase");
                f.SuivreTemps(900);if(f.surligneDebut!=iB)throw new Exception("Mot apres emoji (UTF-16)");
                f.SuivreTemps(1450);
                if(f.surligneDebut!=iD+9 || f.phraseDebut!=iD)throw new Exception("Phrase 2");
                f.texte.Select(0,1);if(f.texte.SelectionBackColor.ToArgb()!=f.texte.BackColor.ToArgb())throw new Exception("Ancienne phrase non effacee");
                f.texte.Select(i2,1);if(f.texte.SelectionBackColor.ToArgb()!=f.texte.BackColor.ToArgb())throw new Exception("Ancien mot non efface");
                f.SuivreTemps(100);if(f.surligneDebut!=0)throw new Exception("Retour en arriere");
                f.SuivreTemps(1450);
                if(f.positionLecture!=iD)throw new Exception("Position notee : "+f.positionLecture);
                if(f.texte.Text!=t)throw new Exception("Texte modifie par le surlignage");
                f.SauverSession(true);
                f.Surligner(-1,0);
            }
            using(var g=new Lecteur()) {
                if(g.texte.Text!=t)throw new Exception("Texte non retrouve a la reouverture");
                if(g.positionLecture!=t.IndexOf("Deuxième"))throw new Exception("Position non retrouvee : "+g.positionLecture);
                g.Opacity=0;g.ShowInTaskbar=false;g.Show();Application.DoEvents();   // affichage : la position doit survivre
                g.dernierControle=DateTime.MinValue;g.Poll(null,EventArgs.Empty);if(!g.reprendre.Enabled)throw new Exception("Bouton Reprendre inactif apres affichage");
                g.texte.Text="Autre texte colle.";g.dernierControle=DateTime.MinValue;g.Poll(null,EventArgs.Empty);
                if(g.PositionValide() || g.reprendre.Enabled)throw new Exception("Position offerte pour un autre texte");
                g.texte.Text=t;g.dernierControle=DateTime.MinValue;g.Poll(null,EventArgs.Empty);
                if(!g.PositionValide() || !g.reprendre.Enabled)throw new Exception("Position perdue apres avoir recolle le meme texte");
                g.SauverSession(true);
            }
            using(var h=new Lecteur()) {
                if(!h.PositionValide())throw new Exception("Position perdue sur le disque apres un autre texte puis le meme");
            }
            string extra="";
            if(jsonPython!=null) {
                var d=new JavaScriptSerializer {MaxJsonLength=int.MaxValue}.Deserialize<Dictionary<string,object>>(File.ReadAllText(jsonPython));
                int[][] mots=Tableau(d["mots"]),phr=Tableau(d["phrases"]);
                if(mots.Length==0 || phr.Length==0)throw new Exception("Minutage Python vide");
                for(int k=1;k<mots.Length;k++)if(mots[k][0]<mots[k-1][0])throw new Exception("Minutage Python non croissant");
                extra=" Minutage produit par lecteur.py lu : "+mots.Length+" mots, "+phr.Length+" phrases, "+d["exactes"]+" phrases alignees exactement.";
            }
            File.WriteAllText(rapport,"Reussi : surlignage mot et phrase selon le temps audio (y compris apres un emoji), effacement, retour en arriere, texte intact ; texte et position retrouves a la reouverture, y compris apres affichage de la fenetre ; bouton Reprendre ; position non offerte pour un autre texte et retrouvee en recollant le meme."+extra+" "+DateTime.Now.ToString("s"));
            return 0;
        } catch(Exception e) {File.WriteAllText(rapport,"ECHEC : "+e);return 1;}
        finally {
            // ne toucher a « session » que si c'est celle du test (originale mise de cote, ou absente au depart)
            try {if(deplace || !existait) {if(Directory.Exists(session))Directory.Delete(session,true);if(deplace)Directory.Move(copie,session);}} catch {}
        }
    }
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        if(args.Length>0 && args[0]=="--test-minutage") {Environment.ExitCode=TesterMinutage(args.Length>1?args[1]:null);return;}
        if(args.Length>0 && args[0]=="--test-cursor") {
            using(var f=new Lecteur()) {
                try {
                    f.Opacity=0;f.ShowInTaskbar=false;f.Show();Application.DoEvents();
                    string before="TABLE DES MATIÈRES. Préambule à ignorer.\r\n\r\n";
                    string body="Chapitre un. Bonjour, voici le passage choisi. La lecture continue sans modifier le document. ";
                    f.texte.Text=before+body+body+body;
                    string original=f.texte.Text;int start=original.IndexOf("Chapitre un.");
                    f.texte.Select(start,12);f.lireCurseur.PerformClick();
                    var req=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(f.temp,"request.json")));
                    if((string)req["text"]!=original.Substring(start) || f.texte.Text!=original)throw new Exception("Texte transmis ou document incorrect");
                    if(!Path.GetFullPath(f.temp).StartsWith(f.racine,StringComparison.OrdinalIgnoreCase))throw new Exception("Temp hors du dossier de Gilles");
                    var until=DateTime.Now.AddSeconds(90);
                    while(!f.audioOuvert && DateTime.Now<until) {Application.DoEvents();System.Threading.Thread.Sleep(30);}
                    if(!f.audioOuvert)throw new Exception("Lecture depuis curseur non démarrée");
                    if(f.surligneDebut!=start || f.surligneLongueur<=0 || f.texte.Text!=original)throw new Exception("Surlignage initial incorrect");
                    int highlighted=f.surligneDebut;
                    using(var image=new Bitmap(f.Width,f.Height)) {f.DrawToBitmap(image,new Rectangle(0,0,f.Width,f.Height));image.Save(Path.Combine(f.racine,"Apercu-surlignage.png"));}
                    System.Threading.Thread.Sleep(300);f.Pauser();int pos=int.Parse(f.Audio("status "+f.alias+" position"));
                    System.Threading.Thread.Sleep(400);
                    if(int.Parse(f.Audio("status "+f.alias+" position"))!=pos || f.surligneDebut!=highlighted)throw new Exception("Pause ou surlignage instable");
                    f.Continuer();System.Threading.Thread.Sleep(400);
                    if(int.Parse(f.Audio("status "+f.alias+" position"))<=pos)throw new Exception("Reprise immobile");
                    f.Arreter();f.texte.Select(original.Length,0);f.LireDepuisCurseur();
                    if(f.travail!=null || !f.statut.Text.Contains("fin du texte"))throw new Exception("Fin de texte non traitée");
                    f.texte.Select(start+12,0);f.LireDepuisCurseur();
                    req=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(f.temp,"request.json")));
                    if((string)req["text"]!=original.Substring(start+12))throw new Exception("Position du curseur incorrecte");
                    f.Arreter();f.Demarrer(false);
                    req=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(f.temp,"request.json")));
                    if((string)req["text"]!=original || f.texte.Text!=original)throw new Exception("Lecture complète altérée");
                    f.Arreter();
                    f.texte.Select(start,0);f.statut.Text="Cliquez dans le texte, puis sur Lire à partir du curseur. Une sélection commence à son début.";
                    using(var image=new Bitmap(f.Width,f.Height)) {f.DrawToBitmap(image,new Rectangle(0,0,f.Width,f.Height));image.Save(Path.Combine(f.racine,"Apercu-1.2.png"));}
                    File.WriteAllText(Path.Combine(f.racine,"verification-curseur.txt"),"Réussi : préambule exclu de la requête moteur ; sélection et curseur ; texte intact ; synthèse réelle ; pause et reprise ; fin du texte ; lecture complète ; surlignage synchronisé ; temporaires locaux. "+DateTime.Now.ToString("s"));
                    f.Close();
                } catch(Exception e) {File.WriteAllText(Path.Combine(f.racine,"verification-curseur-erreur.txt"),e.ToString());Environment.ExitCode=1;}
                finally {f.Arreter();}
            }
            return;
        }
        if(args.Length>1 && args[0]=="--test-long") {
            using(var f=new Lecteur()) {
                try {
                f.Opacity=0;f.ShowInTaskbar=false;f.Show();Application.DoEvents();
                f.Importer(Path.GetFullPath(args[1]));var deadline=DateTime.Now.AddSeconds(90);
                while(f.travail!=null && DateTime.Now<deadline){Application.DoEvents();System.Threading.Thread.Sleep(30);}
                if(f.travail!=null || f.texte.Text.Length<300000 || !f.texte.Text.Contains("Derniere page 300"))throw new Exception("Import grand PDF incomplet");
                f.Demarrer(false);deadline=DateTime.Now.AddSeconds(120);
                while(!f.audioOuvert && DateTime.Now<deadline){Application.DoEvents();System.Threading.Thread.Sleep(30);}
                if(!f.audioOuvert || f.passage!=1)throw new Exception("Pas de lecture progressive");
                System.Threading.Thread.Sleep(300);f.Pauser();
                int pos=int.Parse(f.Audio("status "+f.alias+" position"));
                var wait=DateTime.Now.AddSeconds(5);while(DateTime.Now<wait){Application.DoEvents();System.Threading.Thread.Sleep(30);}
                if(Math.Abs(int.Parse(f.Audio("status "+f.alias+" position"))-pos)>30)throw new Exception("Pause instable");
                int files=Directory.GetFiles(f.dossierLecture,"part-*.wav").Length;
                if(files>3)throw new Exception("Trop de passages en attente");
                f.Continuer();wait=DateTime.Now.AddSeconds(2);while(DateTime.Now<wait){Application.DoEvents();System.Threading.Thread.Sleep(30);}
                if(int.Parse(f.Audio("status "+f.alias+" position"))<=pos)throw new Exception("Reprise en échec : mode="+f.Audio("status "+f.alias+" mode")+", position="+pos+", après="+f.Audio("status "+f.alias+" position"));
                f.Audio("seek "+f.alias+" to end");f.Audio("play "+f.alias);
                deadline=DateTime.Now.AddSeconds(90);
                while(f.passage<2 && DateTime.Now<deadline){Application.DoEvents();System.Threading.Thread.Sleep(30);}
                if(f.passage<2 || f.surligneDebut<=0 || File.Exists(Path.Combine(f.dossierLecture,"part-000001.wav")))throw new Exception("Enchaînement ou suppression en échec");
                f.Arreter();if(f.travail!=null || f.audioOuvert || f.texte.ReadOnly || f.surligneDebut!=-1)throw new Exception("Arrêt en échec");
                File.WriteAllText(Path.Combine(f.racine,"verification-long.txt"),"Réussi : import PDF 300 pages ("+f.texte.Text.Length+" caractères), lecture progressive réelle avec Gilles, pause stable, reprise, file audio bornée à 3 passages, enchaînement et suppression du passage lu, arrêt. "+DateTime.Now.ToString("s"));
                f.Close();
                } catch(Exception e) {File.WriteAllText(Path.Combine(f.racine,"verification-long-erreur.txt"),e.ToString());Environment.ExitCode=1;}
                finally {f.Arreter();}
            }
            return;
        }
        if(args.Length>0 && args[0]=="--test") {
            using(var f=new Lecteur()) {
                f.Show(); Application.DoEvents();
                if(args.Length>1) {
                    f.Importer(Path.GetFullPath(args[1]));var timeout=DateTime.Now.AddSeconds(30);
                    while(f.travail!=null && DateTime.Now<timeout){Application.DoEvents();System.Threading.Thread.Sleep(50);}
                    if(!f.texte.Text.Contains("Bonjour PDF"))throw new Exception("Import PDF échoué");
                }
                using(var image=new Bitmap(f.Width,f.Height)) {f.DrawToBitmap(image,new Rectangle(0,0,f.Width,f.Height)); image.Save(Path.Combine(f.racine,"Apercu.png"));}
                f.texte.Text="Bonjour. Ceci est un test de la fenêtre Piper.";
                f.Demarrer(true,Path.Combine(f.temp,"test-export.wav"));
                var limit=DateTime.Now.AddSeconds(90);
                while(f.travail!=null && DateTime.Now<limit) {Application.DoEvents();System.Threading.Thread.Sleep(50);}
                if(!File.Exists(f.destination) || new FileInfo(f.destination).Length<1000) throw new Exception("Test de synthèse échoué");
                f.LireAudio(f.destination);System.Threading.Thread.Sleep(300);f.Pauser();
                int position=int.Parse(f.Audio("status "+f.alias+" position"));System.Threading.Thread.Sleep(400);
                if(Math.Abs(int.Parse(f.Audio("status "+f.alias+" position"))-position)>30)throw new Exception("La pause ne conserve pas la position");
                f.Continuer();System.Threading.Thread.Sleep(400);
                if(int.Parse(f.Audio("status "+f.alias+" position"))<=position)throw new Exception("La reprise ne progresse pas");
                f.Arreter();
                f.Demarrer(false); f.Arreter(); if(f.travail!=null || f.texte.ReadOnly) throw new Exception("Test arrêt échoué");
                File.WriteAllText(Path.Combine(f.racine,"verification.txt"),"Réussi : import PDF, synthèse Gilles, export WAV, pause avec position stable, reprise avec progression, arrêt.\r\n"+DateTime.Now.ToString("s"));
                f.Close();
            }
            return;
        }
        Application.Run(new Lecteur());
    }
}
