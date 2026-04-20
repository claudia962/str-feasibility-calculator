import https from 'https';
const API = 'str-feasibility-api.vercel.app';
function req(method, path, body=null) {
  return new Promise(resolve=>{
    const s=body?JSON.stringify(body):null;
    const o={hostname:API,path,method,headers:{'Content-Type':'application/json','User-Agent':'claudia-code',...(s?{'Content-Length':Buffer.byteLength(s)}:{})}};
    const r=https.request(o,res=>{let b='';res.on('data',d=>b+=d);res.on('end',()=>resolve({s:res.statusCode,b}))});
    r.on('error',e=>resolve({s:0,b:e.message}));
    if(s)r.write(s);r.end();
  });
}
console.log('Testing https://'+API);
const t=Date.now();
const res=await req('POST','/api/feasibility/analyze',{address:'58 Jeffcott Street West Melbourne VIC 3003',property_type:'apartment',bedrooms:2,bathrooms:2.0,purchase_price:780000,down_payment_pct:20.0,mortgage_rate_pct:6.5,mortgage_term_years:30});
const elapsed=Date.now()-t;
console.log('status:',res.s,'elapsed:',elapsed+'ms');
try {
  const j=JSON.parse(res.b);
  console.log('analysis_status:',j.status,'id:',j.id);
  console.log('steps:',j.steps_complete);
  console.log('score:',j.overall_feasibility_score,'rec:',j.recommendation);
  if(j.comps) console.log('comps:',j.comps.length,'src:',j.comps[0]?.data_source);
  if(j.financials) console.log('gross:$'+j.financials.year1_gross_revenue,'noi:$'+j.financials.noi,'cap:',j.financials.cap_rate);
} catch { console.log('body:',res.b.slice(0,500)); }
