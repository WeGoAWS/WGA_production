// src/directives/markdown-directive.ts
import type { DirectiveBinding } from 'vue';
import { renderMarkdown } from '@/utils/markdown';

// Vue 디렉티브 정의
export default {
    mounted(el: HTMLElement, binding: DirectiveBinding) {
        // 마크다운 텍스트 렌더링
        renderMarkdown(el, binding.value);
    },
    updated(el: HTMLElement, binding: DirectiveBinding) {
        // 값이 변경되면 다시 렌더링
        renderMarkdown(el, binding.value);
    },
};
