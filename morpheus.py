import morpheuslib
import argparse
import sys
import urllib.error
import io
import datetime
import os.path
import pickle

def output2(arg):
    """ Return a file for writing or appending, or None if arg is None. """
    if arg:
        fn = arg
        if fn[0] == '+':
            fn = fn[1:]
            return open(fn, 'a')
        else:
            return open(fn, 'w')
    else:
        return None



class Output2:
    """ Handles lazy computation of output strings for echoing and saving. """
    def __init__(self, an, prolog_file, json_file, echo_arg, some):
        self.an = an
        self.prolog_file = prolog_file
        self.json_file = json_file
        self.echo_arg = echo_arg
        self.some = some
        self.prolog_str = None
        self.json_str = None
        
        
    def prolog(self):
        """ Lazily compute and return the Prolog clause for the Analysis."""
            
        
        if self.prolog_str is None:
            self.prolog_str = self.an.prolog(self.some)
        else:
            pass
        return self.prolog_str

    def json(self):
        """ Lazily compute and return JSON for the Analysis. """
        
        if self.json_str is None:
            self.json_str = self.an.json(self.some)
        else:
            pass
        return self.json_str
    
    def echo(self):
        """ Print output string. """
        if self.echo_arg == 'off':
            pass
        elif self.echo_arg == 'basic':
            print(self.an)
        elif self.echo_arg == 'prolog':
            print(self.prolog())
        elif self.echo_arg == 'json':
            print(self.json())
        
        else:
            pass
        
    def save(self):
        """ Save output string(s) to files as requested. """
        if self.prolog_file is None:
            pass
        else:
            self.prolog_file.write(self.prolog() + '\n')
            
        if self.json_file is None:
            pass
        else:
            self.json_file.write(self.json() + '\n')
            
class Commenter:
    """ Writes comments in output files. """
    def __init__(self, prolog_file, json_file):
        self.json_file = json_file
        self.prolog_file = prolog_file
        if prolog_file is not None:
            self.uq = morpheuslib.Unique()
        else:
            self.uq = None
            
    def register(self, an, c):
        """ Register the analysis' Prolog procedure name. """
        if self.prolog_file is None:
            pass
        else:
            self.uq.test(an.prolog_proc_name(c))
            
    def top_comment(self, _input, label, core, dt, st):
        """ Write a basic comment about file contents to output file(s)."""
        if self.prolog_file is None:
            pass
        else:
            self.prolog_file.write("%%\n")
            if self.prolog_file.mode == 'w':
                self.prolog_file.write("%% " + os.path.basename(self.prolog_file.name) + '\n')
            else:
                pass
            self.prolog_file.write("%% input: " + _input + ' starting at word ' + str(st) +'\n')
            self.prolog_file.write("%% date/time: " + str(dt) + '\n')
            self.prolog_file.write("%% label: " + label + '\n')
            self.prolog_file.write("%% core features: " + str(core) + '\n')
            self.prolog_file.write("%%\n")
            self.prolog_file.write("%% Paste :- dynamic directives (uncommented) over this comment.\n%%\n")
        if self.json_file is None:
            pass
        else:
            self.json_file.write("//\n")
            if self.json_file.mode == 'w':
                self.json_file.write("// " + os.path.basename(self.json_file.name) + '\n')
            else:
                pass
            self.json_file.write("// input: " + _input + ' starting at word ' + str(st) + '\n')
            self.json_file.write("// date/time: " + str(dt) + '\n')
            self.json_file.write("// label: " + label + '\n')
            self.json_file.write("// core features: " + str(core) + '\n')
            self.json_file.write("//\n")
            
    def prolog_bottom(self):
        """ Write a comment listing procedure names generated, and :-dynamic
            directives.
        """
        if self.prolog_file is None:
            pass
        else:
            self.prolog_file.write("\n%%\n")
            self.prolog_file.write("%% Names of Prolog procedures generated follow.\n")
            [self.prolog_file.write("%% " + n + '\n') for n in self.uq.set]
            self.prolog_file.write("%% To make any procedure dynamic, so that you can use\n")
            self.prolog_file.write("%% assert and retract with it, copy the appropriate\n")
            self.prolog_file.write("%% :-dynamic directive from this comment to before the first clause\n")
            self.prolog_file.write("%% in this file.\n")
            [self.prolog_file.write("%% :- dynamic " + n + '.\n') for n in self.uq.set]
            self.prolog_file.write("%%\n")
            
