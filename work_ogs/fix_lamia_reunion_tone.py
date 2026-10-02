"""Repair early OG2 Lamia scenes and the later DC-ship reunion in CURRENT.

Reference: work_og2new/batches/batch_02.done.tsv rows 534-568 and the
OGs relationship bible. PS2-only Beowulf exchange retains its event order.
Dry run by default; --apply edits CURRENT only, with an exclusive Windows
file handle, exact source hash guard, reversible byte backup, and whole-file
verification against a virtually patched hash. Never edits memory cards.
"""
import argparse
import ctypes
import hashlib
import json
import msvcrt
import os
import re
import struct
from pathlib import Path
from ogs_korean_codec import encode, decode

ROOT=Path(__file__).resolve().parent
ISO=ROOT/'build/SRWOGS_AxelRoleSwap_kr_CURRENT.iso'
EXPECTED='94DBCB2995D7A8CACCB6B07C92286DDBF50670B3D275B3D8792661055E8BE5A1'
MAP=0xC10800
MANIFEST=ROOT/'runtime/lamia_reunion_tone_20261001.json'
BACKUP=ROOT/'runtime/lamia_reunion_tone_20261001.bin'
# Exact confirmed scene offsets only; no global replacements.
EDITS={
 0x666283D:'소속불명병：Ｗ１７、@류케이오스 기동코드를 확보했다。',
 0x666287F:'라미아：확인했다。즉시 기동 준비를。@연방군이 움직임을 포착했다。@빈델님 일행의 도착에 대비한다。',
 0x6662915:'라미아（본대가 패배했나。@　예상 이상의 적 전력이 투입된 모양이다）',
 0x666296B:'라미아（본대를 퇴각시킨 전력…@　연방군 특수진압부대 울브즈인가。@　베오울프의 개입 가능성이 높다）',
 0x66629E2:'라미아（베오울프가 추격 중이라면@　전이 시설의 방어가 우선이다。@　본대가 도착할 때까지 확보해야 한다）',
 0x6662A7D:'Ｗ１６：Ｗ１７、보고하겠다。',
 0x6662AA2:'라미아：Ｗ１６、보고해라。',
 0x6662B03:'라미아：Ｗ１０까지인가。@초기형으로 구성된 선발대군。',
 0x6662B43:'라미아：０번부터라면@Ｗ００도 포함되는가？',
 0x6662BBF:'라미아：확인했다。@Ｗ００은 실전투입 불가 상태다。@별도의 수송 대책이 필요하겠군。',
 0x6662C22:'라미아：후기형인 우리는@어떤 임무를 맡게 되나？',
 0x6662CAE:'라미아：그렇군。@우리의 임무는 지령 수행이다。@질문은 철회한다。',
 0x6662CF8:'Ｗ１６：확인했다。@Ｗ１７、곧 전이할 수 있나？',
 0x6662D3B:'라미아：아직이다。@레몬님께서 선발대를 네버랜드에@탑승시키라고 지시하셨다。',
 0x6662DA5:'라미아（트라이로바이트급을 수송에 투입…@　초기형의 보존도 작전에 포함되어 있다。@　지시대로 준비한다）',
 0x6662E20:'라미아（레몬님께서는@　모든 넘버즈를 보존하실 생각인가）',
 0x6662EA9:'라미아：그렇다。레몬님 일행이 도착하면@즉시 전원 탑승할 수 있도록@준비해라。',
 0x6662F69:'라미아：연방군의 방해인가？',
 0x6662FEB:'라미아：실전투입 단계인가。@엑서런스의 완성도는 예상 이상이군。@확보 계획을 변경한다。',
 0x6663054:'라미아：출격한다。',
 0x6663094:'라미아：시설 방어 병력은 유지한다。@엑서런스 확보에는@소수의 기체만 투입하겠다。',
 0x6663149:'라미아：안쥬르그로 출격한다。@실전 기동 데이터도 수집하겠다。@귀환할 때까지 방어를 맡긴다。',
 0x66631B9:'라미아（엑서런스…시류엔진 외에도@　프레임 환장 시스템을 확인할 필요가 있다）',
 0x6663211:'라미아（라즈앙그리프나 아슈세이버에도@　응용 가능한 기술이라면@　운용의 폭을 넓힐 수 있다）',
 0x666326E:'라미아（확보할 가치는 있다。@　전이 준비에 지장이 없도록@　신속히 끝내야 한다）',
 0x66745BB:'라미아：일루젼・애로우…@명중 정밀도와 위력、양호。',
 0x66745F5:'라미아：무장 성능 확인。@임무를 개시한다。',
 0x66746D5:'라미아：확보 작전 개시。@각기、현 위치에서 대기。',
 0x667471A:'라미아：엑서런스 파일럿、@응답하라。',
 0x667474B:'라미아：그 기체를@우리에게 인도하라。',
 0x667477B:'라미아：수송기 내의 장비도@모두 포함한다。',
 0x6674800:'라미아：소속은 밝힐 수 없다。@너희가 이행할 요구는 같다。@기체와 장비를 인도하라。',
 0x66748B8:'라미아：교섭할 시간은 없다。@요구에 응하면@신변의 안전은 보장한다。',
 0x6674901:'라미아：저항할 경우에는@콕핏을 공격한다。@선택하라。',
 0x6674B3A:'라미아：그렇다。@약속은 이행한다。',
 0x6674BE0:'라미아：기동병기인가！？',
 0x6674C0F:'라미아：아니、형태가 다르다。@출현 경로도 불명…@식별 데이터가 없다。',
 0x6674D81:'라미아：신속한 판단이다。@하지만、놓치지 않는다。',
 0x6674DCC:'라미아：저항 행동을 확인했다。@경고대로 공격한다。',
 0x6674E2C:'라미아：감싼 건가！？',
 0x6674E88:'라미아：큭、방해를！',
 0x6675152:'라미아：큭…！@손상된 기체에서 이 출력이…！？',
 0x6675195:'라미아（자폭으로@　이쪽도 파괴할 생각인가！？）',
 0x667541D:'라미아：이 현상은…！？@엑서런스에서 발생하고 있는 건가！？',
 0x6675734:'라미아（레이더 반응 소실。@　대상의 위치를 확인할 수 없다）',
 0x6675778:'라미아（방금 현상은…전이인가？）',
 0x66757E8:'라미아（출력 제어가 불안정하다。@　전력화는 곤란하겠군）',
 0x6675828:'라미아（동료를 위해 자기를 희생한다…@　이해하기 어려운 판단）',
 0x66812A8:'라미아：전황이 예상보다 악화됐다。@전이 준비를 서둘러야 한다。',
 0x668132B:'라미아：위치가 노출됐나。@확보 실패에 이어@방어선까지 위협받고 있다。',
 0x6681374:'라미아：이곳은 내가 방어한다。@너희는 먼저 연구소로 귀환하라。',
 0x668147B:'라미아：이 시설은 포기할 수 없다。@접근하는 기체는 적으로 간주한다。@공격 개시。',
 0x66815C8:'라미아：주변 적기、제압 완료。@다른 방어선의 상황은…',
 0x6681604:'Ｗ１６：Ｗ１７、본대가 도착했다。@빈델님 일행은 바로 출발하신다。',
 0x6681650:'라미아：필요한 시간은 확보했군。@확인했다。',
 0x668167C:'Ｗ１６：너도 신속히 귀환해라。',
 0x668169D:'라미아：알았다。@귀환할 때까지 준비해라。',
 0x6681700:'라미아：귀환했습니다。@엑서런스 확보는 실패했습니다。@선발대와 빈델님은 출발하셨습니까？',
 0x66817AE:'라미아：전이 계획은@예정대로입니까？',
 0x6681823:'라미아：아직@불안정한 기체입니다。',
 0x668185E:'라미아：이후 보고하겠습니다。@레몬님은@남은 인원의 전이를 맡으십니까？',
 0x6681991:'라미아：현재 전력으로@시설을 지킬 수 있겠습니까？',
 0x66819C5:'라미아：실패하면@퇴로를 잃게 됩니다。',
 0x66819FF:'레몬：위험은 알고 있어、Ｗ１７。@그래도 여기서 멈출 수는 없어。@계획대로 진행할 거야。',
 0x6681AA1:'라미아：저쪽에서@무엇을 찾으십니까？',
 0x6681AE0:'라미아：저쪽에 같은 인물이 있더라도@이쪽과는 다르다는 뜻입니까、@레몬님？',
 0x6681BFE:'라미아：선발 넘버즈 말씀이군요。@후속 인원의 도착까지@교두보를 확보할 수 있겠습니까？',
 0x6681CB6:'레몬：그 애들의 능력은@너도 잘 알고 있잖아。',
 0x6681CEE:'레몬：선발대에는 액셀도 있어。@그 사람의 실력은@너도 인정하지？',
 0x6681D38:'라미아：예。액셀 대장님의 조종기술은@잘 알고 있습니다。@대장님이라면 임무를 수행하실 겁니다。',
 0x6681D9D:'라미아：적 반응을 확인했습니다。@레몬님、먼저 전이하십시오。',
 0x6681E00:'라미아：추격을 차단하겠습니다。@적이 전이 시설에 도달하면@계획 전체가 위험해집니다。',
 0x6681ED5:'라미아：추격 가능성은 있습니다。@전이할 시간을 확보하겠습니다。',
 0x6681F2E:'라미아：추격 부대를 확인。@요격한다。',
 0x6681F60:'라미아：진로상의 모든 것을@파괴하면서 접근하고 있다…！',
 0x6681FD9:'라미아：게슈펜스트 Ｍｋ－Ⅲ…@베오울프가 이곳까지@추격해 왔습니다。',
 0x6682068:'라미아：이전 교전 때부터@저희를 추적하고 있습니다。@위험한 상대입니다。',
 0x66820BF:'레몬：이젠 우리가@그의 공격 대상이구나。',
 0x66820E9:'라미아：현재는 명백한 적입니다。@접근을 막겠습니다。',
 0x6682374:'라미아：목적은 무엇인가。@우리뿐 아니라@이 세계까지 파괴할 생각인가？',
 0x6682490:'라미아：의사소통이 성립하지 않는다…！@위험 수준을 다시 평가해야 한다。',
 0x66824F9:'라미아：추격을 차단합니다。@먼저 가십시오。',
 0x66826C4:'레몬：알겠어。@하지만 반드시 귀환해、Ｗ１７。',
 0x66827C2:'라미아：전이할 때까지@임무를 완수한다…！',
 0x66827F0:'라미아：목표、게슈펜스트…！',
 0x6682833:'라미아：베오울프의@추격을 저지한다…！',
 0x5FCF2EB:'라미아：…합류 지점에 도착했다。@전이 후 시간이 걸렸지만、@이제 임무에 복귀할 수 있겠군。',
 0x5FCF356:'라미아：ＤＣ 전함인가。@빈델님이 계시다면、@협력 중이라는 뜻이겠군。',
 0x5FCF3A5:'라미아：베오울프…@예측을 넘는 전투 능력이다。@위험성을 보고해야 한다。',
 0x5FCF3EE:'에키드나：Ｗ１７……',
 0x5FCF40B:'라미아：Ｗ１６…빈델님은 여기 계시나？',
 0x5FCF436:'에키드나：그렇다。@빈델님과 레몬님이@브릿지에서 기다리고 계신다。',
 0x5FCF478:'라미아：알았다。곧 간다',
 0x5FCF4B5:'레몬：Ｗ１７！@지금까지 어디에 있었어…！？',
 0x5FCF4F7:'라미아：보고가 늦었습니다。@…레몬님도 무사하셨군요。',
 0x5FCF587:'라미아：오른팔을 파괴했습니다。@직후 근거리에서 산탄을 맞아、@안쥬르그도 손상을 입었습니다。',
 0x5FCF5E6:'레몬：그런 손상을 입고도 전이한 거야？@상대의 전투 능력이@예측을 벗어났다는 뜻이겠네…。',
 0x5FCF647:'라미아：예。적의 능력은 예측을 넘었습니다。@베오울프는 저희가 추구하는 세계에도@위협이 될 존재라고 판단합니다。',
 0x5FCF755:'라미아：무슨 뜻입니까？',
 0x5FCF76E:'레몬：…아직은 나도 모르겠어。@Ｗ１７、이쪽으로 전이한 뒤의 일을@보고해 주겠니？',
 0x5FCF7C7:'라미아：이쪽에 온 것은 반년 전입니다。@마지막에 전이한 것은 저지만、@도착 순서는 달라진 모양입니다。',
 0x5FCF8A0:'라미아：손상된 상태로@다시 전투에 휘말렸습니다。',
 0x5FCF94D:'라미아：ＤＣ 잔당의 부품을 확보해@안쥬르그를 수리했습니다。@며칠 전에야 재가동했습니다。',
 0x5FCF9C6:'라미아：제 관절도 손상됐습니다。@안쥬르그와 함께 정비를 요청합니다。@기체 장갑은 교체해야 합니다。',
 0x5FCFA2B:'빈델：보고는 들었다。@어쨌든、잘 돌아왔다…Ｗ１７。',
 0x5FCFABC:'라미아：이쪽 베오울프는요？',
 0x5FCFB17:'라미아：이쪽에 온 지 반년、@행동 가능한 범위에서@정보를 수집했습니다。',
 0x5FCFBFB:'레몬：액셀에게 감시를 맡겼어。@그러니 지금은 네가@직접 접촉할 필요는 없어。',
 0x5FCFC59:'라미아：액셀 대장님께서…@무사히 잠입하신 모양이군요。@통신에는 문제가 없습니까？',
 0x5FCFCBE:'레몬：통신 장치가 고장 나서、@연락이 늦었어。@지금은 조치를 취했지。',
 0x5FCFD06:'라미아：대장님은 무사합니까',
 0x5FCFD2B:'레몬：그래。내가 믿는 사람이야。@그라면 임무를 해낼 거야。',
 0x5FCFD71:'라미아：알겠습니다。@대장님의 보고를 기다리겠습니다。',
 0x5FCFDA9:'라미아：이상입니다',
 0x5FCFDBC:'레몬：그래。',
 0x5FCFDC9:'라미아：다음 지시는요？',
 0x5FCFE8B:'라미아：알겠습니다。@접촉을 피하고@감시를 계속하겠습니다。',
}

