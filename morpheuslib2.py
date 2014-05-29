""" module morpheuslib2
Provides classes for accessing Perseus' Morpheus Greek and Latin 
morpholgy service; processing the XML data, and exporting it in other forms.    
"""
# coding: utf-8
import urllib.request
import urllib.error
import json
from xml.etree import ElementTree
import io
import unicodedata
import pickle
import datetime

def read_dict(file):
    """Read a file of lines with key value pairs separated by whitespace into
       a dictionary.
    Args:
        file: The path and name of the file..
    Returns:
        The dictionary
    Raises:
        IOError if file can't be opened.
    """
    f = open(file, 'r')
    lns = [l.rstrip() for l in f.readlines() if len(l) > 0 and l[0] != '#']
    f.close()
    d = {}
    for ln in lns:
            
        l, p = ln.split()
        d[l] = p
    
    return d

def read_list(file):
    """Read a text file of lines into a list, one line per list item.
       Each is rtrimmed.
       Blank lines are skipped.
       Lines beginning with '#' are skipped.
    Arg:
        file: the path and file name (str).
    Returns:
        list of str.
    Raises:
        IOError if f can't be opened.
    """  
    f = open(file, 'r')
    lns = [l.rstrip() for l in f.readlines() if len(l) > 0 and l[0] != '#']
    f.close()
    return lns

def is_letter(c, lang, greek_mode, mixed):
    if mixed:
        return Latin.is_letter(c) or UniGreek.is_letter(c)
    else:
        if lang == 'la':
            return Latin.is_letter(c)
        elif lang == 'greek':
            if greek_mode == 'betacode':
                return BetaCode.is_letter(c)
            elif greek_mode == 'unicode':
                return UniGreek.is_letter(c)
            else:
                raise LangError("Illegal greek_mode " + greek_mode)
        else:
            raise LangError("Illegal lang " + lang)

def num_sfx(s):
    """ Return a numerical suffix (a run of digits at the end of a 
        string).
    Arg:
        str.
    Returns:
        a terminal run of digits, or '' if none.
    """ 
    i = len(s) - 1
    while i >= 0 and s[i].isdigit():
        i = i - 1
    
    return (s[:i + 1], s[i + 1:])

def special_str(x, none):
    """A string meeting lexical requirements of Oz and Prolog."""
    if x is None:
        x = none

    if isinstance(x, str):
        return x.center(len(x) + 2 , "'")

    return str(x)

#Replace with ValueError?
class LangError(ValueError):
    """An exception for unrecognized language options.
    Attributes:
        lang: lang option - must be 'la' or 'greek'
        greek_mode: must be 'betacode' or 'unicode'
    """
    pass

class Latin(object):
    """A class to hold info and functions related to Latin and text in the Latin 
    alphabet.
    Class attributes:
        prons: a dict holding pronoun lemma -> person mappings
        abbrs: a list of Latin abbreviations.
    """
    prons = None
    abbrs = None

    @classmethod
    def is_letter(cls, c):
        """Is the argument a Latin letter?
        Returns:
            bool.
        """
        if unicodedata.category(c) in ['Ll', 'Lu']:
            return unicodedata.name(c).find('LATIN') >= 0
        else:
            return False

    @classmethod    
    def person(cls, lemma):
        """Return the person of the pronoun, if known to the system. 

        In case you are wondering, this method exists because Morpheus omits 
        person information from Latin pronouns (though not from Greek ones).
    
        Args:
            lemma:  the dictionary lemma, e.g. 'is' for 'ea' (str).
        Returns:
            the person '1st'/'2nd'/'3rd', if known (str).
        Raises:
            KeyError, if the pronoun isn't in the dict.
            IOError, if the prons.la file can't be read.
        """    
        
        return cls.get_prons()[lemma]

    @classmethod
    def get_prons(cls):
        """The mapping of pronoun lemmas -> pronoun persons.
        Returns:
            dict.
        Effect:
            sets class attribute prons lazily.
        Raises:
            IOError if file prons.la can't be read.
        """ 
        if cls.prons is None:
            cls.prons = read_dict('prons.la')
        else:
            pass
        return cls.prons

    @classmethod
    def get_abbrs(cls):
        """The list of Latin abbreviations. Currently, these are the praenomina.
        Returns:
            list of str. Empty if read of abbrs.la file fails.
        Effect:
            sets class attribute abbrs lazily.
        Raises:
            IOError if file abbrs.la can't be read.
        """
        if cls.abbrs is None:
            cls.abbrs = read_list('abbrs.la')
        else:
            pass
        return cls.abbrs

