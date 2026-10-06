const nativeFetch = window.fetch.bind(window);
const start = document.querySelector('#start');
const status = document.querySelector('#loading-text');
const progress = document.querySelector('#progress');
const canvas = document.querySelector('#canvas');
function fitCanvas() {
  const area = document.querySelector('#game').getBoundingClientRect();
  const ratio = Math.min(devicePixelRatio || 1, 1.5);
  canvas.width = Math.round(area.width * ratio);
  canvas.height = Math.round(area.height * ratio);
}
window.addEventListener('resize', fitCanvas);
fitCanvas();
let engine;
let loaded = 0;
let total = 1;
let running = false;

async function downloadStep(promise, controller) {
  let timer;
  try {
    return await Promise.race([promise,new Promise((_,reject)=>{
      timer = setTimeout(()=>{
        controller.abort();
        reject(new Error('網路下載逾時，請重新載入或稍後再試。'));
      },15000);
    })]);
  } finally { clearTimeout(timer); }
}

async function download(url) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const controller = new AbortController();
    let reader;
    let size = 0;
    try {
      const response = await downloadStep(nativeFetch(url,{signal:controller.signal}),controller);
      if (!response.ok) throw new Error('遊戲檔案載入失敗，請稍後再試。');
      reader = response.body.getReader();
      const chunks = [];
      for (;;) {
        const {done, value} = await downloadStep(reader.read(),controller);
        if (done) break;
        chunks.push(value); size += value.byteLength; loaded += value.byteLength;
        const percent = Math.min(99, Math.floor(loaded * 100 / total));
        progress.value = Math.max(progress.value,percent);
        status.textContent = `準備冒險… ${progress.value}%`;
      }
      const result = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
      return result;
    } catch (error) {
      loaded -= size;
      controller.abort();
      if (reader) void reader.cancel().catch(()=>{});
      if (attempt === 2) throw new Error(error.name === 'AbortError' ? '網路下載逾時，請重新載入或稍後再試。' : error.message);
      status.textContent = `下載連線中斷，正在重試（${attempt+1}/2）…`;
      await new Promise(resolve=>setTimeout(resolve,300));
    }
  }
}

async function loadParts(files) {
  // Download sequentially to keep transient memory bounded on phones.
  const parts = [];
  let length = 0;
  for (const part of files) {
    const bytes = await download(part.url);
    if (bytes.length !== part.size) throw new Error('遊戲檔案不完整，請重新載入。');
    parts.push(bytes); length += bytes.length;
  }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) { result.set(part, offset); offset += part.length; }
  return result;
}

async function loadWasm(manifest) {
  const compressed = await download(manifest.gzip.url);
  if (compressed.length !== manifest.gzip.size) throw new Error('遊戲引擎載入不完整，請重新載入。');
  let bytes;
  if ('DecompressionStream' in window) {
    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
    bytes = new Uint8Array(await new Response(stream).arrayBuffer());
  } else {
    bytes = window.fflate.gunzipSync(compressed);
  }
  if (bytes.length !== manifest.size) throw new Error('遊戲引擎載入不完整，請重新載入。');
  return bytes;
}

async function fullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) {
      await document.documentElement.requestFullscreen();
      try { await screen.orientation.lock('landscape'); } catch {}
    } else status.textContent = '請保持橫向；這個瀏覽器不支援全螢幕。';
  } catch { status.textContent = '請保持橫向遊玩。'; }
}
document.querySelector('#fullscreen').addEventListener('click', fullscreen);
function immersiveLayout() {
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  document.body.classList.toggle('playing-immersive', document.querySelector('#welcome').hidden && (standalone || !!document.fullscreenElement));
  fitCanvas();
}
document.addEventListener('fullscreenchange', () => {
  immersiveLayout();
  document.querySelector('#fullscreen').textContent = document.fullscreenElement ? '離開全螢幕' : '全螢幕';
});

start.addEventListener('click', async () => {
  if (running) return;
  running = true; start.disabled = true; start.textContent = '準備冒險…'; progress.hidden = false;
  // Establish an audio gesture before downloading; Godot owns its own player.
  const Audio = window.AudioContext || window.webkitAudioContext;
  if (Audio) { const context = new Audio(); await context.resume().catch(() => {}); await context.close().catch(() => {}); }
  try {
    const missing = Engine.getMissingFeatures({threads:false});
    if (missing.length) throw new Error('這個瀏覽器無法執行遊戲，請用新版 Safari 或 Chrome。');
    const manifestResponse = await nativeFetch('assets-1b3d6e634390.json');
    if (!manifestResponse.ok) throw new Error('遊戲資料載入失敗，請重新載入。');
    const manifest = await manifestResponse.json();
    total = manifest.pack.reduce((n, f) => n + f.size, 0) + manifest.wasm.gzip.size;
    const wasm = loadWasm(manifest.wasm);
    // Adapt only the engine's one virtual WASM URL; all other requests stay native.
    const wasmURL = new URL('index.wasm', location.href).href;
    window.fetch = (input, options) => {
      const url = new URL(input instanceof Request ? input.url : String(input), location.href).href;
      return url === wasmURL ? wasm.then(bytes => new Response(bytes, {headers:{'Content-Type':'application/wasm'}})) : nativeFetch(input, options);
    };
    fitCanvas();
    engine = new Engine({executable:'index',canvas,canvasResizePolicy:0,focusCanvas:true,args:['--main-pack','index.pck']});
    try {
      await Promise.all([
        wasm,
        engine.init('index'),
        loadParts(manifest.pack).then(bytes => engine.preloadFile(bytes.buffer, 'index.pck')),
      ]);
    } finally { window.fetch = nativeFetch; }
    status.textContent = '準備完成！'; progress.value = 100;
    await engine.start();
    document.querySelector('#welcome').hidden = true;
    immersiveLayout();
    document.querySelector('#rotate-note').textContent = '戰鬥會暫停，轉回橫向後按「繼續冒險」。';
    canvas.focus();
  } catch (error) {
    console.error(error);
    status.textContent = error.message || '載入失敗，請重新載入。';
    start.disabled = false; start.textContent = '重新載入';
    start.onclick = () => location.reload();
    progress.hidden = true;
  }
});