class Cache:
    def __init__(self, lang):
        self.lang = lang
        self.cache_add = 'none'
        self.cache_read = 'none'
        self.vola = {}
        # Try to open cachewords.
        try:
            g = open('cachewords.' + lang, 'r')
            ls = [l.rstrip() for l in g.readlines() if len(l) > 0 and l[0] != '#']
            g.close()
        except:
            ls = []
            
            
        # Try to open an existing cache.
        try:
            f = open(lang + '.cache', "rb")
            self.pers = pickle.load(f)
            
            f.close()
        except:
            self.pers = None

        if self.pers is None:
            if ls == []:
                self.init_msg = 'no persistent cache or cachewords file'
            else:
                self.pers = dict.fromkeys(ls)
                self.init_msg = 'new persistent cache initialized from cachewords'
        else:
            if ls == []:
                # Write the exiting keys.
                h = open('cachewords.' + lang, 'w')
                h.write('\n'.join(self.pers.keys()))
                h.close()
                self.init_msg = 'cachewords restored from cache keys'
            else:
                # Synchronize.
                di = {}
                
                i = 0
                j = 0
                for k in ls:
                    if k not in self.pers.keys():
                        i += 1
                        di[k] = None
                for k in self.pers.keys():
                    if k in ls:
                        j += 1
                        di[k] = self.pers[k]
                self.pers = di
                self.init_msg = 'cachewords and cache keys synchronized'
            
        
    def persistent(self):
        return  self.pers.keys()
    
    # cf. http://washort.twistedmatrix.com/2010/11/unicode-in-python-and-how-to-prevent-it.html
    def lookup(self, word):
        """ word : an instance of morpheuslib.Word. """
        # Word has to be cleansed of diacritics if beta code Greek.
        if word.lang == 'greek':
            w = morpheuslib.BetaCode.cleanse(word.word)
        else:
            w = word.word
            
        if w in self.pers:
            if self.pers[w] is None:
                self.cach_read = 'none'
                return None
            else:
                self.cache_read = 'persistent'
                return morpheuslib.Analyses(self.pers[w].decode('utf8'), word)
        elif w in self.vola:
            self.cache_read = 'volatile'
            return morpheuslib.Analyses(self.vola[w].decode('utf8'), word)
        else:
            self.cache_read = 'none'
            return None
        
    def cache(self, ans):
        #Beta Code cleaning...
        if ans.word.lang == 'greek':
            w = morpheuslib.BetaCode.cleanse(ans.word.word)
        else:
            w = ans.word.word
        
        if w in self.pers:
            self.cache_add = 'persistent'
            self.pers[w] = ans.text
        else:
            self.cache_add = 'volatile'
            self.vola[w] = ans.text

    def save(self):
        g = open(self.lang + '.cache', "bw")
        pickle.dump(self.pers, g)
        g.close()
        
    
    def size(self, cache):
        """ cache is 'vola' or 'pers'."""
        if cache == 'pers':
                   
            return len(pickle.dumps(self.pers))
        elif cache == 'vola':
                  
            return len(pickle.dumps(self.vola))          
        else:
            return -1
        
    def status_str(self, cache):
        """ cache is 'vola' or 'pers'."""
        sz = self.size(cache)
        if cache == 'pers':
            s = "permanent cache status\n"
            for k in self.pers.keys():
                if self.pers[k] is None:
                    s += (k + " no value yet\n")
                else:
                    s += (k + " value\n")
            s += ("rough size of cache: " + str(sz) + '\n')     
            return s
        elif cache == 'vola':
                  
            s = 'words in volatile cache\n' + '\n'.join(self.vola.keys()) + '\n'
            s +=     ("rough size of cache: " + str(sz) + '\n')
            return s          
        else:
            return 'no such cache'
            
        
def file_or_strio(s):
    """ If s can be opened as a file, return a file stream on file s, otherwise return a memory stream on string s. """
    try:
        f = open(s, 'r')
        return f
    except IOError:
        return io.StringIO(s)


def log(w, f, msg):
    """ Log Word w and msg string to file f. """
    if f is None:
        pass
    else:
        f.write(w.__str__() + ' ' + msg + '\n')
        
##def close_files(f1, f2, f3):
##    if f1 is None:
##        pass
##    else:
##        f1.close()
##        
##    if f2 is None:
##        pass
##    else:
##        f2.close()
##        
##    if f3 is None:
##        pass
##    else:
##        f3.close()

