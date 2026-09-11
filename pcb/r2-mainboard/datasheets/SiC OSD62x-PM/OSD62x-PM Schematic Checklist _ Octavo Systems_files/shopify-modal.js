/**
 * Shopify Modal JavaScript
 *
 * Handles modal functionality and product events for Shopify components
 */

// Listen for all Shopify-related events
document.addEventListener('DOMContentLoaded', function() {
    
    // Store the original addEventListener method
    const originalAddEventListener = EventTarget.prototype.addEventListener;
    
    // Override addEventListener to capture all events
    EventTarget.prototype.addEventListener = function(type, listener, options) {
      // Call the original method
      originalAddEventListener.call(this, type, listener, options);
      
      // Check if this is a Shopify event
      if (type.toLowerCase().includes('shopify')) {
        console.log(`🔵 Shopify Event Listener Added: ${type}`, {
          type: type,
          target: this,
          timestamp: new Date().toISOString()
        });
      }
    };
    
    // Also listen for events that are dispatched
    const originalDispatchEvent = EventTarget.prototype.dispatchEvent;
    EventTarget.prototype.dispatchEvent = function(event) {
      // Check if this is a Shopify event before dispatching
      if (event.type.toLowerCase().includes('shopify')) {
        console.log(`🔵 Shopify Event Dispatched: ${event.type}`, {
          event: event,
          detail: event.detail,
          target: event.target,
          currentTarget: event.currentTarget,
          timestamp: new Date().toISOString()
        });
      }
      
      // Call the original method
      return originalDispatchEvent.call(this, event);
    };

    // Listener for shopify-update-data event (working on body)
    document.body.addEventListener('shopify-update-data', function(event) {
      console.log('🟢 shopify-update-data event received:', event);
      
      // Placeholder constants
      const UPDATE_DELAY = 1000; // milliseconds
      const MAX_RETRIES = 3;
      const RETRY_INTERVAL = 500; // milliseconds
      const SUCCESS_THRESHOLD = 0.8; // 80% success rate
      
      // Placeholder logic
      const handleShopifyUpdateData = (eventData) => {
        // Get the selected variant from the event data
        let selectedVariant = eventData?.product?.selectedOrFirstAvailableVariant || eventData?.selectedVariant;

        
        // Get the selected variant from the shadow DOM
        const variantSelector = document.querySelector('shopify-variant-selector');
        let selectedRadio = null;
        
        if (variantSelector && variantSelector.shadowRoot) {
          // Access the shadow DOM and find the selected radio button
          selectedRadio = variantSelector.shadowRoot.querySelector('[part*="radio-selected"]');
        }
        

        
        // Check if the selected variant is disabled/unavailable
        const isVariantDisabled = selectedRadio && selectedRadio.getAttribute('part')?.includes('radio-disabled');
        
        // Get the buttons
        const addToCartButton = document.querySelector('.product-modal__add-button');
        const buyNowButton = document.querySelector('.product-modal__buy-button');
        
        if (isVariantDisabled) {
          // Disable buttons and update text
          if (addToCartButton) {
            addToCartButton.disabled = true;
            addToCartButton.textContent = 'Unavailable';
            addToCartButton.style.cursor = 'not-allowed';
          }
          if (buyNowButton) {
            buyNowButton.disabled = true;
            buyNowButton.textContent = 'Unavailable';
            buyNowButton.style.cursor = 'not-allowed';
          }
        } else {
          // Enable buttons and restore original text
          if (addToCartButton) {
            addToCartButton.disabled = false;
            addToCartButton.textContent = 'Add to cart';
            addToCartButton.style.cursor = 'pointer';
          }
          if (buyNowButton) {
            buyNowButton.disabled = false;
            buyNowButton.textContent = 'Buy now';
            buyNowButton.style.cursor = 'pointer';
          }
        }
      };
      
      // Execute the logic with the event data
      handleShopifyUpdateData(event.detail || event);
    }, true);

    console.log('🔴 Ready to capture Shopify events. shopify-update-data listener is active on body.');
});