# The scenario renderer requires two-byte display characters. ASCII '@' is
# the sole permitted one-byte line-break control, not a displayed glyph.
SPACING_REWRITES={
 0x6662CAE:'라미아：그렇군。@우리　임무는　지령　수행이다。@질문은　철회한다。',
 0x6663211:'라미아（라즈앙그리프나　아슈세이버에도@　응용할　수　있다면@　운용의　폭을　넓힐　수　있다）',
 0x666326E:'라미아（확보할　가치는　있다。@　전이　준비에　지장　없도록@　속히　끝내야　한다）',
 0x66746D5:'라미아：확보　작전　개시。@각기、현　위치에　대기。',
 0x6674C0F:'라미아：아니、형태가　다르다。@출현　경로　불명…@식별　데이터가　없다。',
 0x6674D81:'라미아：빠른　판단이다。@하지만、놓치지　않는다。',
 0x6675828:'라미아（동료를　위해　자신을　희생…@　이해하기　어려운　판단）',
 0x668132B:'라미아：위치가　노출됐나。@확보　실패에　이어@방어선도　위협받고　있다。',
 0x668147B:'라미아：시설은　포기할　수　없다。@접근하는　기체는　적으로　간주한다。@공격　개시。',
 0x6681650:'라미아：시간은　확보했군。@확인했다。',
 0x6681700:'라미아：귀환했습니다。@엑서런스　확보는　실패입니다。@선발대와　빈델님은　출발하셨습니까？',
 0x668185E:'라미아：추후　보고하겠습니다。@레몬님은@잔류자　전이를　맡으십니까？',
 0x6681991:'라미아：현　전력으로@시설을　지킬　수　있겠습니까？',
 0x66819FF:'레몬：위험은　알아、Ｗ１７。@그래도　여기서　멈출　수　없어。@계획대로　진행할　거야。',
 0x6681D38:'라미아：예。액셀　대장님의　조종기술은@알고　있습니다。@대장님은　임무를　완수하실　겁니다。',
 0x6682068:'라미아：이전　교전부터@저희를　추적하고　있습니다。@위험한　상대입니다。',
 0x66820BF:'레몬：이젠　우리가@그의　공격　대상이군。',
 0x6682374:'라미아：목적은　무엇인가。@우리뿐　아니라@세계까지　파괴할　생각인가？',
 0x6682490:'라미아：의사소통이　성립하지　않는다…！@위험　수준을　재평가해야　한다。',
 0x5FCF3A5:'라미아：베오울프…@예측을　넘는　전투력이다。@위험성을　보고해야　한다。',
 0x5FCF436:'에키드나：그렇다。@빈델님과　레몬님이@브릿지에서　기다리신다。',
 0x5FCF587:'라미아：오른팔을　파괴했습니다。@직후　근거리에서　산탄을　맞아、@안쥬르그도　손상됐습니다。',
 0x5FCF8A0:'라미아：손상된　채로@다시　전투에　휘말렸습니다。',
 0x5FCF94D:'라미아：ＤＣ　잔당의　부품으로@안쥬르그를　수리했습니다。@며칠　전에야　재가동했습니다。',
 0x5FCF9C6:'라미아：제　관절도　손상됐습니다。@안쥬르그와　함께　정비를　요청합니다。@장갑은　교체해야　합니다。',
 0x5FCFB17:'라미아：도착　후　반년간、@행동　가능한　범위에서@정보를　수집했습니다。',
 0x5FCFCBE:'레몬：통신　장치　고장으로@연락이　늦었어。@지금은　조치를　취했지。',
 0x5FCFE8B:'라미아：알겠습니다。@접촉을　피하며@계속　감시하겠습니다。',
}
EDITS={off:SPACING_REWRITES.get(off,text).replace(' ','　')
       for off,text in EDITS.items()}
