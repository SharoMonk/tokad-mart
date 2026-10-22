'use client'
import {useEffect,useMemo,useRef,useState} from 'react'

type Item={id:number;sku:string;name:string;currency:string;unit_price_minor:number;stock:number}
type Location={code:string;name:string;terminals:{code:string;name:string}[]}
type Sale={sale_id:number;reference:string;total_minor:number;payment_status:string}
type Shift={id:number;status:string;opening_cash_minor:number;expected_cash_minor?:number;variance_minor?:number}
type Receipt={reference:string;created_at:string;total_minor:number;lines:{name:string;quantity:number;line_total_minor:number}[]}

const money=(n:number)=>new Intl.NumberFormat('en-NG',{style:'currency',currency:'NGN'}).format(n/100)

export default function CanonicalPOS(){
 const [username,setUsername]=useState('')
 const [password,setPassword]=useState('')
 const [auth,setAuth]=useState(false)
 const [role,setRole]=useState('')
 const [reviewShiftId,setReviewShiftId]=useState('')
 const [reviewNotes,setReviewNotes]=useState('')
 const [reviewDecision,setReviewDecision]=useState('APPROVED')
 const [shift,setShift]=useState<Shift|null>(null)
 const [openingCash,setOpeningCash]=useState('0')
 const [closingCash,setClosingCash]=useState('0')
 const [locations,setLocations]=useState<Location[]>([])
 const [location,setLocation]=useState('')
 const [terminal,setTerminal]=useState('')
 const [query,setQuery]=useState('')
 const [scanCode,setScanCode]=useState('')
 const [scanBusy,setScanBusy]=useState(false)
 const [products,setProducts]=useState<Item[]>([])
 const [cart,setCart]=useState<{item:Item;quantity:number}[]>([])
 const [sale,setSale]=useState<Sale|null>(null)
 const [receipt,setReceipt]=useState<Receipt|null>(null)
 const [message,setMessage]=useState('')
 const [busy,setBusy]=useState(false)
 const attempt=useRef<{fingerprint:string;id:string}|null>(null)
 const sending=useRef(false)
 const scanning=useRef(false)
 const total=useMemo(()=>cart.reduce((n,x)=>n+x.item.unit_price_minor*x.quantity,0),[cart])
 const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.split('=')[1]||'')
 const api=async(path:string,options:RequestInit={})=>{
  const response=await fetch('/api/transactional/'+path,{
   ...options,credentials:'same-origin',cache:'no-store',
   headers:{...(options.method&&options.method!=='GET'?{'X-CSRFToken':csrf()}:{}),...options.headers}
  })
  const result=await response.json()
  if(!response.ok){
   if(response.status===401 || (response.status===403 && (result.error==='not_authenticated' || result.detail==='Authentication credentials were not provided.'))){
    setAuth(false);setShift(null);setPassword('')
    setMessage('Cashier session expired. Sign in again; your pending cart is retained for safe retry.')
    throw Error('Session expired — sign in again to continue.')
   }
   throw Error(result.message||result.error||'Request failed')
  }
  return result
 }
 async function refreshShift(loc=location,term=terminal){
  if(!loc||!term)return
  const data=await api('pos/shifts/?'+new URLSearchParams({location_code:loc,terminal_code:term}))
  setShift(data.shift)
 }
 async function initialize(){
  try{
   const session=await api('pos/session/')
   if(!session.authenticated){setAuth(false);setShift(null);return}
   const scope=await api('pos/scope/')
   if(!scope.locations.length)return
   setLocations(scope.locations)
   const loc=scope.locations[0].code,term=scope.locations[0].terminals[0].code
   setLocation(loc);setTerminal(term);setAuth(true);setRole(session.role||'')
   await refreshShift(loc,term)
  }catch(e){setMessage((e as Error).message)}
 }
 useEffect(()=>{
  void initialize()
  const onFocus=()=>{void initialize()}
  window.addEventListener('focus',onFocus)
  return ()=>window.removeEventListener('focus',onFocus)
 },[])
 async function signIn(){
  try{
   await api('pos/session/')
   await api('pos/login/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})})
   const scope=await api('pos/scope/')
   if(!scope.locations.length)throw Error('No active terminal is assigned to this operator.')
   setLocations(scope.locations)
   const loc=scope.locations[0].code,term=scope.locations[0].terminals[0].code
   setLocation(loc);setTerminal(term);setAuth(true);setRole((await api('pos/session/')).role||'');setPassword('')
   await refreshShift(loc,term)
   setMessage('Signed in using secure session cookies.')
  }catch(e){setMessage((e as Error).message)}
 }
 async function signOut(){
  if(attempt.current){setMessage('Resolve the pending checkout before signing out.');return}
  try{await api('pos/logout/',{method:'POST'})}catch(e){setMessage((e as Error).message);return}
  setAuth(false);setRole('');setCart([]);setReceipt(null);setShift(null);setSale(null)
 }
 function parseCash(value:string){
  if(!/^\d+(\.\d{1,2})?$/.test(value))throw Error('Enter a valid cash amount, e.g. 5000.00')
  const [naira,kobo='']=value.split('.')
  const amount=Number(naira)*100+Number(kobo.padEnd(2,'0'))
  if(!Number.isSafeInteger(amount))throw Error('Cash amount exceeds supported range')
  return amount
 }
 async function openShift(){
  try{
   const data=await api('pos/shifts/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location_code:location,terminal_code:terminal,opening_cash_minor:parseCash(openingCash)})})
   setShift(data.shift);setMessage('Shift opened.')
  }catch(e){setMessage((e as Error).message)}
 }
 async function closeShift(){
  if(!shift||cart.length||attempt.current)return
  try{
   const data=await api(`pos/shifts/${shift.id}/close/`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({closing_cash_minor:parseCash(closingCash)})})
   setShift(null);setMessage('Shift closed. Expected cash: '+money(data.shift.expected_cash_minor)+'; variance: '+money(data.shift.variance_minor))
  }catch(e){setMessage((e as Error).message)}
 }
 async function submitReview(){
  const id=Number(reviewShiftId)
  if(!Number.isSafeInteger(id)||id<=0){setMessage('Enter a valid closed shift ID.');return}
  try{
   const record=await api(`pos/shifts/${id}/review/`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({decision:reviewDecision,notes:reviewNotes})
   })
   setMessage('Shift #'+id+' reviewed: '+record.decision+' (variance '+money(record.variance_minor)+')')
   setReviewNotes('')
  }catch(e){setMessage((e as Error).message)}
 }
 async function search(){
  if(!query.trim()||!location||!terminal)return
  try{
   const data=await api('pos/catalog/?'+new URLSearchParams({q:query,location_code:location,terminal_code:terminal}))
   setProducts(data.products)
  }catch(e){setMessage((e as Error).message)}
 }
 async function scanBarcode(){
  const code=scanCode.trim()
  if(!code||!location||!terminal||!shift||scanning.current||sending.current||attempt.current)return
  scanning.current=true
  setScanBusy(true)
  try{
   const data=await api('pos/catalog/?'+new URLSearchParams({q:code,location_code:location,terminal_code:terminal}))
   const matches=(data.products as Item[]).filter(item=>item.sku.toLocaleLowerCase()===code.toLocaleLowerCase())
   if(matches.length!==1){
    setMessage('Barcode/SKU not found: '+code+'. Use product search or check the label.')
    return
   }
   const item=matches[0]
   if(item.stock<=0){
    setMessage(item.name+' is out of stock.')
    return
   }
   setCart(current=>{
    const existing=current.find(line=>line.item.id===item.id)
    if((existing?.quantity||0)>=item.stock)return current
    return existing
     ?current.map(line=>line.item.id===item.id?{...line,item,quantity:line.quantity+1}:line)
     :[...current,{item,quantity:1}]
   })
   setScanCode('')
   setMessage('Scanned '+item.name+'. Check cart quantity and available stock.')
  }catch(e){setMessage((e as Error).message)}
  finally{scanning.current=false;setScanBusy(false)}
 }
 function updateCart(item:Item,change:number){
  if(sending.current||attempt.current)return
  setCart(current=>{
   const found=current.find(x=>x.item.id===item.id)
   if(!found)return change>0?[...current,{item,quantity:1}]:current
   return current.map(x=>x.item.id===item.id?{...x,quantity:Math.max(0,Math.min(item.stock,x.quantity+change))}:x).filter(x=>x.quantity>0)
  })
 }
 async function checkout(){
  if(sending.current||!cart.length||!shift)return
  const lines=cart.map(x=>({product_id:x.item.id,quantity:x.quantity}))
  const fingerprint=JSON.stringify({lines,location,terminal,total})
  if(!attempt.current)attempt.current={fingerprint,id:crypto.randomUUID()}
  if(attempt.current.fingerprint!==fingerprint){setMessage('An unresolved checkout exists. Restore the original cart before retrying.');return}
  const id=attempt.current.id
  sending.current=true
  setBusy(true)
  setMessage('Submitting cash sale...')
  try{
   const result=await api('pos/shift-sales/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    lines,shift_id:shift.id,location_code:location,terminal_code:terminal,currency:'NGN',amount_minor:total,
    sale_idempotency_key:'sale-'+id,payment_idempotency_key:'payment-'+id,provider_reference:'CASH-'+id
   })})
   attempt.current=null
   setSale(result)
   setCart([])
   setMessage('Sale completed: '+result.reference)
  }catch(e){setMessage((e as Error).message+' — if the request may have reached the server, retry the same sale without changing the cart.')}
  finally{sending.current=false;setBusy(false)}
 }
 async function showReceipt(){
  if(!sale)return
  try{setReceipt(await api(`pos/sales/${sale.sale_id}/receipt/?`+new URLSearchParams({location_code:location,terminal_code:terminal})))}
  catch(e){setMessage((e as Error).message)}
 }
 const button:React.CSSProperties={padding:'10px 14px',margin:4,cursor:'pointer'}
 if(!auth)return <main style={{maxWidth:420,margin:'4rem auto',fontFamily:'system-ui'}}>
  <h1>Tokad Mart · Transactional POS</h1>
  <p>Authorized operator access — cash sales only</p>
  {attempt.current&&<p role="alert">An earlier checkout needs verification. Sign in again and retry the unchanged cart before starting another sale.</p>}
  <input placeholder="Username" value={username} onChange={e=>setUsername(e.target.value)}/>{' '}
  <input placeholder="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)}/>
  <button style={button} onClick={signIn}>Sign in</button><p role="status">{message}</p>
 </main>
 return <main style={{fontFamily:'system-ui',maxWidth:1050,margin:'auto',padding:24}}>
  <header style={{display:'flex',justifyContent:'space-between',gap:20}}>
   <h1>Tokad Mart · Cash POS</h1><button style={button} onClick={signOut}>Sign out</button>
  </header>
  <p>Location: <select value={location} disabled={busy||!!shift||!!cart.length||!!attempt.current} onChange={e=>{setLocation(e.target.value);setTerminal(locations.find(l=>l.code===e.target.value)?.terminals[0]?.code||'');setProducts([]);setShift(null);void refreshShift(e.target.value,locations.find(l=>l.code===e.target.value)?.terminals[0]?.code||'')}}>
   {locations.map(l=><option key={l.code} value={l.code}>{l.name}</option>)}
  </select> Terminal: <select value={terminal} disabled={busy||!!shift||!!cart.length||!!attempt.current} onChange={e=>{setTerminal(e.target.value);setProducts([]);setShift(null);void refreshShift(location,e.target.value)}}>
   {locations.find(l=>l.code===location)?.terminals.map(t=><option key={t.code} value={t.code}>{t.name}</option>)}
  </select></p>
  <section style={{padding:12,border:'1px solid #bbb',marginBottom:16}}>
   <h2>Cashier Shift</h2>
   {shift?<p>Open shift #{shift.id} · Opening cash {money(shift.opening_cash_minor)}
    <input aria-label="Closing cash in naira" value={closingCash} onChange={e=>setClosingCash(e.target.value)} placeholder="Closing cash ₦" />
    <button style={button} disabled={busy||!!cart.length||!!attempt.current} onClick={closeShift}>Close shift</button></p>
   :<p>No open shift.
    <input aria-label="Opening cash in naira" value={openingCash} onChange={e=>setOpeningCash(e.target.value)} placeholder="Opening cash ₦" />
    <button style={button} disabled={busy} onClick={openShift}>Open shift</button></p>}
  </section>
  {role==='SUPERVISOR'&&<section style={{border:'1px solid #aaa',padding:12,marginBottom:16}}>
   <h2>Supervisor reconciliation review</h2>
   <p>Review a closed shift assigned to another cashier. Approval does not change the counted cash.</p>
   <input aria-label="Closed shift ID" placeholder="Closed shift ID" value={reviewShiftId} onChange={e=>setReviewShiftId(e.target.value)}/>
   <select aria-label="Review decision" value={reviewDecision} onChange={e=>setReviewDecision(e.target.value)}><option value="APPROVED">Approve</option><option value="REJECTED">Reject</option></select>
   <input aria-label="Review notes" placeholder="Required review notes" value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)}/>
   <button style={button} disabled={!reviewNotes.trim()} onClick={submitReview}>Submit review</button>
  </section>}
  <section style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:24}}>
   <div>
    <h2>Products</h2>
    <input placeholder="Search name or SKU" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void search()}}/>
    <button style={button} onClick={search}>Search</button>
    <div style={{margin:'12px 0',padding:12,border:'1px solid #ccc'}}>
     <label htmlFor="pos-barcode">Barcode / SKU scanner</label>
     <p style={{fontSize:12}}>Focus this box and scan a product. USB keyboard-wedge scanners usually send Enter after the code. Exact SKU matches add one unit.</p>
     <input id="pos-barcode" autoComplete="off" placeholder="Scan barcode or type SKU" value={scanCode}
      disabled={!shift||busy||scanBusy||!!attempt.current}
      onChange={e=>setScanCode(e.target.value)}
      onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();void scanBarcode()}}}/>
     <button style={button} disabled={!shift||busy||scanBusy||!scanCode.trim()||!!attempt.current} onClick={scanBarcode}>Add scanned item</button>
    </div>
    {products.map(item=><p key={item.id}>{item.name} · {item.sku} · {money(item.unit_price_minor)} · Stock {item.stock} <button style={button} disabled={!shift||item.stock<1||busy||!!attempt.current} onClick={()=>updateCart(item,1)}>Add</button></p>)}
   </div>
   <div>
    <h2>Cart</h2>
    {cart.map(({item,quantity})=><p key={item.id}>{item.name} × {quantity} · {money(item.unit_price_minor*quantity)}
     <button style={button} disabled={busy||!!attempt.current} onClick={()=>updateCart(item,-1)}>−</button>
     <button style={button} disabled={busy||!!attempt.current||quantity>=item.stock} onClick={()=>updateCart(item,1)}>+</button>
    </p>)}
    <h2>Total: {money(total)}</h2>
    <button style={button} disabled={busy||!shift||!cart.length} onClick={checkout}>{busy?'Processing…':'Complete cash sale'}</button>
    {sale&&<button style={button} onClick={showReceipt}>View last receipt</button>}
   </div>
  </section>
  {receipt&&<article id="tokad-print-receipt" style={{border:'1px solid #999',padding:20,maxWidth:380}}>
    <h2>TOKAD MART</h2><p>Receipt {receipt.reference}</p><p>{new Date(receipt.created_at).toLocaleString()}</p>
    {receipt.lines.map((l,i)=><p key={i}>{l.name} × {l.quantity} — {money(l.line_total_minor)}</p>)}
    <strong>Total {money(receipt.total_minor)}</strong>
    <p className="tokad-no-print"><button style={button} onClick={()=>window.print()}>Print receipt</button></p>
   </article>}
  <style>{`
   @media print {
    @page { margin: 3mm; }
    body * { visibility: hidden !important; }
    #tokad-print-receipt, #tokad-print-receipt * { visibility: visible !important; }
    #tokad-print-receipt { position: absolute; top: 0; left: 0; width: 72mm; max-width: 72mm !important; padding: 0 !important; border: 0 !important; color: #000; background: #fff; font-size: 11px; }
    #tokad-print-receipt h2 { text-align:center; font-size: 16px; }
    #tokad-print-receipt .tokad-no-print, #tokad-print-receipt .tokad-no-print * { display: none !important; }
   }
  `}</style>
  <p role="status">{message}</p>
  <p style={{fontSize:12}}>Cash-only session POS with cashier shifts. Card, transfers, refunds and wholesale pricing require separate migration.</p>
 </main>
}
