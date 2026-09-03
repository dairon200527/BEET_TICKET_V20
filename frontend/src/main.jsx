import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './styles/global.css';
import './components/ui/ui.css';
import './components/layout/layout.css';
import './pages/Login.css';
import './components/portal/portal.css';
import App from './App.jsx';
import { AuthProvider } from './context/AuthContext';
import { CooperativaProvider } from './context/CooperativaContext';
import { ToastProvider } from './context/ToastContext';
import { BreadcrumbProvider } from './components/layout/breadcrumbs';
import { AffiliateAuthProvider } from './context/AffiliateAuthContext';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CooperativaProvider>
          <AffiliateAuthProvider>
            <ToastProvider>
              <BreadcrumbProvider>
                <App />
              </BreadcrumbProvider>
            </ToastProvider>
          </AffiliateAuthProvider>
        </CooperativaProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
