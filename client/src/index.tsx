import {
  ConsoleTemplate,
  ThemeProvider,
} from '@pipecat-ai/voice-ui-kit';
// Import styles directly from node_modules
import '../node_modules/@pipecat-ai/voice-ui-kit/dist/voice-ui-kit.css';
import './style.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';

// Coral logo component
const CoralLogo = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className="h-6 w-auto text-foreground"
  >
    <circle cx="12" cy="12" r="10.5" stroke="currentColor" />
    <circle cx="14.5" cy="12.5" r="8" stroke="currentColor" />
    <circle cx="17.5" cy="12.5" r="5" stroke="currentColor" />
  </svg>
);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ConsoleTemplate
        transportType="daily"
        title="Coral Voice Agent"
        logoComponent={<CoralLogo />}
        connectParams={{
          endpoint: '/api/connect',
          requestData: {
            patient_name: 'John Miller',
            device_ordered: 'wheelchair',
          },
        }}
      />
    </ThemeProvider>
  </StrictMode>
);