class BetaCode(object):
    """Holds methods for handling Greek text in BetaCode."""

    beta_ll = 'abgdezhqiklmncoprsstufxywvs'
    beta_lu = beta_ll.upper()        
    beta_diac = "/\()=+|'"
    beta = beta_ll + beta_lu + beta_diac
    uc_shift = '*'
    trans = None

    @classmethod
    def get_trans(cls):
        """Get the BetaCode character-> Unicode character translator.
        Returns:
            dict
        Effect:
            sets the trans class attribute lazily.
        """
        if cls.trans is None:
            cls.trans = str.maketrans(BetaCode.beta, UniGreek.greek)
        else:
            pass
        return cls.trans

    @classmethod
    def make_trans(cls):
        """Prepare the translator
        Effect:
            sets the trans class attribute.
        """
        BetaCode.trans = str.maketrans(BetaCode.beta, UniGreek.greek)

    @classmethod
    def is_letter(cls, c):
        """Is the argument a BetaCode letter? This set includes diacritics.
        Returns:
            bool.
        """
        return c in (cls.beta + cls.uc_shift)
        #return c in "abcdefghijklmnopqrstuwxyzABCDEFGHIJKLMNOPQRSTUWXYZ*/\=+)(|'"
    
    @classmethod
    def to_unicode(cls, s, lunate = False):
        """Convert BetaCode to Unicode. Output is in non-composed chatacters."
        Args:
            s: the string to convert.
            lunate: use the lunate sigma (optional, bool, default = False)?
        Returns:
            str.
        """
        
        
        buf = io.StringIO(' ' * len(s))
        i = 0
        while i < len(s):
            if s[i] == '*':
                print("help")
                i = cls.conv_uc(s, i, buf, lunate)
            elif s[i].isalpha():
                i = BetaCode.conv_lc(s, i, buf, lunate)
            else:
                i = BetaCode.conv_diac(s, i, buf)
        o = buf.getvalue().rstrip()
        buf.close()
        
        if o[-1] == UniGreek.sigma:
            return o[:-1] + UniGreek.final_sigma
        else: 
            return o

    @classmethod
    def conv_uc(cls, s, i, buf, lunate):
        """Helper method for to_unicode(). Performs conversion of uppercase
        letters.
        Args:
            s: the string being converted
            i: index of character being converted (int)
            buf: buffer receiving conversion output (io.StringIO)
            lunate: use lunate sigma (bool)?
        Returns:
            index of next character to convert (int).
        """
        #b receives diacritics.
        b = io.StringIO('  ')
        i = i + 1
        c = s[i]
        
        while not c.isalpha():
            b.write(c)
            i = i + 1
            c = s[i]
        bb = b.getvalue().rstrip()
        #c is now the letter.
        if  c == 's' or c == 'S':
            if lunate:
                buf.write(UniGreek.lunate_sigma.upper())
            else:
                buf.write(UniGreek.sigma.upper()) 
        else:
            buf.write(c.translate(BetaCode.get_trans()).upper())
        for x in bb:
            buf.write(x.translate(BetaCode.get_trans()))
        b.close()
        return i + 1

    @classmethod
    def conv_lc(cls, s, i, buf, lunate):
        """Helper method for to_unicode(). Performs translation of lower case
        characters.
        Args:
            s: the string being converted
            i: index of character being converted (int)
            buf: buffer receiving output (io.StringIO)
            lunate: use lunate sigma (bool)?
        Returns:
            index of next character to convert.
        """
        
        if s[i] == 's' or s[i] == 'S':
            if lunate:
                buf.write(UniGreek.lunate_sigma)
            else:
                buf.write(UniGreek.sigma)
        else:
            print(s[i] + s[i].translate(BetaCode.get_trans()))
            buf.write(s[i].translate(BetaCode.get_trans()))
        return i + 1

    @classmethod   
    def conv_diac(cls, s, i, buf):
        """Helper method for to_unicode(). Performs translation of diacritics.
        Args:
            s: the string being converted
            i: index of character being converted (int)
            buf: buffer receiving output (io.StringIO).
        Returns:
            index of next character to convert.
        """
        buf.write(s[i].translate(BetaCode.get_trans()))
        return i + 1
    
    @classmethod
    def cleanse(cls, s):
        """Remove diacritics from the word for use in a url.
        Arg:
            s: word to be cleansed
        Returns:
            str.
        """
        return ''.join([c for c in s if c.isalpha()])
    
