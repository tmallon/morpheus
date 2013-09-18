""" morpheuslib.py
    Provides classes for use by script morpheus.py, which are also usable by
    other applications that need to fetch and process Perseus morphology
    analysis XML documents.
"""
# coding: utf-8
import urllib.request
import urllib.error
import json
from xml.etree import ElementTree
import io
import unicodedata

def read_dict(f):
    """ Read a file of lines with key value pairs separated by whitespace into a
    dictionary.
    Args:
        f: The path and name of the file..
    Returns:
        The dictionary
    Raises:
        IOError if f can't be opened.
    """
    file = open(f, 'r')
    lns = [l.rstrip() for l in file.readlines() if len(l) > 0 and l[0] != '#']
    file.close()
    d = {}
    for ln in lns:
            
        l, p = ln.split()
        d[l] = p
    return d
        


        
def _str(x, none, quote = None):
    """Convert and optionally quote a value according to the rule:
       if x is  a string optionally quote it with the string quote
       if x is None replace it the value none (string) and uptionally quote it
       if x is any other type convert to string and return unquoted.
       This is essentially a value to atom converter for string and integer
       values for Prolog and Oz, for integers and strings especially.
       
    Args:
        x: any value
        none: string with which to replace x if it is None
        quote: optional string with which to enclose string values.
    Returns:
        The string suitable for interpretation as an atom.
    Raises:
        None.
    """
    if x == None:
        s = none
        
    elif type(x) == type("hi"):
        s = x
    else:
        return str(x)
    if quote == None:
        return s
    else:
        return s.center(len(s) + 2 * len(quote), quote)
    
def uncap(s):
    """ Uncapitalize a string.

    Args:
        s: string
    Returns:
        The argument with the first character's case lowered.
    Raises:
        None.

    """
    if len(s) == 0:
        return s
    else:
        return s[0].lower() + s[1:] 