SPACING_SOURCE_SHA='636440785DF1510081F20A92F2D35BEFA901CEB9DC1BFC5A04982DCF1B6E723F'

# CURRENT full-audit continuation. These are precisely the Lamia/Axel scenario
# records with displayed one-byte spaces, plus the adjoining dialogue replies
# and confirmed role-swap residues. Do not include markup-bearing ASCII tags.
DIALOGUE_SOURCE_SHA='6FE0FCDB3EF76C5E523FC72079D0A2D5B975F2ECCA1462F8EECCB63611AC5200'
DIALOGUE_FOLLOWUP_SOURCE_SHA='151D2A411A2965DA31B35BB336A0008BD1CE6380EA08999D8C73B63CF27C650D'
OTHER_SPEAKER_SOURCE_SHA='44D25D22D427508E15D4FC9C09786BB8945A31A0BD9BA5EA0E51A879E9698CAF'
OTHER_SPEAKER_HALF_SPACES={int(x,16) for x in '''
5E8BCFF 5F531D2 6075FA1 60768FF 60786C6 6078722 6079451 607B742
618550B 61855FD 6186A3C 6186FCE 618830D 618848D 618886A 61BAA70
61BAAA4 61F0F9F 61F3D02 62128C4 62C92AA 6381871 638188E 644C0F4
644E16F 6450E8A 6457C27 6457CC6 647C264 661D1BC
'''.split()}
assert len(OTHER_SPEAKER_HALF_SPACES)==30
OTHER_SPEAKER_OVERRIDES={
 0x60786C6:'다이테츠：공격　개시！@　알블레이드와　소울게인을@　구출하고　적을　격파하라！',
 0x61855FD:'쿄스케：섀도우미러…라고！？',
 0x6186FCE:'아라드：거짓말이지……！？@　액셀　씨！！',
 0x618886A:'리오：그리고@　액셀　씨도　일원이고@　우리의　적……',
 0x61BAA70:'레비：너도　봤겠지……@　그　남자를……',
 0x61F0F9F:'젠가：그자의　싸움엔　망설임이　없다。@　결과가　그걸　증명한다。',
 0x6381871:'타스크：……상상해　버렸어',
 0x6450E8A:'라투니：……오우카　언니와의@　추억을　잊기　싫어……',
 0x6457C27:'윤：！？@　함장님！　제１데크에서@　소울게인이　발진합니다！',
 0x647C264:'레피나：카이　소령、길리엄　소령、@　쿄스케　중위、브루클린　소위、@쿠스하　소위、액셀……',
 0x661D1BC:'린：액셀、아이비스。@　크레이들엔　내가　먼저　돌입한다。@　목표는　저기다',
}
DIALOGUE_FOLLOWUP_OVERRIDES={
 0x61EE1A5:'라미아：설마……@액셀　대장입니까？@극형이라고　들었습니다만？',
 0x61EE499:'라미아：액셀　대장、@임무에　따라　말살하겠습니다。',
 0x62958CB:'라미아：겉모습에　속진　마십시오。@저런　협박에　일일이@반응할　필요는　없습니다。',
 0x6554C77:'라미아：레몬님　일행이　베오울프를@이쪽으로　끌어들인다면@더욱　그렇습니다。',
}
LAMIA_SPACES={int(x,16) for x in '''
6072BF2 6072D03 607768E 6077E5F 607A180 6119FD6 623FEAA 623FFF7
6240060 6240523 6245B38 6245C12 6245DC9 6292524 62958CB 6295C47
639A285 639A576 63BFC62 63BFDEF 63BFE9A 63C1F07 63C2971 63E63A9
63E6983 649FD78 64A16E6 64A19E8 64A1E7C 64A263A 64A27A5 64A27D9
64A2A31 64A2BD1 64B25EB 64B2615 64B27E9 64B2B9D 6554BF8 6554C77
6554ECD 655510D 65AD5B1 65AD7D2 65AEF34 65AF078 65B00D7 662CDED
662CE17 662CFEB 662D39F 6682673
'''.split()}
AXEL_SPACES={int(x,16) for x in '''
5E639CC 5E64806 5EA1013 5F07B5E 5F413A4 5F413EC 5F734B0 6077833
613DD4A 61850C4 61851B1 61853C3 61F29D7 61F2A15 61F2AA7 61F2DB7
61F4FD7 61F54A0 62129F7 6212A39 6212D49 6295140 637F6B8 640CBDB
6456AF8 6458189 65359A4 65AF7DC
'''.split()}
assert len(LAMIA_SPACES)==52 and len(AXEL_SPACES)==28
DIALOGUE_OVERRIDES={
 # Scene 2/3 and postwar Lamia. Shortened text retains speaker and story beat.
 0x6072BF2:'라미아：설마…벌써　복구했습니까？@『시스템ＸＮ』을！？',
 0x6072D03:'라미아：…설명해　주십시오。@그　시스템을　외부자에게　알리고@접촉까지　허용하다니、빈델님？',
 0x607768E:'라미아：ＥＧ－Ｘ　소울게인…@액셀　대장을　여기서@뵐　줄은　몰랐습니다。',
 0x6077E5F:'라미아：…네　뜻대로　해라。@전위의　임무라면@나도　막지　않겠다。',
 0x6119FD6:'라미아：…그　여자도　베오울프처럼@우리에　대해선　몰랐습니다。',
 0x623FEAA:'라미아：그럼@현재는　지구인이@우세하다는　겁니까？',
 0x6240060:'라미아：그렇다면、작은　일에@신경　쓸　수는　없습니다。',
 0x6240523:'라미아：베오울프와　헬리오스　외에@있습니까？　아니、베오울프는@지금　쳐야　합니까？',
 0x6245B38:'라미아：…액셀　대장에　이어、Ｗ１５도@명령을　어길　셈인가。레몬님、@재점검이　필요하지　않겠습니까？',
 0x6245DC9:'라미아：녀석들의　자아　확립은@레몬님이　세운　Ｗ시리즈의@개념에　반하지　않습니까？',
 0x6292524:'라미아：알고　계시지요。',
 0x62958CB:'라미아（외견에　속지　말라고？@　저런　협박에　일일이@　반응할　필요는　없다…）',
 0x6295C47:'라미아：녀석들　때문에　베오울프에게@결정타를　가하지　못했습니다。',
 0x639A285:'라미아：녀석이　문크레이들의@방위　임무를　버렸다는　말은……',
 0x639A576:'라미아：양산형？@시스템ＸＮ　말입니까？',
 0x63BFC62:'라미아：베오울프와　액셀　대장도@이쪽으로　오는　건가？',
 0x63BFDEF:'라미아：……콕핏을　부쉈다면　그렇겠지。@한　방…１초면　끝날@동작을　하지　못했습니다。',
 0x63BFE9A:'라미아（그래……라울・그레덴과@　다시　만났을　때、액셀　대장의@　태도가　그걸　증명했지）',
 0x63C1F07:'라미아：자아、베오울프、액셀　대장……@서로의　주장은　다　들었다。@남은　건　누가　옳은지　겨루는　것뿐。',
 0x63C2971:'라미아：자기　판단？@Ｗ넘버인　네가…',
 0x63E63A9:'라미아：이　승부에@　세계의　명운을　건다……@　그런　말은　하지　않겠다。',
 0x63E6983:'라미아：이제　우린　모두　이방인…@함께　지낼　수　있으리라@생각했는데　말입니다。',
 0x649FD78:'라미아：뭡니까……？@아규이에우스와　류케이오스　외에@또　있다는　겁니까？',
 0x64A16E6:'라미아：살던　세계와　닮았지만@결정적으로　다른　부분을　말입니다。',
 0x64A19E8:'라미아：나도　그동안@수많은　동료를　잃었다。@그들이　믿는　전쟁　속에서。',
 0x64A1E7C:'라미아：헬리오스・올림푸스가@개발한　공간・차원전이장치、@시스템ＸＮ입니다。',
 0x64A263A:'라미아：액셀　대장。@그　후、베오울프는@어떻게　됐습니까？',
 0x64A27A5:'라미아：그렇습니까。@이걸로　우환이　줄었습니다。',
 0x64A27D9:'라미아：그　말씀이　사실이라면……@대장은　빈델님을@배신하셨군요。',
 0x64A2A31:'라미아：액셀　대장、@베오울프가　얻은　힘으로@저와　싸울　수　있겠습니까？',
 0x64A2BD1:'라미아：가까운　사람이@전장에서　쓰러졌다면、그토록@태연할　수는　없을　겁니다。',
 0x64B25EB:'라미아：설마@그걸로　끝낼　참입니까？',
 0x64B2615:'라미아：그　정도십니까、대장。@마무리도　못　하시는군요。',
 0x64B27E9:'라미아：대장、또@이상해지신　겁니까？',
 0x64B2B9D:'라미아：뭐란　겁니까？@모르겠군요。',
 0x6554C77:'라미아：당신들이　베오울프들을@이쪽으로　끌어들인다면@더욱　그렇습니다。',
 0x655510D:'라미아：…확실히　그렇군요。@그럼　누굴　보내실　겁니까？@무능한　자를　보내봐야…',
 0x65AD5B1:'라미아：베오울프를　감시한다。@참견　마라。액셀　대장께도@전해라。',
 0x65AD7D2:'라미아：그렇겠지。@하지만　네놈에　대해선　잘　안다。@얼마나　위험한　자인지도。',
 0x65AEF34:'라미아：우리　병력과@레몬님의　넘버즈를　물리쳤군。',
 0x65AF078:'라미아：이미　말했다。@네놈이　알　필요　없는　일이다！',
 0x65B00D7:'라미아：기체의　외견과　성능이　달랐습니다。@그　남자는…@보통　인간이었습니다。',
 0x662CDED:'라미아：설마@그걸로　끝낼　참입니까？',
 0x662CE17:'라미아：그　정도십니까、대장。@마무리도　못　하시는군요。',
 0x662CFEB:'라미아：대장、또@이상해지신　겁니까？',
 0x662D39F:'라미아：뭐란　겁니까？@모르겠군요。',
 0x6682673:'라미아：불확실한　요소는@제거해야　합니다。@베오울프도　예외는　아닙니다。',
 # Axel strings that cannot be widened mechanically or whose punctuation is bad.
 0x5E25655:'액셀（브로우닝……@　브로우닝이라고？）',
 0x5E639CC:'액셀：추격이　아니라　격파　명령이군。@　적은　달아날　생각이　없단　말이지。',
 0x5E64806:'액셀：기다려、저건……！',
 0x5F413EC:'액셀（또한@　헬리오스　정보　입수……。@　가능하면　신병을　확보）',
 0x5F734B0:'액셀（ＡＩ　제어……@　아니、사람이　타고　있나）',
 0x5F71F2C:'액셀（저건……@　라즈……앙그리프……？）',
 0x613DD4A:'액셀（신형　아인스트……。@　아니、저건！？）',
 0x61850C4:'액셀：움직이지　마라！',
 0x61851B1:'액셀：……쿄스케。@　너희에게　설명할　생각은　없다。@　무장을　해제해라。',
 0x6212A39:'액셀：그리고@　섀도우미러　외의　전이자는@　나타나지　않았다는　건……',
 0x6212D49:'액셀（그렇게@　이　부대도　강해지는군……）',
 0x637F6B8:'액셀：시작의　땅……@지구를　말하는　건가？',
 # Responses and conspicuous non-space role residues from the same scenes.
 0x6662AC5:'Ｗ１６：넘버즈　０번부터　１０번까지@준비　완료。',
 0x6662B87:'Ｗ１６：그래。@레몬님이　그렇게　지시하셨다。',
 0x6662C62:'Ｗ１６：나는　레몬님의　지령을　수행한다。@그　밖에　의문은　없다。',
 0x66816CD:'Ｗ１６：응',
 0x6681DE1:'레몬：Ｗ１７、뭘　하는　거야？',
 0x65AF12A:'라미아：피닉스！',
 0x5F058AE:'빈델：……그래서@　액셀의　보고는？',
 0x5F40C69:'에키드나：베오울프인가。@　대장도　자료를@　모았겠지만……',
 0x5F70E2B:'빈델：……액셀에게@　문제는　없겠지？',
 0x63C28F2:'에키드나：레몬님을…@지켜야　한다……',
 0x63C2A5A:'에키드나：그리고…@레몬님을　위해서…',
 # Current contextual review: the experienced human Axel understands grief;
 # W16's self-directed protection and W17's last choice must not be negated.
 0x6295202:'액셀（…슬프군。@전우를　잃는　건@　익숙해지지　않아）',
 0x63E75C3:'액셀（레몬……@　네가　바란　존재는……）',
 0x63E760D:'액셀（Ｗ１６은　스스로　레몬을　지켰다。@　Ｗ１７도　마지막엔　선택했다。@　둘　다　인형은　아니었어……）',
}