class UniGreek(object):
    """Holds methods for handling Greek text in Unicode."""
    greek_ll = ((''.join([chr(i) for i in range(0x3B1, 0x03CA)]))
                        + chr(0x03DD) + chr(0x03F2))

    #Note coronis is treated here as a diacritic.
    greek_diac = (chr(0x0301) + chr(0x0300) + chr(0x0314) +chr(0x0313)
                          + chr(0x0342) + chr(0x0308) + chr(0x0345)
                          + chr(0x1fbd))

    greek_lu = greek_ll.upper()

    greek = greek_ll + greek_lu + greek_diac

    final_sigma = chr(0x03C2)
    sigma = chr(0x03C3)
    lunate_sigma = chr(0x03F2)
  
    trans = None

    @classmethod
    def make_trans(cls):
        UniGreek.trans = str.maketrans(UniGreek.greek, BetaCode.beta)

    @classmethod
    def get_trans(cls):
        """Get the Unicode character-> BetaCode character translator.
        Returns:
            dict
        Effect:
            sets the trans class attribute lazily.
        """
        if cls.trans is None:
            cls.trans = str.maketrans(UniGreek.greek, BetaCode.beta)
        else:
            pass
        return cls.trans

    @classmethod
    def is_letter(cls, c):
        #Note that coronis is treated here as a letter. 
        if unicodedata.category(c) in ['Ll', 'Lu'] or c == '\u1fbd':
            return unicodedata.name(c).find('GREEK') >= 0
        else:
            return False

    @classmethod
    def to_betacode(cls, s, mode):
        
        """Translate a Unicode Greek string to BetaCode.
        Args:
            s: the string to translate
            mode: 'upper', 'lower', or 'preserve'. 'upper' produces old 
            fashioned (TLG style) BetaCode in all upper case. 'lower' produces
            new-fangled (Perseus style) BetaCode in lower case. 'preserve' keeps
            the incoming case.
        Returns:
            str.
        """
        
        t = unicodedata.normalize('NFD', s)
        buf = io.StringIO(' ' * len(t))
        i = 0
        while i < len(t):
            if t[i].isupper():
                i = UniGreek.conv_uc(t, i, buf, mode)
            elif t[i].isalpha():
                i = UniGreek.conv_lc(t, i, buf, mode)
            else:
                i = UniGreek.conv_diac(t, i, buf)
 
        o = buf.getvalue().rstrip()
        buf.close()
        return o

    @classmethod
    def conv_uc(cls, t, i, buf, mode):
        """Helper method to translate upper case Unicode.
        """
        c = t[i]
        buf.write('*')
        i = i + 1
        while not t[i].isalpha():
            buf.write(t[i].translate(UniGreek.get_trans()))
            i = i + 1
        if mode == 'upper':
            buf.write(c.translate(UniGreek.get_trans()).upper())
        elif mode == 'lower':
            buf.write(c.translate(UniGreek.get_trans()).lower())
        elif mode == 'preserve':
            buf.write(c.translate(UniGreek.get_trans()))
        else:
            raise ValueError("Illegal BetaCode mode " + mode)
        return i

    @classmethod
    def conv_lc(cls, t, i, buf, mode):
        if mode == 'upper':
            buf.write(t[i].translate(UniGreek.get_trans()).upper())
        elif mode == 'lower':
            buf.write(t[i].translate(UniGreek.get_trans()).lower())
        elif mode == 'preserve':
            buf.write(t[i].translate(UniGreek.get_trans()))
        
        return i + 1

    @classmethod
    def conv_diac(cls, t, i, buf):
        buf.write(t[i].translate(UniGreek.get_trans()))
        return i + 1

    
             
