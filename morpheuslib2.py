"""module morpheuslib2
Provides classes for accessing Perseus' Morpheus Greek and Latin 
morpholgy service; processing the XML data, and exporting it in other forms.    


    Copyright (C) 2014  Timothy Mallon (mnstger@gmail.com)

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
import collections
import sqlite3

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
                raise LangError("Invalid greek_mode " + greek_mode)
        else:
            raise LangError("Invalid lang " + lang)

def num_sfx(s):
    """ Return a numerical suffix (a run of digits at the end of a 
        string).
    Arg:
        str.
    Returns:
        a pair consisting of: terminal run of digits, or '' if none; and the
        of this run, or '' if none.
    """ 
    i = len(s) - 1
    while i >= 0 and s[i].isdigit():
        i = i - 1
    
    return (s[:i + 1], s[i + 1:])

def special_str(x, none):
    """A string conversion meeting lexical requirements of Oz and Prolog.
    Args:
        x: the value to be converted
        none: the string to use if x is None.
    Returns:
        str.
    """
    if x is None:
        x = none

    if isinstance(x, str):
        return x.center(len(x) + 2 , "'")

    return str(x)

def url_form(word, lang, greek_mode):
    """A version of the word argument for use in a Morpheus url.
    
    Args:
        word: str
        lang: 'la' or 'greek'
        greek_mode: 'betacode' or 'unicode'.
    Returns:
        str.
    """
    if lang == 'la':
        return word.lower()
    elif lang == 'greek':
        if greek_mode == 'betacode':
            return BetaCode.cleanse(word).lower()
        elif greek_mode == 'unicode':
            return BetaCode.cleanse(UniGreek.to_betacode(word, 'lower'))
        else:
            raise LangError("Invalid greek_mode " + greek_mode)
    else:
        raise LangError("Invalid lang " + lang)

def retry_all(urls, max_tries, cache = None):
        """Try to fetch analyses from a list of urls within a number of tries.
        Args:
            urls: list of MorpheusUrls
            max_tries: how many times to try fetching all the urls (int)
            cache: either Cache or DbCache (optional, default: None).
        Returns:
            a triple consisting of: the number of tries made, a list of 
            MorpheusResponses, a bool indicating whether the operation succeeded
            in getting all the analyses.
        """
        d = 0
       
        
        
        while d < max_tries:
            if d == 0:
                l = [url.fetch(cache) for url in urls]
                
            else:
                l = [resp.retry(cache) for resp in l]
            d = d + 1
            if all([resp.is_ok() for resp in l]):
                return (d, l, True)
            else:
                pass
                
                
        return (d, l, False)


    
class LangError(ValueError):
    """An exception for unrecognized language options.
   
    """
    pass

class ResponseErrorInfo(object):
    """An abstract of an HTTPError.

    Used to avoid problems with pickling exceptions.
    Attributes:
        msg: the msg attribute of the original exception (str)
        code: the error code of the original exception (int).
    """
    def __init__(self, exn):
        """Arg:
            exn: an HTTPError.
        """
        self.msg = exn.msg
        self.code = exn.code

    def __str__(self):
        return "HTTPError " + str(self.code) + " " + self.msg        

class Latin(object):
    """A class to hold info and functions related to Latin and text in the Latin 
    alphabet.
    Class attributes:
        prons: a dict holding pronoun lemma -> person mappings
        abbrs: a list of Latin abbreviations.
    """
    prons = None
    abbrs = None

    @staticmethod
    def is_letter(c):
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

        This method reads a file 'prons.la' which is distributed with this 
        module and must be located in the same directory as the the copy of the 
        module being executed.

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

        This method reads a file 'abbrs.la' which is distributed with this 
        module and must be located in the same directory as the the copy of the 
        module being executed.

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
            cls.trans = str.maketrans(cls.beta, UniGreek.greek)
        else:
            pass
        return cls.trans

    @classmethod
    def make_trans(cls):
        """Prepare the translator
        Effect:
            sets the trans class attribute.
        """
        cls.trans = str.maketrans(cls.beta, UniGreek.greek)

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
                i = cls.conv_lc(s, i, buf, lunate)
            else:
                i = cls.conv_diac(s, i, buf)
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
        # b receives diacritics.
        b = io.StringIO('  ')
        i = i + 1
        c = s[i]
        
        while not c.isalpha():
            b.write(c)
            i = i + 1
            c = s[i]
        bb = b.getvalue().rstrip()
        # c is now the letter.
        if  c == 's' or c == 'S':
            if lunate:
                buf.write(UniGreek.lunate_sigma.upper())
            else:
                buf.write(UniGreek.sigma.upper()) 
        else:
            buf.write(c.translate(cls.get_trans()).upper())
        for x in bb:
            buf.write(x.translate(cls.get_trans()))
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
            print(s[i] + s[i].translate(cls.get_trans()))
            buf.write(s[i].translate(cls.get_trans()))
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
        buf.write(s[i].translate(cls.get_trans()))
        return i + 1
    
    @staticmethod
    def cleanse(s):
        """Remove diacritics from the word for use in a url.
        Arg:
            s: word to be cleansed
        Returns:
            str.
        """
        return ''.join([c for c in s if c.isalpha()])
    @staticmethod
    def fix_grave(word):
        """Return word with a grave accent changed to acute.
        
        Dictionary forms always have an acute accent.
        Arg:
           Greek word in Beta Code (str).
        Returns:
           the word with grave changed to acute (\ -> /).
        """
        return word.replace('\\', '/')
    
    @staticmethod
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
            
class UniGreek(object):
    """Holds methods for handling Greek text in Unicode."""
    greek_ll = ((''.join([chr(i) for i in range(0x3B1, 0x03CA)]))
                        + chr(0x03DD) + chr(0x03F2))

    # Note that coronis is treated here as a diacritic.
    greek_diac = (chr(0x0301) + chr(0x0300) + chr(0x0314) +chr(0x0313)
                          + chr(0x0342) + chr(0x0308) + chr(0x0345)
                          + chr(0x1fbd))

    greek_lu = greek_ll.upper()

    greek = greek_ll + greek_lu + greek_diac

    final_sigma = chr(0x03C2)
    sigma = chr(0x03C3)
    lunate_sigma = chr(0x03F2)
    coronis = chr(0x1fbd)

    trans = None

    @classmethod
    def make_trans(cls):
        cls.trans = str.maketrans(cls.greek, BetaCode.beta)

    @classmethod
    def get_trans(cls):
        """Get the Unicode character-> BetaCode character translator.
        Returns:
            dict
        Effect:
            sets the trans class attribute lazily.
        """
        if cls.trans is None:
            cls.trans = str.maketrans(cls.greek, BetaCode.beta)
        else:
            pass
        return cls.trans

    @staticmethod
    def is_letter(c):
        # Note that coronis is treated here as a letter. 
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
                i = cls.conv_uc(t, i, buf, mode)
            elif t[i].isalpha():
                i = cls.conv_lc(t, i, buf, mode)
            else:
                i = cls.conv_diac(t, i, buf)
 
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
            buf.write(t[i].translate(cls.get_trans()))
            i = i + 1
        if mode == 'upper':
            buf.write(c.translate(cls.get_trans()).upper())
        elif mode == 'lower':
            buf.write(c.translate(cls.get_trans()).lower())
        elif mode == 'preserve':
            buf.write(c.translate(cls.get_trans()))
        else:
            raise ValueError("Invalid BetaCode mode " + mode)
        return i

    @classmethod
    def conv_lc(cls, t, i, buf, mode):
        """Helper method to translate lower case Unicode.
        """
        if mode == 'upper':
            buf.write(t[i].translate(cls.get_trans()).upper())
        elif mode == 'lower':
            buf.write(t[i].translate(cls.get_trans()).lower())
        elif mode == 'preserve':
            buf.write(t[i].translate(cls.get_trans()))
        
        return i + 1

    @classmethod
    def conv_diac(cls, t, i, buf):
        """Helper method to translate Unicode diacritics.
        """
        buf.write(t[i].translate(cls.get_trans()))
        return i + 1

    @staticmethod
    def fix_grave(word):
        """Replace a grave accent with an acute.
        Arg:
           word: a Greek word (Unicode). 
        Returns:
           str.
        """
        w = unicodedata.normalize('NFD', word)
        b = io.StringIO(' ' * len(w))
        for c in w:
            if c == '\u0300':
                b.write('\u0301')
            else:
                b.write(c)
        r = unicodedata.normalize('NFC', b.getvalue())
        b.close()
        return r
 
    @staticmethod
    def fix_2nd_acute(word):
        """Delete a secondary acute accent.
        Arg:
            word: a Greek word (Unicode).
        Returns:
            str.
        """
        w = unicodedata.normalize('NFD', word)
        n = w.count('\u0301') + w.count('\u0342')
        if n > 1:
            i = w.rfind('\u0301')
            r = w[:i] + w[(i + 1):]
            return unicodedata.normalize('NFC', r)
        else:
            return word
    
             
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

        These are the valid combinations of the lang, greek_mode,
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
            raise LangError("Invalid greek_mode: 'betacode' or None specified in"
                            " mixed text mode.")

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
                # '\u00B7' is the middle dot (semicolon).
                self.seps = ",:" + '\u00B7'
                self.terms = ".;" 
                self.abbr_term = ""
                self.abbrs = []
            
            else:
                raise LangError("Invalid greek_mode argument " + greek_mode)
        else:
            raise LangError("Invalid lang argument " + lang)
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
        """Close the text stream and accumulator.
        Effect:
           instance is unusable. Further attempts to use it will cause errors.
        """
        self.text.close()
        self.acc.close()

    @classmethod
    def from_text(cls, label, text, lang, greek_mode = None, mixed = False):
        """Construct a WordStream instance from a string.
        Args:
            label: a label for the text (str)
            text: the text to stream over (str)
            lang: 'la' or 'greek'
            greek_mode: 'unicode' or 'betacode'; value ignored unless lang == 
                'greek' (optional, str, default is None)  
            mixed: is Greek text mixed with Latin? (optional, bool, 
                default is False).
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

    def process(self, filter = None):
        """Iterate through the stream and collect the results in a list.
        Arg:
            filter: a Word -> bool (or other type that implements __bool__())
            function. If provided, only words that satisfy the filter are 
            returned.
        Effect:
            consumes the stream.
        Returns:
            list of Word objects. Returns an empty list after one call.
        Raises:
            TypeError, if argument filter is not callable.          
        """
        if filter is None:
            return [w for w in self]
        else:
            return [w for w in self if filter(w)]

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
    #features = ['label', 'w', 'c', 's']
    features = ['label', 'word', 'w', 'c', 's']

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
        
    def same_w(self, other):
        """Are two words positionally the same?
        
        w is a text-scope ordinal, and so is sufficient to indicate positional sameness.
        Returns:
            bool.
        """
        return self.label == other.label and self.w == other.w
        
    def url_str(self):
        """The form of this Word suitable for submission to Morpheus in a url.
        Returns:
            str.
        """
        return url_form(self.word, self.lang, self.greek_mode)

    def key_pair(self):
        """A pair suitable for use as a key in a Cache.
        Returns:
            (str, str).
        """
        return (self.url_str(), self.lang)   

    def prolog(self, greek_mode = None, betacode_mode = None, lunate = False):
        """A Prolog functor for this word.
        A greek word may be in Beta Code or Unicode, output can be either.
        Args:
            greek_mode: for output 'betacode' or 'unicode'
            betacode_mode: for output: 'upper', 'lower' or 'preserve'.
        Returns:
            str.    
        """
        w = self.dictionary_str()
        if self.lang == 'la':
            pass
        elif self.lang == 'greek':
            if self.greek_mode == 'unicode':
                if greek_mode == 'unicode':
                    pass
                elif greek_mode == 'betacode':
                    # We have to escape "'" for Prolog
                    w = UniGreek.to_betacode(w, betacode_mode).replace("'", "\'") 
                else:
                    raise LangError("Invalid greek_mode " + greek_mode)
            else:
                # self.greek_mode is 'betacode
                if greek_mode == 'unicode':
                    w = BetaCode.to_unicode(w, lunate)
                else:
                    w = w.replace("'", r"\'") 

        return 'word(' + ','.join([special_str(w, 'None'), 
                                   special_str(self.label, 'None'), str(self.w),
                                   str(self.c), str(self.s)]) + ')'
    def dictionary_str(self):
        """Return athe dictionary form.
        
        This is important for Greek words only. It fixes accents to agree with 
        dictionary form (at most one acute or circumflex. no grave).
        """
        if self.lang == 'la':
            return self.word
        else: # lang is greek
            if self.greek_mode == 'betacode':
                fg = BetaCode.fix_grave
                f2a = BetaCode.fix_2nd_acute                    
            elif self.greek_mode == 'unicode':
                fg = UniGreek.fix_grave
                f2a = UniGreek.fix_2nd_acute                    
            else:
                fg = lambda x: x
                f2a = fg
            return f2a(fg(self.word))                      
            
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

    

