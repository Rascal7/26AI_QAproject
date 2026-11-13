await figma.loadFontAsync({family:'Noto Sans KR',style:'Regular'});
await figma.loadFontAsync({family:'Noto Sans KR',style:'Bold'});
const bset=await figma.importComponentSetByKeyAsync('cc8b558dc7d9684011b6b99ce8e6509399bc836b');
const cset=await figma.importComponentSetByKeyAsync('a5bde480886231526d7dd890df3779dc15b52423');
const button=bset.children.find(n=>n.name==='Variant=Primary, State=Default, Size=Medium');
const card=cset.children.find(n=>n.name==='Asset Type=Icon, Variant=Stroke, Direction=Vertical');
const bg=await figma.variables.importVariableByKeyAsync('3fe6117980bb52e96ac3ed63a40765746e689874');
const ids=[];
const rgb=h=>({r:parseInt(h.slice(0,2),16)/255,g:parseInt(h.slice(2,4),16)/255,b:parseInt(h.slice(4,6),16)/255});
const fill=h=>[{type:'SOLID',color:rgb(h)}];
function box(parent,name,w,h,dir='VERTICAL',color='FFFFFF',pad=0,gap=16){
 const n=figma.createAutoLayout();ids.push(n.id);n.name=name;n.layoutMode=dir;n.resize(w,h);n.primaryAxisSizingMode='FIXED';n.counterAxisSizingMode='FIXED';n.fills=fill(color);n.itemSpacing=gap;n.paddingLeft=n.paddingRight=n.paddingTop=n.paddingBottom=pad;parent.appendChild(n);return n;
}
function text(parent,s,size=16,color='22283E',bold=false,w){
 const n=figma.createText();ids.push(n.id);n.fontName={family:'Noto Sans KR',style:bold?'Bold':'Regular'};n.fontSize=size;n.characters=s;n.fills=fill(color);n.lineHeight={unit:'PERCENT',value:150};parent.appendChild(n);if(w){n.textAutoResize='HEIGHT';n.resize(w,n.height);}return n;
}
async function inst(source,parent,props){
 const n=source.createInstance();ids.push(n.id);
 for(const t of n.findAllWithCriteria({types:['TEXT']})){for(const s of t.getStyledTextSegments(['fontName']))await figma.loadFontAsync(s.fontName);}
 parent.appendChild(n);n.setProperties(props);
 for(const t of n.findAllWithCriteria({types:['TEXT']})){t.fontName={family:'Noto Sans KR',style:'Regular'};ids.push(t.id);}
 return n;
}
async function action(parent,label){
 const n=await inst(button,parent,{'Label#2:0':label,'Has Icon Start#4:128':false,'Has Icon End#4:64':false});n.fills=fill('6C5CE7');n.cornerRadius=9;return n;
}
function screen(name,x,active){
 const root=box(figma.currentPage,name,1440,1000,'HORIZONTAL','F7F8FC',0,0);root.x=x;root.y=100;
 const side=box(root,'Navigation',240,1000,'VERTICAL','171D30',28,26);
 text(side,'◈  QA LAB',24,'FFFFFF',true);text(side,'WORKSPACE',11,'99A4BC');text(side,'▦  프로젝트',16,'C4BAFF',true);
 if(active!=='dashboard'){text(side,'로그인 데모',14,'FFFFFF',true);for(const s of ['요구사항','테스트','실행','실행 기록'])text(side,s,15,s===active?'C4BAFF':'ADB5CA',s===active);}
 const main=box(root,'Workspace',1200,1000,'VERTICAL','F7F8FC',48,28);return {root,main};
}
const d=screen('01 · 프로젝트 대시보드',100,'dashboard');
const header=box(d.main,'Header',1104,104,'HORIZONTAL','F7F8FC',0,20);
const title=box(header,'Title',890,104,'VERTICAL','F7F8FC',0,4);text(title,'WORKSPACE',11,'747D91');text(title,'프로젝트',32,'22283E',true);text(title,'웹페이지별 QA, 한곳에서.',15,'747D91');await action(header,'+ 새 프로젝트');
const strip=box(d.main,'Workflow',1104,60,'HORIZONTAL','F0EDFF',18,100);strip.cornerRadius=12;
for(const s of ['① 프로젝트 만들기','② 테스트 추가','③ 실행·기록'])text(strip,s,14,'6854C7');
const cards=box(d.main,'Project cards',1104,280,'HORIZONTAL','F7F8FC',0,24);
for(const [name,url,counts] of [['로그인 데모','127.0.0.1:5000','요구사항 10  ·  테스트 10'],['쇼핑몰 주문','example.com/checkout','요구사항 3  ·  테스트 8']]){
 const n=await inst(card,cards,{'Heading#280:0':name,'Body#280:13':url+'\n\n'+counts,'Button#113:15':false});n.resize(530,265);n.cornerRadius=14;
}
text(d.main,'최근 실행',20,'22283E',true);
for(const data of [['로그인 데모','11월 04일 15:20','PASS 10'],['쇼핑몰 주문','11월 04일 14:45','PASS 7 · FAIL 1']]){
 const row=box(d.main,'Execution record',1104,64,'HORIZONTAL','FFFFFF',20,40);row.cornerRadius=10;text(row,data[0],15,'22283E',true,360);text(row,data[1],14,'747D91',false,340);text(row,data[2],14,'268C6F');
}
const q=screen('02 · 프로젝트 요구사항',1640,'요구사항');text(q.main,'프로젝트 / 로그인 데모',13,'747D91');text(q.main,'요구사항',30,'22283E',true);text(q.main,'로그인 데모 · 127.0.0.1:5000',14,'747D91');
const overall=box(q.main,'Whole project specification',1104,210,'HORIZONTAL','FFFFFF',24,24);overall.cornerRadius=14;
for(const [heading,body] of [['전체 요구사항','이메일로 로그인하고 사용자 홈으로 이동한다.'],['전체 예외사항','잘못된 입력과 제한된 계정은 안전하게 차단한다.']]){
 const col=box(overall,heading,516,162,'VERTICAL','FFFFFF',0,12);text(col,heading,16,'22283E',true);text(col,body,15,'747D91',false,480);
}
const rh=box(q.main,'Requirements header',1104,50,'HORIZONTAL','F7F8FC',0,760);text(rh,'요구사항',20,'22283E',true);await action(rh,'+ 추가');
for(const name of ['정상 로그인','잘못된 비밀번호','비활성 계정 차단']){
 const row=box(q.main,'Requirement',1104,95,'HORIZONTAL','FFFFFF',24,300);row.cornerRadius=12;text(row,name,17,'22283E',true,540);text(row,'테스트 보기 →',14,'6C5CE7');
}
const t=screen('03 · 요구사항별 테스트',3180,'테스트');text(t.main,'로그인 데모 / 테스트',13,'747D91');text(t.main,'테스트',30,'22283E',true);
const tabs=box(t.main,'Tabs',1104,52,'HORIZONTAL','F7F8FC',0,40);text(tabs,'등록된 테스트',15,'747D91');text(tabs,'기본 테스트 추가',15,'747D91');text(tabs,'AI로 추가',15,'6C5CE7',true);
const prompt=box(t.main,'AI request',1104,250,'VERTICAL','FFFFFF',24,18);prompt.cornerRadius=14;text(prompt,'어떤 테스트를 할까요?',20,'22283E',true);
const input=box(prompt,'Prompt',1056,88,'VERTICAL','F3F4F9',16,8);input.cornerRadius=10;input.fills=[figma.variables.setBoundVariableForPaint(input.fills[0],'color',bg)];text(input,'이메일을 비우고 로그인하면 오류 문구가 표시되는지 확인해줘.',15,'747D91',false,1000);await action(prompt,'✦ 테스트 생성');
const draft=box(t.main,'Review generated steps',1104,270,'VERTICAL','FFFFFF',24,18);draft.cornerRadius=14;text(draft,'빈 이메일 입력 검증',20,'22283E',true);text(draft,'페이지 이동  →  로그인 클릭  →  오류 문구 확인',16,'747D91');text(draft,'선택자와 기대 문구를 검토한 뒤 추가하세요.',14,'8A6A2F');await action(draft,'프로젝트에 추가');
figma.viewport.scrollAndZoomIntoView([d.root]);
return {createdNodeIds:ids,frames:[{id:d.root.id,name:d.root.name},{id:q.root.id,name:q.root.name},{id:t.root.id,name:t.root.name}],font:'Noto Sans KR',editable:true};
