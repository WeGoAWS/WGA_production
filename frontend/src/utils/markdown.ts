// src/utils/markdown.ts

export function parseMarkdown(markdown: string): string {
    if (!markdown) return '';

    let html = markdown;

    const codeBlocks: string[] = [];
    html = html.replace(/```([^`]+)```/g, (match, code) => {
        codeBlocks.push(`<pre><code>${code}</code></pre>`);
        return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
    });

    const inlineCodes: string[] = [];
    html = html.replace(/`([^`]+)`/g, (match, code) => {
        inlineCodes.push(`<code>${code}</code>`);
        return `__INLINE_CODE_${inlineCodes.length - 1}__`;
    });

    html = html.replace(/!\[(.*?)\]\((.*?)\)/g, (match, altText, url) => {
        const cleanUrl = url.trim();
        try {
            new URL(cleanUrl);
            return `<div class="markdown-image-container"><a href="${cleanUrl}" target="_blank" rel="noopener noreferrer"><img src="${cleanUrl}" alt="${altText}" class="markdown-image" /></a></div>`;
        } catch (e) {
            return match;
        }
    });

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

    codeBlocks.forEach((block, index) => {
        html = html.replace(`__CODE_BLOCK_${index}__`, block);
    });

    inlineCodes.forEach((code, index) => {
        html = html.replace(`__INLINE_CODE_${index}__`, code);
    });

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
