import os
import document
import argparse
import schema
from collections import defaultdict

sch = schema.Schema(upper=True)

def align_entity(mid_gold, mid_system, annotation_gold, annotation_system, equals):
    '''
    doc_systemのエンティティに対してdoc_goldのエンティティのIDを対応させる
    '''
    tid_map = {}
    mid_mapped = set()
    for tid_system in mid_system:
        tid_map[tid_system] = ''
        for tid_gold in mid_gold:
            if tid_gold in mid_mapped:
                continue
            if equals(annotation_gold, tid_gold, annotation_system, tid_system):
                tid_map[tid_system] = tid_gold
                mid_mapped.add(tid_gold)
                break
    return tid_map

def equals_strict( annotation_gold, tid_gold, annotation_system, tid_system):
    return annotation_gold.region(tid_gold) == annotation_system.region(tid_system)

def equals_cover( annotation_gold, tid_gold, annotation_system, tid_system):
    return annotation_gold.region(tid_gold) <= annotation_system.region(tid_system)

def equals_overlap( annotation_gold, tid_gold, annotation_system, tid_system):
    return annotation_gold.region(tid_gold).isdisjoint( annotation_system.region(tid_system) ) is False

 
def calc_metrics(tp, p, t, percent=True):
    """
    compute overall precision, recall and FB1 (default values are 0.0)
    if percent is True, return 100 * original decimal value
    """
    precision = tp / p if p else 0
    recall = tp / t if t else 0
    fb1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    if percent:
        return 100 * precision, 100 * recall, 100 * fb1
    else:
        return precision, recall, fb1


def print_count(count):
    print("\t".join(['entity type'.rjust(18),'attribute', 'value', '#gold', '#system', '#correct', 'P','R','F1','acc']))
    prec, rec, f1 = calc_metrics(count['entity']['ALL']['']['correct'], count['entity']['']['']['system'], count['entity']['']['']['gold'])
    print("\t".join(['overall'.rjust(18),
                     ''.rjust(10),
                     ''.rjust(10),
                     str(count['entity']['']['']['gold']),
                     str(count['entity']['']['']['system']),
                     str(count['entity']['ALL']['']['correct']),
                     f"{prec:.1f}",
                     f"{rec:.1f}",
                     f"{f1:.1f}"]))
    prec, rec, f1 = calc_metrics(count['entity']['']['']['correct'], count['entity']['']['']['system'], count['entity']['']['']['gold'])
    print("\t".join(['tag total'.rjust(18),
                     ''.rjust(10),
                     ''.rjust(10),
                     str(count['entity']['']['']['gold']),
                     str(count['entity']['']['']['system']),
                     str(count['entity']['']['']['correct']),
                     f"{prec:.1f}",
                     f"{rec:.1f}",
                     f"{f1:.1f}"]))
    for ent_type in sorted(count.keys()):
        if ent_type == 'entity': continue
        prec, rec, f1 = calc_metrics(count[ent_type]['']['']['correct'], count[ent_type]['']['']['system'], count[ent_type]['']['']['gold'])
        print("\t".join([ent_type.rjust(18),
                         ''.rjust(10),
                         ''.rjust(10),
                         str(count[ent_type]['']['']['gold']),
                         str(count[ent_type]['']['']['system']),
                         str(count[ent_type]['']['']['correct']),
                         f"{prec:.1f}",
                         f"{rec:.1f}",
                         f"{f1:.1f}"]))

        for attr in sch.entity[ent_type]['attribute']:
            acc = 'NA'
            if count[ent_type]['']['']['correct'] > 0:
                acc = f"{count[ent_type][attr]['']['correct'] / count[ent_type]['']['']['correct'] * 100:.1f}"
            print("\t".join([''.rjust(18),
                             attr.rjust(10),
                             ''.rjust(10),
                             '',
                             '',
                             str(count[ent_type][attr]['']['correct']),
                             '',
                             '',
                             '',
                             acc]))
            for value in sch.attribute[attr]:
                if( count[ent_type][attr][value]['gold'] > 0 or
                    count[ent_type][attr][value]['system'] ):

                    prec, rec, f1 = calc_metrics(count[ent_type][attr][value]['correct'], count[ent_type][attr][value]['system'], count[ent_type][attr][value]['gold'])
                    print("\t".join([''.rjust(18),
                                     attr.rjust(10),
                                     value.rjust(10),
                                     str(count[ent_type][attr][value]['gold']),
                                     str(count[ent_type][attr][value]['system']),
                                     str(count[ent_type][attr][value]['correct']),
                                     f"{prec:.1f}",
                                     f"{rec:.1f}",
                                     f"{f1:.1f}"]))

