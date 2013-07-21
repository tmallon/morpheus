# coding: utf-8
import urllib.request
import urllib.error
import json
from xml.etree import ElementTree
import io
import unicodedata

def read_dict(f):
    """ Read a file of lines with key value pairs separated by whitespace into a dictionary."""
    file = open(f, 'r')
    lns = [l.rstrip() for l in file.readlines() if len(l) > 0 and l[0] != '#']
    file.close()
    d = {}
    for ln in lns:
            
        l, p = ln.split()
        d[l] = p
    return d
        

def safe_text (s):
        """Return s quoted for Prolog. """
        if s is None:
            
            return 'nothing'.center(9, "'")
        else:
            return s.center(len(s) + 2, "'")

def uncap(s):
    return s[0].lower() + s[1:] 

def isect(l1, l2):
    return [x for x in l1 if x in l2]

def comp(l1, l2):
    return [x for x in l1 if x not in l2]

class WordStream:
    """Reads words from a text file or string, keeping track of word, clause, and sentence position.
    i: word ordinal (zero-based)
    c: clause ordinal (zero based)
    s: sentence ordinal (zero based)
    text: an object that accepts:
        read(1) and returns the next character, or '' when at end of stream
        close()
    lang: 'greek' or 'la'
    label: a scope for i, c, and s.
        
     """
    def __init__ (self, label, text, lang):
        """Set up an accumulator, read language specific configuration, and initialize read character count. """
        self.i = 0
        self.c = 0
        self.s = 0
        
        self.text = text
        self.lang = lang
        self.label = label
        
        self.acc = io.StringIO(' ' * 20)
        self.read_info(lang)
        self.bct = 0

    def __iter__ (self):
        """ """
        return self

    def __str__(self):
        return str(self.text)
	
    def read_info(self, lang):
        """ Read language specific information about how text is punctuated,
            what strings are abbreviations.
        """
        try:
            info = open('info.' + lang, 'r')
            ls = [l.rstrip() for l in info.readlines() if len(l) > 0 and l[0] != '#']
            info.close()
        except IOError:
            pass
        if ls[0] == 'NONE':
            self.seps = ''
        else:
            self.seps = ls[0]
        if ls[1] == 'NONE':
            self.terms = ''
        else:
            self.terms = ls[1]
        if ls[2] == 'NONE':
            self.abbr_term = ''
        else:
            self.abbr_term = ls[2]
        self.abbrs = ls[3:]    
        
        
    def count (self):
        """Word count so far. """
        return self.i
    
    
    def abbr_check(self, s):
        """ Is s in the list of abbreviations? """
        return s in self.abbrs
    
    def close(self):
        """ Close the underlying stream. """
        self.text.close()


    def __next__(self):
        """ Read the next word from the stream, return it. """
        while True:
            c = self.text.read(1)
            if c == '':
                if self.bct > 0:
                    return self.conv_acc()
                    
                else:
                    raise StopIteration
            elif c == ' ':
                if self.bct > 0:
                    return self.conv_acc()
                else:
                    pass
            elif c in self.terms + self.seps:
                self.acc.write(c)
                return self.conv_acc()
                
            else:
                self.acc.write(c)
                self.bct = self.bct + 1
                    
            
    def conv_acc(self):
        """ Convert the accumulator into a string for return. Do location accounting."""
        s = self.acc.getvalue().rstrip()
        self.acc = io.StringIO(' ' * 20)
        self.bct = 0
        s = s.strip("’" + '‘')
        t = s[-1]
        u = s.rstrip(self.seps + self.terms)
        if self.lang == 'greek':
            u = u.lower()
        else:
            pass
        a = Word(self.label, u, self.lang, self.i, self.c, self.s)
           
        if t in self.seps + self.terms:
            self.c = self.c + 1
        if t in self.terms and not self.abbr_check(u + self.abbr_term):
            self.s = self.s + 1
        self.i = self.i + 1
        return a

    
        