class MorpheusUrl(object):
    """ A word's Morpheus service URL.
    Class attribute:
        base: url base to use (str).
    Attributes:
        url: the Perseus url string
        word: (morpheuslib2.Word) the word being looked up.
    """
    # A default base for the Morpheus service.
    base = 'http://www.perseus.tufts.edu/hopper/'

    def __init__ (self, word):
        """ Translate the word into a URL for lookup.
        Args:
            word (morpheuslib.Word): the word to look up.
        """
        self.key = (url_form(word.word, word.lang, word.greek_mode), word.lang)
        self.url = MorpheusUrl.base + "xmlmorph?lang=" + word.lang + "&lookup=" + url_form(word.word, word.lang, word.greek_mode)
        #self.word = word

    def __str__(self):
        return 'morpheuslib2.MorpheusUrl ' + self.url
    
    

    def fetch(self, cache = None):
        """Fetch the <analyses> XML document.
        Arg:
            cache: if given, this cache will be tried before the Morpheus
            service (Cache or DbCache). The result will be cached if it was 
            missing from the cache. 
        Returns:
            an instance of MorpheusResponse.
        Raises:
            urllib.error.HTTPError
            urllib.error.URLError
        """
        
        if cache is None:
            t = None
            try:
                response = urllib.request.urlopen(self.url)
                t = response.read()
                return MorpheusResponse(self, t, None)
            except urllib.error.HTTPError as ex2:
                # These errors are intermittent (403s mostly). Processing can
                # continue.
                return MorpheusResponse(self, t, ResponseErrorInfo(ex2))
            except urllib.error.URLError as ex1:
                # This error typically indicates a connection problem. Best to
                # report it at once.
                raise ex1
            
            
        else:
            resp = cache.lookup_key(self.key)
            if resp is None or not resp.is_ok():
                resp = self.fetch()
                cache.cache(resp)
                return resp
            
            else:
                return resp
                