class WordStream(object):
    """A stream of words from a text file or string. 
        
    The stream keeps track of some structure, namely the word ordinal and 
    the ordinals of the clause and sentence it belongs to. 

    Clauses and sentences are recognized by
    the standard punctuation marks of Greek and Latin. Parentheses and
    are dashes are ignored. An attempt is made to avoid miscounting 
    sentences by recognizing Latin abbreviations for praenomina.

    Attributes:
        i: ordinal of next word read word ordinal (int zero-based)
        c: ordinal of the clause whose words are being read (int zero 
           based)
        s: ordinal of the sentence whose words are being read (int zero
           based)
        text: an open TextIO object
        greek_mode: 'unicode' or 'betacode'.
        lang: 'greek', 'la', or 'mixed'
        label: a label serving as a scope for i, c, and s (str). May be None.

        These are the legal combinations of the lang, greek_mode,
        and mixed arguments:
        if lang == 'la', greek_mode is ignored
        if lang == 'greek', greek_mode must be 'unicode' or 'betacode'
        if mixed == True, greek_mode must be 'unicode'. 
        
    """
    def __init__(self, label, text, lang, greek_mode = None, mixed = False):
        self.label = label
        self.text = text
        self.lang = lang
        self.greek_mode = greek_mode
        self.mixed = mixed

        self.i = 0
        self.c = 0
        self.s = 0
        self.acc = io.StringIO(' ' * 20)

        if mixed and (greek_mode != 'unicode'):
            raise LangError("BetaCode Greek specified in mixed text mode.")

        if lang == 'la':
            self.seps = ",;:"
            self.terms = ".?"
            self.abbr_term = "."
            self.abbrs = Latin.get_abbrs()
        elif lang == 'greek':
            if greek_mode == 'betacode':
                self.seps = ',:'
                self.terms = ".;"
                self.abbr_term = ""
                self.abbrs = []
            elif greek_mode == 'unicode':
                #'\u00B7' is the middle dot (semicolon).
                self.seps = ",:" + '\u00B7'
                self.terms = ".;" 
                self.abbr_term = ""
                self.abbrs = []
            
            else:
                raise LangError("Illegal greek_mode argument " + greek_mode)
        else:
            raise LangError("Illegal lang argument " + lang)
        self.acc_ct = 0

    def __str__(self):
        return 'morpheuslib2.WordStream on ' + str(self.text)

    def __iter__ (self):
       return self  

    def __next__(self):
        """Read the next word from the stream.        
        Returns:
            str.
        Effects:
            see conv_acc().
        """
        while True:
            c = self.text.read(1)
            if c == '':
                if self.acc_ct > 0:
                    return self.conv_acc()                    
                else:
                    raise StopIteration

            elif c.isspace():
                if self.acc_ct > 0:
                    return self.conv_acc()
                else:
                    pass

            elif c in self.terms + self.seps:
                self.acc.write(c)
                return self.conv_acc()
                
            else:               
                if is_letter(c, self.lang, self.greek_mode, self.mixed):
                    self.acc.write(c)
                    self.acc_ct = self.acc_ct + 1
                else:
                    pass

    def close(self):
        """Close the text stream and accumulator."""
        self.text.close()
        self.acc.close()

    @classmethod
    def from_text(cls, label, text, lang, greek_mode = None, mixed = False):
        """Construct a WordStream instance from a string.
        Args:
            label: a label for the text (str)
            text: the text to stream over (str)
            lang: 'la' or 'greek'
            greek_mode: 'unicode' or 'betacode'; value ignored unless lang == 'greek'
        Returns:
            a WordStream instance.
        """
        f = io.StringIO(text)
        return cls(label, f, lang, greek_mode, mixed)
        
    @classmethod
    def from_file(cls, label, file, lang, greek_mode = None, mixed = False):
        """Construct a WordStream instance from a file.
        Args:
            label: a label for this text (str)
            file: path and file name (str)
            lang: 'la', 'greek'
            greek_mode: 'unicode' or 'betacode'; ignored unless lang == 'greek'. 
        Returns:
            an instance of WordStream.
        """    
        f = open(file, 'r')
        return cls(label, f, lang, greek_mode, mixed)

    def process(self):
        """Iterate through the stream and collect the results in a list.
        Returns:
              list of Word objects. Returns an empty list after one call.           
        """
        return [w for w in self]

    def abbr_check(self, s):
        """Is s in the list of recognized abbreviations?
            Returns:
                bool.
        """
        return s in self.abbrs

    def det_lang(self, s):
        if self.mixed:
            b1 = all([Latin.is_letter(c) for c in s]) 
            if b1:
                return 'la'
            b2 = all([UniGreek.is_letter(c) for c in s])
            
            if b2:
                return 'greek'
            raise LangError("Undetermined lang for mixed lang string " + s)
        else:
            return self.lang

    def conv_acc(self):
        """Convert the accumulator into a Word object.
        Returns:
            Word instance
        Effects:
            resets accumulator;
            resets bct (accumulated character count);
            updates word, clause, and sentence count variables.
        """
        s = self.acc.getvalue().rstrip()
        self.acc = io.StringIO(' ' * 20)
        self.acc_ct = 0
        
        
        t = s[-1]
        u = s.rstrip(self.seps + self.terms)
        
        a = Word(self.label, u, self.det_lang(u), self.greek_mode, self.i, self.c, self.s)
        if t in self.seps + self.terms:
            a.term = t   
        if t in self.seps + self.terms and not self.abbr_check(u + self.abbr_term):
            self.c = self.c + 1
        if t in self.terms and not self.abbr_check(u + self.abbr_term):
            self.s = self.s + 1
        self.i = self.i + 1
        return a

