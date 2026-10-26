/**
 * Kazi-Kasi Loading States
 * 
 * Different UX-designed loading screens for different purposes:
 * - Short loads (< 1s): Subtle shimmer
 * - Medium loads (1-3s): Spinner with context
 * - Long loads (3-10s): Progress indicator with tips
 * - Very long loads (> 10s): Detailed explanation with animation
 */

// Loading state manager
const LoadingStates = {
  currentOverlay: null,
  
  // Show loading overlay
  show(type = 'default', message = 'Loading...', tips = []) {
    this.hide();
    
    const overlay = document.createElement('div');
    overlay.className = `loading-overlay loading-${type}`;
    
    let content = '';
    
    switch(type) {
      case 'auth':
        content = `
          <div class="loading-spinner-large"></div>
          <div class="loading-title">Connecting to Google...</div>
          <div class="loading-message">${message}</div>
          <div class="loading-steps">
            <div class="step active">Verifying credentials</div>
            <div class="step">Syncing your profile</div>
            <div class="step">Loading your dashboard</div>
          </div>
        `;
        break;
      
      case 'galaxy':
        content = `
          <div class="galaxy-loader">
            <div class="orbit"></div>
            <div class="orbit"></div>
            <div class="orbit"></div>
            <div class="core"></div>
          </div>
          <div class="loading-title">Entering the Job Verse...</div>
          <div class="loading-message">Loading 3D universe</div>
          <div class="loading-tips">
            ${tips.length > 0 ? `<div class="tip">💡 ${tips[Math.floor(Math.random() * tips.length)]}</div>` : ''}
          </div>
        `;
        break;
      
      case 'search':
        content = `
          <div class="loading-dots">
            <span></span><span></span><span></span>
          </div>
          <div class="loading-message">${message}</div>
        `;
        break;
      
      case 'upload':
        content = `
          <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
          </div>
          <div class="loading-title">Uploading CV...</div>
          <div class="loading-message">${message}</div>
          <div class="progress-text">0%</div>
        `;
        break;
      
      default:
        content = `
          <div class="loading-spinner"></div>
          <div class="loading-message">${message}</div>
        `;
    }
    
    overlay.innerHTML = content;
    document.body.appendChild(overlay);
    this.currentOverlay = overlay;
    
    // Animate progress for upload
    if (type === 'upload') {
      this.animateProgress(overlay);
    }
    
    // Auto-hide after timeout (unless manually hidden)
    if (type !== 'upload') {
      setTimeout(() => {
        if (this.currentOverlay === overlay) {
          this.hide();
        }
      }, 15000); // 15s max
    }
  },
  
  // Hide loading overlay
  hide() {
    if (this.currentOverlay) {
      this.currentOverlay.classList.add('hidden');
      setTimeout(() => {
        if (this.currentOverlay && this.currentOverlay.parentNode) {
          this.currentOverlay.parentNode.removeChild(this.currentOverlay);
        }
        this.currentOverlay = null;
      }, 300);
    }
  },
  
  // Animate progress bar
  animateProgress(overlay) {
    let progress = 0;
    const fill = overlay.querySelector('.progress-fill');
    const text = overlay.querySelector('.progress-text');
    
    const interval = setInterval(() => {
      progress += Math.random() * 15;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
      }
      if (fill) fill.style.width = progress + '%';
      if (text) text.textContent = Math.floor(progress) + '%';
    }, 300);
    
    overlay.dataset.progressInterval = interval;
  },
  
  // Update message
  updateMessage(message) {
    if (this.currentOverlay) {
      const msgEl = this.currentOverlay.querySelector('.loading-message');
      if (msgEl) msgEl.textContent = message;
    }
  }
};

// Expose globally
window.LoadingStates = LoadingStates;

// Auto-detect page loads - minimal version that doesn't block
(function() {
  // Show on link clicks (only for internal navigation)
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link || !link.href) return;
    if (link.target) return;
    if (link.href.indexOf('#') !== -1) return;
    if (link.classList.contains('no-loading')) return;
    // Only show for internal links
    const origin = window.location.origin;
    if (link.href.indexOf(origin) !== 0 && link.href.indexOf('/') !== 0) return;
    LoadingStates.show('default', 'Loading page...');
  });
  
  // Show on form submits (only POST forms)
  document.addEventListener('submit', (e) => {
    const form = e.target.closest('form');
    if (!form) return;
    if (form.method && form.method.toLowerCase() === 'get') return;
    LoadingStates.show('default', 'Processing...');
  });
})();
