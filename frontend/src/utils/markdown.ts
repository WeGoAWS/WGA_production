// src/utils/markdown.ts
// 간단한 마크다운 변환 유틸리티

// 기본적인 마크다운 문법 변환 (라이브러리 없이 간단하게 구현)
export function parseMarkdown(markdown: string): string {
    if (!markdown) return '';

    let html = markdown;

    // 코드 블록 (```)
    html = html.replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>');

    // 인라인 코드 (`)
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 헤더 (###, ##, #)
    html = html.replace(/### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/# (.*?)$/gm, '<h1>$1</h1>');

    // 볼드 (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 이탤릭 (*text*)
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // 링크 [text](url)
    html = html.replace(
        /\[(.*?)\]\((.*?)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    );

    // 순서 없는 목록
    html = html.replace(/^\s*[\-\*]\s+(.*?)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');

    // 순서 있는 목록
    html = html.replace(/^\s*\d+\.\s+(.*?)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*?<\/li>)/gs, '<ol>$1</ol>');

    // 단락 (개행)
    html = html.replace(/\n\s*\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<\/p><p><\/p><p>/g, '</p><p>');

    return html;
}

// 마크다운을 안전하게 렌더링하는 Vue 디렉티브용 함수
export function renderMarkdown(el: HTMLElement, markdown: string): void {
    if (!markdown) {
        el.innerHTML = '';
        return;
    }

    const html = parseMarkdown(markdown);
    el.innerHTML = html;
}