def validate_display(text):
    assert not any(ord(c)<128 and c!='@' for c in text),repr(text)
    assert text.count('@')<=2
    assert all(len(encode(line))<=54 for line in text.split('@')),text
    assert decode(encode(text))==text

def repair_all_dialogue(f,apply):
    """Guarded continuation of the already-applied CURRENT patch."""
    history=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if 'full_dialogue_repair' in history:
        raise ValueError('Full dialogue repair already recorded')
    target_offsets=LAMIA_SPACES|AXEL_SPACES|set(DIALOGUE_OVERRIDES)
    assert len(LAMIA_SPACES)==52 and len(AXEL_SPACES)==28
    plan=[];problems=[]
    with (ROOT/'baseline/srwogs-v1.4.3s1.iso').open('rb') as baseline:
        for off in sorted(target_offsets):
            where=MAP+off
            baseline.seek(where)
            capacity=len(baseline.read(1024).split(b'\0',1)[0])
            f.seek(where);old=f.read(capacity)
            if len(old)!=capacity or b'\0' in old.rstrip(b'\0'):
                problems.append((hex(off),'nonzero after NUL or truncated'))
                continue
            old_text=decode(old.split(b'\0',1)[0])
            new=DIALOGUE_OVERRIDES.get(off)
            if new is None:
                new=(old_text.replace(' ','　').replace('!', '！')
                             .replace('?', '？').replace('.', '。'))
            try:
                validate_display(new)
                raw=encode(new)
            except (AssertionError,UnicodeError) as error:
                problems.append((hex(off),'display/codec',str(error),new))
                continue
            if re.split('[：（]',old_text)[0]!=re.split('[：（]',new)[0]:
                problems.append((hex(off),'speaker changed',old_text,new))
                continue
            if len(raw)>capacity:
                problems.append((hex(off),'capacity',len(raw),capacity,new))
                continue
            if off in LAMIA_SPACES|AXEL_SPACES and ' ' not in old_text:
                problems.append((hex(off),'expected halfwidth space missing',old_text))
                continue
            new_bytes=raw.ljust(capacity,b'\0')
            if old!=new_bytes:
                plan.append({'off':off,'iso_off':where,'old_bytes':old,
                             'new_bytes':new_bytes,'orig':old_text,'new':new})
    if problems:
        for item in problems:print('PROBLEM',item,flush=True)
        raise ValueError(f'{len(problems)} guard failures; no ISO writes')
    assert all(a['iso_off']+len(a['old_bytes'])<=b['iso_off']
               for a,b in zip(plan,plan[1:]))
    print(f'Validated {len(target_offsets)} exact scenario slots; {len(plan)} changed.',flush=True)
    if not apply:return
    before=digest(f)
    if before!=DIALOGUE_SOURCE_SHA:
        raise ValueError(f'Unexpected CURRENT SHA256 {before}')
    target=digest(f,plan)
    record={'status':'prepared','before_sha256':before,'target_sha256':target,
            'live_verified':False,'count':len(plan),
            'edits':[{'off':hex(p['off']),'iso_off':p['iso_off'],
                      'before_hex':p['old_bytes'].hex(),'after_hex':p['new_bytes'].hex(),
                      'orig':p['orig'],'new':p['new']} for p in plan]}
    history['full_dialogue_repair']=record
    MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for p in plan:
            f.seek(p['iso_off']);f.write(p['new_bytes'])
        f.flush();os.fsync(f.fileno())
        assert digest(f)==target,'whole ISO hash mismatch'
    except Exception:
        for p in plan:
            f.seek(p['iso_off']);f.write(p['old_bytes'])
        f.flush();os.fsync(f.fileno())
        assert digest(f)==before,'rollback verification failed'
        record['status']='rolled_back'
        MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    record['status']='applied'
    MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT dialogue repaired:',target,flush=True)

