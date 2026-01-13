(function(){
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
  let ws = null;
  const tickersInput = document.getElementById('tickers');
  const intervalInput = document.getElementById('interval');
  const subscribeBtn = document.getElementById('subscribe');
  const unsubscribeBtn = document.getElementById('unsubscribe');
  const tbody = document.querySelector('#prices tbody');

  function updateTable(prices, ts){
    tbody.innerHTML = '';
    Object.keys(prices).forEach(sym => {
      const tr = document.createElement('tr');
      const tdSym = document.createElement('td'); tdSym.textContent = sym;
      const tdPrice = document.createElement('td'); tdPrice.textContent = prices[sym] === null ? '-' : prices[sym].toFixed(2);
      const tdTs = document.createElement('td'); tdTs.textContent = ts;
      tr.appendChild(tdSym); tr.appendChild(tdPrice); tr.appendChild(tdTs);
      tbody.appendChild(tr);
    });
  }

  function connect(){
    if(ws) return;
    ws = new WebSocket(wsUrl);
    ws.addEventListener('open', ()=> console.log('ws open'));
    ws.addEventListener('message', ev => {
      try{
        const data = JSON.parse(ev.data);
        updateTable(data.prices || {}, data.ts || '');
      }catch(e){ console.error(e); }
    });
    ws.addEventListener('close', ()=> { ws = null; console.log('ws closed'); });
  }

  subscribeBtn.addEventListener('click', ()=>{
    connect();
    if(!ws) return;
    const tickers = tickersInput.value.split(',').map(s=>s.trim().toUpperCase()).filter(s=>s);
    const interval = parseInt(intervalInput.value) || 5;
    ws.send(JSON.stringify({tickers, interval}));
  });

  unsubscribeBtn.addEventListener('click', ()=>{
    if(!ws) return;
    ws.close();
    ws = null;
    tbody.innerHTML = '';
  });
})();