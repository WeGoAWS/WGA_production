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

    // 순서 있는 목록 (개선된 버전)
    let listCounter = 0;
    let inOrderedList = false;

    // 줄 단위로 처리하여 넘버링 유지
    html = html
        .split('\n')
        .map((line) => {
            const orderedListMatch = line.match(/^\s*(\d+)\.\s+(.*?)$/);

            if (orderedListMatch) {
                // 새 목록 시작 또는 목록 계속
                if (!inOrderedList) {
                    inOrderedList = true;
                    listCounter = parseInt(orderedListMatch[1]);
                    return `<ol start="${listCounter}"><li>${orderedListMatch[2]}</li>`;
                } else {
                    listCounter++;
                    return `<li>${orderedListMatch[2]}</li>`;
                }
            } else if (inOrderedList && line.trim() === '') {
                // 빈 줄을 만나면 목록 종료
                inOrderedList = false;
                return '</ol>';
            } else if (inOrderedList) {
                // 목록 내 추가 내용
                return line;
            } else {
                // 일반 텍스트
                return line;
            }
        })
        .join('\n');

    // 목록이 열려있고 파일 끝에 도달한 경우 닫기
    if (inOrderedList) {
        html += '</ol>';
    }

    // 중첩된 ol 태그 정리
    html = html.replace(/<\/ol>\s*<ol[^>]*>/g, '');

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
