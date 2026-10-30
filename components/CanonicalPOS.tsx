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
 const [newSku,setNewSku]=useState('')
 const [newName,setNewName]=useState('')
 const [newPrice,setNewPrice]=useState('')
 const [mappingSku,setMappingSku]=useState('')
 const [mappingCode,setMappingCode]=useState('')
 const [catalogBusy,setCatalogBusy]=useState(false)
 type ProcurementLine={id:number;sku:string;name:string;quantity_ordered:number;quantity_received:number;quantity_outstanding:number;unit_cost_minor:number}
 type ProcurementOrder={id:number;reference:string;supplier_code:string;supplier_name:string;status:string;approval:string;total_cost_minor:number;lines:ProcurementLine[]}
 const [suppliers,setSuppliers]=useState<{code:string;name:string}[]>([])
 const [supplierCode,setSupplierCode]=useState('')
 const [supplierName,setSupplierName]=useState('')
 const [supplierContact,setSupplierContact]=useState('')
 const [poSupplier,setPoSupplier]=useState('')
 const [poReference,setPoReference]=useState('')
 const [approvalNote,setApprovalNote]=useState('')
 const [invoiceReceiptId,setInvoiceReceiptId]=useState('')
 const [invoiceNumber,setInvoiceNumber]=useState('')
 const [invoiceAmount,setInvoiceAmount]=useState('')
 const [invoiceNotes,setInvoiceNotes]=useState('')
 const [supplierPaymentInvoice,setSupplierPaymentInvoice]=useState('')
 const [supplierPaymentReference,setSupplierPaymentReference]=useState('')
 const [supplierPaymentAmount,setSupplierPaymentAmount]=useState('')
 const [supplierPaymentNotes,setSupplierPaymentNotes]=useState('')
 const [supplierVerificationNotes,setSupplierVerificationNotes]=useState('')
 const [supplierPayments,setSupplierPayments]=useState<{id:number;invoice_id:number;reference:string;amount_minor:number;status:string}[]>([])
 const [supplierReconciliation,setSupplierReconciliation]=useState<{invoice_id:number;invoice_number:string;verified_evidence_minor:number;pending_review_minor:number;remaining_unverified_minor:number;review_status:string}[]>([])
 const paymentAttempt=useRef<{fingerprint:string;key:string}|null>(null)
 const [payables,setPayables]=useState<{id:number;number:string;supplier_code:string;amount_minor:number;expected_minor:number;status:string}[]>([])
 const [printOrder,setPrintOrder]=useState<ProcurementOrder|null>(null)
 const [poLines,setPoLines]=useState('')
 const [orders,setOrders]=useState<ProcurementOrder[]>([])
 const [receiptOrderId,setReceiptOrderId]=useState('')
 const [receiptLineId,setReceiptLineId]=useState('')
 const [receiptQuantity,setReceiptQuantity]=useState('')
 const [receiptReference,setReceiptReference]=useState('')
 const [procurementBusy,setProcurementBusy]=useState(false)
 const receiptAttempt=useRef<{fingerprint:string;key:string}|null>(null)
 const [replenishment,setReplenishment]=useState<{sku:string;current_stock:number;outstanding_order_units:number;reorder_gap_units:number}[]>([])
 const [financeStart,setFinanceStart]=useState(new Date().toISOString().slice(0,10))
 const [financeEnd,setFinanceEnd]=useState(new Date().toISOString().slice(0,10))
 const [financeReport,setFinanceReport]=useState<{
   sales:{completed_sale_count:number;gross_minor:number;daily:{date:string;gross_minor:number}[]};
   cashier_shifts:{shift_id:number;terminal:string;variance_minor:number|null;review_status:string}[];
   expenses:{approved_minor:number;pending_review_minor:number};
   supplier_invoice_exposure:{invoice_id:number;invoice_number:string;status:string;amount_minor:number;verified_evidence_minor:number;pending_review_minor:number}[];
   disclaimer:string
 }|null>(null)
 const [expenseReference,setExpenseReference]=useState('')
 const [expenseCategory,setExpenseCategory]=useState('')
 const [expenseDescription,setExpenseDescription]=useState('')
 const [expenseAmount,setExpenseAmount]=useState('')
 const [expenseDate,setExpenseDate]=useState(new Date().toISOString().slice(0,10))
 const [expenseReviewNotes,setExpenseReviewNotes]=useState('')
 const [expenseRows,setExpenseRows]=useState<{id:number;reference:string;category:string;amount_minor:number;review_status:string}[]>([])
 const [financeBusy,setFinanceBusy]=useState(false)
 const [stockSku,setStockSku]=useState('')
 const [stockOperation,setStockOperation]=useState('RECEIVE')
 const [stockQuantity,setStockQuantity]=useState('')
 const [stockReference,setStockReference]=useState('')
 const [stockNotes,setStockNotes]=useState('')
 const [stockBusy,setStockBusy]=useState(false)
 const [reportThreshold,setReportThreshold]=useState('5')
 const [reportRows,setReportRows]=useState<{id:number;sku:string;name:string;unit_price_minor:number;current_stock:number;low_stock:boolean}[]>([])
 const [reportMode,setReportMode]=useState('low')
 const [stockCountSku,setStockCountSku]=useState('')
 const [stockCountExpected,setStockCountExpected]=useState<number|null>(null)
 const [stockCountActual,setStockCountActual]=useState('')
 const [stockCountReference,setStockCountReference]=useState('')
 const [stockCountNotes,setStockCountNotes]=useState('')
 const [countPending,setCountPending]=useState(false)
 const countAttempt=useRef<{fingerprint:string;key:string}|null>(null)
 const stockAttempt=useRef<{fingerprint:string;key:string}|null>(null)
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
 async function createCatalogProduct(){
  if(catalogBusy)return
  setCatalogBusy(true)
  try{
   const amount=parseCash(newPrice)
   if(amount<=0)throw Error('Product price must be greater than zero.')
   const result=await api('pos/manage/products/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
     location_code:location,terminal_code:terminal,
     sku:newSku.trim(),name:newName.trim(),unit_price_minor:amount,currency:'NGN'
    })
   })
   setMappingSku(result.product.sku)
   setNewSku('');setNewName('');setNewPrice('')
   setMessage('Product registered: '+result.product.sku+'. Assign a barcode or register stock through the inventory workflow.')
  }catch(e){setMessage((e as Error).message)}
  finally{setCatalogBusy(false)}
 }
 async function assignCatalogBarcode(){
  if(catalogBusy)return
  setCatalogBusy(true)
  try{
   const data=await api('pos/manage/products/?'+new URLSearchParams({sku:mappingSku,location_code:location,terminal_code:terminal}))
   const product=data.product as Item
   await api(`pos/manage/products/${product.id}/barcodes/`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,code:mappingCode})
   })
   setMessage('Barcode '+mappingCode+' assigned to '+mappingSku+'.')
   setMappingCode('')
  }catch(e){setMessage((e as Error).message)}
  finally{setCatalogBusy(false)}
 }
 async function submitStockOperation(){
  if(stockBusy)return
  const delta=Number(stockQuantity)
  if(!Number.isSafeInteger(delta)||delta===0||Math.abs(delta)>1000000){setMessage('Quantity must be a nonzero whole number up to 1,000,000.');return}
  if(stockOperation==='RECEIVE'&&delta<0){setMessage('Receiving quantity must be positive.');return}
  const payload={
   location_code:location,terminal_code:terminal,
   sku:stockSku.trim(),operation:stockOperation,quantity:delta,
   reference:stockReference.trim(),notes:stockNotes.trim()
  }
  const fingerprint=JSON.stringify(payload)
  if(stockAttempt.current&&stockAttempt.current.fingerprint!==fingerprint){
   setMessage('An inventory request is unresolved. Restore its original fields and retry to avoid double counting.')
   return
  }
  if(!stockAttempt.current)stockAttempt.current={fingerprint,key:crypto.randomUUID()}
  setStockBusy(true)
  try{
   const result=await api('pos/manage/stock/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...payload,idempotency_key:stockAttempt.current.key})
   })
   stockAttempt.current=null
   setStockQuantity('');setStockReference('');setStockNotes('')
   setMessage('Stock '+(result.replayed?'confirmed':'recorded')+
    ': '+payload.sku+' now has '+result.quantity_after+' units at '+location+'.')
  }catch(e){setMessage((e as Error).message+' — retry unchanged fields if the update may have reached the server.')}
  finally{setStockBusy(false)}
 }
 async function loadInventoryReport(){
  try{
   const data=await api('pos/manage/inventory-report/?'+new URLSearchParams({
    location_code:location,terminal_code:terminal,
    threshold:reportThreshold,mode:reportMode
   }))
   setReportRows(data.products)
   setMessage('Inventory report refreshed for '+location+'. Showing up to 200 products.')
  }catch(e){setMessage((e as Error).message)}
 }
 async function reconcileCount(){
  if(countPending||stockCountExpected===null)return
  const count=Number(stockCountActual)
  if(!/^\d+$/.test(stockCountActual)||!Number.isSafeInteger(count)){setMessage('Enter a nonnegative whole-number physical count.');return}
  const delta=count-stockCountExpected
  if(delta===0){setMessage('Physical stock matches recorded stock. No adjustment needed.');return}
  if(Math.abs(delta)>1000000){setMessage('Count variance exceeds the adjustment limit.');return}
  const payload={
   location_code:location,terminal_code:terminal,sku:stockCountSku,
   operation:'ADJUST',quantity:delta,expected_quantity:stockCountExpected,
   reference:stockCountReference.trim(),notes:stockCountNotes.trim()
  }
  const fingerprint=JSON.stringify(payload)
  if(countAttempt.current&&countAttempt.current.fingerprint!==fingerprint){
   setMessage('Unresolved stock count request. Restore the same fields before retrying.')
   return
  }
  if(!countAttempt.current)countAttempt.current={fingerprint,key:crypto.randomUUID()}
  setCountPending(true)
  try{
   const result=await api('pos/manage/stock/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...payload,idempotency_key:countAttempt.current.key})
   })
   countAttempt.current=null
   setMessage('Stocktake recorded: '+stockCountSku+' now has '+result.quantity_after+' units.')
   setStockCountSku('');setStockCountExpected(null);setStockCountActual('')
   setStockCountReference('');setStockCountNotes('')
   await loadInventoryReport()
  }catch(e){setMessage((e as Error).message+' — if uncertain, retry unchanged or verify ledger before repeating.')}
  finally{setCountPending(false)}
 }
 async function refreshProcurement(){
  try{
   const params=new URLSearchParams({location_code:location,terminal_code:terminal})
   const [supply,po,report]=await Promise.all([
    api('pos/manage/suppliers/?'+params),
    api('pos/manage/purchase-orders/?'+params),
    api('pos/manage/replenishment/?'+new URLSearchParams({location_code:location,terminal_code:terminal,threshold:reportThreshold}))
   ])
   setSuppliers(supply.suppliers)
   setOrders(po.orders)
   setReplenishment(report.products)
   const ap=await api('pos/manage/accounts-payable/?'+params)
   setPayables(ap.rows)
   const [paymentList,reconciliation]=await Promise.all([
    api('pos/manage/supplier-payments/?'+params),
    api('pos/manage/supplier-reconciliation/?'+params)
   ])
   setSupplierPayments(paymentList.payments)
   setSupplierReconciliation(reconciliation.rows)
  }catch(e){setMessage((e as Error).message)}
 }
 async function approveOrder(id:number){
  if(procurementBusy)return
  setProcurementBusy(true)
  try{
   await api(`pos/manage/purchase-orders/${id}/approve/`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,note:approvalNote.trim()})
   })
   setApprovalNote('')
   setMessage('Purchase order approved. Goods can now be received.')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message)}
  finally{setProcurementBusy(false)}
 }
 async function recordSupplierInvoice(){
  if(procurementBusy)return
  let amount:number
  try{amount=parseCash(invoiceAmount)}catch(e){setMessage((e as Error).message);return}
  const receiptId=Number(invoiceReceiptId)
  if(!Number.isSafeInteger(receiptId)||receiptId<=0||amount<=0){setMessage('Enter valid receipt ID and invoice amount.');return}
  setProcurementBusy(true)
  try{
   const result=await api('pos/manage/supplier-invoices/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
     location_code:location,terminal_code:terminal,receipt_id:receiptId,
     number:invoiceNumber.trim(),amount_minor:amount,notes:invoiceNotes.trim()
    })
   })
   setMessage('Supplier invoice '+result.status+'. Expected goods value: '+money(result.expected_minor)+'.')
   setInvoiceReceiptId('');setInvoiceNumber('');setInvoiceAmount('');setInvoiceNotes('')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message)}
  finally{setProcurementBusy(false)}
 }
 async function recordPaymentEvidence(){
  if(procurementBusy)return
  const invoiceId=Number(supplierPaymentInvoice)
  let amount:number
  try{amount=parseCash(supplierPaymentAmount)}catch(e){setMessage((e as Error).message);return}
  if(!Number.isSafeInteger(invoiceId)||invoiceId<1||amount<1){setMessage('Enter invoice ID and positive payment amount.');return}
  const payload={
   location_code:location,terminal_code:terminal,invoice_id:invoiceId,
   reference:supplierPaymentReference.trim(),amount_minor:amount,
   notes:supplierPaymentNotes.trim()
  }
  const fingerprint=JSON.stringify(payload)
  if(paymentAttempt.current&&paymentAttempt.current.fingerprint!==fingerprint){
   setMessage('Resolve the existing payment evidence request before changing the details.')
   return
  }
  if(!paymentAttempt.current)paymentAttempt.current={fingerprint,key:crypto.randomUUID()}
  setProcurementBusy(true)
  try{
   const response=await api('pos/manage/supplier-payments/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...payload,idempotency_key:paymentAttempt.current.key})
   })
   paymentAttempt.current=null
   setMessage('Payment evidence #'+response.payment.id+' recorded. Another supervisor must verify it.')
   setSupplierPaymentInvoice('');setSupplierPaymentReference('')
   setSupplierPaymentAmount('');setSupplierPaymentNotes('')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message+' — retry unchanged values if the request may have completed.')}
  finally{setProcurementBusy(false)}
 }
 async function verifyPaymentEvidence(id:number){
  if(procurementBusy)return
  setProcurementBusy(true)
  try{
   await api(`pos/manage/supplier-payments/${id}/verify/`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,notes:supplierVerificationNotes.trim()})
   })
   setSupplierVerificationNotes('')
   setMessage('Payment evidence independently reviewed and marked manually verified.')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message)}
  finally{setProcurementBusy(false)}
 }
 async function registerSupplier(){
  if(procurementBusy)return
  setProcurementBusy(true)
  try{
   const result=await api('pos/manage/suppliers/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,code:supplierCode.trim(),name:supplierName.trim(),contact:supplierContact.trim()})
   })
   setMessage('Supplier registered: '+result.supplier.code)
   setSupplierCode('');setSupplierName('');setSupplierContact('')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message)}
  finally{setProcurementBusy(false)}
 }
 async function createPurchaseOrder(){
  if(procurementBusy)return
  let lines:{sku:string;quantity:number;unit_cost_minor:number}[]
  try{
   lines=poLines.split('\n').filter(l=>l.trim()).map(line=>{
    const parts=line.split(',').map(x=>x.trim())
    if(parts.length!==3||!/^\d+$/.test(parts[1]))throw Error('Use one line per SKU: SKU, quantity, unit cost in naira')
    const quantity=Number(parts[1])
    if(!Number.isSafeInteger(quantity)||quantity<=0)throw Error('Ordered quantity must be positive.')
    return {sku:parts[0],quantity,unit_cost_minor:parseCash(parts[2])}
   })
   if(!lines.length||lines.some(l=>l.unit_cost_minor<=0))throw Error('Enter at least one line with positive unit cost.')
  }catch(e){setMessage((e as Error).message);return}
  setProcurementBusy(true)
  try{
   const result=await api('pos/manage/purchase-orders/',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,supplier_code:poSupplier,reference:poReference.trim(),lines})
   })
   setMessage('Purchase order created: '+result.order.reference)
   setPoReference('');setPoLines('')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message)}
  finally{setProcurementBusy(false)}
 }
 async function receivePurchaseOrder(){
  if(procurementBusy)return
  const quantity=Number(receiptQuantity),orderId=Number(receiptOrderId),lineId=Number(receiptLineId)
  if(!Number.isSafeInteger(quantity)||quantity<=0||!Number.isSafeInteger(lineId)||lineId<=0||!receiptReference.trim()){setMessage('Select an order line, enter positive quantity and delivery note reference.');return}
  const payload={location_code:location,terminal_code:terminal,reference:receiptReference.trim(),lines:[{line_id:lineId,quantity}]}
  const fingerprint=JSON.stringify({orderId,...payload})
  if(receiptAttempt.current&&receiptAttempt.current.fingerprint!==fingerprint){
   setMessage('Unresolved goods receipt. Restore original order, line, quantity and reference before retrying.')
   return
  }
  if(!receiptAttempt.current)receiptAttempt.current={fingerprint,key:crypto.randomUUID()}
  setProcurementBusy(true)
  try{
   const result=await api(`pos/manage/purchase-orders/${orderId}/receive/`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...payload,idempotency_key:receiptAttempt.current.key})
   })
   receiptAttempt.current=null
   setMessage('Goods receipt #'+result.receipt_id+' '+(result.replayed?'confirmed':'recorded')+'; PO '+result.order.reference+' is '+result.order.status+'. Enter receipt ID '+result.receipt_id+' when matching the supplier invoice.')
   setReceiptQuantity('');setReceiptReference('')
   await refreshProcurement()
  }catch(e){setMessage((e as Error).message+' — if delivery was submitted, retry unchanged or verify the order before repeating.')}
  finally{setProcurementBusy(false)}
 }
 async function loadFinance(){
  if(financeBusy)return
  setFinanceBusy(true)
  try{
   const scoped=new URLSearchParams({location_code:location,terminal_code:terminal})
   const [dashboard,expenseReport]=await Promise.all([
    api('pos/manage/financial-dashboard/?'+new URLSearchParams({
     location_code:location,terminal_code:terminal,start:financeStart,end:financeEnd
    })),
    api('pos/manage/expenses/?'+scoped)
   ])
   setFinanceReport(dashboard);setExpenseRows(expenseReport.expenses)
   setMessage('Financial controls refreshed for '+location+'.')
  }catch(e){setMessage((e as Error).message)}
  finally{setFinanceBusy(false)}
 }
 async function recordExpense(){
  if(financeBusy)return
  let amount:number
  try{amount=parseCash(expenseAmount)}catch(e){setMessage((e as Error).message);return}
  setFinanceBusy(true)
  try{
   await api('pos/manage/expenses/',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,
     reference:expenseReference.trim(),category:expenseCategory.trim(),
     description:expenseDescription.trim(),incurred_on:expenseDate,amount_minor:amount})
   })
   setExpenseReference('');setExpenseCategory('');setExpenseDescription('');setExpenseAmount('')
   setMessage('Expense recorded for independent review. No payment was executed.')
  }catch(e){setMessage((e as Error).message)}
  finally{setFinanceBusy(false)}
 }
 async function reviewExpense(expenseId:number,decision:string){
  if(financeBusy)return
  setFinanceBusy(true)
  try{
   await api(`pos/manage/expenses/${expenseId}/review/`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({location_code:location,terminal_code:terminal,
     decision,notes:expenseReviewNotes.trim()})
   })
   setExpenseReviewNotes('')
   setMessage('Expense '+decision.toLowerCase()+'. Refresh the dashboard to see totals.')
  }catch(e){setMessage((e as Error).message)}
  finally{setFinanceBusy(false)}
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
   const data=await api('pos/barcode/?'+new URLSearchParams({code,location_code:location,terminal_code:terminal}))
   const item=data.product as Item
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
   setReceipt(null)
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
  {role==='SUPERVISOR'&&<section style={{padding:12,border:'1px solid #aaa',marginBottom:16}}>
   <h2>Supervisor product and barcode management</h2>
   <p>New products start without stock. Set available quantities through authorized inventory receiving, not the cashier cart.</p>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <input aria-label="New product SKU" placeholder="Unique SKU" value={newSku} onChange={e=>setNewSku(e.target.value)}/>
    <input aria-label="New product name" placeholder="Product name" value={newName} onChange={e=>setNewName(e.target.value)}/>
    <input aria-label="Product price in naira" placeholder="Price in ₦" value={newPrice} onChange={e=>setNewPrice(e.target.value)}/>
    <button style={button} disabled={catalogBusy||!newSku.trim()||!newName.trim()||!newPrice.trim()} onClick={createCatalogProduct}>Register product</button>
   </div>
   <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:12}}>
    <input aria-label="Product SKU to map" placeholder="Existing exact SKU" value={mappingSku} onChange={e=>setMappingSku(e.target.value)}/>
    <input aria-label="Manufacturer barcode" placeholder="Barcode (retain leading zeros)" value={mappingCode} onChange={e=>setMappingCode(e.target.value)}/>
    <button style={button} disabled={catalogBusy||!mappingSku.trim()||!mappingCode.trim()} onClick={assignCatalogBarcode}>Assign barcode</button>
   </div>
  </section>}
  {role==='SUPERVISOR'&&<section style={{padding:12,border:'1px solid #aaa',marginBottom:16}}>
   <h2>Supervisor stock receiving and adjustment</h2>
   <p>Each operation creates an auditable inventory movement. Receive stock with positive quantities; adjustments can add or remove stock.</p>
   {stockAttempt.current&&<p role="alert">An inventory update may be pending. Do not modify these fields until the original request is confirmed.</p>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <input aria-label="Stock product SKU" placeholder="Exact product SKU" value={stockSku} disabled={stockBusy} onChange={e=>setStockSku(e.target.value)}/>
    <select aria-label="Stock operation" value={stockOperation} disabled={stockBusy} onChange={e=>setStockOperation(e.target.value)}>
     <option value="RECEIVE">Receive goods</option><option value="ADJUST">Adjust stock</option>
    </select>
    <input aria-label="Stock quantity change" placeholder="Quantity (e.g. 20 or -2)" value={stockQuantity} disabled={stockBusy} onChange={e=>setStockQuantity(e.target.value)}/>
    <input aria-label="Stock reference" placeholder="Supplier invoice or adjustment reference" value={stockReference} disabled={stockBusy} onChange={e=>setStockReference(e.target.value)}/>
    <input aria-label="Stock operation reason" placeholder="Required explanation" value={stockNotes} disabled={stockBusy} onChange={e=>setStockNotes(e.target.value)}/>
    <button style={button} disabled={stockBusy||!stockSku.trim()||!stockQuantity.trim()||!stockReference.trim()||!stockNotes.trim()} onClick={submitStockOperation}>Record stock movement</button>
   </div>
  </section>}
  {role==='SUPERVISOR'&&<section style={{padding:12,border:'1px solid #aaa',marginBottom:16}}>
   <h2>Inventory report, low-stock alerts and physical stocktake</h2>
   <label>Low-stock threshold <input aria-label="Low stock threshold" value={reportThreshold} onChange={e=>setReportThreshold(e.target.value)}/></label>
   <select aria-label="Inventory report mode" value={reportMode} onChange={e=>setReportMode(e.target.value)}>
    <option value="low">Low stock only</option><option value="all">All active products</option>
   </select>
   <button style={button} onClick={loadInventoryReport}>Refresh inventory report</button>
   <p>Alerts are evaluated when you refresh; they are not background notifications. The report displays at most 200 SKUs.</p>
   <div style={{maxHeight:250,overflowY:'auto'}}>
    <table style={{width:'100%',textAlign:'left'}}>
     <thead><tr><th>SKU</th><th>Product</th><th>Units</th><th>Status</th><th>Count</th></tr></thead>
     <tbody>{reportRows.map(item=><tr key={item.id}>
      <td>{item.sku}</td><td>{item.name}</td><td>{item.current_stock}</td>
      <td>{item.low_stock?'Low stock':'OK'}</td>
      <td><button style={button} disabled={!!countAttempt.current} onClick={()=>{
       setStockCountSku(item.sku);setStockCountExpected(item.current_stock);setStockCountActual(String(item.current_stock))
      }}>Stocktake</button></td>
     </tr>)}</tbody>
    </table>
   </div>
   {stockCountExpected!==null&&<div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:12}}>
    <p>Count {stockCountSku} · recorded baseline {stockCountExpected}</p>
    <input aria-label="Physical count" value={stockCountActual} disabled={countPending} onChange={e=>setStockCountActual(e.target.value)}/>
    <input aria-label="Stocktake reference" placeholder="Count sheet reference" value={stockCountReference} disabled={countPending} onChange={e=>setStockCountReference(e.target.value)}/>
    <input aria-label="Stocktake notes" placeholder="Reason for variance" value={stockCountNotes} disabled={countPending} onChange={e=>setStockCountNotes(e.target.value)}/>
    <button style={button} disabled={countPending||!stockCountReference.trim()||!stockCountNotes.trim()} onClick={reconcileCount}>Apply counted variance</button>
   </div>}
  </section>}
  {role==='SUPERVISOR'&&<section style={{padding:12,border:'1px solid #aaa',marginBottom:16}}>
   <h2>Suppliers, purchase orders and goods received</h2>
   <button style={button} onClick={refreshProcurement} disabled={procurementBusy}>Refresh suppliers, orders and replenishment</button>
   <h3>Register supplier</h3>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <input aria-label="Supplier code" placeholder="Supplier code" value={supplierCode} onChange={e=>setSupplierCode(e.target.value)}/>
    <input aria-label="Supplier name" placeholder="Supplier name" value={supplierName} onChange={e=>setSupplierName(e.target.value)}/>
    <input aria-label="Supplier contact" placeholder="Contact (optional)" value={supplierContact} onChange={e=>setSupplierContact(e.target.value)}/>
    <button style={button} disabled={procurementBusy||!supplierCode.trim()||!supplierName.trim()} onClick={registerSupplier}>Create supplier</button>
   </div>
   <h3>Create purchase order</h3>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <select aria-label="Purchase order supplier" value={poSupplier} onChange={e=>setPoSupplier(e.target.value)}>
     <option value="">Select supplier</option>
     {suppliers.map(s=><option key={s.code} value={s.code}>{s.name} ({s.code})</option>)}
    </select>
    <input aria-label="Purchase order reference" placeholder="Unique PO reference" value={poReference} onChange={e=>setPoReference(e.target.value)}/>
    <textarea aria-label="Purchase order lines" rows={3} placeholder={'One line per item: SKU, quantity, unit cost in ₦\nRICE-001, 20, 1500.00'} value={poLines} onChange={e=>setPoLines(e.target.value)}/>
    <button style={button} disabled={procurementBusy||!poSupplier||!poReference.trim()||!poLines.trim()} onClick={createPurchaseOrder}>Create purchase order</button>
   </div>
   <h3>Approve purchase order</h3>
   <input aria-label="Purchase order approval note" placeholder="Approval justification" value={approvalNote} onChange={e=>setApprovalNote(e.target.value)}/>
   {orders.filter(o=>o.approval==='PENDING').map(o=><p key={o.id}>{o.reference} · {o.supplier_code}
    <button style={button} disabled={procurementBusy||!approvalNote.trim()} onClick={()=>approveOrder(o.id)}>Approve (not own PO)</button>
   </p>)}
   <h3>Receive purchase order (partial deliveries supported)</h3>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <select aria-label="Goods receipt purchase order" value={receiptOrderId} onChange={e=>{setReceiptOrderId(e.target.value);setReceiptLineId('')}} disabled={procurementBusy||!!receiptAttempt.current}>
     <option value="">Select open purchase order</option>
     {orders.filter(o=>o.status!=='RECEIVED'&&o.approval==='APPROVED').map(o=><option key={o.id} value={o.id}>{o.reference} · {o.status}</option>)}
    </select>
    <select aria-label="Goods receipt line" value={receiptLineId} onChange={e=>setReceiptLineId(e.target.value)} disabled={procurementBusy||!!receiptAttempt.current}>
     <option value="">Select outstanding line</option>
     {orders.find(o=>String(o.id)===receiptOrderId)?.lines.filter(l=>l.quantity_outstanding>0).map(l=><option key={l.id} value={l.id}>{l.sku} · outstanding {l.quantity_outstanding}</option>)}
    </select>
    <input aria-label="Goods received units" placeholder="Units received" value={receiptQuantity} disabled={procurementBusy} onChange={e=>setReceiptQuantity(e.target.value)}/>
    <input aria-label="Supplier delivery reference" placeholder="Delivery note / GRN reference" value={receiptReference} disabled={procurementBusy} onChange={e=>setReceiptReference(e.target.value)}/>
    <button style={button} disabled={procurementBusy||!receiptOrderId||!receiptLineId||!receiptQuantity||!receiptReference.trim()} onClick={receivePurchaseOrder}>Record goods received</button>
   </div>
   <p>Goods receipts post inventory movements. Do not also record the same delivery through manual stock receiving.</p>
   <h3>Open purchase orders</h3>
   {orders.filter(o=>o.status!=='RECEIVED').map(o=><p key={o.id}>{o.reference} · {o.supplier_code} · {o.status}: {o.lines.map(l=>l.sku+' '+l.quantity_received+'/'+l.quantity_ordered).join(', ')}</p>)}
   <h3>Supplier invoice matching (one invoice per goods receipt)</h3>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <input aria-label="Goods receipt ID for invoice" placeholder="Goods receipt ID" value={invoiceReceiptId} onChange={e=>setInvoiceReceiptId(e.target.value)}/>
    <input aria-label="Supplier invoice number" placeholder="Supplier invoice number" value={invoiceNumber} onChange={e=>setInvoiceNumber(e.target.value)}/>
    <input aria-label="Supplier invoice amount in naira" placeholder="Invoice amount in ₦" value={invoiceAmount} onChange={e=>setInvoiceAmount(e.target.value)}/>
    <input aria-label="Supplier invoice notes" placeholder="Invoice review notes" value={invoiceNotes} onChange={e=>setInvoiceNotes(e.target.value)}/>
    <button style={button} disabled={procurementBusy||!invoiceReceiptId||!invoiceNumber.trim()||!invoiceAmount.trim()||!invoiceNotes.trim()} onClick={recordSupplierInvoice}>Match supplier invoice</button>
   </div>
   <h3>Accounts payable — recorded invoice exposure (payments not tracked)</h3>
   {payables.map(row=><p key={row.number}>{row.supplier_code} · {row.number}: {money(row.amount_minor)} · {row.status} (expected {money(row.expected_minor)})</p>)}
   <h3>Purchase order print preview</h3>
   <select aria-label="Select purchase order to print" value={printOrder?.id||''} onChange={e=>setPrintOrder(orders.find(o=>String(o.id)===e.target.value)||null)}>
    <option value="">Choose purchase order</option>{orders.map(o=><option key={o.id} value={o.id}>{o.reference}</option>)}
   </select>
   <button style={button} disabled={!printOrder} onClick={()=>window.print()}>Print / Save as PDF</button>
   {printOrder&&<article id="tokad-print-purchase-order">
    <h2>TOKAD MART · PURCHASE ORDER</h2><p>PO: {printOrder.reference} · Supplier: {printOrder.supplier_name}</p>
    <p>Approval: {printOrder.approval} · {printOrder.status}</p>
    <table><thead><tr><th>SKU</th><th>Qty</th><th>Cost</th></tr></thead><tbody>
     {printOrder.lines.map(l=><tr key={l.id}><td>{l.sku}</td><td>{l.quantity_ordered}</td><td>{money(l.unit_cost_minor)}</td></tr>)}
    </tbody></table><strong>Order total {money(printOrder.total_cost_minor)}</strong>
   </article>}
   <h3>Record supplier payment evidence</h3>
   <p>Enter a reference from an already completed external payment. This does not send money.</p>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <select aria-label="Invoice for supplier payment" value={supplierPaymentInvoice} onChange={e=>setSupplierPaymentInvoice(e.target.value)}>
     <option value="">Select matched invoice</option>
     {payables.filter(p=>p.status==='MATCHED').map(p=><option key={p.number} value={p.id}>{p.supplier_code} · {p.number}</option>)}
    </select>
    <input aria-label="Supplier bank payment reference" placeholder="External payment reference" value={supplierPaymentReference} onChange={e=>setSupplierPaymentReference(e.target.value)}/>
    <input aria-label="Supplier payment amount" placeholder="Amount in ₦" value={supplierPaymentAmount} onChange={e=>setSupplierPaymentAmount(e.target.value)}/>
    <input aria-label="Supplier payment evidence notes" placeholder="Evidence reviewed / source" value={supplierPaymentNotes} onChange={e=>setSupplierPaymentNotes(e.target.value)}/>
    <button style={button} disabled={procurementBusy||!supplierPaymentInvoice||!supplierPaymentReference.trim()||!supplierPaymentAmount.trim()||!supplierPaymentNotes.trim()} onClick={recordPaymentEvidence}>Record external payment evidence</button>
   </div>
   <h3>Verify supplier payment evidence</h3>
   <input aria-label="Supplier payment verification notes" placeholder="Independent external evidence review notes" value={supplierVerificationNotes} onChange={e=>setSupplierVerificationNotes(e.target.value)}/>
   {supplierPayments.filter(p=>p.status==='RECORDED').map(p=><p key={p.id}>
    #{p.id} · Invoice {p.invoice_id} · {p.reference} · {money(p.amount_minor)}
    <button style={button} disabled={procurementBusy||!supplierVerificationNotes.trim()} onClick={()=>verifyPaymentEvidence(p.id)}>Manually verify (different supervisor)</button>
   </p>)}
   <h3>Supplier reconciliation</h3>
   {supplierReconciliation.map(row=><p key={row.invoice_id}>
    {row.invoice_number} · {row.review_status}: verified {money(row.verified_evidence_minor)}, pending review {money(row.pending_review_minor)}, unverified exposure {money(row.remaining_unverified_minor)}
   </p>)}
   <p>Verification is a supervisor review of external records, not a bank API confirmation.</p>
   <h3>Replenishment report (threshold {reportThreshold})</h3>
   <div style={{maxHeight:200,overflowY:'auto'}}>
    {replenishment.map(p=><p key={p.sku}>{p.sku}: on hand {p.current_stock}, on order {p.outstanding_order_units}, uncovered target gap {p.reorder_gap_units}</p>)}
   </div>
  </section>}
  {role==='SUPERVISOR'&&<section style={{padding:12,border:'1px solid #aaa',marginBottom:16}}>
   <h2>Financial controls and management reporting</h2>
   <p>Location-scoped operational reporting. Gross sales are not profit or reconciled bank cash.</p>
   <label>From <input aria-label="Financial report start date" type="date" value={financeStart} onChange={e=>setFinanceStart(e.target.value)}/></label>
   <label>To <input aria-label="Financial report end date" type="date" value={financeEnd} onChange={e=>setFinanceEnd(e.target.value)}/></label>
   <button style={button} disabled={financeBusy} onClick={loadFinance}>Refresh financial dashboard</button>
   {financeReport&&<div>
    <p><strong>Completed sales</strong>: {financeReport.sales.completed_sale_count} · Gross {money(financeReport.sales.gross_minor)}</p>
    <p><strong>Expenses</strong>: approved {money(financeReport.expenses.approved_minor)} · awaiting review {money(financeReport.expenses.pending_review_minor)}</p>
    <h3>Daily sales</h3>
    {financeReport.sales.daily.map(d=><p key={d.date}>{d.date}: {money(d.gross_minor)}</p>)}
    <h3>Cashier shift variances</h3>
    {financeReport.cashier_shifts.map(x=><p key={x.shift_id}>Shift #{x.shift_id} · {x.terminal}: {x.variance_minor===null?'Unknown':money(x.variance_minor)} · {x.review_status}</p>)}
    <h3>Supplier invoice evidence</h3>
    {financeReport.supplier_invoice_exposure.map(x=><p key={x.invoice_id}>
      {x.invoice_number} · {x.status}: invoice {money(x.amount_minor)}, verified evidence {money(x.verified_evidence_minor)}, awaiting review {money(x.pending_review_minor)}
    </p>)}
    <p>{financeReport.disclaimer}</p>
   </div>}
   <h3>Record operating expense</h3>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <input aria-label="Expense reference" placeholder="Unique expense reference" value={expenseReference} onChange={e=>setExpenseReference(e.target.value)}/>
    <input aria-label="Expense category" placeholder="Category" value={expenseCategory} onChange={e=>setExpenseCategory(e.target.value)}/>
    <input aria-label="Expense description" placeholder="Description" value={expenseDescription} onChange={e=>setExpenseDescription(e.target.value)}/>
    <input aria-label="Expense amount" placeholder="Amount in ₦" value={expenseAmount} onChange={e=>setExpenseAmount(e.target.value)}/>
    <input aria-label="Expense date" type="date" value={expenseDate} onChange={e=>setExpenseDate(e.target.value)}/>
    <button style={button} disabled={financeBusy||!expenseReference.trim()||!expenseCategory.trim()||!expenseDescription.trim()||!expenseAmount.trim()} onClick={recordExpense}>Record expense</button>
   </div>
   <h3>Independent expense review</h3>
   <input aria-label="Expense review notes" placeholder="Review evidence and reason" value={expenseReviewNotes} onChange={e=>setExpenseReviewNotes(e.target.value)}/>
   {expenseRows.filter(x=>x.review_status==='PENDING').map(x=><p key={x.id}>
    #{x.id} {x.reference} · {x.category} · {money(x.amount_minor)}
    <button style={button} disabled={financeBusy||!expenseReviewNotes.trim()} onClick={()=>reviewExpense(x.id,'APPROVED')}>Approve</button>
    <button style={button} disabled={financeBusy||!expenseReviewNotes.trim()} onClick={()=>reviewExpense(x.id,'REJECTED')}>Reject</button>
   </p>)}
  </section>}
  <section style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:24}}>
   <div>
    <h2>Products</h2>
    <input placeholder="Search name or SKU" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void search()}}/>
    <button style={button} onClick={search}>Search</button>
    <div style={{margin:'12px 0',padding:12,border:'1px solid #ccc'}}>
     <label htmlFor="pos-barcode">Barcode / SKU scanner</label>
     <p style={{fontSize:12}}>Focus this box and scan a product. USB keyboard-wedge scanners usually send Enter after the code. Exact barcode or SKU matches add one unit.</p>
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
    <p className="tokad-no-print"><button style={button} disabled={!!printOrder} onClick={()=>window.print()}>Print receipt</button></p>
   </article>}
  <style>{`
   @media print {
    @page { margin: 3mm; }
    body * { visibility: hidden !important; }
    ${printOrder ? '#tokad-print-purchase-order, #tokad-print-purchase-order *' : '#tokad-print-receipt, #tokad-print-receipt *'} { visibility: visible !important; }
    #tokad-print-receipt { position: absolute; top: 0; left: 0; width: 72mm; max-width: 72mm !important; padding: 0 !important; border: 0 !important; color: #000; background: #fff; font-size: 11px; }
    #tokad-print-receipt h2 { text-align:center; font-size: 16px; }
    #tokad-print-purchase-order { position: absolute; left:0; top:0; width: 190mm; background:white; color:black; }
    #tokad-print-receipt .tokad-no-print, #tokad-print-receipt .tokad-no-print * { display: none !important; }
   }
  `}</style>
  <p role="status">{message}</p>
  <p style={{fontSize:12}}>Cash-only session POS with cashier shifts. Card, transfers, refunds and wholesale pricing require separate migration.</p>
 </main>
}