class MorpheusResponse(object):
    """A wrapper for the result of submitting a MorpheusUrl, whether or not 
    successful.
    Attributes:
        url: a MorpheusUrl that was fetched
        text: the text returned, if successful (bytes)
        exn: ResponseErrorInfo from the exception raised if unsuccessful.
    """
    def __init__(self, url, text, exn):
        self.url = url
        self.text = text
        self.exn = exn
        
        
    def __str__(self):
        return 'morpheuslib2.MorpheusResponse from ' + str(self.url) + \
               (' (ok)' if self.is_ok() else ' (not ok)')
 
    def is_ok(self):
        """Did the fetch succeed?
        Returns:
            bool.
        """
        return self.exn is None

    def key(self):
        """The word that was looked up.
        Returns:
            instance of class Word.
        """
        return self.url.key

    def retry(self, cache = None):
        """Retry the fetch  operation.
        Arg:
            cache: cache to try before the Morpheus service (optional, Cache or
            DBCache, default is None). 
        Returns:
            self if the original fetch was OK, otherwise a new MorpheusResponse.
        """
        if self.is_ok():
            return self
        else:
            return self.url.fetch(cache)

    def make_analysis_list(self, word):
        """Make an AnalysisList from this instance.
        Returns:
            AnalysisList
        """
        return AnalysisList(self.text, word)

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

        See the fix_ methods for more about fixes that can be applied.

        Methods in this class that modify the instance return self in those
        cases where chaining method calls would be natural. 
    Attributes:
        
        elem: (Element) the <analysis> element
        word: (Word) the analysed word.
        
    """
    # Core features are those not specific to a part of speech.
    # lemma_sfx is not original, but created by extracting a numerical suffix
    # from a lemma and making it an attrib of the lemma . This is an optional fix.
    # All other core features are expected for all parts of spech.
    core_features = ['form', 'lemma', 'expandedForm', 'pos', 'lang','dialect',
                    'feature', 'lemma_sfx']

    def __init__ (self, elem, word):
        """Initializes the analysis element and word.
        
        

        Args:
            elem: (Element):the <analysis> element 
            word (Word): the word analyzed.
        """
        
        self.elem = elem
        self.word = word

    def __eq__(self, other):
        if isinstance(other, Analysis):
            if self.get_feature('lang') == other.get_feature('lang'):
                r = self.raw_features()
                if r == other.raw_features():
                    for f in r:
                        if self.get_feature(f) != other.get_feature(f):
                            return False
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(tuple([self.get_feature(f) for f in self.raw_features()]))

    def get_feature(self, feature):
        """Return the feature of this analysis that is in the element named 
        'feature'.
        Arg:
            feature: str.
        Returns:
            str.
        Raises:
            ValueError, if no such feature.
        """
        if feature == 'lang':
            return self.elem.find('form').attrib.get('lang')
        elif feature == 'lemma_sfx':
            return self.elem.find('lemma').attrib.get('sfx')
        elif feature in Word.features:
            return getattr(self.word, feature)
        else:
            e = self.elem.find(feature)
            if e is None:
                raise ValueError("No feature " + feature + " in " + self.raw_str())
            else:
                return e.text

    def fix_lemma(self):
        """Remove a numerical suffix from the lemma, if present.
        
        Effect:    
            if the lemma has a suffix, the <lemma> element text is replaced and
            a new element lemma_sfx is added with the removed suffix. 
        Returns:
            self.
        """
        (lem, sfx) = num_sfx(self.get_feature('lemma'))
        if len(sfx) == 0:
            pass
        else:
            #el = ElementTree.Element('lemma_sfx')
            #el.text = sfx
            #self.elem.append(el)
            el = self.elem.find('lemma')
            el.text = lem
            el.set('sfx', sfx)
        #self.set_feature('lemma', lem)
        return self

    def fix_part(self):
        """Fix the Latin present participle by supplying its missing voice.
        Effect:
            a <voice> element with value 'act' is added to the analysis.
        Returns:
            self.

        """
        if (self.get_feature('pos') == 'part' and 
            self.get_feature('lang') == 'la'
            and self.get_feature('tense') == 'pres'):
            el = ElementTree.Element('voice')
            el.text = 'act'
            self.elem.append(el)
        else:
            pass
        return self

    def fix_pron(self):
        """Fix a pronoun by adding person information, so that verb agreement
           can be computed. Only Latin ones need this.
        Effect:
            adds a <person> element to the analysis, if the pronoun is known.
        Returns:
            self.
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
        return self

    def fix_mood(self):
        """ Fix certain moods - remove them and change the part of speech.
        
        This is useful if you are exporting to Prolog, so that all verb facts
        will be finite forms and have the same arity.
  
        Returns:
            self.
        Effect:
            removes <mood> element from supine, infinitive and gerundive and 
            tranfers its value to the <pos> element.
        """
        el = self.elem.find('mood')
        if el == None:
            pass
        else:
            if el.text == 'supine' or el.text == 'inf' or el.text == 'gerundive':
                self.set_feature('pos', el.text)
                self.elem.remove(el)
            else: 
                pass
        return self
    
    def is_uc(self):
        """Test for upper casing.
        This is done on the lemma, since the form is invariably lower case, 
        whereas the lemma is variably cased.
        
        Returns:
            bool.
        """
        c = self.get_feature('lemma')[0]
        
        return unicodedata.category(c) == 'Lu'
        
        
    def fix_form(self):
        """If the analyzed word was capitalized, restore the capitalization to 
        the form.
        Returns:
            self.
        Effect:
            possbly modifies the form element.
        """
            
        if self.is_uc():
            self.set_feature('form', self.get_feature('form').title())
        
                
            
    def lemma_with_sfx(self):
        s = self.get_feature('lemma_sfx')
        return self.get_feature('lemma') + ('' if s is None else s)
    
    def set_feature(self, feature, text):
        """ Set the feature's value to text.
        Returns:
            self.
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
            return self

    def add_feature(self, feature, value):
        el = ElementTree.Element(feature)
        el.text = value
        self.elem.append(el)
        return self

    def fix(self, *fixes):
        """Apply a list of fixes to this analysis.
        
        Note that the lemma fix should be first, as the pronoun fix depends
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
        """Infections of the analysed word.  
        Returns:
            names of those features specific to the part of speech (list of str).
        """
        return sorted([x.tag for x in self.elem if x.tag not in Analysis.core_features])

    def to_xml(self):
        """The XML text for this analysis. Not identical to the original, if
        fixes were applied.
        Returns:
            bytes.
        """
        return ElementTree.tostring(self.elem, encoding = "utf-8", method= "xml")

    def raw_str(self):
        """A string of feature:value pairs directly from the xml document.
        Returns:
            str.
        """
        return ' '.join([t.tag + ':' + t.text for t in self.elem
                         if t.text is not None])

    def raw_features(self):
        """Tags in the xml document, sorted ascending.

        All the element tags as defined by Morpheus. Therefore, no 'lemma_sfx' or 
        'lang' ('lang' is an attribute of 'form').
        Returns:
            list of str.
        """
        return sorted([t.tag for t in self.elem])
 
    def is_matched(self):
        """Does the form of the analysis match the word submitted?

        For Latin, the test is equality of the lowered word and the returned
        form. For Greek, things are more complicated ... by the BetaCode/Unicode
        issue and accentuation.
        Arg:
            case_check: if True, perform an additional check of the lemma and
            word casing. Optional, default is False.
        Returns:
            bool.
        """
        if self.word.lang == 'la':
            f = self.word.word
        elif self.word.lang == 'greek':
            if self.word.greek_mode == 'betacode':
                f = BetaCode.to_unicode(self.word.word)
            else:
                f = self.word.word        
        #if check_case:
        if unicodedata.category(f[0]) \
        != unicodedata.category(self.get_feature('lemma')[0]):
            return False
        #if self.word.lang == 'la':
            #f = self.word.lower()
        if self.word.lang == 'greek':
            #if self.word.greek_mode == 'betacode':
                #f = BetaCode.to_unicode(self.word.word)
            fg = UniGreek.fix_grave
            f2a = UniGreek.fix_2nd_acute    
            f = f2a(fg(f))            
        else:
            #f = self.lower()
            pass
            
        return f == self.get_feature('form')    

