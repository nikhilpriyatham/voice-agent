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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ConsoleTemplate
        transportType="daily"
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