def repair_dialogue_followup(f,apply):
    history=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if 'dialogue_followup' in history:
        raise ValueError('Dialogue follow-up already recorded')
    plan=[]
    with (ROOT/'baseline/srwogs-v1.4.3s1.iso').open('rb') as baseline:
        for off,new in sorted(DIALOGUE_FOLLOWUP_OVERRIDES.items()):
            where=MAP+off
            baseline.seek(where);capacity=len(baseline.read(1024).split(b'\0',1)[0])
            f.seek(where);old=f.read(capacity)
            old_text=decode(old.split(b'\0',1)[0])
            validate_display(new)
            assert re.split('[：（]',old_text)[0]==re.split('[：（]',new)[0]
            raw=encode(new)
            assert len(raw)<=capacity,(hex(off),len(raw),capacity)
            assert old==old.split(b'\0',1)[0].ljust(capacity,b'\0')
            assert old!=raw.ljust(capacity,b'\0')
            plan.append({'off':off,'iso_off':where,'old_bytes':old,
                         'new_bytes':raw.ljust(capacity,b'\0'),
                         'orig':old_text,'new':new})
    print('Validated follow-up dialogue slots:',len(plan),flush=True)
    if not apply:return
    before=digest(f)
    if before!=DIALOGUE_FOLLOWUP_SOURCE_SHA:
        raise ValueError(f'Unexpected CURRENT SHA256 {before}')
    target=digest(f,plan)
    record={'status':'prepared','before_sha256':before,'target_sha256':target,
            'live_verified':False,
            'edits':[{'off':hex(p['off']),'iso_off':p['iso_off'],
                      'before_hex':p['old_bytes'].hex(),'after_hex':p['new_bytes'].hex(),
                      'orig':p['orig'],'new':p['new']} for p in plan]}
    history['dialogue_followup']=record
    MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for p in plan:f.seek(p['iso_off']);f.write(p['new_bytes'])
        f.flush();os.fsync(f.fileno())
        assert digest(f)==target
    except Exception:
        for p in plan:f.seek(p['iso_off']);f.write(p['old_bytes'])
        f.flush();os.fsync(f.fileno());assert digest(f)==before
        record['status']='rolled_back'
        MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    record['status']='applied'
    MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT dialogue follow-up repaired:',target,flush=True)