class WordStream:
    """A stream of words from a text file or string.

    Attributes:
        i: ordinal of next word read word ordinal (integer zero-based)
        c: ordinal of the clause whose words are being read (integer zero based)
        s: ordinal of the sentence whose words are being read (integer zero
            based)
        text: a TextIO object
    
        lang: 'greek' or 'la'
        label: a scope for i, c, and s (string).
        
    """
    def __init__ (self, label, text, lang):
        """Set up an accumulator, read language-specific configuration,
               and initialize read character count.
        Args:       
            label: scope for the text (string)
            text: TextIO instance to read from
            lang: 'greek' or 'la'.
        Raises:
            IOError if info file couldn't be read.
        """
        self.i = 0
        self.c = 0
        self.s = 0
        
        self.text = text
        self.lang = lang
        self.label = label
        
        self.acc = io.StringIO(' ' * 20)
        self.read_info()
        self.bct = 0

    def __iter__ (self):
        """ """
        return self

    def __str__(self):
        """Return the descriptor of the stream."""
        return str(self.text)
	
    def read_info(self):
        """Read language-specific information about how text is punctuated,
           what strings are abbreviations.
        Returns:   
            No return value; side-effects only.
        Raises:
            IOError if info file can't be opened.
        """
        try:
            info = open('info.' + self.lang, 'r')
            ls = [l.rstrip() for l in info.readlines()
                  if len(l) > 0 and l[0] != '#']
            info.close()
        except IOError:
            raise
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
        self.alpha = ls[3]    
        self.abbrs = ls[4:]    
        
        
    def count (self):
        """The word count so far.

        Returns:
            the number of words in the text after the text has been
            completely read.
        """
        return self.i
    
    
    def abbr_check(self, s):
        """ Is s in the list of abbreviations?
            Returns:
                boolean.
        """
        return s in self.abbrs
    
    def close(self):
        """ Close the underlying stream.
        Effect:
            stream is closed and no longer readable.
        """
        self.text.close()


    def __next__(self):
        """ Read the next word from the stream.

        
        Returns:
            string.
        Effects:
            see conv_acc(),
        """
        while True:
            c = self.text.read(1)
            if c == '':
                if self.bct > 0:
                    return self.conv_acc()
                    
                else:
                    raise StopIteration
            elif c.isspace():
                if self.bct > 0:
                    return self.conv_acc()
                else:
                    pass
            elif c in self.terms + self.seps:
                self.acc.write(c)
                return self.conv_acc()
                
            else:
                if c in self.alpha:
                    self.acc.write(c)
                    self.bct = self.bct + 1
                else:
                    pass
                    
            
    def conv_acc(self):
        """Convert the accumulator into a string.

        
        Returns:
            the word read from the stream, stripped of punctuation.
        Effects:
            resets accumulator;
            resets bct (accumulated character count);
            updates word, clause, and sentence count variables.
        """
        s = self.acc.getvalue().rstrip()
        self.acc = io.StringIO(' ' * 20)
        self.bct = 0
        #s = s.strip("’" + '‘')
        
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
    """One word, with its label, language and position information.
    Attributes:
        label: the scope of the text, e.g. 'Hom. Od. i'.
        word: the string
        lang: 'la' or 'greek'
        w: word ordinal (integer, zero-based)
        c: clause ordinal (integer, zero-based)
        s: sentence ordinal (integer, zero-based)
        
    """
    features = ['label', 'w', 'c', 's']
    
    def __init__ (self, label, word, lang, w, c, s):
        """ Set the word's attributes, which come from the WordStream instance
            which is reading the text source.
        
        
        """
        self.label = label
        self.word = word
        self.lang = lang
        self.w = w
        self.c = c
        self.s = s
        
    def loc_str (self):
        """The word's position information in a comma separated string. """
        return (','.join([self.label.center(len(self.label) + 2, "'"),
                          str(self.w), str(self.c), str(self.s)]))

    def values(self):
        # Delete?
        """ Return a list of the word's attributes."""
        return [self.label, self.w, self.c, self.s]
    
    def __str__(self):
        """ Return a shotrter string containing just word, language,
            word position and label.
        """
        return (self.word + ' (' + self.lang +') word no. ' + str(self.w) +
                ' in ' + self.label.center(len(self.label) + 2, "'") )

class MorpheusUrl:
    """A word's URL at Perseus.
    Attributes:
        url: the Perseus url string
        word: (morpheuslib.Word) the word being looked up.
    """
    def __init__ (self, word):
        """
        Args:
            word (morpheuslib.Word): the word to look up.
        """
        # Greek word text has to be 'cleaned up' for use in the URL string.
        if word.lang == 'greek':
            w = BetaCode.cleanse(word.word)
        else:
            w = word.word
        self.url = "http://www.perseus.tufts.edu/hopper/xmlmorph?lang=" + word.lang + "&lookup=" + w
        self.word = word
        
    def fetch (self):
        """Fetch the <analyses> xml document.
        Returns:
            The Analyses object that wraps the document.
        Raises:
            urllib.error.HTTPError
            urllib.error.URLError
        """
        response = urllib.request.urlopen(self.url)
        return Analyses(response.read(), self.word)

    def __str__(self):
        """ Return the url (string). """
        return self.url
    
class Latin:
    """A class to hold info related to Latin grammar.
    Class attribute:
        prons: a dict holding pronoun lemma -> person mappings.
    """
    prons = None
    
    @classmethod    
    def person(cls, lemma):
        """Return the person of the pronoun, if known to the system.
        Args:
            lemma: (string) the dictionary lemma, e.g. 'is' for 'ea'.
        Returns:
            the person 1st/2nd/3rd, if known.
        Raises:
            KeyError, if the pronoun isn't in the dict.
            IOError, if the prons.la file can't be read.
        """    
        if cls.prons is None:
            cls.prons = read_dict('prons.la')
        else:
            pass
        return cls.prons[lemma]
    
    


    
