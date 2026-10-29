"""Prepare private, UNPUBLISHED supplied-form candidates. No defaults/approvals."""
from __future__ import annotations
import argparse
import csv
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
from uuid import uuid4

from alarm_inspection.domain.pdf_integrations import IntegrationConfig, SourceRef, canonical_json
from alarm_inspection.integrations.pdf_files import PrivatePdfFiles
from alarm_inspection.integrations.pdf_service import bounded_pdf

SUPPLIED={'nfpa72':('b956b9c0ae6864970eb2f582a12a9e59d81162e1843f3b8e54f536a08d43aa71',196),
          'compliance':('f51cb8c0808fa356382b0672ef0f5613306def35503ec37721fe7923ce6c8dd2',283)}


def section(key,target):
    x0,y0,x1,y1=target['rect'];y=(y0+y1)/2
    if key=='nfpa72' and target['qualified_name']=='WMT Control Number':return 'Footer / source control reference'
    if key=='nfpa72':return {1:'Property / testing / system',2:'Power / notifications / visual and functional testing',3:'Supervising station / public emergency reporting',4:'Completion / restoration / defects / acceptance'}[target['page']]
    if y>680:return 'Identity / panel information'
    if y<125:return 'Remarks / acknowledgement / signatures'
    bands=([(580,'1 Doors and beams'),(480,'2 Motion and glass break'),(455,'3 Notification'),(390,'4 Control functions'),(345,'5 Delay egress'),(280,'6 Power'),(185,'7 Communication'),(125,'8 Audio and paging')]
           if x0<300 else [(625,'9 Keypads and areas'),(560,'10 Access control'),(510,'11 Management training'),(410,'12 Labels and signage'),(300,'13 CCTV'),(140,'14 Pharmacy CCTV'),(125,'15 Work order acknowledgement')])
    return next((label for bottom,label in bands if y>=bottom),'Remarks / acknowledgement / signatures')


def _label(target,words,key):
    x0,y0,x1,y1=target['rect'];cy=(y0+y1)/2
    region=(50,245) if key=='nfpa72' else (55,160) if x0<300 else (305,410)
    candidates=[word for word in words if abs(word['y']-cy)<4 and region[0]<=word['x']<min(region[1],x0-2)]
    label=' '.join(w['text'] for w in sorted(candidates,key=lambda w:w['x']))
    return label if label.strip() else target['qualified_name'] or f'Page {target["page"]} field {target["occurrence"]}'


