package fr.lecteurgilles.android

import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineNode
import com.tom_roush.pdfbox.text.PDFTextStripper
import org.xmlpull.v1.XmlPullParser
import java.util.zip.ZipInputStream

/**
 * Ouverture des documents avec leurs repères (version 1.6), comme windows/documents.py :
 * PDF (pages, étiquettes imprimées, signets), DOCX et ODT (titres, sauts de page), Markdown (#),
 * sinon chapitres devinés d'après les titres. Positions en unités UTF-16 du texte renvoyé.
 */
object Documents {
    class Resultat(val texte:String,val reperes:Reperes)

    fun extraire(bytes:ByteArray,mime:String):Resultat {
        val r=when{
            mime=="application/pdf"||bytes.take(4).toByteArray().contentEquals("%PDF".toByteArray())->pdf(bytes)
            mime.contains("wordprocessingml")->xml(bytes,"word/document.xml",false)
            mime.contains("opendocument")->xml(bytes,"content.xml",true)
            mime=="text/html"->texte(android.text.Html.fromHtml(bytes.toString(Charsets.UTF_8),android.text.Html.FROM_HTML_MODE_LEGACY).toString(),false)
            mime.contains("markdown")->texte(bytes.toString(Charsets.UTF_8),true)
            mime.startsWith("text/")->texte(bytes.toString(Charsets.UTF_8),false)
            else->throw IllegalArgumentException("Formats : PDF, DOCX, ODT, TXT, MD, HTML")
        }
        if(r.texte.isBlank())throw IllegalArgumentException("Aucun texte. Un PDF scanné nécessite un OCR.")
        return r
    }

    private fun devinee(t:String,pages:List<Pair<String,Int>> = emptyList())=Reperes(pages,Reperes.chapitresDevines(t),"devinee")

    fun texte(brut:String,markdown:Boolean):Resultat {
        val t=brut.replace("\r\n","\n").replace('\r','\n')
        if(markdown){
            val table=ArrayList<Titre>(); var pos=0
            val titre=Regex("^(#{1,6})\\s+(.+?)\\s*#*\\s*$")
            var code=false
            for(l in t.split('\n')){
                val d=l.trimStart()
                if(d.startsWith("```") || d.startsWith("~~~"))code=!code
                if(!code)titre.find(l)?.let{table.add(Titre(it.groupValues[2],it.groupValues[1].length,pos))}
                pos+=l.length+1
            }
            if(table.isNotEmpty())return Resultat(t,Reperes(emptyList(),table,"titres"))
        }
        return Resultat(t,devinee(t))
    }

    fun pdf(bytes:ByteArray):Resultat = PDDocument.load(bytes).use{doc->
        val n=doc.numberOfPages
        val stripper=PDFTextStripper()
        val pages=(1..n).map{stripper.startPage=it;stripper.endPage=it;stripper.getText(doc)}
        val texte=pages.joinToString("\n\n")
        val debuts=ArrayList<Int>(); var pos=0
        for(p in pages){debuts.add(pos);pos+=p.length+2}
        val etiquettes=try{doc.documentCatalog.pageLabels?.labelsByPageIndices?.toList()?.takeIf{it.size==n}}catch(_:Exception){null}
            ?:(1..n).map{it.toString()}
        val table=ArrayList<Titre>()
        fun parcourir(noeud:PDOutlineNode,niveau:Int){
            for(item in noeud.children()){
                try{
                    val page=item.findDestinationPage(doc)
                    val i=if(page!=null) doc.pages.indexOf(page) else -1
                    val titre=(item.title?:"").trim()
                    if(i in 0 until n && titre.isNotEmpty())table.add(Titre(titre,niveau,Reperes.chercher(texte,titre,debuts[i],debuts[i]+pages[i].length)))
                }catch(_:Exception){}
                if(item.hasChildren())parcourir(item,niveau+1)
            }
        }
        try{doc.documentCatalog.documentOutline?.let{parcourir(it,1)}}catch(_:Exception){table.clear()}
        val liste=etiquettes.zip(debuts)
        Resultat(texte,if(table.isNotEmpty()) Reperes(liste,table,"signets") else devinee(texte,liste))
    }