class AnalysisList:
    """ Provides multiple-pass processing of analyses.
    Attributes:
        word: the analyzed word (Word)
        root: root of the <analyses> document
        text: raw document text (bytes)
        l: the list of Analysis objects
  
    """
    def __init__(self, text, word, list = None):
        """The optional argument list allows instance creation from an existing
        instance of this class. 
        Args:
            text: raw XML text (bytes)
            word: the analyzed word (morpheuslib2.Word)
            list: instance of AnalysisList. Ignored if text is given. Optional,
                default is None.

        To construct from XML text use:
        AnalysisList(text, word); 
        from existing list of Analyses:
        AnalysisList(None, word, list).
        """
        self.word = word
        if text is not None:
            els = ElementTree.fromstring(text).findall('analysis')
            self.l = [Analysis(el, word) for el in els]
        else:
            if list == None:
                self.l = []
            else:
                self.l = list

    def __getitem__(self, i):
        return self.l[i]
    
    def __iter__(self):
        return self.l.__iter__()

    def __len__(self):
        return len(self.l)    
 
    def select(self, i):
        """Select an analysis from those returned.
        Arg:
            i: index of selected analysis.
        Returns:
            a (Word, Analysis) pair.
        Raises:
            IndexError if i is out of range.
        """
        return (self.word, self[i])

    def filter(self, **terms):
        """Filter the analyses successively by the argument terms.
        
        When using filter(), note that it is sensitive to features and their 
        order. For example, if filtering on a case, filter on a part of speech
        that has case first, then on the case. E.g. pos='noun', case='acc'.
        Otherwise, if a verb is among the analyses, trying to filter it on case
        will cause a ValueError to be raised from get_feature().  
        Arg:
            **terms is list of the form feature=value, separated by commas. The
            values are in quotes.
            To exclude the value, prefix it with !. To indicate an integer value,
            prefix it with '#'. The order is ! if needed, # if needed, then value.
        Returns:
            list of Analysis objects.
        Raises:
            ValueError if an invalid feature is requested.
        """
        l = self.l
        
        for k in terms.keys():
            neg = False
            v = terms[k]
            if v[0] == '!':
                neg = True
                v = v[1:]
            if v[0] == '#':
                v = int(v[1:])
            if neg:
                l = [a for a in l if a.get_feature(k) != v]
            else:
                l = [a for a in l if a.get_feature(k) == v]
        return l

    def retain(self, **terms):
        """Retain only analyses that satisfy **terms. See method filter() for
        details about terms.
        
        Essentially a mutating verson of filter().
        Arg:
            **terms: a list of feature=value clauses by which to filter.
            See filter() comment for requirements and precautions.
        Effect:
            replaces the list attribute of the instance.
        Raises:
            ValueError, if a non-existent feature is specified.
        Returns:
            self.
        """
        self.l = self.filter(**terms)
        return self
    

    def dedupe(self):
        """Remove duplicates Analyses from this instance.
        Effect:
            replaces the list with the new list. Use deduped() to get a new
            instance.
        Returns:
            self.
        """   
        self.l =  list(set(self))
        return self
    
    def deduped(self):
        """Return a new AnalysisList deduped.

        Cf. dedupe().
        """
        return AnalysisList(None, self.word, list(set(self)))


    def all_matched(self):
        """Analyses whose form matches the submitted form.'
        Arg:
            check_case: also check whether the initial of the lemma matches the
            initial of the submitted word in case (bool, optional, default is 
            False).
        Returns:
            list of Analysis objects.
        """ 
        return [a for a in self if a.is_matched()]

    def discard_unmatched(self):
        """Remove unmatched Analyses from this instance.
        Arg:
            check_case: check match between case of lemma and submitted word.
            (bool, optional, default is False).
        Effect:
            replace the instance's list with filtered list.
        Returns:
            self.
        """
        self.l = [a for a in self if a.is_matched()]
        return self
      
    def fix(self, *fixes):
        for a in self:
            a.fix(*fixes)
        return self
    
    def get_feature(self, feature):
        return [a.get_feature(feature) for a in self]
    