class Word:
    """One word, with its label, language and position information. """
    def __init__ (self, label, word, lang, w, c, s):
        """ """
        self.label = label
        self.word = word
        self.lang = lang
        self.w = w
        self.c = c
        self.s = s
        
    def loc_str (self):
        """Return the word's position information in a comma separated string. """
        return ','.join([self.label.center(len(self.label) + 2, "'"), str(self.w), str(self.c), str(self.s)])

    def __str__(self):
        return self.word + ' (' + self.lang +') word no. ' + str(self.w) + ' in ' + self.label.center(len(self.label) + 2, "'") 

class MorpheusUrl:
    """Constructs a url for fetching analyses from Morpheus service. """
    def __init__ (self, word):
        """Make the url string. """
        if word.lang == 'greek':
            w = BetaCode.cleanse(word.word)
        else:
            w = word.word
        self.url = "http://www.perseus.tufts.edu/hopper/xmlmorph?lang=" + word.lang + "&lookup=" + w
        self.word = word
        
    def fetch (self):
        """Fetch the analyses xml document, return the Analyses object constructed from it. """
        response = urllib.request.urlopen(self.url)
        return Analyses(response.read(), self.word)

    def __str__(self):
        """ Return the url. """
        return self.url
    
class Latin:
    """Does nothing now but hold dictionaries to fix Latin pronouns with person information. """
    prons = None
    
    @classmethod    
    def person(cls, lemma):
        if cls.prons is None:
            cls.prons = read_dict('prons.la')
        else:
            pass
        return cls.prons[lemma]
    
    


    
class BetaCode:
    """ A place to hang some functions to deal with Beta Code."""
    def cleanse(word):
        """ Remove Beta Code (Perseus lower case) diacritics for submission to Morpheus."""
        return ''.join([c for c in word if unicodedata.category(c) == 'Ll'])
    
    def fix_grave(word):
        """ Return word with grave changed to acute.Dictionary form always has acute."""
        return word.replace('\\', '/')

    def fix_2nd_acute(word):
        """ Remove word without a second acute induced by an enclitic in the text, but not found in the dictionary form. """
        n = word.count('/') + word.count('=')
        if n > 1:
            i = word.rfind('/')
            return word[:i] + word[(i + 1):]
        else:
            
            return word
    
    def uncap(word):
        """ Uncapitalizes a Beta Code string. """
        if word[0] == '*':
            b = io.StringIO('  ')
            i = 1
            c = word[i]
            while not c.isalpha():
                b.write(c)
                i = i + 1
                c = word[i]
            return word[i] + b.getvalue().rstrip() + word[(i + 1):]    
            
        else:
            return word
        
class Converter:
    """ Converter for Morpheus Greek form elements to Latin - all lower case in Greek to all lower case in Latin, no initial cap treatment."""
    conv = None
    @classmethod
    def convert(cls,word):
        if cls.conv is None:
            greek_lc = (''.join([chr(i) for i in range(0x3B1, 0x03CA)])) + chr(0x03DD)
            greek_diac = chr(0x0301) + chr(0x0300) + chr(0x0314) +chr(0x0313) + chr(0x0342) + chr(0x0308) + chr(0x0345) + chr(0x1fbd)
            greek = greek_lc + greek_diac
            gamma_lc = 'abgdezhqiklmncoprsstufxywv'
            
            gamma_diac = "/\()=+|'"
            gamma = gamma_lc + gamma_diac
            cls.conv = str.maketrans(greek, gamma)
        else:
            pass
        return (unicodedata.normalize('NFD', word)).translate(Converter.conv)
            
