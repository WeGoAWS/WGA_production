import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import axios from 'axios';
import markdownDirective from './directives/markdown-directive';

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.directive('markdown', markdownDirective);

app.mount('#app');

axios.defaults.withCredentials = true;