class Cache:
    """A simple cache for MorpheusResponses. 

    Keys are pairs cnsisting of the url form of a word, and its language.
    Words of both languages are stored in one cache.
    This class is not designed for concurrent usage.

    Attributes:
        file : location of cache, new or existing (str)
        pers: a dict of (str, str) -> MorpheusResponse mappings
        status: a basic status message 'reopened_cache', 'new_cache', or 
            'cache_changed'. The status is of the in-memory cache.
        last_save: when changes made to in-memory dict of this instance were
        last saved to disk, or None (datetime). 
    """

    CommitReport = collections.namedtuple('CommitReport', ['will_be_deleted', 
        'will_be_replaced', 'will_be_added'])

    def __init__(self, file):
        """
        Arg:
            file: file name with (for non-relative location) or without (for 
                location in same directory) path.
        """
        f = None
        try:
            f = open(file, 'rb')
            self.last_save, self.pers = pickle.load(f)
            self.status = 'reopened cache'
        except IOError:
            f = open(file, 'wb')
            pickle.dump((datetime.datetime.now(), {}), f)
            self.pers = {}
            self.status = 'new cache'
            self.last_save = None
        except Exception as exn:    
            self.pers = {}
            self.status = 'corrupted cache'
            self.load_exn = exn
            self.last_save = None 
        finally:
            f.close()
            self.file = file

    def __str__(self):
        return "morpheuslib2.Cache at " + self.file

    def __getitem__(self, key):
        """
        Arg:
            a pair consisting of the url form of the word
            and the language of the word (str, str).
        Raises:
            KeyError if the key is not in the cache.
        """
        return self.pers[key]    

    def cache(self, resp):
        """Cache a Morpheus response under  pair consisting of the url form 
            of the word and the language.
        Args:
            resp: an instance of MorpheusResonse.
        Effects:
            updates the cache dict by adding the (word, lang) -> resp mapping
            or replacing an exising one under the key; changes the status
            message to 'cache-changed'.
        """
       
        
        self.pers[resp.key()] = resp
        self.status = 'cache_changed'
 
    def lookup_word(self, word):
        """ Lookup a word in the cache.
        Args:
            word: an instance of Word.
        Returns:
            an Instance of MorpheusResponse such as would have been returned by
            Morpheus service; or None if the word is not found.
        """ 
        return self.pers.get(word.key_pair())

    def lookup_str(self, word, lang, greek_mode = None):
        """Lookup a word in plain string form.
        Args:
            word: str
            lang: 'greek' or 'la'
            greek_mode: 'unicode' or 'betacode' (optional, default: None).
        Returns:
            MorpheusResponse.
        Raises:
            LangError if lang == 'greek' and greek_mode is not 'unicode' or 
            'betacode'.
        """
        if lang == 'greek' and greek_mode not in ['unicode', 'betacode']:
            raise LangError("Invalid greek_mode " + str(greek_mode))
        else:
            return self.pers.get((url_form(word, lang, greek_mode, lang)))
                                 
    def lookup_key(self, key):
        """Look up the key which is a pair consisting of the url form of the word
        and the language of the word.
        Arg:
            (str, str).
        Returns:
            a MorpheusResponse, or None if the key is not found.
            
        """
        try:
            return self.pers[key]
        except KeyError:
            return None
        
    def commit(self):
        """ Commit the cache's current (memory) state.
        Effect:
            overwrites the existing cache file.
        Returns:
            self.
        Raises:
            OS, IO or Pickle error.
        """
        
        t = datetime.datetime.now()
        g = open(self.file, "bw")
        pickle.dump((t, self.pers), g)
        g.close()
        
    
        self.last_save = t
        return self
        
    def cached_words(self, lang = None):
        """ The list words currently stored in this instance.
        Args:
            lang : the language (optional, str) 'greek' or 'la', or None to
            return words for both languages.
        Returns:
            list of (str, str) i.e. (word, lang) pairs. Note that the word is in
            url form.
        """
        if lang is None:
            return self.cached_words('greek') + self.cached_words('la')
        else:
            return [(w, l) for (w, l) in self.pers.keys() if l == lang]

    def count(self):
        """The size - number of words - of this cache.
        Returns:
            int.
        """
        return len(self.cached_words())

    def clear(self):
        """ Remove all entries from this cache in memory.
        Effect:
            clears the instance's dict; sets status to 'cache_changed'.
            No effect on disk cache until save() is called.
        
        """
        self.pers.clear()
        self.status = 'cache_cleared'

    def uncache_word(self, word):
        """Remove the response for the argument word from the cache.
        Arg:
            Word object.
        Effect:
            removes the cache entry from the in-memory cache.
        Returns:
            the value (MorpheusResponse), if the key is found, otherwise None.
        """
        # del self.pers[(url_form(w.word, w.lang, w.greek_mode), w.lang)]
        k = self.pers.pop(word.key_pair(), None)
        self.status = 'cache_changed' 
        return k

    def zap(self):
        """Erase the cache file. Useful if it gets corrupted.
        Effect:
            writes a (datetime, empty dict) pair to the cache file. No effect on
            data in memory.
        """
        
        g = open(self.file, "bw")
        pickle.dump((datetime.datetime.now(), {}), g)
        g.close()
        #self.status = 'cache_zapped'

    def commit_report(self):
        """A report on how a call to commit() will change the cache disk file.

        Returns:
            a Cache.CommitReport named tuple, which is a triple of lists of 
            (str, str) i.e. (word, lang) pairs. The first list is all keys in 
            disk file that will be gone after a save. The second list is all 
            keys in the disk cache that will be updated by values in memory. 
            The third is all keys in memory that will be added to the disk cache.
        Raises:
            IOError
            PickleError
            potentially others. See  Python Library doc sec 12.1.3
        """
        
        
        f = open(self.file, 'rb')
        
        _, dict = pickle.load(f)
            
        fkeys = dict.keys()
        mkeys = self.pers.keys()
        f.close()
        return Cache.CommitReport([k for k in fkeys if k not  in mkeys], 
               [k for k in mkeys if k in fkeys],
               [k for k in mkeys if not k in fkeys])

    def not_ok(self, lang = None):
        """A list of responses in the cash that are lacking the <analyses> 
        document.
        Arg:
            'greek'. 'la', or None. If None, results for both languages are 
            returned. Optional, default is None.
        Returns:
            list of ((word, lang), resp) pairs ((str, str), MorpheusResponse).
        """
        if lang is None:

            return [(k, resp) for (k, resp) in self.pers.items() if not resp.is_ok()]
        else:
            return[((w, l), resp) for ((w, l), resp)in self.pers.items() if (not resp.is_ok()) and (l == lang)]
        
    def filter(self, filter):
        """A list of MorpheusResponses satisfying filter criteria.
        Arg:
            filter: a callable (method of MorpheusResponse, or lambda), 
            returning bool.
        Returns:
            a list of MorpheusResponses.
        Raises:
            AttributeError if the filter calls an a non-existent method.
        """ 
        return [resp for resp in self.pers.values() if filter(resp)]    
        
    @classmethod
    def default(cls):
        """Create a cache with file named morpheuslib2.cache in the current
        directory.
        """
        return cls('morpheuslib2.cache')

    def triples(self, filter = None):
        """A list of (word, lang, pickled response) triples.
        Arg:
            filter: a callable on the triple giving a bool. Optional, default is 
                None.
        """ 
        if filter is None:
            return [(w, l, pickle.dumps(resp)) for ((w, l), resp) in self.pers.items()]
        else:
            
            return [(w, l, pickle.dumps(resp)) for ((w, l), resp) in self.pers.items() if filter(w, l, resp)]

