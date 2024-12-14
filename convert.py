import xml.etree.ElementTree as ET
import os
import sys
import argparse
import regex
import schema,document,annotation

def convert_i2b2_2014(indir, outdir, file_name, schema):

    doc_id = file_name.replace(".xml","")

    doc = document.Document()
    doc.create_annotation_skeleton(schema)
    
    root = ET.parse(f"{indir}/{file_name}")
    text = ""
    for item in root.findall("./TEXT"):
        text = "".join(item.itertext())
        doc.update_txt(text)
    doc.write_txt_file(f"{outdir}/{doc_id}.txt")

    for tags in root.findall("./TAGS"):
        for tag in tags:
            type_val = tag.get('TYPE') or tag.tag
            region = set()
            for i in range(int(tag.get('start')), int(tag.get('end'))):
                region.add(i)
            mid = doc.annotation.create_mention(tag.tag, region)
            doc.annotation.set_attribute(mid, 'TYPE', type_val, upper=True)
    doc.write_ann_file(f"{outdir}/{doc_id}.ann")



def convert_i2b2_2012(indir, outdir, doc_id):
    doc = document.Document()
    doc.create_annotation_skeleton(schema)
    
    line = []
    with open(f"{indir}/{doc_id}.xml.txt") as f:
        pos = 0
        for line_ in f:
            line_ = line_.rstrip('\n')
            w_pos = pos
            word = []
            for w in regex.split(r'(\s+)',line_):
                if w == '':
                    continue
                elif regex.match(r'\s',w):
                    w_pos += len(w)
                else:
                    word.append({'start':w_pos,'end':w_pos+len(w)})
                    w_pos += len(w)
            line.append({'txt':line_, 'word':word, 'index':pos})
            pos += len(line_) + 1
    doc.update_txt('\n'.join(l['txt'] for l in line))

    with open(f"{indir}/{doc_id}.xml.extent") as f:
        for tag_line in f:
            # EVENT="Admission" 1:0 1:0||type="OCCURRENCE"||modality="FACTUAL"||polarity="POS"
            m = regex.match('^(EVENT|TIMEX3)="(.+?)" (\d+)\:(\d+) (\d+):(\d+)\|\|(.*)',tag_line.strip())
            if m:
                tag = m.group(1)
                surface = m.group(2)
                start_line_n = int(m.group(3))-1
                start_word_n = int(m.group(4))
                last_line_n = int(m.group(5))-1
                last_word_n = int(m.group(6))

                start = line[start_line_n]['word'][start_word_n]['start']
                end = line[last_line_n]['word'][last_word_n]['end']

                region = set()
                for i in range(int(start), int(end)):
                    region.add(i)
                try:
                    mid = doc.annotation.create_mention(tag, region)
                
                    for f_pair in m.group(7).split('||'):
                        f,v = f_pair.split('="')
                        v = v[0:-1]
                        doc.annotation.set_attribute(mid, f, v, upper=True)
                except Exception as e:
                    print(e)
    doc.write_ann_file(f"{outdir}/{doc_id}.ann")
    doc.write_txt_file(f"{outdir}/{doc_id}.txt")

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='convert i2b2_2012/i2b2_2014/MedTxt_CR corpus into offset format')
    parser.add_argument('-corpus', metavar='CORPUS', help='corpus name. i2b2_2012 or i2b2_2014 or MedTxt_CR', choices=['i2b2_2012','i2b2_2014','MedTxt_CR'], required=True)
    parser.add_argument('-d', metavar='INPUT_DIR', help='input directory which contains corpus files. Specify path to "testing-PHI-Gold-fixed" for i2b2_2014, "ground_truth/unmerged_i2b2" for i2b2_2012, and directory in which "MedTxt-CR-JA-training-pub.xml" is contained.', required=True)
    parser.add_argument('-dout', metavar='OUTPUT_DIR', help='output directory', required=True)
    options = parser.parse_args()

    upper_ = True
    if options.corpus == 'MedTxt_CR':
        upper_ = False
    schema = schema.Schema(upper=upper_, filepath=f"schema/{options.corpus}.xlsx")
    
    for file_name in os.listdir(options.d):
        if options.corpus == 'i2b2_2014':
            convert_i2b2_2014(options.d, options.dout, file_name)
        elif options.corpus == 'i2b2_2012':
            if file_name.endswith('.txt'):
                doc_id = file_name.replace('.xml.txt','')
                convert(dir_name, out_dir, doc_id)
            
        elif options.corpus == 'MedTxt_CR':
            if file_name != 'MedTxt-CR-JA-training-pub.xml':
                continue
            root = ET.parse(file_name)
            for article in root.findall('./articles/article'):
                doc_id = article.get('id')
                article_content = ''.join(ET.tostring(child, encoding='unicode') for child in article)
                doc = document.Document()
                doc.create_annotation_skeleton(sch)
                doc.load_xml(xml_string=article_content)
                doc.write_ann_file(f"{out_dir}/{doc_id}.ann")
                doc.write_txt_file(f"{out_dir}/{doc_id}.txt")
    
