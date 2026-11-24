// Set this build setting separately for each deployment environment.
const origin = process.env.VP_API_ORIGIN;
if (origin && !/^https:\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)+$/.test(origin)) {
  throw new Error("VP_API_ORIGIN must be a bare HTTPS origin");
}
export const config = {
  framework: "vite",
  installCommand: "npm ci",
  buildCommand: "npm run build",
  outputDirectory: "dist",
  rewrites: [
    ...(origin
      ? [{ source: "/api/:path*", destination: origin + "/api/:path*" }]
      : []),
    ...[
      "/login",
      "/logout",
      "/suppliers/:path*",
      "/exceptions/:path*",
      "/organization",
    ].map((source) => ({ source, destination: "/index.html" })),
  ],
  headers: [
    {
      source: "/(.*)",
      headers: [
        {
          key: "Content-Security-Policy",
          value:
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        },
        { key: "Strict-Transport-Security", value: "max-age=31536000" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        {
          key: "Permissions-Policy",
          value: "camera=(), microphone=(), geolocation=()",
        },
      ],
    },
    {
      source: "/api/:path*",
      headers: [{ key: "Cache-Control", value: "private, no-store" }],
    },
  ],
};
