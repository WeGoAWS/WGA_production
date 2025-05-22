// src/directives/markdown-directive.ts
import type { DirectiveBinding } from 'vue';
import { renderMarkdown } from '@/utils/markdown';

export default {
    mounted(el: HTMLElement, binding: DirectiveBinding) {
        renderMarkdown(el, binding.value);
    },
    updated(el: HTMLElement, binding: DirectiveBinding) {
        renderMarkdown(el, binding.value);
    },
};
