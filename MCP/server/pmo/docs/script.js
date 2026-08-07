// PMO MCP Server Documentation JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');

    // Function to show a specific section
    function showSection(sectionId) {
        // Hide all sections
        sections.forEach(section => {
            section.classList.remove('active');
        });

        // Show the selected section
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.classList.add('active');
        }

        // Update active nav link
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.dataset.section === sectionId) {
                link.classList.add('active');
            }
        });

        // Scroll to top of content
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Add click event listeners to navigation links
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const sectionId = this.dataset.section;
            showSection(sectionId);
            
            // Update URL hash without scrolling
            history.pushState(null, null, '#' + sectionId);
        });
    });

    // Handle browser back/forward buttons
    window.addEventListener('popstate', function() {
        const hash = window.location.hash.substring(1);
        if (hash) {
            showSection(hash);
        } else {
            showSection('overview');
        }
    });

    // Show section from URL hash on load
    const initialHash = window.location.hash.substring(1);
    if (initialHash) {
        showSection(initialHash);
    } else {
        showSection('overview');
    }
});