class BetaCode:
    """ A class to hold functions to deal with Beta Code."""
    
    def cleanse(word):
        """Remove Beta Code (Perseus lower case) diacritics for submission
           to Morpheus.
        Arg:   
            word (string): a Greek word in Beta Code.
        Returns:
            word without diacritics (/\()=|).
        """
        return ''.join([c for c in word if unicodedata.category(c) == 'Ll'])
    
    def fix_grave(word):
        """ Return word (string) with grave changed to acute.Dictionary
            form always has acute.
        Arg:
           string in Beta Code.
        Returns:
           the word with grave changed to acute (\ -> /).
        """
        return word.replace('\\', '/')

    def fix_2nd_acute(word):
        """Return word (string) without a second acute induced by an enclitic
           in the text,but not found in the dictionary form.
        Arg:
            Greek word in Beta Code (string).
        Returns:
            word without a secondary acute accent (string).
        """
        n = word.count('/') + word.count('=')
        if n > 1:
            i = word.rfind('/')
            return word[:i] + word[(i + 1):]
        else:
            
            return word
    
    def uncap(word):
        """ Uncapitalize Greek word in Beta Code.
        Arg:
            string.
        Returns:
            word uncapitalized according to Beta Code convention.
        """
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
    """Converter for Morpheus Greek form elements to Latin - all lower case in
        Greek to all lower case in Latin, no initial cap treatment.
    Class attribute:
        conv: a dict to do character by character conversion.     
    """
    conv = None
    @classmethod
    def convert(cls,word):
        """ Convert word.
        Args:
            word (string): Unicode Greek word.
        Returns:
            a Beta Code string in Perseus' dialect.
        """
        if cls.conv is None:
            greek_lc = ((''.join([chr(i) for i in range(0x3B1, 0x03CA)]))
                        + chr(0x03DD))
            greek_diac = (chr(0x0301) + chr(0x0300) + chr(0x0314) +chr(0x0313)
                          + chr(0x0342) + chr(0x0308) + chr(0x0345)
                          + chr(0x1fbd))
            greek = greek_lc + greek_diac
            gamma_lc = 'abgdezhqiklmncoprsstufxywv'
            
            gamma_diac = "/\()=+|'"
            gamma = gamma_lc + gamma_diac
            cls.conv = str.maketrans(greek, gamma)
        else:
            pass
        return (unicodedata.normalize('NFD', word)).translate(Converter.conv)
            
