package fr.lecteurgilles.android

import android.widget.Button
import android.widget.EditText
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.PDPage
import com.tom_roush.pdfbox.pdmodel.PDPageContentStream
import com.tom_roush.pdfbox.pdmodel.common.PDPageLabelRange
import com.tom_roush.pdfbox.pdmodel.common.PDPageLabels
import com.tom_roush.pdfbox.pdmodel.font.PDType1Font
import com.tom_roush.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline
import com.tom_roush.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Version 1.6 : pages et table des matières à l'ouverture, puis « Aller à… » et lecture. */
@RunWith(AndroidJUnit4::class)
class DocumentsTest {
    private val corps="Le village se reveilla sous la neige. Marc ouvrit la porte."
    private fun pdfExemple():ByteArray {
        PDFBoxResourceLoader.init(InstrumentationRegistry.getInstrumentation().targetContext)
        val contenu=listOf(listOf("Avant-propos",corps),listOf("Table des matieres"),listOf("Chapitre 1 La neige",corps),
            listOf(corps,"La cabane",corps),listOf("Chapitre 2 Le lac",corps),listOf("Fin du livre."))
        PDDocument().use{doc->
            for(lignes in contenu){
                val page=PDPage();doc.addPage(page)
                PDPageContentStream(doc,page).use{cs->
                    cs.beginText();cs.setFont(PDType1Font.HELVETICA,12f);cs.newLineAtOffset(50f,700f)
                    for(l in lignes){cs.showText(l);cs.newLineAtOffset(0f,-20f)}
                    cs.endText()
                }
            }
            val plan=PDDocumentOutline();doc.documentCatalog.documentOutline=plan
            val ch1=PDOutlineItem().apply{title="Chapitre 1 La neige";setDestination(doc.getPage(2))};plan.addLast(ch1)
            ch1.addLast(PDOutlineItem().apply{title="La cabane";setDestination(doc.getPage(3))})
            plan.addLast(PDOutlineItem().apply{title="Chapitre 2 Le lac";setDestination(doc.getPage(4))})
            val labels=PDPageLabels(doc)
            labels.setLabelItem(0,PDPageLabelRange().apply{style=PDPageLabelRange.STYLE_ROMAN_LOWER})
            labels.setLabelItem(2,PDPageLabelRange().apply{style=PDPageLabelRange.STYLE_DECIMAL;start=1})
            doc.documentCatalog.pageLabels=labels
            return ByteArrayOutputStream().also{doc.save(it)}.toByteArray()
        }
    }
    @Test fun pdfPagesEtSignets() {
        val r=Documents.extraire(pdfExemple(),"application/pdf")
        assertEquals(listOf("i","ii","1","2","3","4"),r.reperes.pages.map{it.first})
        assertEquals("signets",r.reperes.source)
        assertEquals(listOf("Chapitre 1 La neige" to 1,"La cabane" to 2,"Chapitre 2 Le lac" to 1),r.reperes.table.map{it.titre to it.niveau})
        for(t in r.reperes.table)assertTrue("${t.titre} mal placé",r.texte.startsWith(t.titre,t.debut))
        assertTrue(r.texte.startsWith("Chapitre 1",r.reperes.debutPage("1")))
        assertTrue(r.reperes.ouSuisJe(r.reperes.table[2].debut+3,r.texte.length).startsWith("page 3 (5 sur 6)"))
    }
    @Test fun docxTitresEtSautDePage() {
        val w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        fun para(texte:String,style:String?=null,saut:Boolean=false)="<w:p>"+(style?.let{"<w:pPr><w:pStyle w:val=\"$it\"/></w:pPr>"}?:"")+"<w:r><w:t>$texte</w:t>"+(if(saut) "<w:br w:type=\"page\"/>" else "")+"</w:r></w:p>"
        val xml="<?xml version=\"1.0\" encoding=\"UTF-8\"?><w:document xmlns:w=\"$w\"><w:body>"+para("Première partie","Titre1")+para(corps)+para("Le départ","Heading2")+para(corps,saut=true)+para("Deuxième partie","Heading1")+para("Fin.")+"</w:body></w:document>"
        val zip=ByteArrayOutputStream().also{b->ZipOutputStream(b).use{z->z.putNextEntry(ZipEntry("word/document.xml"));z.write(xml.toByteArray());z.closeEntry()}}.toByteArray()
        val r=Documents.extraire(zip,"application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assertEquals(listOf("Première partie" to 1,"Le départ" to 2,"Deuxième partie" to 1),r.reperes.table.map{it.titre to it.niveau})
        assertTrue("paragraphes séparés",r.texte.startsWith("Première partie\n"))
        assertEquals(listOf("1","2"),r.reperes.pages.map{it.first})
        for(t in r.reperes.table)assertTrue(r.texte.startsWith(t.titre,t.debut))
    }
    @Test fun allerAUnChapitreEtLire() {
        val texte="Introduction\nUn court texte pour commencer.\nChapitre 1 Le départ\nGilles lit le premier chapitre.\nChapitre 2 Le retour\nGilles lit maintenant le second chapitre, puis il s'arrête."
        ActivityScenario.launch(MainActivity::class.java).use{s->
            var cible=-1
            s.onActivity{a->
                (a.javaClass.getDeclaredField("editor").apply{isAccessible=true}.get(a) as EditText).setText(texte)
                val r=MainActivity::class.java.getDeclaredMethod("reperesActuels").apply{isAccessible=true}.invoke(a) as Reperes
                assertEquals(listOf("Introduction","Chapitre 1 Le départ","Chapitre 2 Le retour"),r.table.map{it.titre})
                cible=r.table[2].debut
                MainActivity::class.java.getDeclaredMethod("allerA",Int::class.javaPrimitiveType).apply{isAccessible=true}.invoke(a,cible)
                assertTrue("la lecture démarre",a.javaClass.getDeclaredField("active").apply{isAccessible=true}.get(a) as Boolean)
            }
            val fin=System.currentTimeMillis()+180000; var mot=-1
            while(System.currentTimeMillis()<fin && mot<0){Thread.sleep(100);s.onActivity{a->mot=a.javaClass.getDeclaredField("highlightStart").apply{isAccessible=true}.get(a) as Int}}
            assertEquals("la lecture commence au chapitre choisi",cible,mot)
            s.onActivity{a->
                val st=(a.javaClass.getDeclaredField("status").apply{isAccessible=true}.get(a) as android.widget.TextView).text.toString()
                assertTrue("chapitre affiché : $st",st.contains("Chapitre 2 Le retour"))
                MainActivity::class.java.getDeclaredMethod("stopReading").apply{isAccessible=true}.invoke(a)
            }
        }
    }
}