def repair_other_speaker_spacing(f,apply):
    """Repair all patch-introduced halfwidth dialogue outside Lamia/Axel."""
    history=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if 'other_speaker_spacing_repair' in history:
        raise ValueError('Other-speaker spacing repair already recorded')
    plan=[]
    with (ROOT/'baseline/srwogs-v1.4.3s1.iso').open('rb') as baseline:
        for off in sorted(OTHER_SPEAKER_HALF_SPACES):
            where=MAP+off
            baseline.seek(where)
            capacity=len(baseline.read(1024).split(b'\0',1)[0])
            f.seek(where);old=f.read(capacity)
            assert old==old.split(b'\0',1)[0].ljust(capacity,b'\0'),hex(off)
            old_text=decode(old.split(b'\0',1)[0])
            assert ' ' in old_text,hex(off)
            new=OTHER_SPEAKER_OVERRIDES.get(off)
            if new is None:
                new=(old_text.replace(' ','　').replace('!','！')
                             .replace('?','？').replace('.','。').replace('1','１'))
            validate_display(new)
            assert re.split('[：（]',old_text)[0]==re.split('[：（]',new)[0],hex(off)
            raw=encode(new)
            assert len(raw)<=capacity,(hex(off),len(raw),capacity)
            new_bytes=raw.ljust(capacity,b'\0')
            assert old!=new_bytes,hex(off)
            plan.append({'off':off,'iso_off':where,'old_bytes':old,
                         'new_bytes':new_bytes,'orig':old_text,'new':new})
    assert len(plan)==30
    assert all(a['iso_off']+len(a['old_bytes'])<=b['iso_off']
               for a,b in zip(plan,plan[1:]))
    print('Validated other-speaker dialogue slots:',len(plan),flush=True)
    if not apply:return
    before=digest(f)
    if before!=OTHER_SPEAKER_SOURCE_SHA:
        raise ValueError(f'Unexpected CURRENT SHA256 {before}')
    target=digest(f,plan)
    record={'status':'prepared','before_sha256':before,'target_sha256':target,
            'live_verified':False,'count':len(plan),
            'edits':[{'off':hex(p['off']),'iso_off':p['iso_off'],
                      'before_hex':p['old_bytes'].hex(),'after_hex':p['new_bytes'].hex(),
                      'orig':p['orig'],'new':p['new']} for p in plan]}
    history['other_speaker_spacing_repair']=record
    MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for p in plan:f.seek(p['iso_off']);f.write(p['new_bytes'])
        f.flush();os.fsync(f.fileno())
        assert digest(f)==target,'whole ISO hash mismatch'
    except Exception:
        for p in plan:f.seek(p['iso_off']);f.write(p['old_bytes'])
        f.flush();os.fsync(f.fileno())
        assert digest(f)==before,'rollback verification failed'
        record['status']='rolled_back'
        MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    record['status']='applied'
    MANIFEST.write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT other-speaker spacing repaired:',target,flush=True)

