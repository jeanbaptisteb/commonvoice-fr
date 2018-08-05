# -*- coding: utf-8 -*-
"""
Created on Thu Aug  2 21:12:29 2018

@author: Jean-Baptiste

This script is intended to retrieve content published on Wikipedia under the Creative Commons Zero licence
Currently, it only supports the French and English Wikipedia versions. 
It still requires a lot of improvements.

If you want to add support for an additional language, you'll probably need:
    * to customize the Spacy imports and models
    * to customize the mapping_lang_template dictionary 
    * to add some customized text cleaning process
    * to be a bit familiar with the structure of the Wikipedia version you're targetting (e.g. the concept of namespaces, revisions, etc.)
    * to do some extensive tests
"""

import requests
import time
import os
import re
from lxml import html
from utils import filter_numbers, maybe_normalize, extract_sentences, check_output_dir, set_custom_boundaries
import spacy
#import language_check #Wikipedia contributors sometimes make spelling mistakes!
import pypandoc
import argparse

parser = argparse.ArgumentParser(description='Wikipedia CC0 text content extraction for Common Voice')
parser.add_argument('--min-words', type=int, default=3, help='Minimum number of words to accept a sentence')
parser.add_argument('--max-words', type=int, default=15, help='Maximum number of words to accept a sentence')
#☺--type "creation" will retrieve only articles created by the user in their first version. On the other hand, --type "all_content" will retrieve any unique content the user added. The Wikipedia API makes it difficult to retrieve this second type of contributions, which explain why it takes so long to complete in the current version of this script.
parser.add_argument('--type', type=str, default="creation", help="Fetching article creation ('creation'), or all kind of content added by the contributor ('all_content'). Currently, the 'all_content' option can take more than 10 hours to complete; it's recommended to first try the 'creation' option, and if it doesn't return satisfying results, then you may try the 'all_content' option.")
parser.add_argument('--user', type=str, default=None, help="Retrieve content for a specific user, e.g. 'User:Mx. Granger'")
parser.add_argument('lang', type=str, help="The Wikipedia version we want to retrieve data from (e.g. 'fr' for French, 'en' for English, etc.")
parser.add_argument('output', type=str, help='Output directory')

args = parser.parse_args()
check_output_dir(args.output)

#TODO: internationalize spacy & nlp imports
spacy_models = {"fr":'fr_core_news_md',
                "en":"en_core_web_md"}
try:
    if args.lang == "fr":
        import fr_core_news_md #if it doesn't work, an alternative is: nlp = spacy.load('fr_core_news_sm') https://spacy.io/models/fr. See also line nlp = fr_core_news_sm.load(), at the bottom of the page
        nlp = fr_core_news_md.load()   #if it doesn't work, try: nlp = spacy.load('fr_core_news_sm'). See  imports, and https://spacy.io/models/fr, https://spacy.io/models/fr, etc.
    elif args.lang == "en":
        import en_core_web_md
        nlp = en_core_web_md.load()
        
except ModuleNotFoundError:
    from spacy.cli import download as spacy_model_download
    spacy_model_download(spacy_models[args.lang])
    nlp = spacy.load(spacy_models[args.lang])
    import nltk
    nltk.download('punkt')

nlp.add_pipe(set_custom_boundaries, before='parser') 
#tool = language_check.LanguageTool('fr-FR') #TODO for later

mapping_specific = [
  [ u'(', u''],
  [ u')', u''],
  [ re.compile('\. $'), u'.' ],
  [ re.compile(' \.'), u'.' ],
  [ u' ,  ', u', ' ],
  [ u' , ', u', ' ],
  [ u'  ', u' ' ],
]

#measure_units = {
#        "mm": "millimètre",
#        "°": "degré",
#        "cm":"centimètre",
#        "m.":"mètre",
#        "km":"kilomètre",
#             
#        }

mapping_lang_template = {"fr":{"template_name":"Modèle:Utilisateur_CC0", 
                               "user_prefix":"Utilisateur:",
                               "talk_prefix":"Discussion:"},
                         "en":{"template_name":"Template:CC-0 Release", 
                               "user_prefix":"User:",
                               "talk_prefix":"Talk:"}
                         }
#useful to check if the page is a translation
translation_templates = ["traduit de", "traduit par", "Translated page"]

