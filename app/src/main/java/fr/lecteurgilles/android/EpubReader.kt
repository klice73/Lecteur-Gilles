package fr.lecteurgilles.android

import android.text.Html
import android.util.Xml
import org.xmlpull.v1.XmlPullParser
import java.io.File
import java.io.ByteArrayOutputStream
import java.net.URI
import java.util.zip.ZipFile

/** Reads the EPUB spine locally; never fetches URLs or executes document scripts. */
object EpubReader {
    private fun read(zip:ZipFile,name:String,limit:Int=10*1024*1024):ByteArray {
        val entry=zip.getEntry(name)?:throw IllegalArgumentException("Élément EPUB manquant : $name")
        require(entry.size<=limit){"Chapitre EPUB trop volumineux"}
        return zip.getInputStream(entry).use { input ->
            val out=ByteArrayOutputStream();val buffer=ByteArray(8192)
            while(true){val n=input.read(buffer);if(n<0)break;require(out.size()+n<=limit){"Chapitre EPUB trop volumineux"};out.write(buffer,0,n)}
            out.toByteArray()
        }
    }
    private fun decode(bytes:ByteArray):String {
        return if(bytes.size>=2 && ((bytes[0]==0xff.toByte() && bytes[1]==0xfe.toByte()) || (bytes[0]==0xfe.toByte() && bytes[1]==0xff.toByte())))bytes.toString(Charsets.UTF_16) else bytes.toString(Charsets.UTF_8).removePrefix("\uFEFF")
    }
    private fun tags(bytes:ByteArray,visit:(XmlPullParser)->Unit) {
        val parser=Xml.newPullParser()
        parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES,true)
        parser.setInput(bytes.inputStream(),null)
        while(parser.eventType!=XmlPullParser.END_DOCUMENT){if(parser.eventType==XmlPullParser.START_TAG)visit(parser);parser.next()}
    }
    private fun resolve(base:String,href:String):String {
        val uri=URI(href)
        require(!uri.isAbsolute && uri.rawAuthority==null){"Référence EPUB externe non prise en charge"}
        val path=uri.path?:throw IllegalArgumentException("Chemin EPUB invalide")
        require(!path.startsWith('/')){"Chemin EPUB absolu non pris en charge"}
        val parts=ArrayList<String>()
        for(part in (base+path).split('/')) when(part){"","."->Unit;".."->{require(parts.isNotEmpty()){"Chemin EPUB invalide"};parts.removeAt(parts.lastIndex)};else->parts.add(part)}
        return parts.joinToString("/")
    }
    fun read(file:File):String = ZipFile(file).use { zip ->
        require(zip.size()<=10000){"EPUB contenant trop de fichiers"}
        var total=0L
        val entries=zip.entries()
        while(entries.hasMoreElements()){val size=entries.nextElement().size;require(size>=0){"Taille EPUB inconnue"};total+=size;require(total<=250L*1024*1024){"EPUB trop volumineux après décompression (250 Mo)"}}
        var opf:String?=null
        tags(read(zip,"META-INF/container.xml",1024*1024)){p->if(p.name=="rootfile" && opf==null)opf=p.getAttributeValue(null,"full-path")}
        val packageName=resolve("",opf?:throw IllegalArgumentException("Structure EPUB introuvable"))
        val base=packageName.substringBeforeLast('/',"").let{if(it.isEmpty()) "" else "$it/"}
        val manifest=HashMap<String,Pair<String,String>>()
        val spine=ArrayList<String>()
        tags(read(zip,packageName)){p->
            if(p.name=="item"){
                val id=p.getAttributeValue(null,"id");val href=p.getAttributeValue(null,"href")
                if(id!=null && href!=null)manifest[id]=Pair(resolve(base,href),p.getAttributeValue(null,"media-type").orEmpty())
            }
            if(p.name=="itemref" && p.getAttributeValue(null,"linear")!="no")p.getAttributeValue(null,"idref")?.let{spine.add(it)}
        }
        require(spine.isNotEmpty()){"Aucun chapitre dans cet EPUB"}
        val encrypted=HashSet<String>()
        if(zip.getEntry("META-INF/encryption.xml")!=null)tags(read(zip,"META-INF/encryption.xml",1024*1024)){p->if(p.name=="CipherReference")p.getAttributeValue(null,"URI")?.let{encrypted.add(resolve("",it))}}
        val output=StringBuilder()
        for(id in spine){
            val item=manifest[id]?:throw IllegalArgumentException("Chapitre EPUB inconnu : $id")
            require(item.first !in encrypted){"Le texte de cet EPUB est protégé. Utilisez une édition EPUB ou PDF sans protection."}
            require(item.second in listOf("application/xhtml+xml","text/html")){"Chapitre EPUB non textuel : ${item.second}"}
            val markup=decode(read(zip,item.first))
                .replace(Regex("(?is)<(script|style)\\b[^>]*>.*?</\\1\\s*>"),"")
            val text=Html.fromHtml(markup,Html.FROM_HTML_MODE_LEGACY).toString().trim()
            if(text.isNotEmpty()){if(output.isNotEmpty())output.append("\n\n");output.append(text)}
            require(output.length<=10_000_000){"Texte EPUB trop volumineux"}
        }
        require(output.isNotBlank()){"Aucun texte lisible dans cet EPUB"}
        output.toString()
    }
}