parser = argparse.ArgumentParser()
parser.add_argument("input", help="text string for analysis or path + file name of text")
parser.add_argument("lang", help = "language of words, greek or la", choices = ['greek', 'la'])
parser.add_argument("--core", help = "core features to export as JSON or Prolog. If not given, all core features are output.")
parser.add_argument("--json", help = "file for JSON output")
parser.add_argument("--prolog", help = "file for Prolog output")
parser.add_argument("--echo", help = "echo feature:value pairs to output", choices = ['basic', 'off', 'prolog', 'json'])
parser.add_argument("--label", help = "optional label for this text")
parser.add_argument("--log", help = 'optional file for logging words that returned no analyses.')
parser.add_argument("--start", type = int, help = "zero-based ordinal of word to start at (default is zero)")
args = parser.parse_args()

t = file_or_strio(args.input)

if args.label is None:
    lbl = 'no label'
else:
    lbl = args.label
    
ws = morpheuslib.WordStream(lbl, t, args.lang)

if args.core is None:
    c = morpheuslib.Analysis.core_features
else:
    c = args.core.split()

if args.start:
    st = args.start
else:
    st = 0
    

print("Terminators recognized:")
print(ws.terms)
print("Separators recognized:")
print(ws.seps)
print("Abbreviations recognized:")
print(ws.abbrs)
print("Input:")
print(args.input)
print("Processing starts at word " + str(st))

try:
    file1 = output2(args.json)
    print('json output to ' + file1.__str__()) 
except IOError as err:
    print(err)
    exit()

try:
    file2 = output2(args.prolog)
    print('Prolog output to ' + file2.__str__())
except IOError as err:
    print(err)
    exit()
    
try:
    file3 = output2(args.log)
    print('Logging to ' + file3.__str__())
except IOError as err:
    print(err)
    exit()
    
retained_ct = 0    
returned_ct = 0
dt = datetime.datetime.now()
log(dt, file3, ' '.join(sys.argv))
com = Commenter(file2, file1)
com.top_comment(args.input, lbl, c, dt, st)

ca = Cache(args.lang)
print (ca.init_msg)
for w in ws:
    print(w)

    if w.w < st:
        print("Skipping this word.")
        
    else:
        ans = ca.lookup(w)
        if ans is not None:
            print("Using  " + ca.cache_read + " cache for " + str(w))
            
        else:
            u = morpheuslib.MorpheusUrl(w)
            print(u)
        
            try:
                ans = u.fetch()
                ca.cache(ans)
                print("Cached " + str(w) + ' ' + ca.cache_add)
            except (urllib.error.HTTPError, urllib.error.URLError ) as err:
                print("Error contacting Perseus: {0}".format(err))
                log(w, file3, 'Run stopped on error ' + format(err))
                break
            except:
                print("Uncategorized error: {0}".format(err))
                log(w, file3, 'Run stopped on error ' + format(err))
                break
        
        ans_ct = ans.count()
        
        if ans_ct == 0:
            print("NO ANALYSES RETURNED.")
            log(w, file3, ' No analyses returned.')
        else:
            print(str(ans_ct) + " analyses returned.")
    
            
            returned_ct += ans_ct
            for an in ans:
                if an.pron_fix_err:
                    print('Latin pronoun not fixed ' + an.form()  + ' < ' + an.lemma())
                    log(w, file3, 'Latin pronoun not fixed ' + an.form()  + ' < ' + an.lemma())
                else:
                    pass
                com.register(an, c)

                o = Output2(an, file2, file1, args.echo, c)
                o.echo()
                o.save()
    
               
            if ans.retct == 0:
                print("NO ANALYSES RETAINED.")
                log(w, file3, ' No analyses retained.')
                [log(x.dud_str(), file3, '? (not retained)') for x in ans.non_ret]
            else:    
                print(str(ans.retct) + " analyses retained.")
            retained_ct +=  ans.retct
    
log(datetime.datetime.now(), file3, 'OPERATIONS ENDED.')
com.prolog_bottom()
if file1 is None:
    pass
else:
    file1.close()
if file2 is None:
    pass
else:
    file2.close()
if file3 is None:
    pass
else:
    file3.close()

ws.close()
print(ca.status_str('pers'))
print(ca.status_str('vola'))      
ca.save()
print("morpheus.py done. Text counts:")
print(str(ws.i - st) + " word(s) analyzed in")
print(str(ws.c) + " clauses;")
print(str(ws.s) + " sentences.")
print(str(retained_ct) + ' analyses retained out of ' + str(returned_ct) + " analyses returned.")
