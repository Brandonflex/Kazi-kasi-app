// Scroll-triggered reveal animations
(function() {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.reveal').forEach(function(el) {
      el.classList.add('in');
    });
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  const elements = document.querySelectorAll('.reveal');
  elements.forEach(el => observer.observe(el));

  requestAnimationFrame(() => {
    elements.forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        el.classList.add('in');
        observer.unobserve(el);
      }
    });
  });
})();

// Header scroll state
window.addEventListener('scroll', () => {
  const header = document.querySelector('header');
  if (header) header.classList.toggle('scrolled', window.scrollY > 10);
}, { passive: true });

// 3D tilt effect on cards
(function() {
  const tiltElements = document.querySelectorAll('[data-tilt]');
  if (!tiltElements.length) return;

  tiltElements.forEach(el => {
    el.addEventListener('mousemove', (e) => {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -6;
      const rotateY = ((x - centerX) / centerX) * 6;
      el.style.transform = `perspective(600px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-2px)`;
    });

    el.addEventListener('mouseleave', () => {
      el.style.transform = 'perspective(600px) rotateX(0) rotateY(0) translateY(0)';
    });
  });

  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -3;
      const rotateY = ((x - centerX) / centerX) * 3;
      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-3px)`;
    });

    card.addEventListener('mouseleave', () => {
      card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateY(0)';
    });
  });
})();

// Loading state wiring
(function() {
  const overlay = document.getElementById('page-loading-overlay');
  if (!overlay) return;

  // Hide overlay when DOM is ready (faster than 'load' which waits for images/fonts)
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    hideOverlay();
  } else {
    document.addEventListener('DOMContentLoaded', hideOverlay);
  }

  function hideOverlay() {
    setTimeout(function() {
      overlay.style.opacity = '0';
      setTimeout(function() { overlay.style.display = 'none'; }, 300);
    }, 150);
  }

  document.addEventListener('click', function(e) {
    const link = e.target.closest('a');
    if (!link || !link.href) return;
    if (link.target) return;
    if (link.href.indexOf('#') !== -1) return;
    if (link.classList.contains('no-loading')) return;
    const origin = window.location.origin;
    if (link.href.indexOf(origin) !== 0 && link.href.indexOf('/') !== 0) return;
    overlay.style.display = 'flex';
    overlay.style.opacity = '1';
  });

  document.addEventListener('submit', function(e) {
    const form = e.target.closest('form');
    if (!form) return;
    if (form.method && form.method.toLowerCase() === 'get') return;
    overlay.style.display = 'flex';
    overlay.style.opacity = '1';
  });
})();
