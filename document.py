import os
import regex
import sys
import time
import copy
import difflib

import schema
import annotation

class Document:

    def __init__(self):
        self.txt = []

    def load_txt_file(self, txt_file_path):
        """アノテーション対象の生テキストをファイルから読み込む。

        """

        if os.path.exists(txt_file_path) is False:
            raise
        with open(txt_file_path) as f:
            pos = 0
            for line in f:
                self.txt.append({'index':pos, 'txt':line.rstrip('\n')})
                pos += len(line)
            self.txt_len = pos

    def write_txt_file(self, out_file_path):
        with open(out_file_path, 'w') as out:
            out.write('\n'.join([line['txt'] for line in self.txt]))

    def create_annotation_skeleton(self, s):
        self.annotation = annotation.Annotation(s)
        
    def load(self, file_path, schema_=None, upper=False):
        if os.path.exists(file_path) is False:
            raise

        if schema_ is None:
            schema_ = schema.Schema()
        self.annotation = annotation.Annotation(schema_)
        with open(file_path) as f:
            for line in f:
                columns = line.rstrip().split("\t")
#                label, info, surface

                # ラベルから注釈の種類とIDを取得します
                match = regex.match(r'^([A-z\#\*])([0-9]*)$', columns[0])
                ann_c, ann_id = match.groups()
                if ann_id != '':
                    ann_id = int(ann_id)

                if ann_c == 'T':
                    # タグと位置情報を取得
                    tag, region_str = columns[1].split(" ", maxsplit=1)
                    if upper:
                        tag = tag.upper()
                    region = set()
                    for r_ in region_str.split(';'):
                        b_, e_ = r_.split(' ')
                        for i in range(int(b_), int(e_)):
                            region.add(i)
                    # データを辞書に追加
                    try:
                        self.annotation.create_mention(tag, region, ann_id)
                    except:
                        ''

                elif ann_c == 'A':
                    columns_ = columns[1].split(" ")
                    tag, tgt_id = columns_[0], columns_[1]
                    tgt_id = int(tgt_id.lstrip('T'))
                    value = columns_[2] if len(columns_) == 3 else ''
                    try:
                        self.annotation.set_attribute(tgt_id, tag, value, upper=upper)
                    except:
                        ''

                elif ann_c == 'R':
                    r_name, src, tgt = columns[1].split(" ")
                    src = int(src.replace("Arg1:", "").lstrip('T'))
                    tgt = int(tgt.replace("Arg2:", "").lstrip('T'))
                    try:
                        self.annotation.create_relation(src, tgt, r_name)
                    except:
                        ''

                elif ann_c == '#':
                    match = regex.search(r'AnnotatorNotes (.+)', columns[1])
                    if match:
                        tgt_id = int(match.group(1).lstrip('T'))
                        try:
                            self.annotation.set_note(tgt_id, columns[2])
                        except:
                            ''
                            
                elif ann_c == '*':
                    match = regex.match(r'([^ ]+) (.+)', columns[1])
                    if match:
                        rel, ids_str = match.groups()
                        ids = {int(tid.lstrip('T')) for tid in ids_str.split(" ")}
                        try:
                            self.annotation.create_equal_group(ids)
                        except:
                            ''

                elif ann_c == 'N':
                    match = regex.match(r'Reference ([^\s]+) (.+?)\:(.+)', columns[1])
                    if match:
                        tgt, algorithm, code = match.groups()
                        tgt = int(tgt.lstrip('T'))
                        try:
                            self.annotation.set_vocab_mapping(tgt, algorithm, 'CUI', code, columns[2])
                        except:
                            ''

                else:
                    print("unexpected: ", line)
                    continue


    def load_xml(self, xml_string='', file_path='', upper=False):