class Exporter(object):
    def __init__(self, *core_features, betacode_mode = None):
        """
        Args:
            features : names of core_features to extract. If inflectional is false,
                include inflectional features here also.
            inflectional: if True (default) all inflectional exported in order
                by feature name; if False, only inflectional features in *features
                are exported. Optional.
            omit: names of features to omit frm export. Optional, default is []
            betacode_mode: if 'lower', 'upper', or preserve, export form, lemma,
            and extendedForm in Beta Code instead of Unicode (the Morpheus default).
            Optional, default is False.
        """
        self.core_features = list(core_features)
        self.unique = set()
        self.vals = []
        self.keys = []
        self.betacode_mode = betacode_mode
        
    def __iter__(self):
        return self.keys.__iter__()

    def __getitem__(self, key):
        try:
            i = self.keys.index(key)
            return self.vals[i]
        except ValueError:
            raise KeyError(key)
        
    
        
    def set_analysis(self, analysis):
        """Set the analysis to export.
        Arg:
            analysis: instance of Analysis.
        Raises:
            ValueError if a feature is not found among analysis's features.
        """
        n = len(self.unique)
        self.unique.add(analysis)
        if len(self.unique) == n:
            return False
        else:
            self.keys = self.core_features + analysis.inflectional_features()
            if analysis.word.lang == 'greek'and self.betacode_mode is not None:
                self.vals = [(UniGreek.to_betacode(analysis.get_feature(k)
                                                   , self.betacode_mode).replace("'", r"\'") 
                              if k in ['form', 'lemma', 'extendedForm'] 
                              else analysis.get_feature(k)) for k in self.keys]
            else:    
                self.vals = [analysis.get_feature(k) for k in self.keys]
            return True
         
    def json(self, omit = []):
        """Export the analysis as JSON key:value pairs.
        Returns:
            str. If exporter was not initialized with an analysis, returns the 
            string 'null'.
        """
       
        l = [(k, self.vals[k]) for k in self.keys if k not in omit]
        return json.dumps(dict(l), ensure_ascii = False)

    def prolog(self, functor, omit = []):
        """A Prolog functor from this analysis."
        
        Default is to use the pos as a functor. Be sure to include 'pos' in the
        features argument of the Exporter constructor if you want this as the
        functor. Any functor arg that can't be found as a key will be used as 
        the functor.
        Arg:
            functor: str.
        Returns:
            str. 
        """
        #func = None
        #try:
            #func   = self[functor]
        #except KeyError:
            #func = functor
        if functor[0] == '$':
            func = self[functor[1:]]
        else:
            func = functor
        vs = [self[k] for k in self.keys if not k in omit]    
        vx = [special_str(v, 'none') for v in vs]
        return func + '(' + ','.join(vx) + ')'

    def oz(self, omit = []):
        """A string for importing as an Oz language record."""
        
        vx = [special_str(self.vals[k], 'none') for k in self.keys if not k in omit]
        return '|'.join(['analysis', ':'.join(self.keys), ':'.join(vx)])

