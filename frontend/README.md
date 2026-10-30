# RecallDSA frontend

The frontend is a React single-page app served by Vite. Run `npm run dev` from
this directory for local development and `npm run build` for a production build.

## Progressive web app

Production builds include a web app manifest and register `public/sw.js` after
the page loads. The service worker caches the app shell and static build assets
so the interface can reopen offline; API data and authenticated requests still
require a network connection. Installability and service-worker behavior
require HTTPS in production (localhost is supported for development).