#        self.annotation = annotation.Annotation(schema.Schema())
        if len(xml_string) > 0:
            # 初期位置
            tag_stack = []
            pos = 0 if len(self.txt) == 0 else self.txt[-1]['index']+len(self.txt[-1]['txt'])+1

            pos_ = pos
            for line in regex.sub(r'<([^\s>]+)(?: ([^>\s"]+?=".*?"))?>', '', xml_string).split('\n'):
                self.txt.append({'index': pos_, 'txt': line})
                pos_ += len(line) + 1

            pattern = regex.compile(r'(.*?)<([^\s>]+)(?: ([^>\s"]+?=".*?"))?>', regex.DOTALL)
            for match in regex.finditer(pattern, xml_string):
                # タグの種類とテキストを取得
                text = match.group(1)
                tag = match.group(2)
                attributes = match.group(3)
                pos = pos + len(text)
                for tag_ in tag_stack:
                    tag_['text'] = tag_['text'] + text

                if tag[0] == '/':
                    tag = tag[1:]
                    # アノテーションを追加
                    if len(tag_stack) == 0 or tag not in [t['tag'] for t in tag_stack]:
                        print(f'warning: no start tag of {tag}')
                        continue
                    while tag_stack[-1]['tag'] != tag:
                        tag_stack.pop(-1)
                    region = set( range(tag_stack[-1]['start_pos'], tag_stack[-1]['start_pos'] + len(tag_stack[-1]['text'])) )

                    try:
                        mid = self.annotation.create_mention( tag_stack[-1]['tag'].upper(), region)
                        for attr in tag_stack[-1]['attribute']:
                            value = tag_stack[-1]['attribute'][attr] if tag_stack[-1]['attribute'][attr] != '' else ''
                            #self.annotation.set_attribute(mid,attr,value.lower())
                            self.annotation.set_attribute(mid,attr,value,upper=upper)
                    except:
                        ''
                    tag_stack.pop(-1)

                else:
                    tag_stack.append({'tag': tag, 'attribute':{}, 'text': '', 'start_pos':pos})
                    if attributes is not None:
                        matches = regex.findall(r'(\w+)="([^"]+)"', attributes)
                        av = {key: value for key, value in matches}
                        for attr_type in av:
                            tag_stack[-1]['attribute'][attr_type] = av[attr_type]
            self.txt_len = self.txt[-1]['index'] + 1 + len(self.txt[-1]['txt'])
        

    def extract_line(self, line_number):
        '''
        このdocumentの指定の行のみから構成されるdocumentを返す
        行番号は1始まり
        '''

        if line_number > len(self.txt):
            raise Exception('too large line_number')

        line = Document()
        line.txt.append({'index':0, 'txt':self.txt[line_number-1]['txt']})
        line.txt_len = len(self.txt[line_number-1]['txt'])
        begin = self.txt[line_number-1]['index']
        line.annotation = annotation.Annotation(self.annotation.get_schema())
        for mid in self.annotation.get_mention_id_in_range(set(range(begin,begin+line.txt_len))):
            line.annotation.create_mention( self.annotation.entity_type(mid),
                                            {pos - begin for pos in self.annotation.region(mid)},
                                            mid )
            for attr in self.annotation.get_attribute(mid):
                line.annotation.set_attribute(mid, attr['type'], attr['value'])
                
            line.annotation.set_note(mid, self.annotation.get_note(mid))

            for term in self.annotation.get_vocab_mapping(mid):
                line.annotation.set_vocab_mapping(mid,
                                                  term['resource'],
                                                  term['system'],
                                                  term['code'],
                                                  term['term'])

        for rel in self.annotation.get_relation():
            if( line.annotation.exists_mention_id(rel['src']) and
                line.annotation.exists_mention_id(rel['tgt']) ):
                line.annotation.create_relation(rel['src'], rel['tgt'], rel['type'])
                
        for equals in self.annotation.get_equal_group():
            ids = set()
            for mid_ in equals:
                if line.annotation.exists_mention_id(mid_):
                    ids.add(mid_)
            if len(ids) > 1:
                line.annotation.create_equal_group(ids)
                
        return line
    

    def surface(self, region):
        txt = '\n'.join([line['txt'] for line in self.txt])
        index_list = sorted(list(region))
        surface = ''
        for i in range(0, len(index_list)):
            if i>0 and index_list[i-1] + 1 < index_list[i]:
                surface += ' '
            surface += txt[index_list[i]]
        return surface

    def char_at(self, index):
        txt = '\n'.join([line['txt'] for line in self.txt])
        return txt[index]
        
    def get_line_number_of_mid(self, mention_id):
        line_n = 0
        region_list = self.annotation.region_list(mention_id)
        while region_list[0] > self.txt[line_n]['index'] + len(self.txt[line_n]['txt']):
            line_n += 1
        return line_n
        

    def write_ann_file(self, out_file=None, tid_refresh=0):
        out_file = out_file or str(time.time()) + '.ann'


        with open(out_file, 'w') as out:
            tid = {}
            aid = 0
            nid = 0
            rid = 0
            noteid = 0

            for mid in self.annotation.get_mention_id():
                tid[mid] = 'T' + str(len(tid) + 1) if tid_refresh == 1 else 'T'+str(mid)

                region = []
                index_list = self.annotation.region_list(mid)

                n_flg = False
                for i in range(0, len(index_list)):
                    # 開始
                    if n_flg:
                        if self.char_at(index_list[i]) == '\n':
                            continue
                        else:
                            region.append(str(index_list[i]))
                            n_flg = False
                        
                    elif i == 0:
                        region.append(str(index_list[i]))

                    elif index_list[i-1]+1 < index_list[i]:
                        region.append(str(index_list[i]))
                        n_flg = False

                    elif self.char_at(index_list[i]) == '\n':
                        region[-1] += ' ' + str(index_list[i]-1)
                        n_flg = True
                        continue

                    # 終了
                    if i==len(index_list)-1 or index_list[i]+1 < index_list[i+1]:
                        if index_list[i] == self.txt_len:
                            region[-1] += ' ' + str(index_list[i])
                            
                        else:
                            region[-1] += ' ' + str(index_list[i]+1)


                out.write('\t'.join([
                    tid[mid],
                    self.annotation.entity_type(mid) + ' ' + ';'.join(region),
                    self.surface(self.annotation.region(mid)).replace('\n', ' ')
                ]) + '\n')
                
                for attr in self.annotation.get_attribute(mid):
                    aid += 1
                    out.write(f"A{aid}\t{attr['type']} {tid[mid]}")
                    if len(attr['value']) > 0:
                        out.write(f" {attr['value']}")
                    out.write("\n")

                for term in self.annotation.get_vocab_mapping(mid):
                    nid += 1
                    out.write(f"N{nid}\tReference {tid[mid]} {term['resource']}:{term['code']}\t{term['term']}\n")

                if len(self.annotation.get_note(mid)) > 0:
                    noteid += 1
                    out.write(f"#{noteid}\tAnnotatorNotes {tid[mid]}\t{self.annotation.get_note(mid)}\n")

            for rel in self.annotation.get_relation():
                rid += 1
                out.write(f"R{rid}\t{rel['type']} Arg1:{tid[rel['src']]} Arg2:{tid[rel['tgt']]}\n")

            for egrp in self.annotation.get_equal_group():
                out.write("\t".join(["*", 'equivalent'+' ' +  ' '.join(tid[x] for x in egrp)]) + "\n")




    def update_txt(self, new_txt):
        '''
        テキストをnew_txtに変更し、アノテーションのインデックス情報をnew_txtに合わせて修正する
        '''
        index_map = []

