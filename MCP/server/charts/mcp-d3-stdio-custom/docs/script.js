// D3 Chart MCP Server Documentation JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');
    
    function showSection(sectionId) {
        sections.forEach(s => s.classList.remove('active'));
        navLinks.forEach(l => l.classList.remove('active'));
        
        const section = document.getElementById(sectionId);
        const link = document.querySelector(`[data-section="${sectionId}"]`);
        
        if (section) section.classList.add('active');
        if (link) link.classList.add('active');
        
        localStorage.setItem('d3-chart-docs-section', sectionId);
    }
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const sectionId = this.getAttribute('data-section');
            showSection(sectionId);
        });
    });
    
    const savedSection = localStorage.getItem('d3-chart-docs-section');
    showSection(savedSection || 'overview');
});