class Analyses:
    """ A wrapper for the <analyses> XML document returned by Perseus.
        The wrapper supports iterating over the <analysis> elements it contains.
    Attributes:
        text: (string) the <analyses> XML document
        root: (ElementTree) the tree parsed from text
        i:
        els:
        retct:
        uq: morpheuslib.Unique to ensure uniqueness
        non_ret:
        
        
    """
    def __init__ (self, text, word):
        """
        Args:
            text (string): the <analyses> document.
            word (Word): the word analysed.
        Effects:
            
        """
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
        """
        Returns:
            the number of analysis elements in the document (integer).
        """
        return len(self.els)

    
    
    def retain(self, a):
        """ Should this analysis be retained?
        Args:
            a (Analysis): the Analysis to check.
        Returns:
            a boolean indicating whether the Analysis is to be retained.
        """
        if a.backcheck():
            return self.uq.test(a)
        else:
            return False
        
    def __next__(self):
        """
        Returns:
            the next <analysis> element converted into an Analysis object.
        """  
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
    """ Wrapper for an <analysis> element.
        Does the work of fixing and converting the analysis element and provides
        access to its attributes.
    Attributes:
        pron_fix_err: boolean - did a pronoun person fix fail?
        elem: (Element) the <analysis> element
        word: (Word) the analysed word.
        
    """
    
    # Core features are those defined for all parts of speech.
    core_features = ['form', 'lemma', 'expandedForm', 'pos', 'lang','dialect', 'feature']
    
    
    
    def __init__ (self, elem, word):
        """
        Initializes the analysis element and word, and fixes it.
        Args:
            elem: (Element):the <analysis> element 
            word (Word): the word analyzed.
        """
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
        self.fix_person()

    def _all_features(self):
        """
        Returns:
            names of all morphological features in the analysis as a list of
            strings.
        """    
        l = [x.tag for x in self.elem]
        l.append('lang')
        return l 

    def export(self, core_fs, word_fs):
        """Export the core features and word feature of this analysis.

        Args:
            core_fs: (list of strings) subset of core features to export
            word_fs: (list of strings) subset of word features to export.
        Returns:
            a sextuple whose elements are lists of:
            (core features, core values, noncore features, non core values,
            word features, word values).
        """
        cf = [f for f in core_fs if f in Analysis.core_features]
        cv = [self.value(f) for f in cf]
        wf = [f for f in word_fs if f in Word.features]
        wv = [getattr(self.word, f)  for f in wf]
        ncf = [f for f in self._all_features() if f not in Analysis.core_features]
        ncf.sort()
        ncv = [self.value(f) for f in ncf]
        return (cf, cv, ncf, ncv, wf, wv)
        
    def __str__(self):
        return ' '.join([t.tag + ':' + t.text for t in self.elem
                         if t.text != None])

    def noncore_features(self):
        """
        Returns:
            those features specific to the part of speech (list of strings).
        """
        return [x.tag for x in self.elem if x.tag not in Analysis.core_features]
    
    def __eq__(self, other):
        # The idea here is that checking non-core features makes an equality
        # test of the form() property redundant.
        if self.pos() == other.pos() and self.lemma() == other.lemma():
            z = self.noncore_features()
            return all([self.value(f) == other.value(f) for f in z])
            
        else:
            return False
        
    def __hash__(self):
        return hash((self.lemma(), self.pos()))
    
                    
    def value(self, feature):
        
        """ The text value of an <analysis>.
        Arg:
            the name of the feature whose value to return.
            
        Returns:
            string, e.g. 'noun' for 'pos'.
        """