def get_article_texts(lang, revid_list):
    url = "https://{lang}.wikipedia.org/w/api.php".format(lang=lang)
    query = {"action":"parse",
             "format":"json"
             }
    text_list = []
    for revid in revid_list:
        time.sleep(1)
        query["oldid"] = revid
        try:
            response = requests.post(url, data=query)
        except:
            time.sleep(30)
            response = requests.post(url, data=query)
        response = response.json()
        if "parse" not in response.keys(): #it's possible that the revision was since deleted, in this case there's nothing to parse
            continue
        raw_html = response["parse"]["text"]["*"]
        document = html.document_fromstring(raw_html)
        all_p = document.xpath("//p")
        for p in all_p:
            text = p.text_content()
            text = text.replace("\xa0", " ")
            #replacing by a space rather than by nothing, to ease the further string cleanup
            text = re.sub(r' \([^)]+\)', '', text) 
            text = re.sub(r'\([^)]+\)', '', text) 
            text = maybe_normalize(text)
            text = maybe_normalize(text, mapping=mapping_specific)
            text = re.sub(r'(\d)\s+(\d)', r'\1\2', text) #In French, there's a space separation between thousand units. It isn't taken into account by num2words, so just let's remove those spaces.
            #TODO: need to internationalize this part below
            #converting latlon coordinates
#            text = re.sub(r'([0-9]+) ?°([0-9]+) ?\'([0-9]+) ?\"', r"\1 degrés \2 minutes \3 secondes", text)
##            text = re.sub(r'-(\d*\.\d+|\d+)', "moins \1", text)
#            for measure in measure_units:
#                text = re.sub(r'(\[0-1]\[,.]\d+|\[0-1]) ?{measure}'.format(measure=measure), r"\1 {full_name}".format(full_name=measure_units[measure]), text)
#                text = re.sub(r'(\d*\[,.]\d+|\d+) ?{measure}'.format(measure=measure), r"\1 {full_name}s".format(full_name=measure_units[measure]), text)
#                
#            text = re.sub(r'(\[0-1]\[,.]\d+|\[0-1]) ?°', r"\1 degré", text)
#            text = re.sub(r'(\d*\[,.]\d+|\d+) ?°', r"\1 degrés", text)
#            text = re.sub(r'(\d*\[,.]\d+|\d+) ?mm', r"\1 millimètres", text)
#            text = re.sub(r'(\d*\[,.]\d+|\d+) ?cm', r"\1 centimètres", text)
#            text = re.sub(r'(\d*\[,.]\d+|\d+) ?m[^a-z]', r"\1 mètres ", text)
#            text = re.sub(r'(\d*\[,.]\d+|\d+) ?km', r"\1 kilomètres", text)
#            text = text.replace(" ?%", r" pour cent") 
            #remove references between brackets
            text = re.sub(r'\[[0-9]+\]', '', text) #r'\[[0-9]+*\]'
            #Transforming numbers in letters
            text = filter_numbers(text, lang=lang)
            text = text.strip()
#        text= " ".join([p.text_content().replace("\xa0", " ") for p in all_p])
            if "\n" in text:
                text = ""
#            text = text.replace("%", "pour cent") 
            if len(text.split()) > 3:
                #TODO: check content spelling
#                try:
#                    matches = tool.check(text)
#                    text = language_check.correct(text, matches)
#                except Exception as e:
#                    print(text)
#                    print("erreur correction : ", str(e))
#                    print(revid)
#                    print("*"*20)
                text_list.append(text)
        
    return text_list


def get_user_list(lang, template_name):
    url = "https://{lang}.wikipedia.org/w/api.php".format(lang=lang) 
    user_list = []
    eicontinue = None
    query = {"action":"query",
             "list":"embeddedin",
             "eititle":template_name, #Mod%C3%A8le:Utilisateur_CC0&"}
             "einamespace":"2",
             "format":"json"
             }
    while True:
        if eicontinue != None: #=2|9655949
            query["eicontinue"] = eicontinue 
        r = requests.post(url, data=query)
#        r = requests.get(url, params=query)
        response = r.json()
        for page in response["query"]["embeddedin"]:
            name = page["title"].replace(mapping_lang_template[args.lang]["user_prefix"], "")
            if "/" not in name: #if there's a slash, the template in embedded in a subpage, so it's not obvious that the user publishes her contribution under CC0
                user_list.append(name)
            
        if "continue" in response.keys():
            eicontinue = response["continue"]["eicontinue"]
        else:
            break
    return user_list


def get_added_content(url, revid, lang):
    
    compare_query = {"action":"compare",
                     "fromrev":revid,
                     "torelative":"prev",
                     "prop":"rel|diffsize|size|diff|title",
                     "format":"json"}
