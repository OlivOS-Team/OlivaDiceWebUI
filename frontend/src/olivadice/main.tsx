import React from 'react';
import ReactDOM from 'react-dom/client';
import '../index.css';
import { OlivaDiceApp } from './OlivaDiceApp';
import { ConfirmProvider } from './ui';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><ConfirmProvider><OlivaDiceApp /></ConfirmProvider></React.StrictMode>,
);
