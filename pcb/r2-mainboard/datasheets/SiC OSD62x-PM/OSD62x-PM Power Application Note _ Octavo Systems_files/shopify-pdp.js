/**
 * Shopify PDP (Product Detail Page) JavaScript
 *
 * Handles product detail page functionality including quantity controls, accordion, and slider
 */

document.addEventListener('DOMContentLoaded', function() {
    initializePDPFunctionality();
});

function initializePDPFunctionality() {
    console.log('Initializing Shopify PDP functionality');
    
    // Initialize quantity controls
    initializeQuantityControls();
    
    // Initialize accordion functionality
    initializeProductAccordion();
    
    // Initialize product slider
    initializeProductSlider();
}

/** Quantity increment/decrement functions **/
let cartQuantity = 1;

function initializeQuantityControls() {
    // Bind click events to quantity buttons
    const decreaseButton = document.querySelector('.decrease');
    const increaseButton = document.querySelector('.increase');
    
    if (decreaseButton) {
        decreaseButton.addEventListener('click', decreaseValue);
    }
    
    if (increaseButton) {
        increaseButton.addEventListener('click', increaseValue);
    }
}

function decreaseValue() {
    const countDisplay = document.getElementById('single-product__count');
    if (cartQuantity > 1) {
        countDisplay.textContent = --cartQuantity;
    }
}

function increaseValue() {
    const countDisplay = document.getElementById('single-product__count');
    countDisplay.textContent = ++cartQuantity;
}

/** Product Card Accordion **/
function initializeProductAccordion() {
    const accordionHeaders = document.querySelectorAll('.single-product__accordion__header');
    
    accordionHeaders.forEach(header => {
        header.addEventListener('click', shopifyToggleAccordion);
    });
}

function shopifyToggleAccordion(event) {
    const block = document.querySelector(event.currentTarget.dataset.toggle);
    if (!block) return;
    
    event.currentTarget.classList.toggle('active');
    block.style.maxHeight = event.currentTarget.classList.contains('active') ? `${block.scrollHeight}px` : '';
}

/** Product Slider (You may also like section) **/
function initializeProductSlider() {
    const prevButton = document.querySelector('.collection__slider-button.prev');
    const nextButton = document.querySelector('.collection__slider-button.next');
    
    if (prevButton) {
        prevButton.addEventListener('click', () => moveSlider(-1));
    }
    
    if (nextButton) {
        nextButton.addEventListener('click', () => moveSlider(1));
    }
}

function moveSlider(direction) {
    const slider = document.getElementById('collection__product-slider');
    if (!slider) return;

    const scrollAmount = 300;
    const currentScroll = slider.scrollLeft;
    const newScroll = currentScroll + (direction * scrollAmount);

    // Smooth scroll to the new position
    slider.scrollTo({
        left: newScroll,
        behavior: 'smooth'
    });
}

// Make functions available globally for PHP onclick handlers
window.decreaseValue = decreaseValue;
window.increaseValue = increaseValue;
window.shopifyToggleAccordion = shopifyToggleAccordion;
window.moveSlider = moveSlider;