#    print(compare_query)
    response = requests.post(url, params=compare_query).json()
    if "compare" not in response.keys():
        return None
    revid_size = response["compare"]["tosize"]
    if "prev" in response["compare"].keys(): #If there are previous revisions, we need to check if the current revision isn't a derivative work (i.e. a revert)
        #Check if it's a revert
        rvcontinue = None
        revid_size = 0
        while True:
            #Let's compare the current and previous revisions of the page
            pr_query = {"action":"query", "prop":"revisions", 
                    "rvprop":"ids|tags|size", "format":"json",
#                    "revids":previous_revision_id 
                    "rvendid":revid,
                    "titles":response["compare"]["totitle"]
                    } #for retrieving a list of previous revisions until the current one            
            if rvcontinue != None:
                pr_query["rvcontinue"] = rvcontinue
            pr_response = requests.post(url, pr_query).json()
            for page in pr_response["query"]["pages"]:
                #Check if the current revision is a revert.
                for revision in pr_response["query"]["pages"][page]["revisions"]:
#                    print(revision.keys())
                    if revision["revid"] == revid:                        
                        revid_tags = revision["tags"]
                        if "mw-rollback" in revid_tags: #Here, we're sure it's a revert
                            return None
                        continue
                    #If this previous revision has the same size of the current revision, maybe the revision we want to retrieve is a revert. Let's be conservative, and consider it is.
                    if revision["size"] == revid_size: 
                        return None
            if "continue" in pr_response.keys():
                rvcontinue = pr_response["continue"]["rvcontinue"]
            else:
                break
    #Now, let's retrieve the revision content!
    raw_html = response["compare"]["*"]
    document = html.document_fromstring(raw_html)
    added_lines = document.xpath("//td[@class='diff-addedline']")
#        deleted_lines = document.xpath("//td[@class='diff-deletedline']")
    text_list = []
    for td in added_lines:
        for div in td:
            if len(div.getchildren()) > 0: #if there are children tags, it's because this is an inline modification, and not an addition -> skip it                
                continue
            else:
                text = div.text_content()
                if "#REDIRECT" in text:  
                    return None
                try:
                    #this line checks if there's garbage in wikicode
#                    text = pypandoc.convert_text(text, to="plain", format="html").replace("\r\n", " ")
                    #if not, we convert the mediwiki code to html
                    text = pypandoc.convert_text(text, to="html", format="mediawiki").replace("\r\n", " ")
                    #and we retrieve the real plain text
                    #TODO: add cleaning up of (), [], etc.
                    text = html.document_fromstring(text)
                    text = text.text_content()
                    text = text.replace("\xa0", " ")
                    #replacing by a space rather than by nothing, to ease the further string cleanup
                    text = re.sub(r' \([^)]+\)', '', text) 
                    text = re.sub(r'\([^)]+\)', '', text) 
                    text = maybe_normalize(text)
                    text = maybe_normalize(text, mapping=mapping_specific)
                    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text) #In French, there's a space separation between thousand units. It isn't taken into account by num2words, so just let's remove those spaces.
                    #TODO: need to internationalize this part below
                    #converting latlon coordinates
#                    text = re.sub(r'([0-9]+) ?°([0-9]+) ?\'([0-9]+) ?\"', r"\1 degrés \2 minutes \3 secondes", text)
        #            text = re.sub(r'-(\d*\.\d+|\d+)', "moins \1", text)
#                    for measure in measure_units:
#                        text = re.sub(r'(\[0-1]\[,.]\d+|\[0-1]) ?{measure}'.format(measure=measure), r"\1 {full_name}".format(full_name=measure_units[measure]), text)
#                        text = re.sub(r'(\d*\[,.]\d+|\d+) ?{measure}'.format(measure=measure), r"\1 {full_name}s".format(full_name=measure_units[measure]), text)
#                    text = text.replace(" ?%", r" pour cent") 
                    #remove references between brackets
                    text = re.sub(r'\[[0-9]+\]', '', text) #r'\[[0-9]+*\]'
                    #Transforming numbers in letters
                    text = filter_numbers(text, lang=lang)
                    text = text.strip()
                except:
                    continue #if pandoc cannot convert wikicode, there's a problem, and we don't want to retrieve malformed text
                if len(text.split()) > 3: #Let's not retrieve too short text
                    text_list.append(text)
    return " ".join(text_list)


