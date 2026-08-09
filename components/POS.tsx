'use client'

import { useEffect, useMemo, useState } from 'react'

type Product = { id:number; name:string; sku:string; barcode?:string|null; retail_price:string; wholesale_price:string; unit:string }
type CartLine = Product & { quantity:number }
type Shift = { id:number; location:number; opening_cash:string; open:boolean }
type Sale = { id:number; number:string; total:string }

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

export default function POS() {
  const [username,setUsername] = useState('')
  const [password,setPassword] = useState('')
  const [token,setToken] = useState('')
  const [query,setQuery] = useState('')
  const [products,setProducts] = useState<Product[]>([])
  const [cart,setCart] = useState<CartLine[]>([])
  const [locationId,setLocationId] = useState('1')
  const [shift,setShift] = useState<Shift|null>(null)
  const [openingCash,setOpeningCash] = useState('0')
  const [customerWholesale,setCustomerWholesale] = useState(false)
  const [payment,setPayment] = useState('CASH')
  const [message,setMessage] = useState('')
  const [lastSale,setLastSale] = useState<Sale|null>(null)

  useEffect(() => { const saved = window.localStorage.getItem('tokad_token'); if(saved) setToken(saved) }, [])

  useEffect(() => {
    if(!token || !query.trim()) { setProducts([]); return }
    const c = new AbortController()
    fetch(`${API}/products/?q=${encodeURIComponent(query)}`, { signal:c.signal, headers:{Authorization:`Token ${token}`} })
      .then(r=>r.ok?r.json():[]).then(setProducts).catch(()=>{})
    return () => c.abort()
  }, [query, token])

  useEffect(() => {
    if(!token) return
    fetch(`${API}/shifts/`, {headers:{Authorization:`Token ${token}`}}).then(r=>r.ok?r.json():[]).then((xs:Shift[])=>setShift(xs.find(x=>x.open)||null)).catch(()=>{})
  }, [token])

  const total = useMemo(() => cart.reduce((s,p)=>s+Number(customerWholesale?p.wholesale_price:p.retail_price)*p.quantity,0),[cart,customerWholesale])

  function login() {
    setMessage('Signing in…')
    fetch(`${API}/auth/token/`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})})
      .then(async r=>{const d=await r.json(); if(!r.ok) throw new Error(d.non_field_errors?.[0]||'Invalid credentials'); return d})
      .then(d=>{window.localStorage.setItem('tokad_token',d.token);setToken(d.token);setPassword('');setMessage('Signed in.')})
      .catch(e=>setMessage(e.message))
  }

  function logout() { window.localStorage.removeItem('tokad_token'); setToken(''); setShift(null); setCart([]); }

  async function openShift() {
    const r=await fetch(`${API}/shifts/`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Token ${token}`},body:JSON.stringify({location_id:Number(locationId),opening_cash:openingCash})})
    const d=await r.json(); if(!r.ok) return setMessage(d.detail||JSON.stringify(d)); setShift(d); setMessage(`Shift #${d.id} opened.`)
  }

  function add(p:Product) { setCart(c=>{const x=c.find(i=>i.id===p.id);return x?c.map(i=>i.id===p.id?{...i,quantity:i.quantity+1}:i):[...c,{...p,quantity:1}]}) }
  function changeQty(id:number,delta:number) { setCart(c=>c.map(i=>i.id===id?{...i,quantity:i.quantity+delta}:i).filter(i=>i.quantity>0)) }

  async function checkout() {
    if(!shift || !cart.length) return
    setMessage('Processing…')
    const key=crypto.randomUUID()
    const r=await fetch(`${API}/sales/checkout/`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Token ${token}`,'Idempotency-Key':key},body:JSON.stringify({shift_id:shift.id,location_id:shift.location,items:cart.map(i=>({product_id:i.id,quantity:i.quantity})),payments:[{method:payment,amount:total.toFixed(2)}]})})
    const d=await r.json()
    if(!r.ok) return setMessage(d.detail||JSON.stringify(d))
    setLastSale(d); setCart([]); setMessage(`Sale ${d.number} completed.`)
  }

  async function printReceipt() {
    if(!lastSale) return
    const r=await fetch(`${API}/sales/${lastSale.id}/receipt/`,{headers:{Authorization:`Token ${token}`}})
    const d=await r.json();
    const rows=d.items.map((i:{name:string;quantity:string;unit_price:string;line_total:string})=>`<tr><td>${i.name}</td><td>${i.quantity}</td><td>₦${i.line_total}</td></tr>`).join('')
    const payments=d.payments.map((p:{method:string;amount:string})=>`<div>${p.method}: ₦${p.amount}</div>`).join('')
    const w=window.open('', '_blank', 'width=420,height=700')
    if(!w) return setMessage('Allow pop-ups to print receipts.')
    w.document.write(`<html><head><title>${d.sale_number}</title><style>body{font-family:monospace;width:300px;margin:auto}table{width:100%;font-size:12px}h1{text-align:center;font-size:18px}.total{font-weight:bold;font-size:16px}</style></head><body><h1>TOKAD MART</h1><div>Receipt: ${d.sale_number}</div><div>${new Date(d.created_at).toLocaleString()}</div><hr/><table>${rows}</table><hr/><div>Subtotal: ₦${d.subtotal}</div><div>Discount: ₦${d.discount}</div><div>Tax: ₦${d.tax}</div><div class='total'>TOTAL: ₦${d.total}</div><hr/>${payments}<p>Thank you.</p></body></html>`)
    w.document.close(); w.focus(); w.print()
  }

  if(!token) return <main style={{maxWidth:420,margin:'80px auto',padding:24,fontFamily:'system-ui'}}><h1>Tokad Mart POS</h1><p>Cashier sign in</p><input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Username" style={{width:'100%',padding:12,marginBottom:8}}/><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password" style={{width:'100%',padding:12,marginBottom:8}}/><button onClick={login} style={{width:'100%',padding:14}}>Sign in</button><p>{message}</p></main>

  if(!shift) return <main style={{maxWidth:520,margin:'80px auto',padding:24,fontFamily:'system-ui'}}><h1>Tokad Mart POS</h1><p>No open cashier shift.</p><label>Location ID <input value={locationId} onChange={e=>setLocationId(e.target.value)} /></label><br/><label>Opening cash <input value={openingCash} onChange={e=>setOpeningCash(e.target.value)} /></label><button onClick={openShift} style={{display:'block',padding:14,marginTop:16}}>Open shift</button><button onClick={logout} style={{marginTop:12}}>Sign out</button><p>{message}</p></main>

  return <main style={{fontFamily:'system-ui',padding:24,maxWidth:1200,margin:'auto'}}><header style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><h1>Tokad Mart POS</h1><p>Shift #{shift.id} · Location #{shift.location}</p></div><button onClick={logout}>Sign out</button></header><div style={{display:'grid',gridTemplateColumns:'1.4fr 1fr',gap:24}}><section><input autoFocus value={query} onChange={e=>setQuery(e.target.value)} placeholder="Scan barcode or search product…" style={{width:'100%',padding:14,fontSize:18}}/>{products.map(p=><button key={p.id} onClick={()=>add(p)} style={{display:'block',width:'100%',padding:14,textAlign:'left',marginTop:8}}>{p.name} · {p.sku} · ₦{customerWholesale?p.wholesale_price:p.retail_price}</button>)}<label style={{display:'block',marginTop:16}}>Wholesale pricing <input type="checkbox" checked={customerWholesale} onChange={e=>setCustomerWholesale(e.target.checked)}/></label></section><aside><h2>Cart</h2>{cart.map(i=><div key={i.id} style={{display:'flex',justifyContent:'space-between',padding:8}}><span>{i.name} × {i.quantity} <button onClick={()=>changeQty(i.id,-1)}>-</button> <button onClick={()=>changeQty(i.id,1)}>+</button></span><span>₦{(Number(customerWholesale?i.wholesale_price:i.retail_price)*i.quantity).toFixed(2)}</span></div>)}<h2>₦{total.toFixed(2)}</h2><select value={payment} onChange={e=>setPayment(e.target.value)}><option>CASH</option><option>POS</option><option>TRANSFER</option></select><button disabled={!cart.length} onClick={checkout} style={{display:'block',width:'100%',padding:16,marginTop:12}}>Complete sale</button>{lastSale&&<button onClick={printReceipt} style={{display:'block',width:'100%',padding:12,marginTop:8}}>Print receipt</button>}<p>{message}</p></aside></div></main>
}
