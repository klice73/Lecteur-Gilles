package fr.lecteurgilles.android

import android.media.AudioTrack
import android.widget.Button
import android.widget.EditText
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ReaderTest {
    private fun field(a:MainActivity,name:String):Any? = MainActivity::class.java.getDeclaredField(name).apply{isAccessible=true}.get(a)
    @Test fun gillesAndPauseResume() = verifyReading(false)
    @Test fun cursorAndPauseResume() = verifyReading(true)
    private fun verifyReading(fromCursor:Boolean) {
        val prefix="TABLE DES MATIÈRES. Passage à ignorer.\n"
        val body="Bonjour. Je suis Gilles. Ceci est un test de lecture, de pause et de reprise. ".repeat(8)
        val original=prefix+body
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { a ->
                val editor=field(a,"editor") as EditText
                editor.setText(original)
                editor.setSelection(prefix.length,prefix.length+7)
                (field(a,if(fromCursor) "playFromCursor" else "play") as Button).performClick()
                assertEquals(original,editor.text.toString())
            }
            val deadline=System.currentTimeMillis()+180000
            var position=0
            while(System.currentTimeMillis()<deadline && position<3000) {
                Thread.sleep(200)
                scenario.onActivity { a ->position=(field(a,"track") as? AudioTrack)?.playbackHeadPosition?:0 }
            }
            assertTrue("La voix Gilles n'a pas produit de lecture",position>=3000)
            // Version 1.5 : le surlignage avance mot à mot pendant la lecture
            val vus=HashSet<Int>()
            val fin=System.currentTimeMillis()+4000
            while(System.currentTimeMillis()<fin){Thread.sleep(60);scenario.onActivity{a->vus.add(field(a,"highlightStart") as Int)}}
            vus.remove(-1)
            assertTrue("Le surlignage ne suit pas mot à mot : ${vus.size} positions",vus.size>=4)
            scenario.onActivity { a -> (field(a,"pause") as Button).performClick() }
            Thread.sleep(250)
            var first=0
            var marked=-1
            scenario.onActivity { a ->
                assertTrue(field(a,"paused") as Boolean)
                assertEquals("▶ Continuer",(field(a,"play") as Button).text.toString())
                first=(field(a,"track") as AudioTrack).playbackHeadPosition
                marked=field(a,"highlightStart") as Int
                val pos=a.getPreferences(android.content.Context.MODE_PRIVATE).getInt("position",-1)
                assertTrue("Position non enregistrée à la pause : $pos",pos>=if(fromCursor) prefix.length else 0)
                assertTrue("Le passage lu n’est pas surligné",marked>=if(fromCursor) prefix.length else 0)
                assertEquals(original,(field(a,"editor") as EditText).text.toString())
            }
            val instrumentation=androidx.test.platform.app.InstrumentationRegistry.getInstrumentation()
            val image=instrumentation.uiAutomation.takeScreenshot()
            val dir=java.io.File(instrumentation.targetContext.getExternalFilesDir(null),"screenshots").apply{mkdirs()}
            java.io.File(dir,if(fromCursor) "lecture-curseur.png" else "lecture-complete.png").outputStream().use{image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,it)}
            image.recycle()
            Thread.sleep(500)
            scenario.onActivity { a ->assertEquals("Le surlignage bouge pendant la pause",marked,field(a,"highlightStart") as Int);assertEquals("La pause avance",first,(field(a,"track") as AudioTrack).playbackHeadPosition);(field(a,"play") as Button).performClick() }
            Thread.sleep(500)
            scenario.onActivity { a ->
                assertTrue("La reprise n'avance pas",(field(a,"track") as AudioTrack).playbackHeadPosition>first)
                MainActivity::class.java.getDeclaredMethod("stopReading").apply{isAccessible=true}.invoke(a)
                assertFalse(field(a,"active") as Boolean)
                assertEquals(-1,field(a,"highlightStart") as Int)
                val editor=field(a,"editor") as EditText
                assertTrue(editor.isEnabled)
                assertTrue("Reprendre inactif après l'arrêt",(field(a,"resume") as Button).isEnabled)
                assertEquals(original,editor.text.toString())
                editor.setSelection(editor.text.length)
                (field(a,"playFromCursor") as Button).performClick()
                assertFalse(field(a,"active") as Boolean)
                assertEquals(-1,field(a,"highlightStart") as Int)
                assertTrue((field(a,"status") as android.widget.TextView).text.contains("fin du texte"))
            }
        }
    }
    @Test fun positionKeptAfterClosing() {
        val original="Premier paragraphe à ignorer.\n"+"Gilles lit ce texte, phrase après phrase, pour vérifier la reprise. ".repeat(6)
        var avant=-1
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { a -> val e=field(a,"editor") as EditText; e.setText(original); e.setSelection(original.indexOf("Gilles")); (field(a,"playFromCursor") as Button).performClick() }
            val deadline=System.currentTimeMillis()+180000
            var position=0
            while(System.currentTimeMillis()<deadline && position<20000){Thread.sleep(200);scenario.onActivity{a->position=(field(a,"track") as? AudioTrack)?.playbackHeadPosition?:0}}
            assertTrue("Pas de lecture",position>=20000)
            scenario.onActivity { a -> (field(a,"pause") as Button).performClick(); avant=a.getPreferences(android.content.Context.MODE_PRIVATE).getInt("position",-1) }
            assertTrue("Position avant fermeture : $avant",avant>=original.indexOf("Gilles"))
        }
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { a ->
                val e=field(a,"editor") as EditText
                assertEquals("Texte non retrouvé après fermeture",original,e.text.toString())
                assertEquals("Curseur non replacé",avant,e.selectionStart)
                assertTrue("Reprendre inactif après réouverture",(field(a,"resume") as Button).isEnabled)
                (field(a,"resume") as Button).performClick()
                assertTrue("Reprendre ne relance pas la lecture",field(a,"active") as Boolean)
            }
            // la lecture reprise commence à la phrase enregistrée, pas au début du texte
            val limite=System.currentTimeMillis()+180000
            var premier=-1
            while(System.currentTimeMillis()<limite && premier<0){Thread.sleep(100);scenario.onActivity{a->premier=field(a,"highlightStart") as Int}}
            assertEquals("La reprise doit commencer exactement à la phrase enregistrée",avant,premier)
            scenario.onActivity { a -> MainActivity::class.java.getDeclaredMethod("stopReading").apply{isAccessible=true}.invoke(a) }
        }
    }
}
