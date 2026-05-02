import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data is considered fresh for 4s — prevents duplicate requests fired
      // in quick succession (e.g. two components mounting at the same time).
      staleTime: 4_000,

      // Retry failed requests twice with default exponential backoff before
      // surfacing an error to the UI.
      retry: 2,

      // Stop polling automatically when the browser tab loses focus.
      // This is the primary reason to use React Query over raw setInterval:
      // your backend gets zero requests while the user is on another tab.
      refetchIntervalInBackground: false,
    },
  },
});