def repair_spacing(f,apply):
    report=json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert 'spacing_repair' not in report,'Spacing repair already recorded'
    plan=[]
    for row in report['edits']:
        if 'kind' in row:continue
        off=int(row['off'],16);new=EDITS[off];validate_display(new)
        old=encode(row['new']).ljust(row['length'],b'\0')
        raw=encode(new)
        assert len(raw)<=row['length'],(row['off'],len(raw),row['length'])
        assert re.split('[：（]',new)[0]==re.split('[：（]',row['new'])[0]
        f.seek(row['iso_off']);assert f.read(row['length'])==old,row['off']
        raw=raw.ljust(row['length'],b'\0')
        if raw!=old:plan.append({'iso_off':row['iso_off'],'old_bytes':old,'new_bytes':raw,'new':new})
    print('Validated all 117 display strings; changed slots:',len(plan),flush=True)
    if not apply:return
    before=digest(f);assert before==SPACING_SOURCE_SHA,before
    target=digest(f,plan)
    record={'status':'prepared','before_sha256':before,'target_sha256':target,
            'live_verified':False,'edits':[{'iso_off':p['iso_off'],'before_hex':p['old_bytes'].hex(),'after_hex':p['new_bytes'].hex(),'text':p['new']} for p in plan]}
    report['spacing_repair']=record
    MANIFEST.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for p in plan:f.seek(p['iso_off']);f.write(p['new_bytes'])
        f.flush();os.fsync(f.fileno())
        assert digest(f)==target,'Whole-file verification failed'
    except Exception:
        for p in plan:f.seek(p['iso_off']);f.write(p['old_bytes'])
        f.flush();os.fsync(f.fileno());assert digest(f)==before
        record['status']='rolled_back'
        MANIFEST.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    record['status']='applied'
    MANIFEST.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT spacing repaired:',target,flush=True)

