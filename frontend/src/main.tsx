import { createRoot } from "react-dom/client";
import {
  createBrowserRouter,
  RouterProvider,
  redirect,
} from "react-router-dom";
import {
  api,
  Shell,
  Home,
  Directory,
  Detail,
  Editor,
  Login,
  Failure,
  signIn,
  manage,
  save,
} from "./workspace";
import { Queue, ExceptionDetail } from "./Exceptions";
import "./style.css";
const router = createBrowserRouter([
  { path: "/login", Component: Login, action: signIn },
  {
    path: "/",
    Component: Shell,
    ErrorBoundary: Failure,
    loader: () => api("/account"),
    children: [
      {
        path: "exceptions",
        Component: Queue,
        loader: async ({ request }) => {
          const [data, members] = await Promise.all([
            api("/exceptions" + new URL(request.url).search),
            api("/exceptions/members"),
          ]);
          return { data, members };
        },
      },
      {
        path: "exceptions/:fid",
        Component: ExceptionDetail,
        loader: async ({ params, request }) => {
          const [d, members] = await Promise.all([
            api("/exceptions/" + params.fid + new URL(request.url).search),
            api("/exceptions/members"),
          ]);
          return { d, members };
        },
      },
      { index: true, Component: Home, loader: () => api("/dashboard") },
      {
        path: "logout",
        action: async () => {
          await api("/logout", { method: "POST" });
          return redirect("/login");
        },
      },
      {
        path: "suppliers",
        Component: Directory,
        loader: async ({ request }) => {
          const params = new URL(request.url).searchParams;
          const q = params.get("q") || "",
            archived = params.get("archived") === "true" ? "true" : "false",
            page = Math.max(1, Number(params.get("page")) || 1);
          return {
            q,
            archived,
            page,
            rows: await api(
              "/suppliers?" +
                new URLSearchParams({ q, archived, page: String(page) }),
            ),
          };
        },
      },
      {
        path: "suppliers/new",
        Component: Editor,
        action: save,
        loader: () => null,
      },
      {
        path: "suppliers/:id/edit",
        Component: Editor,
        action: save,
        loader: ({ params }) => api("/suppliers/" + params.id),
      },
      {
        path: "suppliers/:id",
        Component: Detail,
        action: manage,
        loader: async ({ params, request }) => {
          const page = Math.max(
            1,
            Number(new URL(request.url).searchParams.get("documents")) || 1,
          );
          const base = "/suppliers/" + params.id;
          const [s, docs] = await Promise.all([
            api(base),
            api(base + "/documents?page=" + page),
          ]);
          return { s, docs, page };
        },
      },
    ],
  },
]);
createRoot(document.getElementById("root")!).render(
  <RouterProvider router={router} />,
);
