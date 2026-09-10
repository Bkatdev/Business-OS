(() => {
  'use strict';
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const progress = document.createElement('div');
  progress.id = 'bos-scroll-progress';
  document.body.appendChild(progress);
  const updateProgress = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    progress.style.width = (max > 0 ? Math.min(100, (window.scrollY / max) * 100) : 0) + '%';
  };
  updateProgress();
  addEventListener('scroll', updateProgress, { passive: true });
  addEventListener('resize', updateProgress);

  const candidates = document.querySelectorAll('.page-content > *, .card, .panel, .v9-card, .v9-panel, table');
  candidates.forEach((el, i) => {
    if (i < 28) el.classList.add('bos-reveal');
  });
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('bos-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.06, rootMargin: '0px 0px -24px 0px' });
  document.querySelectorAll('.bos-reveal').forEach((el) => io.observe(el));

  document.querySelectorAll('.card, .panel, .v9-card, .v9-panel, .metric-card, .stat-card').forEach((el) => {
    el.classList.add('bos-pointer-glow');
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty('--bos-x', `${e.clientX - r.left}px`);
      el.style.setProperty('--bos-y', `${e.clientY - r.top}px`);
    }, { passive: true });
  });
})();
