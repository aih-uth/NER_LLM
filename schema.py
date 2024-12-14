import pandas as pd
import json

class Schema:
    entity = {}
    attribute = {}
    relation = {} # relation[type] = [{'src':set(), 'tgt':set(), 'description': ''}]
    schema = {'entity':entity, 'attribute':attribute, 'relation':relation}
    
    def __init__(self, filepath='schema.xlsx', upper=False):
        schema_attribute = pd.read_excel(filepath, engine='openpyxl', sheet_name='attribute', na_values='', keep_default_na=False)
        attr_type = ''
        for index, row in schema_attribute.iterrows():
            if pd.notna(row['type']):
                attr_type = row['type']
                if upper:
                    attr_type = attr_type.upper()
            value = ''
            if pd.notna(row['value']):
                value = row['value']
                if upper:
                    value = value.upper()

            if attr_type not in self.attribute:
                self.attribute[attr_type] = {value: {} }
            elif value not in self.attribute[attr_type]:
                self.attribute[attr_type][value] = {} 
            for clm in ['description', 'inclusion example']:
                if pd.notna(row[clm]):
                    self.attribute[attr_type][value][clm] = row[clm]
#                    print(attr_type,'=',row['value'])
                
        schema_entity = pd.read_excel(filepath, engine='openpyxl', sheet_name='entity')
        for index, row in schema_entity.iterrows():
            ent_type = row['type']
            if upper:
                ent_type = ent_type.upper()
            if ent_type not in self.entity:
                self.entity[ent_type] = {}
            for clm in ['description', 'inclusion', 'inclusion example', 'exclusion', 'exclusion example']:
                if pd.notna(row[clm]):
                    self.entity[ent_type][clm] = row[clm]
            self.entity[ent_type]['attribute'] = []
            if pd.notna(row['attribute']):
                for attr_name in row['attribute'].split("\n"):
                    if upper:
                        attr_name = attr_name.upper()
                    self.entity[ent_type]['attribute'].append(attr_name)
                
        schema_relation = pd.read_excel(filepath, engine='openpyxl', sheet_name='relation')
        rel_type = ''
        description = ''
        for index, row in schema_relation.iterrows():
            if pd.notna(row['type']):
                rel_type = row['type']
                self.relation[rel_type] = []
            rel= {'src':row['source'].strip().split('\n'),
                  'tgt':row['target'].strip().split('\n')}
            if pd.notna(row['description']):
                description = row['description']
            rel['description'] = description
            for clm in ['inclusion example']:
                if pd.notna(row[clm]):
                    rel[clm] = row[clm]
            self.relation[rel_type].append(rel)
            

    def to_json(self, category='entity', target='all'):
        if target == 'all':
            return json.dumps(self.schema[category], ensure_ascii=False, indent=4)
        else:
            return '{' + ','.join(['"' + t + '":"' + self.entity[t]["description"] + '"' for t in sorted(self.entity)]) + '}'

    def is_entity_type(self, tag_name):
        return tag_name in self.entity

    def is_attribute(self, attr_name, attr_value, ent_type=''):
        if( attr_name not in self.attribute or
            (attr_value not in self.attribute[attr_name] and 'ANY' not in self.attribute[attr_name]) ):
            return False
        if ent_type != '':
            if( ent_type not in self.entity or
                attr_name not in self.entity[ent_type]['attribute'] ):
                return False
        return True

    def is_relation(self, src, tgt, rel_type):
        if( src in self.entity and
            tgt in self.entity and
            rel_type in self.relation ):
            
            for rel in self.relation[rel_type]:
                if ((src in rel['src'] or 'ANY' in rel['src']) and
                    (tgt in rel['tgt'] or 'ANY' in rel['tgt'])):
                    return True
                
        return False

    def relation_between_pair(self, src_ent_type='', tgt_ent_type=''):
        rel_list = []
        for rel_type in self.relation:
            for rel in self.relation[rel_type]:
                if ((src_ent_type == '' or src_ent_type in rel['src'] or 'ANY' in rel['src']) and
                    (tgt_ent_type == '' or tgt_ent_type in rel['tgt'] or 'ANY' in rel['tgt'])):
                    rel_list.append({'type':rel_type, 'detail':rel})
        return rel_list
    
if __name__ == '__main__':
    s = Schema()

