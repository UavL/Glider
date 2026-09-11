/**
 * Shopify Pagination JavaScript
 *
 * Handles pagination functionality for Shopify collections
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize pagination handlers
    initializePaginationHandlers();
});

function initializePaginationHandlers() {
    // Add event listener for the shopify-list-context-update event to toggle pagination states
    document.addEventListener(
        "shopify-list-context-update",
        (event) => {
            // Find all pagination containers
            const paginationContainers = document.querySelectorAll(".collection-pagination");
            
            paginationContainers.forEach((paginationContainer) => {
                // Find associated list ID from the container's buttons
                const previousButton = paginationContainer.querySelector(".pagination-button--previous");
                const nextButton = paginationContainer.querySelector(".pagination-button--next");
                
                if (!previousButton || !nextButton) return;
                
                const { hasNextPage, hasPreviousPage } = event.detail;
                
                // Hide the entire pagination container if there are no next or previous pages
                if (!hasNextPage && !hasPreviousPage) {
                    paginationContainer.style.display = "none";
                } else {
                    // Show the pagination container and manage button states
                    paginationContainer.style.display = "flex";
                    
                    if (!hasNextPage) {
                        nextButton.setAttribute("disabled", "true");
                    } else {
                        nextButton.removeAttribute("disabled");
                    }
                    if (!hasPreviousPage) {
                        previousButton.setAttribute("disabled", "true");
                    } else {
                        previousButton.removeAttribute("disabled");
                    }
                }
                
                console.log('Pagination event listener processed for container:', paginationContainer);
            });
        },
    );
    
    console.log('Pagination handlers initialized successfully');
}

// Global pagination functions that can be called from PHP-generated onclick handlers
window.handlePaginationClick = function(listId, direction) {
    const listElement = document.getElementById(listId);
    if (!listElement) {
        console.error('List element not found:', listId);
        return;
    }
    
    if (direction === 'next') {
        listElement.nextPage();
    } else if (direction === 'previous') {
        listElement.previousPage();
    }
    
    // Scroll to top after pagination
    window.scrollTo(0, 0);
};