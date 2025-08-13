document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    setupSmoothScrolling();
    setupScrollSpy();
    setupScrollAnimations();
    highlightCode();
});

function setupSmoothScrolling() {
    const navLinks = document.querySelectorAll('a[href^="#"]');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
}

function setupScrollSpy() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${id}`) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }, { rootMargin: '-30% 0px -70% 0px' });

    sections.forEach(section => {
        observer.observe(section);
    });
}

function setupScrollAnimations() {
    const sections = document.querySelectorAll('.content-section');

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1
    });

    sections.forEach(section => {
        observer.observe(section);
    });
}

function highlightCode() {
    const codeBlocks = document.querySelectorAll('pre code.language-python');
    const keywordRegex = new RegExp('\\b(from|import|class|def|return|async|await|yield|with|as|if|elif|else|try|except|finally|raise|for|in|while)\\b', 'g');
    const classRegex = new RegExp('\\b([A-Z][a-zA-Z0-9_]*)\\b', 'g');
    const functionRegex = new RegExp('([a-z_][a-zA-Z0-9_]*)\\(', 'g');
    const commentRegex = new RegExp('#.*$', 'gm');
    const stringRegex = new RegExp('(\".*?\")|(\'.*?\')', 'g');

    codeBlocks.forEach(block => {
        let html = block.innerHTML;

        html = html.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        
        html = html.replace(commentRegex, '<span class="comment">$&</span>');
        html = html.replace(keywordRegex, '<span class="keyword">$&</span>');
        html = html.replace(stringRegex, '<span class="string">$&</span>');
        html = html.replace(classRegex, (match, p1) => {

            if (new RegExp('class-name|keyword').test(match)) return match;
            return `<span class="class-name">${p1}</span>`;
        });
        html = html.replace(functionRegex, '<span class="function">$1</span>(');

        block.innerHTML = html;
    });
}
