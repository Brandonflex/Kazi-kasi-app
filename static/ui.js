/**
 * Kazi-Kasi UI Interactions
 * - Tab switching for digest page
 * - Loading overlay for page transitions
 * - Skeleton loader management
 */

// Tab switching for digest page
window.showTab = function(tabName) {
  var contents = document.querySelectorAll('.tab-content');
  var buttons = document.querySelectorAll('.tab-btn');
  
  for (var i = 0; i < contents.length; i++) {
    contents[i].classList.remove('active');
  }
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].classList.remove('active');
  }
  
  var target = document.getElementById('tab-' + tabName);
  if (target) {
    target.classList.add('active');
  }
  
  if (event && event.target) {
    event.target.classList.add('active');
  }
};

// Loading overlay for page transitions
(function() {
  // Create loading overlay
  var overlay = document.createElement('div');
  overlay.className = 'loading-overlay';
  overlay.innerHTML = '<div class="loading-spinner"></div><div class="loading-text">Loading...</div>';
  document.body.appendChild(overlay);
  
  // Hide when page is fully loaded
  window.addEventListener('load', function() {
    setTimeout(function() {
      overlay.classList.add('hidden');
      setTimeout(function() {
        if (overlay.parentNode) {
          overlay.parentNode.removeChild(overlay);
        }
      }, 300);
    }, 300);
  });
  
  // Show on link clicks (for SPA-like feel)
  document.addEventListener('click', function(e) {
    var link = e.target.closest('a');
    if (link && link.href && link.href.indexOf(window.location.origin) === 0 && !link.target) {
      overlay.classList.remove('hidden');
    }
  });
})();

// Skeleton loader helper
window.showSkeleton = function(containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  
  container.innerHTML = '<div class="skeleton skeleton-card"></div>'.repeat(3);
};

window.hideSkeleton = function(containerId, content) {
  var container = document.getElementById(containerId);
  if (container) {
    container.innerHTML = content;
  }
};
