// src/utils/markdown.ts

export function parseMarkdown(markdown: string): string {
    if (!markdown) return '';

    let html = markdown;

    html = html.replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>');

    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    html = html.replace(/### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/# (.*?)$/gm, '<h1>$1</h1>');

    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    html = html.replace(
        /\[(.*?)\]\((.*?)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    );

    html = html.replace(/^\s*[\-\*]\s+(.*?)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');

    let listCounter = 0;
    let inOrderedList = false;

    html = html
        .split('\n')
        .map((line) => {
            const orderedListMatch = line.match(/^\s*(\d+)\.\s+(.*?)$/);

            if (orderedListMatch) {
                if (!inOrderedList) {
                    inOrderedList = true;
                    listCounter = parseInt(orderedListMatch[1]);
                    return `<ol start="${listCounter}"><li>${orderedListMatch[2]}</li>`;
                } else {
                    listCounter++;
                    return `<li>${orderedListMatch[2]}</li>`;
                }
            } else if (inOrderedList && line.trim() === '') {
                inOrderedList = false;
                return '</ol>';
            } else if (inOrderedList) {
                return line;
            } else {
                return line;
            }
        })
        .join('\n');

    if (inOrderedList) {
        html += '</ol>';
    }

    html = html.replace(/<\/ol>\s*<ol[^>]*>/g, '');

    html = html.replace(/\n\s*\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<\/p><p><\/p><p>/g, '</p><p>');

    return html;
}

export function renderMarkdown(el: HTMLElement, markdown: string): void {
    if (!markdown) {
        el.innerHTML = '';
        return;
    }

    const html = parseMarkdown(markdown);
    el.innerHTML = html;
}
