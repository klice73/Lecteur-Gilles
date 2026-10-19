package fr.lecteurgilles.android

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.media.*
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Spanned
import android.text.style.BackgroundColorSpan
import java.util.concurrent.ConcurrentLinkedQueue
import android.text.InputType
import android.view.View
import android.view.WindowManager
import android.widget.*
import com.k2fsa.sherpa.onnx.*
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger
import java.util.zip.ZipInputStream

class MainActivity : Activity() {
    /** Version 1.5 : un élément par mot (avec sa phrase), dans l'ordre de l'audio. */
    private data class SpokenSpan(val id:Int,val firstFrame:Long,val lastFrame:Long,val start:Int,val end:Int,val phraseStart:Int,val phraseEnd:Int)
    private val spokenSpans=ConcurrentLinkedQueue<SpokenSpan>()
    private val highlightHandler=Handler(Looper.getMainLooper())
    private var highlight:BackgroundColorSpan?=null
    private var phraseHighlight:BackgroundColorSpan?=null
    private var highlightStart=-1
    private var phraseHighlightStart=-1
    private val highlightTick=object:Runnable {
        override fun run(){
            if(destroyed)return
            if(active && !paused) {
                val frame=track?.playbackHeadPosition?.toLong()?.and(0xffffffffL)
                if(frame!=null) {
                    while(true) {
                        val span=spokenSpans.peek()?:break
                        if(span.id!=generation.get() || frame>=span.lastFrame) {spokenSpans.poll();continue}
                        if(frame>=span.firstFrame && highlightStart!=span.start) markWord(span)
                        break
                    }
                }
            }
            highlightHandler.postDelayed(this,40)
        }
    }
    private fun clearHighlight(){
        highlight?.let{editor.text.removeSpan(it)};highlight=null;highlightStart=-1
        phraseHighlight?.let{editor.text.removeSpan(it)};phraseHighlight=null;phraseHighlightStart=-1
    }
    /** Phrase en jaune clair, mot en cours en jaune foncé ; défile seulement si le mot sort de l'écran. */
    private fun markWord(s:SpokenSpan){
        val n=editor.text.length
        if(s.start<0 || s.end>n || s.end<=s.start)return
        if(phraseHighlightStart!=s.phraseStart){
            phraseHighlight?.let{editor.text.removeSpan(it)}
            phraseHighlight=null;phraseHighlightStart=-1
            if(s.phraseStart>=0 && s.phraseEnd<=n && s.phraseEnd>s.phraseStart) {
                phraseHighlight=BackgroundColorSpan(0xfffff6c4.toInt()).also{editor.text.setSpan(it,s.phraseStart,s.phraseEnd,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)}
                phraseHighlightStart=s.phraseStart
            }
            notePosition(if(s.phraseStart>=0) s.phraseStart else s.start)
        }
        highlight?.let{editor.text.removeSpan(it)}
        highlight=BackgroundColorSpan(0xffffd54f.toInt()).also{editor.text.setSpan(it,s.start,s.end,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)}
        highlightStart=s.start
        editor.setSelection(s.start)
        editor.layout?.let { layout ->
            val line=layout.getLineForOffset(s.start)
            val top=layout.getLineTop(line)+editor.totalPaddingTop
            val bottom=layout.getLineBottom(line)+editor.totalPaddingTop
            if(top<editor.scrollY || bottom>editor.scrollY+editor.height)editor.scrollTo(0,maxOf(0,top-editor.height/3))
        }
    }
    // ---- Version 1.5 : texte et position de lecture conservés (fermeture, arrêt du téléphone, déconnexion) ----
    private val textFile by lazy { File(filesDir,"texte-courant.txt") }
    private var readingHash=""           // empreinte du texte lu (fixe pendant la lecture)
    private fun prefs()=getPreferences(MODE_PRIVATE)
    private fun empreinte(t:CharSequence)="${t.length}-${t.toString().hashCode()}"
    private fun notePosition(position:Int){
        if(readingHash.isEmpty())return
        prefs().edit().putInt("position",position).putString("position_texte",readingHash).apply()
    }
    private fun savedPosition():Int{
        val p=prefs().getInt("position",-1)
        if(p<0 || prefs().getString("position_texte","")!=empreinte(editor.text) || p>=editor.text.length)return -1
        return p
    }
    private fun saveText(){
        try { val tmp=File(filesDir,"texte-courant.tmp"); tmp.writeText(editor.text.toString()); if(!tmp.renameTo(textFile)){textFile.delete();tmp.renameTo(textFile)} } catch(_:Exception){}
    }
    private fun loadText():String? = try { if(textFile.exists()) textFile.readText() else null } catch(_:Exception){ null }
    private fun resumeWhereLeft(){
        if(active){status.text="Arrêtez la lecture en cours avant de reprendre.";return}
        val p=savedPosition()
        if(p<0){status.text="Aucune position de lecture enregistrée pour ce texte.";return}
        editor.setSelection(p);startReading(true)
    }
    private val noisy=object:android.content.BroadcastReceiver(){
        // écouteurs ou casque Bluetooth débranchés : pause (et position enregistrée)
        override fun onReceive(c:android.content.Context?,i:Intent?){ if(i?.action==AudioManager.ACTION_AUDIO_BECOMING_NOISY) pauseReading() }
    }
    private lateinit var editor: EditText
    private lateinit var status: TextView
    private lateinit var play: Button
    private lateinit var pause: Button
    private lateinit var playFromCursor: Button
    private lateinit var resume: Button
    private lateinit var speed: Spinner
    private val worker = Executors.newSingleThreadExecutor()
    private val generation = AtomicInteger()
    @Volatile private var paused = false
    @Volatile private var active = false
    @Volatile private var destroyed = false
    @Volatile private var track: AudioTrack? = null
    private var engine: OfflineTts? = null // Access only on worker
    private lateinit var audioManager: AudioManager
    private lateinit var focus: AudioFocusRequest
    private fun dp(value:Int)=(value*resources.displayMetrics.density).toInt()

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        PDFBoxResourceLoader.init(applicationContext)
        audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
        focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setOnAudioFocusChangeListener { change -> if(change < 0) runOnUiThread { pauseReading() } }.build()
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16),dp(16),dp(16),dp(12)); setBackgroundColor(0xffeef4f3.toInt()) }
        layout.setOnApplyWindowInsetsListener { v, insets -> v.setPadding(dp(16),dp(16)+insets.systemWindowInsetTop,dp(16),dp(12)+insets.systemWindowInsetBottom); insets }
        val title = TextView(this).apply { text = "Lecteur Gilles"; textSize = 26f; setTextColor(0xff145c54.toInt()) }
        layout.addView(title)
        layout.addView(TextView(this).apply { text = "Voix française • hors connexion • sans quota"; textSize = 14f })
        val tools = LinearLayout(this)
        tools.addView(button("Ouvrir un document") { openDocument() }, LinearLayout.LayoutParams(0,dp(56),1f))
        tools.addView(button("Coller") {
            val clip = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
            clip.primaryClip?.getItemAt(0)?.coerceToText(this)?.let { stopReading(); editor.setText(it); saveText(); controls() }
        }, LinearLayout.LayoutParams(0,dp(56),0.5f))
        layout.addView(tools)
        speed = Spinner(this).apply { adapter=ArrayAdapter(this@MainActivity,android.R.layout.simple_spinner_dropdown_item,listOf("Vitesse 0,8×","Vitesse 1×","Vitesse 1,2×","Vitesse 1,5×"));setSelection(1) }
        layout.addView(speed)
        editor = EditText(this).apply {
            hint="Collez votre texte ou ouvrez un PDF, DOCX, ODT, HTML ou TXT."
            textSize=18f; gravity=android.view.Gravity.TOP
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            setHorizontallyScrolling(false)
            setText(loadText() ?: getPreferences(MODE_PRIVATE).getString("text","Bonjour ! Je suis Gilles. Collez votre texte, puis appuyez sur Lire."))
        }
        layout.addView(editor,LinearLayout.LayoutParams(-1,0,1f))
        val controls=LinearLayout(this)
        play=button("▶ Lire tout") { if(active && paused) resumeReading() else if(!active) startReading() }
        pause=button("Ⅱ Pause") {pauseReading()}.apply {isEnabled=false}
        controls.addView(play,LinearLayout.LayoutParams(0,dp(60),1f));controls.addView(pause,LinearLayout.LayoutParams(0,dp(60),1f))
        controls.addView(button("■ Arrêter") {stopReading()},LinearLayout.LayoutParams(0,dp(60),1f))
        layout.addView(controls)
        playFromCursor=button("▶ Lire à partir du curseur") {startReading(true)}
        resume=button("⟲ Reprendre où j'étais") {resumeWhereLeft()}
        val cursorRow=LinearLayout(this)
        cursorRow.addView(playFromCursor,LinearLayout.LayoutParams(0,dp(56),1f));cursorRow.addView(resume,LinearLayout.LayoutParams(0,dp(56),1f))
        layout.addView(cursorRow)
        layout.addView(TextView(this).apply {text="Touchez le texte pour placer le curseur. Une sélection commence à son début ; la lecture continue jusqu’à la fin.";textSize=12f})
        status=TextView(this).apply {text="Prêt. La première préparation peut prendre un moment.";textSize=14f;setPadding(0,12,0,8)}
        layout.addView(status)
        layout.addView(button("À propos et licences") {showLicenses()})
        setContentView(layout)
        highlightHandler.post(highlightTick)
        registerReceiver(noisy,android.content.IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY))
        val p=savedPosition()
        if(p>=0){editor.setSelection(p);status.text="Position de lecture retrouvée. Touchez ⟲ Reprendre où j'étais."}
        controls()
    }
    private fun showLicenses(){
        val names=(assets.list("licenses")?:emptyArray()).sorted()
        AlertDialog.Builder(this).setTitle("Gilles — licences et sources")
            .setItems(names.toTypedArray()) { _, index ->
                val text=assets.open("licenses/${names[index]}").bufferedReader().use{it.readText()}
                val content=TextView(this).apply {setText(text);textSize=14f;setTextIsSelectable(true);setPadding(dp(16),dp(12),dp(16),dp(12))}
                AlertDialog.Builder(this).setTitle(names[index]).setView(ScrollView(this).apply{addView(content)}).setPositiveButton("Fermer",null).show()
            }.setNegativeButton("Fermer",null).show()
    }
    private fun button(label:String,action:()->Unit)=Button(this).apply {text=label;isAllCaps=false;setOnClickListener{action()}}
    private fun ui(job:()->Unit) {runOnUiThread {if(!destroyed)job()}}
    private fun message(text:String){ui {status.text=text}}
    private fun controls(){playFromCursor.isEnabled=!active;resume.isEnabled=!active&&savedPosition()>=0;editor.isEnabled=!active;speed.isEnabled=!active;play.text=if(paused)"▶ Continuer" else "▶ Lire tout";pause.isEnabled=active&&!paused}
    private fun stopReading(){if(active)savePosition();generation.incrementAndGet();spokenSpans.clear();clearHighlight();active=false;paused=false;track?.let {try{it.pause();it.flush()}catch(_:IllegalStateException){}};audioManager.abandonAudioFocusRequest(focus);window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);controls();status.text="Arrêté."}
    private fun pauseReading(){if(!active||paused)return;paused=true;savePosition();track?.let{try{it.pause()}catch(_:IllegalStateException){}};controls();status.text="En pause. ▶ Continuer reprend au même endroit.";window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
    private fun resumeReading(){if(audioManager.requestAudioFocus(focus)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED){status.text="La sortie audio est occupée.";return};paused=false;track?.play();controls();status.text="Lecture reprise.";window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
    /** Enregistre tout de suite (pause, arrêt, fermeture) ; la phrase en cours est déjà notée. */
    private fun savePosition(){ if(phraseHighlightStart>=0) notePosition(phraseHighlightStart) else if(highlightStart>=0) notePosition(highlightStart) }
    private fun copyAssets(path:String,target:File){
        val files=assets.list(path)?:emptyArray()
        if(files.isEmpty()){target.parentFile?.mkdirs();assets.open(path).use{input->target.outputStream().use{input.copyTo(it)}}}
        else{target.mkdirs();for(name in files)copyAssets("$path/$name",File(target,name))}
    }
    private fun getEngine():OfflineTts {
        engine?.let{return it}
        val name="vits-piper-fr_FR-gilles-low"
        val dir=File(filesDir,name)
        val marque="ready-voix-plafonnee-1" // changer ce nom à chaque nouvelle voix livrée dans l’APK
        if(!File(dir,marque).exists()){dir.deleteRecursively();copyAssets(name,dir);File(dir,marque).writeText("ok")}
        return OfflineTts(config=OfflineTtsConfig(model=OfflineTtsModelConfig(
            vits=OfflineTtsVitsModelConfig(model=File(dir,"fr_FR-gilles-low.onnx").path,tokens=File(dir,"tokens.txt").path,dataDir=File(dir,"espeak-ng-data").path),numThreads=2),maxNumSentences=1)).also{engine=it}
    }
    private fun startReading(fromCursor:Boolean=false){
        if(active)return
        val fullText=editor.text.toString()
        val text=if(fromCursor) ReadingStart.fromCursor(fullText,editor.selectionStart,editor.selectionEnd) else fullText
        val baseOffset=fullText.length-text.length
        if(text.isBlank()){status.text=if(fromCursor) "Le curseur est à la fin du texte. Placez-le avant le passage à lire." else "Ajoutez un texte à lire.";return}
        if(audioManager.requestAudioFocus(focus)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED){status.text="La sortie audio est occupée.";return}
        readingHash=empreinte(fullText);saveText()
        val id=generation.incrementAndGet();val rate=listOf(0.8f,1f,1.2f,1.5f)[speed.selectedItemPosition]
        active=true;paused=false;controls();status.text="Préparation de Gilles…";window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        worker.execute {
            var output:AudioTrack?=null
            var finished=false
            try {
                val tts=getEngine();if(id!=generation.get())return@execute
                val sampleRate=tts.sampleRate()
                output=AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                    .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_FLOAT).setSampleRate(sampleRate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                    .setBufferSizeInBytes(maxOf(sampleRate*2,AudioTrack.getMinBufferSize(sampleRate,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_FLOAT))).setTransferMode(AudioTrack.MODE_STREAM).build()
                track=output
                if(!paused)output.play()
                var frames=0L
                val parts=TextChunks.ranges(text)
                // Version 1.5 : une file prépare les phrases suivantes pendant que la phrase en cours est jouée
                // (pas de silence entre les phrases sur un téléphone lent). Seule elle utilise le moteur.
                class Phrase(val samples:FloatArray,val mots:List<Minutage.Temps>,val debut:Int,val fin:Int)
                val fin=Phrase(FloatArray(0),emptyList(),-1,-1)
                val file=java.util.concurrent.ArrayBlockingQueue<Phrase>(4)
                var erreurPreparation:Exception?=null
                val arret=java.util.concurrent.atomic.AtomicBoolean(false)   // la lecture s'arrête : la préparation aussi
                fun continuer()=id==generation.get() && !arret.get()
                val preparation=Thread {
                    try {
                        for((index,part) in parts.withIndex()){
                            if(!continuer())break
                            ui{if(id==generation.get()&&!paused)status.text="Lecture : passage ${index+1} / ${parts.size}"}
                            for(r in Minutage.phrases(part.text)){
                                if(!continuer())break
                                val phrase=part.text.substring(r.first,r.last+1)
                                val audio=tts.generateWithCallback(phrase,0,rate){if(continuer())1 else 0}
                                if(!continuer() || audio.samples.isEmpty())continue
                                val debutPhrase=baseOffset+part.start+r.first
                                val item=Phrase(audio.samples,Minutage.minuter(phrase,audio.samples,sampleRate),debutPhrase,debutPhrase+phrase.trimEnd().length)
                                while(continuer() && !file.offer(item,50,java.util.concurrent.TimeUnit.MILLISECONDS)){}
                            }
                        }
                    } catch(e:Exception){erreurPreparation=e}
                    finally { while(continuer() && !file.offer(fin,50,java.util.concurrent.TimeUnit.MILLISECONDS)){} }
                }
                preparation.start()
                try {
                    while(id==generation.get()){
                        val ph=file.poll(50,java.util.concurrent.TimeUnit.MILLISECONDS)?:continue
                        if(ph===fin)break
                        val samples=ph.samples
                        for(m in ph.mots)spokenSpans.add(SpokenSpan(id,frames+m.t0,frames+m.t1,ph.debut+m.debut,ph.debut+m.fin,ph.debut,ph.fin))
                        var offset=0
                        while(offset<samples.size && id==generation.get()){
                            if(paused){Thread.sleep(30);continue}
                            val written=output.write(samples,offset,minOf(4096,samples.size-offset),AudioTrack.WRITE_NON_BLOCKING)
                            if(written<0)throw IllegalStateException("Erreur audio $written")
                            offset+=written;frames+=written
                            if(written==0)Thread.sleep(10)
                        }
                    }
                } finally {
                    arret.set(true)          // erreur d'écriture ou arrêt : la préparation s'interrompt
                    preparation.join()       // le moteur n'est jamais libéré pendant une préparation
                }
                erreurPreparation?.let{throw it}
                while(id==generation.get() && (output.playbackHeadPosition.toLong() and 0xffffffffL)<frames)Thread.sleep(40)
                finished=id==generation.get()
            } catch(e:Exception){if(id==generation.get())message("Lecture impossible : ${e.message}")}
            finally {
                track=null;try{output?.stop();output?.release()}catch(_:Exception){}
                val fini=id==generation.get() && finished
                ui{if(id==generation.get()){if(fini){prefs().edit().putInt("position",-1).apply()};spokenSpans.clear();clearHighlight();active=false;paused=false;controls();audioManager.abandonAudioFocusRequest(focus);window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);if(!status.text.startsWith("Lecture impossible"))status.text="Lecture terminée."}}
            }
        }
    }
    private fun openDocument(){
        val intent=Intent(Intent.ACTION_OPEN_DOCUMENT).apply{addCategory(Intent.CATEGORY_OPENABLE);type="*/*";putExtra(Intent.EXTRA_MIME_TYPES,arrayOf("application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.oasis.opendocument.text","text/plain","text/html","text/markdown"))}
        startActivityForResult(intent,10)
    }
    @Deprecated("Android legacy activity result compatible with API 26")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?){
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode!=10||resultCode!=RESULT_OK)return
        val uri=data?.data?:return;stopReading();val id=generation.incrementAndGet();status.text="Ouverture du document…"
        worker.execute{try{val text=readDocument(uri);ui{if(id==generation.get()){editor.setText(text);saveText();controls();status.text="Document prêt. Appuyez sur ▶ Lire."}}}catch(e:Exception){ui{if(id==generation.get())status.text="Ouverture impossible : ${e.message}"}}}
    }
    private fun readDocument(uri:Uri):String{
        val mime=contentResolver.getType(uri).orEmpty()
        val bytes=contentResolver.openInputStream(uri)?.use{input->
            val out=java.io.ByteArrayOutputStream();val buf=ByteArray(8192);var total=0
            while(true){val n=input.read(buf);if(n<0)break;total+=n;if(total>30*1024*1024)throw IllegalArgumentException("Fichier supérieur à 30 Mo");out.write(buf,0,n)};out.toByteArray()
        }?:throw IllegalArgumentException("Fichier inaccessible")
        val text=when{
            mime=="application/pdf"||bytes.take(4).toByteArray().contentEquals("%PDF".toByteArray())->PDDocument.load(bytes).use{PDFTextStripper().getText(it)}
            mime.contains("wordprocessingml")||mime.contains("opendocument")-> {
                val wanted=if(mime.contains("opendocument"))"content.xml" else "word/document.xml"
                ZipInputStream(bytes.inputStream()).use{zip->
                    var result:String?=null
                    while(true){val entry=zip.nextEntry?:break;if(entry.name==wanted){
                        val xmlBuffer=java.io.ByteArrayOutputStream();val xmlPart=ByteArray(8192)
                        while(true){val n=zip.read(xmlPart);if(n<0)break;if(xmlBuffer.size()+n>10*1024*1024)throw IllegalArgumentException("Document trop long");xmlBuffer.write(xmlPart,0,n)}
                        val xml=xmlBuffer.toByteArray()
                        val parser=android.util.Xml.newPullParser();parser.setInput(xml.inputStream(),"UTF-8")
                        val out=StringBuilder()
                        while(parser.eventType!=org.xmlpull.v1.XmlPullParser.END_DOCUMENT){
                            if(parser.eventType==org.xmlpull.v1.XmlPullParser.TEXT)out.append(parser.text)
                            if(parser.eventType==org.xmlpull.v1.XmlPullParser.END_TAG && parser.name in listOf("p","h","tr"))out.append('\n')
                            parser.next()
                        };result=out.toString();break
                    }};result?:throw IllegalArgumentException("Texte du document introuvable")
                }
            }
            mime=="text/html"->android.text.Html.fromHtml(bytes.toString(Charsets.UTF_8),android.text.Html.FROM_HTML_MODE_LEGACY).toString()
            mime.startsWith("text/")->bytes.toString(Charsets.UTF_8)
            else->throw IllegalArgumentException("Formats : PDF, DOCX, ODT, TXT, HTML")
        }
        if(text.isBlank())throw IllegalArgumentException("Aucun texte. Un PDF scanné nécessite un OCR.")
        return text
    }
    override fun onSaveInstanceState(out:Bundle){if(!active)saveText();super.onSaveInstanceState(out)} // texte dans le fichier privé, pas dans le Bundle (limite ~1 Mo)
    override fun onStop(){pauseReading();savePosition();if(!active)saveText();super.onStop()}
    override fun onDestroy(){try{unregisterReceiver(noisy)}catch(_:Exception){};savePosition();destroyed=true;highlightHandler.removeCallbacks(highlightTick);stopReading();worker.execute{engine?.release();engine=null};worker.shutdown();super.onDestroy()}
}
