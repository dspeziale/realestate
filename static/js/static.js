/* Copyright 2025 SILICONDEV SPA */
/* Filename: static/js/app.js */
/* Description: Custom JavaScript for Real Estate Auction Management */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert.alert-dismissible');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        });
    }, 5000);

    // Sidebar toggle for mobile
    const sidebarToggle = document.querySelector('[data-bs-toggle="collapse"][data-bs-target="#sidebar"]');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            const sidebar = document.getElementById('sidebar');
            sidebar.classList.toggle('show');
        });
    }

    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Price formatting
    const priceInputs = document.querySelectorAll('.price-input');
    priceInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            const value = parseFloat(this.value);
            if (!isNaN(value)) {
                this.value = value.toFixed(2);
            }
        });
    });

    // Property search with autocomplete
    const searchInput = document.getElementById('property-search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            if (query.length < 2) {
                hideSearchResults();
                return;
            }

            searchTimeout = setTimeout(function() {
                searchProperties(query);
            }, 300);
        });

        // Hide results when clicking outside
        document.addEventListener('click', function(event) {
            if (!searchInput.contains(event.target)) {
                hideSearchResults();
            }
        });
    }

    // Initialize auction countdown timers
    updateCountdownTimers();
    setInterval(updateCountdownTimers, 1000);

    // Initialize bid functionality
    initializeBidding();

    // Initialize infinite scroll for property listings
    initializeInfiniteScroll();
});

// Property search functionality
function searchProperties(query) {
    fetch(`/properties/api/search?q=${encodeURIComponent(query)}&limit=10`)
        .then(response => response.json())
        .then(data => {
            showSearchResults(data);
        })
        .catch(error => {
            console.error('Search error:', error);
            hideSearchResults();
        });
}

function showSearchResults(results) {
    let resultsContainer = document.getElementById('search-results');
    
    if (!resultsContainer) {
        resultsContainer = document.createElement('div');
        resultsContainer.id = 'search-results';
        resultsContainer.className = 'search-results position-absolute w-100 bg-white border border-top-0 shadow-sm';
        resultsContainer.style.zIndex = '1000';
        document.getElementById('property-search').parentNode.appendChild(resultsContainer);
    }

    if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="p-3 text-muted">Nessun risultato trovato</div>';
    } else {
        const html = results.map(property => `
            <div class="search-result-item p-2 border-bottom" style="cursor: pointer;" 
                 onclick="window.location.href='/properties/${property.id}'">
                <div class="fw-bold">${property.title}</div>
                <div class="text-muted small">${property.address}</div>
                <div class="text-success small">€${property.price.toLocaleString('it-IT', {minimumFractionDigits: 2})}</div>
            </div>
        `).join('');
        resultsContainer.innerHTML = html;
    }

    resultsContainer.style.display = 'block';
}

function hideSearchResults() {
    const resultsContainer = document.getElementById('search-results');
    if (resultsContainer) {
        resultsContainer.style.display = 'none';
    }
}