#        print('---GPT---')
#        print('\n'.join([line['txt'] for line in self.txt]))
#        print('---GOLD---')
#        print(new_txt)
        try:
            sm = difflib.SequenceMatcher(None, list('\n'.join([line['txt'] for line in self.txt])), list(new_txt), autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ['replace', 'equal']:
                    for i, pos in enumerate(range(i1,i2)):
                        index_map.append( j1 + i )
                elif tag == 'delete':
                    for i, pos in enumerate(range(i1,i2)):
                        index_map.append(-1)
            delete_mid = []

            for mid in self.annotation.get_mention_id():
#                print(f"T{mid}: {self.surface(self.annotation.region(mid))}")
                new_index_list = []
                old_index_list = self.annotation.region_list(mid)
                for old_i, pos in enumerate(old_index_list):
                    if index_map[pos] != -1 or new_txt[index_map[pos]] in [' ', '　', '\t']:
                        if( new_index_list and
                            regex.match(r'^[ 　\t]+$', new_txt[new_index_list[-1]+1:index_map[pos]]) ):
                            for pos_ in range(new_index_list[-1]+1, index_map[pos]):
                                new_index_list.append( pos_ )
                        new_index_list.append( index_map[pos] )
#                print(new_index_list)
                while new_index_list and new_txt[new_index_list[0]] in [' ', '　', '\t']:
#                    print(f"「{new_txt[new_index_list[0]]}」")
                    del new_index_list[0]
                while new_index_list and new_txt[new_index_list[-1]] in [' ', '　', '\t']:
                    del new_index_list[-1]
                
                if new_index_list:
                    self.annotation.set_mention(mid, set(new_index_list))
                else:
                    delete_mid.append(mid)

            for mid in delete_mid:
                self.annotation.delete_mention(mid)

            self.txt = []
            pos = 0
            for line in new_txt.split('\n'):
                self.txt.append({'index':pos, 'txt':line})
                pos += len(line)+1
        except Exception as e:
            print('ERROR in update_txt:', e)
            raise
        else:
            self.txt_len = pos
#        print('update_txt end.')

            

    def bio(self, except_attr=False):
        '''
        BIOタグのシーケンスを返す。改行文字を含まないテキストに対してのシーケンスであることに注意
        '''
        bio = ['O' for _ in range(0,len(self.txt))]

        for tid in sorted(self.ann['T'].keys(), key=lambda t: (self.ann['T'][t]['begin'], self.ann['T'][t]['end'])):
            if self.ann['T'][tid]['tag'] in ['EL', 'EL_umls', 'EL_tmp','info']:
                continue

            tag = self.ann['T'][tid]['tag']
            if except_attr is False:
                attr = ''
                patient_attr = ''
                stop_attr = ''
                if tid in sorted(self.ann['A']):
                    for attr_name in self.ann['A'][tid]:
                        if attr_name in ['finding_type', 'execute_type', 'execute_by_patient']:
                            continue
                        elif attr_name == 'patient':
                            if tag in ['PN','judge','state','value','quantity_evaluation','quality_evaluation','quality_progress','quantity_progress','body','tissue','function','activity','job','smoking','drinking','age','sex','allergy','person','gene']:
                                patient_attr = '-patient'
                            continue
                        elif attr_name == 'family':
                            if patient_attr != '-patient':
                                patient_attr = '-family'
                            continue
                        elif attr_name == 'Stop':
                            stop_attr = 'stop'
                            continue
                        attr_val = regex.sub(r'^\d_','',self.ann['A'][tid][attr_name])
                        if len(attr_val) == 0:
                            attr_val = attr_name
                        attr += '-' + attr_val

                if patient_attr == '' and tag in ['PN','judge','state','value','quantity_’evaluation','quality_evaluation','quality_progress','quantity_progress','body','tissue','function','activity','job','smoking','drinking','age','sex','allergy','person','gene']:
                    patient_attr = '-others'
                if stop_attr == '' and tag in ['smoking', 'drinking']:
                    stop_attr = '-current'
                tag += attr + stop_attr + patient_attr

            for pos in self.ann['T'][tid]['region']:
                if pos ==self.ann['T'][tid]['begin'] or bio[pos-1] not in [f"B-{tag}", f"I-{tag}"]:
                    bio[pos] = f"B-{tag}"
                else:
                    bio[pos] = f"I-{tag}"

        bio_without_newline = []
        for i in range(0,len(bio)):
            if self.txt[i] != '\n':
                bio_without_newline.append(bio[i])
        return bio_without_newline

    def to_xml(self, id_flg=False, attr_flg=True):
        char = []
        for line in self.txt:
            for c in line['txt']:
                char.append({'c':c, 'mid':{'start':[], 'end':[]}})
            char.append({'c':'\n', 'mid':{'start':[], 'end':[]}})

        for mid in self.annotation.get_mention_id():
            region = self.annotation.region_list(mid)
            char[region[0]]['mid']['start'].append(mid)
            char[region[-1]]['mid']['end'].append(mid)

        xml = ''
        for c in char:
            if c['mid']['start']:
                for mid in sorted(c['mid']['start'], key=lambda t:self.annotation.region_list(t)[-1]-self.annotation.region_list(t)[0], reverse=True):
                    attr = ''
                    if attr_flg:
                        attr = ' '.join([at['type']+'="'+at['value']+'"' for at in self.annotation.get_attribute(mid)])
                        if attr:
                            attr = ' ' + attr
                    id_str = ''
                    if id_flg:
                        id_str = f' id="{mid}"'
                    xml += f"<{self.annotation.entity_type(mid)}{attr}{id_str}>"
            xml += c['c']
            if c['mid']['end']:
                for mid in sorted(c['mid']['end'], key=lambda t:self.annotation.region_list(t)[-1]-self.annotation.region_list(t)[0]):
                    xml += f"</{self.annotation.entity_type(mid)}>"

        return xml


if __name__ == "__main__":
    d=Document()
#    print('argument:', sys.argv[1])
    d.load('corpus/20240418/conl/HPO_public/001_case1.ann')
    d.load_txt_file('corpus/20240418/conl/HPO_public/001_case1.txt')

    print(d.to_xml(id_flg=True,attr_flg=False))
    '''
    d.write_ann_file('test.ann')
    
    d2=d.extract_line(2)
    d2.write_ann_file('test2.ann')
    d2.write_txt_file('test2.txt')

    new_txt = '\n'.join([line['txt'] for line in d.txt])
    new_txt = new_txt[2:]
    d.update_txt(new_txt)
    d.write_ann_file('test_update.ann')
    d.write_txt_file('test_update.txt')
    #d2.load('../../brat/data/iCorpus/gpt_annotation.ann')
    #d2.load_txt_file('../../brat/data/iCorpus/gpt_annotation.txt')
    #d2.update_txt('\n'.join([line['txt'] for line in d.txt]))

    '''

