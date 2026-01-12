import {
  ConsoleTemplate,
  ThemeProvider,
} from '@pipecat-ai/voice-ui-kit';
import '@pipecat-ai/voice-ui-kit/dist/style.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ConsoleTemplate
        transportType="smallwebrtc"
        connectParams={{
          connectionUrl: '/api/offer',
          requestData: {
            patient_name: 'John Miller',
            device_ordered: 'wheelchair',
          },
        }}
      />
    </ThemeProvider>
  </StrictMode>
);
