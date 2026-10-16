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
    @Test fun gillesAndPauseResume() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { a ->
                (field(a,"editor") as EditText).setText("Bonjour. Je suis Gilles. Ceci est un test de lecture, de pause et de reprise. ".repeat(8))
                (field(a,"play") as Button).performClick()
            }
            val deadline=System.currentTimeMillis()+180000
            var position=0
            while(System.currentTimeMillis()<deadline && position<3000) {
                Thread.sleep(200)
                scenario.onActivity { a ->position=(field(a,"track") as? AudioTrack)?.playbackHeadPosition?:0 }
            }
            assertTrue("La voix Gilles n'a pas produit de lecture",position>=3000)
            scenario.onActivity { a -> (field(a,"pause") as Button).performClick() }
            Thread.sleep(250)
            var first=0
            scenario.onActivity { a ->
                assertTrue(field(a,"paused") as Boolean)
                assertEquals("▶ Continuer",(field(a,"play") as Button).text.toString())
                first=(field(a,"track") as AudioTrack).playbackHeadPosition
            }
            Thread.sleep(500)
            scenario.onActivity { a ->assertEquals("La pause avance",first,(field(a,"track") as AudioTrack).playbackHeadPosition);(field(a,"play") as Button).performClick() }
            Thread.sleep(500)
            scenario.onActivity { a ->
                assertTrue("La reprise n'avance pas",(field(a,"track") as AudioTrack).playbackHeadPosition>first)
                MainActivity::class.java.getDeclaredMethod("stopReading").apply{isAccessible=true}.invoke(a)
                assertFalse(field(a,"active") as Boolean)
                assertTrue((field(a,"editor") as EditText).isEnabled)
            }
        }
    }
}