##        if feature == 'lang':
##            return self.ret_lang()
##        else:

        if self.elem.find(feature) is None:
            return feature + ' not found.'
        
        else:
            return self.elem.find(feature).text

    

    def pos (self):
        """
        Returns:
            the part of speech (string).
        """
        return self.elem.find('pos').text

    def lemma(self):
        """
        Returns:
            the lemma to which the form is assigned (string).
        """
        return self.elem.find('lemma').text

    def form(self):
        """
        Returns:
            the form, generally equals the form submitted for Latin, not always
            (usually?) for Greek.
        """
        return self.elem.find('form').text
    
    def fix(self, feat, text):
        """ Set the feature's value to text.
        Returns:
            no return value.
        Effect:
            sets the text of <feat> to the text argument.
        """
        el = self.elem.find(feat)
        if el is None:
            pass
        else:
            el.text = text

    def fix_lemma(self):
        """ Fix the lemma, which sometimes has a numerical suffix, by discarding
            the trailing digits.
        Returns:
            nothing returned.
        Effect:    
            the <lemma> element text is replaced. 
                
        """
        
        self.fix('lemma', self.lemma().rstrip('0123456789'))

    def fix_person(self):
        """Change the grammatical person to an integer.

           Returns:
                nothing returned.
           Effect:
                changes the <person> element text.
        """
        el = self.elem.find('person')
        if el is None:
            pass
        else:
            el.text = el.text[0]
    
    def ret_lang(self):
        """ Return the language name returned by Morpheus as an attribute of the
            form tag.
            
        Returns:
            string.
        """
        return self.elem.find('form').attrib.get('lang')

    def fix_lang(self):
        """ Copy the returned language into its own tag.
        Returns:
            nothing returned.
        Effect:
            adds a <lang> tag to the analysis.
        """ 
        el = ElementTree.Element('lang')
        la = self.ret_lang()
        # Taking the plunge and calling latin 'latin' instead of 'la'.
        # You only code once right?
        # N.B. The string used to identify Latin to Perseus is still 'la'.
        if la == 'la':
            la = 'latin'
        else:
            pass
        el.text = la
        self.elem.append(el)
   
    def fix_bad_mood(self):
        """ Fix infelicitous moods - remove them and change the part of speech.

        Returns:
            nothing returned.
        Effect:
            removes <mood> element from some analyses and tranfers its value to
            the <pos> element.
        """
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
        """ Return tense value which is defined only for verbs and verbal nouns
            and adjectives.
            
        Returns:
            string.
        """
        el = self.elem.find('tense')
        if el == None:
            return 'no tense'
        else: 
            return el.text

    def fix_part(self):
        """ Fix the Latin present participle by supplying its missing its voice.

        Returns:
            nothing returned.
        Effect:
            a <voice> element with value 'act' is added to the analysis.
        """
        if (self.pos() == 'part' and self.word.lang == 'la'
            and self.tense() == 'pres'):
            el = ElementTree.Element('voice')
            el.text = 'act'
            self.elem.append(el)
        else:
            pass

    def fix_pron(self):
        """ Fix a pronoun by adding person information, so that verb agreement
            can be computed. Only Latin ones need this.
            
        Returns:
            nothing returned.
        Effect:
            adds a <person> element to the analysis, if the pronoun is known.
        """ 
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
     	    
    
    


    def dict(self, q):
        """ Computes a dict of feature value pairs for use in computing JSON
            output.
            
        Args:
            q: the export sextuple
            core_fs: a list of core features (string) to export
            word_fs: a list of word features (string) to export.
        Returns:
            a dictionary of all word information, and tag, text pairs for
            features in arguments.
        """
        d = {}

        
        f = q[0] + q[2] + q[4]
        v = q[1] + q[3] + q[5]
        for i in range(0, len(f)):
            d[f[i]] = v[i]
        
        return d

    
    
    def json(self, q):
        """ Return JSON string. for features in list 'some' Features are in no
            guaranteed order.
        Args:
            core_fs: a list of core features (string) to export
            word_fs: a list of word features (string) to export.
        Returns:
            he analysis asa JSON string.

        """
        return json.dumps(self.dict(q),ensure_ascii = False)

    
    def backcheck(self):
        """ Does the analysis form returned match the form submitted?

        Returns:
            boolean.

        """
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
        """ A string representing the submitted and returned form match.
            Originally for debugging.
        """    
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
    

        
    def prolog(self, q):
        """ The exported analysis converted into a Prolog fact string."""
        v = q[1] + q[3] + q[5]
        vs = [_str(x, 'nothing', "'") for x in v]
        return self.pos() + '(' + ','.join(vs) + ').'
        
    def arity(self, core_fs, word_fs):
        """ Computes the arity of the Prolog fact specified by the arguments.

        Args:
            core_fs: a list of core features (string) to export
            word_fs: a list of word features (string) to export.
        Returns:
            integer.

        """
        
        return len(core_fs) + len(word_fs) + len(self.noncore_features())
       

    def prolog_proc_name(self, core_fs, word_fs):
        """ Compute the Prolog procedure name: functor and arity separated by /.
            E.g. 'verb/11'.

        Args:
            core_fs: a list of core features (string) to export
            word_fs: a list of word features (string) to export.
        Returns:
            string.

        """
        return self.pos() + '/' + str(self.arity(core_fs, word_fs))

    def oz(self, q):
        """ Compute a string for conversion to an Oz language record.

        Args:
            core_fs: a list of core features (string) to export
            word_fs: a list of word features (string) to export.
        Returns:
            string.
        """    

        f = q[0] + q[2] + q[4]
        
        v = q[1] + q[3] + q[5]
        vs = [_str(x, 'nil', "'") for x in v]
        return '|'.join(['analysis', ':'.join(f), ':'.join(vs)])
    
    
class Unique:
    """ A class to register objects.

    Attribute:
       set: a set
    """
    def __init__(self):
        self.set = set()
        
    def test(self, x):
        """ Has x been registered?
        Arg:
            x: any object.
        Returns:
            boolean.
        """
        n = len(self.set)
        self.set.add(x)
        return len(self.set) > n
    

    
        