class Word(object):
    """One word, with its label, language and position information.
    
    Attributes:
        label: the scope of the text, e.g. 'Hom. Od. i'.
        word: the string
        lang: 'la' or 'greek'
        greek_mode: 'unicode' or 'betacode'
        term: sentence or clause terminator found with this word, or None (str)
        w: word ordinal (int, zero-based)
        c: clause ordinal (int, zero-based)
        s: sentence ordinal (int, zero-based)
        
    """
    features = ['label', 'w', 'c', 's']

    def __init__ (self, label, word, lang, greek_mode, w, c, s):
        """ Set the word's attributes, which come from the WordStream instance
            which is reading the text source.
        Args:
            label: the label of the containing text (str)
            word: the word (str)
            lang: 'la' or 'greek'
            greek_mode: 'unicode' or 'betacode'
            w: the word's ordinal in the text (zero-based, int)
            c: the ordinal of the word's containing clause (zero-based, int)
            s: the ordinal of the word's containing sentences (zero-based, int).
        """
        self.label = label
        self.word = word
        self.lang = lang
        self.term = None
        
        self.greek_mode = greek_mode
        self.w = w
        self.c = c
        self.s = s
    
    def for_url(self):
        """A version of the word for use in a Morpheus url. In Perseus BetaCode
        without diacritics.

        Returns:
            str.
        """
        if self.lang == 'la':
            return self.word.lower()
        elif self.lang == 'greek':
            if self.greek_mode == 'betacode':
                return BetaCode.cleanse(self.word).lower()
            elif self.greek_mode == 'unicode':
                return BetaCode.cleanse(UniGreek.to_betacode(self.word, 'lower'))
            else:
                raise LangError("Illegal greek_mode " + self.greek_mode)
        else:
            raise LangError("Illegal lang " + self.lang)

    def for_form_comp(self):
        """A version of the word for comparison wuth the form returned by
        Morpheus
        Returns:
            str.
        Raises:
            LangError.
        """
        if self.lang == 'la':
            return self.word.lower()
        elif self.lang == 'greek':
            if self.greek_mode == 'unicode':
                return self.word.lower()
            elif self.greek_mode == 'betacode':
                return BetaCode.to_unicode(self.word).lower()
            else:
                raise LangError("Invalid greek_mode " + self.lang)
        else:
            raise LangError("Invalid lang " + self.lang)

    def make_url(self):
        """ Convenience method to create a url for Morpheus service.
        Returns:
            MorpheusUrl instance.
        """
        return MorpheusUrl(self)

    @classmethod
    def from_str(cls, word, lang, greek_mode = None):
        """ A covenience method to construct a Word without a textual 
            context.
            Args:
                word: Latin or Greek word to look up (str)
                lang: 'la' or 'greek'.
                greek_mode: 'unicode' or 'betacode'.
            Returns:
                an instance of morpheuslib.Word with label 'none' and ordinals
                set to 0.
        """    
        return cls(None, word, lang, greek_mode, 0, 0, 0)

    @classmethod
    def basic(cls, word, lang, greek_mode):
        """A covenience method to construct a Word without a textual 
           context.
        Args:
            word: Latin or Greek word to look up (str)
            lang: 'la' or 'greek'.
            greek_mode: 'unicode' or 'betacode'.
        Returns:
            an instance of morpheuslib.Word with label 'none' and ordinals
            set to 0.
        """    
        return cls(None, word, lang, greek_mode, 0, 0, 0)

