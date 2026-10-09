(() => {
  const key = document.title.startsWith('Minna') ? 'minna-details' : 'rb-details';
  let expanded = false;
  try { expanded = localStorage.getItem(key) === 'true'; } catch (_) {}
  const button = document.createElement('button');
  button.type = 'button';
  button.id = 'detailToggle';
  button.className = 'hbtn ghost detail-toggle';
  const labels = {vi: ['Chi tiết', 'Thu gọn'], en: ['Details', 'Simplify'], ja: ['詳細', '簡易表示']};
  const update = () => {
    const l = document.documentElement.lang || 'vi';
    button.textContent = (labels[l] || labels.vi)[expanded ? 1 : 0];
    button.setAttribute('aria-pressed', String(expanded));
    document.body.classList.toggle('show-details', expanded);
  };
  (document.querySelector('.menu-actions') || document.querySelector('header')).append(button);
  button.addEventListener('click', () => {
    expanded = !expanded;
    try { localStorage.setItem(key, String(expanded)); } catch (_) {}
    update();
    window.dispatchEvent(new Event('resize'));
  });
  new MutationObserver(update).observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
  update();
})();