print("Retrieving CC0 user list")
if args.user == None:
    #generate a list of tuples (user, licence), if later we want to retrieve other licences than CC0
    CC0_user_list = [(user, "CC0") for user in get_user_list(args.lang, mapping_lang_template[args.lang]["template_name"])]
else:
    CC0_user_list = [(user, "CC0") for user in args.user.split(";")]
print("User list retrieved")
translations = {}
for user, licence in CC0_user_list:
    revid_list = []
    uccontinue = None
    text_list = []
    print("Processing user", user, "(https://{lang}.wikipedia.org/wiki/{prefix}{user})...".format(lang=args.lang, prefix=mapping_lang_template[args.lang]["user_prefix"], user=user))    
    while True:
        time.sleep(1) #Let's give Wikimedia servers a rest
        query = {"action":"query",
                 "list":"usercontribs",
                 "ucuser":user,
                 "uclimit":"500",
                 "ucnamespace":"0",
                 "format":"json",
                 "ucprop":"ids|title|timestamp|comment|size|flags|tags"
                 }
        if uccontinue != None:
            query["uccontinue"] = uccontinue        
        url = "https://{lang}.wikipedia.org/w/api.php".format(lang=args.lang)
        r = requests.post(url, data=query)            
        my_json = r.json()        
        #TODO: exclude reverts
        for contrib in my_json["query"]["usercontribs"]:                    
            if "minor" not in contrib.keys() and ("tags" in contrib.keys() and "mw-new-redirect" not in contrib["tags"] and "contenttranslation" not in contrib["tags"]) and ("comment" in contrib.keys() and "redirect" not in contrib["comment"]):
            #Let's exclude : minor edits, redirections, and translations (not under CC0 licence)
                #Let's double check if it's not a translation:
                discussion_page_title = mapping_lang_template[args.lang]["talk_prefix"] + contrib["title"]                
                if discussion_page_title not in translations.keys():                                      
                    #check if the page is a translation
                    discussion_query = {"action":"query", "prop":"revisions", 
                        "rvprop":"content", "format":"json",
                        "titles":discussion_page_title }
                    try:
                        discussion_response = requests.post(url, data=discussion_query).json()["query"]["pages"]
                    except:
                        print(url, discussion_query)
                        time.sleep(10)
                        try:
                            discussion_response = requests.post(url, data=discussion_query).json()["query"]["pages"]
                        except:
                            print(url, discussion_query)
                            continue
                    translation = False
                    translations[discussion_page_title] = False
                    #Check if there's a template "translated from" in the discussion page. If so, the extrated data is maybe not under a CC0 license.
                    for page in discussion_response:
                        if "revisions" in discussion_response[page].keys():
                            discussion_content = discussion_response[page]["revisions"][0]["*"]
                            for template_name in translation_templates:
                                if "{{"+template_name in discussion_content:
                                    translation = True
                                    translation[discussion_page_title] = True
                                    print("Translation from", contrib["title"], "excluded")
                        #not "else" here, because the discusion page may be inexistant
                if translations[discussion_page_title] == True:
                        continue
                elif translations[discussion_page_title] == False: #There's a chance the content is a translation, and therefore not under a CC0 licence. Let's be conservative, and don't retrieve the content
                    #if we want to retrieve any kind of contribution
                    if args.type == "all_content": 
                        try:                        
                            text_list.append(get_added_content(url, contrib["revid"], args.lang))
                            text_list.append()
                        except:
                            continue
                    #if we want to retrieve only page creations (faster)
                    elif args.type == "creation" and "new" in contrib.keys(): 
                        revid_list.append(str(contrib["revid"]))                        
        #Retrieving the uccontinue value to go to the next page of contributions        
        if "continue" in my_json.keys():
            try:
                uccontinue = my_json["continue"]["uccontinue"]
            except:
                break                        
        else:
            break
    time.sleep(30) #Gives Wikimedia servers a rest
    print("Extracting sentences")
    if args.type == "creation":       
        text_list = get_article_texts(args.lang, revid_list)    
    else:
        text_list = list(filter(None, text_list))
    extracted_sentences = list(extract_sentences(text_list,args.min_words, args.max_words,nlp=nlp))
    print(len(extracted_sentences), "sentences retrieved")
    if len(extracted_sentences) > 0: #If we extrated at least one sentence...
        with open(os.path.join(args.output, "_".join([str(user), str(licence)]) + ".txt" ), "wb") as f:
            for sentence in extracted_sentences:
                f.write(str(sentence + " \n").encode("utf8"))
    print(user, "contributions retrieved")
print("Done.")

