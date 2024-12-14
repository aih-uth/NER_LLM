from openai import OpenAI
import anthropic

import os
import regex
import argparse
import unicodedata
import configparser
import xml.etree.ElementTree as ET
import tiktoken
import Levenshtein

import schema,document,annotation

llm = ''
LLM = { 'GPT':
        {'client': OpenAI(api_key=os.environ.get("OPENAI_API_KEY")),
         'model' : "gpt-4o-2024-05-13",
         'temperature':0.0,
         'too_long_label':'length',
         'MAX_TOKEN_LEN': 128000 },
        'CLAUDE':
        {'client' : anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY")),
         'model': 'claude-3-5-sonnet-20240620',
         'temperature':0.0,
         'too_long_label':'max_tokens',
         'max_tokens': 4096 } }


def token_count(string):
    enc = tiktoken.encoding_for_model("gpt-4o")
    return len(enc.encode(string))



def jsonize(string):
    """stringの前後にあるカッコ以外の文字列を削除する。GPTの出力としてJSON形式を想定している場合に使用する。
    """

    string = regex.sub('^[^\{\[]+', '', string).lstrip()
    string = regex.sub('[^\}\]]+$', '', string).rstrip()
    return string


def named_entity_recognition(input_text, prompt, NER_mode):
    """call OpenAI API to execute named entity recognition
    """

    instruction = ''
    if NER_mode['guideline']:
        gtype = 'guideline'
        if NER_mode['guideline'] == 'simple':
            gtype = 'entityType'
        instruction = prompt['instruction'] + '\n' + prompt[gtype] + "\n"

    instruction += '# input and output\n'
    for i in range(1,NER_mode['example_num']+1):
        instruction += prompt[f'example_{i}'] + '\n'
    messages = [
        {"role": "user", "content": f"{instruction}\n - input\n{input_text}\n - output\n"}
    ]

    fin_reason = ''
    if llm == 'GPT':
        response = LLM[llm]['client'].chat.completions.create(
            model=LLM[llm]['model'],
            messages=messages,
            temperature=LLM[llm]['temperature'],
        )
        fin_reason = response.choices[0].finish_reason

    elif llm == 'CLAUDE':
        response = LLM[llm]['client'].messages.create(
            model=LLM[llm]['model'],
            messages=messages,
            max_tokens=LLM[llm]['max_tokens'],
            temperature=LLM[llm]['temperature'],
        )
        fin_reason = response.stop_reason
    
    if response.stop_reason == LLM[llm]['too_long_label']:
        print("too long output. retry.")
        input_line = input_text.split('\n')
        line_n = int(len(input_line)/2)

        ret = named_entity_recognition('\n'.join(input_line[0:line_n]), prompt, NER_mode)
        ret += named_entity_recognition('\n'.join(input_line[line_n:]), prompt, NER_mode)
        return ret
    xml_string = response.content[0].text

    return xml_string



def annotate_entity(document, ner_file, prompt, NER_mode, ner_out_file='', force=False):
    if document is None:
        raise Exception('document is None')

    original_txt = '\n'.join([line['txt'] for line in document.txt])
    try:
        entity_xml = ''

        if force is False and ner_file:
            with open(ner_file) as f:
                entity_xml = f.read()

                sfx_o = original_txt.replace(' ','')[-10:]
                sfx_n = regex.sub(r'\<\/?[A-z].*?(?: [A-z].*?=".*?")*\>', '', entity_xml).replace(' ','')[-50:]
                if sfx_o not in sfx_n:
                    print(f' too long output??\noriginal:{sfx_o}\nnew:{sfx_n}')
                    entity_xml = ''

        n = 0
        while entity_xml == '':
            entity_xml += named_entity_recognition(original_txt, prompt, NER_mode) + '\n'
            n = n+1
            if n == 5:
                raise Exception("ERROR: LLM returns no string five times.")

    except Exception as e:
        print(e)

    finally:
        if ner_out_file:
            with open(ner_out_file, 'w') as out:
                out.write(entity_xml)

    try:
        document.txt = []
        document.load_xml(xml_string = entity_xml)
        document.update_txt(original_txt)

    except Exception as e:
        raise Exception('ERROR in annotate_entity: ' + str(e))
    return entity_xml



