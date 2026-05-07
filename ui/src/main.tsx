import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000 } },
});

const router = createBrowserRouter([
  {
    path: "/login",
    lazy: async () => {
      const { Login } = await import("./auth/login");
      const Component = () => (
        <Login
          onSuccess={() => {
            window.location.href = "/graph/staging";
          }}
        />
      );
      return { Component };
    },
  },
  {
    path: "/",
    lazy: async () => ({ Component: (await import("./components/AppLayout")).AppLayout }),
    children: [
      { index: true, element: <Navigate to="/graph/staging" replace /> },
      {
        path: "graph/:env",
        lazy: async () => ({ Component: (await import("./views/graph/GraphView")).default }),
      },
      {
        path: "browse/:env",
        lazy: async () => ({
          Component: (await import("./views/ontology-browser/OntologyBrowser")).default,
        }),
      },
      {
        path: "chat",
        lazy: async () => ({ Component: (await import("./views/chat/ChatPage")).default }),
      },
      // Legacy redirects so deep-linked bookmarks don't 404
      { path: "ingest", element: <Navigate to="/chat" replace /> },
      { path: "ingest/:id", element: <Navigate to="/chat" replace /> },
      { path: "diff", element: <Navigate to="/graph/staging" replace /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