class MorpheusUrl(object):
    """ A word's Morpheus service URL.
    Class attribute:
        base: url base to use (str).
    Attributes:
        url: the Perseus url string
        word: (morpheuslib.Word) the word being looked up.
    """
    # A default base for the Morpheus service.
    base = 'http://www.perseus.tufts.edu/hopper/'

    def __init__ (self, word):
        """ Translate the word into a URL for lookup.
        Args:
            word (morpheuslib.Word): the word to look up.
        """
        self.url = MorpheusUrl.base + "xmlmorph?lang=" + word.lang + "&lookup=" + word.for_url()
        self.word = word

    def __str__(self):
        return 'morpheuslib2.MorpheusUrl ' + self.url
    
    

    def fetch (self):
        """ Fetch the <analyses> xml document.
        Returns:
            an instance of MorpheusResponse.
        Raises:
            urllib.error.HTTPError
            urllib.error.URLError
        """
        t = None
        try:
            response = urllib.request.urlopen(self.url)
            t = response.read()
            return MorpheusResponse(self, t, None)
        except Exception as exn:
            return MorpheusResponse(self, t, exn)

class MorpheusResponse(object):
    """ A wrapper for the result of submitting a MorpheusUrl.
    Attributes:
        url: a MorpheusUrl that was fetched
        text: the text returned, if successful (bytes)
        exn: the exception raised if unsuccessful.
    """
    def __init__(self, url, text, exn):
        self.url = url
        self.text = text
        self.exn = exn

    def is_ok(self):
        """Did the fetch succeed?
        Returns:
            bool.
        """
        return self.exn is None

    def word(self):
        """The word that was looked up.
        Returns:
            instance of class Word.
        """
        return self.url.word

    def retry(self):
        """Retry the fetch. 
        Returns:
            self if the original fetch was OK, otherwise a new MorpheusResponse.
        """
        if self.is_ok():
            return self
        else:
            return self.url.fetch()

    def make_analysis_list(self):
        return AnalysisList(self.text, self.word())

    def save_text(self, file, mode):
        """Save the document text returned by Perseus in a text file. Text is
        converted from bytes to str in utf-8 encoding.

        Args:
            file: path and file name (string)
            mode: Python mode code 'w' or 'a'.
        Returns:
            number of bytes written (int).
        Effect:
            creates, overwrites, or appends to file specified by location 
            argument, according to mode.
        """  
        f = open(file, mode, encoding="utf-8")
        n = f.write(self.text.decode(encoding="utf-8", errors="strict"))
        f.close() 
        return n

