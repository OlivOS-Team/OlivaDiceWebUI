import React from 'react';
import ReactDOM from 'react-dom/client';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '../index.css';
import { OlivaDiceApp } from './OlivaDiceApp';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><OlivaDiceApp /></React.StrictMode>,
);
