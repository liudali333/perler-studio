/* =====================================================================
 * [REMAKE] 换图重转
 * 原图页签下多两个入口：把当前原图裁一裁、或直接换一张图，交给拼豆图纸工坊重新出一版图纸
 * （新图纸在独立页面打开，这份图纸的编辑与进度不受影响）。
 * 裁切用独立浮层：拖框、拖角改大小，确认后把裁切结果作为新图提交。
 * 本地双击打开（file://）时没有后台，两个入口自动隐藏。
 * ===================================================================== */
(() => {
  const bar = document.getElementById('remakeBar');
  if (!bar || location.protocol === 'file:') { if (bar) bar.remove(); return; }
  const fileIn = document.getElementById('remakeFile');
  const img = document.querySelector('#sourceCards img');
  let picked = null;

  const busy = (on, text) => {
    bar.querySelectorAll('button').forEach(b => (b.disabled = on));
    const tip = bar.querySelector('.rb-tip');
    if (on) tip.textContent = text; else tip.textContent = '想换一张？原图裁一下再重做，出来的豆格会更准。';
  };

  async function submit(blob, name) {
    busy(true, '正在重新做图纸，大概二十秒…');
    const fd = new FormData();
    fd.append('file', blob, name);
    fd.append('task', state.title || D.taskName);
    fd.append('boards', '36,52,78,104,156');
    fd.append('default_size', String(D.defaultSize || 78));
    try {
      const job = await (await fetch('/api/convert', { method: 'POST', body: fd })).json();
      if (job.error) throw new Error(job.error);
      poll(job.id);
    } catch (e) {
      busy(false);
      toast('重转失败：' + (e.message || e));
    }
  }

  async function poll(id) {
    let n = 0;
    const tick = async () => {
      const j = await (await fetch('/api/jobs/' + id)).json();
      if (j.status === 'done') {
        busy(false);
        const w = window.open('/api/jobs/' + id + '/blueprint', '_blank');
        if (!w) location.href = '/api/jobs/' + id + '/blueprint';
        toast('新图纸做好啦');
        return;
      }
      if (j.status === 'error') { busy(false); toast('重转失败：' + j.error); return; }
      busy(true, j.step || '正在做图纸…');
      if (++n < 240) setTimeout(tick, 1000);
    };
    tick();
  }

  fileIn.onchange = () => {
    const f = fileIn.files && fileIn.files[0];
    if (f) submit(f, f.name);
    fileIn.value = '';
  };
  document.getElementById('remakeNew').onclick = () => fileIn.click();

  /* ---- 裁切浮层 ---- */
  function cropModal(src, onDone) {
    const wrap = document.createElement('div');
    wrap.className = 'rm-mask';
    wrap.innerHTML = `
      <div class="rm-box">
        <div class="rm-hd">裁切原图 <span>拖动方框选主体，框外的部分不会进图纸</span></div>
        <div class="rm-stage"><img class="rm-img" src="${src}" alt="裁切预览"><div class="rm-rect">
          <i data-h="nw"></i><i data-h="ne"></i><i data-h="sw"></i><i data-h="se"></i>
        </div></div>
        <div class="rm-ft"><button class="btn rm-cancel">取消</button><button class="btn primary rm-ok">用这块重做</button></div>
      </div>`;
    document.body.appendChild(wrap);
    const imgEl = wrap.querySelector('.rm-img'), rect = wrap.querySelector('.rm-rect');
    let box = { x: .08, y: .08, w: .84, h: .84 };
    const paint = () => {
      rect.style.left = box.x * 100 + '%'; rect.style.top = box.y * 100 + '%';
      rect.style.width = box.w * 100 + '%'; rect.style.height = box.h * 100 + '%';
    };
    paint();
    let drag = null;
    const start = (e, mode) => { drag = { mode, sx: e.clientX, sy: e.clientY, box: { ...box } }; e.preventDefault(); };
    rect.addEventListener('pointerdown', e => {
      const h = e.target.dataset && e.target.dataset.h;
      start(e, h || 'move');
    });
    wrap.querySelector('.rm-stage').addEventListener('pointerdown', e => {
      if (e.target !== imgEl) return;
      const r = imgEl.getBoundingClientRect();
      box = { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height, w: .1, h: .1 };
      paint(); start(e, 'se');
    });
    window.addEventListener('pointermove', e => {
      if (!drag) return;
      const r = imgEl.getBoundingClientRect();
      const dx = (e.clientX - drag.sx) / r.width, dy = (e.clientY - drag.sy) / r.height, b = drag.box;
      if (drag.mode === 'move') {
        box.x = Math.min(Math.max(0, b.x + dx), 1 - b.w);
        box.y = Math.min(Math.max(0, b.y + dy), 1 - b.h);
      } else {
        let x0 = b.x, y0 = b.y, x1 = b.x + b.w, y1 = b.y + b.h;
        if (drag.mode.includes('w')) x0 = Math.min(Math.max(0, b.x + dx), x1 - .05);
        if (drag.mode.includes('e')) x1 = Math.max(Math.min(1, b.x + b.w + dx), x0 + .05);
        if (drag.mode.includes('n')) y0 = Math.min(Math.max(0, b.y + dy), y1 - .05);
        if (drag.mode.includes('s')) y1 = Math.max(Math.min(1, b.y + b.h + dy), y0 + .05);
        box = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
      }
      paint();
    });
    window.addEventListener('pointerup', () => { drag = null; });
    const close = () => wrap.remove();
    wrap.querySelector('.rm-cancel').onclick = close;
    wrap.querySelector('.rm-ok').onclick = () => {
      const im = new Image();
      im.onload = () => {
        const sx = Math.round(box.x * im.width), sy = Math.round(box.y * im.height);
        const sw = Math.round(box.w * im.width), sh = Math.round(box.h * im.height);
        const c = document.createElement('canvas');
        c.width = sw; c.height = sh;
        c.getContext('2d').drawImage(im, sx, sy, sw, sh, 0, 0, sw, sh);
        c.toBlob(b => { close(); onDone(b, 'crop.png'); }, 'image/png');
      };
      im.src = src;
    };
  }

  document.getElementById('remakeCrop').onclick = () => {
    if (!img) return toast('这张图纸没有原图');
    cropModal(D.images[0], (blob, name) => submit(blob, name));
  };
})();
/* ===== [REMAKE] END ===== */