class Analysis:
    """ Wrapper for an <analysis> element.

        Does the work of fixing and converting the analysis element and provides
        access to its attributes.
    Attributes:
        
        elem: (Element) the <analysis> element
        word: (Word) the analysed word.
        
    """
    # Core features are those not specific to a part of speech.
    core_features = ['form', 'lemma', 'expandedForm', 'pos', 'lang','dialect', 'feature', 'lemma_sfx']

    def __init__ (self, elem, word):
        """
        Initializes the analysis element and word, and fixes the analysis.
        
        See the fix_ methods for more about the fixes.

        Args:
            elem: (Element):the <analysis> element 
            word (Word): the word analyzed.
        """
        
        self.elem = elem
        self.word = word

    def get_feature(self, feature):
        """Return the argument feature of this analysis.
        Returns:
            str.
        Raises:
            ValueError, if no such feature.
        """
        if feature == 'lang':
            return self.elem.find('form').attrib.get('lang')
        elif feature in Word.features:
            return getattr(self.word, feature)
        else:
            e = self.elem.find(feature)
            if e is None:
                raise ValueError("No feature " + feature)
            else:
                return e.text

    def fix_lemma(self):
        """Remove a numerical suffix from the lemma, if present.
        
        Effect:    
            if the lemma has a suffix, the <lemma> element text is replaced and
            a new element lemma_sfx is added with the removed suffix. 
        """
        (lem, sfx) = num_sfx(self.get_feature('lemma'))
        if len(sfx) == 0:
            pass
        else:
            el = ElementTree.Element('lemma_sfx')
            el.text = sfx
            self.elem.append(el)
        
        self.set_feature('lemma', lem)

    def fix_part(self):
        """Fix the Latin present participle by supplying its missing voice.
        Effect:
            a <voice> element with value 'act' is added to the analysis.
        """
        if (self.get_feature('pos') == 'part' and 
            self.get_feature('lang') == 'la'
            and self.get_feature('tense') == 'pres'):
            el = ElementTree.Element('voice')
            el.text = 'act'
            self.elem.append(el)
        else:
            pass

    def fix_pron(self):
        """Fix a pronoun by adding person information, so that verb agreement
           can be computed. Only Latin ones need this.
        Effect:
            adds a <person> element to the analysis, if the pronoun is known.
        Raises:
            KeyError if lemma isn't in the prons dict.
        """ 
        if self.get_feature('pos') == 'pron' and \
            self.get_feature('lang') == 'la':
            
            person = Latin.person(self.get_feature('lemma'))
            el = ElementTree.Element('person')
            el.text = person
            self.elem.append(el)
        else:
            pass

    def set_feature(self, feature, text):
        """ Set the feature's value to text.
        
        Effect:
            sets the text of the element to the text argument.
        Raises:
            ValueError if no such feature.
        """
        el = self.elem.find(feature)
        if el is None:
            raise ValueError("No feature " + feature)
        else:
            el.text = text

    def fix(self, *fixes):
        """Apply a list of fixes to this analysis.
        
        Note that the lemma shoyuld be fixed first, as the pronoun fix depends
        on it.

        Arg:
            fixes: names of fixes: 'pron', 'lemma', 'part'. See the method
            comments for more information.
        Effects:
            possibly alters the analysis. See fix_ method comments.
        Raises:
            AttributeError if no such fix exists.
        """
        for fix in fixes:
            getattr(self, 'fix_' + fix)()
            
    def inflectional_features(self):
        """Infections of the analysed word  
        Returns:
            names of those features specific to the part of speech (list of strings).
        """
        return sorted([x.tag for x in self.elem if x.tag not in Analysis.core_features])

    def to_xml(self):
        """The XML text for this analysis. Not identical to the original, if
        fixes were applied.
        Returns:
            bytes.
        """
        return ElementTree.tostring(self.elem, encoding = "utf-8", method= "xml")    

class AnalysisList:
    """ Provides multiple-pass processing of analyses.
    Attributes:
        word: the analyzed word (Word)
        root: root of the <analyses> document
        text: raw document text (bytes)
        l: the list of Analysis objects
  
    """
    def __init__(self, text, word):
        self.word = word
        els = ElementTree.fromstring(text).findall('analysis')
        self.l = [Analysis(el, word) for el in els]

    def __getitem__(self, i):
        return self.l[i]
    
    def __iter__(self):
        return self.l.__iter__()

    def len(self):
        return len(self.l)    
 
    def select(self, i):
        """Select an analysis from those returned.
        Returns:
            a (Word, Analysis) pair.
        """
        return (self.word, self[i])

