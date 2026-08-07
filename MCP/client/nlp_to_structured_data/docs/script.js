// NLP to Structured Data Client Documentation - Navigation Script

// Navigation functionality
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all links and sections
            navLinks.forEach(l => l.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Show corresponding section
            const targetId = this.getAttribute('href').substring(1);
            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                targetSection.classList.add('active');
            }
        });
    });

    // Handle submenu navigation
    const submenuLinks = document.querySelectorAll('.nav-submenu .nav-link');
    submenuLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active from main nav
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Show agents section and scroll to specific agent
            sections.forEach(s => s.classList.remove('active'));
            const agentsSection = document.getElementById('agents');
            if (agentsSection) {
                agentsSection.classList.add('active');
            }
            
            // Scroll to specific agent
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});