def build_candidate(data,key,*,words=None):
    if key not in SUPPLIED:raise ValueError('Unknown integration.')
    inventory=bounded_pdf(data,[1,2,3,4] if key=='nfpa72' else [1],'inventory')
    ident=str(uuid4());from hashlib import sha256
    original={'key':PrivatePdfFiles.template_key(key,ident,'original.pdf'),'sha256':sha256(data).hexdigest(),'size':len(data)}
    if words is None:words={int(page):rows for page,rows in bounded_pdf(data,inventory['selected_pages'],'words').items()}
    targets=inventory['targets'];mappings=[];inputs=[];groups=[];review=[];bindings={}
    labels={t['id']:_label(t,(words or {}).get(t['page'],[]),key) for t in targets}
    identity={('compliance',1,0):'inspector_name',('compliance',1,278):'inspector_name',('compliance',1,6):'store_number',
              ('compliance',1,9):'address',('nfpa72',1,5):'store_number',('nfpa72',1,6):'address',('nfpa72',4,14):'inspector_name'}
    # Identity bindings apply ONLY to the recorded supplied fingerprint/count.
    known=inventory['source_sha256']==SUPPLIED[key][0] and len(targets)==SUPPLIED[key][1]
    buttons=[t for t in targets if t['kind'] in {'checkbox','radio'}]
    clusters=[]
    for target in sorted(buttons,key=lambda t:(t['page'],-sum(t['rect'][1::2])/2,t['rect'][0])):
        cy=(target['rect'][1]+target['rect'][3])/2
        cluster=next((row for row in clusters if row[0]['page']==target['page'] and
            abs((row[0]['rect'][1]+row[0]['rect'][3])/2-cy)<1.1 and (key=='nfpa72' or (row[0]['rect'][0]<300)==(target['rect'][0]<300))),None)
        if cluster is None:clusters.append([target])
        else:cluster.append(target)
    supplemental=None
    for index,row in enumerate(clusters):
        row.sort(key=lambda t:t['rect'][0]);input_id=f'g_{row[0]["page"]}_{index:03}'
        # NFPA visual and functional columns are INDEPENDENT results, not Yes/No.
        if key=='nfpa72' and not (row[0]['page']==1 and len(row)==2):
            for target in row:
                local=f'f_{target["page"]}_{target["occurrence"]:03}'
                label=f'{labels[target["id"]]} — independent {"visual" if target["rect"][0]<275 else "functional"} result'
                inputs.append(dict(id=local,label=label[:200],meaning=f'Independent observed result for target {target["id"]}; no preset is evidence.',type='dropdown',options=['Yes','No'],required=True))
                bindings[target['id']]=dict(source={'kind':'manual','id':local},label=label)
                groups.append(dict(id='answer_'+local,members={'Yes':[target['id']],'No':[]},required=True))
            continue
        options=['Yes','No','NA'] if len(row)==3 else ['Yes','No']
        label=(labels[row[0]['id']]+' — not applicable?' if len(row)==1 else labels[row[0]['id']]+' — observed result')
        if key=='nfpa72' and row[0]['page']==1:label='Separate supplemental sheets attached?';supplemental={'kind':'manual','id':input_id}
        inputs.append(dict(id=input_id,label=label[:200],meaning='Explicit observed answer for these reviewed widget locations; empty choice clears markers, never means missing.',type='dropdown',options=options,required=True))
        members={option:[] for option in options}
        if len(row)==1:members['Yes']=[row[0]['id']]
        else:
            for option,target in zip(options,row):members[option]=[target['id']]
        groups.append(dict(id='answer_'+input_id,members=members,required=True))
        for target in row:bindings[target['id']]=dict(source={'kind':'manual','id':input_id},label=label)
    for target in targets:
        ident_target=target['id'];label=labels[ident_target];sec=section(key,target);kind=target['kind'];reason=''
        font=max(4,min(9,math.floor((target['rect'][3]-target['rect'][1]-2)/1.2*2)/2))
        if known and key=='nfpa72' and target['page']==1 and target['occurrence']==9:label='Property representative address (independent from store address)'
        if known and key=='compliance' and target['occurrence'] in (84,85):label='D130 relays — '+('number installed' if target['occurrence']==84 else 'number tested good')
        mapping=dict(target_id=ident_target,label=label[:200],section=sec,font_size=font,minimum_font_size=font)
        if kind=='signature':mapping.update(disposition='sign_later',reason='Candidate blank for later signing; administrator must resolve the signature policy.')
        elif kind in {'unknown','pushbutton'}:mapping.update(disposition='excluded',reason='Unsupported target requires explicit administrator review; no original value retained.')
        elif ident_target in bindings:mapping.update(disposition='source',source=bindings[ident_target]['source'],label=bindings[ident_target]['label'][:200],required=True)
        elif known and (key,target['page'],target['occurrence']) in identity:
            mapping.update(disposition='source',source={'kind':'inspection','field':identity[(key,target['page'],target['occurrence'])]},required=True)
        else:
            local=f'f_{target["page"]}_{target["occurrence"]:03}'
            typ='text';options=[]
            if kind=='choice' and not target['flags']&(1<<18):typ='dropdown';options=[str(o[0] if isinstance(o,list) else o) for o in target['options'] if str(o).strip()]
            if key=='compliance' and kind=='text' and (re.search(r'GOOD|INSTALLED|COUNT|VOLTS|AMPS|AMP HR',target['qualified_name']) or (sec[:1] in {'1','2','3','4','5'} and target['rect'][0]>160 and target['rect'][0]<270)):
                typ='number'
            transforms=[]
            name=target['qualified_name']
            if key=='nfpa72' and re.search(r'DateTime|Restore|^Time(_[0-9]+)?$',name):
                typ='datetime';transforms=[{'kind':'time' if name.startswith('Time') else 'date','format':'%H:%M' if name.startswith('Time') else '%m/%d/%Y' if target['page']==4 and target['occurrence'] in (15,37) else '%m/%d/%Y %H:%M'}]
            elif key=='compliance' and 'DateTime' in name:
                typ='date';transforms=[{'kind':'date','format':'%m/%d/%Y'}]
            definition=dict(id=local,label=label[:200],meaning=f'Actual value for {sec}; template {inventory["source_sha256"]}, target {ident_target}. Administrator review required.',type=typ,required=True)
            if typ=='dropdown':definition['options']=options
            if typ=='number':definition['minimum']=0
            inputs.append(definition);mapping.update(disposition='source',source={'kind':'manual','id':local},required=True,transforms=transforms)
        mappings.append(mapping)
        review.append(dict(target_id=ident_target,page=target['page'],occurrence=target['occurrence'],section=sec,label=mapping['label'],qualified_name=target['qualified_name'],kind=kind,
            rect=target['rect'],same_name_targets=target['same_name_targets'],disposition=mapping['disposition'],source=mapping.get('source'),font_size=font,
            preset_present=target['value'] is not None,verified=False,review='Required: semantic meaning, type/units, optional/NA/negative policies, overflow, signatures and business defaults.'))
    # Candidate-only conditional omissions for explicit single NA markers.
    # Quantity/tested-good sources remain independent; no automatic counts.
    definitions={definition['id']:definition for definition in inputs}
    for row in clusters:
        if len(row)!=1 or key!='compliance':continue
        marker=row[0];binding=bindings[marker['id']]['source'];cy=(marker['rect'][1]+marker['rect'][3])/2
        condition={'source':binding,'operator':'equals','expected':'No'}
        for target,mapping in zip(targets,mappings):
            if target['kind'] not in {'text','choice'} or target['page']!=marker['page'] or abs((target['rect'][1]+target['rect'][3])/2-cy)>1.3:continue
            if (target['rect'][0]<300)!=(marker['rect'][0]<300):continue
            source=mapping.get('source',{})
            if source.get('kind')!='manual':continue
            definitions[source['id']].update(required=False,required_when=condition)
            mapping.update(required=False,required_when=condition,missing='blank',reason='Candidate: this row may be blank when explicitly marked not applicable; review policy before publication.')
    config=IntegrationConfig.model_validate(dict(integration_key=key,version_id=ident,original=original,inventory=inventory,mappings=mappings,manual_inputs=inputs,
        answer_groups=groups,signature_policy='unresolved',supplemental_policy='unresolved',supplemental_source=supplemental,
        applicability=None,categories=[],default_timezone=None,filename_policy='unresolved'))
    return config,review


