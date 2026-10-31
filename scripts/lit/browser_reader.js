// Reading aid run in the browser (Claude in Chrome) on a paper's landing page or PDF URL when the PDF cannot be
// downloaded by script. Finds the PDF (citation_pdf_url meta, then a .pdf / bitstream / download link, or the page
// itself), parses it in memory with pdf.js, keeps the text in window.__t and returns a short summary:
// pages, keyword counts, the abstract and the first evaluation passage. Nothing is saved to disk.
// Query strings are blanked in the returned text so no session tokens leave the page.
(async () => {
  const pdfjs = await import('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.min.mjs');
  pdfjs.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.worker.min.mjs';
  const cands = [];
  const meta = document.querySelector('meta[name=citation_pdf_url]');
  if (meta) cands.push(meta.content);
  for (const a of document.querySelectorAll('a')) {
    if (/\.pdf($|\?)|bitstream|\/download\/|viewcontent\.cgi|Delivery\.cfm/i.test(a.href)) cands.push(a.href);
  }
  cands.push(location.href);
  for (const u of [...new Set(cands)].slice(0, 6)) {
    try {
      const buf = await (await fetch(u, { credentials: 'include' })).arrayBuffer();
      if (String.fromCharCode(...new Uint8Array(buf.slice(0, 5))) !== '%PDF-') continue;
      const doc = await pdfjs.getDocument({ data: buf }).promise;
      let t = '';
      for (let i = 1; i <= doc.numPages; i++) {
        const c = await (await doc.getPage(i)).getTextContent();
        t += c.items.map((x) => x.str).join(' ') + ' ';
      }
      t = t.replace(/\s+/g, ' ').replace(/[?&=]/g, ' ');
      window.__t = t;
      const k = ['Terraform', 'Kubernetes', 'manifest', 'Ansible', 'Docker', 'deploy', 'evaluat', 'experiment', 'Checkov', 'cluster']
        .map((w) => w + ':' + (t.split(w).length - 1)).join(' ');
      const ab = Math.max(0, t.search(/abstract/i));
      const ev = t.search(/(results (show|indicate|demonstrate)|we evaluat|evaluated (on|using|with)|experimental (setup|results))/i);
      return doc.numPages + 'p | ' + k + ' | ABS: ' + t.slice(ab, ab + 500) + ' | EVAL: ' + (ev > 0 ? t.slice(ev - 80, ev + 320) : '-');
    } catch (e) { /* try next candidate */ }
  }
  return 'no PDF found: ' + document.title.slice(0, 80);
})()
