import {
  ConsoleTemplate,
  ThemeProvider,
} from '@pipecat-ai/voice-ui-kit';
import '@pipecat-ai/voice-ui-kit/styles.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

//@ts-ignore - fontsource-variable/geist is not typed
import '@fontsource-variable/geist';
//@ts-ignore - fontsource-variable/geist is not typed
import '@fontsource-variable/geist-mono';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ConsoleTemplate
        transportType="smallwebrtc"
        onConnect={async () => {
          // This is called for the initial connection setup
          // The WebRTC offer will be sent to /noop which is proxied to /api/offer
          const response = await fetch('/api/offer', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              patient_name: 'John Miller',
              device_ordered: 'wheelchair',
            }),
          });
          return response;
        }}
        clientOptions={{
          params: {
            patient_name: 'John Miller',
            device_ordered: 'wheelchair',
          },
        } as any}
      />
    </ThemeProvider>
  </StrictMode>
);