    /** Entrée d'une archive ZIP (DOCX, ODT), 10 Mo au plus ; null si absente. */
    private fun entree(bytes:ByteArray,nom:String):ByteArray? = ZipInputStream(bytes.inputStream()).use{zip->
        while(true){
            val e=zip.nextEntry?:break
            if(e.name==nom){
                val b=java.io.ByteArrayOutputStream();val part=ByteArray(8192)
                while(true){val k=zip.read(part);if(k<0)break;if(b.size()+k>10*1024*1024)throw IllegalArgumentException("Document trop long");b.write(part,0,k)}
                return@use b.toByteArray()
            }
        }
        null
    }
    private fun lecteur(xml:ByteArray):XmlPullParser {
        val p=android.util.Xml.newPullParser()
        p.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES,true)   // noms sans préfixe : « p » et non « w:p »
        p.setInput(xml.inputStream(),"UTF-8")
        return p
    }
    private const val W="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    private val styleTitre=Regex("(?i)^(?:heading|titre|title)\\s*(\\d?)$")

    /** styleId -> niveau de titre d'après styles.xml (niveau de plan, ou nom « heading N » / « titre N »),
     *  comme docx_styles() de windows/documents.py : les styles personnalisés de titre sont reconnus. */
    private fun stylesDocx(bytes:ByteArray):Map<String,Int> {
        val niveaux=HashMap<String,Int>()
        val xml=try{entree(bytes,"word/styles.xml")}catch(_:Exception){null}?:return niveaux
        try{
            val p=lecteur(xml); var id:String?=null; var plan:Int?=null; var nom:Int?=null
            while(p.eventType!=XmlPullParser.END_DOCUMENT){
                if(p.eventType==XmlPullParser.START_TAG) when(p.name){
                    "style"->{id=p.getAttributeValue(W,"styleId");plan=null;nom=null}
                    "outlineLvl"->p.getAttributeValue(W,"val")?.toIntOrNull()?.let{if(it in 0..8)plan=it+1}
                    "name"->Regex("(?i)^(?:heading|titre)\\s*(\\d)$").find(p.getAttributeValue(W,"val")?:"")?.let{nom=it.groupValues[1].toInt()}
                }
                if(p.eventType==XmlPullParser.END_TAG && p.name=="style"){val n=plan?:nom;val s=id;if(s!=null && n!=null)niveaux[s]=n;id=null}
                p.next()
            }
        }catch(_:Exception){}
        return niveaux
    }

    private fun xml(bytes:ByteArray,nom:String,odt:Boolean):Resultat {
        val xml=entree(bytes,nom)?:throw IllegalArgumentException("Texte du document introuvable")
        val styles=if(odt) emptyMap() else stylesDocx(bytes)
        val p=lecteur(xml)
        val t="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        val out=StringBuilder(); val table=ArrayList<Titre>(); val pages=arrayListOf(0)
        var debutPara=0; var niveau=0; var saut=false
        var dansTabs=false
        var dansT=false   // DOCX : seul le texte des éléments w:t est du texte (pas les codes de champ, le texte supprimé, les retours de mise en forme)
        while(p.eventType!=XmlPullParser.END_DOCUMENT){
            when(p.eventType){
                XmlPullParser.TEXT->if(odt || dansT)out.append(p.text)
                XmlPullParser.START_TAG->when(p.name){
                    "p","h"->{
                        debutPara=out.length;niveau=0
                        if(odt){
                            if(saut && out.isNotEmpty())pages.add(out.length);saut=false
                            if(p.name=="h")niveau=p.getAttributeValue(t,"outline-level")?.toIntOrNull()?:1
                        }
                    }
                    "t"->if(!odt && p.namespace==W)dansT=true
                    "pStyle"->if(!odt){
                        val sid=p.getAttributeValue(W,"val")?:""
                        val m=styleTitre.find(sid)
                        if(m!=null)niveau=m.groupValues[1].toIntOrNull()?:1 else styles[sid]?.let{niveau=it}
                    }
                    "outlineLvl"->if(!odt && niveau==0)p.getAttributeValue(W,"val")?.toIntOrNull()?.let{if(it in 0..8)niveau=it+1}
                    "pageBreakBefore"->if(!odt && debutPara>0)pages.add(debutPara)
                    "lastRenderedPageBreak"->if(!odt && out.isNotEmpty())pages.add(out.length)
                    "br","cr"->if(!odt){out.append('\n');if(p.getAttributeValue(W,"type")=="page")pages.add(out.length)}
                    "tabs"->dansTabs=true
                    "tab"->if(!odt && !dansTabs)out.append('\t')   // w:tabs/w:tab = taquets de tabulation, pas du texte
                    "soft-page-break"->if(odt)saut=true
                }
                XmlPullParser.END_TAG->{
                    if(p.name=="t")dansT=false
                    if(p.name=="tabs")dansTabs=false
                    if(p.name in listOf("p","h","tr")){
                        if(p.name!="tr" && niveau>0){
                            val s=out.substring(debutPara)
                            if(s.isNotBlank())table.add(Titre(s.trim(),niveau,debutPara+(s.length-s.trimStart().length)))
                        }
                        niveau=0;out.append('\n')
                    }
                }
            }
            p.next()
        }
        val texte=out.toString()
        val lp=pages.filter{it<maxOf(1,texte.length)}.distinct().sorted()
        val listePages=if(lp.size>=2) lp.mapIndexed{i,x->(i+1).toString() to x} else emptyList()
        return Resultat(texte,if(table.isNotEmpty()) Reperes(listePages,table,"titres") else devinee(texte,listePages))
    }
}
