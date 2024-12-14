import os
import sys
from collections import defaultdict
import schema

class Annotation:
    
    def __init__(self, schema):
        self.schema = schema

        self.mention = defaultdict(lambda: {'type':'',
                                            'region': set(),
                                            'attribute': set(), 
                                            'relation': [], # [{'rid':relation-id, 'role':'src'|'tgt'}] 関係ridにsrc|tgtとして参加している
                                            'equal_group': -1,
                                            'term':[], # [{'resource':'UMLS', 'system':'CUI', 'code':'C0000001'}]
                                            'note':''
                                            } )
        self.attribute = [] # attribute[aid] = {'type': name, 'value':value}
        self.relation = {} # {'src':mention_id, 'tgt':mention_id, 'type':relation-type}
        self.equal_group = [] # [set(mention-id,...)]

    def get_schema(self):
        return self.schema
    
    def get_new_mention_id(self):
        mention_id = 0
        if len(self.mention) == 0:
            mention_id = 1
        else:
            sorted_keys = sorted(self.mention.keys())
            mention_id = max(2,sorted_keys[0] + 1)
            for i in range(1,len(sorted_keys)):
                if sorted_keys[i-1]+1 != sorted_keys[i]:
                    break
                mention_id = sorted_keys[i]+1
        return mention_id

    def entity_type(self, mention_id):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            raise
        return self.mention[mention_id]['type']

    def exists_mention_id(self, mention_id):
        return mention_id in self.mention
    
    def create_mention(self, entity_type, region, mid=-1):
        if self.schema.is_entity_type(entity_type) is False:
            print('undefined entity type:',entity_type)
            raise
        if mid == -1:
            mid = self.get_new_mention_id()
        self.mention[mid]['type'] = entity_type
        self.mention[mid]['region'] = region
        return mid

    def set_mention(self, mid, region):
        if mid not in self.mention:
            print("mention id not found:", mention_id)
            raise
        self.mention[mid]['region'] = region

    
    def set_attribute(self, mention_id, attribute_name, attribute_value, upper=False):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            raise Exception("unknown mention")
        if upper:
            attribute_name = attribute_name.upper()
            attribute_value = attribute_value.upper()
        if self.schema.is_attribute(attribute_name, attribute_value, self.entity_type(mention_id)) is False:
            print(f"attribute {attribute_name}={attribute_value} is not allowed for the entity type:", self.entity_type(mention_id))
            raise Exception("unknown attribute type-value pair")

        aid = -1
        try:
            for aid_, attr in enumerate(self.attribute):
                if( attr['type'] == attribute_name and
                    attr['value'] == attribute_value ):
                    aid = aid_
                    break
            if aid == -1:
                self.attribute.append({'type':attribute_name, 'value':attribute_value})
                aid = len(self.attribute)-1
            self.mention[mention_id]['attribute'].add(aid)
            return aid
        except Exception as e:
            print(' exception occur', flush=True)
            raise e
    
    def create_relation(self, src, tgt, rel):
        if src not in self.mention or tgt not in self.mention:
            print("mention id not found:", mention_id)
            raise Exception("unknown mention")
        if self.schema.is_relation(self.entity_type(src), self.entity_type(tgt), rel) is False:
            print(f"relation {self.entity_type(src)} -{rel}-> {self.entity_type(tgt)} is not allowed.")
            raise

        rid = -1
        for rid_ in self.relation:
            if self.relation[rid_] == {'src':src, 'tgt':tgt, 'type':rel}:
                rid = rid_
                break
        if rid == -1:
            rid = len(self.relation)
            self.relation[rid] = {'src':src, 'tgt':tgt, 'type':rel}
        self.mention[src]['relation'].append({'rid':rid, 'role':'src'})
        self.mention[tgt]['relation'].append({'rid':rid, 'role':'tgt'})

    def set_vocab_mapping(self, mention_id, resource, system, code, term):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            raise
        term = {'resource':resource,
                'system':system,
                'code':code,
                'term':term }
        self.mention[mention_id]['term'].append(term)

    def get_vocab_mapping(self, mention_id):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            raise
        return self.mention[mention_id]['term']
    
    def set_note(self, mention_id, note_text, mode='n'):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            raise
        if mode == 'n':
            self.mention[mention_id]['note'] = note_text
        elif mode == 'a':
            self.mention[mention_id]['note'] += note_text

    def create_equal_group(self, mention_ids):
        for mid in mention_ids:
            if mid not in self.mention:
                print("mention id not found:", mid)
                raise
        if isinstance(mention_ids, set):
            self.equal_group.append(mention_ids)
        else:
            self.equal_group.append(set(mention_ids))
        gid = len(self.equal_group)+1
        for mid in mention_ids:
            self.mention[mid]['equal_group'] = gid

    def delete_mention(self, mid):
        for rel in self.mention[mid]['relation']:
            other_role = 'src' if rel['role'] == 'tgt' else 'tgt'
            other_mid = self.relation[rel['rid']][other_role]
            self.mention[other_mid]['relation'].remove( rel['rid'] )
            del self.relation[rel['rid']]
        if self.mention[mid]['equal_group'] != -1:
            self.equal_group[ self.mention[mid]['equal_group'] ].remove(mid)
            if len(self.equal_group[ self.mention[mid]['equal_group'] ]) == 1:
                del self.equal_group[ self.mention[mid]['equal_group'] ]
        del self.mention[mid]

    def delete_relations(self):
        self.relation = {}
        self.equal_group = []
        for mid in self.get_mention_id():
            self.mention[mid]['relation'] = []
            self.mention[mid]['equal_group'] = -1

    def get_mention_id(self):
        return self.mention.keys()
    
    def get_mention_id_in_range(self, region):
        mids = []
        for mid in self.mention:
            if self.mention[mid]['region'] <= region:
                mids.append(mid)
        return mids
    
    def region(self, mention_id):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            print("current mentions:", self.mention)
            raise
        return self.mention[mention_id]['region']
    
    def region_list(self, mention_id):
        if mention_id not in self.mention:
            print("mention id not found:", mention_id)
            print("current mentions:", self.mention)
            raise
        return sorted(list(self.mention[mention_id]['region']))

    def get_attribute(self, mid):
        if mid not in self.mention:
            print("mention id not found:", mid)
            raise
        return [ self.attribute[aid] for aid in self.mention[mid]['attribute'] ]

    def get_note(self, mid):
        if mid not in self.mention:
            print("mention id not found:", mid)
            raise
        return self.mention[mid]['note']

    def get_relation(self, mid=-1):
        if mid == -1:
            return self.relation.values()
        else:
            if mid not in self.mention:
                print("mention id not found:", mid)
                raise
            rels = []
            for rel in self.relation:
                if rel['src'] == mid or rel['tgt'] == mid:
                    rels.append(rel)
            return rels

    def get_equal_group(self):
        return self.equal_group

        
    def is_state_core(self, tid):
        if tid not in self.mention:
            print("mention id not found:", tid)
            raise
        if self.entity_type(tid) in ['state', 'value', 'quantity_evaluation']:
            return True
        else:
            return False

    def get_equivalents(tid):
        eid = [];
        for symR in self.ann['symR']:
            if symR['rel'] != 'equivalent':
                continue
            if tid in symR['id']:
                for sym_id in symR['id']:
                    if sym_id == tid:
                        continue
                    eid.append(sym_id)
        return eid

    def is_human_state(self, tid, consider_equivalent=True):
        for rel in self.mention[tid]['relation']:
            if self.relation[rel['rid']]['type'] == 'same_racipe':
                return False
            if self.relation[rel['rid']]['type'] == 'denominator' and rel['role'] == 'tgt':
                return False
            if( self.relation[rel['rid']]['type'] in ['value_of',
                                                     'eval_of',
                                                     'prog_of',
                                                     'attribute_of',
                                                     'site',
                                                     'refered_site'] and
                rel['role'] == 'src'):
                tgt = self.relation[rel['rid']]['tgt']
                if( self.mention[tgt]['type'] in ['execute',
                                                  'action',
                                                  'explatin',
                                                  'detail',
                                                  'clinical_test',
                                                  'consultation',
                                                  'drug',
                                                  'device',
                                                  'treatment',
                                                  'p_change',
                                                  'route',
                                                  'rp_info']):
                    return False
                if self.is_human_state(tgt) is False:
                    return False
        if(consider_equivalent and self.mention[tid]['equal_group'] != -1):
            for eid in self.equal_group[self.mention[tid]['equal_group']]:
                if self.is_human_state(eid, False) is False:
                    return False
        return True

    def is_local_state(self, tid, consider_equivalent=True):
        for rel in self.mention[tid]['relation']:
            if( self.relation[rel['rid']]['type'] in ['value_of',
                                                      'eval_of',
                                                      'prog_of',
                                                      'attribute_of',
                                                      'site',
                                                      'refered_site'] and
                rel['role'] == 'src' ):
                tgt = self.relation[rel['rid']]['tgt']
                if self.mention[tid]['type'] != 'quantity_evaluation':
                    if( self.mention[tgt]['type'] in ['state',
                                                      'value',
                                                      'quantity_evaluation',
                                                      'quality_evaluation',
                                                      'quantity_progress',
                                                      'qnality_progress']):
                        return True
                if self.is_local_state(tgt):
                    return True
        if(consider_equivalent and self.mention[tid]['equal_group'] != -1):
            for eid in self.equal_group[self.mention[tid]['equal_group']]:
                if self.is_local_state(eid, False):
                    return True
        return False


if __name__ == "__main__":
    schema = schema.Schema()
    a=Annotation(schema)