class Analyses:
    """The set of analyses returned (i.e, an interface to an XML document.) """
    def __init__ (self, text, word):
        """ """
        self.text = text
        self.root = ElementTree.fromstring(text)
        self.i = 0
        self.els = self.root.findall('analysis')
        self.word = word
        self.retct = 0
        self.uq = Unique()
        self.non_ret = []
    def __iter__(self):
        return self

    def count(self):
        """ Number of analysis elements in the document. """
        return len(self.els)

    
    
    def retain(self, a):
        if a.backcheck():
            return self.uq.test(a)
        else:
            return False
        
    def __next__(self):
        """ Return the analysis elements converted into objects. """  
        if self.i >= self.count():
            raise StopIteration
        else:
            a = Analysis(self.els[self.i], self.word)
            self.i = self.i + 1
            if self.retain(a):
                self.retct = self.retct + 1
                
                return a
            else:
                self.non_ret.append(a)
                return self.__next__()

    def __str__(self):
        return '\n'.join([a.__str__() for a in self])
	
class Analysis:
    """Interface to on <analysis> element. Does the work of fixing and converting analyses. """
    
    # Core features are those defined for all parts of speech.
    core_features = ['form', 'lemma', 'expandedForm', 'pos', 'lang','dialect', 'feature']
    
    
    
    def __init__ (self, elem, word):
        """Initializes the analysis element and word, and fixes it. """
        self.pron_fix_err = False
        self.elem = elem
        self.word = word
        #Subtle order issue here. Lemma has to be fixed before pronoun fix.
        #Lookup of suffixed pronoun lemmas will fail. 
        self.fix_lemma()
        self.fix_lang()
        self.fix_bad_mood()
        self.fix_pron()
        self.fix_part()

        
        
    def __str__(self):
        return ' '.join([t.tag + ':' + t.text for t in self.elem if t.text != None])

    def noncore_features(self):
        """ Return those features specific to the part of speech. """
        return [x.tag for x in self.elem if x.tag not in Analysis.core_features]
    
    def __eq__(self, other):
        if self.pos() == other.pos() and self.lemma() == other.lemma():
            z = self.noncore_features()
            return all([self.value(f) == other.value(f) for f in z])
            
        else:
            return False
        
    def __hash__(self):
        return hash((self.lemma(), self.pos()))
    
                    
    def value(self, feature):
        """ Return the feature's value, e.g. 'noun' for 'pos'. """
        if self.elem.find(feature) is None:
            print(feature + ' not found.')
            return None
        else:
            return self.elem.find(feature).text

    

    def pos (self):
        """Return the part of speech. """
        return self.elem.find('pos').text

    def lemma(self):
        """Return the lemma, i.e. dictionary headword to which the form is assigned. """
        return self.elem.find('lemma').text

    def form(self):
        """ Return the form, generally equals the form submitted for Latin, not always (usually?) for Greek. """
        return self.elem.find('form').text
    
    def fix(self, feat, text):
        """ Set the feature's value to text. """
        el = self.elem.find(feat)
        if el == None:
            pass
        else:
            el.text = text

    def fix_lemma(self):
        """ Fix the lemma, which sometimes has a numerical suffix, by discarding the trailing digits."""
        self.fix('lemma', self.lemma().rstrip('0123456789'))

    
    
    def ret_lang(self):
        """ Return the language name returned by Morpheus as an attribute of the form tag."""
        return self.elem.find('form').attrib.get('lang')

    def fix_lang(self):
        """Move the returned language into its own tag.""" 
        el = ElementTree.Element('lang')
        el.text = self.ret_lang()
        self.elem.append(el)
   
    def fix_bad_mood(self):
        """ Fix infelicitous moods - remove them and change the part of speech."""
        el = self.elem.find('mood')
        if el == None:
            pass
        else:
            if el.text == 'supine' or el.text == 'inf' or el.text == 'gerundive':
                self.fix('pos', el.text)
                self.elem.remove(el)
            else: 
                pass

    def tense(self):
        """Return tense value which is defined only for verbs and verbal nuns and adjectives. """
        el = self.elem.find('tense')
        if el == None:
            return 'no tense'
        else: 
            return el.text

    def fix_part(self):
        """ Fix the Latin present participle by supplying its missing its voice. """
        if self.pos() == 'part' and self.word.lang == 'la' and self.tense() == 'pres':
            el = ElementTree.Element('voice')
            el.text = 'act'
            self.elem.append(el)
        else:
            pass

    def fix_pron(self):
        """ Fix a pronoun by adding person information, so that verb agreement can be computed. Only Latin ones need this.""" 
        if self.pos() == 'pron' and self.word.lang == 'la':
            try:
                person = Latin.person(self.lemma())
            except KeyError:
                self.pron_fix_err = True
            else:
                el = ElementTree.Element('person')
                el.text = person
                self.elem.append(el)
        else:
            pass 
     	    
    
    def select_core (self, some):
        """Select a subset of the core features for output.  """
        return [safe_text(x.text) for x in self.elem if x.tag in isect(Analysis.core_features,  some)]


    def noncore(self):
        """None-core feaures are those that vary by part of speech. They are output in feature name order. """
        return [safe_text(y.text) for y in sorted([x for x in self.elem if x.tag not in Analysis.core_features], key = lambda el: el.tag)]


    def dict(self, some):
        """ A dictionary of all word information, and tag, text pairs for features in list 'some', for JSON. """
        d = {}
        d['label'] = self.word.label
        d['w'] = self.word.w
        d['c'] = self.word.c
        d['s'] = self.word.s
        d['pos'] = self.pos()
        
        co = [(y.tag, y.text) for y in self.elem if y.tag in isect(Analysis.core_features, some)]
        for (a, e) in co:
            d[a] = e
        nc = [(y.tag, y.text) for y in self.elem if y.tag not in Analysis.core_features]
        for (a, e) in nc:
            d[a] = e
        return d

    
    
    def json(self, some):
        """ Return JSON string. for features in list 'some' Features are in no guaranteed order."""
        return json.dumps(self.dict(some),ensure_ascii = False)

    
    def backcheck(self):
        """ Return whether form returned matches the form submitted. """
        w = self.word.word
        x = self.form()
        if self.word.lang == 'la':
            w = uncap(w)
            print(w + " =? " + x)
            return w == x
        elif self.word.lang == 'greek':
            x = Converter.convert(x)
            w = BetaCode.uncap(w)
            w = BetaCode.fix_grave(w)
            w = BetaCode.fix_2nd_acute(w)
            print(w + " =? " + x)
            return x == w
        else:
            return False
        
    def dud_str(self):
        w = self.word.word
        x = self.form()
        if self.word.lang == 'la':
            w = uncap(w)
            
            return w + " /= " + x
        elif self.word.lang == 'greek':
            x = Converter.convert(x)
            w = BetaCode.uncap(w)
            w = BetaCode.fix_grave(w)
            w = BetaCode.fix_2nd_acute(w)
            
            return w + " /= " + x
        else:
            return ''
    
    def prolog (self, some):
        """Return  a Prolog fact clause from the analysis, limiting the core
           features to the names in the list argument 'some'. """
        if len(self.noncore()) == 0:
            return self.pos() + '(' + self.word.loc_str() + ',' + ','.join(self.select_core(some)) + ').'
        else:
            return self.pos() + '(' + self.word.loc_str() + ',' + ','.join(self.select_core(some)) + ',' + ','.join(self.noncore()) + ').'
        
    def arity(self, some):
        """ Return the arity of the eventual Prolog fact. """
        # Value is 4 location terms + number of core terms in some + number of
        # non-core terms.
        return 4 + len(some) + len(self.noncore())

    def prolog_proc_name(self, some):
        """ Return the Prolog procedure name: functor and arity separated by /."""
        return self.pos() + '/' + str(self.arity(some))
    
class Unique:
    """ A class to test whether an object has been found already."""
    def __init__(self):
        self.set = set()
        
    def test(self, x):
        """ Return whether x has not been found so far. """
        n = len(self.set)
        self.set.add(x)
        return len(self.set) > n
    

    
        