def annotate_file(file_name, input_dir, output_dir, schema, prompt, ner_file=''):
    doc = document.Document()
    doc.create_annotation_skeleton(schema)
    doc_id = file_name.replace('.txt','')
    print(f"input file:{doc_id}")
    try:
        doc.load_txt_file(f"{input_dir}/{file_name}")
        ner = annotate_entity(doc, ner_file, prompt, NER_mode, ner_out_file=f"{output_dir}/{doc_id}_ner.txt")

    except Exception as e:
        print('Error in annotation', str(e))

    try:
        with open(f"{output_dir}/{doc_id}.txt", 'w') as f:
            f.write("\n".join([line['txt'] for line in doc.txt]))
        doc.write_ann_file(f'{output_dir}/{doc_id}.ann')
    except Exception as e:
        print('Error while TXT/ANN file creation')

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='execute NER using LLM')
    parser.add_argument('-llm', metavar='LLM', help='GPT|CLAUDE', required=True)
    parser.add_argument('-d', metavar='INPUT_DIR', default='brat', help='input directory')
    parser.add_argument('-dout', metavar='OUTPUT_DIR', default='out', help='output directory')
    parser.add_argument('-E', metavar='EXAMPLE_COUNT', choices=[0,1,2], type=int, help='int. include #example in prompt', required=True)
    parser.add_argument('-gtype', metavar='GUIDELINE', default=None, choices=['detail','simple',None], help='guideline type')
    parser.add_argument('-corpus', metavar='CORPUS', choices=['i2b2-2014','i2b2-2012', 'MedTxt_CR'], help='corpus name', required=True)

    options = parser.parse_args()
    llm = options.llm
    NER_mode = {'example_num':options.E,
                'guideline':options.gtype,
                'corpus':options.corpus}

    #schema = schema.Schema(upper=True)
    schema = schema.Schema(filepath=f"schema/{options.corpus}.xlsx")
    prompt = {}
    for label in ['instruction', 'guideline','entityType']:
        with open(f'prompt/{options.corpus}/{label}.txt') as f:
            prompt[label] = f.read();
    
    print(llm, NER_mode)
    try:
        if options.d is not None:
            for file_ in sorted(os.listdir(options.d)):
                if file_.endswith('.txt'):
                    if 'example_2' not in prompt:
                        print(f'load {file_} as example')
                        doc = document.Document()
                        doc.create_annotation_skeleton(schema)
                        doc_id = file_.replace('.txt','')
                        doc.load_txt_file(f"{options.d}/{doc_id}.txt")
#                        doc.load(f"{options.d}/{doc_id}.ann", schema_=schema, upper=True)
                        doc.load(f"{options.d}/{doc_id}.ann", schema_=schema)
                        label = 'example_2'
                        if 'example_1' not in prompt:
                            label = 'example_1'
                        prompt[label] = " - input\n" + '\n'.join(line['txt'] for line in doc.txt) + "\n - output\n" + doc.to_xml() + "\n"
                        print("--- exemplar in prompt ---")
                        print(prompt[label])
                        continue

                    try:
                        ner_file = ''
                        doc_id = file_.replace('.txt', '')
                        if os.path.isfile(f"{options.dout}/{doc_id}_ner.txt") and os.path.getsize(f"{options.dout}/{doc_id}_ner.txt") > 0:
                            continue
                            ner_file = f"{options.dout}/{doc_id}_ner.txt"
                        annotate_file(file_, options.d, f"{options.dout}", schema, prompt, NER_mode, ner_file=ner_file)

                    except Exception as e:
                        print(f'Error: {e} skip {file_}')
    except KeyboardInterrupt:
        print("interrupt. ")
