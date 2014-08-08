import io
import morpheuslib2
text1 = "quas φαντασίας"
text2 = "φαντασίας quas"
text = "solutus enim corporeis nexibus, animus semper vigens motibus indefessis, ex cogitationibus subiectis et curis, quae mortalium sollicitant mentes, colligit visa nocturna, quas φαντασίας nos appellamus."
ws = morpheuslib2.WordStream.from_text("Ammianus", text, 'la',greek_mode=None,mixed=True)
for w in ws:
    print(w.word)
#sio1 = io.StringIO(text)
#sio2 = io.StringIO(text2)
#n = 0
#c = sio1.read(1)
#while c:
    #print(c)
    #n = n + 1
    #c = sio1.read(1)
print(str(n))

#c = sio2.read(1)
#n = 0

#while c:
    #print(c)
    #n = n + 1
    #c = sio2.read(1)
#print(str(n))

    