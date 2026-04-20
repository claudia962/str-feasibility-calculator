import https from 'https';
const token = 'sbp_541ec1b3cce5bb3d627c57c5ae5fdb1e114a492c';
const PROJECT = 'eywxieynkuioyycgnbbe';
async function q(sql) {
  return new Promise(r => {
    const body = JSON.stringify({query:sql});
    const opts = {hostname:'api.supabase.com',path:`/v1/projects/${PROJECT}/database/query`,method:'POST',headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json','Content-Length':Buffer.byteLength(body),'User-Agent':'claudia-code'}};
    const req = https.request(opts,res=>{let b='';res.on('data',d=>b+=d);res.on('end',()=>r({s:res.statusCode,b}))});
    req.on('error',e=>r({s:0,b:e.message}));
    req.write(body);req.end();
  });
}
// Check what columns feature_flags has
let r = await q("SELECT column_name FROM information_schema.columns WHERE table_name='feature_flags'");
console.log('feature_flags cols:', r.s, r.b);
// Insert using correct column
r = await q("INSERT INTO feature_flags (flag_name,enabled,description) VALUES ('FEASIBILITY_AUTO_REFRESH',TRUE,'Monthly auto-refresh') ON CONFLICT (flag_name) DO NOTHING");
console.log('insert:', r.s, r.b.slice(0,200));
// Verify tables exist
r = await q("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name");
console.log('tables:', r.s, r.b.slice(0,500));
