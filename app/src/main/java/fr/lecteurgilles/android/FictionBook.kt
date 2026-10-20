package fr.lecteurgilles.android

import android.util.Xml
import org.xmlpull.v1.XmlPullParser
import java.util.zip.ZipInputStream

/** FictionBook: body text only, including notes; binary covers and metadata are excluded. */
object FictionBook {
    fun read(input:ByteArray,zipped:Boolean):Documents.Resultat {
        val bytes=if(zipped)ZipInputStream(input.inputStream()).use{zip->
            var book:ByteArray?=null;var count=0;var total=0L
            while(true){val e=zip.nextEntry?:break;require(++count<=1000){"Archive contenant trop de fichiers"}
                val output=java.io.ByteArrayOutputStream();val buf=ByteArray(8192)
                while(true){val n=zip.read(buf);if(n<0)break;total+=n;require(total<=50L*1024*1024){"Archive trop volumineuse"};if(e.name.endsWith(".fb2",true))output.write(buf,0,n)}
                if(e.name.endsWith(".fb2",true)){require(book==null){"Archive contenant plusieurs livres : ouvrez un FB2 à la fois"};book=output.toByteArray()}
            };book?:throw IllegalArgumentException("Aucun fichier FB2 dans cette archive")
        }else input
        val parser=Xml.newPullParser();parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES,true);parser.setInput(bytes.inputStream(),null)
        val text=StringBuilder();val table=ArrayList<Titre>();var body=0;var section=0;var titleStart=-1;var root=false
        val blocks=setOf("p","v","subtitle","text-author","empty-line")
        fun line(){if(text.isNotEmpty() && text.last()!='\n')text.append('\n')}
        while(parser.eventType!=XmlPullParser.END_DOCUMENT){
            val name=parser.name.orEmpty()
            when(parser.eventType){
                XmlPullParser.START_TAG->{
                    if(parser.depth==1){require(name=="FictionBook"){"Ce fichier n'est pas un FictionBook"};root=true}
                    if(name=="body")body++
                    if(body>0){if(name=="section")section++;if(name in blocks || name=="title")line();if(name=="title")titleStart=text.length}
                }
                XmlPullParser.TEXT->if(body>0 && !parser.isWhitespace)text.append(parser.text)
                XmlPullParser.END_TAG->if(body>0){
                    if(name=="title" && titleStart>=0){val title=text.substring(titleStart).trim();if(title.isNotEmpty())table.add(Titre(title,section.coerceAtLeast(1),titleStart));titleStart=-1}
                    if(name in blocks || name in setOf("title","section","body"))line()
                    if(name=="section")section--;if(name=="body")body--
                }
            };require(text.length<=10_000_000){"Texte trop volumineux"};parser.next()
        }
        require(root && text.isNotBlank()){"Aucun texte dans ce FictionBook"}
        val t=text.toString().trimEnd()
        return if(table.isEmpty())Documents.texte(t,false) else Documents.Resultat(t,Reperes(emptyList(),table,"titres"))
    }
}