class DbCache(object):
    """A cache implemented in the Sqlite database.
    
    The database has one table whose primary key is the (word, lang) pair used
    in the file system cache dictionary. The MorpheusResponse is pickled and placed
    in an Sqlite BLOB column.
    Attributes:
        cnx: sqlite3.Connection
    """
    def __init__(self, file):
        """Creates the cache table in the database at file, if it doesn't exist.
        Arg:
           file name (for relative location) or path + file name (for absolute
                location.
        Effect:
            creates an opn connection to the cache database.
        """
        self.cnx = sqlite3.connect(file)
        try:
            self.cnx.execute("select * from cache")
        except sqlite3.OperationalError:
            self.cnx.execute("create table cache(word TEXT, lang TEXT, resp BLOB, primary key(word, lang))")  
        
    def insert(self, resp):
        """Insert the argument into the cache table.
        Arg:
            resp: MorpheusResponse.
        Raises:
            sqlite3.IntegrityError if the key (word, lang) is already in the
            database.
        Returns:
            self.
        """
        # c = self.cnx.cursor()
        # w = resp.word()
        # r = pickle.dumps(resp)
        # t = (url_form(w.word, w.lang, w.greek_mode), w.lang, r)
        w, l = resp.word().key_pair()
        self.cnx.execute('insert into cache values (?,?,?)', (w, l, pickle.dumps(resp)))
        self.cnx.commit()
        return self

    def cache(self, resp):
        """A 'no-fault' method like Cache.cache(), if the key is in the table, 
        an update is done, otherwise an insert.
        Arg:
            resp: MorpheusResponse.
        Returns:
            self.
        Raises:
            other exception.
        """
        try:
            self.insert(resp)
        except sqlite3.IntegrityError:
            self.update(resp)
        except Exception as exn:
            raise exn
    
    def close(self):
        """Close this instance's connection.
        Effect:
            instance is no longer usable.
        """
        self.cnx.close()

    def count(self, lang = None):
        """A count of the responses currently in the cache.
        Arg:
            lang: 'greek' or 'la' (optional). If omitted, count for both languages.
        Returns:
            int.
        """
        if lang is None:
            (n,) = self.cnx.execute("select count(*) from cache").fetchone()
        else:
            (n,) = self.cnx.execute("select count(*) from cache where lang = ?", (lang,)).fetchone()
        return n
 
    def lookup_word(self, word):
        """Lookup the word in this cache.
        Arg:
            instance of Word.
        Returns:
            MorpheusResponse.
        """
        t = word.key_pair()
        r = self.cnx.execute("select resp from cache where word = ? and lang = ?", t).fetchone()
        if r is None:
            return r
        else:  
            return pickle.loads(r[0])

    def zap(self):
        """Erase this cache's data table.
        Effect:
            immediate and cannot be rolled back. Does not drop the cache table.
        Returns:
            self.
        """
        self.cnx.execute("delete from cache")
        return self

    def update(self, resp):
        """Replace the response currently keyed to the argument's (word, lang)
        pair with the argument.
        Arg:
            MorpheusResponse.
        Returns:
            self.
        """
        w, l = resp.word().key_pair()
        self.cnx.execute("update cache set resp = ? where word = ? and lang = l", (pickle.dumps(resp), w, l))
        self.cnx.commit()
        return self

    def import_cache(self, cache, filter = None):
        """Import responses from a cache into this database.
        Args:
            cache: instance of class Cache.
            filter: a callable (w, lang, resp) -> bool.
        Raises:
            sqlite3.IntegrityError if a key violation would result from any
            insert operation.
        """ 
        self.cnx.executemany("insert into cache values (?,?,?)", cache.triples(filter)) 
        self.cnx.commit()

    @classmethod
    def default(cls):
        return cls('morpheuslib2.dbcache')