def install_candidate(session,config,data,*,files,actor_id):
    """Administrative provisioning only; no publication, activation or enablement."""
    from alarm_inspection.integrations.pdf_service import intake
    from alarm_inspection.integrations.pdf_repository import update_draft
    row=intake(session,config.integration_key,data,'reference-template.pdf',files=files,actor_id=actor_id)
    actual=IntegrationConfig.model_validate_json(row.payload_json)
    if config.inventory!=actual.inventory:raise ValueError('Source inventory changed; review a new candidate.')
    raw=config.model_dump(mode='json');raw.update(version_id=actual.version_id,original=actual.original.model_dump(mode='json'))
    update_draft(session,IntegrationConfig.model_validate(raw),files=files,expected_revision=1,actor_id=actor_id)
    return row.id


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True,type=Path);parser.add_argument('--key',choices=SUPPLIED,required=True);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();os.umask(0o077);args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    data=args.source.read_bytes();config,review=build_candidate(data,args.key)
    expected,count=SUPPLIED[args.key]
    if config.inventory.source_sha256!=expected or len(config.inventory.targets)!=count:raise ValueError('Supplied reference identity/count differs; manual re-inventory required.')
    (args.output/'candidate.json').write_text(canonical_json(config))
    (args.output/'review.json').write_text(canonical_json({'status':'UNPUBLISHED: BUSINESS DEFAULTS AND PER-TARGET VERIFICATION DEFERRED','fields':review}))
    with (args.output/'review.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(review[0]));writer.writeheader();writer.writerows(review)
    for page in config.inventory.selected_pages:(args.output/f'page-{page}.png').write_bytes(bounded_pdf(data,config.inventory.selected_pages,'page',page=page))
    print(f'{args.key}: private unpublished candidate with {len(review)} targets; no business defaults established.')


if __name__=='__main__':main()