class Cache:
    """A simple cache. Values are MorpheusResponse mappings.
    Words of both languages are stored in one cache.
    This class is not designed for concurrent usage.

    Attributes:
        file : location of cache, new or existing (str)
        pers: a dict of (str, str) -> MorpheusResponse mappings
        status: a basic status message 'reopened_cache', 'new_cache', or 'cache_changed'
        last_save: when changes made to in-memory dict of this instance were
        last saved to disk, or None (datetime). 
    """
    def __init__(self, file):
        self.file = file
        self.last_save = None
        try:
            f = open(file, 'rb')
            self.last_save, self.pers = pickle.load(f)
            
            f.close()
            self.status = 'reopened_cache'
        except Exception:
            self.pers = {}
            self.status = 'new_cache'

    def cache(self, resp):
        """ Cache a Morpheus response under  pair consisting of the url form 
            of the word and the language.
        Args:
            resp: an instance of MorpheusResonse.
        Effects:
            updates the cache dict by adding the (word, lang) -> resp mapping
            or replacing an exising one under the key; changes the status
            message to 'cache-changed'.
        Returns:
            doesn't return a value."""
       
        
        self.pers[(resp.word().for_url(), resp.word().lang)] = resp
        self.status = 'cache_changed'
 
    def lookup(self, word):
        """ Lookup a word in the cache.
        Args:
            word: an instance of Word.
        Returns:
            an Instance of MorpheusResponse such as would have been returned by
            Morpheus service; or None if the word is not found.
        """ 
        return self.pers.get((word.for_url(), word.lang))

    def save(self):
        """ Save the cache's current state.
        Effect:
            overwrites the existing cache file.
        Raises:
            OS, IO or Pickle error.
        """
        
        t = datetime.datetime.now()
        g = open(self.file, "bw")
        pickle.dump((t, self.pers), g)
        g.close()
        
    
        self.last_save = t
        
    def cached_words(self, lang):
        """ The list words currently stored in this instance.
        Args:
            lang : the language (str) 'greek' or 'la'.
        Returns:
            list of str.
        """
        return [w for (w, l) in self.pers.keys() if l == lang]

    def clear(self):
        """ Remove all entries from this cache in memory.
        Effect:
            clears the instance's dict; sets status to 'cache_changed'.
            No effect on disk cache until save() is called.
        
        """
        self.pers.clear()
        self.status = 'cache_changed'

    def uncache(self, word):
        del self.pers[(word.word, word.lang)]
        self.status = 'cache_changed' 
    
    @classmethod
    def default(cls):
        """Create a cache with file named morpheuslib2.cache in the current
        directory.
        """
        return cls('morpheuslib2.cache')

class Exporter(object):
    def __init__(self, *features, inflectional = True):
        """
        Args:
            features : names of core_features to export. If infleional is false,
                include inflectional features here also.
            inflectional: if True (default) all inflectional exported in order
                by feature name; if False, only inflectional features in *features
                are exported.
        """
        self.features = list(features)
        self.inflectional = inflectional
        self.vals = []
        self.keys = []
    
    def __iter__(self):
        return self.keys.__iter__()

    def __getitem__(self, key):
        try:
            i = self.keys.index(key)
            return self.vals[i]
        except ValueError:
            raise KeyError(key)

    def set_analysis(self, analysis):
        """Extract the features for export from the argument.
        Arg:
            analysis: instance of Analysis.
        Raises:
            ValueError if a feature is not found among analysis's features.
        """
        self.keys = self.features
        if self.inflectional:
            self.keys = self.keys + analysis.inflectional_features()
        self.vals = [analysis.get_feature(k) for k in self.keys]
         
    def json(self):
        """Export the analysis as JSON key:value pairs.
        Returns:
            str. If exporter was not initialized with an analysis, returns the 
            string 'null'
        """
       
        return json.dumps(dict(zip(self.keys, self.vals)), ensure_ascii = False)

    def prolog(self, functor = 'pos'):
        """A Prolog fact from this analysis."
        
        Default is to use the pos as a functor. Be sure to include 'pos' in the
        features argument of the Exporter constructor if you want this as the
        functor. Any functor arg that can't be found as a key will be used as 
        the functor.
        """
        func = None
        try:
            func   = self[functor]
        except KeyError:
            func = functor

        vx = [special_str(v, 'none') for v in self.vals]
        return func + '(' + ','.join(vx) + ')'

    def oz(self):
        """A form for importing as Oz language records."""
        
        vx = [special_str(v, 'none') for v in self.vals]
        return '|'.join(['analysis', ':'.join(self.keys), ':'.join(vx)])