def evaluate_entity_attribute(tid_map,
                              annotation_gold,
                              annotation_system,
                              count = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'correct':0, 'system':0, 'gold':0}))),
                              include_ent = [],
                              exclude_ent = []):
    sch = schema.Schema(upper=True)
    
    for tid_system in annotation_system.get_mention_id():
        ent_type = annotation_system.entity_type(tid_system)
        if ent_type in exclude_ent: continue;
        if include_ent and ent_type not in include_ent: continue;

        attr_system = annotation_system.get_attribute(tid_system)
        
        # correct
        if( tid_map[tid_system] != '' and
            annotation_gold.entity_type(tid_map[tid_system]) == ent_type):
            count['entity']['']['']['correct'] += 1
            count[ent_type]['']['']['correct'] += 1

            attr_gold = annotation_gold.get_attribute(tid_map[tid_system])
            attr_ok = True
            for attr_type in sch.entity[ent_type]['attribute']:
                attr_value_system, attr_value_gold = None,None
                for attr in attr_system:
                    if attr['type'] == attr_type:
                        attr_value_system = attr['value']
                        break
                for attr in attr_gold:
                    if attr['type'] == attr_type:
                        attr_value_gold = attr['value']
                if attr_value_system is None:
                    attr_value_system = ent_type # i2b2 2014
                if ((attr_value_system is None and attr_value_gold is None) or
                    attr_value_system == attr_value_gold or
                    (attr_value_system == 'POSITIVE' and attr_value_gold == 'POS') or
                    (attr_value_system == 'NEGATIVE' and attr_value_gold == 'NEG') ):
                    count[ent_type][attr_type][attr_value_system]['correct'] += 1
                    count[ent_type][attr_type]['']['correct'] += 1
                else:
                    attr_ok = False
            if attr_ok:
                count['entity']['ALL']['']['correct'] += 1
                count[ent_type]['ALL']['']['correct'] += 1

        # system
        count['entity']['']['']['system'] += 1
        count[ent_type]['']['']['system'] += 1

        for attr_type in sch.entity[ent_type]['attribute']:
            attr_value_system = ''
            for attr in attr_system:
                if attr['type'] == attr_type:
                    attr_value_system = attr['value']
                    break
            count[ent_type][attr_type][attr_value_system]['system'] += 1

    # gold
    for mid_gold in annotation_gold.get_mention_id():
        ent_type = annotation_gold.entity_type(mid_gold)
        if ent_type in exclude_ent: continue;
        if include_ent and ent_type not in include_ent: continue;
        count['entity']['']['']['gold'] += 1
        count[ent_type]['']['']['gold'] += 1
        attr_gold = annotation_gold.get_attribute(mid_gold)
        for attr_type in sch.entity[ent_type]['attribute']:
            attr_value_gold = ''
            for attr in attr_gold:
                if attr['type'] == attr_type:
                    attr_value_gold = attr['value']
                    break
            count[ent_type][attr_type][attr_value_gold]['gold'] += 1

    #print_count(count)
    return count



def evaluate(annotation_gold, annotation_system, count, equal_func, include_ent, exclude_ent):
    mid_gold = []
    for mid in annotation_gold.get_mention_id():
        if include_ent and annotation_gold.entity_type(mid) not in include_ent : continue
        if annotation_gold.entity_type(mid) in exclude_ent : continue
        mid_gold.append(mid)
            
    mid_system = []
    for mid in annotation_system.get_mention_id():
        if include_ent and annotation_system.entity_type(mid) not in include_ent : continue
        if annotation_system.entity_type(mid) in exclude_ent : continue
        mid_system.append(mid)
        
    tid_map = align_entity(mid_gold, mid_system, annotation_gold, annotation_system, equal_func)
    count = evaluate_entity_attribute(tid_map,
                                      annotation_gold,
                                      annotation_system,
                                      count,
                                      include_ent=include_ent,
                                      exclude_ent=exclude_ent)
    return count


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='evaluation')
    parser.add_argument('-dir_s', metavar='DIRECTORY_SYSTEM', help='directory which contains NER results', required=True)
    parser.add_argument('-dir_g', metavar='DIRECTORY_GOLD', help='directory which contains gold standard files (the same as the input directory of annotate.py)', required=True)
    parser.add_argument('-corpus', metavar='CORPUS', help='corpus name (i2b2_2012/i2b2-2014/MedTxt_CR)', choices=['i2b2_2012','i2b2-2014', 'MedTxt_CR'], required=True)
    args = parser.parse_args()
    
    if args.dir_s and args.dir_g:

        count_strict= defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'correct':0, 'system':0, 'gold':0})))
        count_overlap= defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'correct':0, 'system':0, 'gold':0})))

        include_ent = []
        if args.corpus == 'i2b2_2012':
            include_ent = ['EVENT','TIMEX3'] # i2b2 2012
        elif args.corpus == 'MedTxt_CR':
            include_ent = ['a', 'd', 't-test', 'timex3', 'm-key', 'm-val','t-key', 't-val']
        exclude_ent = []

        for file_ in sorted(os.listdir(args.dir_s)):
            txt_file = file_.replace('.ann','.txt')
            if file_.endswith('.ann'):
#                print(file_)

                if os.path.exists(f"{args.dir_g}/{file_}") is False:
                    print(f"Skip {file_}: not exist in gold directory")
                    continue

                if os.path.exists(f"{args.dir_s}/{file_}") is False:
                    print(f"Skip {file_}: not exist in NER results directory")
                    continue
                #if os.path.getsize(f"{args.dir_s}/{file_}") == 0:
                #    print(f"{file_} size 0. skip.")
                #    continue
                
                #print(" load gold")
                doc_gold=document.Document()
                doc_gold.load_txt_file(f"{args.dir_g}/{txt_file}")
                doc_gold.load(f"{args.dir_g}/{file_}", schema_=sch, upper=True)

                #print(" load system")
                doc_gpt=document.Document()
                doc_gpt.load_txt_file(f"{args.dir_s}/{txt_file}")
                doc_gpt.load(f"{args.dir_s}/{file_}", schema_=sch, upper=True)

                #print(" evaluate")
                evaluate(doc_gold.annotation, doc_gpt.annotation, count_strict, equals_strict, include_ent, exclude_ent)
                evaluate(doc_gold.annotation, doc_gpt.annotation, count_overlap, equals_overlap, include_ent, exclude_ent)
                
        print('OVER ALL (strict)')
        print_count(count_strict)
        print('OVER ALL (overlap)')
        print_count(count_overlap)