def digest(f,plan=()):
    h=hashlib.sha256();f.seek(0);pos=0
    while b:=f.read(8*1024*1024):
        b=bytearray(b)
        for p in plan:
            lo=max(pos,p['iso_off']);hi=min(pos+len(b),p['iso_off']+len(p['new_bytes']))
            if lo<hi:b[lo-pos:hi-pos]=p['new_bytes'][lo-p['iso_off']:hi-p['iso_off']]
        h.update(b);pos+=len(b)
    return h.hexdigest().upper()

def plan_edits(f):
    plan=[];bad=[]
    for off,new in EDITS.items():
        f.seek(MAP+off);old=f.read(512).split(b'\0',1)[0]
        orig=decode(old);validate_display(new);raw=encode(new)
        assert encode(orig)==old
        assert re.split('[：（]',orig)[0]==re.split('[：（]',new)[0],hex(off)
        assert new.count('@')<=2
        assert encode(decode(raw))==raw
        if len(raw)>len(old):bad.append((hex(off),len(raw),len(old),new))
        plan.append({'off':hex(off),'iso_off':MAP+off,'orig':orig,'new':new,
                     'old_bytes':old,'new_bytes':raw.ljust(len(old),b'\0')})
    if bad:raise ValueError(f'Over-capacity slots: {bad}')
    return plan

def plan_weapons(f):
    import build_stage35_soulgain_return_hotfix as m
    plan=[]
    with m.BASELINE.open('rb') as baseline:
        for label,base in m.ARCHIVES.items():
            at=m.unit_off(base,m.SOULGAIN_SLOT)
            f.seek(at);unit=f.read(m.UNIT_STRIDE)
            assert m.u16(unit,0x46)==m.UID_ANGELG
            assert struct.unpack_from('<5H',unit,0x24)==m.ENHANCED_WEAPONS
            f.seek(m.unit_off(base,m.RETURN_SLOT));soul=f.read(m.UNIT_STRIDE)
            assert struct.unpack_from('<5H',soul,0x24)==m.ENHANCED_WEAPONS
            assert m.u16(soul,0x46)==m.UID_SOULGAIN
            for offset,old,new in m.isolated_angelg_weapon_plan(f,baseline,base):
                plan.append({'off':hex(offset),'iso_off':offset,
                    'orig':old.hex(),'new':new.hex(),'old_bytes':old,'new_bytes':new,
                    'kind':label+' isolated original Angelg weapon'})
            old=unit[0x24:0x2E]
            new=struct.pack('<5H',*m.REVERSE_ANGELG_WEAPONS)
            plan.append({'off':hex(at+0x24),'iso_off':at+0x24,
                'orig':old.hex(),'new':new.hex(),'old_bytes':old,'new_bytes':new,
                'kind':label+' Unit136 weapon references'})
    return plan

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--repair-spacing',action='store_true');ap.add_argument('--repair-all-dialogue',action='store_true');ap.add_argument('--repair-dialogue-followup',action='store_true');ap.add_argument('--repair-other-speakers',action='store_true');args=ap.parse_args()
    if args.apply:
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
        k.CreateFileW.restype=ctypes.c_void_p
        h=k.CreateFileW(str(ISO),0xC0000000,0,None,3,0,None)
        if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        f=os.fdopen(msvcrt.open_osfhandle(h,os.O_RDWR|os.O_BINARY),'r+b')
    else:f=ISO.open('rb')
    with f:
        if args.repair_other_speakers:return repair_other_speaker_spacing(f,args.apply)
        if args.repair_dialogue_followup:return repair_dialogue_followup(f,args.apply)
        if args.repair_all_dialogue:return repair_all_dialogue(f,args.apply)
        if args.repair_spacing:return repair_spacing(f,args.apply)
        plan=plan_edits(f)
        print(f'{len(plan)} text slots fit; speaker names/order preserved.',flush=True)
        weapons=plan_weapons(f)
        print(f'{len(weapons)} guarded weapon ranges; enhanced Soulgain untouched.',flush=True)
        plan+=weapons
        ordered=sorted(plan,key=lambda p:p['iso_off'])
        assert all(a['iso_off']+len(a['old_bytes'])<=b['iso_off'] for a,b in zip(ordered,ordered[1:]))
        for p in plan: print(p['off'],p['orig'],'=>',p['new'],flush=True)
        if not args.apply:return
        before=digest(f)
        if before!=EXPECTED:raise ValueError(f'Unexpected CURRENT hash: {before}')
        if BACKUP.exists() or MANIFEST.exists():raise FileExistsError('Refusing to overwrite repair evidence')
        target=digest(f,plan)
        backup=b''.join(p['old_bytes'] for p in plan);BACKUP.write_bytes(backup)
        pos=0;changes=[]
        for p in plan:
            changes.append({k:v for k,v in p.items() if k not in ('old_bytes','new_bytes')}|{'backup_pos':pos,'length':len(p['old_bytes'])})
            pos+=len(p['old_bytes'])
        report={'status':'prepared','before_sha256':before,'target_sha256':target,'backup_sha256':hashlib.sha256(backup).hexdigest().upper(),'edits':changes,'scope':'OG2 early Lamia scenes and DC-ship reunion; isolate Unit136 Angelg weapons. Battle text, portrait commands, enhanced Soulgain and memory cards unchanged','live_verified':False}
        MANIFEST.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        try:
            for p in plan:f.seek(p['iso_off']);f.write(p['new_bytes'])
            f.flush();os.fsync(f.fileno())
            assert digest(f)==target,'Whole-file verification failed'
        except Exception:
            for p in plan:f.seek(p['iso_off']);f.write(p['old_bytes'])
            f.flush();os.fsync(f.fileno())
            assert digest(f)==before,'Rollback verification failed'
            raise
        report['status']='applied';report['changed_bytes']=sum(sum(a!=b for a,b in zip(p['old_bytes'],p['new_bytes'])) for p in plan)
        MANIFEST.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Updated CURRENT in place:',target,flush=True)

if __name__=='__main__':main()