// Countdown timer functionality
function updateCountdownTimers() {
    const timers = document.querySelectorAll('.countdown-timer');
    timers.forEach(function(timer) {
        const endTime = new Date(timer.dataset.endTime);
        const now = new Date();
        const timeLeft = endTime - now;

        if (timeLeft <= 0) {
            timer.innerHTML = '<span class="text-danger">Terminata</span>';
            timer.classList.add('text-danger');
            return;
        }

        const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
        const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

        let timeString = '';
        if (days > 0) {
            timeString += `${days}g `;
        }
        if (hours > 0 || days > 0) {
            timeString += `${hours.toString().padStart(2, '0')}:`;
        }
        timeString += `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

        timer.textContent = timeString;

        // Add warning classes based on time remaining
        if (timeLeft < 3600000) { // Less than 1 hour
            timer.classList.add('text-danger', 'fw-bold');
        } else if (timeLeft < 86400000) { // Less than 1 day
            timer.classList.add('text-warning', 'fw-bold');
        }
    });
}

// Bidding functionality
function initializeBidding() {
    const bidForm = document.getElementById('bid-form');
    if (!bidForm) return;

    const auctionId = bidForm.dataset.auctionId;
    const bidInput = document.getElementById('bid-amount');
    const bidButton = document.getElementById('bid-button');
    const currentPriceElement = document.getElementById('current-price');

    // Update bid input placeholder with minimum bid
    if (bidInput) {
        const minimumBid = parseFloat(bidInput.dataset.minimumBid);
        bidInput.placeholder = `Minimo: €${minimumBid.toLocaleString('it-IT', {minimumFractionDigits: 2})}`;
        
        // Auto-set minimum bid when input is focused
        bidInput.addEventListener('focus', function() {
            if (!this.value) {
                this.value = minimumBid.toFixed(2);
            }
        });
    }

    // Handle bid submission
    if (bidForm) {
        bidForm.addEventListener('submit', function(event) {
            event.preventDefault();
            placeBid(auctionId, parseFloat(bidInput.value));
        });
    }

    // Poll for auction updates
    if (auctionId) {
        setInterval(function() {
            updateAuctionStatus(auctionId);
        }, 5000);
    }
}

function placeBid(auctionId, amount) {
    const bidButton = document.getElementById('bid-button');
    const originalText = bidButton.textContent;
    
    // Disable button and show loading
    bidButton.disabled = true;
    bidButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Invio offerta...';

    fetch(`/auctions/${auctionId}/bid`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.getAttribute('content')
        },
        body: JSON.stringify({ amount: amount })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update UI with new bid
            showBidSuccess(data);
            updateAuctionStatus(auctionId);
            
            // Clear input and reset to new minimum
            const bidInput = document.getElementById('bid-amount');
            bidInput.value = '';
            
            // Show success message
            showAlert('success', data.message);
        } else {
            showAlert('danger', data.message);
        }
    })
    .catch(error => {
        console.error('Bid error:', error);
        showAlert('danger', 'Errore durante l\'invio dell\'offerta. Riprova.');
    })
    .finally(() => {
        // Re-enable button
        bidButton.disabled = false;
        bidButton.textContent = originalText;
    });
}

function updateAuctionStatus(auctionId) {
    fetch(`/auctions/api/${auctionId}/status`)
        .then(response => response.json())
        .then(data => {
            // Update current price
            const currentPriceElement = document.getElementById('current-price');
            if (currentPriceElement && data.current_price) {
                currentPriceElement.textContent = `€${data.current_price.toLocaleString('it-IT', {minimumFractionDigits: 2})}`;
            }

            // Update bid count
            const bidCountElement = document.getElementById('bid-count');
            if (bidCountElement) {
                bidCountElement.textContent = data.total_bids;
            }

            // Update minimum bid
            const bidInput = document.getElementById('bid-amount');
            if (bidInput && data.current_price) {
                const minimumBid = data.current_price + parseFloat(bidInput.dataset.increment);
                bidInput.dataset.minimumBid = minimumBid;
                bidInput.placeholder = `Minimo: €${minimumBid.toLocaleString('it-IT', {minimumFractionDigits: 2})}`;
            }

            // Update winning bidder
            const winningBidderElement = document.getElementById('winning-bidder');
            if (winningBidderElement && data.winning_bidder) {
                winningBidderElement.textContent = data.winning_bidder;
            }
        })
        .catch(error => {
            console.error('Status update error:', error);
        });
}

function showBidSuccess(data) {
    // Create success animation or update
    const currentPriceElement = document.getElementById('current-price');
    if (currentPriceElement) {
        currentPriceElement.classList.add('text-success');
        setTimeout(() => {
            currentPriceElement.classList.remove('text-success');
        }, 2000);
    }
}

// Alert functionality
function showAlert(type, message) {
    const alertsContainer = document.getElementById('alerts-container') || document.querySelector('.container-fluid > .row > .col-12');
    
    const alertHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = alertHTML;
    const alertElement = tempDiv.firstElementChild;
    
    if (alertsContainer) {
        alertsContainer.insertBefore(alertElement, alertsContainer.firstChild);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertElement);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    }
}

// Infinite scroll functionality
function initializeInfiniteScroll() {
    const loadMoreButton = document.getElementById('load-more');
    if (!loadMoreButton) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !loadMoreButton.disabled) {
                loadMoreButton.click();
            }
        });
    }, {
        threshold: 0.1
    });

    observer.observe(loadMoreButton);
}

// Utility functions
function formatPrice(price) {
    return new Intl.NumberFormat('it-IT', {
        style: 'currency',
        currency: 'EUR'
    }).format(price);
}

function formatDate(dateString) {
    const options = { 
        year: 'numeric', 
        month: '2-digit', 
        day: '2-digit', 
        hour: '2-digit', 
        minute: '2-digit' 
    };
    return new Date(dateString).toLocaleDateString('it-IT', options);
}

// Export functions for global use
window.AsteImmobili = {
    placeBid,
    updateAuctionStatus,
    showAlert,
    formatPrice,
    formatDate
};